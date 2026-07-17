import ollama


OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma2:2b"


def _model_structure_text(base_name: str, objects: list, flows: list) -> str:
    """Shared description of the current model — used by both CTL generation and chat."""
    flow_lines = "\n".join(f"    {i+1}. {m} : {snd} -> {rcv}"
                           for i, (m, snd, rcv) in enumerate(flows))
    return f"""ระบบชื่อ: {base_name}
Objects ในระบบ: {', '.join(objects)}

ลำดับข้อความ (message instance : ผู้ส่ง -> ผู้รับ):
{flow_lines}

โครงสร้างตัวแปรใน Event-B Machine (สำคัญมาก ใช้อ้างอิงตามนี้):
- sentMessages : เซตของข้อความที่ "ถูกส่งแล้ว" ข้อความจะถูกเพิ่มเข้าเรื่อยๆ และไม่เคยถูกลบ
  ดังนั้นเมื่อ sequence ทำงานจนจบ ข้อความทุกตัวจะอยู่ใน sentMessages
- receivedMessages : ข้อความที่ถูกรับแล้ว (subset ของ sentMessages)
- sender, receiver : ความสัมพันธ์ผู้ส่ง/ผู้รับ (message |-> object)

รูปแบบ CTL ของ ProB: state predicate (สูตร B) ต้องอยู่ใน {{ }} เสมอ แล้วครอบด้วย CTL operator (AG, EF, AF, EG, AX ...)
วิธีเขียน predicate ข้างใน {{ }} :
- "ข้อความ M ถูกส่งแล้ว" :  {{M : sentMessages}}
- "ผู้ส่งของ M คือ Obj"  :  {{M |-> Obj : sender}}
- "ผู้รับของ M คือ Obj"  :  {{M |-> Obj : receiver}}"""


def build_model_context(base_name: str, objects: list, flows: list) -> str:
    """System prompt that makes the chat aware of the currently-loaded model."""
    return f"""คุณเป็นผู้ช่วยด้าน Formal Methods (Event-B และ CTL) ประจำโปรแกรม ChronoSeq-B
ผู้ใช้กำลังทำงานกับโมเดลด้านล่างนี้ ให้ตอบคำถามและช่วยเขียน/เพิ่มสูตร CTL โดย**อ้างอิงจากโครงสร้างจริงนี้เท่านั้น** ใช้ชื่อ message instance จริง (ตัวที่มีเลขต่อท้าย เช่น _1, _2) และรูปแบบ CTL ของ ProB ที่ถูกต้อง

{_model_structure_text(base_name, objects, flows)}

เมื่อผู้ใช้ขอให้เพิ่มหรือแก้สูตร CTL ให้สร้างสูตรที่ valid ใน ProB โดยใช้ message instance จริงจากลำดับด้านบน (ห้ามคิดชื่อขึ้นเอง) พร้อมอธิบายความหมายของแต่ละสูตรสั้นๆ ตอบเป็นภาษาไทย"""


def generate_ctl_with_ollama(base_name: str, objects: list, flows: list) -> str:
    # flows: list of (message_instance, sender, receiver) in sequence order.
    instances = [m for (m, _, _) in flows]
    first = instances[0] if instances else "A"
    last = instances[-1] if instances else "B"
    prev = instances[-2] if len(instances) >= 2 else first

    prompt = f"""
    คุณเป็นผู้เชี่ยวชาญด้าน Formal Methods (Event-B และ CTL) ช่วยสร้างสูตร CTL สำหรับตรวจสอบระบบใน ProB

    {_model_structure_text(base_name, objects, flows)}

    งานของคุณ: สร้างสูตร CTL 3 แบบ โดย**ใช้ชื่อ instance จริง**จากลำดับด้านบน (เช่น {first}, {last})
    1. Reachability (ระบบทำงานจนจบได้) เช่น :  EF({{{last} : sentMessages}})
    2. Sequence (ลำดับถูกต้อง: ข้อความก่อนหน้าเกิด แล้วนำไปสู่ข้อความถัดไป) เช่น :  AG({{{prev} : sentMessages}} => AF({{{last} : sentMessages}}))
    3. Safety (ผู้ส่ง/ผู้รับถูกต้องเสมอ) เช่น :  AG({{{first} : sentMessages}} => {{{first} |-> ... : sender}})

    ตอบกลับเป็นภาษาไทยเท่านั้น อธิบายเข้าใจง่ายสำหรับผู้เริ่มต้น ไม่ต้องใช้สัญลักษณ์เรียงลำดับ ใช้แค่ - หรือ ตัวเลขก็พอ
    """
    try:
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}])
        return response['message']['content']
    except Exception as e:
        return f"ไม่สามารถติดต่อ Ollama ได้: {str(e)}"


def chat_with_ollama(model: str, messages: list) -> str:
    client = ollama.Client(host=OLLAMA_HOST)
    resp = client.chat(model=model, messages=messages)
    return resp["message"]["content"]
