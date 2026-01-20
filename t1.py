import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import xml.etree.ElementTree as ET
import zipfile
import tempfile

# ===================== DOMAIN LOGIC =====================

def to_pascal_case(name: str) -> str:
    """แปลง string เป็น PascalCase"""
    if not name:
        return "System"
    parts = re.split(r"[^A-Za-z0-9]+", name)
    parts = [p for p in parts if p]
    if not parts:
        return "System"
    return "".join(p[0].upper() + p[1:] for p in parts)

def extract_base_name_from_xml(xml_path: str) -> str:
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for elem in root.iter():
            if elem.tag == 'diagram':
                name = elem.get('name')
                if name and name != 'หน้า-1':
                    return to_pascal_case(name)
        name = root.get("name")
        if not name:
            for elem in root.iter():
                if "name" in elem.attrib:
                    name = elem.attrib["name"]
                    if name and name != 'หน้า-1':
                        break
        if not name or name == 'หน้า-1':
            filename = os.path.basename(xml_path)
            name, _ = os.path.splitext(filename)
        return to_pascal_case(name)
    except Exception as e:
        raise RuntimeError(f"อ่าน XML ไม่ได้: {e}")

def extract_objects_from_xml(xml_path: str) -> list:
    """ดึงรายชื่อ Objects (Lifelines)"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        objects = set()
        for elem in root.iter():
            style = elem.get('style', '')
            if 'umlLifeline' in style:
                value = elem.get('value', '')
                if value:
                    if ':' in value:
                        parts = value.split(':')
                        class_name = parts[-1].strip()
                        if class_name:
                            objects.add(class_name)
                    else:
                        objects.add(value.strip())
        return sorted(list(objects))
    except Exception as e:
        raise RuntimeError(f"ดึง objects จาก XML ไม่ได้: {e}")

def extract_messages_and_data(xml_path: str) -> tuple:
    """
    ดึง Messages และ DataMessages
    แก้ไข: นับ Return Message (เส้นประ) เป็น Messages ด้วย ไม่ว่าจะตัวเล็กหรือใหญ่
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        messages = set()
        data_messages = set()
        
        for elem in root.iter():
            # เช็คว่าเป็นเส้น (edge="1") หรือดูจาก style
            is_edge = elem.get('edge') == '1'
            value = elem.get('value', '')
            
            if is_edge and value:
                # Clean HTML tags
                clean_value = re.sub(r'<[^>]*>', '', value).strip()
                if not clean_value: continue

                # กรณีมีวงเล็บ: Message(Data)
                if '(' in clean_value and ')' in clean_value:
                    match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', clean_value)
                    if match:
                        msg_name = match.group(1).strip()
                        params = match.group(2).strip()
                        
                        # ส่วนหน้าวงเล็บ -> Messages
                        messages.add(msg_name)
                        
                        # ส่วนในวงเล็บ -> DataMessages
                        if params:
                            for param in params.split(','):
                                p = param.strip()
                                if p: data_messages.add(p)
                
                # กรณีไม่มีวงเล็บ (เช่น paymentDetails, return, ACK)
                else:
                    # Logic ใหม่: ถือเป็น Message เสมอ (รวมถึง Return Message)
                    # ไม่สนใจว่าเป็นตัวเล็กหรือใหญ่
                    # แต่ถ้าอยากกรองคำว่า return ทิ้ง หรือจัดการพิเศษ สามารถทำตรงนี้ได้
                    if clean_value:
                        messages.add(clean_value)
                        
        return sorted(list(messages)), sorted(list(data_messages))
        
    except Exception as e:
        print(f"Error extracting messages: {e}")
        return [], []
    

    """
    ดึง Sequence Flow พร้อมจับคู่เงื่อนไข (Guard) ให้แม่นยำขึ้น
    รองรับทั้ง:
    1. Text floating over Frame (Spatial check)
    2. Text inside Frame (Parent check)
    3. Condition embedded in Frame value
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # --- 1. เตรียมข้อมูล Lifelines (เหมือนเดิม) ---
        lifelines = []
        # สร้าง Map ID -> Element เพื่อใช้ lookup parent
        id_to_elem = {e.get('id'): e for e in root.iter()}
        
        for elem in root.iter():
            eid = elem.get('id')
            style = elem.get('style', '')
            value = elem.get('value', '')
            
            is_lifeline = 'umlLifeline' in style or 'participant' in style
            is_actor = 'shape=umlActor' in style
            
            if (is_lifeline or is_actor) and value:
                name = value
                if ':' in name: name = name.split(':')[-1]
                name = re.sub(r'<[^>]*>', '', name).strip()
                
                geom = elem.find('mxGeometry')
                if geom is not None:
                    try:
                        x = float(geom.get('x', 0))
                        w = float(geom.get('width', 0))
                        center_x = x + (w / 2)
                        lifelines.append({'id': eid, 'name': name, 'center_x': center_x})
                    except: pass

        def find_closest_lifeline(target_x):
            if not lifelines: return "Unknown"
            closest = None
            min_dist = float('inf')
            for lf in lifelines:
                dist = abs(lf['center_x'] - target_x)
                if dist < min_dist:
                    min_dist = dist
                    closest = lf['name']
            return closest if min_dist < 100 else "Unknown"

        def get_name_by_id(node_id):
            for lf in lifelines:
                if lf['id'] == node_id: return lf['name']
            return None
            
        def get_absolute_geometry(elem):
            """คำนวณพิกัดจริง (Absolute) โดยบวกพิกัด Parent เข้าไปเรื่อยๆ"""
            try:
                geom = elem.find('mxGeometry')
                if geom is None: return 0, 0, 0, 0
                
                x = float(geom.get('x', 0))
                y = float(geom.get('y', 0))
                w = float(geom.get('width', 0))
                h = float(geom.get('height', 0))
                
                # ถ้าเป็น Child ให้บวกพิกัด Parent
                parent_id = elem.get('parent')
                while parent_id and parent_id != '1' and parent_id != '0':
                    parent = id_to_elem.get(parent_id)
                    if parent is not None:
                        p_geom = parent.find('mxGeometry')
                        if p_geom is not None:
                            x += float(p_geom.get('x', 0))
                            y += float(p_geom.get('y', 0))
                    parent_id = parent.get('parent') if parent else None
                
                return x, y, w, h
            except:
                return 0, 0, 0, 0

        # --- 2. ค้นหา Frames (OPT, ALT) ---
        frames = []
        frag_counter = 1
        for elem in root.iter():
            style = elem.get('style', '')
            value = elem.get('value', '') or ''
            eid = elem.get('id')
            
            if 'umlFrame' in style:
                clean_val = re.sub(r'<[^>]*>', '', value).strip()
                
                # ตรวจสอบว่าเงื่อนไขฝังอยู่ในชื่อกรอบหรือไม่? (Case 3)
                # เช่น "opt [Login=1]"
                embedded_cond = None
                match = re.search(r'\[(.*?)\]', clean_val)
                if match:
                    embedded_cond = match.group(1).strip().replace('==', '=').replace(':=', '=')
                
                # กำหนด Suffix
                clean_lower = clean_val.lower()
                suffix = ""
                if clean_lower.startswith('opt'): suffix = f"_opt{frag_counter}"
                elif clean_lower.startswith('alt'): suffix = f"_alt{frag_counter}"
                elif clean_lower.startswith('loop'): suffix = f"_loop{frag_counter}"
                elif clean_lower.startswith('par'): suffix = f"_par{frag_counter}"
                
                if suffix:
                    # ใช้ Absolute Geometry เพื่อความชัวร์
                    fx, fy, fw, fh = get_absolute_geometry(elem)
                    
                    frames.append({
                        'id': eid,
                        'y_start': fy,
                        'y_end': fy + fh,
                        'x_start': fx,
                        'x_end': fx + fw,
                        'suffix': suffix,
                        'condition': embedded_cond # ถ้ามีก็ใส่เลย
                    })
                    frag_counter += 1

        # --- 3. ค้นหา Text Condition [...] (Floating or Child) ---
        for elem in root.iter():
            value = elem.get('value', '')
            style = elem.get('style', '')
            eid = elem.get('id')
            parent_id = elem.get('parent')
            
            # ข้ามถ้าเป็น Frame (เพราะดูไปแล้ว) หรือไม่มี [...]
            if 'umlFrame' in style: continue
            
            clean_val = re.sub(r'<[^>]*>', '', value).strip()
            match = re.search(r'\[(.*?)\]', clean_val)
            
            if match:
                raw_cond = match.group(1).strip()
                condition = raw_cond.replace('==', '=').replace(':=', '=')
                
                # Case 1: เป็น Child ของ Frame โดยตรง
                parent_frame = next((f for f in frames if f['id'] == parent_id), None)
                if parent_frame:
                    if not parent_frame['condition']: # ถ้ายังไม่มีเงื่อนไข ให้ใส่เข้าไป
                         parent_frame['condition'] = condition
                    continue
                
                # Case 2: เป็นข้อความลอย (Spatial Check)
                tx, ty, tw, th = get_absolute_geometry(elem)
                
                # หา Frame ที่ "ครอบ" ข้อความนี้อยู่
                for frame in frames:
                    # เงื่อนไข: ข้อความต้องอยู่ในกรอบ หรือ อยู่ตรงหัวมุมกรอบ
                    # (ยอมให้ Text Y น้อยกว่า Frame Y ได้นิดหน่อย เผื่อวางเหลื่อม)
                    if (frame['x_start'] <= tx <= frame['x_end']) and \
                       (frame['y_start'] - 20 <= ty <= frame['y_end']):
                        
                        if not frame['condition']:
                            frame['condition'] = condition
                        break

        # --- 4. หา Message Flows และ Match กับ Frame (Logic เดิม) ---
        flows = []
        for elem in root.iter():
            if elem.get('edge') == '1':
                value = elem.get('value', '')
                msg_name = re.sub(r'<[^>]*>', '', value).strip()
                if not msg_name: continue
                
                source_name, target_name = None, None
                src_id, trg_id = elem.get('source'), elem.get('target')
                
                if src_id: source_name = get_name_by_id(src_id)
                if trg_id: target_name = get_name_by_id(trg_id)
                
                # หา Absolute Y ของ Message
                geom = elem.find('mxGeometry')
                y_coord = 0
                
                if geom is not None:
                    # พยายามหาจาก sourcePoint
                    points_list = geom.findall('mxPoint')
                    src_pt = None
                    trg_pt = None
                    for pt in points_list:
                        if pt.get('as') == 'sourcePoint': src_pt = pt
                        if pt.get('as') == 'targetPoint': trg_pt = pt
                    
                    if not source_name and src_pt is not None:
                        # mxPoint ใน edge มักจะเป็น relative ถ้า parent != 1
                        # แต่สำหรับ Edge ปกติ parent มักเป็น 1
                        # เพื่อความชัวร์ ใช้ค่าดิบไปก่อน ถ้า parent=1
                        sx = float(src_pt.get('x', 0))
                        sy = float(src_pt.get('y', 0))
                        source_name = find_closest_lifeline(sx)
                        y_coord = sy
                        
                    if not target_name and trg_pt is not None:
                        tx = float(trg_pt.get('x', 0))
                        target_name = find_closest_lifeline(tx)
                    
                    if y_coord == 0 and src_pt: y_coord = float(src_pt.get('y', 0))

                if not source_name or source_name == "Unknown": continue
                if not target_name: target_name = "Unknown" 

                # แยก Param
                data_param = None
                if '(' in msg_name:
                    match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', msg_name)
                    if match:
                        msg_name = match.group(1).strip()
                        raw_params = match.group(2).strip()
                        if raw_params: data_param = raw_params.split(',')[0].strip()

                # --- Match Frame ---
                current_suffix = ""
                current_condition = None
                
                # หา Frame ที่ Message นี้อยู่ข้างใน (เอาตัวที่เล็กที่สุด หรือล่าสุด)
                for frag in frames:
                    if frag['y_start'] <= y_coord <= frag['y_end']:
                        current_suffix = frag['suffix']
                        current_condition = frag['condition']
                        # ไม่ break เพื่อรองรับ Nested Frame (เอาตัวในสุด)

                flows.append({
                    'msg': msg_name,
                    'from': source_name,
                    'to': target_name,
                    'data': data_param,
                    'y': y_coord,
                    'opt_suffix': current_suffix,
                    'guard_cond': current_condition
                })
        
        return sorted(flows, key=lambda x: x['y'])
        
    except Exception as e:
        print(f"Extract Error: {e}")
        return []



def extract_sequence_from_xml(xml_path: str) -> list:
    """
    Fixed Logic (Final Version 2):
    1.  Detection Fix: ตรวจจับ Frame จาก 'Value' (opt, alt) ด้วย ไม่ใช่แค่ Style
        (รองรับทั้ง umlFrame, sysml.package หรือกล่องสี่เหลี่ยมธรรมดาที่พิมพ์ว่า opt)
    2.  Absolute Geometry: คำนวณพิกัดจริงแม่นยำ
    3.  Text Mapping: จับคู่เงื่อนไข [Condition] เข้ากับกล่อง
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        id_to_elem = {e.get('id'): e for e in root.iter()}

        # --- Helper: คำนวณพิกัดจริง (Absolute) ---
        def get_abs_geom(elem):
            try:
                geom = elem.find('mxGeometry')
                if geom is None: return None
                
                x = float(geom.get('x', 0))
                y = float(geom.get('y', 0))
                w = float(geom.get('width', 0))
                h = float(geom.get('height', 0))
                
                curr_parent_id = elem.get('parent')
                while curr_parent_id and curr_parent_id != '1' and curr_parent_id != '0':
                    parent_node = id_to_elem.get(curr_parent_id)
                    if parent_node is not None:
                        p_geom = parent_node.find('mxGeometry')
                        if p_geom is not None:
                            x += float(p_geom.get('x', 0))
                            y += float(p_geom.get('y', 0))
                    if parent_node is not None:
                        curr_parent_id = parent_node.get('parent')
                    else:
                        break
                return {'x': x, 'y': y, 'w': w, 'h': h}
            except:
                return None

        # ==========================================
        # PHASE 1: สร้าง Array เก็บ Scopes (Frames)
        # ==========================================
        fragment_scopes = []
        frag_counter = 1
        
        # 1.1 หา Frame ทั้งหมด (แก้ไขจุดที่มองไม่เห็น opt)
        for elem in root.iter():
            # ต้องเป็น Vertex (Shape) เท่านั้น ไม่ใช่เส้น (Edge)
            if elem.get('vertex') != '1': continue
            
            style = elem.get('style', '')
            value = elem.get('value', '') or ''
            clean_val = re.sub(r'<[^>]*>', '', value).strip().lower()
            
            # --- FIX: ตรวจสอบว่าเป็น Frame หรือไม่ ---
            # 1. เช็คจาก Style (เดิม)
            is_frame_style = 'umlFrame' in style or 'sysml.package' in style
            # 2. เช็คจากคำขึ้นต้น (ใหม่ - ครอบคลุมกว่า)
            is_frame_label = clean_val.startswith(('opt', 'alt', 'loop', 'par', 'break'))
            
            # ถ้าเข้าเกณฑ์ข้อใดข้อหนึ่ง ให้ถือว่าเป็น Frame
            if is_frame_style or is_frame_label:
                suffix = ""
                if clean_val.startswith('opt'): suffix = f"_opt{frag_counter}"
                elif clean_val.startswith('alt'): suffix = f"_alt{frag_counter}"
                elif clean_val.startswith('loop'): suffix = f"_loop{frag_counter}"
                elif clean_val.startswith('par'): suffix = f"_par{frag_counter}"
                elif clean_val.startswith('break'): suffix = f"_break{frag_counter}"
                
                # ถ้า Style เป็น Frame แต่ Label ว่างเปล่า หรือเขียนชื่ออื่น ให้ default เป็น opt ไว้ก่อน
                if not suffix and is_frame_style:
                     suffix = f"_opt{frag_counter}" 

                if suffix:
                    abs_geom = get_abs_geom(elem)
                    if abs_geom:
                        embedded_cond = None
                        match = re.search(r'\[(.*?)\]', value)
                        if match:
                            embedded_cond = match.group(1).strip().replace('==', '=').replace(':=', '=')

                        fragment_scopes.append({
                            'id': elem.get('id'),
                            'type': suffix,
                            'y_start': abs_geom['y'],
                            'y_end': abs_geom['y'] + abs_geom['h'],
                            'x_start': abs_geom['x'],
                            'x_end': abs_geom['x'] + abs_geom['w'],
                            'height': abs_geom['h'],
                            'condition': embedded_cond
                        })
                        frag_counter += 1

        # 1.2 หา Text Conditions [...] แล้ว Map เข้า Scope
        for elem in root.iter():
            if elem.get('vertex') != '1': continue
            
            value = elem.get('value', '')
            clean_val = re.sub(r'<[^>]*>', '', value).strip()
            
            # ข้ามถ้าตัวเองเป็น Frame อยู่แล้ว (ป้องกัน Loop ตัวเอง)
            if clean_val.lower().startswith(('opt', 'alt', 'loop', 'par')): continue

            match = re.search(r'\[(.*?)\]', clean_val)
            if match:
                raw_cond = match.group(1).strip().replace('==', '=').replace(':=', '=')
                abs_geom = get_abs_geom(elem)
                
                if abs_geom:
                    tx, ty = abs_geom['x'], abs_geom['y']
                    
                    # Parent Check
                    parent_id = elem.get('parent')
                    matched = False
                    for scope in fragment_scopes:
                        if scope['id'] == parent_id:
                            if not scope['condition']: 
                                scope['condition'] = raw_cond
                            matched = True
                            break
                    if matched: continue

                    # Spatial Check (แก้ให้แม่นยำขึ้นสำหรับ Text ลอย)
                    for scope in fragment_scopes:
                        # ยอมให้ Text ลอยเหนือหัวกล่องได้นิดหน่อย (-40) และต้องอยู่ในช่วงความกว้าง
                        if (scope['x_start'] <= tx <= scope['x_end']) and \
                           (scope['y_start'] - 40 <= ty <= scope['y_end']):
                            
                            # ถ้ากล่องยังไม่มีเงื่อนไข ใส่เลย
                            if not scope['condition']: 
                                scope['condition'] = raw_cond
                                break

        # ==========================================
        # PHASE 2: เตรียม Lifelines
        # ==========================================
        lifelines = []
        for elem in root.iter():
            style = elem.get('style', '')
            value = elem.get('value', '')
            if ('umlLifeline' in style or 'participant' in style or 'shape=umlActor' in style) and value:
                name = value.split(':')[-1]
                name = re.sub(r'<[^>]*>', '', name).strip()
                abs_geom = get_abs_geom(elem)
                if abs_geom:
                    lifelines.append({
                        'name': name, 
                        'center_x': abs_geom['x'] + abs_geom['w']/2
                    })
                    
        def find_closest_lifeline(target_x):
            if not lifelines: return "Unknown"
            closest, min_dist = "Unknown", float('inf')
            for lf in lifelines:
                dist = abs(lf['center_x'] - target_x)
                if dist < min_dist:
                    min_dist = dist; closest = lf['name']
            if min_dist > 150: return "Unknown"
            return closest

        # ==========================================
        # PHASE 3: Match Messages
        # ==========================================
        flows = []
        for elem in root.iter():
            if elem.get('edge') == '1':
                value = elem.get('value', '')
                msg_name = re.sub(r'<[^>]*>', '', value).strip()
                if not msg_name: continue
                
                geom = elem.find('mxGeometry')
                src_x, trg_x, y_coord = 0, 0, 0
                source_name, target_name = None, None
                
                if geom is not None:
                    src_pt = next((pt for pt in geom.findall('mxPoint') if pt.get('as')=='sourcePoint'), None)
                    trg_pt = next((pt for pt in geom.findall('mxPoint') if pt.get('as')=='targetPoint'), None)
                    
                    if src_pt is not None:
                        src_x = float(src_pt.get('x', 0))
                        y_coord = float(src_pt.get('y', 0))
                        source_name = find_closest_lifeline(src_x)
                    
                    if trg_pt is not None:
                        trg_x = float(trg_pt.get('x', 0))
                        target_name = find_closest_lifeline(trg_x)
                
                if not source_name or source_name == "Unknown": continue
                if not target_name: target_name = "Unknown"
                
                # Param Extraction
                data_param = None
                if '(' in msg_name:
                    m = re.match(r'([a-zA-Z0-9_]+)\((.*?)\)', msg_name)
                    if m: msg_name, data_param = m.group(1), m.group(2).split(',')[0].strip()

                # --- Scope Matching ---
                matched_suffix = ""
                matched_condition = None
                min_scope_height = float('inf')
                
                for scope in fragment_scopes:
                    # เช็คว่า Message อยู่ในแนวตั้งของ Scope นี้หรือไม่
                    if scope['y_start'] <= y_coord <= scope['y_end']:
                        if scope['height'] < min_scope_height:
                            min_scope_height = scope['height']
                            matched_suffix = scope['type']
                            matched_condition = scope['condition']
                
                flows.append({
                    'msg': msg_name, 'from': source_name, 'to': target_name,
                    'data': data_param, 'y': y_coord,
                    'opt_suffix': matched_suffix,
                    'guard_cond': matched_condition
                })
                
        return sorted(flows, key=lambda x: x['y'])
        
    except Exception as e:
        print(f"Error extracting sequence: {e}")
        import traceback
        traceback.print_exc()
        return []


