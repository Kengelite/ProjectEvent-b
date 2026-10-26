"""Classify every model (dataset + pending batches) and write model_categories.csv.

    python tools/categorize.py

Three levels:
  group    pass / fail / test           (design intent; model_001 = test)
  variant  plain / augmented / mutated / diagram_error / original
  family   for fail models: which part of the model the defect is in
           (+ mutation_type and category model_error / non_inductive)
"""
import csv, glob, json, os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# models 002-048 were built before mutation types had names
FIRST_BATCH_TYPES = {
    "ParcelLocker": "inverted1", "LabSampleTesting": "inverted2",
    "BankTransfer": "rm_guard2", "OnlineAuction": "rm_guard",
    "SmartMeterBilling": "wrong_recv", "SmartPlugControl": "wrong_recv",
    "GymCheckIn": "init_recv", "TaxiDispatch": "send_recv", "ToolRentalLocker": "combo",
    "TrafficLightController": "tight_success", "ColdChainMonitor": "missing_helper",
    "AirportBaggage": "neg_delay", "PrinterQueue": "counter_init",
    "LoginRateLimiter": "offbyone", "BatteryChargeCycle": "decrement",
    "MedicationDispenser": "wrong_current", "ChatMessaging": "data_subset",
    "CourseEnrollment": "dom_data", "ConferenceRoomBooking": "dom_sends",
}
FAMILY = {
    "inverted1": "A. diagram error (time interval)", "inverted2": "A. diagram error (time interval)",
    "inverted3": "A. diagram error (time interval)", "inverted_frame": "A. diagram error (time interval)",
    "mod_alt": "F. diagram error (mod condition)", "mod_opt": "F. diagram error (mod condition)",
    "mod_inverted": "A+F. diagram error (time interval + mod condition)",
    "rm_guard": "B. message bookkeeping", "rm_guard2": "B. message bookkeeping",
    "wrong_recv": "B. message bookkeeping", "send_recv": "B. message bookkeeping",
    "init_recv": "B. message bookkeeping", "combo": "B. message bookkeeping",
    "tight_success": "C. timing invariant", "tight_time_init": "C. timing invariant",
    "missing_helper": "C. timing invariant", "neg_delay": "C. timing invariant",
    "counter_init": "D. loop counter", "offbyone": "D. loop counter", "decrement": "D. loop counter",
    "wrong_current": "E. message-set / data invariant", "data_subset": "E. message-set / data invariant",
    "dom_data": "E. message-set / data invariant", "dom_sends": "E. message-set / data invariant",
}

