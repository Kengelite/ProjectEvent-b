"""Package the labelled dataset into a clean training folder.

    python tools/make_release.py [--out ../EventB_PO_Training] [--seed 20261026]

Output (rebuilt from scratch each run):
    README.pdf                  Thai summary: numbers, what to upload, structure, caveats
    upload/train.jsonl          chat-format records to fine-tune on
    upload/val.jsonl            chat-format records for validation during training
    upload/test.jsonl           chat-format records kept out of training (evaluation only)
    data/dataset.jsonl          one row per model: model text, features, labels, topic, split
    data/po_details.jsonl       one row per proof obligation
    data/split.csv              model_id -> train / val / test
    csv/summary.csv             per-model numbers (features + labels + topic + split)
    csv/pass_fail_list.csv      per-model pass / fail
    csv/model_categories.csv    topic, diagram error, expected vs Rodin (analysis only)
    models/model_XXX/           model.txt, label.json, po_details.json, features.json
    by_topic/<NN_Topic>/<pass|fail>/<model_XXX_Case>/   the same models grouped by topic and
                                Rodin result, with a list.csv per topic
    FLOW.pdf, FLOW.png          workflow diagram (tools/make_user_flow.py)
    SOURCES.md                  provenance (tools, versions, dates) and references
    PROVENANCE.pdf, csv/provenance.csv   where every single model came from

Nothing that reveals the answer (meta.json, diagrams, Rodin files) is copied into the
inputs. The split is stratified by result and by kind of failing PO; model_001 (the
reconstructed Payment case kept for testing) always goes to test.
"""
import argparse, csv, glob, hashlib, html, json, os, shutil, statistics, subprocess, sys, tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from categorize import TOPIC, TOPIC_NAMES                       # noqa: E402
from make_batch_report import CHROME, CSS, esc                  # noqa: E402
import make_user_flow                                           # noqa: E402

SPLIT = (("train", 0.70), ("val", 0.15), ("test", 0.15))
PROJECT = os.path.dirname(DATASET)
CONVERTER_REPO = "https://github.com/Kengelite/ProjectEvent-b"
# (provenance item, detail) — Thai, shown in README.pdf and SOURCES.md
PROVENANCE = [
    ("แผนภาพต้นทาง", "ข้อมูลสังเคราะห์ ไม่ได้นำมาจากชุดข้อมูลภายนอก — Sequence Diagram 197 แบบจำลอง "
                    "สร้างด้วยโปรแกรมสร้างแผนภาพอัตโนมัติ (EventB_PO_Dataset/tools/generators/) เป็นไฟล์รูปแบบ draw.io "
                    "ชื่อระบบเป็นสถานการณ์สมมติ ครอบคลุม 11 หัวข้อ: 47 แบบจำลองแรกกำหนดสถานการณ์ทีละแบบ "
                    "และ 150 แบบจำลองสุ่มโครงสร้างด้วย seed คงที่ (สร้างซ้ำได้) ทุกแผนภาพตรวจด้วย parser ของ ChronoSeq-B "
                    "· model_001 Payment & Notification เป็นกรณีทดสอบจากงานเดิมของผู้วิจัย"),
    ("การแปลง", "ChronoSeq-B ({repo}) commit {commit} — แปลงแผนภาพเป็น Event-B และ Rodin project "
                "โดยไม่แก้ไขผลลัพธ์ภายหลัง"),
    ("การพิสูจน์", "Rodin Platform บน Windows (Eclipse platform 4.23) ร่วมกับ Atelier B provers plugin — "
                   "ใน proof file พบ reasoner com.clearsy.atelierb.provers.core.externalML และ externalPP"),
    ("ช่วงเวลาพิสูจน์", "รอบแรก 1–2 ตุลาคม 2026 (26 แบบจำลองที่ไม่เปลี่ยน ใช้ผลรอบนี้) · รอบหลัก 26 ตุลาคม 2026"),
    ("การอ่านผล", "อ่านสถานะจากไฟล์ .bps: PO ผ่านเมื่อ confidence = 1000 และ proof ไม่อยู่ในสถานะ broken"),
    ("เครื่องมือประมวลผล", "Python {python} · script ใน EventB_PO_Dataset/tools/ ({repo})"),
]
REFERENCES = [
    "Abrial, J.-R. (2010). <i>Modeling in Event-B: System and Software Engineering</i>. Cambridge University Press.",
    "Abrial, J.-R., Butler, M., Hallerstede, S., Hoang, T. S., Mehta, F., & Voisin, L. (2010). Rodin: An open toolset "
    "for modelling and reasoning in Event-B. <i>International Journal on Software Tools for Technology Transfer, 12</i>(6), "
    "447–466. https://doi.org/10.1007/s10009-010-0145-y",
    "Event-B and the Rodin Platform. https://www.event-b.org/",
    "CLEARSY. Atelier B (provers ML and PP, Rodin plugin). https://www.atelierb.eu/",
    "Object Management Group. (2017). <i>OMG Unified Modeling Language (UML), Version 2.5.1</i>. https://www.omg.org/spec/UML/2.5.1",
    "draw.io (diagrams.net). https://www.drawio.com/",
    "ChronoSeq-B — Sequence Diagram to Event-B converter. " + CONVERTER_REPO,
    "OpenAI. Fine-tuning guide (chat-format training data). https://platform.openai.com/docs/guides/fine-tuning",
    "Hugging Face. TRL — SFTTrainer. https://huggingface.co/docs/trl/sft_trainer",
]

# related work: similar data, methods or tools — NOT where this dataset came from
RELATED = [
    ("คลังแบบจำลอง Event-B", "DEPLOY Project. DEPLOY Repository of Event-B models and case studies. "
                            "http://deploy-eprints.ecs.soton.ac.uk/"),
    ("กรณีศึกษา Event-B", "Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. "
                         "<i>Formal Aspects of Computing, 20</i>(1), 61–77."),
    ("แปลง UML เป็น B", "Snook, C., & Butler, M. (2006). UML-B: Formal modeling and design aided by UML. "
                       "<i>ACM Transactions on Software Engineering and Methodology, 15</i>(1), 92–122."),
    ("LLM กับการพิสูจน์", "Polu, S., & Sutskever, I. (2020). Generative language modeling for automated theorem proving. "
                         "arXiv:2009.03393."),
    ("ชุดข้อมูลการพิสูจน์ + RAG", "Yang, K., Swope, A. M., Gu, A., Chalamala, R., Song, P., Yu, S., Godil, S., Prenger, R., & "
                                "Anandkumar, A. (2023). LeanDojo: Theorem proving with retrieval-augmented language models. "
                                "<i>NeurIPS 2023 Datasets and Benchmarks Track</i>. arXiv:2306.15626."),
    ("RAG", "Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. "
            "<i>Advances in Neural Information Processing Systems, 33</i>."),
    ("fine-tune แบบประหยัด", "Hu, E. J., et al. (2022). LoRA: Low-rank adaptation of large language models. "
                            "<i>International Conference on Learning Representations (ICLR)</i>."),
]