def generate_events(sequence: list) -> str:
    """
    สร้าง EVENTS ของ Event-B
    - แก้ไข: Guard Condition ใช้ Index รันต่อเนื่อง (grd3, grd4...) แทนชื่อ grd_logic
    """
    events_text = []
    
    for idx, flow in enumerate(sequence):
        seq_id = idx + 1
        msg_name = flow['msg']
        sender = flow['from']
        receiver = flow['to']
        data = flow['data']
        
        # ดึงค่า Suffix และ Condition
        suffix = flow.get('opt_suffix', '')
        condition = flow.get('guard_cond') 
        
        msg_instance = f"{msg_name}_{seq_id}"
        
        # ==================================================
        # 1. SEND EVENT
        # ==================================================
        
        # เริ่มต้นมี 2 Guards เสมอ
        send_guards = [
            f"grd1: {msg_instance} /: sentMessages",
            f"grd2: currentMessage = {{}}"
        ]
        
        # ถ้ามีเงื่อนไข ให้เพิ่มเป็น grd3 (หรือเลขถัดไป)
        if condition:
            clean_cond = condition.strip()
            # คำนวณ index ถัดไปอัตโนมัติ (เช่น มี 2 ตัวแล้ว ตัวต่อไปคือ 3)
            next_idx = len(send_guards) + 1
            send_guards.append(f"grd{next_idx}: {clean_cond}")

        # เตรียม Actions
        send_actions = [
            f"act1: sentMessages := sentMessages \\/ {{{msg_instance}}}",
            f"act2: sender := sender \\/ {{{msg_instance} |-> {sender}}}",
            f"act3: receiver := receiver \\/ {{{msg_instance} |-> {receiver}}}",
            f"act4: receivedMessages := {{}}"
        ]
        
        # Run เลข Action ต่อจาก 4
        current_act_idx = 5
        
        if data:
            send_actions.append(f"act{current_act_idx}: senderdataMessages := senderdataMessages \\/ {{{msg_instance} |-> {data}}}")
            current_act_idx += 1
            
        send_actions.append(f"act{current_act_idx}: currentMessage := {{{msg_instance}}}")

        # ประกอบร่าง Send Event
        send_evt_str = f"    EVENT send{msg_instance}{suffix}\n    WHEN\n"
        send_evt_str += "        " + "\n        ".join(send_guards) + "\n"
        send_evt_str += "    THEN\n"
        send_evt_str += "        " + "\n        ".join(send_actions) + "\n"
        send_evt_str += "    END"
        
        events_text.append(send_evt_str)
        
        # ==================================================
        # 2. RECEIVE EVENT
        # ==================================================
        
        recv_guards = [
            f"grd1: {msg_instance} : sentMessages",
            f"grd2: {msg_instance} |-> {sender} : sender",
            f"grd3: {msg_instance} |-> {receiver} : receiver",
            f"grd4: {msg_instance} /: receivedMessages",
            f"grd5: currentMessage = {{{msg_instance}}}"
        ]
        
        recv_actions = [
            f"act1: receivedMessages := receivedMessages \\/ {{{msg_instance}}}"
        ]
        
        current_act_idx = 2
        
        if data:
            recv_actions.append(f"act{current_act_idx}: receiverdataMessages := receiverdataMessages \\/ {{{msg_instance} |-> {data}}}")
            current_act_idx += 1
            
        recv_actions.append(f"act{current_act_idx}: currentMessage := {{}}")

        # ประกอบร่าง Receive Event
        recv_evt_str = f"    EVENT receive{msg_instance}{suffix}\n    WHEN\n"
        recv_evt_str += "        " + "\n        ".join(recv_guards) + "\n"
        recv_evt_str += "    THEN\n"
        recv_evt_str += "        " + "\n        ".join(recv_actions) + "\n"
        recv_evt_str += "    END"
        
        events_text.append(recv_evt_str)
        
    return "\n".join(events_text)