TOPIC_NAMES = {
    "FIN": ("Finance & Payment", "การเงินและการชำระเงิน"),
    "HEA": ("Healthcare & Medical", "สุขภาพและการแพทย์"),
    "TRA": ("Transportation & Mobility", "การเดินทางและยานพาหนะ"),
    "LOG": ("Logistics & Supply Chain", "โลจิสติกส์และคลังสินค้า"),
    "HOME": ("Smart Home & Building", "บ้านและอาคารอัจฉริยะ"),
    "IND": ("Industrial, Energy & Infrastructure", "อุตสาหกรรม พลังงาน และโครงสร้างพื้นฐาน"),
    "RET": ("Retail, Food & E-commerce", "ค้าปลีก อาหาร และ e-commerce"),
    "BOOK": ("Booking, Hospitality & Events", "การจอง ที่พัก และกิจกรรม"),
    "EDU": ("Education & Public Services", "การศึกษาและบริการภาครัฐ"),
    "IT": ("IT & Digital Services", "ไอทีและบริการดิจิทัล"),
    "AGR": ("Agriculture & Environment", "เกษตรและสิ่งแวดล้อม"),
}
TOPIC = {
    # dataset (model_001-048)
    "Payment & Notification": "FIN", "ATMWithdrawal": "FIN", "BankTransfer": "FIN", "InsuranceClaim": "FIN",
    "BloodBankRequest": "HEA", "FitnessTracker": "HEA", "HospitalTriage": "HEA", "LabSampleTesting": "HEA",
    "MedicationDispenser": "HEA",
    "AirportBaggage": "TRA", "CarRentalBooking": "TRA", "FerryTicketGate": "TRA", "SmartParking": "TRA",
    "TaxiDispatch": "TRA", "TrafficLightController": "TRA",
    "ColdChainMonitor": "LOG", "DroneDelivery": "LOG", "PackageTracking": "LOG", "ParcelLocker": "LOG",
    "WarehouseRobotFleet": "LOG",
    "ElevatorControl": "HOME", "SmartDoorLock": "HOME", "SmartPlugControl": "HOME", "ThermostatControl": "HOME",
    "VoiceAssistant": "HOME",
    "BatteryChargeCycle": "IND", "FactoryRobotArm": "IND", "SmartMeterBilling": "IND",
    "CoffeeOrderKiosk": "RET", "FoodOrderApp": "RET", "OnlineAuction": "RET", "ToolRentalLocker": "RET",
    "VendingMachine": "RET",
    "CinemaTicketing": "BOOK", "ConferenceRoomBooking": "BOOK", "GymCheckIn": "BOOK", "HotelCheckIn": "BOOK",
    "CourseEnrollment": "EDU", "EmergencyDispatch": "EDU", "LibraryLoan": "EDU", "OnlineExam": "EDU",
    "ChatMessaging": "IT", "EmailVerification": "IT", "LoginRateLimiter": "IT", "PrinterQueue": "IT",
    "SensorDataPipeline": "IT", "ServerAutoScaling": "IT",
    "SmartGreenhouse": "AGR",
    # batch_02
    "BikeSharing": "TRA", "PharmacyRefill": "HEA", "CampusWifiAccess": "IT", "RestaurantReservation": "BOOK",
    "GarageGateControl": "TRA", "CargoShipTracking": "LOG", "IrrigationZoneControl": "AGR",
    "RideHailingSurge": "TRA", "HomeSecurityAlarm": "HOME", "OnlineBankingOTP": "FIN",
    "HospitalBedAllocation": "HEA", "EVChargingSession": "IND", "SelfCheckoutLane": "RET",
    "FlightCheckIn": "TRA", "VideoStreaming": "IT", "TollPlazaETC": "TRA", "SmartWasteBin": "AGR",
    "DigitalLibraryAccess": "EDU", "RemotePatientMonitor": "HEA", "OnlineQuizGame": "IT",
    "ConcertTicketQueue": "BOOK", "FleetFuelCard": "FIN", "GreenhouseLighting": "AGR",
    "ApartmentIntercom": "HOME", "WarehousePicking": "LOG", "TelemedicineVisit": "HEA",
    "AirportShuttle": "TRA", "CropDroneSpraying": "AGR", "SchoolBusTracking": "TRA",
    "InventoryReorder": "LOG", "CafeLoyaltyPoints": "RET", "CloudBackupJob": "IT", "SmartStreetLight": "IND",
    "EventCheckInQR": "BOOK", "PetDoorController": "HOME", "WaterLeakDetection": "HOME",
    "MuseumAudioGuide": "BOOK", "FoodTruckOrdering": "RET", "DormLaundry": "HOME",
    "FactoryQualityGate": "IND", "GlucoseMeterSync": "HEA", "AirQualityMonitor": "AGR",
    "CarWashBooking": "BOOK", "SmartFridgeInventory": "HOME", "CourseAutoGrading": "EDU",
    "HotelRoomService": "BOOK", "LiftMaintenance": "HOME", "RailFareGate": "TRA",
    "SolarPanelMonitor": "IND", "MailroomSorting": "LOG",
    # batch_03
    "ParkingPermitPortal": "TRA", "BloodDonationDrive": "HEA", "SmartBeehive": "AGR",
    "TaxFilingPortal": "EDU", "OnlineDonation": "FIN", "SmartMirrorFitness": "HEA",
    "JobApplicationPortal": "IT", "PrintFleetMonitor": "IT", "BoardingSchoolGate": "EDU",
    "MeetingRoomDisplay": "BOOK", "DigitalVotingBooth": "EDU", "PortCraneControl": "LOG",
    "SmartAquarium": "HOME", "RentalScooter": "TRA", "FarmMilkingRobot": "AGR", "IoTDoorbell": "HOME",
    "PharmacyDelivery": "HEA", "CustomsClearance": "LOG", "BusTicketBooking": "TRA",
    "ThermalCameraScreening": "HEA", "StudentAttendance": "EDU", "CloudCIPipeline": "IT",
    "LiftEmergencyCall": "HOME", "GolfCartFleet": "BOOK", "SmartBabyMonitor": "HOME",
    "RecyclingKiosk": "AGR", "TrainSeatReservation": "TRA", "HospitalPharmacyRobot": "HEA",
    "CanteenPayment": "FIN", "ForestFireSensor": "AGR", "MarketplaceEscrow": "FIN",
    "CarRentalReturn": "TRA", "VaccineColdBox": "HEA", "SmartLibraryShelf": "EDU",
    "DentalAppointment": "HEA", "WindTurbineMonitor": "IND", "PassportRenewalKiosk": "EDU",
    "SmartGymLocker": "BOOK", "DroneTrafficControl": "TRA", "WarehouseForklift": "LOG",
    "LabEquipmentBooking": "EDU", "ParcelReturnDropoff": "LOG", "CenterPivotIrrigation": "AGR",
    "TradingOrderGateway": "FIN", "MedicalImagingPACS": "HEA", "FireSprinklerSystem": "HOME",
    "HomeEnergyBattery": "IND", "CampusShuttleBus": "TRA", "ConferenceBadgeScan": "BOOK",
    "PatientIntakeForm": "HEA",
    # batch_04
    "StreetParkingMeter": "TRA", "AmbulanceRouting": "HEA", "SmartPillBox": "HEA",
    "RoboticLawnMower": "HOME", "PodcastPublishing": "IT", "FlightCrewScheduling": "TRA",
    "SmartShoppingCart": "RET", "EVBatterySwap": "IND", "MarathonTiming": "BOOK",
    "HotelKeylessEntry": "BOOK", "SmartRainGauge": "AGR", "InsuranceTelematics": "FIN",
    "BankBranchQueue": "FIN", "MobileTopUp": "FIN", "SatelliteGroundStation": "IT",
    "PrisonVisitBooking": "EDU", "ArtGalleryTicketing": "BOOK", "GroceryDeliverySlot": "RET",
    "SmartHelmetMining": "IND", "RemoteExamProctor": "EDU", "TrafficSignalPriority": "TRA",
    "HomeOxygenConcentrator": "HEA", "SmartVendingFridge": "RET", "CoworkingDeskBooking": "BOOK",
    "LivestockFeeder": "AGR", "PipelineLeakSCADA": "IND", "ArchiveDocumentScan": "IT",
    "ChildcareCheckin": "EDU", "AirportSecurityLane": "TRA", "SmartTrashCompactor": "AGR",
    "PhotoPrintKiosk": "RET", "MedicalTranscription": "HEA", "GasStationPrepay": "FIN",
    "PublicWifiHotspot": "IT", "OfficeLightingControl": "HOME", "VeterinaryClinic": "HEA",
    "StadiumEntryGate": "BOOK", "OnlineGroceryPicking": "RET", "DisasterAlertBroadcast": "EDU",
    "SoilTestingLab": "AGR", "ShipLockOperation": "TRA", "ConcessionStandOrder": "RET",
    "BuildingVisitorPass": "HOME", "CraneLoadMonitor": "IND", "RuralTelehealthKiosk": "HEA",
    "BulkSMSGateway": "IT", "HospitalLabRequest": "HEA", "SmartCurtainControl": "HOME",
    "ParentalControlRouter": "IT", "SeaportPilotBooking": "LOG",
}