# Published work similar to our models (found by web search 2026-10-27). Similar system or method only —
# NOT a source of the data. keys: kw = regex on the case name, topics = topic codes it also covers.
SIMILAR = [
    # ── method (applies to every model) ──
    {"id": "M1", "kind": "วิธีการ", "about": "แปลง UML Sequence Diagram เป็น Event-B (combined fragments)", "all": True, "checked": True,
     "ref": "Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2015). Extending causal semantics of UML2.0 sequence "
            "diagram for distributed systems. ICSOFT-EA 2015, 339–347.", "url": "https://www.scitepress.org/Papers/2015/55177/"},
    {"id": "M2", "kind": "วิธีการ", "about": "Sequence Diagram ที่มี fragment ซ้อนกัน", "all": True, "checked": True,
     "ref": "Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2017). A causal semantics for UML2.0 sequence diagrams "
            "with nested combined fragments. ENASE 2017.", "url": "https://www.scitepress.org/Papers/2017/63141"},
    {"id": "M3", "kind": "วิธีการ", "about": "แปลง UML timing diagram เป็น Event-B (กรณีศึกษาลิฟต์)", "all": True,
     "ref": "Joochim, T., Gravell, A., & Poppleton, M. Translating UML 2.0 timing diagrams into Event-B and UML-B.",
     "url": "https://eprints.soton.ac.uk/268489/", "kw": r"Lift|Elevator"},
    {"id": "M4", "kind": "วิธีการ", "about": "deadline / delay ใน Event-B (ตรงกับ t_time / t_delay)", "all": True,
     "ref": "Sarshogh, M. R., & Butler, M. (2011). Specification and refinement of discrete timing properties in Event-B. "
            "ECEASST, 46.", "url": "https://journal.ub.tu-berlin.de/eceasst/article/view/701"},
    # ── finance ──
    {"id": "S1", "kind": "ระบบ", "about": "ATM / บัญชีธนาคาร (UML-B ATM)", "topics": ["FIN"],
     "ref": "Event-B Wiki. Event-B Examples (ATM development).", "url": "https://wiki.event-b.org/index.php/Event-B_Examples",
     "kw": r"ATM|^Bank|Withdraw|Transfer|Payment|Wallet|TopUp|Card|Escrow|Trading|Canteen|Prepay"},
    {"id": "S2", "kind": "ระบบ", "about": "กระเป๋าเงินอิเล็กทรอนิกส์ (Mondex)", "topics": ["FIN"],
     "ref": "Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. "
            "Formal Aspects of Computing, 20(1), 61–77.", "url": "", "kw": r"Payment|Wallet|TopUp|Transfer|Card|OTP"},
    {"id": "S3", "kind": "ระบบ", "about": "ระบบบริจาค Gift Aid (Event-B ตามกฎหมาย)", "checked": True,
     "ref": "Williams, D. M., Darwish, S., Schneider, S., & Michael, D. R. (2020). Swiftaid Rodin Event-B models "
            "[dataset]. Zenodo. https://doi.org/10.5281/zenodo.3715494", "url": "https://zenodo.org/records/3715494",
     "kw": r"Donation|Charity|Tax"},
    # ── healthcare ──
    {"id": "S4", "kind": "ระบบ", "about": "เครื่องฟอกไต (ABZ 2016 case study)", "topics": ["HEA"],
     "ref": "Mashkoor, A. (2016). The hemodialysis machine case study. ABZ 2016.",
     "url": "https://irit.fr/ABZ-CS/html_files/files/2016/PDF/Case_Study_The%20Hemodialysis%20Machine_2016.pdf"},
    {"id": "S5", "kind": "ระบบ", "about": "อุปกรณ์การแพทย์ด้วย Event-B + Rodin", "topics": ["HEA"], "checked": True,
     "ref": "Mashkoor, A., & Biro, M. (2017). Towards the trustworthy development of active medical devices: "
            "A hemodialysis case study. arXiv:1706.06369.", "url": "https://arxiv.org/abs/1706.06369",
     "kw": r"Dialysis|Medical|Pill|Glucose|Oxygen|Medication"},
    {"id": "S6", "kind": "ระบบ", "about": "ระบบบริการสุขภาพ: จัดสรรผู้ป่วยให้ผู้ให้บริการ (Event-B)", "topics": ["HEA"],
     "ref": "Petre, L., et al. (2020). Event-B model of a healthcare system as distributed medical providers. "
            "Fundamenta Informaticae.", "url": "https://content.iospress.com/articles/fundamenta-informaticae/fi1886",
     "kw": r"Hospital|Patient|Triage|Telemedicine|Telehealth|Clinic|Appointment|Pharmacy|Lab(?!el)|Vaccine|Blood|Dental|Veterinary"},
    {"id": "S7", "kind": "ระบบ", "about": "ระบบสั่งการฉุกเฉิน / ดับเพลิง (Event-B workflow)", "checked": True,
     "ref": "Dghaym, D., Butler, M., & Salehi Fathabadi, A. (2014). Evaluation of graphical control flow management "
            "approaches for Event-B modelling. ECEASST, 66.", "url": "https://eceasst.org/index.php/eceasst/article/view/2094",
     "kw": r"Emergency|Dispatch|Ambulance|Disaster|Fire"},
    # ── transportation ──
    {"id": "S8", "kind": "ระบบ", "about": "ไฟจราจร (Rodin Handbook)", "kw": r"Traffic|Signal|Crossing",
     "ref": "Jastram, M., & Butler, M. Rodin User's Handbook — traffic light tutorial.",
     "url": "https://www3.hhu.de/stups/handbook/rodin/release-2014-12-04/html/tut_building_the_model.html"},
    {"id": "S9", "kind": "ระบบ", "about": "ระบบควบคุมรถไฟ (ABZ 2018 Hybrid ERTMS/ETCS Level 3)", "kw": r"Train|Rail|Metro|Tram",
     "ref": "Mammar, A., Frappier, M., Tueno Fotso, S. J., & Laleau, R. (2018). An Event-B model of the hybrid "
            "ERTMS/ETCS level 3 standard. ABZ 2018.", "url": "https://hal.archives-ouvertes.fr/hal-01797810"},
    {"id": "S10", "kind": "ระบบ", "about": "ควบคุมความเร็วรถยนต์ (ABZ 2020)", "topics": ["TRA"],
     "ref": "Mammar, A., & Frappier, M. (2020). Modeling of a speed control system using Event-B. ABZ 2020, 367–381.",
     "url": "https://doi.org/10.1007/978-3-030-48077-6_29",
     "kw": r"CarRental|Taxi|Ride|Vehicle|Scooter|Parking|Toll|Garage|GolfCart|FleetFuel|Bus(?!iness)|^EV|Shuttle|Bike"},
    {"id": "S11", "kind": "ระบบ", "about": "ระบบฐานล้อเครื่องบิน (ABZ 2014)", "checked": True,
     "ref": "Méry, D., & Singh, N. K. (2014). Modelling an aircraft landing system in Event-B (full report). arXiv:1407.0927.",
     "url": "https://arxiv.org/abs/1407.0927", "kw": r"Airport|Flight|Drone|Aircraft"},
    {"id": "S12", "kind": "ระบบ", "about": "เรือไร้คนขับเข้าเทียบท่า (Event-B + STPA)", "topics": ["LOG"],
     "ref": "Control logic verification of safety of the intended functionality for maritime autonomous surface ships "
            "based on Event-B: A case of autonomous berthing scenario.", "url": "https://trid.trb.org/View/2728291",
     "kw": r"Ship|Port|Cargo|Pilot|Seaport|Ferry"},
    # ── logistics ──
    {"id": "S13", "kind": "ระบบ", "about": "คลังสินค้าอัตโนมัติ (stacker crane) ใน Event-B", "topics": ["LOG"],
     "ref": "Event-B model of an automated storage and retrieval warehouse with stacker cranes. Tomas Bata University "
            "repository.", "url": "https://m.publikace.k.utb.cz/handle/10563/1008104",
     "kw": r"Warehouse|Picking|Forklift|Storage|Mailroom|Sorting|Inventory"},
    {"id": "S14", "kind": "ระบบ", "about": "การสื่อสารผู้ซื้อ–ผู้ขาย B2B (DEPLOY)", "topics": ["LOG"],
     "ref": "Hoang, T. S. Event-B model of buyer/seller (order/supply chain) communication. DEPLOY repository, eprint 128.",
     "url": "https://web-archive.southampton.ac.uk/deploy-eprints.ecs.soton.ac.uk/128/index.html",
     "kw": r"Reorder|Supply|Customs|Purchase|Parcel|Package|Delivery|Courier|Mail"},
    {"id": "S15", "kind": "formal อื่น", "about": "ป้องกันเครนท่าเรือชนกัน (Petri net)",
     "ref": "Kezić, D., Antonić, R., & Račić, N. (2006). Port cranes collision avoidance supervisor (Petri nets). "
            "Promet – Traffic & Transportation.", "url": "https://doaj.org/article/eca9ff9373974108bfd3dc156107cf13",
     "kw": r"Crane"},
    # ── smart home / building ──
    {"id": "S16", "kind": "ระบบ", "about": "ระบบ IoT (invariant ของสถาปัตยกรรม)", "topics": ["HOME", "AGR"], "checked": True,
     "ref": "Attiogbé, C., & Rocheteau, J. (2019). Architectural invariants and correctness of IoT-based systems. "
            "arXiv:1912.08912.", "url": "https://arxiv.org/abs/1912.08912", "kw": r"Smart|IoT|Sensor|Monitor|Tracker|Thermostat|Voice|Lighting|Camera|Laundry|Timing|AudioGuide"},
    {"id": "S17", "kind": "ระบบ", "about": "ประตู–กุญแจกับความปลอดภัยเมื่อเกิดไฟไหม้ (ตัวอย่าง Event-B)", "topics": ["HOME"],
     "checked": True, "ref": "Nicoletti, S. M., Peppelman, M., Kolb, C., & Stoelinga, M. (2021). Model-based joint "
                            "analysis of safety and security: Survey and identification of gaps. arXiv:2106.06272.",
     "url": "https://arxiv.org/abs/2106.06272", "kw": r"Door|Lock|Fire|Alarm|Security|Sprinkler|Gate(?!way)|Intercom"},
    {"id": "S18", "kind": "ระบบ", "about": "กุญแจห้องพักอิเล็กทรอนิกส์ (กรณีศึกษาของ Abrial)",
     "ref": "Electronic hotel key system (SCEH) specified in Event-B and animated with ProB. arXiv:1212.4959.",
     "url": "https://arxiv.org/abs/1212.4959", "kw": r"Hotel|Keyless|Locker|Badge"},
    # ── industrial / energy ──
    {"id": "S19", "kind": "ระบบ", "about": "โครงข่ายไฟฟ้าอัจฉริยะผ่าน IoT (Event-B dataset)", "topics": ["IND"],
     "ref": "University of Southampton. Event-B model of an IoT-enabled smart grid [dataset].",
     "url": "https://eprints.soton.ac.uk/498327",
     "kw": r"Grid|Solar|Energy|Battery|Wind|Turbine|PipelineLeak|Charging|SmartMeter|StreetLight"},
    {"id": "S20", "kind": "ระบบ", "about": "สายการผลิตโลหะ (production cell) ใน Event-B", "topics": ["IND"],
     "ref": "Gondal, A., Poppleton, M., Butler, M., & Snook, C. (2010). Feature-oriented modelling using Event-B. SETP-10.",
     "url": "https://eprints.soton.ac.uk/268579", "kw": r"Factory|Robot|Arm|Quality|Assembly|Mining|Crane"},
    # ── retail / food ──
    {"id": "S21", "kind": "ระบบ", "about": "ตู้ขายสินค้า (vending machine) ใน Event-B", "topics": ["RET"], "checked": True,
     "ref": "Stock, S., Leuschel, M., & Mashkoor, A. (2025). Failure divergence refinement for Event-B. arXiv:2505.19069.",
     "url": "https://arxiv.org/abs/2505.19069", "kw": r"Vending|Kiosk|Fridge"},
    {"id": "S22", "kind": "ระบบ", "about": "ตู้ขายสินค้าแบบ refine หลายขั้น + LTL", "checked": True,
     "ref": "Schneider, S., Treharne, H., Wehrheim, H., & Williams, D. (2014). Managing LTL properties in Event-B "
            "refinement. arXiv:1406.6622.", "url": "https://arxiv.org/abs/1406.6622", "kw": r"Vending"},
    {"id": "S23", "kind": "ระบบ", "about": "ซื้อของออนไลน์: ตะกร้า → ชำระเงิน → ส่งของ", "topics": ["RET"], "checked": True,
     "ref": "Babin, G., et al. (2014). A formal approach for correct-by-construction system substitution. arXiv:1404.7513.",
     "url": "https://arxiv.org/abs/1404.7513",
     "kw": r"Order|Grocery|Shopping|Cart|Marketplace|Checkout|Food|Concession|Truck|Cafe|Restaurant|Photo|Coffee|Auction"},
    # ── booking ──
    {"id": "S24", "kind": "ระบบ", "about": "จองห้องพักผ่าน REST service ใน Event-B", "topics": ["BOOK"], "checked": True,
     "ref": "Rauf, I., Vistbakka, I., & Troubitsyna, E. (2018). Formal verification of stateful services with REST APIs "
            "using Event-B. IEEE ICWS 2018, 131–138.",
     "url": "https://research.abo.fi/en/publications/formal-verification-of-stateful-services-with-rest-apis-using-eve/",
     "kw": r"Hotel|Reservation|Booking|Seat|Desk|Room|Rental|Ticket|Appointment|Queue"},
    # ── education / public ──
    {"id": "S25", "kind": "ระบบ", "about": "ระบบลงคะแนนเลือกตั้ง", "topics": ["EDU"], "kw": r"Vot|Ballot",
     "ref": "Gibson, J. P., Kherroubi, S., & Méry, D. (2017). Applying a dependency mechanism for voting protocol "
            "models using Event-B. FORTE 2017.", "url": "https://hal.archives-ouvertes.fr/hal-01658423"},
    {"id": "S26", "kind": "ระบบ", "about": "ระบบบริหารมหาวิทยาลัย: รับสมัคร สอบ เช็กชื่อ ผลการเรียน", "topics": ["EDU"],
     "ref": "Formal modeling and proving of Campus Management System: Event-B perspective. "
            "Bahria University Journal of ICT.", "url": "https://ojs.bahria.edu.pk/index.php/bujict/article/view/174",
     "kw": r"Exam|Course|Student|Attendance|Campus|Library|School|Childcare|Proctor|Grading|Quiz|Enroll|Boarding"},
    {"id": "S27", "kind": "ระบบ", "about": "ลงทะเบียนวิชา (ตัวอย่างในบทนำ Event-B)", "topics": ["EDU"],
     "ref": "Hoang, T. S. (2013). An introduction to the Event-B modelling method. In Industrial Deployment of System "
            "Engineering Methods. Springer.", "url": "https://www.southampton.ac.uk/~tsh2n14/publications/chapters/eventb-dbook13.pdf",
     "kw": r"Course|Enroll"},
    # ── IT ──
    {"id": "S28", "kind": "ระบบ", "about": "โปรโตคอลอุปกรณ์ IoT (LwM2M client)", "topics": ["IT"], "checked": True,
     "ref": "Mouakher, I., Dhaou, F., & Attiogbé, J. C. (2020). Toward a correct implementation of LwM2M client with "
            "Event-B. ICSOFT 2020.", "url": "https://www.scitepress.org/Papers/2020/98326/", "kw": r"Wifi|Hotspot|Router|Doorbell"},
    {"id": "S29", "kind": "ระบบ", "about": "ยืนยันตัวตน / สิทธิ์การเข้าถึง (authentication pattern)", "topics": ["IT"],
     "ref": "Yagmahan, Rezazadeh, & Butler (2024). Authentication pattern and serverless access control in Event-B "
            "(ABZ 2024) [dataset].", "url": "https://eprints.soton.ac.uk/489451/",
     "kw": r"Login|OTP|Auth|Access|Portal|Verification|Parental|Passport|Permit|Check-?In|CheckIn|Visitor"},
    {"id": "S30", "kind": "ระบบ", "about": "ประกอบ web service (BPEL) แล้วตรวจด้วย Event-B", "topics": ["IT"],
     "ref": "Verification and validation of web service composition using Event B method. HAL hal-00634407.",
     "url": "https://hal.archives-ouvertes.fr/hal-00634407",
     "kw": r"Cloud|Pipeline|Gateway|Backup|Streaming|Publishing|Job|API|Escrow|Server|Insurance|Archive|Document"},
    {"id": "S31", "kind": "ระบบ", "about": "คลังรูปแบบการสื่อสารสำหรับระบบกระจาย (Event-B)", "topics": ["IT"],
     "ref": "Modeling communication semantics for distributed systems in Event-B. WTF (SBC).",
     "url": "https://sol.sbc.org.br/index.php/wtf/article/view/23083",
     "kw": r"Chat|Messag|SMS|Email|Notification|Broadcast|Podcast|Alert|Satellite"},
    # ── agriculture ──
    {"id": "S32", "kind": "ระบบ", "about": "ตัวควบคุมปั๊มน้ำ (Event-B, refine 2 ขั้น)", "topics": ["AGR"], "checked": True,
     "ref": "Karmakar, R., Sarkar, B. B., & Chaki, N. (2020). Event-B based formal modeling of a controller: A case study. "
            "EasyChair Preprint.", "url": "https://easychair.org/publications/preprint/NGXM",
     "kw": r"Irrigation|Pump|Water|Rain|Leak|Aquarium|Sprinkler"},
    {"id": "S33", "kind": "formal อื่น", "about": "model checking สำหรับเกษตรแม่นยำ (timed automata)", "topics": ["AGR"],
     "ref": "Model-checking pour l'agriculture de précision [doctoral thesis]. Université de Montpellier.",
     "url": "https://esploro.umontpellier.fr/esploro/outputs/doctoral/Model-checking-pour-lagriculture-de-précision/9939414009311",
     "kw": r"Farm|Crop|Livestock|Beehive|Greenhouse|Soil|Milking|Feeder|Forest|Recycling|Waste|Trash"},
]