# ================= NEW FUNCTION: Extract Variables form Fragments =================

def extract_variables_from_fragments(xml_path: str) -> dict:
    """
    ค้นหาตัวแปรจากเงื่อนไข [ ... ] ทั่วทั้ง Diagram
    รองรับ: [Login=1], [Login==1], [amount > 2000], [val : 0..100]
    Returns: Dict { 'var_name': {'val': 'value', 'type': 'assign_type'} }
    """
    variables = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        for elem in root.iter():
            value = elem.get('value', '')
            if not value: continue
            
            # Clean HTML
            clean_val = re.sub(r'<[^>]*>', '', value).strip()
            
            # 1. หา Assignment/Equality: [Login=1] หรือ [Login==1] หรือ [Login:=1]
            # Group 1: Name, Group 2: Value
            match_eq = re.search(r'\[\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|:=|=)\s*(\d+)\s*\]', clean_val)
            if match_eq:
                name = match_eq.group(1)
                val = match_eq.group(2)
                variables[name] = {'val': val, 'op': ':='} # Deterministic
                continue

            # 2. หา Range/Non-deterministic: [amount : 0..2000] หรือ [amount in 0..2000]
            match_range = re.search(r'\[\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::|in|:∈)\s*(\d+\.\.\d+)\s*\]', clean_val)
            if match_range:
                name = match_range.group(1)
                val_range = match_range.group(2)
                variables[name] = {'val': val_range, 'op': ':∈'} # Non-deterministic
                continue
                
            # 3. หา Comparison: [retry < 5], [amount > 0] -> Default 0
            match_cmp = re.search(r'\[\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<|>|<=|>=|!=)\s*(\d+)\s*\]', clean_val)
            if match_cmp:
                name = match_cmp.group(1)
                if name not in variables:
                    variables[name] = {'val': '0', 'op': ':='} # Default start at 0
                    
    except Exception as e:
        print(f"Var Extract Error: {e}")
        
    return variables

