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
import customtkinter as ctk
# ===================== DOMAIN LOGIC =====================ddd

BG      = "#0D1117"
PANEL   = "#161B22"
CARD    = "#1C2230"
BORDER  = "#2A3040"
ACCENT  = "#58A6FF"
GREEN   = "#3FB950"
VIOLET  = "#BC8CFF"
GOLD    = "#E3B341"
WARN    = "#F78166"
TEXT    = "#E6EDF3"
MUTED   = "#8B949E"
CHAT_ME = "#1C3048"
CHAT_AI = "#182618"

MONO = ("Courier New", 11)
UI   = ("Segoe UI",    10)
SM   = ("Segoe UI",     9)


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

def extract_fragments_from_xml(xml_path: str) -> list:
    """ปรับปรุงใหม่: รองรับ sysml.package และ Text Box เงื่อนไขที่แยกต่างหาก"""
    root = extract_xml_root(xml_path)
    fragments = []
    counts = {'opt': 1, 'loop': 1, 'par': 1, 'alt': 1}
    
    temp_frags = []
    # 1. หากรอบ Fragment (รองรับทั้ง umlFrame และ sysml.package)
    for elem in root.iter('mxCell'):
        val = clean_html(elem.get('value', '')).strip()
        val_lower = val.lower()
        style = elem.get('style', '').lower()
        
        f_type = None
        for t in ['opt', 'loop', 'par', 'alt']:
            if val_lower.startswith(t) and ('umlframe' in style or 'sysml.package' in style or 'shape=rect' in style):
                f_type = t
                break
        
        if f_type:
            geo = elem.find('mxGeometry')
            if geo is not None:
                y = float(geo.get('y', 0))
                h = float(geo.get('height', 0))
                
                # ลองหาเงื่อนไขกรณีพิมพ์รวมกันมาในกล่อง (เช่น opt [Login == 1])
                cond = ""
                match = re.search(r'\[(.*?)\]', val)
                if match:
                    cond = match.group(1).strip()
                    
                temp_frags.append({
                    'type': f_type,
                    'condition': cond,
                    'y_start': y,
                    'y_end': y + h
                })
                
    # 2. หาเงื่อนไขจาก Text box ที่แยกออกมา (กรณีวาดแยกกันแบบใน XML)
    for elem in root.iter('mxCell'):
        val = clean_html(elem.get('value', '')).strip()
        style = elem.get('style', '').lower()
        
        if 'text' in style and '[' in val and ']' in val:
            match = re.search(r'\[(.*?)\]', val)
            if match:
                cond_text = match.group(1).strip()
                geo = elem.find('mxGeometry')
                if geo is not None:
                    y = float(geo.get('y', 0))
                    # แมป Text Box เข้ากับ Fragment ที่ครอบมันอยู่ (ยืดหยุ่นให้ +- 30 pixels)
                    for f in temp_frags:
                        if not f['condition']: 
                            if (f['y_start'] - 30) <= y <= (f['y_end'] + 30):
                                f['condition'] = cond_text
                                break
                                
    # 3. จัดการตั้งชื่อ ID ให้ Fragment
    for f in temp_frags:
        f['id'] = f"{f['type']}{counts[f['type']]}"
        counts[f['type']] += 1
        fragments.append(f)
        
    return fragments

# (ฟังก์ชัน extract_detailed_sequence และ generate_step_events ใช้ตัวเดิมจากรอบที่แล้วได้เลยครับ 
# แนะนำให้ก๊อปปี้ apply_rules_1_and_2 ด้านล่างนี้ไปวางทับแทน เพื่อแก้เรื่อง Message ซ้ำซ้อน)

