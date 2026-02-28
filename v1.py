import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import xml.etree.ElementTree as ET
import zipfile
import tempfile
import base64
import zlib
import urllib.parse
import ollama  # อย่าลืม uv add ollama

# ===================== DOMAIN LOGIC =====================

def to_pascal_case(name: str) -> str:
    """แปลง string เป็น PascalCase"""
    if not name: return "System"
    parts = re.split(r"[^A-Za-z0-9]+", name)
    parts = [p for p in parts if p]
    if not parts: return "System"
    return "".join(p[0].upper() + p[1:] for p in parts)

def clean_html(raw_html):
    """ลบ HTML tags ออกจากข้อความใน Draw.io"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def extract_xml_root(xml_path: str):
    """จัดการถอดรหัส XML Draw.io กรณีมีการบีบอัดข้อมูล"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # ค้นหา <diagram> เพื่อเช็คว่ามีการบีบอัดข้อมูล (Compressed) หรือไม่
        diagram_element = root.find(".//diagram")
        if diagram_element is not None and diagram_element.text:
            try:
                # ขั้นตอน: Base64 Decode -> Decompress (Deflate) -> URL Decode
                compressed_data = base64.b64decode(diagram_element.text)
                xml_content = zlib.decompress(compressed_data, -15).decode('utf-8')
                xml_content = urllib.parse.unquote(xml_content)
                return ET.fromstring(xml_content)
            except:
                return root # ถ้าถอดรหัสไม่สำเร็จ ให้ใช้ root เดิม
        return root
    except Exception as e:
        raise RuntimeError(f"อ่าน XML ไม่ได้: {e}")

def extract_base_name_from_xml(xml_path: str) -> str:
    try:
        root = extract_xml_root(xml_path)
        name = None
        for elem in root.iter():
            if elem.tag == 'diagram':
                name = elem.get('name')
                if name and name != 'หน้า-1': break
        if not name:
            filename = os.path.basename(xml_path)
            name, _ = os.path.splitext(filename)
        return to_pascal_case(name)
    except:
        return "System"

def extract_objects_from_xml(xml_path: str) -> list:
    try:
        root = extract_xml_root(xml_path)
        objects = set()
        for elem in root.iter():
            style = elem.get('style', '')
            if 'umlLifeline' in style or 'shape=umlActor' in style or 'shape=rect' in style:
                value = clean_html(elem.get('value', ''))
                if value:
                    class_name = value.split(':')[-1].strip() if ':' in value else value.strip()
                    if class_name: objects.add(class_name)
        return sorted(list(objects))
    except: return []

def extract_messages_from_xml(xml_path: str) -> tuple:
    """
    Logic ใหม่:
    - ทุกชื่อบนเส้น (ทึบ/ประ) = Messages
    - ข้อมูลในวงเล็บ (params) = DataMessages
    """
    try:
        root = extract_xml_root(xml_path)
        messages = set()
        data_messages = set()
        
        for elem in root.iter('mxCell'):
            # ตรวจสอบว่าเป็นเส้นเชื่อม (edge="1") และมีค่าข้อความ (value)
            if elem.get('edge') == '1' and elem.get('value'):
                # 1. ล้าง HTML และดึงข้อความดิบมา
                raw_value = clean_html(elem.get('value')).strip()
                if not raw_value or raw_value.startswith('«'): continue

                # 2. แยกชื่อ Message ออกจากวงเล็บ
                # ใช้ Regex แยก: กลุ่ม 1 คือชื่อก่อนวงเล็บ, กลุ่ม 2 คือของในวงเล็บ
                match = re.search(r'^([a-zA-Z0-9_]+)(?:\((.*?)\))?', raw_value)
                
                if match:
                    msg_name = match.group(1).strip()
                    params_str = match.group(2)
                    
                    # ชื่อข้างหน้า (หรือชื่อเพียวๆ) คือ Message เสมอ
                    if msg_name:
                        messages.add(msg_name)
                    
                    # 3. ถ้ามีของในวงเล็บ ให้ถือว่าเป็น DataMessages
                    if params_str:
                        # แยกพารามิเตอร์ด้วยจุลภาค (,)
                        for p in re.split(r'[,;]', params_str):
                            data_val = p.strip()
                            if data_val:
                                data_messages.add(data_val)
                                
        return sorted(list(messages)), sorted(list(data_messages))
    except Exception as e:
        raise RuntimeError(f"ดึง messages ไม่ได้: {e}")
    



