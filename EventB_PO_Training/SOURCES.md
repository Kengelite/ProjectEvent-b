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