def apply_rules_1_and_2(xml_path: str, version: int = 1) -> str:
    base_name = extract_base_name_from_xml(xml_path)
    fragments = extract_fragments_from_xml(xml_path)
    edges = extract_detailed_sequence(xml_path)
    
    objects = sorted(list(set([e['sender'] for e in edges] + [e['receiver'] for e in edges])))
    # สร้างเฉพาะ Message แบบมีลำดับ (เช่น submitPayment_1) ลบตัวธรรมดาทิ้งเพื่อไม่ให้รก
    msg_instances = [f"{e['msg']}_{i}" for i, e in enumerate(edges, 1)]
    data_messages = sorted(list(set([e['data'] for e in edges if e['data']])))
    
    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    
    # ---------------- Parsing Fragment Conditions ----------------
    frag_vars = {}
    for f in fragments:
        cond = f['condition']
        if cond:
            match = re.search(r'([a-zA-Z0-9_]+)\s*(==|=|<=|>=|<|>)\s*([0-9]+)', cond)
            if match:
                frag_vars[match.group(1)] = {'op': match.group(2), 'val': match.group(3)}
            else:
                frag_vars[cond] = {'op': '=', 'val': '0'}
    
    for f in fragments:
        if f['type'] == 'loop' and 'retry' not in frag_vars:
            frag_vars['retry'] = {'op': '=', 'val': '0'}
        elif f['type'] == 'par' and f['id'] not in frag_vars:
            frag_vars[f"par_{f['id'].replace('par', '')}"] = {'op': '=', 'val': '0'}

    # ---------------- VARIABLES ----------------
    base_vars = ["sentMessages", "sender", "receiver", "receivedMessages", 
                 "senderdataMessages", "currentMessage", "receiverdataMessages"]
    all_vars = base_vars + list(frag_vars.keys())
    
    # ---------------- INVARIANTS ----------------
    invs = [
        "inv1: sentMessages ⊆ Messages",
        "inv2: currentMessage ⊆ Messages",
        "inv3: sender ⊆ Messages × Objects",
        "inv4: receiver ⊆ Messages × Objects",
        "inv5: receivedMessages ⊆ sentMessages",
        "inv6: senderdataMessages ⊆ Messages × DataMessages",
        "inv7: receiverdataMessages ⊆ Messages × DataMessages"
    ]
    inv_idx = 8
    for v in frag_vars.keys():
        invs.append(f"inv{inv_idx}: {v} ∈ ℤ")
        inv_idx += 1
        
    # ---------------- INITIALISATION ----------------
    inits = [
        "act1: sentMessages := ∅",
        "act2: sender := ∅",
        "act3: receiver := ∅",
        "act4: receivedMessages := ∅",
        "act5: senderdataMessages := ∅",
        "act6: receiverdataMessages := ∅",
        "act7: currentMessage := ∅"
    ]
    act_idx = 8
    for v, details in frag_vars.items():
        op = details['op']
        val = details['val']
        if op in ['<', '<=']:
            inits.append(f"act{act_idx}: {v} :∈ 0..{val}")
        else:
            inits.append(f"act{act_idx}: {v} := {val}")
        act_idx += 1

    return f"""CONTEXT {context_name}
SETS
    Objects; Messages; DataMessages
CONSTANTS
    {", ".join(objects)}
    {", ".join(msg_instances)}
    {", ".join(data_messages) if data_messages else "/* No Data */"}
AXIOMS
    axm1: Objects = {{ {", ".join(objects)} }}
    axm2: Messages = {{ {", ".join(msg_instances)} }}
    axm3: DataMessages = {{ {", ".join(data_messages) if data_messages else ""} }}
END

MACHINE {machine_name}
SEES {context_name}
VARIABLES 
    {", ".join(all_vars)}
INVARIANTS
    {"\n    ".join(invs)}
EVENTS
    INITIALISATION BEGIN
        {"\n        ".join(inits)}
    END

{generate_step_events(edges)}

END"""

