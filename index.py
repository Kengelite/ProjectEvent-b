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
    """
    ดึงชื่อระบบ (base name) จาก XML ของ sequence diagram
    
    สำหรับ Draw.io: ดึงจาก attribute 'name' ของ <diagram>
    Fallback: ใช้ชื่อไฟล์
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # สำหรับ Draw.io: หา <diagram name="...">
        for elem in root.iter():
            if elem.tag == 'diagram':
                name = elem.get('name')
                if name and name != 'หน้า-1':  # ข้ามชื่อ default ของ Draw.io
                    return to_pascal_case(name)
        
        # หา attribute name ของ root
        name = root.get("name")
        
        # หา name จาก element ข้างใน
        if not name:
            for elem in root.iter():
                if "name" in elem.attrib:
                    name = elem.attrib["name"]
                    if name and name != 'หน้า-1':
                        break
        
        # Fallback: เอาจากชื่อไฟล์
        if not name or name == 'หน้า-1':
            filename = os.path.basename(xml_path)
            name, _ = os.path.splitext(filename)
        
        base_name = to_pascal_case(name)
        return base_name
    
    except Exception as e:
        raise RuntimeError(f"อ่าน XML ไม่ได้: {e}")


def extract_objects_from_xml(xml_path: str) -> list:
    """
    ดึงรายชื่อ objects จาก XML sequence diagram (Draw.io format)
    มองหา element ที่มี style="shape=umlLifeline" และดึง value attribute
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        objects = set()
        
        # สำหรับ Draw.io: หา mxCell ที่มี style="shape=umlLifeline"
        for elem in root.iter():
            style = elem.get('style', '')
            if 'umlLifeline' in style:
                value = elem.get('value', '')
                if value:
                    # ดึงชื่อ class จาก format "name:ClassName" หรือ ":ClassName"
                    # เช่น "user:User" -> "User", ":PaymentService" -> "PaymentService"
                    if ':' in value:
                        parts = value.split(':')
                        class_name = parts[-1].strip()
                        if class_name:
                            objects.add(class_name)
                    else:
                        # ถ้าไม่มี : ใช้ทั้ง value
                        objects.add(value.strip())
        
        # ถ้าไม่เจอ ลองวิธีเดิม (สำหรับ XML format อื่น ๆ)
        if not objects:
            for elem in root.iter():
                tag_lower = elem.tag.lower()
                if 'lifeline' in tag_lower or 'participant' in tag_lower:
                    name = elem.get('name') or elem.get('id')
                    if name:
                        objects.add(name)
        
        return sorted(list(objects))
    except Exception as e:
        raise RuntimeError(f"ดึง objects จาก XML ไม่ได้: {e}")


