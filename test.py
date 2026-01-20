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
    """ดึงชื่อระบบจาก XML"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        for elem in root.iter('diagram'):
            name = elem.get('name')
            if name and name != 'หน้า-1':
                return to_pascal_case(name)
        
        filename = os.path.basename(xml_path)
        name, _ = os.path.splitext(filename)
        return to_pascal_case(name)
    
    except Exception as e:
        raise RuntimeError(f"อ่าน XML ไม่ได้: {e}")


def extract_objects_from_xml(xml_path: str) -> list:
    """ดึง objects จาก lifelines"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        objects = set()
        
        for elem in root.iter():
            if elem.tag != 'mxCell':
                continue
            style = elem.get('style', '')
            if 'umlLifeline' not in style:
                continue
            value = elem.get('value', '')
            if not value:
                continue
            
            if ':' in value:
                class_name = value.split(':')[-1].strip()
                if class_name:
                    objects.add(class_name)
            else:
                objects.add(value.strip())
        
        return sorted(list(objects))
    except Exception as e:
        raise RuntimeError(f"ดึง objects ไม่ได้: {e}")


def extract_messages_from_xml(xml_path: str) -> tuple:
    """ดึง messages และ data messages จาก XML"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        message_list = []
        data_messages_set = set()
        message_index = 1
        
        # Step 1: สร้าง map lifeline id -> class name
        lifeline_map = {}
        for elem in root.iter():
            if elem.tag != 'mxCell':
                continue
            style = elem.get('style', '')
            if 'umlLifeline' not in style:
                continue
            elem_id = elem.get('id', '')
            value = elem.get('value', '')
            if not value or not elem_id:
                continue
            
            if ':' in value:
                class_name = value.split(':')[-1].strip()
                if class_name:
                    lifeline_map[elem_id] = class_name
            else:
                lifeline_map[elem_id] = value.strip()
        
        # Step 2: หา message arrows
        for elem in root.iter():
            if elem.tag != 'mxCell':
                continue
            if elem.get('edge') != '1':
                continue
            
            value = elem.get('value', '').strip()
            if not value:
                continue
            
            source_id = elem.get('source', '')
            target_id = elem.get('target', '')
            if not source_id or not target_id:
                continue
            
            sender_obj = lifeline_map.get(source_id)
            receiver_obj = lifeline_map.get(target_id)
            if not sender_obj or not receiver_obj:
                continue
            
            # Step 3: แยก message name และ parameters
            msg_name = None
            data_params = []
            
            if '(' in value and ')' in value:
                match = re.match(r'([a-zA-Z_]\w*)\s*\((.*?)\)', value)
                if match:
                    msg_name = match.group(1)
                    params_str = match.group(2).strip()
                    if params_str:
                        for param in params_str.split(','):
                            param = param.strip()
                            if param and re.match(r'^[a-zA-Z_]\w*$', param):
                                data_params.append(param)
                                data_messages_set.add(param)
            elif re.match(r'^[a-zA-Z_]\w*$', value):
                msg_name = value
                if value[0].islower():
                    data_params.append(value)
                    data_messages_set.add(value)
            
            if msg_name:
                message_list.append({
                    'name': msg_name,
                    'sender': sender_obj,
                    'receiver': receiver_obj,
                    'data': data_params,
                    'index': message_index
                })
                message_index += 1
        
        return message_list, sorted(list(data_messages_set))
        
    except Exception as e:
        raise RuntimeError(f"ดึง messages ไม่ได้: {e}")


def generate_events(message_list: list) -> str:
    """สร้าง send/receive events"""
    if not message_list:
        return ""
    
    events = []
    
    for msg in message_list:
        msg_name = msg['name']
        sender = msg['sender']
        receiver = msg['receiver']
        data = msg['data']
        index = msg['index']
        msg_id = f"{msg_name}_{index}"
        
        # Send event
        send_event = f"""    send{msg_id}
        WHEN
            grd1: {msg_id} ∉ sentMessages
            grd2: currentMessage = ∅
        THEN
            act1: sentMessages ≔ sentMessages ∪ {{{msg_id}}}
            act2: sender ≔ sender ∪ {{{msg_id} ↦ {sender}}}
            act3: receiver ≔ receiver ∪ {{{msg_id} ↦ {receiver}}}
            act4: receivedMessages ≔ ∅"""
        
        act_num = 5
        if data:
            for d in data:
                send_event += f"\n            act{act_num}: senderdataMessages ≔ senderdataMessages ∪ {{{msg_id} ↦ {d}}}"
                act_num += 1
        
        send_event += f"\n            act{act_num}: currentMessage ≔ {{{msg_id}}}\n        END"
        events.append(send_event)
        
        # Receive event
        recv_event = f"""    receive{msg_id}
        WHEN
            grd1: {msg_id} ∈ sentMessages
            grd2: {msg_id} ↦ {sender} ∈ sender
            grd3: {msg_id} ↦ {receiver} ∈ receiver
            grd4: {msg_id} ∉ receivedMessages
            grd5: currentMessage = {{{msg_id}}}
        THEN
            act1: receivedMessages ≔ receivedMessages ∪ {{{msg_id}}}"""
        
        act_num = 2
        if data:
            for d in data:
                recv_event += f"\n            act{act_num}: receiverdataMessages ≔ receiverdataMessages ∪ {{{msg_id} ↦ {d}}}"
                act_num += 1
        
        recv_event += f"\n            act{act_num}: currentMessage ≔ ∅\n        END"
        events.append(recv_event)
    
    return "\n".join(events)


def apply_rules_1_to_5(xml_path: str, version: int = 1) -> str:
    """แปลง XML เป็น Event-B specification"""
    base_name = extract_base_name_from_xml(xml_path)
    objects = extract_objects_from_xml(xml_path)
    message_list, data_messages = extract_messages_from_xml(xml_path)
    
    messages = sorted(list(set([f"{msg['name']}_{msg['index']}" for msg in message_list])))
    
    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    
    # SETS
    sets_lines = ["    Objects"]
    if messages:
        sets_lines.append("    Messages")
    if data_messages:
        sets_lines.append("    DataMessages")
    sets_section = "\n".join(sets_lines)
    
    # CONSTANTS
    constants_lines = []
    if objects:
        constants_lines.extend(objects)
    if messages:
        constants_lines.extend(messages)
    if data_messages:
        constants_lines.extend(data_messages)
    
    constants_section = "\n    ".join(constants_lines) if constants_lines else "    /* ไม่พบข้อมูล */"
    
    # AXIOMS
    axioms_lines = []
    if objects:
        axioms_lines.append(f"    axm1: Objects = {{ {' , '.join(objects)} }}")
    if messages:
        axiom_num = len(axioms_lines) + 1
        axioms_lines.append(f"    axm{axiom_num}: Messages = {{ {' , '.join(messages)} }}")
    if data_messages:
        axiom_num = len(axioms_lines) + 1
        axioms_lines.append(f"    axm{axiom_num}: DataMessages = {{ {' , '.join(data_messages)} }}")
    
    axioms_section = "\n".join(axioms_lines) if axioms_lines else "    /* ไม่มีข้อมูล */"
    
    # EVENTS
    events_section = generate_events(message_list)
    
    event_b_text = f"""\