def extract_detailed_sequence(xml_path: str):
    root = extract_xml_root(xml_path)
    fragments = extract_fragments_from_xml(xml_path) 
    lifelines = {} 
    lifelines_geo = [] 
    edges = []

    # Map Lifelines
    for elem in root.iter('mxCell'):
        style = elem.get('style', '')
        if 'umlLifeline' in style or 'shape=umlActor' in style or 'shape=rect' in style:
            val = clean_html(elem.get('value', ''))
            name = val.split(':')[-1].strip() if ':' in val else val.strip()
            name = name if name else f"Obj_{elem.get('id')}"
            lifelines[elem.get('id')] = name
            
            geo = elem.find('mxGeometry')
            if geo is not None:
                x = float(geo.get('x', 0))
                width = float(geo.get('width', 100))
                center_x = x + (width / 2)
                lifelines_geo.append({'id': elem.get('id'), 'name': name, 'center_x': center_x})

    def get_nearest_lifeline(target_x, tolerance=100):
        closest_name = "Unknown"
        min_dist = float('inf')
        for ll in lifelines_geo:
            dist = abs(ll['center_x'] - target_x)
            if dist < min_dist and dist <= tolerance:
                min_dist = dist
                closest_name = ll['name']
        return closest_name

    # Extract Edges
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1' and elem.get('value'):
            val = clean_html(elem.get('value'))
            geo = elem.find('mxGeometry')
            
            # --- [จุดที่แก้ไข] ดึงพิกัด Y จาก sourcePoint หรือ targetPoint ของเส้นแทน ---
            y_pos = 0
            if geo is not None:
                sp = geo.find("./mxPoint[@as='sourcePoint']")
                tp = geo.find("./mxPoint[@as='targetPoint']")
                if sp is not None and sp.get('y'):
                    y_pos = float(sp.get('y'))
                elif tp is not None and tp.get('y'):
                    y_pos = float(tp.get('y'))
                else:
                    y_pos = float(geo.get('y', 0))
            # -----------------------------------------------------------------
            
            source_id = elem.get('source')
            target_id = elem.get('target')
            source_name = lifelines.get(source_id) if source_id else None
            target_name = lifelines.get(target_id) if target_id else None
            
            if geo is not None:
                if not source_name:
                    sp = geo.find("./mxPoint[@as='sourcePoint']")
                    if sp is not None: source_name = get_nearest_lifeline(float(sp.get('x', 0)))
                if not target_name:
                    tp = geo.find("./mxPoint[@as='targetPoint']")
                    if tp is not None: target_name = get_nearest_lifeline(float(tp.get('x', 0)))
            
            source_name = source_name or "Unknown"
            target_name = target_name or "Unknown"

            match = re.search(r'^([a-zA-Z0-9_]+)(?:\((.*?)\))?', val)
            if match:
                msg_name = match.group(1).strip()
                data_name = match.group(2).strip() if match.group(2) else None
                
                # เช็คว่าพิกัด Y ของเส้น อยู่ในขอบเขตความสูงของกล่อง Fragment ไหม (+- ระยะเผื่อ 20)
                in_frag = None
                tolerance = 20 
                for f in fragments:
                    if (f['y_start'] - tolerance) <= y_pos <= (f['y_end'] + tolerance):
                        in_frag = f
                        break

                edges.append({
                    'msg': msg_name,
                    'data': data_name,
                    'sender': source_name,
                    'receiver': target_name,
                    'y': y_pos,
                    'fragment': in_frag
                })

    # เรียงลำดับจากบนลงล่าง
    edges.sort(key=lambda x: x['y'])
    return edges

