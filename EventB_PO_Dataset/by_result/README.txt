by_result/ — แยก model ตามผลจาก Rodin เพื่อเปิดดูเท่านั้น

pass/  = model ที่ PO discharge ครบ (failed = 0)
fail/  = model ที่มี PO พิสูจน์ไม่ได้อย่างน้อย 1 ข้อ (failed > 0)

ชื่อโฟลเดอร์ = <model_id>_<case>  ข้างในเป็นสำเนาของ models/<model_id>/
ผ่าน/ไม่ผ่านอ่านจาก models/<model_id>/label.json (prover: Rodin 3.9 + Atelier B ML/PP)

ห้ามใช้โฟลเดอร์นี้ (หรือชื่อโฟลเดอร์ pass/fail) เป็นข้อมูล train หรือ input ของ LLM
เพราะชื่อโฟลเดอร์คือเฉลย — สำหรับ train ให้ใช้ dataset.jsonl

สร้างใหม่ได้ด้วย: python tools/make_by_result.py
