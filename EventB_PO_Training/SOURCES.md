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

ค้นจากเว็บเมื่อ 27 ต.ค. 2026 — คล้ายด้านระบบหรือวิธีการ **ไม่ใช่แหล่งที่มาของข้อมูล** แบบจำลองแต่ละตัวจับคู่กับงานเหล่านี้ใน `csv/similar_work.csv` (ตามชื่อระบบก่อน ถ้าไม่พบใช้ตามหัวข้อ) ควรเปิดตรวจลิงก์ก่อนอ้างในเล่ม

| รหัส | ด้าน | คล้ายเรื่อง | อ้างอิง |
|---|---|---|---|
| S1 | วิธีการ | แปลง UML Sequence Diagram เป็น Event-B (combined fragments) | Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2015). Extending causal semantics of UML2.0 sequence diagram for distributed systems. ICSOFT-EA 2015, 339–347. https://www.scitepress.org/Papers/2015/55177/ |
| S2 | วิธีการ | Sequence Diagram ที่มี fragment ซ้อนกัน | Dhaou, F., Mouakher, I., Attiogbé, C., & Bsaies, K. (2017). A causal semantics for UML2.0 sequence diagrams with nested combined fragments. ENASE 2017. https://www.scitepress.org/Papers/2017/63141 |
| S3 | วิธีการ | แปลง UML timing diagram เป็น Event-B (กรณีศึกษาลิฟต์) | Joochim, T., Gravell, A., & Poppleton, M. Translating UML 2.0 timing diagrams into Event-B and UML-B. https://eprints.soton.ac.uk/268489/ |
| S4 | วิธีการ | deadline / delay ใน Event-B (ตรงกับ t_time / t_delay ของเรา) | Sarshogh, M. R., & Butler, M. (2011). Specification and refinement of discrete timing properties in Event-B. ECEASST, 46. https://journal.ub.tu-berlin.de/eceasst/article/view/701 |
| S5 | ระบบ | ไฟจราจร (ตัวอย่างใน Rodin Handbook) | Jastram, M., & Butler, M. Rodin User's Handbook — Traffic light tutorial. https://www3.hhu.de/stups/handbook/rodin/release-2014-12-04/html/tut_building_the_model.html |
| S6 | ระบบ | ATM / บัญชีธนาคาร (UML-B ATM ใน Event-B Examples) | Event-B Wiki. Event-B Examples (ATM development). https://wiki.event-b.org/index.php/Event-B_Examples |
| S7 | ระบบ | กระเป๋าเงินอิเล็กทรอนิกส์ (Mondex) | Butler, M., & Yadav, D. (2008). An incremental development of the Mondex system in Event-B. Formal Aspects of Computing, 20(1), 61–77.  |
| S8 | ระบบ | เครื่องฟอกไต (ABZ 2016 case study) | Mashkoor, A. (2016). The hemodialysis machine case study. ABZ 2016. https://irit.fr/ABZ-CS/html_files/files/2016/PDF/Case_Study_The%20Hemodialysis%20Machine_2016.pdf |
| S9 | ระบบ | อุปกรณ์การแพทย์ (Event-B + Rodin, เครื่องฟอกไต) | Mashkoor, A., et al. (2017). Towards the trustworthy development of active medical devices: A hemodialysis case study. arXiv:1706.06369. https://arxiv.org/abs/1706.06369 |
| S10 | ระบบ | ระบบควบคุมรถไฟ (ABZ 2018 Hybrid ERTMS/ETCS Level 3) | Mammar, A., Frappier, M., Tueno Fotso, S. J., & Laleau, R. (2018). An Event-B model of the hybrid ERTMS/ETCS level 3 standard. ABZ 2018. https://hal.archives-ouvertes.fr/hal-01797810 |
| S11 | ระบบ | ควบคุมความเร็ว / ไฟรถยนต์ (ABZ 2020) | Mammar, A., & Frappier, M. (2020). Modeling of a speed control system using Event-B. ABZ 2020, 367–381. https://doi.org/10.1007/978-3-030-48077-6_29 |
| S12 | ระบบ | ระบบฐานล้อเครื่องบิน (ABZ 2014 landing gear) | Mammar, A., & Laleau, R. (2014). Modelling an aircraft landing system in Event-B (full report). arXiv:1407.0927. https://arxiv.org/abs/1407.0927 |
| S13 | ระบบ | ระบบ IoT (invariant ของสถาปัตยกรรม IoT) | Architectural invariants and correctness of IoT-based systems. arXiv:1912.08912. https://arxiv.org/abs/1912.08912 |
| S14 | ระบบ | โครงข่ายไฟฟ้าอัจฉริยะผ่าน IoT (Event-B dataset) | University of Southampton. Event-B model of an IoT-enabled smart grid (dataset). https://eprints.soton.ac.uk/498327 |
| S15 | ระบบ | โปรโตคอลอุปกรณ์ IoT (LwM2M client) | Toward a correct implementation of LwM2M client with Event-B. ICSOFT 2020. https://www.scitepress.org/Papers/2020/98326/ |
| S16 | ระบบ | ระบบลงคะแนนเลือกตั้ง | Gibson, J. P., Kherroubi, S., & Méry, D. (2017). Applying a dependency mechanism for voting protocol models using Event-B. FORTE 2017. https://hal.archives-ouvertes.fr/hal-01658423 |

ไม่พบงาน Event-B ที่ตรงกับหัวข้อโลจิสติกส์ ค้าปลีก การจอง และเกษตร และไม่พบงานที่ใช้ LLM ทำนายผล Proof Obligation ของ Event-B (ณ วันที่ค้น) — จุดนี้เป็นช่องว่างที่งานนี้เติมได้
