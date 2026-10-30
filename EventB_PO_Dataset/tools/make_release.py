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
    models/model_XXX/           model.txt, label.json, po_details.json, features.json, tree.txt, tree.json
    by_topic/<NN_Topic>/<pass|fail>/<model_XXX_Case>/   the same models grouped by topic and
                                Rodin result, with a list.csv per topic
    FLOW.pdf, FLOW.png          workflow diagram (tools/make_user_flow.py)
    SOURCES.md                  provenance (tools, versions, dates) and references
    PROVENANCE.pdf, csv/provenance.csv   where every single model came from
    SIMILAR_WORK.pdf, csv/similar_work.csv   published work similar to each model (related work)
    trees/                      event tree + guard tree of each model (tools/extract_trees.py): SUMMARY.pdf,
                                TREES.pdf, csv tables, by_topic/ text files; checked against the diagrams by
                                tools/verify_trees.py. data/trees.jsonl holds the same trees as data.

Nothing that reveals the answer (meta.json, diagrams, Rodin files) is copied into the
inputs. The split is stratified by result and by kind of failing PO; model_001 (the
reconstructed Payment case kept for testing) always goes to test.
"""
import argparse, csv, glob, hashlib, html, json, os, re, shutil, statistics, subprocess, sys, tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from categorize import TOPIC, TOPIC_NAMES                       # noqa: E402
from make_batch_report import CHROME, CSS, esc                  # noqa: E402
import extract_trees, make_tree_report, make_user_flow, verify_trees   # noqa: E402

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
    "Abrial, J.-R. (2010). <i>Modeling in Event-B: System and Software Engineering</i>. Cambridge University Press. "
    "https://doi.org/10.1017/CBO9781139195881",
    "Abrial, J.-R., Butler, M., Hallerstede, S., Hoang, T. S., Mehta, F., & Voisin, L. (2010). Rodin: An open toolset "
    "for modelling and reasoning in Event-B. <i>International Journal on Software Tools for Technology Transfer, 12</i>(6), "
    "447–466. https://doi.org/10.1007/s10009-010-0145-y",
    "Event-B and the Rodin Platform. https://wiki.event-b.org/",
    "CLEARSY. Atelier B (provers ML and PP, Rodin plugin). https://www.atelierb.eu/",
    "Object Management Group. (2017). <i>OMG Unified Modeling Language (UML), Version 2.5.1</i>. https://www.omg.org/spec/UML/2.5.1",
    "draw.io (diagrams.net). https://www.drawio.com/",
    "ChronoSeq-B — Sequence Diagram to Event-B converter. " + CONVERTER_REPO,
    "OpenAI. Supervised fine-tuning guide (chat-format training data). "
    "https://developers.openai.com/api/docs/guides/supervised-fine-tuning",
    "Hugging Face. TRL — SFTTrainer. https://huggingface.co/docs/trl/sft_trainer",
]

# related work: similar data, methods or tools — NOT where this dataset came from
RELATED = [
    ("คลังแบบจำลอง Event-B", "DEPLOY Project. DEPLOY Repository of Event-B models and case studies. "
                            "https://web-archive.southampton.ac.uk/deploy-eprints.ecs.soton.ac.uk/"),
    ("กรณีศึกษา Event-B", "Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. "
                         "<i>Formal Aspects of Computing, 20</i>(1), 61–77. https://doi.org/10.1007/s00165-007-0061-4"),
    ("แปลง UML เป็น B", "Snook, C., & Butler, M. (2006). UML-B: Formal modeling and design aided by UML. "
                       "<i>ACM Transactions on Software Engineering and Methodology, 15</i>(1), 92–122. "
                       "https://doi.org/10.1145/1125808.1125811"),
    ("LLM กับการพิสูจน์", "Polu, S., & Sutskever, I. (2020). Generative language modeling for automated theorem proving. "
                         "arXiv:2009.03393."),
    ("ชุดข้อมูลการพิสูจน์ + RAG", "Yang, K., Swope, A. M., Gu, A., Chalamala, R., Song, P., Yu, S., Godil, S., Prenger, R., & "
                                "Anandkumar, A. (2023). LeanDojo: Theorem proving with retrieval-augmented language models. "
                                "<i>NeurIPS 2023 Datasets and Benchmarks Track</i>. arXiv:2306.15626."),
    ("RAG", "Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. "
            "<i>Advances in Neural Information Processing Systems, 33</i>, 9459–9474."),
    ("fine-tune แบบประหยัด", "Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). "
                            "LoRA: Low-rank adaptation of large language models. <i>International Conference on Learning "
                            "Representations (ICLR)</i>. arXiv:2106.09685."),
]

# Published work similar to our models (found by web search 2026-10-27). Similar system or method only —
# NOT a source of the data. keys: kw = regex on the case name, topics = topic codes it also covers.
SIMILAR = [
    # ── method (applies to every model) ──
    {"id": "M1", "kind": "วิธีการ", "about": "แปลง UML Sequence Diagram เป็น Event-B (combined fragments)", "all": True, "checked": True,
     "ref": "Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2015). Extending causal semantics of UML2.0 sequence "
            "diagram for distributed systems. In ICSOFT-EA 2015 (pp. 339–347). SciTePress.",
     "url": "https://doi.org/10.5220/0005517703390347"},
    {"id": "M2", "kind": "วิธีการ", "about": "ความหมายเชิงรูปนัยของ Sequence Diagram ที่มี fragment ซ้อนกัน "
                                           "(ต่อยอดจาก M1 แต่ไม่ได้แปลงเป็น Event-B)", "all": True, "checked": True,
     "ref": "Dhaou, F., Mouakher, I., Attiogbé, J. C., & Bsaies, K. (2017). A causal semantics for UML2.0 sequence diagrams "
            "with nested combined fragments. In ENASE 2017 (pp. 47–56). SciTePress.",
     "url": "https://doi.org/10.5220/0006314100470056"},
    {"id": "M3", "kind": "วิธีการ", "about": "แปลง UML timing diagram เป็น Event-B (กรณีศึกษาลิฟต์)", "all": True,
     "checked": True, "ref": "Joochim, T., Snook, C., Poppleton, M., & Gravell, A. (2010). Timing diagrams requirements "
                            "modeling using Event-B formal methods. In Proceedings of the IASTED International Conference "
                            "on Software Engineering (SE 2010). ACTA Press.",
     "url": "https://doi.org/10.2316/P.2010.677-028", "kw": r"Lift|Elevator"},
    {"id": "M4", "kind": "วิธีการ", "about": "deadline / delay ใน Event-B (ตรงกับ t_time / t_delay)", "all": True,
     "checked": True, "ref": "Sarshogh, M. R., & Butler, M. (2012). Specification and refinement of discrete timing "
                            "properties in Event-B. Electronic Communications of the EASST, 46.",
     "url": "https://doi.org/10.14279/tuj.eceasst.46.701"},
    # ── finance ──
    {"id": "S1", "kind": "ระบบ", "about": "ATM / บัญชีธนาคาร (UML-B ATM)", "topics": ["FIN"],
     "ref": "Event-B Wiki. (n.d.). Event-B examples: UML-B development of an ATM.", "checked": True,
     "url": "https://wiki.event-b.org/index.php/Event-B_Examples",
     "kw": r"ATM|^Bank|Withdraw|Transfer|Payment|Wallet|TopUp|Card|Escrow|Trading|Canteen|Prepay"},
    {"id": "S2", "kind": "ระบบ", "about": "กระเป๋าเงินอิเล็กทรอนิกส์ (Mondex)", "topics": ["FIN"],
     "ref": "Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. "
            "Formal Aspects of Computing, 20(1), 61–77.", "checked": True,
     "url": "https://doi.org/10.1007/s00165-007-0061-4", "kw": r"Payment|Wallet|TopUp|Transfer|Card"},
    {"id": "S3", "kind": "ระบบ", "about": "ระบบบริจาค Gift Aid (Event-B ตามกฎหมาย)", "checked": True,
     "ref": "Williams, D. M., Darwish, S., Schneider, S., & Michael, D. R. (2020). Legislation-driven development of a "
            "Gift Aid system using Event-B. Formal Aspects of Computing, 32(2–3), 251–273. "
            "Models: Swiftaid Rodin Event-B models, Zenodo, https://doi.org/10.5281/zenodo.3715494",
     "url": "https://doi.org/10.1007/s00165-020-00512-5",
     "kw": r"(?<!Blood)Donation|Charity|Tax(?!i)"},
    # ── healthcare ──
    {"id": "S4", "kind": "ระบบ", "about": "เครื่องฟอกไต (ABZ 2016 case study)", "topics": ["HEA"],
     "ref": "Mashkoor, A. (2016). The hemodialysis machine case study. In ABZ 2016 (LNCS 9675, pp. 329–343). Springer.",
     "checked": True, "url": "https://doi.org/10.1007/978-3-319-33600-8_29"},
    {"id": "S5", "kind": "ระบบ", "about": "อุปกรณ์การแพทย์ด้วย Event-B + Rodin", "topics": ["HEA"], "checked": True,
     "ref": "Mashkoor, A., & Biro, M. (2016). Towards the trustworthy development of active medical devices: "
            "A hemodialysis case study. IEEE Embedded Systems Letters, 8(1), 14–17.",
     "url": "https://doi.org/10.1109/LES.2015.2494459",
     "kw": r"Dialysis|Medical|Pill|Glucose|Oxygen|Medication"},
    {"id": "S6", "kind": "ระบบ", "about": "ระบบบริการสุขภาพ: จัดสรรผู้ป่วยให้ผู้ให้บริการ (Event-B)", "topics": ["HEA"],
     "checked": True, "ref": "Petre, L., Sanwal, U., Shah, G., Panchal, C., Tyagi, D., & Petre, I. (2020). A computational "
                            "model for the access to medical service in a basic prototype of a healthcare system. "
                            "Fundamenta Informaticae, 171(1–4), 331–343.",
     "url": "https://doi.org/10.3233/FI-2020-1886",
     "kw": r"Hospital|Patient|Triage|Telemedicine|Telehealth|Clinic|Appointment|Pharmacy|LabSample|Vaccine|Blood|Dental|Veterinary"},
    {"id": "S7", "kind": "ระบบ", "about": "ระบบสั่งการฉุกเฉิน / ดับเพลิง (Event-B workflow)", "checked": True,
     "ref": "Dghaym, D., Butler, M., & Salehi Fathabadi, A. (2014). Evaluation of graphical control flow management "
            "approaches for Event-B modelling. Electronic Communications of the EASST, 66.",
     "url": "https://doi.org/10.14279/tuj.eceasst.66.891",
     "kw": r"Emergency|Ambulance|Disaster|Fire"},
    # ── transportation ──
    {"id": "S8", "kind": "ระบบ", "about": "ไฟจราจร (บทสอนใน Rodin Handbook)", "kw": r"TrafficLight|TrafficSignal|Crossing",
     "checked": True, "ref": "Jastram, M., & Butler, M. (2014). Rodin user's handbook: Covers Rodin v.2.8. CreateSpace. "
                            "Section 2.4 \"The First Machine: A Traffic Light Controller\".",
     "url": "https://stups.hhu-hosting.de/handbook/rodin/release-2014-12-04/html/tut_building_the_model.html"},
    {"id": "S9", "kind": "ระบบ", "about": "ระบบควบคุมรถไฟ (ABZ 2018 Hybrid ERTMS/ETCS Level 3)", "kw": r"Train|Rail|Metro|Tram",
     "ref": "Mammar, A., Frappier, M., Tueno Fotso, S. J., & Laleau, R. (2018). An Event-B model of the hybrid "
            "ERTMS/ETCS level 3 standard. In ABZ 2018 (LNCS 10817, pp. 353–366). Springer.", "checked": True,
     "url": "https://doi.org/10.1007/978-3-319-91271-4_24"},
    {"id": "S10", "kind": "ระบบ", "about": "ควบคุมความเร็วรถยนต์ (ABZ 2020)", "topics": ["TRA"],
     "ref": "Mammar, A., & Frappier, M. (2020). Modeling of a speed control system using Event-B. In ABZ 2020 "
            "(LNCS 12071, pp. 367–381). Springer.", "checked": True,
     "url": "https://doi.org/10.1007/978-3-030-48077-6_29",
     "kw": r"CarRental|Taxi|Ride|Vehicle|Scooter|Parking|Toll|Garage|GolfCart|FleetFuel|Bus(?!iness)|^EV|Shuttle|Bike"},
    {"id": "S11", "kind": "ระบบ", "about": "ระบบฐานล้อเครื่องบิน (ABZ 2014)", "checked": True,
     "ref": "Méry, D., & Singh, N. K. (2014). Modelling an aircraft landing system in Event-B (full report). arXiv:1407.0927.",
     "url": "https://arxiv.org/abs/1407.0927", "kw": r"Airport|Flight|Drone|Aircraft"},
    {"id": "S12", "kind": "ระบบ", "about": "เรือไร้คนขับเข้าเทียบท่า (Event-B + STPA)", "topics": ["LOG"], "checked": True,
     "ref": "Zhang, R., Ma, X., Qiao, W., Zhang, H., & Han, B. (2027). Control logic verification of safety of the intended "
            "functionality for maritime autonomous surface ships based on Event-B: A case of autonomous berthing scenario. "
            "Reliability Engineering & System Safety, 277, 113158.", "url": "https://doi.org/10.1016/j.ress.2026.113158",
     "kw": r"Ship|Port(?!al)|Cargo|Pilot|Seaport|Ferry"},
    # ── logistics ──
    {"id": "S13", "kind": "ระบบ", "about": "คลังสินค้าอัตโนมัติ (stacker crane) ใน Event-B", "topics": ["LOG"], "checked": True,
     "ref": "Hrušecká, D., Adla, R., Krayem, S., & Pivnička, M. (2018). Event-B model for increasing the efficiency of "
            "warehouse management. Polish Journal of Management Studies, 17(2), 63–74.",
     "url": "https://doi.org/10.17512/pjms.2018.17.2.06",
     "kw": r"Warehouse|Picking|Forklift|Storage|Mailroom|Sorting|(?<!Fridge)Inventory"},
    {"id": "S14", "kind": "ระบบ", "about": "การสื่อสารผู้ซื้อ–ผู้ขาย B2B (DEPLOY)", "topics": ["LOG"],
     "ref": "Hoang, T. S. (2009). Event-B model of the Buyer / Seller B2B Communication [Rodin archive]. "
            "DEPLOY Repository, ID 128. University of Southampton.", "checked": True,
     "url": "http://web.archive.org/web/20161018043310/http://deploy-eprints.ecs.soton.ac.uk:80/128/",
     "kw": r"Reorder|Supply|Customs|Purchase|Parcel|Package|Delivery|Courier|Mail"},
    {"id": "S15", "kind": "formal อื่น", "about": "ป้องกันเครนท่าเรือชนกัน (Petri net)",
     "ref": "Kezić, D., Antonić, R., & Račić, N. (2006). Automatic supervisory system synthesis for port cranes collision "
            "prevention by using Petri net. Promet – Traffic & Transportation, 18(3), 143–150.", "checked": True,
     "url": "https://hrcak.srce.hr/102243",
     "kw": r"Crane"},
    # ── smart home / building ──
    {"id": "S16", "kind": "ระบบ", "about": "ระบบ IoT (invariant ของสถาปัตยกรรม)", "topics": ["HOME", "AGR"], "checked": True,
     "ref": "Attiogbé, C., & Rocheteau, J. (2022). Architectural invariants and correctness of IoT-based systems. "
            "In MEDI 2022 short papers and DETECT workshop (CCIS 1751, pp. 75–88). Springer. (preprint arXiv:1912.08912)",
     "url": "https://doi.org/10.1007/978-3-031-23119-3_6", "kw": r"Smart|IoT|Sensor|Monitor|Tracker|Thermostat|Voice|Lighting|Camera|Laundry|Timing|AudioGuide"},
    {"id": "S17", "kind": "ระบบ", "about": "ประตู–กุญแจกับความปลอดภัยเมื่อเกิดไฟไหม้ (ตัวอย่าง Event-B)", "topics": ["HOME"],
     "checked": True, "ref": "Nicoletti, S. M., Peppelman, M., Kolb, C., & Stoelinga, M. (2023). Model-based joint "
                            "analysis of safety and security: Survey and identification of gaps. Computer Science Review, "
                            "50, 100597.",
     "url": "https://doi.org/10.1016/j.cosrev.2023.100597", "kw": r"Door|(?<!Ship)Lock(?!er)|Fire|Alarm|Security|Sprinkler|Gate(?!way)|Intercom"},
    {"id": "S18", "kind": "ระบบ", "about": "กุญแจห้องพักอิเล็กทรอนิกส์ (SCEH) ใน Event-B ตรวจด้วย ProB", "checked": True,
     "ref": "Sayar, I. (2012). D'Event-B vers UML/OCL en passant par UML/EM-OCL [Master's thesis, Université de Sfax]. "
            "arXiv:1212.4959.",
     "url": "https://arxiv.org/abs/1212.4959", "kw": r"Hotel|Keyless|Locker|Badge"},
    # ── industrial / energy ──
    {"id": "S19", "kind": "ระบบ", "about": "โครงข่ายไฟฟ้าอัจฉริยะผ่าน IoT (Event-B dataset)", "topics": ["IND"],
     "checked": True, "ref": "Akkad, A. S. A. (2024). Dataset in support of the thesis 'An information security model "
                            "for an Internet of Things-enabled smart grid in the Saudi energy sector' [Data set]. "
                            "University of Southampton.",
     "url": "https://doi.org/10.5258/SOTON/D3060",
     "kw": r"Grid|Solar|Energy|Battery|Wind|Turbine|PipelineLeak|Charging|SmartMeter|StreetLight"},
    {"id": "S20", "kind": "ระบบ", "about": "สายการผลิตโลหะ (production cell) ใน Event-B", "topics": ["IND"],
     "ref": "Gondal, A., Poppleton, M., Butler, M., & Snook, C. (2010). Feature-oriented modelling using Event-B. "
            "In International Conference on Software Engineering Theory and Practice (SETP-10).", "checked": True,
     "url": "https://eprints.soton.ac.uk/268579", "kw": r"Factory|RobotArm|Assembly|Mining|Crane"},
    # ── retail / food ──
    {"id": "S21", "kind": "ระบบ", "about": "ตู้ขายสินค้า (vending machine) ใน Event-B", "topics": ["RET"], "checked": True,
     "ref": "Stock, S., Leuschel, M., & Mashkoor, A. (2025). Failure divergence refinement for Event-B. In TASE 2025 "
            "(LNCS 15841, pp. 85–103). Springer.",
     "url": "https://doi.org/10.1007/978-3-031-98208-8_6", "kw": r"Vending|Kiosk"},
    {"id": "S22", "kind": "ระบบ", "about": "ตู้ขายสินค้าแบบ refine หลายขั้น + LTL", "checked": True,
     "ref": "Schneider, S., Treharne, H., Wehrheim, H., & Williams, D. M. (2014). Managing LTL properties in Event-B "
            "refinement. In iFM 2014 (LNCS 8739, pp. 221–237). Springer.",
     "url": "https://doi.org/10.1007/978-3-319-10181-1_14", "kw": r"Vending"},
    {"id": "S23", "kind": "ระบบ", "about": "ซื้อของออนไลน์: ตะกร้า → ชำระเงิน → ออกใบเสร็จ → ส่งของ", "topics": ["RET"],
     "checked": True, "ref": "Babin, G. (2014). A formal approach for correct-by-construction system substitution. "
                            "EDCC 2014 Student Forum. arXiv:1404.7513.",
     "url": "https://arxiv.org/abs/1404.7513",
     "kw": r"(?<!Trading)Order|Grocery|Shopping|(?<!Golf)Cart|Marketplace|Checkout|Food|Concession|Truck|Cafe|Restaurant|Coffee|Auction"},
    # ── booking ──
    {"id": "S24", "kind": "ระบบ", "about": "จองห้องพักผ่าน REST service ใน Event-B", "topics": ["BOOK"], "checked": True,
     "ref": "Rauf, I., Vistbakka, I., & Troubitsyna, E. (2018). Formal verification of stateful services with REST APIs "
            "using Event-B. In 2018 IEEE International Conference on Web Services (ICWS) (pp. 131–138). IEEE.",
     "url": "https://doi.org/10.1109/ICWS.2018.00024",
     "kw": r"Hotel|Reservation|Booking|Seat|Desk|Room|Rental|Ticket|Appointment|(?<!Printer)Queue"},
    # ── education / public ──
    {"id": "S25", "kind": "ระบบ", "about": "ระบบลงคะแนนเลือกตั้ง", "topics": ["EDU"], "kw": r"Vot|Ballot",
     "ref": "Gibson, J. P., Kherroubi, S., & Méry, D. (2017). Applying a dependency mechanism for voting protocol "
            "models using Event-B. In FORTE 2017 (LNCS 10321, pp. 124–138). Springer.", "checked": True,
     "url": "https://doi.org/10.1007/978-3-319-60225-7_9"},
    {"id": "S26", "kind": "ระบบ", "about": "ระบบบริหารมหาวิทยาลัย: รับสมัคร สอบ เช็กชื่อ ผลการเรียน", "topics": ["EDU"],
     "checked": True, "ref": "Akhter, N. (2017). Formal modeling and proving of Campus Management System: Event-B "
                            "perspective. Bahria University Journal of Information & Communication Technologies, 10(2).",
     "url": "http://web.archive.org/web/20220809115202/http://ojs.bahria.edu.pk/index.php/bujict/article/view/174",
     "kw": r"Exam|Course|Student|Attendance|Campus|Library|School|Childcare|Proctor|Grading|Quiz|Enroll|Boarding"},
    {"id": "S27", "kind": "ระบบ", "about": "ระบบจัดการรายวิชา: เปิด–ปิดวิชาและลงทะเบียนผู้เรียน (ตัวอย่างในบทนำ Event-B)",
     "topics": ["EDU"], "checked": True,
     "ref": "Hoang, T. S. (2013). An introduction to the Event-B modelling method. In A. Romanovsky & M. Thomas (Eds.), "
            "Industrial deployment of system engineering methods (pp. 211–236). Springer. "
            "https://doi.org/10.1007/978-3-642-33170-1", "url": "https://www.southampton.ac.uk/~tsh2n14/publications/chapters/eventb-dbook13.pdf",
     "kw": r"Course|Enroll"},
    # ── IT ──
    {"id": "S28", "kind": "ระบบ", "about": "โปรโตคอลอุปกรณ์ IoT (LwM2M client)", "topics": ["IT"], "checked": True,
     "ref": "Mouakher, I., Dhaou, F., & Attiogbé, J. C. (2020). Toward a correct implementation of LwM2M client with "
            "Event-B. In ICSOFT 2020 (pp. 172–179). SciTePress.", "url": "https://doi.org/10.5220/0009832601720179", "kw": r"Wifi|Hotspot|Router|Doorbell"},
    {"id": "S29", "kind": "ระบบ", "about": "ควบคุมสิทธิ์การเข้าถึงและทรัพยากรของแอป serverless (Event-B)", "topics": ["IT"],
     "checked": True, "ref": "Yagmahan, M. S. N., Rezazadeh, A., & Butler, M. (2024). An Event-B formal model for access "
                            "control and resource management of serverless apps. In ABZ 2024 (LNCS 14759, pp. 181–190). "
                            "Springer.", "url": "https://doi.org/10.1007/978-3-031-63790-2_11",
     "kw": r"Login|OTP|Auth|Access|Portal|Verification|Parental|Passport|Permit|Check-?In|CheckIn|Visitor"},
    {"id": "S30", "kind": "ระบบ", "about": "ประกอบ web service (BPEL) แล้วตรวจด้วย Event-B", "topics": ["IT"],
     "checked": True, "ref": "Aït-Sadoune, I., & Aït-Ameur, Y. (2008). Verification and validation of web service "
                            "composition using Event B method. In ABZ 2008 (LNCS 5238, pp. 339–340). Springer.",
     "url": "https://doi.org/10.1007/978-3-540-87603-8_28",
     "kw": r"Cloud|DataPipeline|CIPipeline|Gateway|Backup|Streaming|Publishing|Job|API|Server|Insurance|Archive|Document"},
    {"id": "S31", "kind": "ระบบ", "about": "คลังรูปแบบการสื่อสารสำหรับระบบกระจาย (Event-B)", "topics": ["IT"],
     "checked": True, "ref": "Dotti, F. L., & Ribeiro, L. (2012). Modeling communication semantics for distributed "
                            "systems in Event-B. In Anais do XIII Workshop de Testes e Tolerância a Falhas (WTF 2012) "
                            "(pp. 101–114). SBC.", "url": "https://doi.org/10.5753/wtf.2012.23083",
     "kw": r"Chat|Messag|SMS|Email|Notification|Broadcast|Podcast|Alert|Satellite"},
    # ── agriculture ──
    {"id": "S32", "kind": "ระบบ", "about": "ตัวควบคุมปั๊มน้ำ (Event-B, refine 2 ขั้น)", "topics": ["AGR"], "checked": True,
     "ref": "Karmakar, R., Sarkar, B. B., & Chaki, N. (2021). Event-B based formal modeling of a controller: A case study. "
            "In COMSYS 2020 (AISC 1255, pp. 649–658). Springer.", "url": "https://doi.org/10.1007/978-981-15-7834-2_60",
     "kw": r"Irrigation|Pump|Water|Rain|Aquarium|Sprinkler"},
    {"id": "S33", "kind": "formal อื่น", "about": "model checking สำหรับเกษตรแม่นยำ (timed automata)", "topics": ["AGR"],
     "checked": True, "ref": "Saddem, R. (2019). Model-checking pour l'agriculture de précision [Doctoral thesis, "
                            "Université de Montpellier].", "url": "https://theses.hal.science/tel-02476234",
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


SIMILAR_GROUPS = [("วิธีการ (ใช้กับทุกแบบจำลอง)", ["M1", "M2", "M3", "M4"]),
                  ("การเงินและการชำระเงิน", ["S1", "S2", "S3"]),
                  ("สุขภาพและการแพทย์", ["S4", "S5", "S6", "S7"]),
                  ("การเดินทางและยานพาหนะ", ["S8", "S9", "S10", "S11", "S12"]),
                  ("โลจิสติกส์และคลังสินค้า", ["S13", "S14", "S15"]),
                  ("บ้านและอาคารอัจฉริยะ", ["S16", "S17", "S18"]),
                  ("อุตสาหกรรม พลังงาน และโครงสร้างพื้นฐาน", ["S19", "S20"]),
                  ("ค้าปลีก อาหาร และ e-commerce", ["S21", "S22", "S23"]),
                  ("การจอง ที่พัก และกิจกรรม", ["S24"]),
                  ("การศึกษาและบริการภาครัฐ", ["S25", "S26", "S27"]),
                  ("ไอทีและบริการดิจิทัล", ["S28", "S29", "S30", "S31"]),
                  ("เกษตรและสิ่งแวดล้อม", ["S32", "S33"])]


def similar_pdf(out, rows, sim):
    """SIMILAR_WORK.pdf: published work similar to the models, and which model resembles which."""
    by_id = {x["id"]: x for x in SIMILAR}
    assert sorted(i for _, ids in SIMILAR_GROUPS for i in ids) == sorted(by_id)
    used = Counter(i for q in sim for i in q["similar_system"].split("; ") if i)
    checked = sum(bool(x.get("checked")) for x in SIMILAR)
    h = ["<h1>งานที่คล้ายกับแบบจำลองของเรา</h1>",
         f"<div class='sub'>{len(SIMILAR)} รายการอ้างอิง · จับคู่ครบ {len(sim)} แบบจำลอง · ค้นจากเว็บเมื่อ 27 ต.ค. 2026</div>"]
    h.append("<h2>1. เอกสารนี้คืออะไร</h2>")
    h.append("<div class='warn'><b>งานในเอกสารนี้ไม่ใช่แหล่งที่มาของข้อมูล</b><br>แบบจำลองทั้ง 198 ตัวเป็นข้อมูลสังเคราะห์ "
             "ที่สร้างขึ้นเอง (ดู <code>PROVENANCE.pdf</code>) งานด้านล่างเป็นงานตีพิมพ์ที่ทำแบบจำลอง Event-B "
             "(หรือ formal method อื่น) ของระบบประเภทเดียวกัน หรือใช้วิธีการเดียวกัน ใช้อ้างเป็นงานที่เกี่ยวข้อง "
             "(related work) และใช้แสดงว่าระบบในชุดข้อมูลเป็นระบบที่มีผู้ศึกษาด้วยวิธีทางรูปนัยมาก่อน</div>")
    h.append("<table><tr><th style='width:22%'>ประเภท</th><th>ความหมาย</th></tr>"
             "<tr><td>วิธีการ (M1–M4)</td><td>แปลงแผนภาพ UML เป็น Event-B และการจัดการเวลาใน Event-B — ใช้กับทุกแบบจำลอง</td></tr>"
             "<tr><td>ระบบ (S1–S33)</td><td>ระบบประเภทเดียวกับแบบจำลองของเรา จับคู่จากชื่อระบบ เช่น TrafficLightController "
             "↔ ไฟจราจร</td></tr>"
             "<tr><td>formal อื่น</td><td>ใช้ formal method อื่น (Petri net, timed automata) เพราะไม่พบงาน Event-B ที่ตรง</td></tr>"
             f"<tr><td>✓ ตรวจแล้ว</td><td>ตรวจซ้ำแล้ว {checked} จาก {len(SIMILAR)} รายการ เมื่อ 27 ต.ค. 2026 — "
             "เทียบผู้แต่ง ปี ชื่อเรื่อง แหล่งตีพิมพ์ และ DOI กับ Crossref / DOI / arXiv / HAL "
             "และเปิดอ่านบทคัดย่อหรือเนื้อหาว่าตรงกับเรื่องที่ระบุ</td></tr></table>")
    h.append("<p><b>ข้อค้นพบ:</b> ไม่พบงานที่ใช้ LLM ทำนายผล Proof Obligation ของ Event-B ณ วันที่ค้น "
             "— เป็นช่องว่างที่งานนี้เติมได้</p>")

    h.append("<h2>2. รายการอ้างอิงตามหัวข้อ</h2>")
    for name, ids in SIMILAR_GROUPS:
        h.append(f"<div class='grp'><h3>{esc(name)}</h3><table class='refs2'><tr><th style='width:6%'>รหัส</th>"
                 "<th style='width:24%'>คล้ายเรื่อง</th><th>อ้างอิง</th><th style='width:6%'>ตรวจ</th>"
                 "<th style='width:9%'>แบบจำลอง</th></tr>")
        for i in ids:
            x = by_id[i]
            n = len(sim) if x.get("all") else used[i]
            kind = "" if x["kind"] in ("ระบบ", "วิธีการ") else f"<br><span class='ln'>({esc(x['kind'])})</span>"
            link = f"<br><span class='url'>{esc(x['url'])}</span>" if x["url"] else ""
            h.append(f"<tr><td><b>{i}</b></td><td>{esc(x['about'])}{kind}</td><td>{esc(x['ref'])}{link}</td>"
                     f"<td class='c'>{'✓' if x.get('checked') else ''}</td><td class='n'>{n}</td></tr>")
        h.append("</table></div>")

    h.append("<h2 style='break-before:page'>3. แบบจำลองแต่ละตัวคล้ายกับงานไหน</h2>")
    h.append("<p>คอลัมน์ <b>ระบบที่คล้าย</b> จับคู่จากชื่อระบบ · <b>หัวข้อเดียวกัน</b> เป็นงานในหัวข้อเดียวกันเพิ่มเติม · "
             "ทุกแบบจำลองยังคล้ายกับงานด้านวิธีการ M1–M4 · รหัสดูได้จากข้อ 2 · ไฟล์เดียวกันอยู่ใน "
             "<code>csv/similar_work.csv</code></p>")
    for code, (en, th) in TOPIC_NAMES.items():
        g = [(r, q) for r, q in zip(rows, sim) if r["topic"] == en]
        h.append(f"<h3>{esc(th)} ({len(g)})</h3><table class='prov'><tr><th style='width:12%'>ID</th>"
                 "<th style='width:30%'>แบบจำลอง</th><th style='width:8%'>ผล</th><th>ระบบที่คล้าย</th>"
                 "<th style='width:22%'>หัวข้อเดียวกัน</th></tr>")
        for r, q in g:
            sys_ = ", ".join(f"<b>{i}</b> {esc(by_id[i]['about'])}" for i in q["similar_system"].split("; ") if i)
            h.append(f"<tr><td>{r['id']}</td><td>{esc(r['case'])}</td><td class='res-{r['result']}'>{r['result']}</td>"
                     f"<td>{sys_}</td><td>{esc(q['similar_topic'].replace('; ', ', ')) or '–'}</td></tr>")
        h.append("</table>")

    css = (CSS + EXTRA_CSS + "td.res-pass { color: #2e7d5b; font-weight: bold; } td.res-fail { color: #c0392b; font-weight: bold; }"
           "table.prov { font-size: 8.4pt; } table.prov td { padding: 2px 5px; } table.refs2 { font-size: 8.8pt; }"
           ".grp { break-inside: avoid; } .url { color: #2f5fa8; font-size: 8pt; overflow-wrap: anywhere; } td.c { text-align: center; color: #2e7d5b; font-weight: bold; }")
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "similar.html")
        open(page, "w").write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><style>{css}</style></head>"
                              f"<body>{''.join(h)}</body></html>")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={os.path.join(out, 'SIMILAR_WORK.pdf')}", f"file://{page}"],
                       check=True, capture_output=True)


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
           "✓ = ตรวจซ้ำแล้วเมื่อ 27 ต.ค. 2026 (ผู้แต่ง ปี ชื่อเรื่อง แหล่งตีพิมพ์ DOI และเนื้อหาตรงกับที่ระบุ เทียบกับ Crossref / DOI / arXiv / HAL)", "",
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
    extract_trees.main()
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
        for f in ("model.txt", "label.json", "po_details.json", "features.json", "tree.txt", "tree.json"):
            if os.path.exists(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), dst)

    trees_folder(out, rows)

    by_topic(out, rows)
    sim = similar_rows(rows)
    write_csv(os.path.join(out, "csv", "similar_work.csv"), sim, list(sim[0]))
    similar_pdf(out, rows, sim)
    prov = provenance_rows(rows)
    write_csv(os.path.join(out, "csv", "provenance.csv"), prov, list(prov[0]))
    provenance_pdf(out, prov)
    write_sources(out)
    pdf(out, rows, po_rows)
    make_user_flow.main(out)
    return rows


def topic_dir(en):
    k = [v[0] for v in TOPIC_NAMES.values()].index(en) + 1
    return f"{k:02d}_" + en.replace(" & ", "_and_").replace(", ", "_").replace(" ", "_")


def model_dir(r):
    return f"{r['id']}_{r['case'].replace(' ', '').replace('&', 'And')}"


def trees_folder(out, rows):
    """trees/: everything about the event and guard trees, checked against the diagrams."""
    tdir = os.path.join(out, "trees")
    os.makedirs(tdir)
    trees = {r["id"]: json.load(open(os.path.join(DATASET, "models", r["id"], "tree.json"))) for r in rows}
    with open(os.path.join(out, "data", "trees.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            t = trees[r["id"]]
            f.write(json.dumps({"id": r["id"], "case": r["case"], "split": r["split"],
                                **{k: t[k] for k in ("guard_codes", "guard_paths", "event_codes", "event_guards",
                                                     "event_paths")}}, ensure_ascii=False) + "\n")
    for r in rows:
        dst = os.path.join(tdir, "by_topic", topic_dir(r["topic"]), r["result"])
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(os.path.join(DATASET, "models", r["id"], "tree.txt"), os.path.join(dst, model_dir(r) + ".txt"))
    utf8 = lambda name, data, fields: write_csv_bom(os.path.join(tdir, name), data, fields)
    utf8("guard_codes.csv", [{"model_id": r["id"], "case": r["case"], "code": c, "guard": g}
                             for r in rows for c, g in trees[r["id"]]["guard_codes"].items()],
         ["model_id", "case", "code", "guard"])
    utf8("event_codes.csv", [{"model_id": r["id"], "case": r["case"], "code": c, "event": n,
                              "guards": " ".join(trees[r["id"]]["event_guards"][c])}
                             for r in rows for c, n in trees[r["id"]]["event_codes"].items()],
         ["model_id", "case", "code", "event", "guards"])
    check = verify_trees.main(out)
    stats = []
    for r in rows:
        t, c = trees[r["id"]], check["results"][r["id"]]
        stats.append({"model_id": r["id"], "case": r["case"], "topic": r["topic"], "result": r["result"],
                      "events": len(t["event_codes"]), "event_paths": len(t["event_paths"]),
                      "loops": len({re.search(r"↺ (\w+)", p).group(1) for p in t["event_paths"] if "↺" in p}),
                      "guard_codes": len(t["guard_codes"]), "guard_paths": len(t["guard_paths"]),
                      "guard_path_list": " | ".join(t["guard_paths"]),
                      "checked_against": "diagram" if "messages" in c else "rodin .bpo",
                      "check": "pass" if not c["errors"] else "; ".join(c["errors"])})
    utf8("tree_summary.csv", stats, list(stats[0]))
    utf8("check.csv", [{k: s_[k] for k in ("model_id", "case", "checked_against", "check")} for s_ in stats],
         ["model_id", "case", "checked_against", "check"])
    make_tree_report.main(tdir, rows, trees)
    make_tree_report.summary(tdir, rows, trees, stats, check)


def write_csv_bom(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def by_topic(out, rows):
    """by_topic/<NN_Topic>/<pass|fail>/<model_XXX_Case>/ + list.csv per topic (Rodin results)."""
    for code, (en, th) in TOPIC_NAMES.items():
        group = sorted((r for r in rows if r["topic"] == en), key=lambda r: r["id"])
        tdir = os.path.join(out, "by_topic", topic_dir(en))
        for r in group:
            res = "fail" if r["failed"] else "pass"
            dst = os.path.join(tdir, res, model_dir(r))
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
            "│   ├── split.csv             ← โมเดลไหนอยู่ train / val / test",
            "│   └── trees.jsonl           ← event tree + guard tree ของทุกโมเดล (รหัส + เส้นทาง)",
            "├── csv/",
            "│   ├── summary.csv           ← ตัวเลขต่อโมเดล (feature + label)",
            "│   ├── pass_fail_list.csv    ← pass / fail ต่อโมเดล",
            "│   └── model_categories.csv  ← หัวข้อ + จุดผิดใน diagram (ใช้วิเคราะห์ ห้ามเป็น input)",
            "├── models/model_001 … model_198/",
            "│   ├── model.txt             ← Event-B (input)",
            "│   ├── label.json            ← total / discharged / failed",
            "│   ├── po_details.json       ← ผลราย PO",
            "│   ├── features.json",
            "│   └── tree.txt · tree.json  ← event tree + guard tree",
            "├── by_topic/                 ← โมเดลชุดเดียวกัน แยกตามหัวข้อ และผล Rodin",
            "│   ├── 01_Finance_and_Payment/",
            "│   │   ├── list.csv          ← รายชื่อ + ผล ของหัวข้อนี้",
            "│   │   ├── pass/model_003_ATMWithdrawal/ …",
            "│   │   └── fail/model_004_BankTransfer/ …",
            "│   └── … (11 หัวข้อ)",
            "├── FLOW.pdf · FLOW.png       ← แผนภาพขั้นตอนการดำเนินงาน",
            "├── PROVENANCE.pdf            ← ที่มาของแบบจำลองแต่ละตัว (csv/provenance.csv)",
            "├── SIMILAR_WORK.pdf          ← งานตีพิมพ์ที่คล้ายกับแบบจำลอง (csv/similar_work.csv)",
            "├── trees/                    ← event tree + guard tree ของทุกโมเดล",
            "│   ├── SUMMARY.pdf           ← สรุปวิธีทำและผลตรวจความถูกต้อง",
            "│   ├── TREES.pdf             ← รหัสและ tree ของทุกโมเดล",
            "│   ├── guard_codes.csv · event_codes.csv · tree_summary.csv · check.csv",
            "│   └── by_topic/<หัวข้อ>/<pass|fail>/<model>.txt",
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
             "✓ = ตรวจซ้ำแล้วเมื่อ 27 ต.ค. 2026 (ผู้แต่ง ปี ชื่อเรื่อง แหล่งตีพิมพ์ DOI และเนื้อหาตรงกับที่ระบุ เทียบกับ Crossref / DOI / arXiv / HAL)</p><table style='font-size:8.4pt'><tr><th>รหัส</th><th>คล้ายเรื่อง</th>"
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