def apply_rules_full(xml_path: str, version: int = 1) -> str:
    """สร้าง Context, Machine, Events และ Variables"""
    base_name = extract_base_name_from_xml(xml_path)
    objects = extract_objects_from_xml(xml_path)
    messages, data_messages = extract_messages_and_data(xml_path)
    sequence_flows = extract_sequence_from_xml(xml_path)
    
    # ดึงตัวแปร (Update)
    fragment_vars = extract_variables_from_fragments(xml_path)
    
    msg_instances = [f"{f['msg']}_{i+1}" for i, f in enumerate(sequence_flows)]
    
    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    
    # --- CONTEXT ---
    sets_str = "    Objects\n    Messages\n    DataMessages"
    
    all_constants = objects + messages + data_messages + msg_instances
    
    axioms_list = []
    if objects: axioms_list.append(f"axm1: Objects = {{ {', '.join(objects)} }}")
    # Reversed Messages ตามที่ขอ
    if messages: axioms_list.append(f"axm2: Messages = {{ {', '.join(reversed(messages))} }}")
    if data_messages: axioms_list.append(f"axm3: DataMessages = {{ {', '.join(data_messages)} }}")
    
    # if msg_instances:
    #     axioms_list.append(f"axm4: /* Message Instances */")
    #     for i, inst in enumerate(msg_instances):
    #          axioms_list.append(f"axm_inst_{i}: {inst} : Messages")

    axioms_str = "\n    ".join(axioms_list)
    constants_str = "\n    ".join(all_constants) if all_constants else ""

    # --- MACHINE ---
    events_str = generate_events(sequence_flows)

    base_vars = [
        "sentMessages", "sender", "receiver", 
        "receivedMessages", "senderdataMessages", 
        "currentMessage", "receiverdataMessages"
    ]
    
    # เพิ่มตัวแปรใหม่
    extra_var_names = sorted(list(fragment_vars.keys()))
    all_vars = base_vars + extra_var_names
    variables_str = "\n    ".join(all_vars)

    # Invariants (INT)
    extra_invariants = []
    for i, var in enumerate(extra_var_names):
        # เลข inv รันต่อจาก 7
        extra_invariants.append(f"inv{7+i+1}: {var} : INT")
        
    invariants_str = "\n    ".join(extra_invariants)

    # Initialisation
    extra_init_actions = []
    for i, var in enumerate(extra_var_names):
        info = fragment_vars[var]
        val = info['val']
        operator = info['op'] # := หรือ :∈
        
        act_num = 7 + i + 1 
        extra_init_actions.append(f"act{act_num}: {var} {operator} {val}")
        
    init_actions_str = "\n        ".join(extra_init_actions)

    event_b_text = f"""CONTEXT {context_name}
SETS
{sets_str}
CONSTANTS
    {constants_str}
AXIOMS
    {axioms_str}
END

MACHINE {machine_name}
SEES
    {context_name}
VARIABLES
    {variables_str}
INVARIANTS
    inv1: sentMessages <: Messages
    inv2: currentMessage <: Messages
    inv3: sender <: Messages * Objects
    inv4: receiver <: Messages * Objects
    inv5: receivedMessages <: sentMessages
    inv6: senderdataMessages <: Messages * DataMessages
    inv7: receiverdataMessages <: Messages * DataMessages
    {invariants_str}
EVENTS
    INITIALISATION
    BEGIN
        act1: sentMessages := {{}}
        act2: sender := {{}}
        act3: receiver := {{}}
        act4: receivedMessages := {{}}
        act5: senderdataMessages := {{}}
        act6: currentMessage := {{}}
        act7: receiverdataMessages := {{}}
        {init_actions_str}
    END

{events_str}
END
"""
    return event_b_text