def where(pos):
    """Kind of event in which each expected failure occurs."""
    out = set()
    for p in pos:
        ev, kind = p.split("/")[0], p.split("/")[-1]
        out.add(kind if kind in ("FIS", "WD") else "INITIALISATION" if ev == "INITIALISATION"
                else "checkloop" if ev.startswith("checkloop") else "send" if ev.startswith("send")
                else "receive")
    return "+".join(sorted(out))


def rows():
    """A staged model that carries a model_id (rebuilt first round) replaces that dataset row."""
    integrated = {json.load(open(p)).get("integrated_from")
                  for p in glob.glob(os.path.join(ROOT, "models", "*", "meta.json"))}
    staged = [json.load(open(p)) for p in
              sorted(glob.glob(os.path.join(ROOT, "batches", "**", "meta.json"), recursive=True))
              if os.path.relpath(p, os.path.join(ROOT, "batches")).split(os.sep)[0] not in integrated]
    replaced = {m["model_id"]: m for m in staged if "model_id" in m}
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "models", "*", "meta.json"))):
        m = json.load(open(p))
        if m["model_id"] in replaced:
            out.append((m["model_id"], replaced[m["model_id"]]["batch"], replaced[m["model_id"]], None))
            continue
        lab = json.load(open(os.path.join(os.path.dirname(p), "label.json")))
        out.append((m["model_id"], "dataset", m, lab["failed"]))
    out += [("", m["batch"], m, None) for m in staged if "model_id" not in m]
    return out