def extract_detailed_events(xml_path: str):
    root = extract_xml_root(xml_path) # ใช้ฟังก์ชันถอดรหัสเดิม
    lifelines = {} # id -> name
    edges = []

    # 1. สร้าง Map สำหรับ Lifelines (เพื่อดูว่า ID นี้คือเครื่องไหน)
    for elem in root.iter('mxCell'):
        style = elem.get('style', '')
        if 'umlLifeline' in style or 'shape=umlActor' in style or 'shape=rect' in style:
            val = clean_html(elem.get('value', ''))
            name = val.split(':')[-1].strip() if ':' in val else val.strip()
            lifelines[elem.get('id')] = name if name else f"Object_{elem.get('id')}"

    # 2. สกัด Edges (เส้นข้อความ) พร้อมพิกัด Y เพื่อเรียงลำดับ
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1' and elem.get('value'):
            value = clean_html(elem.get('value'))
            source_id = elem.get('source')
            target_id = elem.get('target')
            
            # ดึงพิกัด Y จาก mxGeometry เพื่อเรียงลำดับก่อน-หลัง
            geo = elem.find('mxGeometry')
            y_pos = float(geo.get('y', 0)) if geo is not None else 0
            
            # แยกชื่อ Message และ Data
            match = re.search(r'^([a-zA-Z0-9_]+)(?:\((.*?)\))?', value)
            if match:
                msg_name = match.group(1)
                data_name = match.group(2) if match.group(2) else None
                edges.append({
                    'msg': msg_name,
                    'data': data_name,
                    'sender': lifelines.get(source_id, "Unknown"),
                    'receiver': lifelines.get(target_id, "Unknown"),
                    'y': y_pos
                })

    # เรียงลำดับตามตำแหน่ง Y (บนลงล่าง)
    edges.sort(key=lambda x: x['y'])
    return edges

def generate_event_b_events(edges):
    event_list = []
    
    for i, edge in enumerate(edges, 1):
        m = f"{edge['msg']}_{i}"
        snd = edge['sender']
        rcv = edge['receiver']
        data = edge['data']
        
        # --- SEND EVENT ---
        send_event = f"""
    send{m}
    WHEN
        grd1: {m} ∉ sentMessages
        grd2: currentMessage = ∅
        """
        # ถ้าไม่ใช่เส้นแรก ต้องได้รับข้อความก่อนหน้าก่อน (Sequence Control)
        if i > 1:
            prev_m = f"{edges[i-2]['msg']}_{i-1}"
            send_event += f"    grd3: {prev_m} ∈ receivedMessages\n"
            
        send_event += f"""    THEN
        act1: sentMessages := sentMessages ∪ {{{m}}}
        act2: sender := sender ∪ {{{m} ↦ {snd}}}
        act3: receiver := receiver ∪ {{{m} ↦ {rcv}}}
        act4: receivedMessages := ∅
        """
        if data:
            send_event += f"        act5: senderdataMessages := senderdataMessages ∪ {{{m} ↦ {data}}}\n"
            send_event += f"        act6: currentMessage := {{{m}}}\n"
        else:
            send_event += f"        act5: currentMessage := {{{m}}}\n"
        send_event += "    END"
        
        # --- RECEIVE EVENT ---
        receive_event = f"""
    receive{m}
    WHEN
        grd1: {m} ∈ sentMessages
        grd2: {m} ↦ {snd} ∈ sender
        grd3: {m} ↦ {rcv} ∈ receiver
        grd4: {m} ∉ receivedMessages
        grd5: currentMessage = {{{m}}}
    THEN
        act1: receivedMessages := receivedMessages ∪ {{{m}}}
        """
        if data:
            receive_event += f"        act2: receiverdataMessages := receiverdataMessages ∪ {{{m} ↦ {data}}}\n"
            receive_event += f"        act3: currentMessage := ∅\n"
        else:
            receive_event += f"        act2: currentMessage := ∅\n"
        receive_event += "    END"
        
        event_list.append(send_event)
        event_list.append(receive_event)
        
    return "\n".join(event_list)