# ===================== UI CLASS =====================

class SequenceToEventBApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Sequence Diagram XML → Event-B (With Events)")
        self.master.geometry("1000x700")
        self.current_xml_path = None
        
        # Top Frame
        top_frame = tk.Frame(master)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(top_frame, text="📁 เลือกไฟล์ XML", command=self.open_xml_file, bg="#4CAF50", fg="black").pack(side=tk.LEFT)
        
        tk.Label(top_frame, text="Ver:").pack(side=tk.LEFT, padx=(15, 5))
        self.version_var = tk.IntVar(value=1)
        tk.Entry(top_frame, textvariable=self.version_var, width=3).pack(side=tk.LEFT)
        
        tk.Button(top_frame, text="🔄 แปลงเป็น Event-B", command=self.run_transform, bg="#2196F3", fg="black").pack(side=tk.LEFT, padx=10)
        tk.Button(top_frame, text="💾 บันทึก", command=self.save_output, bg="#FF9800", fg="black").pack(side=tk.LEFT)
        
        self.lbl_file = tk.Label(master, text="ยังไม่ได้เลือกไฟล์", fg="gray")
        self.lbl_file.pack(fill=tk.X, padx=10)
        
        self.text_output = ScrolledText(master, font=("Courier New", 10))
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def open_xml_file(self):
        path = filedialog.askopenfilename(filetypes=[("XML", "*.xml"), ("All", "*.*")])
        if path:
            self.current_xml_path = path
            self.lbl_file.config(text=f"📄 {os.path.basename(path)}", fg="green")
            self.run_transform() # Auto preview

    def run_transform(self):
        if not self.current_xml_path: return
        try:
            res = apply_rules_full(self.current_xml_path, self.version_var.get())
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert(tk.END, res)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_output(self):
        content = self.text_output.get("1.0", tk.END).strip()
        if not content: return
        path = filedialog.asksaveasfilename(defaultextension=".eventb", filetypes=[("Event-B", "*.eventb"), ("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            messagebox.showinfo("Saved", "บันทึกเรียบร้อย")

if __name__ == "__main__":
    root = tk.Tk()
    SequenceToEventBApp(root)
    root.mainloop()