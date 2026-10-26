"""Generate a batch of new dataset models (diagram + Event-B + Rodin project).

    python tools/generators/gen_batch.py --batch batch_02 --seed 20261023

Output (staging, before Rodin):  batches/<batch>/
    <Case>/<Case>.drawio.xml   generated sequence diagram
    <Case>/<Case>_EventB.txt   Event-B text exactly as the converter writes it
    <Case>/<Case>_Rodin.zip    the matching Rodin project
    <Case>/meta.json           design intent, diagram error, expected failing POs
    Rodin_Import_<batch>.zip   all projects in one archive for Rodin's
                               "Existing Projects into Workspace -> Select archive file"

Every diagram is parsed back with ChronoSeq-B and compared with the intended
structure (senders, receivers, data, timing, guard conditions, now-bindings);
a mismatch discards the sample and a new one is drawn from the next seed.
After Rodin has proved the batch, run tools/generators/integrate_batch.py.
"""
import argparse, io, json, os, random, re, shutil, sys, tempfile, zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(os.path.dirname(HERE))
PROJECT = os.path.dirname(DATASET)
sys.path.insert(0, PROJECT)
sys.path.insert(0, HERE)
import rodin_exporter                                                    # noqa: E402
from eventb_generator import apply_rules_1_and_2                         # noqa: E402
from xml_parser import (extract_detailed_sequence, get_message_warnings,  # noqa: E402
                        validate_sequence_diagram)
from drawio_builder import build                                         # noqa: E402
from eventb_mutation import (mutate_text, mutate_bum, init_action_label,  # noqa: E402
                             checkloop_event, count_consistency)

