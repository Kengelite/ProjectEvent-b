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

1. Abrial, J.-R. (2010). *Modeling in Event-B: System and Software Engineering*. Cambridge University Press. https://doi.org/10.1017/CBO9781139195881
2. Abrial, J.-R., Butler, M., Hallerstede, S., Hoang, T. S., Mehta, F., & Voisin, L. (2010). Rodin: An open toolset for modelling and reasoning in Event-B. *International Journal on Software Tools for Technology Transfer, 12*(6), 447–466. https://doi.org/10.1007/s10009-010-0145-y
3. Event-B and the Rodin Platform. https://wiki.event-b.org/
4. CLEARSY. Atelier B (provers ML and PP, Rodin plugin). https://www.atelierb.eu/
5. Object Management Group. (2017). *OMG Unified Modeling Language (UML), Version 2.5.1*. https://www.omg.org/spec/UML/2.5.1
6. draw.io (diagrams.net). https://www.drawio.com/
7. ChronoSeq-B — Sequence Diagram to Event-B converter. https://github.com/Kengelite/ProjectEvent-b
8. OpenAI. Supervised fine-tuning guide (chat-format training data). https://developers.openai.com/api/docs/guides/supervised-fine-tuning
9. Hugging Face. TRL — SFTTrainer. https://huggingface.co/docs/trl/sft_trainer

## งานที่เกี่ยวข้อง

งานด้านล่างใกล้เคียงกับงานนี้ด้านข้อมูล วิธีการ หรือเครื่องมือ ใช้เป็นงานที่เกี่ยวข้องเท่านั้น **ไม่ใช่แหล่งที่มาของข้อมูล** — ข้อมูลในชุดนี้สร้างขึ้นเองทั้งหมด (ดูหัวข้อที่มาของข้อมูล)

- **คลังแบบจำลอง Event-B** — DEPLOY Project. DEPLOY Repository of Event-B models and case studies. https://web-archive.southampton.ac.uk/deploy-eprints.ecs.soton.ac.uk/
- **กรณีศึกษา Event-B** — Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. *Formal Aspects of Computing, 20*(1), 61–77. https://doi.org/10.1007/s00165-007-0061-4
- **แปลง UML เป็น B** — Snook, C., & Butler, M. (2006). UML-B: Formal modeling and design aided by UML. *ACM Transactions on Software Engineering and Methodology, 15*(1), 92–122. https://doi.org/10.1145/1125808.1125811
- **LLM กับการพิสูจน์** — Polu, S., & Sutskever, I. (2020). Generative language modeling for automated theorem proving. arXiv:2009.03393.
- **ชุดข้อมูลการพิสูจน์ + RAG** — Yang, K., Swope, A. M., Gu, A., Chalamala, R., Song, P., Yu, S., Godil, S., Prenger, R., & Anandkumar, A. (2023). LeanDojo: Theorem proving with retrieval-augmented language models. *NeurIPS 2023 Datasets and Benchmarks Track*. arXiv:2306.15626.
- **RAG** — Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *Advances in Neural Information Processing Systems, 33*, 9459–9474.
- **fine-tune แบบประหยัด** — Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). LoRA: Low-rank adaptation of large language models. *International Conference on Learning Representations (ICLR)*. arXiv:2106.09685.

## งานที่คล้ายกับแบบจำลองของเรา

ค้นจากเว็บเมื่อ 27 ต.ค. 2026 — คล้ายด้านระบบหรือวิธีการ **ไม่ใช่แหล่งที่มาของข้อมูล** แบบจำลองแต่ละตัวจับคู่กับงานเหล่านี้ใน `csv/similar_work.csv` (ตามชื่อระบบก่อน ถ้าไม่พบใช้ตามหัวข้อ) ✓ = ตรวจซ้ำแล้วเมื่อ 27 ต.ค. 2026 (ผู้แต่ง ปี ชื่อเรื่อง แหล่งตีพิมพ์ DOI และเนื้อหาตรงกับที่ระบุ เทียบกับ Crossref / DOI / arXiv / HAL)