# ===================== ปรับปรุง DOMAIN LOGIC =====================

def extract_detailed_sequence(xml_path: str):
    """สกัดข้อมูลเส้นลำดับจากบนลงล่าง พร้อมคำนวณหาระยะ Sender/Receiver หากวาดเส้นไม่ติด (Snap)"""
    root = extract_xml_root(xml_path)
    lifelines = {} 
    lifelines_geo = [] # เก็บพิกัดแกน X ของแต่ละ Lifeline
    edges = []

    # 1. Map Lifelines (ID -> Name) และคำนวณจุดกึ่งกลาง (Center X)
    for elem in root.iter('mxCell'):
        style = elem.get('style', '')
        if 'umlLifeline' in style:
            val = clean_html(elem.get('value', ''))
            name = val.split(':')[-1].strip() if ':' in val else val.strip()
            name = name if name else f"Obj_{elem.get('id')}"
            
            lifelines[elem.get('id')] = name
            
            # หาจุดกึ่งกลางแกน X เพื่อเตรียมไว้เทียบระยะ
            geo = elem.find('mxGeometry')
            if geo is not None:
                x = float(geo.get('x', 0))
                width = float(geo.get('width', 100)) # ค่าเริ่มต้นของ lifeline ปกติคือกว้าง 100
                center_x = x + (width / 2)
                lifelines_geo.append({'id': elem.get('id'), 'name': name, 'center_x': center_x})

    # ฟังก์ชันช่วยหาระยะที่ใกล้ที่สุด (Tolerance +- 100 pixels ปรับเพิ่มลดได้)
    def get_nearest_lifeline(target_x, tolerance=100):
        closest_name = "Unknown"
        min_dist = float('inf')
        for ll in lifelines_geo:
            dist = abs(ll['center_x'] - target_x)
            if dist < min_dist and dist <= tolerance:
                min_dist = dist
                closest_name = ll['name']
        return closest_name

    # 2. Extract Edges (Messages) พร้อมพิกัด Y
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1' and elem.get('value'):
            val = clean_html(elem.get('value'))
            geo = elem.find('mxGeometry')
            y_pos = float(geo.get('y', 0)) if geo is not None else 0
            
            # 2.1 หา Source และ Target (ถ้ามี Attribute จากการ Snap ให้ใช้เลย)
            source_id = elem.get('source')
            target_id = elem.get('target')
            
            source_name = lifelines.get(source_id) if source_id else None
            target_name = lifelines.get(target_id) if target_id else None
            
            # 2.2 ถ้าหาไม่เจอ (วาดไม่ติดกัน) ให้ดึงจากพิกัด x ของเส้น (sourcePoint / targetPoint)
            if geo is not None:
                if not source_name:
                    sp = geo.find("./mxPoint[@as='sourcePoint']")
                    if sp is not None:
                        source_name = get_nearest_lifeline(float(sp.get('x', 0)))
                        
                if not target_name:
                    tp = geo.find("./mxPoint[@as='targetPoint']")
                    if tp is not None:
                        target_name = get_nearest_lifeline(float(tp.get('x', 0)))
            
            # Fallback สุดท้ายถ้าหาพิกัดไม่ได้เลยจริงๆ
            source_name = source_name or "Unknown"
            target_name = target_name or "Unknown"

            # 2.3 แยก Message Name และ Data ในวงเล็บ
            match = re.search(r'^([a-zA-Z0-9_]+)(?:\((.*?)\))?', val)
            if match:
                msg_name = match.group(1).strip()
                data_name = match.group(2).strip() if match.group(2) else None
                edges.append({
                    'msg': msg_name,
                    'data': data_name,
                    'sender': source_name,
                    'receiver': target_name,
                    'y': y_pos
                })

    # เรียงลำดับตามตำแหน่ง Y (บนลงล่าง)
    edges.sort(key=lambda x: x['y'])
    return edges