CONTEXT {context_name}
SETS
{sets_section}
CONSTANTS
    {constants_section}
AXIOMS
{axioms_section}
END

MACHINE {machine_name}
SEES
    {context_name}
VARIABLES
    sentMessages
    sender
    receiver
    receivedMessages
    senderdataMessages
    currentMessage
    receiverdataMessages
INVARIANTS
    inv1: sentMessages ⊆ Messages
    inv2: currentMessage ⊆ Messages
    inv3: sender ⊆ Messages × Objects
    inv4: receiver ⊆ Messages × Objects
    inv5: receivedMessages ⊆ sentMessages
    inv6: senderdataMessages ⊆ Messages × DataMessages
    inv7: receiverdataMessages ⊆ Messages × DataMessages
EVENTS
    INITIALISATION
    BEGIN
        sentMessages := ∅
        sender := ∅
        receiver := ∅
        receivedMessages := ∅
        senderdataMessages := ∅
        currentMessage := ∅
        receiverdataMessages := ∅
    END
{events_section}
END
"""
    return event_b_text


# ===================== TKINTER UI =====================

class SequenceToEventBApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Sequence Diagram → Event-B Converter")
        self.master.geometry("1100x750")
        self.current_xml_path = None
        
        top_frame = tk.Frame(master)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(top_frame, text="📁 เลือกไฟล์ XML", command=self.open_xml_file,
                 bg="#4CAF50", fg="white", padx=10, pady=5, font=("Arial", 10)).pack(side=tk.LEFT)
        
        tk.Label(top_frame, text="เวอร์ชัน:").pack(side=tk.LEFT, padx=(15, 5))
        self.version_var = tk.IntVar(value=1)
        tk.Entry(top_frame, textvariable=self.version_var, width=5).pack(side=tk.LEFT)
        
        tk.Button(top_frame, text="🔄 แปลงเป็น Event-B", command=self.run_transform,
                 bg="#2196F3", fg="white", padx=10, pady=5, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        
        tk.Button(top_frame, text="💾 บันทึก", command=self.save_output,
                 bg="#FF9800", fg="white", padx=10, pady=5, font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.lbl_file = tk.Label(master, text="ยังไม่ได้เลือกไฟล์ XML", anchor="w", fg="gray", font=("Arial", 9))
        self.lbl_file.pack(fill=tk.X, padx=10)
        
        info_frame = tk.Frame(master)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(info_frame, text="ข้อมูลที่ตรวจพบ:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.lbl_objects = tk.Label(info_frame, text="", anchor="w", justify=tk.LEFT, fg="blue", wraplength=1050)
        self.lbl_objects.pack(fill=tk.X, pady=2)
        
        tk.Label(master, text="ผลลัพธ์ Event-B:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(5,0))
        
        self.text_output = ScrolledText(master, wrap=tk.NONE, font=("Courier New", 9))
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
    
    def open_xml_file(self):
        path = filedialog.askopenfilename(title="เลือกไฟล์ XML", filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if not path:
            return
        
        self.current_xml_path = path
        self.lbl_file.config(text=f"📄 {os.path.basename(path)}", fg="green")
        
        try:
            base_name = extract_base_name_from_xml(path)
            objects = extract_objects_from_xml(path)
            message_list, data_messages = extract_messages_from_xml(path)
            
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert(tk.END, f"✅ ระบบ: {base_name}\n")
            self.text_output.insert(tk.END, f"✅ Objects: {len(objects)}\n")
            self.text_output.insert(tk.END, f"✅ Messages: {len(message_list)}\n")
            self.text_output.insert(tk.END, f"✅ Data: {len(data_messages)}\n\n")
            
            info_parts = []
            if objects:
                info_parts.append(f"Objects: {', '.join(objects)}")
            if message_list:
                msg_names = [f"{m['name']}_{m['index']}" for m in message_list]
                info_parts.append(f"Messages: {', '.join(msg_names)}")
            if data_messages:
                info_parts.append(f"Data: {', '.join(data_messages)}")
            
            self.lbl_objects.config(text=" | ".join(info_parts) if info_parts else "ไม่พบข้อมูล")
                
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def run_transform(self):
        if not self.current_xml_path:
            messagebox.showwarning("เตือน", "กรุณาเลือกไฟล์ XML ก่อน")
            return
        
        try:
            version = int(self.version_var.get())
            if version <= 0:
                raise ValueError()
        except:
            messagebox.showwarning("เตือน", "กรุณาใส่เวอร์ชันเป็นจำนวนเต็มบวก")
            return
        
        try:
            result_text = apply_rules_1_to_5(self.current_xml_path, version)
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert(tk.END, result_text)
            self.auto_save_result(result_text)
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def save_output(self):
        content = self.text_output.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("เตือน", "ไม่มีผลลัพธ์ให้บันทึก")
            return
        
        path = filedialog.asksaveasfilename(title="บันทึก", defaultextension=".txt",
                                           filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("สำเร็จ", f"บันทึกแล้ว: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"บันทึกไม่สำเร็จ: {e}")
    
    def auto_save_result(self, content: str):
        if not content:
            return
        
        base_name = extract_base_name_from_xml(self.current_xml_path)
        version = self.version_var.get()
        context_name = f"{base_name}Context"
        machine_name = f"{base_name}InteractionMachine_{version}"
        
        zip_path = filedialog.asksaveasfilename(title="บันทึก Event-B Project", defaultextension=".zip",
                                               initialfile=f"{base_name}_EventB.zip", filetypes=[("ZIP files", "*.zip")])
        if not zip_path:
            return
        
        try:
            temp_dir = tempfile.mkdtemp()
            files_created = []
            
            # .buc
            buc = os.path.join(temp_dir, f"{context_name}.buc")
            with open(buc, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<org.eventb.core.contextFile version="3">\n')
                f.write(f'<org.eventb.core.context name="{context_name}"/>\n</org.eventb.core.contextFile>\n')
            files_created.append((buc, f"{context_name}.buc"))
            
            # .bcc
            bcc = os.path.join(temp_dir, f"{context_name}.bcc")
            with open(bcc, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<org.eventb.core.scContextFile/>\n')
            files_created.append((bcc, f"{context_name}.bcc"))
            
            # .bum
            bum = os.path.join(temp_dir, f"{machine_name}.bum")
            with open(bum, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<org.eventb.core.machineFile version="5">\n')
                f.write(f'<org.eventb.core.seesContext name="ctx" org.eventb.core.target="{context_name}"/>\n</org.eventb.core.machineFile>\n')
            files_created.append((bum, f"{machine_name}.bum"))
            
            # .bpo, .bpr, .bps
            for ext, xml_type in [('.bpo', 'poFile'), ('.bpr', 'roDB'), ('.bps', 'scMachineFile')]:
                name = machine_name if ext != '.bpr' else base_name
                path = os.path.join(temp_dir, f"{name}{ext}")
                with open(path, "w", encoding="utf-8") as f:
                    f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                    if ext == '.bpr':
                        f.write(f'<org.rodinp.core.{xml_type} version="1"/>\n')
                    else:
                        f.write(f'<org.eventb.core.{xml_type} version="{"1" if ext == ".bpo" else "5"}"/>\n')
                files_created.append((path, f"{name}{ext}"))
            
            # .txt
            txt = os.path.join(temp_dir, f"{base_name}_readable.txt")
            with open(txt, "w", encoding="utf-8") as f:
                f.write(content)
            files_created.append((txt, f"{base_name}_readable.txt"))
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, archive_name in files_created:
                    zipf.write(file_path, archive_name)
            
            import shutil
            shutil.rmtree(temp_dir)
            
            messagebox.showinfo("✅ สำเร็จ", f"บันทึก ZIP แล้ว!\n\n{os.path.basename(zip_path)}\n\nไฟล์ทั้งหมด: {len(files_created)} ไฟล์")
            
        except Exception as e:
            messagebox.showerror("Error", f"บันทึกไม่สำเร็จ: {e}")


def main():
    root = tk.Tk()
    app = SequenceToEventBApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()