def similar_rows(rows):
    """For each model: the published work whose system (by name, else by topic) or method is similar."""
    import re
    out = []
    for r in rows:
        code = TOPIC[r["case"]]
        by_name = [x["id"] for x in SIMILAR if x.get("kw") and re.search(x["kw"], r["case"])]
        by_topic = [x["id"] for x in SIMILAR if code in x.get("topics", []) and x["id"] not in by_name]
        out.append({"model_id": r["id"], "case": r["case"], "topic": r["topic"],
                    "similar_system": "; ".join(by_name), "similar_topic": "; ".join(by_topic),
                    "similar_method": "; ".join(x["id"] for x in SIMILAR if x.get("all"))})
    return out


def provenance():
    commit = subprocess.run(["git", "-C", PROJECT, "log", "-1", "--format=%h (%ad)", "--date=short", "main", "--",
                             "eventb_generator.py", "xml_parser.py", "rodin_exporter.py"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    py = sys.version.split()[0]
    return [(k, v.format(repo=CONVERTER_REPO, commit=commit, python=py)) for k, v in PROVENANCE]


ERROR_TH = {"inverted1": "ช่วงเวลากลับด้าน 1 จุด", "inverted2": "ช่วงเวลากลับด้าน 2 จุด",
            "inverted3": "ช่วงเวลากลับด้าน 3 จุด", "inverted_frame": "ช่วงเวลากลับด้านใน fragment",
            "mod_alt": "mod กับตัวนับ loop (alt)", "mod_opt": "mod กับตัวนับ loop (opt)",
            "mod_inverted": "ช่วงเวลากลับด้าน + mod"}


def provenance_rows(rows):
    """One row per model: origin, how the diagram was made, diagram error, conversion and proof."""
    commit = subprocess.run(["git", "-C", PROJECT, "log", "-1", "--format=%h", "main", "--",
                             "eventb_generator.py", "xml_parser.py", "rodin_exporter.py"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    out = []
    for r in rows:
        m = json.load(open(os.path.join(DATASET, "models", r["id"], "meta.json")))
        batch = m.get("batch") or ""
        if r["id"] == "model_001":
            origin, detail, gen = ("งานเดิมของผู้วิจัย",
                                   "กรณีศึกษาจากงานวิทยานิพนธ์เดิม แผนภาพและไฟล์ .bum ต้นฉบับสูญหาย "
                                   "จึงสร้าง model.txt กลับจากไฟล์ Rodin (.buc / .bpo) มีเฉพาะชื่อ event", "")
        elif batch == "round1":
            origin, gen = "รอบแรก: กำหนดสถานการณ์ทีละแบบ", "script เขียนไฟล์ draw.io"
            detail = "กำหนดสถานการณ์และโครงสร้างทีละแบบ แล้วเขียนเป็นไฟล์ draw.io ด้วย script"
            if "round1_version" in m:
                gen += " + redo_round1.py"
                detail += ("; 23 ต.ค. 2026 เพิ่มจุดผิดลงในแผนภาพเดิม แทนการแก้ Event-B หลังแปลง"
                           if r["result"] == "fail" else "; 23 ต.ค. 2026 แปลงใหม่จากแผนภาพเดิมโดยไม่เติม invariant")
        else:
            origin, gen = f"สร้างอัตโนมัติ ({batch})", "gen_batch.py"
            detail = f"สุ่มโครงสร้างด้วย seed {m.get('seed')} อย่างน้อย {m.get('min_msgs')} message"
            if r["result"] == "fail":
                detail += " และเขียนจุดผิดลงในแผนภาพตอนสร้าง"
        out.append({
            "model_id": r["id"], "case": r["case"], "topic": r["topic"], "result": r["result"],
            "origin": origin, "origin_detail": detail, "generator": gen, "seed": m.get("seed", ""),
            "diagram_created": m.get("diagram_created") or "",
            "diagram_error": ERROR_TH.get(m.get("mutation_type"), ""),
            "error_detail": m["mutation"] if m.get("variant") == "diagram_error" else "",
            "converter": "ChronoSeq-B (รุ่นเดิม)" if r["id"] == "model_001" else f"ChronoSeq-B {commit}",
            "prover": "Rodin" if r["id"] == "model_001" else "Rodin + Atelier B (ML/PP)",
            "proved_on": m.get("proved_on", ""), "total_po": r["total_po"], "failed": r["failed"],
            "earlier_version": (m.get("round1_version") or "").replace(" (archived)", ""),
        })
    return out


def provenance_pdf(out, prov):
    groups = [("งานเดิมของผู้วิจัย", lambda p: p["model_id"] == "model_001"),
              ("รอบแรก: กำหนดสถานการณ์ทีละแบบ", lambda p: p["origin"].startswith("รอบแรก")),
              ("สร้างอัตโนมัติ", lambda p: p["origin"].startswith("สร้างอัตโนมัติ"))]
    h = ["<h1>ที่มาของแบบจำลองแต่ละตัว</h1>",
         f"<div class='sub'>{len(prov)} แบบจำลอง · ข้อมูลสังเคราะห์ ไม่ได้นำมาจากชุดข้อมูลภายนอก · "
         "ตารางเดียวกันอยู่ใน csv/provenance.csv</div>"]
    h.append("<h2>1. สรุปตามที่มา</h2><table><tr><th>ที่มา</th><th>แบบจำลอง</th><th>วิธีสร้างแผนภาพ</th>"
             "<th>สร้างแผนภาพ</th><th>พิสูจน์</th><th>ผ่าน / ไม่ผ่าน</th></tr>")
    how = {"งานเดิมของผู้วิจัย": "กรณีศึกษาเดิม (สร้าง model.txt กลับจากไฟล์ Rodin)",
           "รอบแรก: กำหนดสถานการณ์ทีละแบบ": "กำหนดสถานการณ์ทีละแบบ เขียนเป็นไฟล์ draw.io ด้วย script "
                                          "(21 แบบจำลองแก้ใหม่ 23 ต.ค. 2026 ดูคอลัมน์ประวัติ)",
           "สร้างอัตโนมัติ": "สุ่มด้วย gen_batch.py (batch_02 / 03 / 04) seed คงที่ สร้างซ้ำได้"}
    for name, f in groups:
        g = [p for p in prov if f(p)]
        dates = sorted({p["diagram_created"] for p in g if p["diagram_created"]})
        proved = sorted({p["proved_on"] for p in g})
        span = lambda d: "–" if not d else d[0] if len(d) == 1 else f"{d[0]}<br>ถึง {d[-1]}"
        h.append(f"<tr><td>{esc(name)}</td><td class='n'>{len(g)}</td><td>{esc(how[name])}</td>"
                 f"<td class='d'>{span(dates)}</td><td class='d'>{span(proved)}</td>"
                 f"<td class='n'>{sum(p['result'] == 'pass' for p in g)} / {sum(p['result'] == 'fail' for p in g)}</td></tr>")
    h.append("</table>")
    h.append("<p>ทุกแบบจำลอง (ยกเว้น model_001) แปลงด้วย ChronoSeq-B และพิสูจน์ด้วย Rodin + Atelier B (ML/PP) "
             "แบบจำลองที่ไม่ผ่านมีจุดผิดอยู่ในแผนภาพเท่านั้น</p>")
    h.append("<h2>2. รายแบบจำลอง</h2>")
    for name, f in groups:
        g = [p for p in prov if f(p)]
        h.append(f"<h3>{esc(name)} ({len(g)})</h3><table class='prov'><tr><th>ID</th><th>แบบจำลอง</th><th>ผล</th>"
                 "<th>วิธีสร้าง</th><th>seed</th><th>สร้างแผนภาพ</th><th>จุดผิดในแผนภาพ</th><th>พิสูจน์</th></tr>")
        for p in g:
            how_one = p["generator"] or "สร้างกลับจากไฟล์ Rodin"
            if p["earlier_version"]:
                how_one += f"<br><span class='ln'>เดิม: {esc(p['earlier_version'][:70])}…</span>"
            h.append(f"<tr><td>{p['model_id']}</td><td>{esc(p['case'])}</td>"
                     f"<td class='res-{p['result']}'>{p['result']}</td><td>{how_one if p['earlier_version'] else esc(how_one)}</td>"
                     f"<td class='n'>{p['seed']}</td><td class='d'>{p['diagram_created'] or '–'}</td>"
                     f"<td>{esc(p['diagram_error']) or '–'}</td><td class='d'>{p['proved_on']}</td></tr>")
        h.append("</table>")
    css = (CSS + EXTRA_CSS + "td.res-pass { color: #2e7d5b; font-weight: bold; } td.res-fail { color: #c0392b; font-weight: bold; }"
           "table.prov { font-size: 8.4pt; } table.prov td { padding: 2px 5px; } td.d { white-space: nowrap; }")
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "prov.html")
        open(page, "w").write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{css}</style></head>"
                              f"<body>{''.join(h)}</body></html>")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(out, 'PROVENANCE.pdf')}", f"file://{page}"],
                       check=True, capture_output=True)