def generate_step_events(edges):
    """สร้างคู่ Send/Receive สำหรับแต่ละ Message ตามลำดับ"""
    events = []
    for i, edge in enumerate(edges, 1):
        m = f"{edge['msg']}_{i}"
        snd, rcv, data = edge['sender'], edge['receiver'], edge['data']
        
        # --- SEND EVENT ---
        send = f"""
    send{m}
    WHEN
        grd1: {m} ∉ sentMessages
        grd2: currentMessage = ∅"""
        # ลำดับ Sequence: ต้องได้รับข้อความก่อนหน้าแล้วเท่านั้น (ยกเว้นเส้นแรก)
        if i > 1:
            prev_m = f"{edges[i-2]['msg']}_{i-1}"
            send += f"\n        grd3: {prev_m} ∈ receivedMessages"
        
        send += f"""
    THEN
        act1: sentMessages := sentMessages ∪ {{{m}}}
        act2: sender := sender ∪ {{{m} ↦ {snd}}}
        act3: receiver := receiver ∪ {{{m} ↦ {rcv}}}
        act4: receivedMessages := ∅"""
        if data:
            send += f"\n        act5: senderdataMessages := senderdataMessages ∪ {{{m} ↦ {data}}}"
            send += f"\n        act6: currentMessage := {{{m}}}"
        else:
            send += f"\n        act5: currentMessage := {{{m}}}"
        send += "\n    END"
        
        # --- RECEIVE EVENT ---
        receive = f"""
    receive{m}
    WHEN
        grd1: {m} ∈ sentMessages
        grd2: {m} ↦ {snd} ∈ sender
        grd3: {m} ↦ {rcv} ∈ receiver
        grd4: {m} ∉ receivedMessages
        grd5: currentMessage = {{{m}}}
    THEN
        act1: receivedMessages := receivedMessages ∪ {{{m}}}"""
        if data:
            receive += f"\n        act2: receiverdataMessages := receiverdataMessages ∪ {{{m} ↦ {data}}}"
            receive += f"\n        act3: currentMessage := ∅"
        else:
            receive += f"\n        act2: currentMessage := ∅"
        receive += "\n    END"
        
        events.extend([send, receive])
    return "\n".join(events)

# ===================== ปรับปรุงฟังก์ชันแปลงหลัก =====================

def apply_rules_1_and_2(xml_path: str, version: int = 1) -> str:
    """ฟังก์ชันหลักที่รวม Logic ทั้งหมดเพื่อสร้างไฟล์ Event-B"""
    base_name = extract_base_name_from_xml(xml_path)
    edges = extract_detailed_sequence(xml_path)
    
    # รวบรวม Constants ทั้งหมด
    objects = sorted(list(set([e['sender'] for e in edges] + [e['receiver'] for e in edges])))
    msg_instances = [f"{e['msg']}_{i}" for i, e in enumerate(edges, 1)]
    raw_messages = sorted(list(set([e['msg'] for e in edges])))
    data_messages = sorted(list(set([e['data'] for e in edges if e['data']])))
    
    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    
    return f"""CONTEXT {context_name}
SETS
    Objects; Messages; DataMessages
CONSTANTS
    {", ".join(objects)}
    {", ".join(raw_messages)}
    {", ".join(msg_instances)}
    {", ".join(data_messages) if data_messages else "/* No Data */"}
AXIOMS
    axm1: Objects = {{ {", ".join(objects)} }}
    axm2: Messages = {{ {", ".join(raw_messages + msg_instances)} }}
    axm3: DataMessages = {{ {", ".join(data_messages) if data_messages else ""} }}
END

MACHINE {machine_name}
SEES {context_name}
VARIABLES 
    sentMessages sender receiver receivedMessages 
    senderdataMessages currentMessage receiverdataMessages
INVARIANTS
    inv1: sentMessages ⊆ Messages
    inv2: currentMessage ⊆ Messages
    inv3: sender ⊆ Messages × Objects
    inv4: receiver ⊆ Messages × Objects
    inv5: receivedMessages ⊆ sentMessages
    inv6: senderdataMessages ⊆ Messages × DataMessages
    inv7: receiverdataMessages ⊆ Messages × DataMessages
EVENTS
    INITIALISATION BEGIN
        sentMessages, sender, receiver, receivedMessages, 
        senderdataMessages, currentMessage, receiverdataMessages := ∅, ∅, ∅, ∅, ∅, ∅, ∅
    END

{generate_step_events(edges)}

END"""


