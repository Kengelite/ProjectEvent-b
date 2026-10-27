# แหล่งที่มา (Sources)

## ที่มาของข้อมูล

| รายการ | รายละเอียด |
|---|---|
| แผนภาพต้นทาง | ข้อมูลสังเคราะห์ ไม่ได้นำมาจากชุดข้อมูลภายนอก — Sequence Diagram 197 แบบจำลอง สร้างด้วยโปรแกรมสร้างแผนภาพอัตโนมัติ (EventB_PO_Dataset/tools/generators/) เป็นไฟล์รูปแบบ draw.io ชื่อระบบเป็นสถานการณ์สมมติ ครอบคลุม 11 หัวข้อ: 47 แบบจำลองแรกกำหนดสถานการณ์ทีละแบบ และ 150 แบบจำลองสุ่มโครงสร้างด้วย seed คงที่ (สร้างซ้ำได้) ทุกแผนภาพตรวจด้วย parser ของ ChronoSeq-B · model_001 Payment & Notification เป็นกรณีทดสอบจากงานเดิมของผู้วิจัย |
| การแปลง | ChronoSeq-B (https://github.com/Kengelite/ProjectEvent-b) commit 20fad33 (2026-08-30) — แปลงแผนภาพเป็น Event-B และ Rodin project โดยไม่แก้ไขผลลัพธ์ภายหลัง |
| การพิสูจน์ | Rodin Platform บน Windows (Eclipse platform 4.23) ร่วมกับ Atelier B provers plugin — ใน proof file พบ reasoner com.clearsy.atelierb.provers.core.externalML และ externalPP |
| ช่วงเวลาพิสูจน์ | รอบแรก 1–2 ตุลาคม 2026 (26 แบบจำลองที่ไม่เปลี่ยน ใช้ผลรอบนี้) · รอบหลัก 26 ตุลาคม 2026 |
| การอ่านผล | อ่านสถานะจากไฟล์ .bps: PO ผ่านเมื่อ confidence = 1000 และ proof ไม่อยู่ในสถานะ broken |
| เครื่องมือประมวลผล | Python 3.14.0 · script ใน EventB_PO_Dataset/tools/ (https://github.com/Kengelite/ProjectEvent-b) |

ที่มาของแบบจำลองทีละตัว (วิธีสร้าง, seed, วันที่, จุดผิด, วันที่พิสูจน์): `csv/provenance.csv` และ `PROVENANCE.pdf`

## เอกสารอ้างอิง

1. Abrial, J.-R. (2010). *Modeling in Event-B: System and Software Engineering*. Cambridge University Press.
2. Abrial, J.-R., Butler, M., Hallerstede, S., Hoang, T. S., Mehta, F., & Voisin, L. (2010). Rodin: An open toolset for modelling and reasoning in Event-B. *International Journal on Software Tools for Technology Transfer, 12*(6), 447–466. https://doi.org/10.1007/s10009-010-0145-y
3. Event-B and the Rodin Platform. https://www.event-b.org/
4. CLEARSY. Atelier B (provers ML and PP, Rodin plugin). https://www.atelierb.eu/
5. Object Management Group. (2017). *OMG Unified Modeling Language (UML), Version 2.5.1*. https://www.omg.org/spec/UML/2.5.1
6. draw.io (diagrams.net). https://www.drawio.com/
7. ChronoSeq-B — Sequence Diagram to Event-B converter. https://github.com/Kengelite/ProjectEvent-b
8. OpenAI. Fine-tuning guide (chat-format training data). https://platform.openai.com/docs/guides/fine-tuning
9. Hugging Face. TRL — SFTTrainer. https://huggingface.co/docs/trl/sft_trainer

## งานที่เกี่ยวข้อง

งานด้านล่างใกล้เคียงกับงานนี้ด้านข้อมูล วิธีการ หรือเครื่องมือ ใช้เป็นงานที่เกี่ยวข้องเท่านั้น **ไม่ใช่แหล่งที่มาของข้อมูล** — ข้อมูลในชุดนี้สร้างขึ้นเองทั้งหมด (ดูหัวข้อที่มาของข้อมูล)

- **คลังแบบจำลอง Event-B** — DEPLOY Project. DEPLOY Repository of Event-B models and case studies. http://deploy-eprints.ecs.soton.ac.uk/
- **กรณีศึกษา Event-B** — Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. *Formal Aspects of Computing, 20*(1), 61–77.
- **แปลง UML เป็น B** — Snook, C., & Butler, M. (2006). UML-B: Formal modeling and design aided by UML. *ACM Transactions on Software Engineering and Methodology, 15*(1), 92–122.
- **LLM กับการพิสูจน์** — Polu, S., & Sutskever, I. (2020). Generative language modeling for automated theorem proving. arXiv:2009.03393.
- **ชุดข้อมูลการพิสูจน์ + RAG** — Yang, K., Swope, A. M., Gu, A., Chalamala, R., Song, P., Yu, S., Godil, S., Prenger, R., & Anandkumar, A. (2023). LeanDojo: Theorem proving with retrieval-augmented language models. *NeurIPS 2023 Datasets and Benchmarks Track*. arXiv:2306.15626.
- **RAG** — Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *Advances in Neural Information Processing Systems, 33*.
- **fine-tune แบบประหยัด** — Hu, E. J., et al. (2022). LoRA: Low-rank adaptation of large language models. *International Conference on Learning Representations (ICLR)*.

## งานที่คล้ายกับแบบจำลองของเรา

ค้นจากเว็บเมื่อ 27 ต.ค. 2026 — คล้ายด้านระบบหรือวิธีการ **ไม่ใช่แหล่งที่มาของข้อมูล** แบบจำลองแต่ละตัวจับคู่กับงานเหล่านี้ใน `csv/similar_work.csv` (ตามชื่อระบบก่อน ถ้าไม่พบใช้ตามหัวข้อ) ✓ = เปิดตรวจชื่อเรื่องและผู้แต่งแล้ว รายการอื่นมาจากผลค้นหา ควรเปิดตรวจก่อนอ้างในเล่ม

| รหัส | ด้าน | คล้ายเรื่อง | อ้างอิง | ตรวจ |
|---|---|---|---|---|
| M1 | วิธีการ | แปลง UML Sequence Diagram เป็น Event-B (combined fragments) | Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2015). Extending causal semantics of UML2.0 sequence diagram for distributed systems. ICSOFT-EA 2015, 339–347. https://www.scitepress.org/Papers/2015/55177/ | ✓ |
| M2 | วิธีการ | Sequence Diagram ที่มี fragment ซ้อนกัน | Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2017). A causal semantics for UML2.0 sequence diagrams with nested combined fragments. ENASE 2017. https://www.scitepress.org/Papers/2017/63141 | ✓ |
| M3 | วิธีการ | แปลง UML timing diagram เป็น Event-B (กรณีศึกษาลิฟต์) | Joochim, T., Gravell, A., & Poppleton, M. Translating UML 2.0 timing diagrams into Event-B and UML-B. https://eprints.soton.ac.uk/268489/ |  |
| M4 | วิธีการ | deadline / delay ใน Event-B (ตรงกับ t_time / t_delay) | Sarshogh, M. R., & Butler, M. (2011). Specification and refinement of discrete timing properties in Event-B. ECEASST, 46. https://journal.ub.tu-berlin.de/eceasst/article/view/701 |  |
| S1 | ระบบ | ATM / บัญชีธนาคาร (UML-B ATM) | Event-B Wiki. Event-B Examples (ATM development). https://wiki.event-b.org/index.php/Event-B_Examples |  |
| S2 | ระบบ | กระเป๋าเงินอิเล็กทรอนิกส์ (Mondex) | Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. Formal Aspects of Computing, 20(1), 61–77.  |  |
| S3 | ระบบ | ระบบบริจาค Gift Aid (Event-B ตามกฎหมาย) | Williams, D. M., Darwish, S., Schneider, S., & Michael, D. R. (2020). Swiftaid Rodin Event-B models [dataset]. Zenodo. https://doi.org/10.5281/zenodo.3715494 https://zenodo.org/records/3715494 | ✓ |
| S4 | ระบบ | เครื่องฟอกไต (ABZ 2016 case study) | Mashkoor, A. (2016). The hemodialysis machine case study. ABZ 2016. https://irit.fr/ABZ-CS/html_files/files/2016/PDF/Case_Study_The%20Hemodialysis%20Machine_2016.pdf |  |
| S5 | ระบบ | อุปกรณ์การแพทย์ด้วย Event-B + Rodin | Mashkoor, A., & Biro, M. (2017). Towards the trustworthy development of active medical devices: A hemodialysis case study. arXiv:1706.06369. https://arxiv.org/abs/1706.06369 | ✓ |
| S6 | ระบบ | ระบบบริการสุขภาพ: จัดสรรผู้ป่วยให้ผู้ให้บริการ (Event-B) | Petre, L., et al. (2020). Event-B model of a healthcare system as distributed medical providers. Fundamenta Informaticae. https://content.iospress.com/articles/fundamenta-informaticae/fi1886 |  |
| S7 | ระบบ | ระบบสั่งการฉุกเฉิน / ดับเพลิง (Event-B workflow) | Dghaym, D., Butler, M., & Salehi Fathabadi, A. (2014). Evaluation of graphical control flow management approaches for Event-B modelling. ECEASST, 66. https://eceasst.org/index.php/eceasst/article/view/2094 | ✓ |
| S8 | ระบบ | ไฟจราจร (Rodin Handbook) | Jastram, M., & Butler, M. Rodin User's Handbook — traffic light tutorial. https://www3.hhu.de/stups/handbook/rodin/release-2014-12-04/html/tut_building_the_model.html |  |
| S9 | ระบบ | ระบบควบคุมรถไฟ (ABZ 2018 Hybrid ERTMS/ETCS Level 3) | Mammar, A., Frappier, M., Tueno Fotso, S. J., & Laleau, R. (2018). An Event-B model of the hybrid ERTMS/ETCS level 3 standard. ABZ 2018. https://hal.archives-ouvertes.fr/hal-01797810 |  |
| S10 | ระบบ | ควบคุมความเร็วรถยนต์ (ABZ 2020) | Mammar, A., & Frappier, M. (2020). Modeling of a speed control system using Event-B. ABZ 2020, 367–381. https://doi.org/10.1007/978-3-030-48077-6_29 |  |
| S11 | ระบบ | ระบบฐานล้อเครื่องบิน (ABZ 2014) | Méry, D., & Singh, N. K. (2014). Modelling an aircraft landing system in Event-B (full report). arXiv:1407.0927. https://arxiv.org/abs/1407.0927 | ✓ |
| S12 | ระบบ | เรือไร้คนขับเข้าเทียบท่า (Event-B + STPA) | Control logic verification of safety of the intended functionality for maritime autonomous surface ships based on Event-B: A case of autonomous berthing scenario. https://trid.trb.org/View/2728291 |  |
| S13 | ระบบ | คลังสินค้าอัตโนมัติ (stacker crane) ใน Event-B | Event-B model of an automated storage and retrieval warehouse with stacker cranes. Tomas Bata University repository. https://m.publikace.k.utb.cz/handle/10563/1008104 |  |
| S14 | ระบบ | การสื่อสารผู้ซื้อ–ผู้ขาย B2B (DEPLOY) | Hoang, T. S. Event-B model of buyer/seller (order/supply chain) communication. DEPLOY repository, eprint 128. https://web-archive.southampton.ac.uk/deploy-eprints.ecs.soton.ac.uk/128/index.html |  |
| S15 | formal อื่น | ป้องกันเครนท่าเรือชนกัน (Petri net) | Kezić, D., Antonić, R., & Račić, N. (2006). Port cranes collision avoidance supervisor (Petri nets). Promet – Traffic & Transportation. https://doaj.org/article/eca9ff9373974108bfd3dc156107cf13 |  |
| S16 | ระบบ | ระบบ IoT (invariant ของสถาปัตยกรรม) | Attiogbé, C., & Rocheteau, J. (2019). Architectural invariants and correctness of IoT-based systems. arXiv:1912.08912. https://arxiv.org/abs/1912.08912 | ✓ |
| S17 | ระบบ | ประตู–กุญแจกับความปลอดภัยเมื่อเกิดไฟไหม้ (ตัวอย่าง Event-B) | Nicoletti, S. M., Peppelman, M., Kolb, C., & Stoelinga, M. (2021). Model-based joint analysis of safety and security: Survey and identification of gaps. arXiv:2106.06272. https://arxiv.org/abs/2106.06272 | ✓ |
| S18 | ระบบ | กุญแจห้องพักอิเล็กทรอนิกส์ (กรณีศึกษาของ Abrial) | Electronic hotel key system (SCEH) specified in Event-B and animated with ProB. arXiv:1212.4959. https://arxiv.org/abs/1212.4959 |  |
| S19 | ระบบ | โครงข่ายไฟฟ้าอัจฉริยะผ่าน IoT (Event-B dataset) | University of Southampton. Event-B model of an IoT-enabled smart grid [dataset]. https://eprints.soton.ac.uk/498327 |  |
| S20 | ระบบ | สายการผลิตโลหะ (production cell) ใน Event-B | Gondal, A., Poppleton, M., Butler, M., & Snook, C. (2010). Feature-oriented modelling using Event-B. SETP-10. https://eprints.soton.ac.uk/268579 |  |
| S21 | ระบบ | ตู้ขายสินค้า (vending machine) ใน Event-B | Stock, S., Leuschel, M., & Mashkoor, A. (2025). Failure divergence refinement for Event-B. arXiv:2505.19069. https://arxiv.org/abs/2505.19069 | ✓ |
| S22 | ระบบ | ตู้ขายสินค้าแบบ refine หลายขั้น + LTL | Schneider, S., Treharne, H., Wehrheim, H., & Williams, D. (2014). Managing LTL properties in Event-B refinement. arXiv:1406.6622. https://arxiv.org/abs/1406.6622 | ✓ |
| S23 | ระบบ | ซื้อของออนไลน์: ตะกร้า → ชำระเงิน → ส่งของ | Babin, G., et al. (2014). A formal approach for correct-by-construction system substitution. arXiv:1404.7513. https://arxiv.org/abs/1404.7513 | ✓ |
| S24 | ระบบ | จองห้องพักผ่าน REST service ใน Event-B | Rauf, I., Vistbakka, I., & Troubitsyna, E. (2018). Formal verification of stateful services with REST APIs using Event-B. IEEE ICWS 2018, 131–138. https://research.abo.fi/en/publications/formal-verification-of-stateful-services-with-rest-apis-using-eve/ | ✓ |
| S25 | ระบบ | ระบบลงคะแนนเลือกตั้ง | Gibson, J. P., Kherroubi, S., & Méry, D. (2017). Applying a dependency mechanism for voting protocol models using Event-B. FORTE 2017. https://hal.archives-ouvertes.fr/hal-01658423 |  |
| S26 | ระบบ | ระบบบริหารมหาวิทยาลัย: รับสมัคร สอบ เช็กชื่อ ผลการเรียน | Formal modeling and proving of Campus Management System: Event-B perspective. Bahria University Journal of ICT. https://ojs.bahria.edu.pk/index.php/bujict/article/view/174 |  |
| S27 | ระบบ | ลงทะเบียนวิชา (ตัวอย่างในบทนำ Event-B) | Hoang, T. S. (2013). An introduction to the Event-B modelling method. In Industrial Deployment of System Engineering Methods. Springer. https://www.southampton.ac.uk/~tsh2n14/publications/chapters/eventb-dbook13.pdf |  |
| S28 | ระบบ | โปรโตคอลอุปกรณ์ IoT (LwM2M client) | Mouakher, I., Dhaou, F., & Attiogbé, J. C. (2020). Toward a correct implementation of LwM2M client with Event-B. ICSOFT 2020. https://www.scitepress.org/Papers/2020/98326/ | ✓ |
| S29 | ระบบ | ยืนยันตัวตน / สิทธิ์การเข้าถึง (authentication pattern) | Yagmahan, Rezazadeh, & Butler (2024). Authentication pattern and serverless access control in Event-B (ABZ 2024) [dataset]. https://eprints.soton.ac.uk/489451/ |  |
| S30 | ระบบ | ประกอบ web service (BPEL) แล้วตรวจด้วย Event-B | Verification and validation of web service composition using Event B method. HAL hal-00634407. https://hal.archives-ouvertes.fr/hal-00634407 |  |
| S31 | ระบบ | คลังรูปแบบการสื่อสารสำหรับระบบกระจาย (Event-B) | Modeling communication semantics for distributed systems in Event-B. WTF (SBC). https://sol.sbc.org.br/index.php/wtf/article/view/23083 |  |
| S32 | ระบบ | ตัวควบคุมปั๊มน้ำ (Event-B, refine 2 ขั้น) | Karmakar, R., Sarkar, B. B., & Chaki, N. (2020). Event-B based formal modeling of a controller: A case study. EasyChair Preprint. https://easychair.org/publications/preprint/NGXM | ✓ |
| S33 | formal อื่น | model checking สำหรับเกษตรแม่นยำ (timed automata) | Model-checking pour l'agriculture de précision [doctoral thesis]. Université de Montpellier. https://esploro.umontpellier.fr/esploro/outputs/doctoral/Model-checking-pour-lagriculture-de-précision/9939414009311 |  |

ไม่พบงานที่ใช้ LLM ทำนายผล Proof Obligation ของ Event-B (ณ วันที่ค้น) — จุดนี้เป็นช่องว่างที่งานนี้เติมได้