def write_sources(out):
    import re
    md = ["# แหล่งที่มา (Sources)", "", "## ที่มาของข้อมูล", "", "| รายการ | รายละเอียด |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in provenance()]
    md += ["", "ที่มาของแบบจำลองทีละตัว (วิธีสร้าง, seed, วันที่, จุดผิด, วันที่พิสูจน์): "
           "`csv/provenance.csv` และ `PROVENANCE.pdf`"]
    md += ["", "## เอกสารอ้างอิง", ""]
    md += [f"{k}. " + re.sub(r"</?i>", "*", r) for k, r in enumerate(REFERENCES, start=1)]
    md += ["", "## งานที่เกี่ยวข้อง", "",
           "งานด้านล่างใกล้เคียงกับงานนี้ด้านข้อมูล วิธีการ หรือเครื่องมือ ใช้เป็นงานที่เกี่ยวข้องเท่านั้น "
           "**ไม่ใช่แหล่งที่มาของข้อมูล** — ข้อมูลในชุดนี้สร้างขึ้นเองทั้งหมด (ดูหัวข้อที่มาของข้อมูล)", ""]
    md += [f"- **{k}** — " + re.sub(r"</?i>", "*", r) for k, r in RELATED]
    md += ["", "## งานที่คล้ายกับแบบจำลองของเรา", "",
           "ค้นจากเว็บเมื่อ 27 ต.ค. 2026 — คล้ายด้านระบบหรือวิธีการ **ไม่ใช่แหล่งที่มาของข้อมูล** "
           "แบบจำลองแต่ละตัวจับคู่กับงานเหล่านี้ใน `csv/similar_work.csv` (ตามชื่อระบบก่อน ถ้าไม่พบใช้ตามหัวข้อ) "
           "✓ = เปิดตรวจชื่อเรื่องและผู้แต่งแล้ว รายการอื่นมาจากผลค้นหา ควรเปิดตรวจก่อนอ้างในเล่ม", "",
           "| รหัส | ด้าน | คล้ายเรื่อง | อ้างอิง | ตรวจ |", "|---|---|---|---|---|"]
    md += [f"| {x['id']} | {x['kind']} | {x['about']} | {x['ref']} {x['url']} | {'✓' if x.get('checked') else ''} |"
           for x in SIMILAR]
    md += ["", "ไม่พบงานที่ใช้ LLM ทำนายผล Proof Obligation ของ Event-B (ณ วันที่ค้น) — จุดนี้เป็นช่องว่างที่งานนี้เติมได้"]
    open(os.path.join(out, "SOURCES.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
SYSTEM = ("You are an Event-B proof-obligation analyst. Given an Event-B model (context and machine) "
          "generated by ChronoSeq-B from a sequence diagram, predict the proof obligations that Rodin "
          "(auto-provers with Atelier B ML/PP) generates for the machine and context, and which of them "
          "it cannot discharge. Answer with JSON only.")
QUESTION = ("How many proof obligations does this model have, how many are discharged, how many fail, "
            "and which ones fail?\n\nEvent-B model:\n```\n{model}\n```")


def kind(failed_pos):
    kinds = sorted({p.split("/")[-1] for p in failed_pos})
    return "+".join(kinds) if kinds else "none"


def assign_splits(rows, seed):
    groups = defaultdict(list)
    for r in rows:
        if r["id"] != "model_001":
            groups[(r["result"], r["fail_kind"])].append(r["id"])
    split = {"model_001": "test"}
    for key in sorted(groups):
        ids = sorted(groups[key], key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
        n = len(ids)
        n_val = round(n * SPLIT[1][1])
        n_test = round(n * SPLIT[2][1])
        for k, i in enumerate(ids):
            split[i] = "val" if k < n_val else "test" if k < n_val + n_test else "train"
    return split


def chat(r):
    answer = {"total_po": r["total_po"], "discharged": r["discharged"], "failed": r["failed"],
              "failed_pos": r["failed_pos"]}
    return {"id": r["id"], "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUESTION.format(model=r["model"])},
        {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}]}


def load():
    rows, po_rows = [], []
    cats = {r["model_id"]: r for r in csv.DictReader(open(os.path.join(DATASET, "model_categories.csv")))}
    for line in open(os.path.join(DATASET, "dataset.jsonl")):
        d = json.loads(line)
        mdir = os.path.join(DATASET, "models", d["id"])
        pos = json.load(open(os.path.join(mdir, "po_details.json")))
        failed_pos = sorted(p["po"] for p in pos if not p["discharged"])
        assert len(failed_pos) == d["failed"] and len(pos) == d["total_po"], d["id"]
        code = TOPIC[d["case"]]
        rows.append({**d, "topic": TOPIC_NAMES[code][0], "topic_th": TOPIC_NAMES[code][1],
                     "result": "fail" if d["failed"] else "pass", "failed_pos": failed_pos,
                     "fail_kind": kind(failed_pos), "category": cats[d["id"]]})
        po_rows += [{"id": d["id"], **p} for p in pos]
    return rows, po_rows


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def build(out, seed):
    rows, po_rows = load()
    split = assign_splits(rows, seed)
    for r in rows:
        r["split"] = split[r["id"]]
    if os.path.exists(out):
        shutil.rmtree(out)
    for sub in ("upload", "data", "csv", "models", "by_topic"):
        os.makedirs(os.path.join(out, sub))

    for name, _ in SPLIT:
        with open(os.path.join(out, "upload", f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                if r["split"] == name:
                    f.write(json.dumps(chat(r), ensure_ascii=False) + "\n")
    feats = [k for k in rows[1] if k.startswith("n_") or k in ("fragments", "max_nesting_depth")]
    with open(os.path.join(out, "data", "dataset.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            keep = {k: r.get(k) for k in ["id", "case", "topic", "topic_th", "split", "model"] + feats
                    + ["total_po", "discharged", "failed", "discharge_rate", "failed_pos"]}
            f.write(json.dumps(keep, ensure_ascii=False) + "\n")
    with open(os.path.join(out, "data", "po_details.jsonl"), "w", encoding="utf-8") as f:
        for p in po_rows:
            f.write(json.dumps({k: p[k] for k in ("id", "po", "component", "type", "discharged")},
                               ensure_ascii=False) + "\n")
    write_csv(os.path.join(out, "data", "split.csv"), rows, ["id", "split"])

    num = [k for k in feats if k != "fragments"]
    write_csv(os.path.join(out, "csv", "summary.csv"), rows,
              ["id", "case", "topic", "topic_th", "split", "result"] + num
              + ["total_po", "discharged", "failed", "discharge_rate", "fail_kind"])
    write_csv(os.path.join(out, "csv", "pass_fail_list.csv"), rows,
              ["id", "case", "topic_th", "split", "result", "total_po", "failed", "fail_kind"])
    cat_rows = [{**r["category"], "split": r["split"]} for r in rows]
    write_csv(os.path.join(out, "csv", "model_categories.csv"), cat_rows,
              list(rows[0]["category"]) + ["split"])

    for r in rows:
        src, dst = os.path.join(DATASET, "models", r["id"]), os.path.join(out, "models", r["id"])
        os.makedirs(dst)
        for f in ("model.txt", "label.json", "po_details.json", "features.json"):
            if os.path.exists(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), dst)

    by_topic(out, rows)
    sim = similar_rows(rows)
    write_csv(os.path.join(out, "csv", "similar_work.csv"), sim, list(sim[0]))
    prov = provenance_rows(rows)
    write_csv(os.path.join(out, "csv", "provenance.csv"), prov, list(prov[0]))
    provenance_pdf(out, prov)
    write_sources(out)
    pdf(out, rows, po_rows)
    make_user_flow.main(out)
    return rows


def by_topic(out, rows):
    """by_topic/<NN_Topic>/<pass|fail>/<model_XXX_Case>/ + list.csv per topic (Rodin results)."""
    for k, (code, (en, th)) in enumerate(TOPIC_NAMES.items(), start=1):
        group = sorted((r for r in rows if r["topic"] == en), key=lambda r: r["id"])
        name = en.replace(" & ", "_and_").replace(", ", "_").replace(" ", "_")
        tdir = os.path.join(out, "by_topic", f"{k:02d}_{name}")
        for r in group:
            res = "fail" if r["failed"] else "pass"
            dst = os.path.join(tdir, res, f"{r['id']}_{r['case'].replace(' ', '').replace('&', 'And')}")
            shutil.copytree(os.path.join(out, "models", r["id"]), dst)
        with open(os.path.join(tdir, "list.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["model_id", "case", "result", "total_po", "discharged", "failed", "failed_pos", "split"])
            for r in group:
                w.writerow([r["id"], r["case"], "fail" if r["failed"] else "pass", r["total_po"],
                            r["discharged"], r["failed"], "; ".join(r["failed_pos"]), r["split"]])


EXTRA_CSS = """
.upload { border: 2px solid #2e7d5b; background: #e6f4ec; border-radius: 6px; padding: 8px 12px; margin: 8px 0; }
.warn { border-left: 4px solid #c0392b; background: #fdecea; padding: 6px 10px; margin: 8px 0; }
.kpi { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 8px 0 4px; }
.kpi div { border: 1px solid #cfd6e1; border-radius: 6px; padding: 6px 10px; }
.kpi b { display: block; font-size: 17pt; color: #12325c; font-variant-numeric: tabular-nums; }
.kpi span { font-size: 8.8pt; color: #5a6475; }
pre.wrap { white-space: pre-wrap; word-break: break-all; }
ol.refs li { margin-bottom: 4px; font-size: 9.6pt; overflow-wrap: anywhere; }
"""


def pdf(out, rows, po_rows):
    n = len(rows)
    n_fail = sum(r["result"] == "fail" for r in rows)
    tot = sum(r["total_po"] for r in rows)
    bad = sum(r["failed"] for r in rows)
    po_total = sorted(r["total_po"] for r in rows)
    h = ["<h1>EventB PO Dataset — ชุดสำหรับเทรน AI</h1>",
         f"<div class='sub'>{n} โมเดล · label จาก Rodin + Atelier B (ML/PP) · ทุกโมเดลเป็นผลของสูตรแปลง ChronoSeq-B</div>",
         "<div class='kpi'>"
         f"<div><b>{n}</b><span>โมเดล</span></div>"
         f"<div><b>{n - n_fail} / {n_fail}</b><span>pass / fail</span></div>"
         f"<div><b>{tot:,}</b><span>PO ทั้งหมด</span></div>"
         f"<div><b>{bad}</b><span>PO ที่พิสูจน์ไม่ได้</span></div></div>"]

    h.append("<h2>1. ต้องอัปอะไรไปเทรน</h2>")
    counts = Counter(r["split"] for r in rows)
    h.append("<div class='upload'><b>อัป 2 ไฟล์นี้ไปเทรน (fine-tune)</b><br>"
             f"<code>upload/train.jsonl</code> ({counts['train']} โมเดล) — ใช้เทรน<br>"
             f"<code>upload/val.jsonl</code> ({counts['val']} โมเดล) — ใช้ตรวจระหว่างเทรน (validation file)<br><br>"
             f"<b>ห้ามอัป</b> <code>upload/test.jsonl</code> ({counts['test']} โมเดล) — เก็บไว้วัดผลหลังเทรนเท่านั้น</div>")
    h.append("<p>ไฟล์ทั้ง 3 เป็นรูปแบบ chat (<code>messages</code>: system / user / assistant) "
             "ใช้กับ OpenAI fine-tuning, Hugging Face (TRL / SFTTrainer) และเครื่องมือส่วนใหญ่ได้ตรง ๆ "
             "ถ้าเครื่องมือที่ใช้ต้องการรูปแบบอื่น ใช้ <code>data/dataset.jsonl</code> แปลงต่อได้</p>")
    h.append("<table><tr><th>ถ้าจะทำ</th><th>ใช้ไฟล์</th></tr>"
             "<tr><td>Fine-tune LLM</td><td><code>upload/train.jsonl</code> + <code>upload/val.jsonl</code></td></tr>"
             "<tr><td>วัดผลหลังเทรน</td><td><code>upload/test.jsonl</code> — ให้โมเดลตอบจากข้อความ user แล้วเทียบกับคำตอบ assistant</td></tr>"
             "<tr><td>RAG (ค้นโมเดลที่คล้ายมาเป็นตัวอย่าง)</td><td>ทำดัชนีจาก train ใน <code>data/dataset.jsonl</code> "
             "(คอลัมน์ <code>model</code> + label) แล้วทดสอบกับ test</td></tr>"
             "<tr><td>ML ทั่วไปจาก feature (ไม่ใช้ LLM)</td><td><code>csv/summary.csv</code> (คอลัมน์ n_* = input, total_po / failed = เป้าหมาย)</td></tr></table>")

    h.append("<h2>2. ตัวอย่างข้อมูล 1 รายการ</h2>")
    ex = next(r for r in rows if r["split"] == "train" and r["result"] == "fail" and r["failed"] == 2)
    c = chat(ex)
    short = c["messages"][1]["content"]
    short = short[:short.index("```") + 380] + "\n... (ต่อจนจบโมเดล) ...\n```"
    h.append("<pre class='wrap'>" + esc(json.dumps({"id": c["id"], "messages": [
        {"role": "system", "content": "You are an Event-B proof-obligation analyst. ... Answer with JSON only."},
        {"role": "user", "content": short},
        c["messages"][2]]}, ensure_ascii=False, indent=1)) + "</pre>")
    h.append("<p>คำตอบ (assistant) = จำนวน PO ทั้งหมด, ที่พิสูจน์ได้, ที่ล้ม และชื่อ PO ที่ล้ม — "
             "ชื่อ PO อ่านแบบ <code>&lt;event&gt;/&lt;label&gt;/&lt;ชนิด&gt;</code> เช่น <code>INITIALISATION/act12/FIS</code></p>")

    h.append("<h2>3. โครงสร้าง folder</h2>")
    tree = ["EventB_PO_Training/",
            "├── README.pdf                ← ไฟล์นี้",
            "├── upload/                   ← ไฟล์สำหรับเทรน",
            "│   ├── train.jsonl",
            "│   ├── val.jsonl",
            "│   └── test.jsonl            ← ห้ามใช้เทรน",
            "├── data/",
            "│   ├── dataset.jsonl         ← ทุกโมเดล: ข้อความ Event-B + feature + label + topic + split",
            "│   ├── po_details.jsonl      ← ผลราย PO (ผ่าน / ไม่ผ่าน)",
            "│   └── split.csv             ← โมเดลไหนอยู่ train / val / test",
            "├── csv/",
            "│   ├── summary.csv           ← ตัวเลขต่อโมเดล (feature + label)",
            "│   ├── pass_fail_list.csv    ← pass / fail ต่อโมเดล",
            "│   └── model_categories.csv  ← หัวข้อ + จุดผิดใน diagram (ใช้วิเคราะห์ ห้ามเป็น input)",
            "├── models/model_001 … model_198/",
            "│   ├── model.txt             ← Event-B (input)",
            "│   ├── label.json            ← total / discharged / failed",
            "│   ├── po_details.json       ← ผลราย PO",
            "│   └── features.json",
            "├── by_topic/                 ← โมเดลชุดเดียวกัน แยกตามหัวข้อ และผล Rodin",
            "│   ├── 01_Finance_and_Payment/",
            "│   │   ├── list.csv          ← รายชื่อ + ผล ของหัวข้อนี้",
            "│   │   ├── pass/model_003_ATMWithdrawal/ …",
            "│   │   └── fail/model_004_BankTransfer/ …",
            "│   └── … (11 หัวข้อ)",
            "├── FLOW.pdf · FLOW.png       ← แผนภาพขั้นตอนการดำเนินงาน",
            "├── PROVENANCE.pdf            ← ที่มาของแบบจำลองแต่ละตัว (csv/provenance.csv)",
            "└── SOURCES.md                ← แหล่งที่มาและเอกสารอ้างอิง"]
    h.append("<pre>" + esc("\n".join(tree)) + "</pre>")

    h.append("<h2>4. การแบ่ง train / val / test</h2>")
    h.append("<p>แบ่ง 70 / 15 / 15 แบบรักษาสัดส่วน pass/fail และชนิดของ PO ที่ล้มให้เท่ากันทุกชุด "
             "(ใช้ seed คงที่ — สร้างใหม่ได้ผลเดิม) · model_001 (Payment) อยู่ใน test เสมอ</p>")
    kinds = ["none", "FIS", "WD", "FIS+WD"]
    h.append("<table><tr><th>ชุด</th><th>โมเดล</th><th>pass</th><th>fail: FIS</th><th>fail: WD</th><th>fail: FIS+WD</th><th>PO</th></tr>")
    for name, _ in SPLIT:
        g = [r for r in rows if r["split"] == name]
        kc = Counter(r["fail_kind"] for r in g)
        h.append(f"<tr><td>{name}</td><td class='n'>{len(g)}</td>" + "".join(f"<td class='n'>{kc[k]}</td>" for k in kinds)
                 + f"<td class='n'>{sum(r['total_po'] for r in g):,}</td></tr>")
    h.append("</table>")

    h.append("<h2>5. สถิติ</h2>")
    h.append(f"<p>PO ต่อโมเดล: ต่ำสุด {po_total[0]} · มัธยฐาน {statistics.median(po_total):g} · สูงสุด {po_total[-1]} "
             f"· ความยาวข้อความ Event-B เฉลี่ย {sum(len(r['model']) for r in rows) // n:,} ตัวอักษร</p>")
    tc = Counter(p["type"] for p in po_rows)
    fc = Counter(p["type"] for p in po_rows if not p["discharged"])
    h.append("<table><tr><th>ชนิด PO</th><th>ความหมาย</th><th>ทั้งหมด</th><th>ล้ม</th></tr>")
    mean = {"INV": "invariant ยังจริงหลัง event", "FIS": "action :∈ มีค่าให้เลือก", "WD": "สูตรคำนวณได้ (เช่น mod)",
            "THM": "theorem", "GRD": "guard refinement"}
    for t, k in tc.most_common():
        h.append(f"<tr><td><code>{esc(t)}</code></td><td>{esc(mean.get(t, ''))}</td><td class='n'>{k:,}</td><td class='n'>{fc[t]}</td></tr>")
    h.append("</table>")
    h.append("<table style='break-inside:avoid'><tr><th>หัวข้อ</th><th>pass</th><th>fail</th><th>รวม</th><th>train / val / test</th></tr>")
    for code, (en, th) in TOPIC_NAMES.items():
        g = [r for r in rows if r["topic"] == en]
        sc = Counter(r["split"] for r in g)
        h.append(f"<tr><td>{esc(th)}</td><td class='n'>{sum(r['result'] == 'pass' for r in g)}</td>"
                 f"<td class='n'>{sum(r['result'] == 'fail' for r in g)}</td><td class='n'>{len(g)}</td>"
                 f"<td class='n'>{sc['train']} / {sc['val']} / {sc['test']}</td></tr>")
    h.append("</table>")

    h.append("<h2>6. ข้อควรรู้ก่อนเทรน</h2><ul>")
    h.append("<li><b>input มีแค่ข้อความ Event-B</b> (<code>model.txt</code>) — "
             "ห้ามใส่คอลัมน์ใน <code>model_categories.csv</code> เช่น ชนิดจุดผิด หรือ expected เพราะเป็นเฉลย</li>")
    h.append("<li><b>PO ที่ล้มมีแค่ FIS กับ WD</b> — สูตรแปลงทำให้ INV ไม่ล้มจาก diagram "
             "โมเดลที่เทรนจะเรียนรู้รูปแบบ <code>:∈ a..b</code> ที่ a &gt; b และ <code>mod</code> กับตัวนับ loop "
             "ซึ่งตรงกับพฤติกรรมจริงของสูตรแปลง แต่ไม่ครอบคลุมความผิดแบบอื่น</li>")
    h.append("<li><b>label ขึ้นกับ prover</b> — ทั้งชุดใช้ Rodin + Atelier B (ML/PP) ค่าเดียวกัน "
             "ถ้ารันด้วย prover อื่นจำนวนที่พิสูจน์ได้อาจต่าง</li>")
    h.append(f"<li><b>ข้อความยาว</b> — เฉลี่ยราว {sum(len(r['model']) for r in rows) // n // 3:,} token ต่อโมเดล "
             f"(ยาวสุดราว {max(len(r['model']) for r in rows) // 3:,} token) ควรเลือก LLM ที่รับ context ได้อย่างน้อย 8k</li>")
    h.append("<li>สร้าง folder นี้ใหม่ได้ด้วย <code>python tools/make_release.py</code> ใน EventB_PO_Dataset</li></ul>")

    h.append("<h2>7. แหล่งที่มา</h2><h3>ที่มาของข้อมูล</h3><table><tr><th style='width:20%'>รายการ</th><th>รายละเอียด</th></tr>")
    h += [f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in provenance()]
    h.append("</table><h3>เอกสารอ้างอิง</h3><ol class='refs'>")
    h += [f"<li>{r}</li>" for r in REFERENCES]
    h.append("</ol><h3>งานที่เกี่ยวข้อง</h3><p>ใกล้เคียงด้านข้อมูล วิธีการ หรือเครื่องมือ — เป็นงานที่เกี่ยวข้องเท่านั้น "
             "<b>ไม่ใช่แหล่งที่มาของข้อมูล</b> ข้อมูลในชุดนี้สร้างขึ้นเองทั้งหมด</p>"
             "<table><tr><th style='width:20%'>ด้าน</th><th>อ้างอิง</th></tr>")
    h += [f"<tr><td>{esc(k)}</td><td>{r}</td></tr>" for k, r in RELATED]
    h.append("</table>")
    sim = similar_rows(rows)
    h.append("<h3>งานที่คล้ายกับแบบจำลองของเรา</h3><p>ค้นจากเว็บเมื่อ 27 ต.ค. 2026 — คล้ายด้านระบบหรือวิธีการ "
             "<b>ไม่ใช่แหล่งที่มาของข้อมูล</b> · การจับคู่รายแบบจำลองอยู่ใน <code>csv/similar_work.csv</code> · "
             "✓ = เปิดตรวจชื่อเรื่องและผู้แต่งแล้ว รายการอื่นมาจากผลค้นหา ควรเปิดตรวจก่อนอ้างในเล่ม</p><table style='font-size:8.4pt'><tr><th>รหัส</th><th>คล้ายเรื่อง</th>"
             "<th>อ้างอิง</th><th>ตรวจ</th><th>แบบจำลอง</th></tr>")
    for x in SIMILAR:
        n = sum(x["id"] in "; ".join((q["similar_system"], q["similar_topic"], q["similar_method"])).split("; ")
                for q in sim)
        h.append(f"<tr><td>{x['id']}</td><td>{esc(x['about'])}</td><td style='overflow-wrap:anywhere'>{esc(x['ref'])}"
                 f"{'<br>' + esc(x['url']) if x['url'] else ''}</td><td>{'✓' if x.get('checked') else ''}</td>"
                 f"<td class='n'>{n}</td></tr>")
    h.append("</table><p>ไม่พบงานที่ใช้ LLM ทำนายผล Proof Obligation ของ Event-B ณ วันที่ค้น "
             "— เป็นช่องว่างที่งานนี้เติมได้</p>")

    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "readme.html")
        open(page, "w").write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{CSS}{EXTRA_CSS}"
                              f"</style></head><body>{''.join(h)}</body></html>")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(out, 'README.pdf')}", f"file://{page}"],
                       check=True, capture_output=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(DATASET), "EventB_PO_Training"))
    ap.add_argument("--seed", type=int, default=20261026)
    a = ap.parse_args()
    rows = build(os.path.abspath(a.out), a.seed)
    print(os.path.abspath(a.out), Counter(r["split"] for r in rows))
