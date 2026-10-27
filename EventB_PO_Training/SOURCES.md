# แหล่งที่มา (Sources)

## ที่มาของข้อมูล

| รายการ | รายละเอียด |
|---|---|
| แผนภาพต้นทาง | Sequence Diagram 197 แบบจำลอง สร้างด้วย draw.io (ไฟล์ .drawio.xml) ครอบคลุม 11 หัวข้อ และ model_001 Payment & Notification ซึ่งเป็นกรณีทดสอบจากงานเดิม |
| การแปลง | ChronoSeq-B (https://github.com/Kengelite/ProjectEvent-b) commit 20fad33 (2026-08-30) — แปลงแผนภาพเป็น Event-B และ Rodin project โดยไม่แก้ไขผลลัพธ์ภายหลัง |
| การพิสูจน์ | Rodin Platform บน Windows (Eclipse platform 4.23) ร่วมกับ Atelier B provers plugin — ใน proof file พบ reasoner com.clearsy.atelierb.provers.core.externalML และ externalPP |
| ช่วงเวลาพิสูจน์ | รอบแรก 1–2 ตุลาคม 2026 (26 แบบจำลองที่ไม่เปลี่ยน ใช้ผลรอบนี้) · รอบหลัก 26 ตุลาคม 2026 |
| การอ่านผล | อ่านสถานะจากไฟล์ .bps: PO ผ่านเมื่อ confidence = 1000 และ proof ไม่อยู่ในสถานะ broken |
| เครื่องมือประมวลผล | Python 3.14.0 · script ใน EventB_PO_Dataset/tools/ (https://github.com/Kengelite/ProjectEvent-b) |

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