def main():
    table = []
    for mid, where_from, m, failed in rows():
        intent = m["design_intent"]
        group = {"expected_pass": "pass", "expected_fail": "fail"}.get(intent, "test")
        mtype = m.get("mutation_type") or ("" if "batch" in m else FIRST_BATCH_TYPES.get(m["case"], ""))
        inv = m.get("added_invariants") or {}
        code = TOPIC.get(m["case"])
        if code is None:
            raise SystemExit(f"no topic for {m['case']} — add it to TOPIC")
        table.append({
            "model_id": mid, "source": where_from, "case": m["case"],
            "topic": TOPIC_NAMES[code][0], "topic_th": TOPIC_NAMES[code][1], "group": group,
            "variant": m["variant"], "category": m.get("category", ""),
            "family": FAMILY.get(mtype, ""), "mutation_type": mtype,
            "fails_in": where(m.get("expected_failed_pos", [])),
            "expected_failed": m.get("expected_failed_count", 0 if group != "fail" else ""),
            "rodin_failed": "" if failed is None else failed,
            "added_invariants": "; ".join(inv.values()) if isinstance(inv, dict) else "",
        })
    path = os.path.join(ROOT, "model_categories.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)

    print(f"{len(table)} models -> {path}\n")
    print("topic (pass / fail / test):")
    for code, (en, th) in TOPIC_NAMES.items():
        rs = [r for r in table if r["topic"] == en]
        g = Counter(r["group"] for r in rs)
        print(f"  {th:38} {len(rs):3}  pass {g['pass']:2} / fail {g['fail']:2}" + (f" / test {g['test']}" if g["test"] else ""))
    print()
    print("group / variant:", dict(Counter((r["group"], r["variant"]) for r in table)))
    print("\nfail families:")
    for fam, n in sorted(Counter(r["family"] for r in table if r["group"] == "fail").items()):
        types = Counter(r["mutation_type"] for r in table if r["family"] == fam)
        print(f"  {fam:34} {n:3}  {dict(types)}")
    print("\nfail category:", dict(Counter(r["category"] for r in table if r["group"] == "fail")))
    print("fails in:", dict(Counter(r["fails_in"] for r in table if r["group"] == "fail")))
    print("by source:", dict(Counter((r["source"], r["group"]) for r in table)))


if __name__ == "__main__":
    main()