# (case name, objects, nouns used for message and data names)
DOMAINS = [
    ("BikeSharing", ["Rider", "BikeApp", "Dock", "PaymentHub"], ["Bike", "Ride", "Fee"]),
    ("PharmacyRefill", ["Patient", "PharmacyApp", "Pharmacist", "InsurerAPI"], ["Refill", "Prescription", "Claim"]),
    ("CampusWifiAccess", ["Student", "AccessPoint", "AuthRadius", "CampusNOC"], ["Session", "Token", "Quota"]),
    ("RestaurantReservation", ["Diner", "BookingSite", "HostStand", "KitchenDisplay"], ["Table", "Booking", "Menu"]),
    ("GarageGateControl", ["Car", "EntryGate", "GarageServer", "PayKiosk"], ["Ticket", "Slot", "Fee"]),
    ("CargoShipTracking", ["Shipper", "PortSystem", "Vessel", "CustomsDesk"], ["Container", "Manifest", "Berth"]),
    ("IrrigationZoneControl", ["Controller", "SoilProbe", "Valve", "WeatherAPI"], ["Moisture", "Schedule", "Zone"]),
    ("RideHailingSurge", ["Passenger", "RideApp", "PricingEngine", "DriverApp"], ["Fare", "Trip", "Surge"]),
    ("HomeSecurityAlarm", ["Sensor", "AlarmPanel", "MonitorCenter", "Owner"], ["Alert", "Zone", "Code"]),
    ("OnlineBankingOTP", ["Customer", "BankApp", "OTPService", "CoreLedger"], ["Transfer", "Otp", "Account"]),
    ("HospitalBedAllocation", ["Ward", "BedManager", "AdmissionDesk", "Porter"], ["Bed", "Patient", "Transfer"]),
    ("EVChargingSession", ["EVCar", "Charger", "CSMS", "BillingSvc"], ["Session", "Energy", "Tariff"]),
    ("SelfCheckoutLane", ["Shopper", "SelfCheckout", "ScaleUnit", "POSServer"], ["Item", "Basket", "Receipt"]),
    ("FlightCheckIn", ["Traveler", "CheckInKiosk", "AirlineDCS", "BagDrop"], ["Boarding", "Seat", "Bag"]),
    ("VideoStreaming", ["Viewer", "PlayerApp", "CDNEdge", "LicenseServer"], ["Stream", "Chunk", "License"]),
    ("TollPlazaETC", ["Vehicle", "TollGate", "ETCBackend", "Camera"], ["Toll", "Plate", "Account"]),
    ("SmartWasteBin", ["Bin", "Gateway", "FleetPlanner", "Truck"], ["Fill", "Route", "Pickup"]),
    ("DigitalLibraryAccess", ["Reader", "LibraryPortal", "DRMServer", "Publisher"], ["Ebook", "Loan", "License"]),
    ("RemotePatientMonitor", ["Wearable", "HomeHub", "ClinicServer", "Nurse"], ["Vital", "Alert", "Report"]),
    ("OnlineQuizGame", ["Player", "GameServer", "Leaderboard", "Matchmaker"], ["Answer", "Score", "Round"]),
    ("ConcertTicketQueue", ["Fan", "TicketSite", "QueueServer", "PaymentGW"], ["Seat", "Ticket", "Queue"]),
    ("FleetFuelCard", ["Driver", "FuelPump", "CardIssuer", "FleetMgr"], ["Fuel", "Card", "Limit"]),
    ("GreenhouseLighting", ["Scheduler", "LightCtrl", "LuxSensor", "PowerMeter"], ["Light", "Lux", "Energy"]),
    ("ApartmentIntercom", ["Visitor", "IntercomPanel", "ResidentApp", "DoorRelay"], ["Call", "Door", "Code"]),
    ("WarehousePicking", ["Picker", "HandScanner", "WMS", "Conveyor"], ["Order", "Bin", "Tote"]),
    ("TelemedicineVisit", ["Patient", "TeleApp", "Doctor", "EHRSystem"], ["Visit", "Note", "Prescription"]),
    ("AirportShuttle", ["Passenger", "ShuttleApp", "Dispatcher", "Shuttle"], ["Seat", "Pickup", "Route"]),
    ("CropDroneSpraying", ["Farmer", "DroneCtrl", "SprayDrone", "FieldMap"], ["Mission", "Spray", "Area"]),
    ("SchoolBusTracking", ["Parent", "BusApp", "GPSUnit", "SchoolOffice"], ["Bus", "Stop", "Arrival"]),
    ("InventoryReorder", ["Shelf", "StockSystem", "Supplier", "Buyer"], ["Stock", "Order", "Invoice"]),
    ("CafeLoyaltyPoints", ["Customer", "PosTerminal", "LoyaltyAPI", "CRM"], ["Point", "Reward", "Visit"]),
    ("CloudBackupJob", ["Agent", "BackupServer", "StorageNode", "AdminConsole"], ["Snapshot", "Chunk", "Job"]),
    ("SmartStreetLight", ["LampNode", "Gateway", "CityCMS", "MotionSensor"], ["Lamp", "Dim", "Fault"]),
    ("EventCheckInQR", ["Attendee", "ScannerApp", "EventServer", "BadgePrinter"], ["Pass", "Badge", "Entry"]),
    ("PetDoorController", ["PetTag", "PetDoor", "HomeHub", "OwnerApp"], ["Entry", "Curfew", "Log"]),
    ("WaterLeakDetection", ["LeakSensor", "ShutoffValve", "HomeHub", "PlumberSvc"], ["Leak", "Valve", "Ticket"]),
    ("MuseumAudioGuide", ["Visitor", "GuideApp", "BeaconNode", "ContentServer"], ["Exhibit", "Audio", "Tour"]),
    ("FoodTruckOrdering", ["Customer", "OrderTablet", "Kitchen", "PickupScreen"], ["Order", "Dish", "Pickup"]),
    ("DormLaundry", ["Student", "LaundryApp", "Washer", "PaymentHub"], ["Machine", "Cycle", "Credit"]),
    ("FactoryQualityGate", ["Conveyor", "VisionCam", "QCServer", "RejectArm"], ["Part", "Defect", "Batch"]),
    ("GlucoseMeterSync", ["Meter", "PhoneApp", "CloudLog", "Doctor"], ["Reading", "Insulin", "Alert"]),
    ("AirQualityMonitor", ["AQSensor", "Gateway", "CityPortal", "Purifier"], ["Pm", "Alert", "Fan"]),
    ("CarWashBooking", ["Driver", "WashApp", "WashBay", "Cashier"], ["Slot", "Wash", "Payment"]),
    ("SmartFridgeInventory", ["Fridge", "HomeApp", "GroceryAPI", "Owner"], ["Item", "Expiry", "Order"]),
    ("CourseAutoGrading", ["Student", "LMS", "AutoGrader", "Instructor"], ["Submission", "Grade", "Feedback"]),
    ("HotelRoomService", ["Guest", "RoomTablet", "KitchenOrder", "ServiceStaff"], ["Meal", "Order", "Bill"]),
    ("LiftMaintenance", ["Technician", "LiftCtrl", "MaintPortal", "SafetyLock"], ["Fault", "Job", "Lock"]),
    ("RailFareGate", ["Commuter", "FareGate", "FareServer", "TopUpKiosk"], ["Card", "Fare", "Balance"]),
    ("SolarPanelMonitor", ["Inverter", "SolarHub", "GridMeter", "OwnerApp"], ["Power", "Fault", "Export"]),
    ("MailroomSorting", ["Courier", "Sorter", "MailServer", "Resident"], ["Parcel", "Slot", "Notice"]),
    # ── second set (batch_03 onwards) ──
    ("ParkingPermitPortal", ["Resident", "PermitPortal", "CityDB", "Enforcer"], ["Permit", "Plate", "Fine"]),
    ("BloodDonationDrive", ["Donor", "DonorApp", "BloodCenter", "LabTech"], ["Donation", "Slot", "Screening"]),
    ("SmartBeehive", ["HiveSensor", "HiveGateway", "BeeCloud", "Beekeeper"], ["Weight", "Swarm", "Honey"]),
    ("TaxFilingPortal", ["Taxpayer", "FilingPortal", "RevenueDept", "BankAPI"], ["Return", "Refund", "Payment"]),
    ("OnlineDonation", ["Donor", "CharitySite", "PaymentGW", "CRM"], ["Gift", "Receipt", "Campaign"]),
    ("SmartMirrorFitness", ["User", "SmartMirror", "CoachAI", "CloudSync"], ["Workout", "Rep", "Plan"]),
    ("JobApplicationPortal", ["Applicant", "CareerSite", "ATS", "Recruiter"], ["Resume", "Interview", "Offer"]),
    ("PrintFleetMonitor", ["PrinterNode", "PrintServer", "TonerVendor", "ITDesk"], ["Toner", "Job", "Alert"]),
    ("BoardingSchoolGate", ["Student", "GateKiosk", "SchoolDB", "GuardianApp"], ["Pass", "Exit", "Notice"]),
    ("MeetingRoomDisplay", ["Organizer", "RoomDisplay", "CalendarAPI", "Facilities"], ["Meeting", "Room", "Checkin"]),
    ("DigitalVotingBooth", ["Voter", "VotingTerminal", "ElectionServer", "Auditor"], ["Ballot", "Vote", "Receipt"]),
    ("PortCraneControl", ["CraneOperator", "CraneCtrl", "TerminalOS", "Truck"], ["Container", "Lift", "Slot"]),
    ("SmartAquarium", ["TankSensor", "AquaHub", "Feeder", "OwnerApp"], ["Ph", "Feed", "Light"]),
    ("RentalScooter", ["Rider", "ScooterApp", "Scooter", "ParkingZone"], ["Unlock", "Trip", "Battery"]),
    ("FarmMilkingRobot", ["Cow", "MilkRobot", "HerdServer", "Farmer"], ["Milk", "Yield", "Health"]),
    ("IoTDoorbell", ["Visitor", "Doorbell", "CloudRelay", "OwnerApp"], ["Ring", "Video", "Message"]),
    ("PharmacyDelivery", ["Pharmacist", "DeliveryApp", "Courier", "Patient"], ["Package", "Route", "Signature"]),
    ("CustomsClearance", ["Importer", "CustomsPortal", "Inspector", "Warehouse"], ["Declaration", "Duty", "Release"]),
    ("BusTicketBooking", ["Passenger", "BusApp", "OperatorAPI", "PaymentHub"], ["Seat", "Ticket", "Route"]),
    ("ThermalCameraScreening", ["ThermalCam", "EdgeNode", "FacilityApp", "Guard"], ["Scan", "Fever", "Alert"]),
    ("StudentAttendance", ["Student", "ClassScanner", "AttendanceDB", "Teacher"], ["Checkin", "Absence", "Report"]),
    ("CloudCIPipeline", ["Developer", "GitServer", "CIRunner", "Registry"], ["Commit", "Build", "Image"]),
    ("LiftEmergencyCall", ["Passenger", "LiftPhone", "CallCenter", "Technician"], ["Call", "Fault", "Dispatch"]),
    ("GolfCartFleet", ["Golfer", "CartApp", "GolfCart", "ProShop"], ["Cart", "Round", "Fee"]),
    ("SmartBabyMonitor", ["BabyCam", "HomeHub", "ParentApp", "CloudAI"], ["Cry", "Climate", "Alert"]),
    ("RecyclingKiosk", ["Customer", "RecycleKiosk", "Compactor", "RewardAPI"], ["Bottle", "Credit", "Voucher"]),
    ("TrainSeatReservation", ["Traveler", "RailApp", "SeatServer", "Conductor"], ["Seat", "Ticket", "Coach"]),
    ("HospitalPharmacyRobot", ["Nurse", "DispenseRobot", "PharmacyDB", "Ward"], ["Dose", "Drawer", "Order"]),
    ("CanteenPayment", ["Student", "CanteenPOS", "WalletAPI", "Parent"], ["Meal", "Balance", "Topup"]),
    ("ForestFireSensor", ["FireSensor", "LoRaGateway", "FireCenter", "Ranger"], ["Smoke", "Alert", "Patrol"]),
    ("MarketplaceEscrow", ["Buyer", "Marketplace", "EscrowSvc", "Seller"], ["Order", "Escrow", "Dispute"]),
    ("CarRentalReturn", ["Renter", "ReturnKiosk", "FleetServer", "Inspector"], ["Car", "Damage", "Invoice"]),
    ("VaccineColdBox", ["ColdBox", "Gateway", "HealthHub", "Courier"], ["Vaccine", "Reading", "Alarm"]),
    ("SmartLibraryShelf", ["ShelfReader", "LibraryHub", "CatalogDB", "Librarian"], ["Book", "Shelf", "Hold"]),
    ("DentalAppointment", ["Patient", "ClinicApp", "Dentist", "InsurerAPI"], ["Appointment", "Treatment", "Claim"]),
    ("WindTurbineMonitor", ["Turbine", "SCADA", "GridOperator", "Technician"], ["Rpm", "Fault", "Power"]),
    ("PassportRenewalKiosk", ["Citizen", "PassportKiosk", "ImmigrationDB", "PrintCenter"], ["Photo", "Form", "Passport"]),
    ("SmartGymLocker", ["Member", "LockerPanel", "GymServer", "FrontDesk"], ["Locker", "Pin", "Session"]),
    ("DroneTrafficControl", ["DronePilot", "UTMServer", "Drone", "AirAuthority"], ["Flight", "Corridor", "Permit"]),
    ("WarehouseForklift", ["Forklift", "FleetCtrl", "WMS", "SafetyBeacon"], ["Pallet", "Route", "Aisle"]),
    ("LabEquipmentBooking", ["Researcher", "BookingPortal", "Instrument", "LabManager"], ["Slot", "Sample", "Run"]),
    ("ParcelReturnDropoff", ["Customer", "DropBox", "ReturnsAPI", "Retailer"], ["Return", "Label", "Refund"]),
    ("CenterPivotIrrigation", ["PivotCtrl", "FieldSensor", "FarmCloud", "Farmer"], ["Water", "Sector", "Rain"]),
    ("TradingOrderGateway", ["Trader", "OrderGateway", "Exchange", "RiskEngine"], ["Order", "Fill", "Margin"]),
    ("MedicalImagingPACS", ["Radiologist", "Modality", "PACSServer", "RIS"], ["Study", "Image", "Report"]),
    ("FireSprinklerSystem", ["SmokeDetector", "FirePanel", "SprinklerValve", "FireDept"], ["Fire", "Valve", "Alarm"]),
    ("HomeEnergyBattery", ["BatteryPack", "EnergyHub", "GridMeter", "OwnerApp"], ["Charge", "Export", "Tariff"]),
    ("CampusShuttleBus", ["Student", "ShuttleApp", "BusDriver", "TransitOffice"], ["Stop", "Seat", "Arrival"]),
    ("ConferenceBadgeScan", ["Attendee", "BadgeScanner", "EventCRM", "Exhibitor"], ["Badge", "Lead", "Session"]),
    ("PatientIntakeForm", ["Patient", "KioskTablet", "HISServer", "Nurse"], ["Form", "Consent", "Record"]),
    # ── third set (batch_04 onwards) ──
    ("StreetParkingMeter", ["Driver", "ParkingMeter", "CityPayAPI", "Warden"], ["Session", "Fee", "Fine"]),
    ("AmbulanceRouting", ["Paramedic", "AmbulanceUnit", "DispatchCenter", "ERDesk"], ["Route", "Patient", "Eta"]),
    ("SmartPillBox", ["PillBox", "CareApp", "Caregiver", "PharmacyAPI"], ["Dose", "Reminder", "Refill"]),
    ("RoboticLawnMower", ["Mower", "BaseStation", "HomeApp", "RainSensor"], ["Zone", "Blade", "Dock"]),
    ("PodcastPublishing", ["Creator", "StudioApp", "HostingSvc", "Directory"], ["Episode", "Feed", "Audio"]),
    ("FlightCrewScheduling", ["CrewMember", "CrewPortal", "Scheduler", "OpsCenter"], ["Duty", "Roster", "Swap"]),
    ("SmartShoppingCart", ["Shopper", "SmartCart", "StoreServer", "Checkout"], ["Item", "Coupon", "Total"]),
    ("EVBatterySwap", ["Rider", "SwapStation", "BatteryCloud", "Technician"], ["Battery", "Swap", "Credit"]),
    ("MarathonTiming", ["Runner", "ChipMat", "TimingServer", "ResultsBoard"], ["Split", "Finish", "Bib"]),
    ("HotelKeylessEntry", ["Guest", "PhoneKey", "DoorLock", "PMSServer"], ["Key", "Room", "Access"]),
    ("SmartRainGauge", ["RainGauge", "WeatherHub", "FloodCenter", "Resident"], ["Rainfall", "Warning", "Level"]),
    ("InsuranceTelematics", ["CarDongle", "TelematicsHub", "InsurerAPI", "Driver"], ["Trip", "Rating", "Premium"]),
    ("BankBranchQueue", ["Customer", "QueueKiosk", "TellerApp", "BranchDisplay"], ["Ticket", "Counter", "Service"]),
    ("MobileTopUp", ["Subscriber", "TopUpApp", "TelcoGW", "PaymentHub"], ["Topup", "Credit", "Bundle"]),
    ("SatelliteGroundStation", ["Operator", "GroundStation", "Satellite", "MissionCtrl"], ["Pass", "Telemetry", "Command"]),
    ("PrisonVisitBooking", ["Visitor", "VisitPortal", "PrisonDB", "Officer"], ["Visit", "Slot", "Clearance"]),
    ("ArtGalleryTicketing", ["Visitor", "GalleryApp", "TicketDesk", "Turnstile"], ["Ticket", "Entry", "Tour"]),
    ("GroceryDeliverySlot", ["Customer", "GroceryApp", "SlotEngine", "Driver"], ["Slot", "Order", "Delivery"]),
    ("SmartHelmetMining", ["Miner", "SmartHelmet", "MineGateway", "SafetyOfficer"], ["Gas", "Location", "Alarm"]),
    ("RemoteExamProctor", ["Candidate", "ExamClient", "ProctorSvc", "Invigilator"], ["Exam", "Flag", "Session"]),
    ("TrafficSignalPriority", ["Bus", "TransitSignal", "TrafficCenter", "Intersection"], ["Priority", "Green", "Lane"]),
    ("HomeOxygenConcentrator", ["Concentrator", "HomeHub", "RespiratoryTeam", "Patient"], ["Flow", "Purity", "Alert"]),
    ("SmartVendingFridge", ["Customer", "FridgeLock", "VendorCloud", "Restocker"], ["Item", "Charge", "Restock"]),
    ("CoworkingDeskBooking", ["Member", "DeskApp", "SpaceServer", "FrontDesk"], ["Desk", "Booking", "Pass"]),
    ("LivestockFeeder", ["FeederUnit", "FarmHub", "FeedSupplier", "Rancher"], ["Feed", "Ration", "Order"]),
    ("PipelineLeakSCADA", ["FlowMeter", "RTU", "SCADAServer", "FieldCrew"], ["Pressure", "Leak", "Work"]),
    ("ArchiveDocumentScan", ["Clerk", "ScanStation", "DMSServer", "Auditor"], ["Document", "Batch", "Index"]),
    ("ChildcareCheckin", ["Parent", "CheckinTablet", "DaycareDB", "Teacher"], ["Child", "Pickup", "Note"]),
    ("AirportSecurityLane", ["Passenger", "ScannerLane", "SecurityServer", "Officer"], ["Tray", "Scan", "Alert"]),
    ("SmartTrashCompactor", ["Compactor", "CityGateway", "WasteDepot", "Collector"], ["Level", "Route", "Service"]),
    ("PhotoPrintKiosk", ["Customer", "PrintKiosk", "PhotoCloud", "LabPrinter"], ["Photo", "Print", "Order"]),
    ("MedicalTranscription", ["Doctor", "DictationApp", "SpeechAI", "EHR"], ["Dictation", "Transcript", "Note"]),
    ("GasStationPrepay", ["Driver", "PumpTerminal", "ForecourtCtrl", "PaymentGW"], ["Fuel", "Prepay", "Receipt"]),
    ("PublicWifiHotspot", ["User", "Hotspot", "CaptivePortal", "AAAServer"], ["Session", "Voucher", "Quota"]),
    ("OfficeLightingControl", ["OccupancySensor", "LightGateway", "BMS", "FacilityMgr"], ["Occupancy", "Dim", "Schedule"]),
    ("VeterinaryClinic", ["PetOwner", "VetApp", "Veterinarian", "LabSystem"], ["Appointment", "Vaccine", "Invoice"]),
    ("StadiumEntryGate", ["Fan", "StadiumGate", "TicketServer", "Steward"], ["Ticket", "Entry", "Seat"]),
    ("OnlineGroceryPicking", ["Picker", "PickApp", "StoreWMS", "Packer"], ["Order", "Item", "Bag"]),
    ("DisasterAlertBroadcast", ["SensorNet", "AlertServer", "CellBroadcast", "Citizen"], ["Quake", "Alert", "Shelter"]),
    ("SoilTestingLab", ["Farmer", "SampleKiosk", "LabLIMS", "Agronomist"], ["Sample", "Nutrient", "Report"]),
    ("ShipLockOperation", ["Captain", "LockControl", "CanalAuthority", "LockGate"], ["Lock", "Level", "Passage"]),
    ("ConcessionStandOrder", ["Customer", "ConcessionApp", "KitchenScreen", "Runner"], ["Snack", "Order", "Pickup"]),
    ("BuildingVisitorPass", ["Visitor", "LobbyKiosk", "AccessServer", "Host"], ["Pass", "Badge", "Visit"]),
    ("CraneLoadMonitor", ["LoadCell", "CraneCtrl", "SiteServer", "SafetyOfficer"], ["Load", "Limit", "Alarm"]),
    ("RuralTelehealthKiosk", ["Villager", "TeleKiosk", "RemoteDoctor", "Pharmacy"], ["Consult", "Vital", "Prescription"]),
    ("BulkSMSGateway", ["Marketer", "SMSPortal", "CarrierGW", "Subscriber"], ["Campaign", "Message", "Delivery"]),
    ("HospitalLabRequest", ["Physician", "OrderEntry", "LabLIS", "Phlebotomist"], ["Order", "Sample", "Result"]),
    ("SmartCurtainControl", ["Owner", "CurtainMotor", "HomeHub", "LightSensor"], ["Scene", "Position", "Lux"]),
    ("ParentalControlRouter", ["Parent", "HomeRouter", "FilterCloud", "ChildDevice"], ["Rule", "Block", "Report"]),
    ("SeaportPilotBooking", ["ShipAgent", "PilotPortal", "PilotStation", "Harbormaster"], ["Pilot", "Berth", "Arrival"]),
]