| รหัส | ด้าน | คล้ายเรื่อง | อ้างอิง | ตรวจ |
|---|---|---|---|---|
| M1 | วิธีการ | แปลง UML Sequence Diagram เป็น Event-B (combined fragments) | Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2015). Extending causal semantics of UML2.0 sequence diagram for distributed systems. In ICSOFT-EA 2015 (pp. 339–347). SciTePress. https://doi.org/10.5220/0005517703390347 | ✓ |
| M2 | วิธีการ | ความหมายเชิงรูปนัยของ Sequence Diagram ที่มี fragment ซ้อนกัน (ต่อยอดจาก M1 แต่ไม่ได้แปลงเป็น Event-B) | Dhaou, F., Mouakher, I., Attiogbé, J. C., & Bsaies, K. (2017). A causal semantics for UML2.0 sequence diagrams with nested combined fragments. In ENASE 2017 (pp. 47–56). SciTePress. https://doi.org/10.5220/0006314100470056 | ✓ |
| M3 | วิธีการ | แปลง UML timing diagram เป็น Event-B (กรณีศึกษาลิฟต์) | Joochim, T., Snook, C., Poppleton, M., & Gravell, A. (2010). Timing diagrams requirements modeling using Event-B formal methods. In Proceedings of the IASTED International Conference on Software Engineering (SE 2010). ACTA Press. https://doi.org/10.2316/P.2010.677-028 | ✓ |
| M4 | วิธีการ | deadline / delay ใน Event-B (ตรงกับ t_time / t_delay) | Sarshogh, M. R., & Butler, M. (2012). Specification and refinement of discrete timing properties in Event-B. Electronic Communications of the EASST, 46. https://doi.org/10.14279/tuj.eceasst.46.701 | ✓ |
| S1 | ระบบ | ATM / บัญชีธนาคาร (UML-B ATM) | Event-B Wiki. (n.d.). Event-B examples: UML-B development of an ATM. https://wiki.event-b.org/index.php/Event-B_Examples | ✓ |
| S2 | ระบบ | กระเป๋าเงินอิเล็กทรอนิกส์ (Mondex) | Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. Formal Aspects of Computing, 20(1), 61–77. https://doi.org/10.1007/s00165-007-0061-4 | ✓ |
| S3 | ระบบ | ระบบบริจาค Gift Aid (Event-B ตามกฎหมาย) | Williams, D. M., Darwish, S., Schneider, S., & Michael, D. R. (2020). Legislation-driven development of a Gift Aid system using Event-B. Formal Aspects of Computing, 32(2–3), 251–273. Models: Swiftaid Rodin Event-B models, Zenodo, https://doi.org/10.5281/zenodo.3715494 https://doi.org/10.1007/s00165-020-00512-5 | ✓ |
| S4 | ระบบ | เครื่องฟอกไต (ABZ 2016 case study) | Mashkoor, A. (2016). The hemodialysis machine case study. In ABZ 2016 (LNCS 9675, pp. 329–343). Springer. https://doi.org/10.1007/978-3-319-33600-8_29 | ✓ |
| S5 | ระบบ | อุปกรณ์การแพทย์ด้วย Event-B + Rodin | Mashkoor, A., & Biro, M. (2016). Towards the trustworthy development of active medical devices: A hemodialysis case study. IEEE Embedded Systems Letters, 8(1), 14–17. https://doi.org/10.1109/LES.2015.2494459 | ✓ |
| S6 | ระบบ | ระบบบริการสุขภาพ: จัดสรรผู้ป่วยให้ผู้ให้บริการ (Event-B) | Petre, L., Sanwal, U., Shah, G., Panchal, C., Tyagi, D., & Petre, I. (2020). A computational model for the access to medical service in a basic prototype of a healthcare system. Fundamenta Informaticae, 171(1–4), 331–343. https://doi.org/10.3233/FI-2020-1886 | ✓ |
| S7 | ระบบ | ระบบสั่งการฉุกเฉิน / ดับเพลิง (Event-B workflow) | Dghaym, D., Butler, M., & Salehi Fathabadi, A. (2014). Evaluation of graphical control flow management approaches for Event-B modelling. Electronic Communications of the EASST, 66. https://doi.org/10.14279/tuj.eceasst.66.891 | ✓ |
| S8 | ระบบ | ไฟจราจร (บทสอนใน Rodin Handbook) | Jastram, M., & Butler, M. (2014). Rodin user's handbook: Covers Rodin v.2.8. CreateSpace. Section 2.4 "The First Machine: A Traffic Light Controller". https://stups.hhu-hosting.de/handbook/rodin/release-2014-12-04/html/tut_building_the_model.html | ✓ |
| S9 | ระบบ | ระบบควบคุมรถไฟ (ABZ 2018 Hybrid ERTMS/ETCS Level 3) | Mammar, A., Frappier, M., Tueno Fotso, S. J., & Laleau, R. (2018). An Event-B model of the hybrid ERTMS/ETCS level 3 standard. In ABZ 2018 (LNCS 10817, pp. 353–366). Springer. https://doi.org/10.1007/978-3-319-91271-4_24 | ✓ |
| S10 | ระบบ | ควบคุมความเร็วรถยนต์ (ABZ 2020) | Mammar, A., & Frappier, M. (2020). Modeling of a speed control system using Event-B. In ABZ 2020 (LNCS 12071, pp. 367–381). Springer. https://doi.org/10.1007/978-3-030-48077-6_29 | ✓ |
| S11 | ระบบ | ระบบฐานล้อเครื่องบิน (ABZ 2014) | Méry, D., & Singh, N. K. (2014). Modelling an aircraft landing system in Event-B (full report). arXiv:1407.0927. https://arxiv.org/abs/1407.0927 | ✓ |
| S12 | ระบบ | เรือไร้คนขับเข้าเทียบท่า (Event-B + STPA) | Zhang, R., Ma, X., Qiao, W., Zhang, H., & Han, B. (2027). Control logic verification of safety of the intended functionality for maritime autonomous surface ships based on Event-B: A case of autonomous berthing scenario. Reliability Engineering & System Safety, 277, 113158. https://doi.org/10.1016/j.ress.2026.113158 | ✓ |
| S13 | ระบบ | คลังสินค้าอัตโนมัติ (stacker crane) ใน Event-B | Hrušecká, D., Adla, R., Krayem, S., & Pivnička, M. (2018). Event-B model for increasing the efficiency of warehouse management. Polish Journal of Management Studies, 17(2), 63–74. https://doi.org/10.17512/pjms.2018.17.2.06 | ✓ |
| S14 | ระบบ | การสื่อสารผู้ซื้อ–ผู้ขาย B2B (DEPLOY) | Hoang, T. S. (2009). Event-B model of the Buyer / Seller B2B Communication [Rodin archive]. DEPLOY Repository, ID 128. University of Southampton. http://web.archive.org/web/20161018043310/http://deploy-eprints.ecs.soton.ac.uk:80/128/ | ✓ |
| S15 | formal อื่น | ป้องกันเครนท่าเรือชนกัน (Petri net) | Kezić, D., Antonić, R., & Račić, N. (2006). Automatic supervisory system synthesis for port cranes collision prevention by using Petri net. Promet – Traffic & Transportation, 18(3), 143–150. https://hrcak.srce.hr/102243 | ✓ |
| S16 | ระบบ | ระบบ IoT (invariant ของสถาปัตยกรรม) | Attiogbé, C., & Rocheteau, J. (2022). Architectural invariants and correctness of IoT-based systems. In MEDI 2022 short papers and DETECT workshop (CCIS 1751, pp. 75–88). Springer. (preprint arXiv:1912.08912) https://doi.org/10.1007/978-3-031-23119-3_6 | ✓ |
| S17 | ระบบ | ประตู–กุญแจกับความปลอดภัยเมื่อเกิดไฟไหม้ (ตัวอย่าง Event-B) | Nicoletti, S. M., Peppelman, M., Kolb, C., & Stoelinga, M. (2023). Model-based joint analysis of safety and security: Survey and identification of gaps. Computer Science Review, 50, 100597. https://doi.org/10.1016/j.cosrev.2023.100597 | ✓ |
| S18 | ระบบ | กุญแจห้องพักอิเล็กทรอนิกส์ (SCEH) ใน Event-B ตรวจด้วย ProB | Sayar, I. (2012). D'Event-B vers UML/OCL en passant par UML/EM-OCL [Master's thesis, Université de Sfax]. arXiv:1212.4959. https://arxiv.org/abs/1212.4959 | ✓ |
| S19 | ระบบ | โครงข่ายไฟฟ้าอัจฉริยะผ่าน IoT (Event-B dataset) | Akkad, A. S. A. (2024). Dataset in support of the thesis 'An information security model for an Internet of Things-enabled smart grid in the Saudi energy sector' [Data set]. University of Southampton. https://doi.org/10.5258/SOTON/D3060 | ✓ |
| S20 | ระบบ | สายการผลิตโลหะ (production cell) ใน Event-B | Gondal, A., Poppleton, M., Butler, M., & Snook, C. (2010). Feature-oriented modelling using Event-B. In International Conference on Software Engineering Theory and Practice (SETP-10). https://eprints.soton.ac.uk/268579 | ✓ |
| S21 | ระบบ | ตู้ขายสินค้า (vending machine) ใน Event-B | Stock, S., Leuschel, M., & Mashkoor, A. (2025). Failure divergence refinement for Event-B. In TASE 2025 (LNCS 15841, pp. 85–103). Springer. https://doi.org/10.1007/978-3-031-98208-8_6 | ✓ |
| S22 | ระบบ | ตู้ขายสินค้าแบบ refine หลายขั้น + LTL | Schneider, S., Treharne, H., Wehrheim, H., & Williams, D. M. (2014). Managing LTL properties in Event-B refinement. In iFM 2014 (LNCS 8739, pp. 221–237). Springer. https://doi.org/10.1007/978-3-319-10181-1_14 | ✓ |
| S23 | ระบบ | ซื้อของออนไลน์: ตะกร้า → ชำระเงิน → ออกใบเสร็จ → ส่งของ | Babin, G. (2014). A formal approach for correct-by-construction system substitution. EDCC 2014 Student Forum. arXiv:1404.7513. https://arxiv.org/abs/1404.7513 | ✓ |
| S24 | ระบบ | จองห้องพักผ่าน REST service ใน Event-B | Rauf, I., Vistbakka, I., & Troubitsyna, E. (2018). Formal verification of stateful services with REST APIs using Event-B. In 2018 IEEE International Conference on Web Services (ICWS) (pp. 131–138). IEEE. https://doi.org/10.1109/ICWS.2018.00024 | ✓ |
| S25 | ระบบ | ระบบลงคะแนนเลือกตั้ง | Gibson, J. P., Kherroubi, S., & Méry, D. (2017). Applying a dependency mechanism for voting protocol models using Event-B. In FORTE 2017 (LNCS 10321, pp. 124–138). Springer. https://doi.org/10.1007/978-3-319-60225-7_9 | ✓ |
| S26 | ระบบ | ระบบบริหารมหาวิทยาลัย: รับสมัคร สอบ เช็กชื่อ ผลการเรียน | Akhter, N. (2017). Formal modeling and proving of Campus Management System: Event-B perspective. Bahria University Journal of Information & Communication Technologies, 10(2). http://web.archive.org/web/20220809115202/http://ojs.bahria.edu.pk/index.php/bujict/article/view/174 | ✓ |
| S27 | ระบบ | ระบบจัดการรายวิชา: เปิด–ปิดวิชาและลงทะเบียนผู้เรียน (ตัวอย่างในบทนำ Event-B) | Hoang, T. S. (2013). An introduction to the Event-B modelling method. In A. Romanovsky & M. Thomas (Eds.), Industrial deployment of system engineering methods (pp. 211–236). Springer. https://doi.org/10.1007/978-3-642-33170-1 https://www.southampton.ac.uk/~tsh2n14/publications/chapters/eventb-dbook13.pdf | ✓ |
| S28 | ระบบ | โปรโตคอลอุปกรณ์ IoT (LwM2M client) | Mouakher, I., Dhaou, F., & Attiogbé, J. C. (2020). Toward a correct implementation of LwM2M client with Event-B. In ICSOFT 2020 (pp. 172–179). SciTePress. https://doi.org/10.5220/0009832601720179 | ✓ |
| S29 | ระบบ | ควบคุมสิทธิ์การเข้าถึงและทรัพยากรของแอป serverless (Event-B) | Yagmahan, M. S. N., Rezazadeh, A., & Butler, M. (2024). An Event-B formal model for access control and resource management of serverless apps. In ABZ 2024 (LNCS 14759, pp. 181–190). Springer. https://doi.org/10.1007/978-3-031-63790-2_11 | ✓ |
| S30 | ระบบ | ประกอบ web service (BPEL) แล้วตรวจด้วย Event-B | Aït-Sadoune, I., & Aït-Ameur, Y. (2008). Verification and validation of web service composition using Event B method. In ABZ 2008 (LNCS 5238, pp. 339–340). Springer. https://doi.org/10.1007/978-3-540-87603-8_28 | ✓ |
| S31 | ระบบ | คลังรูปแบบการสื่อสารสำหรับระบบกระจาย (Event-B) | Dotti, F. L., & Ribeiro, L. (2012). Modeling communication semantics for distributed systems in Event-B. In Anais do XIII Workshop de Testes e Tolerância a Falhas (WTF 2012) (pp. 101–114). SBC. https://doi.org/10.5753/wtf.2012.23083 | ✓ |
| S32 | ระบบ | ตัวควบคุมปั๊มน้ำ (Event-B, refine 2 ขั้น) | Karmakar, R., Sarkar, B. B., & Chaki, N. (2021). Event-B based formal modeling of a controller: A case study. In COMSYS 2020 (AISC 1255, pp. 649–658). Springer. https://doi.org/10.1007/978-981-15-7834-2_60 | ✓ |
| S33 | formal อื่น | model checking สำหรับเกษตรแม่นยำ (timed automata) | Saddem, R. (2019). Model-checking pour l'agriculture de précision [Doctoral thesis, Université de Montpellier]. https://theses.hal.science/tel-02476234 | ✓ |

ไม่พบงานที่ใช้ LLM ทำนายผล Proof Obligation ของ Event-B (ณ วันที่ค้น) — จุดนี้เป็นช่องว่างที่งานนี้เติมได้