# ===================== TKINTER UI =====================

class SequenceToEventBApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Sequence Diagram XML → Event-B & AI CTL")
        self.master.geometry("1100x750")
        self.current_xml_path = None
        
        top_frame = tk.Frame(master)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(top_frame, text="📁 เลือกไฟล์ XML", command=self.open_xml_file, bg="#4CAF50", fg="black", padx=10).pack(side=tk.LEFT)
        
        tk.Label(top_frame, text="Ver:").pack(side=tk.LEFT, padx=(10, 2))
        self.version_var = tk.IntVar(value=1)
        tk.Entry(top_frame, textvariable=self.version_var, width=3).pack(side=tk.LEFT)
        
        tk.Button(top_frame, text="🔄 แปลงเป็น Event-B", command=self.run_transform, bg="#2196F3", fg="black", padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="🤖 สร้าง CTL (AI)", command=self.run_ai_ctl, bg="#9C27B0", fg="black", padx=10).pack(side=tk.LEFT)
        tk.Button(top_frame, text="💾 บันทึก", command=self.save_output, bg="#FF9800", fg="black", padx=10).pack(side=tk.LEFT, padx=5)
        
        self.lbl_file = tk.Label(master, text="ยังไม่ได้เลือกไฟล์ XML", anchor="w", fg="gray")
        self.lbl_file.pack(fill=tk.X, padx=10)
        
        info_frame = tk.Frame(master)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_objects = tk.Label(info_frame, text="", anchor="w", fg="blue", wraplength=1000)
        self.lbl_objects.pack(fill=tk.X)
        
        self.text_output = ScrolledText(master, wrap=tk.NONE, font=("Courier New", 11))
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def open_xml_file(self):
        path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if path:
            self.current_xml_path = path
            self.lbl_file.config(text=f"📄 {os.path.basename(path)}", fg="green")
            obj = extract_objects_from_xml(path)
            msg, data = extract_messages_from_xml(path)
            self.lbl_objects.config(text=f"พบ: {len(obj)} Objects | {len(msg)} Messages | {len(data)} Data")

    def run_transform(self):
        if not self.current_xml_path: return
        res = apply_rules_1_and_2(self.current_xml_path, self.version_var.get())
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, res)

    def run_ai_ctl(self):
        if not self.current_xml_path: return
        self.text_output.insert(tk.END, "\n\n" + "="*30 + " AI ANALYZING CTL " + "="*30 + "\n")
        self.master.update_idletasks()
        
        try:
            base = extract_base_name_from_xml(self.current_xml_path)
            msgs, _ = extract_messages_from_xml(self.current_xml_path)
            
            prompt = f"System: {base}\nMessages: {msgs}\nGenerate 3 CTL formulas for ProB. Use 'sentMessages' variable. Format: AG({{msg}} <: sentMessages -> AF({{msg2}} <: sentMessages)). Add Thai explanation."
            
            client = ollama.Client(host='http://127.0.0.1:11434')
            response = client.chat(model='gemma2:2b', messages=[{'role': 'user', 'content': prompt}])
            self.text_output.insert(tk.END, response['message']['content'])
        except Exception as e:
            self.text_output.insert(tk.END, f"\n❌ AI Error: {e}")
        self.text_output.see(tk.END)

    def save_output(self):
        # (ฟังก์ชัน save_output คงเดิม)
        pass