VERBS = ["request", "confirm", "notify", "update", "check", "send", "report", "approve", "cancel",
         "sync", "fetch", "validate", "assign", "release", "schedule", "log", "reserve", "query",
         "issue", "ack"]
SUFFIX = ["ID", "Info", "Data", "Code", "Ref", "Value"]
ENUM_VARS = ["phase", "mode", "tier", "grade", "stage"]
ENUM_VALS = [("LOW", "HIGH"), ("OK", "ERROR"), ("ACTIVE", "IDLE"), ("GREEN", "RED"),
             ("GOLD", "SILVER", "BRONZE"), ("FAST", "SLOW", "NORMAL"), ("MANUAL", "AUTO")]
NUM_VARS = ["score", "load", "temp", "gauge", "usage"]
FLAG_VARS = ["isVip", "hasKey", "online", "approved", "urgent"]
OPT_VARS = ["optIn", "needAck", "withExtra", "useCache", "express"]
LOOP_VARS = ["retryNo", "roundNo", "pollNo", "cycleNo", "attemptNo", "stepNo", "passNo"]
DUR_HI = [1, 2, 3, 5, 8, 10, 15, 20, 30, 60]

# 30 pass + 20 fail -> keeps the dataset at 60:40. Every model is the converter's output,
# unchanged: a fail model fails because its DIAGRAM is wrong, never because the Event-B
# was edited afterwards. The converter only emits typing invariants and inv5 (whose guard
# it always writes), so a diagram can make a PO fail in two ways only:
#   FIS  a duration written backwards {5..3} -> t_time :∈ 5..3 has no value to pick
#   WD   a condition "c mod k" on a loop counter -> needs c ≥ 0, which no invariant gives
# The "mutated"/"augmented" variants below plan_ops() were used for the first 48 models.
DIAGRAM_FAILS = {             # mtype: (inverted intervals, mod frame, interval inside a frame)
    "inverted1": (1, None, False), "inverted2": (2, None, False), "inverted3": (3, None, False),
    "inverted_frame": (1, None, True),
    "mod_alt": (0, "alt", False), "mod_opt": (0, "opt", False),
    "mod_inverted": (1, "any", False),
}
PLAN = ([("expected_pass", "plain", None)] * 30
        + [("expected_fail", "diagram_error", t) for t in
           ["inverted1"] * 4 + ["inverted2"] * 3 + ["inverted3"] * 2 + ["inverted_frame"] * 3
           + ["mod_alt"] * 3 + ["mod_opt"] * 3 + ["mod_inverted"] * 2])