def generate_step_events(edges):
    events = []
    for i, edge in enumerate(edges, 1):
        m = f"{edge['msg']}_{i}"
        snd, rcv, data = edge['sender'], edge['receiver'], edge['data']
        frag = edge['fragment']
        
        # ใส่ _opt1 เข้าไปในชื่อ event หากอยู่ใน Option Fragment
        suffix = f"_{frag['id']}" if frag and frag['type'] == 'opt' else ""
        
        # --- SEND EVENT ---
        send = f"""
    send{m}{suffix}
    WHEN
        grd1: {m} ∉ sentMessages
        grd2: currentMessage = ∅"""
        
        grd_idx = 3
        if i > 1:
            prev_m = f"{edges[i-2]['msg']}_{i-1}"
            send += f"\n        grd{grd_idx}: {prev_m} ∈ receivedMessages"
            grd_idx += 1
            
        # เพิ่ม Guard ของ Fragment
        if frag and frag['condition']:
            cond_clean = frag['condition'].replace("==", "=").strip()
            send += f"\n        grd{grd_idx}: {cond_clean}"
            
        send += f"""
    THEN
        act1: sentMessages := sentMessages ∪ {{{m}}}
        act2: sender := sender ∪ {{{m} ↦ {snd}}}
        act3: receiver := receiver ∪ {{{m} ↦ {rcv}}}
        act4: receivedMessages := ∅"""
        
        act_idx = 5
        if data:
            send += f"\n        act{act_idx}: senderdataMessages := senderdataMessages ∪ {{{m} ↦ {data}}}"
            act_idx += 1
            send += f"\n        act{act_idx}: currentMessage := {{{m}}}"
        else:
            send += f"\n        act{act_idx}: currentMessage := {{{m}}}"
        send += "\n    END"
        
        # --- RECEIVE EVENT ---
        receive = f"""
    receive{m}{suffix}
    WHEN
        grd1: {m} ∈ sentMessages
        grd2: {m} ↦ {snd} ∈ sender
        grd3: {m} ↦ {rcv} ∈ receiver
        grd4: {m} ∉ receivedMessages
        grd5: currentMessage = {{{m}}}"""
        
        grd_idx = 6
        if frag and frag['condition']:
            cond_clean = frag['condition'].replace("==", "=").strip()
            receive += f"\n        grd{grd_idx}: {cond_clean}"
            
        receive += f"""
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

def apply_rules_1_and_2(xml_path: str, version: int = 1) -> str:
    base_name = extract_base_name_from_xml(xml_path)
    fragments = extract_fragments_from_xml(xml_path)
    edges = extract_detailed_sequence(xml_path)
    
    objects = sorted(list(set([e['sender'] for e in edges] + [e['receiver'] for e in edges])))
    msg_instances = [f"{e['msg']}_{i}" for i, e in enumerate(edges, 1)]
    raw_messages = sorted(list(set([e['msg'] for e in edges])))
    data_messages = sorted(list(set([e['data'] for e in edges if e['data']])))
    
    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    
    # ---------------- Parsing Fragment Conditions ----------------
    frag_vars = {}
    for f in fragments:
        cond = f['condition']
        if cond:
            # ใช้ Regex จับตัวแปร เครื่องหมาย และตัวเลข (เช่น amount < 2000)
            match = re.search(r'([a-zA-Z0-9_]+)\s*(==|=|<=|>=|<|>)\s*([0-9]+)', cond)
            if match:
                frag_vars[match.group(1)] = {'op': match.group(2), 'val': match.group(3)}
            else:
                # กรณีเขียนมาแค่ Login (ไม่มีเครื่องหมาย)
                frag_vars[cond] = {'op': '=', 'val': '0'}
    
    # สร้างตัวแปร Default สำหรับ Loop และ Par 
    for f in fragments:
        if f['type'] == 'loop' and 'retry' not in frag_vars:
            frag_vars['retry'] = {'op': '=', 'val': '0'}
        elif f['type'] == 'par' and f['id'] not in frag_vars:
            frag_vars[f"par_{f['id'].replace('par', '')}"] = {'op': '=', 'val': '0'}

    # ---------------- VARIABLES ----------------
    base_vars = ["sentMessages", "sender", "receiver", "receivedMessages", 
                 "senderdataMessages", "currentMessage", "receiverdataMessages"]
    all_vars = base_vars + list(frag_vars.keys())
    
    # ---------------- INVARIANTS ----------------
    invs = [
        "inv1: sentMessages ⊆ Messages",
        "inv2: currentMessage ⊆ Messages",
        "inv3: sender ⊆ Messages × Objects",
        "inv4: receiver ⊆ Messages × Objects",
        "inv5: receivedMessages ⊆ sentMessages",
        "inv6: senderdataMessages ⊆ Messages × DataMessages",
        "inv7: receiverdataMessages ⊆ Messages × DataMessages"
    ]
    inv_idx = 8
    for v in frag_vars.keys():
        invs.append(f"inv{inv_idx}: {v} ∈ ℤ")
        inv_idx += 1
        
    # ---------------- INITIALISATION ----------------
    inits = [
        "act1: sentMessages := ∅",
        "act2: sender := ∅",
        "act3: receiver := ∅",
        "act4: receivedMessages := ∅",
        "act5: senderdataMessages := ∅",
        "act6: receiverdataMessages := ∅",
        "act7: currentMessage := ∅"
    ]
    act_idx = 8
    for v, details in frag_vars.items():
        op = details['op']
        val = details['val']
        # จัดการเงื่อนไข < หรือ <= ให้อยู่ในรูป Set :∈ 0..val
        if op in ['<', '<=']:
            inits.append(f"act{act_idx}: {v} :∈ 0..{val}")
        else:
            inits.append(f"act{act_idx}: {v} := {val}")
        act_idx += 1

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
    {", ".join(all_vars)}
INVARIANTS
    {"\n    ".join(invs)}
EVENTS
    INITIALISATION BEGIN
        {"\n        ".join(inits)}
    END

{generate_step_events(edges)}

END"""

# ===================== TKINTER UI =====================



class SequenceToEventBApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Sequence Diagram XML → Event-B & AI CTL")
        self.master.geometry("1360x820")
        
        # ==========================================
        #  NIKE MINIMALIST PALETTE (ขาว-ดำ-เทา)
        # ==========================================
        self.BG = "#FFFFFF"           
        self.PANEL = "#F7F7F7"        
        self.CARD = "#FFFFFF"         
        self.TEXT = "#111111"         
        self.MUTED = "#8D8D8D"        
        self.BORDER = "#EAEAEA"       
        
        self.CHAT_ME = "#111111"      
        self.CHAT_ME_FG = "#FFFFFF"
        self.CHAT_AI = "#F2F2F2"      
        self.CHAT_AI_FG = "#111111"

        self.FONT_H1 = ("Segoe UI", 16, "bold")
        self.FONT_UI = ("Segoe UI", 10)
        self.FONT_BOLD = ("Segoe UI", 10, "bold")
        self.FONT_SM = ("Segoe UI", 9)
        self.FONT_MONO = ("Consolas", 11)

        self.master.configure(bg=self.BG)
        self.current_xml_path = None
        self._chat_history = []

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_topbar()
        self._build_subheader()
        self._build_statusbar()
        
        body = tk.Frame(self.master, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._build_editor(body)
        tk.Frame(body, bg=self.BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self._build_chat(body)

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(self.master, bg=self.BG, height=60)
        bar.pack(fill=tk.X, padx=10, pady=5)
        bar.pack_propagate(False)

        logo = tk.Frame(bar, bg=self.BG)
        logo.pack(side=tk.LEFT, padx=10)
        tk.Label(logo, text="EVENT-B", font=self.FONT_H1, bg=self.BG, fg=self.TEXT).pack(side=tk.LEFT)
        tk.Label(logo, text=" STUDIO", font=("Segoe UI", 16), bg=self.BG, fg=self.MUTED).pack(side=tk.LEFT)

        tk.Frame(bar, bg=self.BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=15, padx=15)

        defs = [
            ("Choose XML", self.open_xml_file),
            ("Transform",  self.run_transform),
            ("Generate CTL", self.run_ai_ctl),
            ("Save",       self.save_output),
        ]
        
        for label, cmd in defs:
            b = ctk.CTkButton(
                bar, 
                text=label.upper(), 
                command=cmd,
                fg_color="#EEEEEE",      
                text_color="#111111",    
                hover_color="#DDDDDD",   
                corner_radius=18,        
                font=("Segoe UI", 12, "bold"),
                width=120,
                height=36,
                cursor="hand2"
            )
            b.pack(side=tk.LEFT, padx=6, pady=12)

        vf = tk.Frame(bar, bg=self.BG)
        vf.pack(side=tk.RIGHT, padx=10)
        tk.Label(vf, text="VERSION", bg=self.BG, fg=self.MUTED, font=self.FONT_SM).pack(side=tk.LEFT, padx=5)
        self.version_var = tk.IntVar(value=1)
        tk.Spinbox(vf, from_=1, to=99, textvariable=self.version_var, width=3,
                   bg=self.PANEL, fg=self.TEXT, buttonbackground=self.BORDER,
                   relief=tk.FLAT, font=self.FONT_UI).pack(side=tk.LEFT)

    # ── Subheader ─────────────────────────────────────────────────────────────
    def _build_subheader(self):
        sub = tk.Frame(self.master, bg=self.BG)
        sub.pack(fill=tk.X, padx=15, pady=(0, 5))
        
        guide_frame = ctk.CTkFrame(sub, fg_color=self.PANEL, corner_radius=10, height=36)
        guide_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        guide_frame.pack_propagate(False)
        
        steps_text = "WORKFLOW :   1. CHOOSE XML   ➔   2. TRANSFORM   ➔   3. GENERATE CTL"
        tk.Label(guide_frame, text=steps_text, bg=self.PANEL, fg=self.MUTED, font=self.FONT_SM).pack(side=tk.LEFT, padx=15, pady=8)

        self.lbl_top_file = tk.Label(guide_frame, text="📄 NO FILE SELECTED", bg=self.PANEL, fg=self.MUTED, font=self.FONT_BOLD)
        self.lbl_top_file.pack(side=tk.RIGHT, padx=15, pady=8)

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self.master, bg=self.PANEL, height=30)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self.lbl_file = tk.Label(bar, text=" WAITING FOR FILE...",
                                 bg=self.PANEL, fg=self.MUTED, font=self.FONT_SM, anchor="w")
        self.lbl_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.lbl_objects = tk.Label(bar, text="", bg=self.PANEL, fg=self.TEXT, font=self.FONT_SM, anchor="e")
        self.lbl_objects.pack(side=tk.RIGHT, padx=15)

    # ── Left: editor (ปรับให้มี 2 กล่อง แบ่งด้วย PanedWindow) ─────────────────
    def _build_editor(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ใช้ PanedWindow เพื่อให้ลากปรับขนาดกล่องบน/ล่างได้
        paned = tk.PanedWindow(frame, orient=tk.VERTICAL, bg=self.BORDER, sashwidth=5, bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        # ====== กล่องบน (EVENT-B OUTPUT) ======
        top_frame = tk.Frame(paned, bg=self.BG)
        
        hdr1 = tk.Frame(top_frame, bg=self.BG)
        hdr1.pack(fill=tk.X, pady=(0, 5))
        tk.Label(hdr1, text="EVENT-B OUTPUT", bg=self.BG, fg=self.TEXT, font=self.FONT_BOLD).pack(side=tk.LEFT)

        wrap1 = tk.Frame(top_frame, bg=self.BORDER, bd=1)
        wrap1.pack(fill=tk.BOTH, expand=True)

        self.text_output = tk.Text(
            wrap1, wrap=tk.NONE, font=self.FONT_MONO,
            bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT,
            selectbackground=self.MUTED, selectforeground=self.BG,
            relief=tk.FLAT, bd=0, padx=20, pady=20, undo=True)

        vsb1 = tk.Scrollbar(wrap1, orient=tk.VERTICAL, command=self.text_output.yview, bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        hsb1 = tk.Scrollbar(wrap1, orient=tk.HORIZONTAL, command=self.text_output.xview, bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        self.text_output.configure(yscrollcommand=vsb1.set, xscrollcommand=hsb1.set)
        
        vsb1.pack(side=tk.RIGHT, fill=tk.Y)
        hsb1.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_output.pack(fill=tk.BOTH, expand=True)
        
        paned.add(top_frame, minsize=200)

        # ====== กล่องล่าง (AI CTL OUTPUT) ======
        bot_frame = tk.Frame(paned, bg=self.BG)
        
        hdr2 = tk.Frame(bot_frame, bg=self.BG)
        hdr2.pack(fill=tk.X, pady=(10, 5))
        tk.Label(hdr2, text="AI CTL OUTPUT", bg=self.BG, fg=self.TEXT, font=self.FONT_BOLD).pack(side=tk.LEFT)

        wrap2 = tk.Frame(bot_frame, bg=self.BORDER, bd=1)
        wrap2.pack(fill=tk.BOTH, expand=True)

        # สร้างตัวแปรใหม่สำหรับ AI
        self.text_ctl = tk.Text(
            wrap2, wrap=tk.NONE, font=self.FONT_MONO,
            bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT,
            selectbackground=self.MUTED, selectforeground=self.BG,
            relief=tk.FLAT, bd=0, padx=20, pady=20, undo=True)

        vsb2 = tk.Scrollbar(wrap2, orient=tk.VERTICAL, command=self.text_ctl.yview, bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        hsb2 = tk.Scrollbar(wrap2, orient=tk.HORIZONTAL, command=self.text_ctl.xview, bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        self.text_ctl.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)
        hsb2.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_ctl.pack(fill=tk.BOTH, expand=True)
        
        paned.add(bot_frame, minsize=150)

    # ── Right: chat panel ─────────────────────────────────────────────────────
    def _build_chat(self, parent):
        frame = tk.Frame(parent, bg=self.BG, width=400)
        frame.pack(side=tk.RIGHT, fill=tk.Y)
        frame.pack_propagate(False)

        hdr = tk.Frame(frame, bg=self.BG, height=38)
        hdr.pack(fill=tk.X, pady=(0, 5))
        hdr.pack_propagate(False)
        
        tk.Label(hdr, text="AI EVENT-B CHAT", bg=self.BG, fg=self.TEXT,
                 font=self.FONT_BOLD).pack(side=tk.LEFT)
                 
        ctk.CTkButton(
            hdr, text="CLEAR", command=self._clear_chat,
            fg_color="transparent", text_color=self.MUTED, hover_color=self.BORDER,
            corner_radius=10, font=("Segoe UI", 10), width=60, height=28, cursor="hand2"
        ).pack(side=tk.RIGHT)

        self._model_var = tk.StringVar(value="gemma2:2b")

        msg_wrap = tk.Frame(frame, bg=self.CARD)
        msg_wrap.pack(fill=tk.BOTH, expand=True)

        self._chat_canvas = tk.Canvas(msg_wrap, bg=self.CARD, highlightthickness=0)
        csb = tk.Scrollbar(msg_wrap, orient=tk.VERTICAL, command=self._chat_canvas.yview,
                           bg=self.CARD, troughcolor=self.CARD, relief=tk.FLAT, bd=0)
        self._chat_canvas.configure(yscrollcommand=csb.set)
        csb.pack(side=tk.RIGHT, fill=tk.Y)
        self._chat_canvas.pack(fill=tk.BOTH, expand=True)

        self._chat_inner = tk.Frame(self._chat_canvas, bg=self.CARD)
        self._chat_win = self._chat_canvas.create_window((0, 0), window=self._chat_inner, anchor="nw")
        
        self._chat_inner.bind("<Configure>", lambda e: self._chat_canvas.configure(scrollregion=self._chat_canvas.bbox("all")))
        self._chat_canvas.bind("<Configure>", lambda e: self._chat_canvas.itemconfig(self._chat_win, width=e.width))

        inp = tk.Frame(frame, bg=self.BG, pady=10)
        inp.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Frame(inp, bg=self.BORDER, height=1).pack(fill=tk.X, pady=(0, 10))

        self._chat_input = ctk.CTkTextbox(
            inp, 
            height=70,             
            wrap="word",
            fg_color=self.PANEL,   
            text_color=self.TEXT,  
            font=self.FONT_UI,
            corner_radius=15,      
            border_width=0
        )
        self._chat_input.pack(fill=tk.X, padx=5)
        
        self._chat_input.bind("<Return>", self._on_enter)
        self._chat_input.bind("<Shift-Return>", lambda e: None)

        btn_row = tk.Frame(inp, bg=self.BG)
        btn_row.pack(fill=tk.X, pady=(10, 0))
        
        self._btn_send = ctk.CTkButton(
            btn_row, text="SEND", command=self._send_chat,
            fg_color="#111111", text_color="#FFFFFF", hover_color="#333333",
            corner_radius=18, font=("Segoe UI", 12, "bold"), width=90, height=34, cursor="hand2"
        )
        self._btn_send.pack(side=tk.RIGHT)
        
        tk.Label(btn_row, text="Shift+Enter for newline", bg=self.BG, fg=self.MUTED,
                 font=self.FONT_SM).pack(side=tk.RIGHT, padx=10)

    # ══════════════════════════════════════════════════════════════════════════
    #  LOGIC
    # ══════════════════════════════════════════════════════════════════════════

    def _on_enter(self, event):
        if not (event.state & 0x1): 
            self._send_chat()
            return "break"

    def _send_chat(self):
        msg = self._chat_input.get("1.0", tk.END).strip()
        if not msg: return
        self._chat_input.delete("1.0", tk.END)
        self._add_bubble("user", msg)
        self._chat_history.append({"role": "user", "content": msg})
        self._btn_send.configure(state="disabled")
        import threading
        threading.Thread(target=self._ollama_worker, daemon=True).start()

    def _ollama_worker(self):
        try:
            client = ollama.Client(host="http://127.0.0.1:11434")
            resp = client.chat(model=self._model_var.get(), messages=self._chat_history)
            text = resp["message"]["content"]
            self._chat_history.append({"role": "assistant", "content": text})
            self.master.after(0, lambda: self._add_bubble("assistant", text))
        except Exception as e:
            self.master.after(0, lambda: self._add_bubble("assistant", f"Error: {e}"))
        finally:
            self.master.after(0, lambda: self._btn_send.configure(state="normal"))

    def _add_bubble(self, role: str, text: str):
        is_user = role == "user"
        outer = tk.Frame(self._chat_inner, bg=self.CARD)
        outer.pack(fill=tk.X, padx=5, pady=8)

        bg_color = self.CHAT_ME if is_user else self.CHAT_AI
        fg_color = self.CHAT_ME_FG if is_user else self.CHAT_AI_FG

        bubble = ctk.CTkFrame(outer, fg_color=bg_color, corner_radius=15)
        bubble.pack(side=tk.RIGHT if is_user else tk.LEFT,
                    anchor="e" if is_user else "w",
                    padx=(40, 0) if is_user else (0, 40))

        lbl_name = "YOU" if is_user else "EVENT-B AI"
        name_fg = self.MUTED if is_user else self.TEXT

        ctk.CTkLabel(bubble, text=lbl_name, text_color=name_fg, fg_color="transparent",
                     font=self.FONT_SM).pack(anchor="w", padx=15, pady=(8, 0))
        ctk.CTkLabel(bubble, text=text, text_color=fg_color, fg_color="transparent",
                     font=self.FONT_UI, wraplength=260, justify="left"
                     ).pack(anchor="w", padx=15, pady=(0, 10))

        self._chat_canvas.update_idletasks()
        self._chat_canvas.yview_moveto(1.0)

    def _clear_chat(self):
        for w in self._chat_inner.winfo_children(): w.destroy()
        self._chat_history.clear()

    def open_xml_file(self):
        path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if path:
            self.current_xml_path = path
            filename = os.path.basename(path)
            
            self.lbl_file.config(text=f" FILE: {filename}", fg=self.TEXT)
            self.lbl_top_file.config(text=f"📄 SELECTED : {filename}", fg=self.TEXT)
            
            obj = extract_objects_from_xml(path)
            msg, data = extract_messages_from_xml(path)
            self.lbl_objects.config(text=f"{len(obj)} OBJ  |  {len(msg)} MSG  |  {len(data)} DATA")

    def run_transform(self):
        if not self.current_xml_path: return
        res = apply_rules_1_and_2(self.current_xml_path, self.version_var.get())
        
        # ปริ้นลงกล่อง Event-B (กล่องบน)
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, res)

    def run_ai_ctl(self):
        if not self.current_xml_path: return
        
        # ปริ้นลงกล่อง AI CTL (กล่องล่าง)
        self.text_ctl.delete("1.0", tk.END)
        self.text_ctl.insert(tk.END, "Analyzing CTL properties with AI...\n\n")
        self.master.update_idletasks()
        try:
            base = extract_base_name_from_xml(self.current_xml_path)
            msgs, _ = extract_messages_from_xml(self.current_xml_path)
            prompt = (f"System: {base}\nMessages: {msgs}\n"
                      "Generate 3 CTL formulas for ProB. Use 'sentMessages' variable. "
                      "Format: AG({msg} <: sentMessages -> AF({msg2} <: sentMessages)). "
                      "Add Thai explanation.")
            client = ollama.Client(host="http://127.0.0.1:11434")
            response = client.chat(model="gemma2:2b", messages=[{"role": "user", "content": prompt}])
            
            self.text_ctl.insert(tk.END, response["message"]["content"])
        except Exception as e:
            self.text_ctl.insert(tk.END, f"\n AI Error: {e}")
            
        self.text_ctl.see(tk.END)

    def save_output(self):
        # ดึงข้อมูลจากทั้ง 2 กล่องมารวมกันตอนเซฟ
        eventb_text = self.text_output.get("1.0", tk.END).strip()
        ctl_text = self.text_ctl.get("1.0", tk.END).strip()
        
        content = ""
        if eventb_text:
            content += f"================ EVENT-B MACHINE ================\n{eventb_text}\n\n"
        if ctl_text:
            content += f"================ AI CTL PROPERTIES ================\n{ctl_text}\n"

        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path and content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)


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

    ตอบกลับเป็นภาษาไทยเท่านั้น และใช้คำอธิบายที่เข้าใจง่ายสำหรับผู้เริ่มต้น ไม่ต้องใช้สัญลักษณ์ในการเรียงลำดับอธิบาย ใช้แค่ - หรือ ตัวเลขก็พอ
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

# def patched_init(self, master):
#     # เรียกใช้ __init__ เดิมก่อนเพื่อให้หน้าจอหลักถูกสร้าง
#     original_init(self, master)
    
#     # หาปุ่มใน top_frame เพื่อเพิ่มปุ่มใหม่ต่อท้าย
#     # เราจะหา Frame แรกที่เจอใน master
#     for widget in master.winfo_children():
#         if isinstance(widget, tk.Frame):
#             self.btn_ai = tk.Button(
#                 widget,
#                 text="สร้าง CTL (Ollama)",
#                 command=self.run_ai_ctl,
#                 bg="#9C27B0", # สีม่วง
#                 fg="black",
#                 padx=10,
#                 pady=5
#             )
#             self.btn_ai.pack(side=tk.LEFT, padx=10)
#             break

def run_ai_ctl(self):
    if not self.current_xml_path:
        messagebox.showwarning("เตือน", "กรุณาเลือกไฟล์ XML ก่อน")
        return
        
    # เคลียร์ข้อความเก่าในกล่องล่างทิ้งก่อน (จะได้ไม่งงเวลาเจาะหลายรอบ)
    self.text_ctl.delete("1.0", tk.END)
    
    # เปลี่ยนเป็น self.text_ctl ให้ชี้ไปที่กล่องล่าง
    self.text_ctl.insert(tk.END, "\n" + "="*50 + "\n")
    self.text_ctl.insert(tk.END, "กำลังส่งข้อมูลให้ Ollama วิเคราะห์ CTL...\n")
    self.text_ctl.see(tk.END)
    self.master.update_idletasks()
    
    try:
        base_name = extract_base_name_from_xml(self.current_xml_path)
        objects = extract_objects_from_xml(self.current_xml_path)
        messages, _ = extract_messages_from_xml(self.current_xml_path)
        
        ctl_result = generate_ctl_with_ollama(base_name, objects, messages)
        
        self.text_ctl.insert(tk.END, f"\n✨ [AI Generated CTL Properties]:\n{ctl_result}\n")
        self.text_ctl.insert(tk.END, "="*50 + "\n")
        self.text_ctl.see(tk.END)
    except Exception as e:
        messagebox.showerror("AI Error", str(e))
        
# นำฟังก์ชันใหม่ไปสวมแทนที่ของเดิมใน Class
# SequenceToEventBApp.__init__ = patched_init
SequenceToEventBApp.run_ai_ctl = run_ai_ctl
# ==========================================================


def main():
    root = tk.Tk()
    app = SequenceToEventBApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()