# ==========================================================
# ส่วนเพิ่มใหม่: OLLAMA & CTL LOGIC (วางต่อท้าย Class เดิม)
# ==========================================================


def generate_ctl_with_ollama(base_name, objects, messages):
    prompt = f"""
    คุณเป็นผู้เชี่ยวชาญด้าน Formal Methods (Event-B และ CTL)
    ข้อมูลระบบชื่อ: {base_name}
    Objects ในระบบ: {', '.join(objects)}
    Messages ที่เกิดขึ้น: {', '.join(messages)}
    
    ตัวแปรใน Event-B Machine:
    - sentMessages (เซตของข้อความที่ถูกส่งแล้ว)
    
    งานของคุณ:
    ช่วยสร้างสูตร CTL 3 สูตรสำหรับตรวจสอบความถูกต้องของระบบนี้ใน ProB
    1. Safety: ข้อความสำคัญต้องไม่ถูกส่งซ้ำซ้อน
    2. Liveness: เมื่อมีการส่งข้อความต้นทาง จะต้องมีการตอบกลับเสมอ
    3. Sequence: ลำดับการทำงานต้องถูกต้อง
    
    ตอบกลับด้วยสูตร CTL ในรูปแบบ ProB Syntax (เช่น AG({{A}} <: sentMessages -> AF({{B}} <: sentMessages)))
    พร้อมคำอธิบายภาษาไทยสั้นๆ
    """
    try:
        response = ollama.chat(model='gemma2:2b', messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content']
    except Exception as e:
        return f" ไม่สามารถติดต่อ Ollama ได้: {str(e)}"

# --- ส่วนการทำ Monkey Patching เพื่อเพิ่มปุ่มโดยไม่แก้ Code Class เดิม ---

# เก็บฟังก์ชัน __init__ เดิมไว้
original_init = SequenceToEventBApp.__init__

def patched_init(self, master):
    # เรียกใช้ __init__ เดิมก่อนเพื่อให้หน้าจอหลักถูกสร้าง
    original_init(self, master)
    
    # หาปุ่มใน top_frame เพื่อเพิ่มปุ่มใหม่ต่อท้าย
    # เราจะหา Frame แรกที่เจอใน master
    for widget in master.winfo_children():
        if isinstance(widget, tk.Frame):
            self.btn_ai = tk.Button(
                widget,
                text="สร้าง CTL (Ollama)",
                command=self.run_ai_ctl,
                bg="#9C27B0", # สีม่วง
                fg="black",
                padx=10,
                pady=5
            )
            self.btn_ai.pack(side=tk.LEFT, padx=10)
            break

def run_ai_ctl(self):
    if not self.current_xml_path:
        messagebox.showwarning("เตือน", "กรุณาเลือกไฟล์ XML ก่อน")
        return
        
    self.text_output.insert(tk.END, "\n" + "="*50 + "\n")
    self.text_output.insert(tk.END, "กำลังส่งข้อมูลให้ Ollama วิเคราะห์ CTL...\n")
    self.text_output.see(tk.END)
    self.master.update_idletasks()
    
    try:
        base_name = extract_base_name_from_xml(self.current_xml_path)
        objects = extract_objects_from_xml(self.current_xml_path)
        messages, _ = extract_messages_from_xml(self.current_xml_path)
        
        ctl_result = generate_ctl_with_ollama(base_name, objects, messages)
        
        self.text_output.insert(tk.END, f"\n✨ [AI Generated CTL Properties]:\n{ctl_result}\n")
        self.text_output.insert(tk.END, "="*50 + "\n")
        self.text_output.see(tk.END)
    except Exception as e:
        messagebox.showerror("AI Error", str(e))

# นำฟังก์ชันใหม่ไปสวมแทนที่ของเดิมใน Class
SequenceToEventBApp.__init__ = patched_init
SequenceToEventBApp.run_ai_ctl = run_ai_ctl
# ==========================================================


def main():
    root = tk.Tk()
    app = SequenceToEventBApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()