CATEGORY = {"missing_helper": "non_inductive", "data_subset": "non_inductive",
            "rm_guard": "non_inductive", "rm_guard2": "non_inductive",
            "mod_alt": "non_inductive", "mod_opt": "non_inductive"}


# ── structure generation ─────────────────────────────────────────────────────
class ModelGen:
    def __init__(self, rng, domain, min_msgs=4, mod_mode=None):
        self.rng = rng
        self.mod_mode = mod_mode              # "alt" / "opt": put a "c mod k" frame inside a loop
        self.mod_used = False
        self.loop_stack = []
        self.min_msgs = min_msgs
        self.case, objs, self.nouns = domain
        self.objects = objs[:rng.choice([2, 3, 3, 4, 4])]
        self.max_msgs = rng.randint(6, 12)
        self.n = 0
        self.names, self.vars = set(), set()
        self.enum_pools = set()
        self.loops = []                       # (var, bound)
        self.used_now = False

    def pick_var(self, pool):
        free = [v for v in pool if v not in self.vars]
        v = self.rng.choice(free)
        self.vars.add(v)
        return v

    def msg(self):
        r = self.rng
        self.n += 1
        for _ in range(200):
            name = r.choice(VERBS) + r.choice(self.nouns)
            if name not in self.names:
                break
        self.names.add(name)
        a, b = r.sample(range(len(self.objects)), 2)
        data, x = None, r.random()
        if x < 0.55:
            data = [self.data_name()]
        elif x < 0.65:
            data = sorted({self.data_name(), self.data_name()})
        dur = (0, r.choice(DUR_HI)) if r.random() < 0.35 else None
        delay = r.choice([1, 2, 3, 5, 10]) if r.random() < 0.12 else None
        return {"t": "msg", "name": name, "data": data, "a": a, "b": b, "dur": dur,
                "delay": delay, "kind": "r" if r.random() < 0.25 else "f", "now": None}

    def data_name(self):
        noun = self.rng.choice(self.nouns)
        return noun[0].lower() + noun[1:] + self.rng.choice(SUFFIX)

    def allowed(self, level, anc):
        if level >= 3:
            return []
        kinds = ["opt", "loop", "alt", "par"]
        if "alt" in anc:          # an alt nested in an alt confuses branch-condition lookup
            kinds.remove("alt")
        if "opt" in anc:
            kinds.remove("opt")
        return kinds

    def block(self, level, anc, extra):
        """Elements that start and end with a message (keeps frames apart)."""
        elems = [self.msg()]
        if (self.mod_mode and not self.mod_used and anc and anc[-1] == "loop"
                and self.mod_mode in self.allowed(level, anc)):
            elems += [self.frame(level, anc, [self.mod_mode]), self.msg()]
        for _ in range(extra):
            kinds = self.allowed(level, anc)
            if kinds and self.n <= self.max_msgs - 3 and self.rng.random() < 0.4:
                elems += [self.frame(level, anc, kinds), self.msg()]
            elif self.n < self.max_msgs:
                elems.append(self.msg())
        return elems

    def frame(self, level, anc, kinds, prev_msg=None):
        r, t = self.rng, self.rng.choice(kinds)
        if t in ("opt", "alt") and self.mod_mode == t and self.loop_stack and not self.mod_used:
            self.mod_used = True
            v, k = self.loop_stack[-1], r.choice([2, 3, 4])
            conds = [f"{v} mod {k} == 0"] + ([f"{v} mod {k} != 0"] if t == "alt" else [])
            return {"t": "frame", "type": t, "conds": conds,
                    "branches": [self.block(level + 1, anc + [t], r.randint(0, 1)) for _ in conds]}
        if t == "opt":
            v = self.pick_var(OPT_VARS)
            return {"t": "frame", "type": "opt", "conds": [f"{v} == 1"],
                    "branches": [self.block(level + 1, anc + ["opt"], r.randint(0, 1))]}
        if t == "loop":
            v, bound = self.pick_var(LOOP_VARS), r.randint(2, 12)
            self.loops.append((v, bound))
            self.loop_stack.append(v)
            body = self.block(level + 1, anc + ["loop"], r.randint(0, 2))
            self.loop_stack.pop()
            return {"t": "frame", "type": "loop", "conds": [f"{v} < {bound}"], "branches": [body]}
        if t == "par":
            k = r.choice([2, 2, 3])
            return {"t": "frame", "type": "par", "conds": [],
                    "branches": [[self.msg() for _ in range(r.randint(1, 2))] for _ in range(k)]}
        # alt
        kind = r.choice(["enum", "enum", "flag", "num"])
        if prev_msg is not None and not self.used_now and level == 0 and r.random() < 0.3:
            kind = "time"
        if kind == "time":
            self.used_now = True
            if not prev_msg["dur"] or prev_msg["dur"][1] < 4:
                prev_msg["dur"] = (0, r.choice([10, 20, 30, 60]))
            prev_msg["now"] = "t_obs"
            k = r.randint(1, prev_msg["dur"][1] - 1)
            conds = [f"t_obs <= {k}", f"t_obs > {k}"]
        elif kind == "enum":
            v = self.pick_var(ENUM_VARS)
            pool = r.choice([p for p in ENUM_VALS if p not in self.enum_pools])
            self.enum_pools.add(pool)
            conds = [f"{v} == {x}" for x in pool]
        elif kind == "flag":
            v = self.pick_var(FLAG_VARS)
            conds = [f"{v} == 1", f"{v} == 0"]
        else:
            v, k = self.pick_var(NUM_VARS), r.choice([10, 20, 50, 100, 500])
            conds = [f"{v} < {k}", f"{v} >= {k}"]
        return {"t": "frame", "type": "alt", "conds": conds,
                "branches": [self.block(level + 1, anc + ["alt"], r.randint(0, 1)) for _ in conds]}

    def top(self):
        elems = [self.msg()]
        for k in range(max(self.rng.choice([0, 1, 1, 2, 2, 3]), 1 if self.mod_mode else 0)):
            if self.n > self.max_msgs - 3:
                break
            elems.append(self.msg())
            kinds = ["loop"] if self.mod_mode and k == 0 else self.allowed(0, [])
            elems += [self.frame(0, [], kinds, prev_msg=elems[-1]), self.msg()]
        while self.n < self.min_msgs:
            elems.append(self.msg())
        return elems