def extract_messages_from_xml(xml_path: str) -> tuple:
    """
    ดึง Messages และ DataMessages จาก XML sequence diagram
    
    Returns:
        (messages, data_messages) - tuple ของ 2 lists
        
    Messages: ชื่อ method/function ที่เรียก เช่น submitPayment, sendNotification
    DataMessages: parameters และ return values เช่น amount, paymentDetails
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        messages = set()
        data_messages = set()
        
        # หา edge ที่เป็นข้อความ (message arrows)
        for elem in root.iter():
            style = elem.get('style', '')
            value = elem.get('value', '')
            
            # หา message arrow (endArrow=open หรือ endArrow=block)
            if 'endArrow' in style and value:
                # แยก message name และ parameters
                # เช่น "submitPayment(amount)" -> message: submitPayment, data: amount
                # เช่น "paymentDetails" -> data: paymentDetails
                
                if '(' in value and ')' in value:
                    # มี parameters
                    match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', value)
                    if match:
                        msg_name = match.group(1).strip()
                        params = match.group(2).strip()
                        
                        messages.add(msg_name)
                        
                        # แยก parameters (ถ้ามีหลายตัว คั่นด้วย ,)
                        if params:
                            for param in params.split(','):
                                param = param.strip()
                                if param:
                                    data_messages.add(param)
                else:
                    # ไม่มี parameters - อาจเป็น return value หรือ simple message
                    clean_value = value.strip()
                    if clean_value and not clean_value.startswith('«'):
                        # ถ้าเป็นคำเดียว อาจเป็น message หรือ data
                        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', clean_value):
                            # ถ้าเป็น camelCase หรือขึ้นต้นด้วยตัวพิมพ์เล็ก อาจเป็น data
                            if clean_value[0].islower():
                                data_messages.add(clean_value)
                            else:
                                messages.add(clean_value)
        
        return sorted(list(messages)), sorted(list(data_messages))
    except Exception as e:
        raise RuntimeError(f"ดึง messages จาก XML ไม่ได้: {e}")


def apply_rules_1_and_2(xml_path: str, version: int = 1) -> str:
    """
    กฏข้อ 1: การตั้งชื่อ CONTEXT และ MACHINE
    กฏข้อ 2: การแปลง Objects, Messages, DataMessages เป็น SETS และ CONSTANTS
    
    CONTEXT = <BaseName>Context
    MACHINE = <BaseName>InteractionMachine_<version>
    SETS: Objects, Messages, DataMessages
    CONSTANTS: แต่ละ object, message, data message
    AXIOMS: กำหนดเซตของแต่ละประเภท
    """
    base_name = extract_base_name_from_xml(xml_path)
    objects = extract_objects_from_xml(xml_path)
    messages, data_messages = extract_messages_from_xml(xml_path)
    
    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    
    # สร้าง SETS
    sets_lines = ["    Objects"]
    if messages:
        sets_lines.append("    Messages")
    if data_messages:
        sets_lines.append("    DataMessages")
    sets_section = "\n".join(sets_lines)
    
    # สร้าง CONSTANTS
    constants_lines = []
    if objects:
        constants_lines.extend(objects)
    if messages:
        constants_lines.extend(messages)
    if data_messages:
        constants_lines.extend(data_messages)
    
    if constants_lines:
        constants_section = "\n    ".join(constants_lines)
    else:
        constants_section = "    /* ไม่พบ objects/messages ใน XML */"
    
    # สร้าง AXIOMS
    axioms_lines = []
    if objects:
        object_list = " , ".join(objects)
        axioms_lines.append(f"    axm1: Objects = {{ {object_list} }}")
    
    if messages:
        message_list = " , ".join(messages)
        axiom_num = len(axioms_lines) + 1
        axioms_lines.append(f"    axm{axiom_num}: Messages = {{ {message_list} }}")
    
    if data_messages:
        data_list = " , ".join(data_messages)
        axiom_num = len(axioms_lines) + 1
        axioms_lines.append(f"    axm{axiom_num}: DataMessages = {{ {data_list} }}")
    
    axioms_section = "\n".join(axioms_lines) if axioms_lines else "    /* ไม่มีข้อมูลให้ประกาศ */"
    
    # สร้างโครง Event-B แบบเรียบง่าย
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
END
"""
    return event_b_text


# ===================== TKINTER UI =====================

class SequenceToEventBApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Sequence Diagram XML → Event-B (Rules 1-3)")
        self.master.geometry("1000x700")
        
        self.current_xml_path = None
        
        # เฟรมบน
        top_frame = tk.Frame(master)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn_open = tk.Button(
            top_frame,
            text="📁 เลือกไฟล์ XML ของ Sequence Diagram",
            command=self.open_xml_file,
            bg="#4CAF50",
            fg="white",
            padx=10,
            pady=5
        )
        self.btn_open.pack(side=tk.LEFT)
        
        tk.Label(top_frame, text="เวอร์ชัน Machine:").pack(side=tk.LEFT, padx=(15, 5))
        self.version_var = tk.IntVar(value=1)
        self.entry_version = tk.Entry(top_frame, textvariable=self.version_var, width=5)
        self.entry_version.pack(side=tk.LEFT)
        
        self.btn_transform = tk.Button(
            top_frame,
            text="🔄 แปลง (กฏข้อ 1-3)",
            command=self.run_transform,
            bg="#2196F3",
            fg="white",
            padx=10,
            pady=5
        )
        self.btn_transform.pack(side=tk.LEFT, padx=10)
        
        self.btn_save = tk.Button(
            top_frame,
            text="💾 บันทึกผลลัพธ์",
            command=self.save_output,
            bg="#FF9800",
            fg="white",
            padx=10,
            pady=5
        )
        self.btn_save.pack(side=tk.LEFT)
        
        # label แสดงชื่อไฟล์
        self.lbl_file = tk.Label(master, text="ยังไม่ได้เลือกไฟล์ XML", anchor="w", fg="gray")
        self.lbl_file.pack(fill=tk.X, padx=10)
        
        # กล่องแสดง objects ที่พบ
        info_frame = tk.Frame(master)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(info_frame, text="ข้อมูลที่ตรวจพบ:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.lbl_objects = tk.Label(info_frame, text="", anchor="w", justify=tk.LEFT, fg="blue", wraplength=950)
        self.lbl_objects.pack(fill=tk.X)
        
        # กล่องข้อความแสดงผล Event-B
        output_label = tk.Label(master, text="ผลลัพธ์ Event-B:", font=("Arial", 10, "bold"))
        output_label.pack(anchor="w", padx=10)
        
        self.text_output = ScrolledText(master, wrap=tk.NONE, font=("Courier New", 10))
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
    
    def open_xml_file(self):
        filetypes = [("XML files", "*.xml"), ("All files", "*.*")]
        path = filedialog.askopenfilename(
            title="เลือกไฟล์ XML ของ Sequence Diagram",
            filetypes=filetypes
        )
        if not path:
            return
        
        self.current_xml_path = path
        self.lbl_file.config(text=f"📄 ไฟล์: {os.path.basename(path)}", fg="green")
        
        try:
            base_name = extract_base_name_from_xml(path)
            objects = extract_objects_from_xml(path)
            messages, data_messages = extract_messages_from_xml(path)
            
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert(tk.END, f"✅ ตรวจพบชื่อระบบ: {base_name}\n")
            self.text_output.insert(tk.END, f"✅ พบ {len(objects)} objects\n")
            self.text_output.insert(tk.END, f"✅ พบ {len(messages)} messages\n")
            self.text_output.insert(tk.END, f"✅ พบ {len(data_messages)} data messages\n\n")
            
            info_parts = []
            if objects:
                info_parts.append(f"Objects: {', '.join(objects)}")
            if messages:
                info_parts.append(f"Messages: {', '.join(messages)}")
            if data_messages:
                info_parts.append(f"DataMessages: {', '.join(data_messages)}")
            
            if info_parts:
                self.lbl_objects.config(text=" | ".join(info_parts))
            else:
                self.lbl_objects.config(text="ไม่พบข้อมูลใน XML")
                
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
        except Exception:
            messagebox.showwarning("เตือน", "กรุณาใส่เวอร์ชัน Machine เป็นจำนวนเต็มบวก")
            return
        
        try:
            result_text = apply_rules_1_and_2(self.current_xml_path, version)
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert(tk.END, result_text)
            
            # ดาวน์โหลดไฟล์อัตโนมัติหลังแปลงเสร็จ
            self.auto_save_result(result_text)
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def save_output(self):
        content = self.text_output.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("เตือน", "ไม่มีผลลัพธ์ให้บันทึก")
            return
        
        filetypes = [("Event-B files", "*.eventb"), ("Text files", "*.txt"), ("All files", "*.*")]
        path = filedialog.asksaveasfilename(
            title="บันทึกผลลัพธ์",
            defaultextension=".eventb",
            filetypes=filetypes
        )
        
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("✅ สำเร็จ", f"บันทึกไฟล์เรียบร้อย!\n📄 {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", f"บันทึกไฟล์ไม่สำเร็จ: {e}")
    
    def auto_save_result(self, content: str):
        """บันทึกไฟล์อัตโนมัติหลังแปลงเสร็จ - สร้าง ZIP ที่มี 7 ไฟล์ Event-B"""
        if not content:
            return
        
        # สร้างชื่อไฟล์จาก XML ต้นฉบับ
        base_name = extract_base_name_from_xml(self.current_xml_path)
        version = self.version_var.get()
        
        context_name = f"{base_name}Context"
        machine_name = f"{base_name}InteractionMachine_{version}"
        
        # ให้เลือกที่จะบันทึก ZIP
        suggested_name = f"{base_name}_EventB_Project.zip"
        filetypes = [("ZIP files", "*.zip"), ("All files", "*.*")]
        zip_path = filedialog.asksaveasfilename(
            title="บันทึก Event-B Project (ZIP)",
            defaultextension=".zip",
            initialfile=suggested_name,
            filetypes=filetypes
        )
        
        if not zip_path:
            return
        
        try:
            # สร้างโฟลเดอร์ชั่วคราว
            temp_dir = tempfile.mkdtemp()
            files_created = []
            
            # 1. สร้างไฟล์ .buc (Context)
            buc_path = os.path.join(temp_dir, f"{context_name}.buc")
            with open(buc_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write('<org.eventb.core.contextFile version="3">\n')
                f.write(f'<org.eventb.core.context name="{context_name}"/>\n')
                f.write('</org.eventb.core.contextFile>\n')
            files_created.append((buc_path, f"{context_name}.buc"))
            
            # 2. สร้างไฟล์ .bcc (Context Configuration)
            bcc_path = os.path.join(temp_dir, f"{context_name}.bcc")
            with open(bcc_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write('<org.eventb.core.scContextFile/>\n')
            files_created.append((bcc_path, f"{context_name}.bcc"))
            
            # 3. สร้างไฟล์ .bum (Machine)
            bum_path = os.path.join(temp_dir, f"{machine_name}.bum")
            with open(bum_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write('<org.eventb.core.machineFile version="5">\n')
                f.write(f'<org.eventb.core.seesContext name="sees_{context_name}" org.eventb.core.target="{context_name}"/>\n')
                f.write('</org.eventb.core.machineFile>\n')
            files_created.append((bum_path, f"{machine_name}.bum"))
            
            # 4. สร้างไฟล์ .bpo (Proof Obligations)
            bpo_path = os.path.join(temp_dir, f"{machine_name}.bpo")
            with open(bpo_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write('<org.eventb.core.poFile version="1"/>\n')
            files_created.append((bpo_path, f"{machine_name}.bpo"))
            
            # 5. สร้างไฟล์ .bpr (Project)
            bpr_path = os.path.join(temp_dir, f"{base_name}.bpr")
            with open(bpr_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write('<org.rodinp.core.roDB version="1"/>\n')
            files_created.append((bpr_path, f"{base_name}.bpr"))
            
            # 6. สร้างไฟล์ .bps (Static Checker)
            bps_path = os.path.join(temp_dir, f"{machine_name}.bps")
            with open(bps_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write('<org.eventb.core.scMachineFile version="5"/>\n')
            files_created.append((bps_path, f"{machine_name}.bps"))
            
            # 7. บันทึกไฟล์ text สำหรับอ่านง่าย
            txt_path = os.path.join(temp_dir, f"{base_name}_readable.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)
            files_created.append((txt_path, f"{base_name}_readable.txt"))
            
            # สร้างไฟล์ ZIP
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, archive_name in files_created:
                    zipf.write(file_path, archive_name)
            
            # ลบไฟล์ชั่วคราว
            import shutil
            shutil.rmtree(temp_dir)
            
            file_names = [name for _, name in files_created]
            
            messagebox.showinfo(
                "✅ สำเร็จ", 
                f"บันทึก Event-B Project เรียบร้อย!\n\n"
                f"📦 ไฟล์ ZIP: {os.path.basename(zip_path)}\n\n"
                f"ไฟล์ภายใน ZIP ({len(file_names)} ไฟล์):\n" + 
                "\n".join([f"  • {f}" for f in file_names])
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"บันทึกไฟล์ไม่สำเร็จ: {e}")


def main():
    root = tk.Tk()
    app = SequenceToEventBApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()