def label_of(m):
    s = m["name"] + (f"({', '.join(m['data'])})" if m["data"] else "()")
    if m["dur"]:
        s += f" {{{m['dur'][0]}..{m['dur'][1]}}}"
    return s


def layout(gen, elems):
    """Assign y positions following the parser's geometry rules (see module doc)."""
    out = {"msgs": [], "frames": [], "texts": [], "seps": []}
    expect = []

    def mid_x(m):
        return 40 + (m["a"] + m["b"]) * 125 + 20

    def lay(elems, level, cursor, conds):
        last = None
        for el in elems:
            if el["t"] == "msg":
                y = cursor
                out["msgs"].append((label_of(el), el["a"], el["b"], y, el["kind"]))
                if el["delay"]:
                    out["texts"].append((f"{{t..t+{el['delay']}}}", y - 8, level, mid_x(el)))
                if el["now"]:
                    out["texts"].append((f"{el['now']} = now", y + 8, level, mid_x(el)))
                expect.append({**el, "conds": list(conds)})
                last, cursor = y, cursor + 50
                continue
            y0 = cursor - 15
            if el["type"] in ("opt", "loop"):
                out["texts"].append((f"[{el['conds'][0]}]", y0 + 5, level))
                cursor, last = lay(el["branches"][0], level + 1, y0 + 50, conds + [el["conds"][0]])
            elif el["type"] == "alt":
                cur = y0 + 50
                for bi, (bc, br) in enumerate(zip(el["conds"], el["branches"])):
                    if bi == 0:
                        out["texts"].append((f"[{bc}]", y0 + 5, level))
                    else:
                        out["seps"].append((last + 22, level))
                        out["texts"].append((f"[{bc}]", last + 35, level))
                        cur = last + 80
                    cur, last = lay(br, level + 1, cur, conds + [bc])
            else:  # par
                cur = y0 + 50
                for bi, br in enumerate(el["branches"]):
                    if bi:
                        out["seps"].append((last + 22, level))
                        cur = last + 50
                    cur, last = lay(br, level + 1, cur, conds)
            y1 = last + 25
            out["frames"].append((el["type"], y0, y1, level))
            cursor = y1 + 35
        return cursor, last

    lay(elems, 0, 130, [])
    out["frames"].sort(key=lambda f: f[1])
    out["texts"].sort(key=lambda t: t[1])
    return {"name": gen.case, "objects": gen.objects, **out}, expect


def check_parse(xml_path, expect, objects):
    ok, _ = validate_sequence_diagram(xml_path)
    if not ok or get_message_warnings(xml_path):
        return "invalid diagram or unlabelled arrow"
    edges = extract_detailed_sequence(xml_path)
    if len(edges) != len(expect):
        return f"{len(edges)} edges parsed, {len(expect)} intended"
    for e, x in zip(edges, expect):
        want = {"msg": x["name"], "sender": objects[x["a"]], "receiver": objects[x["b"]],
                "data": ",".join(x["data"]) if x["data"] else None,
                "duration": f"{x['dur'][0]}..{x['dur'][1]}" if x["dur"] else None,
                "delay": str(x["delay"]) if x["delay"] else None,
                "conds": x["conds"], "now": x["now"]}
        got = {"msg": e["msg"], "sender": e["sender"], "receiver": e["receiver"], "data": e["data"],
               "duration": e["duration"], "delay": e["delay"],
               "conds": [c for c in e["conditions"] if c], "now": e.get("now_var")}
        if got != want:
            return f"mismatch {x['name']}: got {got} want {want}"
    return None


# ── mutations / augmentations ────────────────────────────────────────────────
def plan_ops(rng, mtype, variant, edges, gen, txt, bum):
    """Return (ops, expected_failed_pos as callable(labels), description)."""
    n = len(edges)
    inst = [f"{e['msg']}_{i}" for i, e in enumerate(edges, 1)]
    recv = [f"receive{e['msg']}_{i}{e.get('opt_suffix', '')}" for i, e in enumerate(edges, 1)]
    send = [f"send{e['msg']}_{i}{e.get('opt_suffix', '')}" for i, e in enumerate(edges, 1)]
    timed = [i for i, e in enumerate(edges) if e.get("duration")]
    pair = lambda: (lambda i: (i, rng.randint(i + 1, n - 1)))(rng.randint(0, n - 2))

    if variant == "augmented":
        groups = [["currentMessage ⊆ sentMessages"], ["receivedMessages ⊆ dom(receiver)"]]
        groups += [[f"{v} ≤ {b}"] for v, b in gen.loops]
        for k in timed:
            groups.append(rng.choice([[f"t_time_{k+1} ≥ 0"],
                                      [f"t_time_{k+1} ≥ 0", f"t_delay_{k+1} ≥ 0"],
                                      [f"t_time_{k+1} ≥ 0", f"t_delay_{k+1} ≥ 0", f"t_success_{k+1} ≥ 0"]]))
        chosen = rng.sample(groups, min(len(groups), rng.randint(1, 3)))
        inv = [p for g in chosen for p in g]
        return {"add_inv": inv}, lambda L: [], "added provable invariants: " + "; ".join(inv)

    if mtype in ("rm_guard", "rm_guard2"):
        idx = sorted(rng.sample(range(n), 2 if mtype == "rm_guard2" else 1))
        return ({"remove_guard": [(recv[i], "grd1") for i in idx]},
                lambda L: [f"{recv[i]}/inv5/INV" for i in idx],
                "removed guard `m ∈ sentMessages` from " + ", ".join(recv[i] for i in idx))
    if mtype == "wrong_recv":
        i, j = pair()
        return ({"replace_in_event": [(recv[i], f"receivedMessages ∪ {{{inst[i]}}}",
                                       f"receivedMessages ∪ {{{inst[j]}}}")]},
                lambda L: [f"{recv[i]}/inv5/INV"],
                f"{recv[i]} records {inst[j]} (not yet sent) as received")
    if mtype == "init_recv":
        j = rng.randint(1, n - 1)
        return ({"set_init": {"receivedMessages": f"{{{inst[j]}}}"}},
                lambda L: ["INITIALISATION/inv5/INV"],
                f"INITIALISATION marks {inst[j]} as received before anything is sent")
    if mtype == "send_recv":
        i, j = pair()
        return ({"replace_in_event": [(send[i], "receivedMessages := ∅",
                                       f"receivedMessages := {{{inst[j]}}}")]},
                lambda L: [f"{send[i]}/inv5/INV"],
                f"{send[i]} sets receivedMessages to {{{inst[j]}}} instead of ∅")
    if mtype == "combo":
        i, j = pair()
        k = rng.randint(1, n - 1)
        return ({"set_init": {"receivedMessages": f"{{{inst[k]}}}"},
                 "replace_in_event": [(recv[i], f"receivedMessages ∪ {{{inst[i]}}}",
                                       f"receivedMessages ∪ {{{inst[j]}}}")]},
                lambda L: ["INITIALISATION/inv5/INV", f"{recv[i]}/inv5/INV"],
                f"INITIALISATION marks {inst[k]} received; {recv[i]} records {inst[j]}")
    if mtype in DIAGRAM_FAILS:
        vs = [f"t_time_{i + 1}" for i, e in enumerate(edges)
              if e.get("duration") and int(e["duration"].split("..")[0]) > int(e["duration"].split("..")[1])]
        fis = [f"INITIALISATION/{init_action_label(bum, v)}/FIS" for v in vs]
        wd = wd_pos(txt)
        desc = []
        if vs:
            desc.append("duration interval written backwards on " + ", ".join(vs))
        if wd:
            desc.append("condition " + ", ".join(sorted(set(re.findall(r"\w+ mod \d+", txt))))
                        + " on a loop counter: no invariant gives the counter ≥ 0")
        return {}, lambda L: fis + wd, "diagram: " + "; ".join(desc)
    if mtype == "tight_success":
        k = rng.choice(timed)
        hi = int(edges[k]["duration"].split("..")[1]) + int(edges[k].get("delay") or 0)
        x = max(0, hi - rng.randint(1, max(1, hi // 2)))
        return ({"add_inv": [f"t_success_{k+1} ≤ {x}"]}, lambda L: [f"{recv[k]}/{L[0]}/INV"],
                f"t_success_{k+1} ≤ {x} although it can reach {hi}")
    if mtype == "tight_time_init":
        k = rng.choice([i for i in timed if int(edges[i]["duration"].split("..")[1]) >= 2])
        hi = int(edges[k]["duration"].split("..")[1])
        x = rng.randint(0, hi - 1)
        return ({"add_inv": [f"t_time_{k+1} ≤ {x}"]}, lambda L: [f"INITIALISATION/{L[0]}/INV"],
                f"t_time_{k+1} ≤ {x} but INITIALISATION chooses it from 0‥{hi}")
    if mtype == "counter_init":
        v, b = rng.choice(gen.loops)
        return ({"add_inv": [f"{v} ≤ {b}"], "set_init": {v: str(b + 1)}},
                lambda L: [f"INITIALISATION/{L[0]}/INV"],
                f"{v} ≤ {b} added (provable) but {v} initialised to {b + 1}")
    if mtype == "offbyone":
        v, b = rng.choice(gen.loops)
        chk = checkloop_event(txt, v, b)
        return ({"add_inv": [f"{v} ≤ {b}"], "replace_in_event": [(chk, f"{v} < {b}", f"{v} ≤ {b}")]},
                lambda L: [f"{chk}/{L[0]}/INV"],
                f"off-by-one: {chk} guard {v} < {b} weakened to {v} ≤ {b} against {v} ≤ {b}")
    if mtype == "decrement":
        v, b = rng.choice(gen.loops)
        chk = checkloop_event(txt, v, b)
        return ({"add_inv": [f"{v} ≥ 0", f"{v} ≤ {b}"],
                 "replace_in_event": [(chk, f"{v} := {v} + 1", f"{v} := {v} − 1")]},
                lambda L: [f"{chk}/{L[0]}/INV"],
                f"{v} ≥ 0 and {v} ≤ {b} added; {chk} decrements the counter")
    if mtype == "missing_helper":
        k = rng.choice(timed)
        return ({"add_inv": [f"t_time_{k+1} ≥ 0", f"t_success_{k+1} ≥ 0"]},
                lambda L: [f"{recv[k]}/{L[1]}/INV"],
                f"t_time_{k+1} ≥ 0 (provable) and t_success_{k+1} ≥ 0 (true, needs missing t_delay_{k+1} ≥ 0)")
    if mtype == "neg_delay":
        k = rng.choice(timed)
        return ({"add_inv": [f"t_time_{k+1} ≥ 0", f"t_delay_{k+1} ≥ 0", f"t_success_{k+1} ≥ 0"],
                 "set_init": {f"t_delay_{k+1}": "−2"}},
                lambda L: [f"INITIALISATION/{L[1]}/INV"],
                f"time invariants for message {k+1} added; t_delay_{k+1} initialised to −2")
    if mtype == "wrong_current":
        i, j = pair()
        return ({"add_inv": ["currentMessage ⊆ sentMessages"],
                 "replace_in_event": [(send[i], f"currentMessage := {{{inst[i]}}}",
                                       f"currentMessage := {{{inst[j]}}}")]},
                lambda L: [f"{send[i]}/{L[0]}/INV"],
                f"currentMessage ⊆ sentMessages added; {send[i]} sets currentMessage to {{{inst[j]}}}")
    if mtype == "data_subset":
        return ({"add_inv": ["receiverdataMessages ⊆ senderdataMessages"]},
                lambda L: [f"{recv[i]}/{L[0]}/INV" for i, e in enumerate(edges) if e["data"]],
                "receiverdataMessages ⊆ senderdataMessages (true when reachable, not inductive)")
    raise ValueError(mtype)


def wd_pos(txt):
    """event/grdN/WD for every guard that uses mod (its WD condition is "left operand ≥ 0")."""
    out, ev = [], None
    for line in txt.split("\n"):
        if re.match(r"^ {4}(INITIALISATION|send|receive|checkloop)\S*", line):
            ev = line.split()[0]
        m = re.match(r"^\s+(grd\d+): .* mod \d+", line)
        if m:
            out.append(f"{ev}/{m.group(1)}/WD")
    return out


def requirements_ok(mtype, gen, expect):
    n, timed = len(expect), [m for m in expect if m["dur"]]
    if n < 4:
        return False
    if mtype in DIAGRAM_FAILS:
        return not DIAGRAM_FAILS[mtype][1] or gen.mod_used
    if mtype in ("counter_init", "offbyone", "decrement"):
        return bool(gen.loops)
    if mtype in ("tight_success", "missing_helper", "neg_delay"):
        return bool(timed)
    if mtype == "tight_time_init":
        return any(m["dur"][1] >= 2 for m in timed)
    if mtype == "data_subset":
        return any(m["data"] for m in expect)
    return True


def make_one(domain, intent, variant, mtype, seed, tmp, min_msgs=4):
    for attempt in range(1000):
        rng = random.Random(seed * 1000 + attempt)
        n_inv, mod_mode, in_frame = DIAGRAM_FAILS.get(mtype, (0, None, False))
        if mod_mode == "any":
            mod_mode = rng.choice(["alt", "opt"])
        gen = ModelGen(rng, domain, min_msgs, mod_mode)
        elems = gen.top()
        flat, framed = [], set()

        def walk(es, inside):
            for e in es:
                if e["t"] == "msg":
                    flat.append(e)
                    if inside:
                        framed.add(id(e))
                else:
                    for br in e["branches"]:
                        walk(br, True)
        walk(elems, False)
        if not requirements_ok(mtype, gen, flat):
            continue
        if n_inv:                                        # write the interval backwards
            cands = [m for m in flat if m["dur"] and m["dur"][1] >= 2 and (not in_frame or id(m) in framed)]
            if len(cands) < n_inv:
                continue
            for m in rng.sample(cands, n_inv):
                m["dur"] = (m["dur"][1], rng.randint(0, m["dur"][1] - 1))
        spec, expect = layout(gen, elems)
        xml_path = os.path.join(tmp, f"{gen.case}.drawio.xml")
        with open(xml_path, "w") as f:
            f.write(build(spec))
        if check_parse(xml_path, expect, gen.objects):
            continue
        return gen, spec, xml_path
    raise RuntimeError(f"could not generate {domain[0]} ({mtype})")


def main(batch, seed, min_msgs=4):
    out = os.path.join(DATASET, "batches", batch)
    if os.path.exists(out):
        raise SystemExit(f"{out} already exists — choose a new batch name")
    # a case name is a Rodin project name: never reuse one from the dataset or another batch
    import glob
    used = {json.load(open(p))["case"] for p in
            glob.glob(os.path.join(DATASET, "models", "*", "meta.json"))
            + glob.glob(os.path.join(DATASET, "batches", "**", "meta.json"), recursive=True)}
    free = [d for d in DOMAINS if d[0] not in used]
    if len(free) < len(PLAN):
        raise SystemExit(f"only {len(free)} unused domain names left; add more to DOMAINS")
    domains = free[:len(PLAN)]
    os.makedirs(out)
    rng = random.Random(seed)
    plan = PLAN[:]
    rng.shuffle(plan)
    rodin_zip = io.BytesIO()
    zall = zipfile.ZipFile(rodin_zip, "w", zipfile.ZIP_DEFLATED)
    tmp = tempfile.mkdtemp()
    summary = []
    for k, (domain, (intent, variant, mtype)) in enumerate(zip(domains, plan)):
        gen, spec, xml_tmp = make_one(domain, intent, variant, mtype, seed + k, tmp, min_msgs)
        case = gen.case
        d = os.path.join(out, case)
        os.makedirs(d)
        xml_path = os.path.join(d, f"{case}.drawio.xml")
        shutil.copy(xml_tmp, xml_path)

        rodin_exporter._next_export_name = lambda p, n=case: n   # readable name, no M-counter bump
        txt = apply_rules_1_and_2(xml_path, 1)
        zin = zipfile.ZipFile(io.BytesIO(rodin_exporter.generate_rodin_zip(xml_path, 1)))
        bum_name = next(x for x in zin.namelist() if x.endswith(".bum"))
        bum = zin.read(bum_name).decode("utf-8")
        edges = extract_detailed_sequence(xml_path)

        ops, expected, desc = ({}, lambda L: [], "generator output, unchanged") \
            if variant == "plain" else plan_ops(random.Random(seed * 7 + k), mtype, variant,
                                                edges, gen, txt, bum)
        n_inv = len(re.findall(r"^ {4}inv\d+:", txt, re.M))
        labels = [f"inv{n_inv + i + 1}" for i in range(len(ops.get("add_inv", [])))]
        if ops:
            txt, bum = mutate_text(txt, ops, labels), mutate_bum(bum, ops, labels)
        ET.fromstring(bum.encode("utf-8"))
        (ti, bi), (tg, bg) = count_consistency(txt, bum)
        assert ti == bi and tg == bg, f"{case}: text/bum disagree ({ti}/{bi} inv, {tg}/{bg} grd)"
        exp = expected(labels)

        with open(os.path.join(d, f"{case}_EventB.txt"), "w") as f:
            f.write(txt)
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in zin.namelist():
                data = bum.encode("utf-8") if name == bum_name else zin.read(name)
                zout.writestr(name, data)
                zall.writestr(name, data)
        with open(os.path.join(d, f"{case}_Rodin.zip"), "wb") as f:
            f.write(zbuf.getvalue())
        meta = {"case": case, "design_intent": intent, "variant": variant,
                "rodin_project": f"{case}_Project", "batch": batch, "seed": seed + k, "min_msgs": min_msgs,
                "mutation": desc, "operations": ops}
        if variant == "augmented":
            meta["added_invariants"] = dict(zip(labels, ops["add_inv"]))
        if intent == "expected_fail":
            meta["category"] = CATEGORY.get(mtype, "model_error")
            meta["mutation_type"] = mtype
        meta["expected_failed_pos"] = exp
        meta["expected_failed_count"] = len(exp)
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        summary.append((case, len(gen.objects), len(edges), variant, mtype or "", len(exp)))
    zall.close()
    with open(os.path.join(out, f"Rodin_Import_{batch}.zip"), "wb") as f:
        f.write(rodin_zip.getvalue())
    shutil.rmtree(tmp)

    for row in summary:
        print("{:24} obj={} msg={:2} {:13} {:16} expected_failed={}".format(*row))
    p = sum(1 for r in summary if r[5] == 0)
    print(f"\n{len(summary)} models | expected pass {p} / fail {len(summary) - p}")
    print(f"Rodin archive: {os.path.join(out, f'Rodin_Import_{batch}.zip')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--seed", type=int, default=20261023)
    ap.add_argument("--min-msgs", type=int, default=4,
                    help="smallest number of messages per diagram (batch_02/03 used 4)")
    a = ap.parse_args()
    main(a.batch, a.seed, a.min_msgs)
