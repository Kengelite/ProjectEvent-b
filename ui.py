import os
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import customtkinter as ctk

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

from xml_parser import (
    extract_objects_from_xml,
    extract_messages_from_xml,
    extract_base_name_from_xml,
    extract_detailed_sequence,
    validate_sequence_diagram,
    get_message_warnings,
)
from eventb_generator import apply_rules_1_and_2
from ai_service import generate_ctl_with_ollama, chat_with_ollama, build_model_context
from rodin_exporter import generate_rodin_zip


TRANSLATIONS = {
    "EN": {
        "title":          "ChronoSeq-B — Sequence Diagram → Event-B & AI CTL",
        "choose_xml":     "Choose XML",
        "transform":      "Transform",
        "export_rodin":   "Export Rodin",
        "generate_ctl":   "Generate CTL",
        "save":           "Save",
        "version":        "VERSION",
        "workflow":       "WORKFLOW :   1. CHOOSE XML   ➔   2. TRANSFORM   ➔   3. GENERATE CTL",
        "no_file":        "📄 NO FILE SELECTED",
        "selected":       "📄 SELECTED : {name}",
        "waiting":        " WAITING FOR FILE...",
        "file":           " FILE: {name}",
        "objects":        "{o} OBJ  |  {m} MSG  |  {d} DATA",
        "eventb_output":  "EVENT-B OUTPUT",
        "ctl_output":     "AI CTL OUTPUT",
        "chat_title":     "AI EVENT-B CHAT",
        "clear":          "CLEAR",
        "send":           "SEND",
        "newline_hint":   "Shift+Enter for newline",
        "you":            "YOU",
        "ai":             "EVENT-B AI",
        "lang_btn":       "🌐 ไทย",
        "warn":           "Warning",
        "select_first":   "Please select an XML file first",
        "ai_analyzing":   "Sending data to Ollama for CTL analysis...\n",
        "success":        "Success",
        "exported":       "Exported:\n{path}\n\nImport into Rodin via File → Import → Existing Projects into Workspace",
        "import_ok_title": "Import successful",
        "import_ok":       "✅ Valid Sequence Diagram\n\nFile: {name}\n{o} objects  |  {m} messages  |  {d} data",
        "import_warn_title": "Imported — check arrows",
        "import_warn":     "Imported: {name}\n{o} objects  |  {m} messages  |  {d} data\n\n⚠ {n} arrow(s) have NO message and were skipped:\n{items}\n\nAdd a label to these arrows in draw.io.",
        "invalid_title":       "Invalid file",
        "invalid_read_error":  "Cannot read this XML file. Please make sure it is a valid draw.io file.",
        "invalid_not_drawio":  "This is not a draw.io diagram (no mxCell found).",
        "invalid_no_object":   "No Object / Lifeline found — this does not look like a Sequence Diagram.",
        "invalid_no_message":  "No Message (arrow between objects) found — this does not look like a Sequence Diagram.",
    },
    "TH": {
        "title":          "ChronoSeq-B — แปลง Sequence Diagram → Event-B & AI CTL",
        "choose_xml":     "เลือกไฟล์ XML",
        "transform":      "แปลง",
        "export_rodin":   "ส่งออก Rodin",
        "generate_ctl":   "สร้าง CTL",
        "save":           "บันทึก",
        "version":        "เวอร์ชัน",
        "workflow":       "ขั้นตอน :   1. เลือก XML   ➔   2. แปลง   ➔   3. สร้าง CTL",
        "no_file":        "📄 ยังไม่ได้เลือกไฟล์",
        "selected":       "📄 เลือกแล้ว : {name}",
        "waiting":        " กำลังรอไฟล์...",
        "file":           " ไฟล์: {name}",
        "objects":        "{o} อ็อบเจกต์  |  {m} ข้อความ  |  {d} ข้อมูล",
        "eventb_output":  "ผลลัพธ์ EVENT-B",
        "ctl_output":     "ผลลัพธ์ AI CTL",
        "chat_title":     "แชต AI EVENT-B",
        "clear":          "ล้าง",
        "send":           "ส่ง",
        "newline_hint":   "Shift+Enter เพื่อขึ้นบรรทัดใหม่",
        "you":            "คุณ",
        "ai":             "AI EVENT-B",
        "lang_btn":       "🌐 EN",
        "warn":           "เตือน",
        "select_first":   "กรุณาเลือกไฟล์ XML ก่อน",
        "ai_analyzing":   "กำลังส่งข้อมูลให้ Ollama วิเคราะห์ CTL...\n",
        "success":        "สำเร็จ",
        "exported":       "ส่งออกแล้ว:\n{path}\n\nนำเข้า Rodin ด้วย File → Import → Existing Projects into Workspace",
        "import_ok_title": "นำเข้าสำเร็จ",
        "import_ok":       "✅ เป็น Sequence Diagram ที่ถูกต้อง\n\nไฟล์: {name}\n{o} object  |  {m} message  |  {d} data",
        "import_warn_title": "นำเข้าแล้ว — ตรวจสอบลูกศร",
        "import_warn":     "นำเข้า: {name}\n{o} object  |  {m} message  |  {d} data\n\n⚠ มีลูกศร {n} เส้นที่ไม่มีข้อความ (ถูกข้าม):\n{items}\n\nกรุณาใส่ข้อความกำกับลูกศรเหล่านี้ใน draw.io",
        "invalid_title":       "ไฟล์ไม่ถูกต้อง",
        "invalid_read_error":  "อ่านไฟล์ XML นี้ไม่ได้ กรุณาตรวจสอบว่าเป็นไฟล์ draw.io ที่ถูกต้อง",
        "invalid_not_drawio":  "ไฟล์นี้ไม่ใช่ไดอะแกรมของ draw.io (ไม่พบ mxCell)",
        "invalid_no_object":   "ไม่พบ Object / Lifeline — ไฟล์นี้ดูเหมือนจะไม่ใช่ Sequence Diagram",
        "invalid_no_message":  "ไม่พบ Message (เส้นลูกศรระหว่าง object) — ไฟล์นี้ดูเหมือนจะไม่ใช่ Sequence Diagram",
    },
}

# Icon shown before each toolbar button label
BTN_ICONS = {
    "choose_xml":   "📂",
    "transform":    "⚙",
    "generate_ctl": "✨",
    "export_rodin": "📦",
}


class SequenceToEventBApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.lang = "EN"
        self.current_filename = None
        self.master.title(TRANSLATIONS[self.lang]["title"])
        self.master.geometry("1360x820")
        try:
            self._win_icon = tk.PhotoImage(file=os.path.join(_ASSETS_DIR, "icon.png"))
            self.master.iconphoto(True, self._win_icon)
        except Exception:
            pass

        self.BG       = "#FFFFFF"
        self.PANEL    = "#F7F7F7"
        self.CARD     = "#FFFFFF"
        self.TEXT     = "#111111"
        self.MUTED    = "#8D8D8D"
        self.BORDER   = "#EAEAEA"
        self.CHAT_ME    = "#111111"
        self.CHAT_ME_FG = "#FFFFFF"
        self.CHAT_AI    = "#F2F2F2"
        self.CHAT_AI_FG = "#111111"

        self.FONT_H1   = ("Segoe UI", 16, "bold")
        self.FONT_UI   = ("Segoe UI", 10)
        self.FONT_BOLD = ("Segoe UI", 10, "bold")
        self.FONT_SM   = ("Segoe UI", 9)
        self.FONT_MONO = ("Consolas", 9)

        self.master.configure(bg=self.BG)
        self.current_xml_path = None
        self._chat_history = []
        self._bubble_names = []   # (label_widget, is_user) for re-translation

        self._build_ui()

    # ── i18n ────────────────────────────────────────────────────────────────────

    def t(self, key, **kwargs):
        text = TRANSLATIONS[self.lang].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _btn_label(self, key):
        """Toolbar button caption: icon + uppercased translated label."""
        icon = BTN_ICONS.get(key, "")
        label = self.t(key).upper()
        return f"{icon}  {label}" if icon else label

    def _toggle_language(self):
        self.lang = "TH" if self.lang == "EN" else "EN"
        self._apply_language()

    def _apply_language(self):
        self.master.title(self.t("title"))
        self.btn_choose_xml.configure(text=self._btn_label("choose_xml"))
        self.btn_transform.configure(text=self._btn_label("transform"))
        self.btn_generate_ctl.configure(text=self._btn_label("generate_ctl"))
        self.btn_export_rodin.configure(text=self._btn_label("export_rodin"))
        self.btn_lang.configure(text=self.t("lang_btn"))
        self.lbl_workflow.config(text=self.t("workflow"))
        self.lbl_eventb_hdr.config(text=self.t("eventb_output"))
        self.lbl_ctl_hdr.config(text=self.t("ctl_output"))
        self.lbl_chat_hdr.config(text=self.t("chat_title"))
        self.btn_clear.configure(text=self.t("clear"))
        self._btn_send.configure(text=f"{self.t('send')}  ➤")
        self.lbl_newline_hint.config(text=self.t("newline_hint"))

        # Dynamic / stateful labels
        if self.current_filename:
            self.lbl_top_file.config(text=self.t("selected", name=self.current_filename))
            self.lbl_file.config(text=self.t("file", name=self.current_filename))
        else:
            self.lbl_top_file.config(text=self.t("no_file"))
            self.lbl_file.config(text=self.t("waiting"))

        # Existing chat bubble name labels
        for lbl, is_user in self._bubble_names:
            try:
                lbl.configure(text=self.t("you") if is_user else self.t("ai"))
            except tk.TclError:
                pass

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_subheader()
        self._build_statusbar()
        body = tk.Frame(self.master, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._build_editor(body)
        tk.Frame(body, bg=self.BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self._build_chat(body)

    def _build_topbar(self):
        bar = tk.Frame(self.master, bg=self.BG, height=60)
        bar.pack(fill=tk.X, padx=10, pady=5)
        bar.pack_propagate(False)

        logo = tk.Frame(bar, bg=self.BG)
        logo.pack(side=tk.LEFT, padx=10)
        try:
            from PIL import Image
            _img = Image.open(os.path.join(_ASSETS_DIR, "logo.png"))
            ratio = _img.width / _img.height
            self._logo_img = ctk.CTkImage(light_image=_img, dark_image=_img,
                                          size=(int(46 * ratio), 46))
            ctk.CTkLabel(logo, image=self._logo_img, text="").pack(side=tk.LEFT)
        except Exception:
            tk.Label(logo, text="ChronoSeq", font=self.FONT_H1, bg=self.BG, fg=self.TEXT).pack(side=tk.LEFT)
            tk.Label(logo, text="-B", font=self.FONT_H1, bg=self.BG, fg=self.MUTED).pack(side=tk.LEFT)

        tk.Frame(bar, bg=self.BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=15, padx=15)

        # Version is no longer user-editable; keep a fixed default so the
        # Event-B / Rodin generators still receive a version number.
        self.version_var = tk.IntVar(value=1)

        buttons = {}
        for key, cmd in [
            ("choose_xml",   self.open_xml_file),
            ("transform",    self.run_transform),
            ("generate_ctl", self.run_ai_ctl),
            ("export_rodin", self.export_rodin_zip),
        ]:
            primary = key == "export_rodin"   # final deliverable → highlighted
            btn = ctk.CTkButton(
                bar, text=self._btn_label(key), command=cmd,
                fg_color="#111111" if primary else "#FFFFFF",
                text_color="#FFFFFF" if primary else "#222222",
                hover_color="#2C2C2C" if primary else "#F2F2F2",
                border_width=0 if primary else 1,
                border_color="#E4E4E4",
                corner_radius=10, font=("Segoe UI", 11, "bold"),
                width=150, height=40, cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=5, pady=10)
            buttons[key] = btn
        self.btn_choose_xml   = buttons["choose_xml"]
        self.btn_transform    = buttons["transform"]
        self.btn_generate_ctl = buttons["generate_ctl"]
        self.btn_export_rodin = buttons["export_rodin"]

        vf = tk.Frame(bar, bg=self.BG)
        vf.pack(side=tk.RIGHT, padx=10)
        self.btn_lang = ctk.CTkButton(
            vf, text=self.t("lang_btn"), command=self._toggle_language,
            fg_color="#FFFFFF", text_color="#222222", hover_color="#F2F2F2",
            border_width=1, border_color="#E4E4E4",
            corner_radius=10, font=("Segoe UI", 11, "bold"),
            width=92, height=40, cursor="hand2"
        )
        self.btn_lang.pack(side=tk.RIGHT, padx=(10, 0))

    def _build_subheader(self):
        sub = tk.Frame(self.master, bg=self.BG)
        sub.pack(fill=tk.X, padx=15, pady=(0, 5))
        guide_frame = ctk.CTkFrame(sub, fg_color=self.PANEL, corner_radius=10, height=36)
        guide_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        guide_frame.pack_propagate(False)
        self.lbl_workflow = tk.Label(guide_frame,
                 text=self.t("workflow"),
                 bg=self.PANEL, fg=self.MUTED, font=self.FONT_SM)
        self.lbl_workflow.pack(side=tk.LEFT, padx=15, pady=8)
        self.lbl_top_file = tk.Label(guide_frame, text=self.t("no_file"),
                                     bg=self.PANEL, fg=self.MUTED, font=self.FONT_BOLD)
        self.lbl_top_file.pack(side=tk.RIGHT, padx=15, pady=8)

    def _build_statusbar(self):
        bar = tk.Frame(self.master, bg=self.PANEL, height=30)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        self.lbl_file = tk.Label(bar, text=self.t("waiting"),
                                 bg=self.PANEL, fg=self.MUTED, font=self.FONT_SM, anchor="w")
        self.lbl_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.lbl_objects = tk.Label(bar, text="", bg=self.PANEL, fg=self.TEXT, font=self.FONT_SM, anchor="e")
        self.lbl_objects.pack(side=tk.RIGHT, padx=15)

    def _enable_wheel_scroll(self, widget):
        """Make the mouse wheel scroll a Text widget vertically (Win/Mac/Linux)."""
        def _on_wheel(event):
            if event.num == 4:          # Linux scroll up
                widget.yview_scroll(-3, "units")
            elif event.num == 5:        # Linux scroll down
                widget.yview_scroll(3, "units")
            else:                       # Windows / macOS
                widget.yview_scroll(int(-1 * (event.delta / 120)) * 3, "units")
            return "break"
        widget.bind("<MouseWheel>", _on_wheel)
        widget.bind("<Button-4>", _on_wheel)
        widget.bind("<Button-5>", _on_wheel)

    def _enable_select_all(self, widget):
        """Select-all + copy on a Text widget for Windows/Linux (Ctrl) and macOS
        (Command). tkinter's default Ctrl+A only jumps to the line start."""
        def _sel(event=None):
            widget.focus_set()
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
            return "break"

        def _copy(event=None):
            try:
                text = widget.get("sel.first", "sel.last")
            except tk.TclError:
                text = widget.get("1.0", "end-1c")   # nothing selected -> copy all
            if text:
                widget.clipboard_clear()
                widget.clipboard_append(text)
            return "break"

        widget.bind("<<SelectAll>>", _sel)
        widget.bind("<<Copy>>", _copy)
        for seq in ("<Control-a>", "<Control-A>", "<Command-a>", "<Command-A>"):
            widget.bind(seq, _sel)
        for seq in ("<Control-c>", "<Control-C>", "<Command-c>", "<Command-C>"):
            widget.bind(seq, _copy)

    def _copy_all(self, widget, btn=None):
        """Copy the whole content of a Text widget to the clipboard."""
        text = widget.get("1.0", "end-1c")
        if not text.strip():
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(text)
        self.master.update()          # flush so other apps see it
        if btn is not None:
            btn.configure(text="✓ Copied")
            btn.after(1200, lambda: btn.configure(text="📋 Copy"))

    def _build_editor(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        paned = tk.PanedWindow(frame, orient=tk.VERTICAL, bg=self.BORDER, sashwidth=5, bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        # Event-B output (top)
        top_frame = tk.Frame(paned, bg=self.BG)
        hdr1 = tk.Frame(top_frame, bg=self.BG)
        hdr1.pack(fill=tk.X, pady=(0, 5))
        self.lbl_eventb_hdr = tk.Label(hdr1, text=self.t("eventb_output"), bg=self.BG, fg=self.TEXT, font=self.FONT_BOLD)
        self.lbl_eventb_hdr.pack(side=tk.LEFT)
        self.btn_copy_eventb = ctk.CTkButton(
            hdr1, text="📋 Copy",
            command=lambda: self._copy_all(self.text_output, self.btn_copy_eventb),
            fg_color="transparent", text_color=self.MUTED, hover_color=self.BORDER,
            corner_radius=8, font=("Segoe UI", 10), width=80, height=26, cursor="hand2")
        self.btn_copy_eventb.pack(side=tk.RIGHT)
        wrap1 = tk.Frame(top_frame, bg=self.BORDER, bd=1)
        wrap1.pack(fill=tk.BOTH, expand=True)
        self.text_output = tk.Text(wrap1, wrap=tk.NONE, font=self.FONT_MONO,
                                   bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT,
                                   selectbackground=self.MUTED, selectforeground=self.BG,
                                   relief=tk.FLAT, bd=0, padx=20, pady=20, undo=True)
        vsb1 = tk.Scrollbar(wrap1, orient=tk.VERTICAL, command=self.text_output.yview,
                             bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        hsb1 = tk.Scrollbar(wrap1, orient=tk.HORIZONTAL, command=self.text_output.xview,
                             bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        self.text_output.configure(yscrollcommand=vsb1.set, xscrollcommand=hsb1.set)
        vsb1.pack(side=tk.RIGHT, fill=tk.Y)
        hsb1.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_output.pack(fill=tk.BOTH, expand=True)
        self._enable_wheel_scroll(self.text_output)
        self._enable_select_all(self.text_output)
        paned.add(top_frame, minsize=200)

        # AI CTL output (bottom)
        bot_frame = tk.Frame(paned, bg=self.BG)
        hdr2 = tk.Frame(bot_frame, bg=self.BG)
        hdr2.pack(fill=tk.X, pady=(10, 5))
        self.lbl_ctl_hdr = tk.Label(hdr2, text=self.t("ctl_output"), bg=self.BG, fg=self.TEXT, font=self.FONT_BOLD)
        self.lbl_ctl_hdr.pack(side=tk.LEFT)
        self.btn_copy_ctl = ctk.CTkButton(
            hdr2, text="📋 Copy",
            command=lambda: self._copy_all(self.text_ctl, self.btn_copy_ctl),
            fg_color="transparent", text_color=self.MUTED, hover_color=self.BORDER,
            corner_radius=8, font=("Segoe UI", 10), width=80, height=26, cursor="hand2")
        self.btn_copy_ctl.pack(side=tk.RIGHT)
        wrap2 = tk.Frame(bot_frame, bg=self.BORDER, bd=1)
        wrap2.pack(fill=tk.BOTH, expand=True)
        self.text_ctl = tk.Text(wrap2, wrap=tk.NONE, font=self.FONT_MONO,
                                bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT,
                                selectbackground=self.MUTED, selectforeground=self.BG,
                                relief=tk.FLAT, bd=0, padx=20, pady=20, undo=True)
        vsb2 = tk.Scrollbar(wrap2, orient=tk.VERTICAL, command=self.text_ctl.yview,
                             bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        hsb2 = tk.Scrollbar(wrap2, orient=tk.HORIZONTAL, command=self.text_ctl.xview,
                             bg=self.BG, troughcolor=self.PANEL, relief=tk.FLAT, bd=0)
        self.text_ctl.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)
        hsb2.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_ctl.pack(fill=tk.BOTH, expand=True)
        self._enable_wheel_scroll(self.text_ctl)
        self._enable_select_all(self.text_ctl)
        paned.add(bot_frame, minsize=150)

    def _build_chat(self, parent):
        frame = tk.Frame(parent, bg=self.BG, width=400)
        frame.pack(side=tk.RIGHT, fill=tk.Y)
        frame.pack_propagate(False)

        hdr = tk.Frame(frame, bg=self.BG, height=38)
        hdr.pack(fill=tk.X, pady=(0, 5))
        hdr.pack_propagate(False)
        self.lbl_chat_hdr = tk.Label(hdr, text=self.t("chat_title"), bg=self.BG, fg=self.TEXT, font=self.FONT_BOLD)
        self.lbl_chat_hdr.pack(side=tk.LEFT)
        self.btn_clear = ctk.CTkButton(hdr, text=self.t("clear"), command=self._clear_chat,
                      fg_color="transparent", text_color=self.MUTED, hover_color=self.BORDER,
                      corner_radius=10, font=("Segoe UI", 10), width=60, height=28, cursor="hand2")
        self.btn_clear.pack(side=tk.RIGHT)

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
        self._chat_inner.bind("<Configure>", lambda e: self._chat_canvas.configure(
            scrollregion=self._chat_canvas.bbox("all")))
        self._chat_canvas.bind("<Configure>", lambda e: self._chat_canvas.itemconfig(
            self._chat_win, width=e.width))

        inp = tk.Frame(frame, bg=self.BG, pady=10)
        inp.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(inp, bg=self.BORDER, height=1).pack(fill=tk.X, pady=(0, 10))
        self._chat_input = ctk.CTkTextbox(inp, height=70, wrap="word",
                                          fg_color=self.PANEL, text_color=self.TEXT,
                                          font=self.FONT_UI, corner_radius=15, border_width=0)
        self._chat_input.pack(fill=tk.X, padx=5)
        self._chat_input.bind("<Return>", self._on_enter)
        self._chat_input.bind("<Shift-Return>", lambda e: None)

        btn_row = tk.Frame(inp, bg=self.BG)
        btn_row.pack(fill=tk.X, pady=(10, 0))
        self._btn_send = ctk.CTkButton(btn_row, text=f"{self.t('send')}  ➤", command=self._send_chat,
                                       fg_color="#111111", text_color="#FFFFFF", hover_color="#2C2C2C",
                                       corner_radius=10, font=("Segoe UI", 11, "bold"),
                                       width=96, height=38, cursor="hand2")
        self._btn_send.pack(side=tk.RIGHT)
        self.lbl_newline_hint = tk.Label(btn_row, text=self.t("newline_hint"), bg=self.BG, fg=self.MUTED,
                 font=self.FONT_SM)
        self.lbl_newline_hint.pack(side=tk.RIGHT, padx=10)

    # ── Chat logic ────────────────────────────────────────────────────────────

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
        threading.Thread(target=self._ollama_worker, daemon=True).start()

    def _get_model_context(self):
        """Build (and cache) a system prompt describing the currently-loaded model."""
        if not self.current_xml_path:
            return None
        if getattr(self, "_ctx_cache_path", None) == self.current_xml_path:
            return self._ctx_cache_text
        text = None
        try:
            base_name = extract_base_name_from_xml(self.current_xml_path)
            objects = extract_objects_from_xml(self.current_xml_path)
            edges = extract_detailed_sequence(self.current_xml_path)
            flows = [(f"{e['msg']}_{i}", e['sender'], e['receiver'])
                     for i, e in enumerate(edges, 1)]
            text = build_model_context(base_name, objects, flows)
        except Exception:
            text = None
        self._ctx_cache_path = self.current_xml_path
        self._ctx_cache_text = text
        return text

    def _ollama_worker(self):
        try:
            ctx = self._get_model_context()
            messages = ([{"role": "system", "content": ctx}] if ctx else []) + self._chat_history
            text = chat_with_ollama(self._model_var.get(), messages)
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
        lbl_name = self.t("you") if is_user else self.t("ai")
        name_fg = self.MUTED if is_user else self.TEXT
        name_lbl = ctk.CTkLabel(bubble, text=lbl_name, text_color=name_fg, fg_color="transparent",
                     font=self.FONT_SM)
        name_lbl.pack(anchor="w", padx=15, pady=(8, 0))
        self._bubble_names.append((name_lbl, is_user))

        # Read-only Text so the user can drag-select part of it and press ⌘/Ctrl+C
        # (a CTkLabel cannot be selected at all).
        lines = sum(max(1, -(-len(p) // 38)) for p in text.split("\n"))
        msg = tk.Text(bubble, width=38, height=min(max(lines, 1), 30), wrap="word",
                      bg=bg_color, fg=fg_color, relief=tk.FLAT, bd=0,
                      highlightthickness=0, padx=13, pady=0, cursor="xterm",
                      font=self.FONT_UI, selectbackground=self.MUTED,
                      selectforeground="#FFFFFF")
        msg.insert("1.0", text)
        msg.pack(anchor="w", fill="x", padx=2, pady=(0, 6))
        self._make_readonly_selectable(msg)

        if not is_user:   # AI bubbles: a copy-all button too
            cbtn = ctk.CTkButton(bubble, text="📋 Copy", width=64, height=22,
                                 corner_radius=8, font=("Segoe UI", 10),
                                 fg_color="transparent", text_color=self.MUTED,
                                 hover_color=self.BORDER, cursor="hand2")
            cbtn.configure(command=lambda t=text, b=cbtn: self._copy_text(t, b))
            cbtn.pack(anchor="e", padx=10, pady=(0, 8))
        self._chat_canvas.update_idletasks()
        self._chat_canvas.yview_moveto(1.0)

    def _make_readonly_selectable(self, widget):
        """Text widget that can't be edited but can be drag-selected and copied."""
        def _copy(event=None):
            try:
                sel = widget.get("sel.first", "sel.last")
            except tk.TclError:
                sel = ""
            if sel:
                self.master.clipboard_clear()
                self.master.clipboard_append(sel)
                self.master.update()
            return "break"

        def _select_all(event=None):
            widget.tag_add("sel", "1.0", "end-1c")
            return "break"

        widget.bind("<Key>", lambda e: "break")          # block typing (keep selection/copy)
        widget.bind("<<Copy>>", _copy)
        for seq in ("<Command-c>", "<Control-c>", "<Command-C>", "<Control-C>"):
            widget.bind(seq, _copy)
        for seq in ("<Command-a>", "<Control-a>", "<Command-A>", "<Control-A>"):
            widget.bind(seq, _select_all)

    def _copy_text(self, text, btn=None):
        """Copy raw text to the clipboard (used by chat bubbles)."""
        if not text.strip():
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(text)
        self.master.update()          # flush so other apps see it
        if btn is not None:
            btn.configure(text="✓ Copied")
            btn.after(1200, lambda: btn.configure(text="📋 Copy"))

    def _clear_chat(self):
        for w in self._chat_inner.winfo_children(): w.destroy()
        self._chat_history.clear()
        self._bubble_names.clear()

    # ── Action handlers ───────────────────────────────────────────────────────

    def open_xml_file(self):
        path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if not path: return

        # Only accept real Sequence Diagrams — reject anything else with an alert
        ok, reason = validate_sequence_diagram(path)
        if not ok:
            messagebox.showerror(self.t("invalid_title"), self.t(f"invalid_{reason}"))
            return

        self.current_xml_path = path
        self._ctx_cache_path = None       # force chat to rebuild model context for the new import
        filename = path.split("/")[-1]
        self.current_filename = filename
        self.lbl_file.config(text=self.t("file", name=filename), fg=self.TEXT)
        self.lbl_top_file.config(text=self.t("selected", name=filename), fg=self.TEXT)
        obj = extract_objects_from_xml(path)
        msg, data = extract_messages_from_xml(path)
        self.lbl_objects.config(text=self.t("objects", o=len(obj), m=len(msg), d=len(data)))

        warns = get_message_warnings(path)
        if warns:
            items = "\n".join(f"• {w}" for w in warns)
            messagebox.showwarning(
                self.t("import_warn_title"),
                self.t("import_warn", name=filename, o=len(obj), m=len(msg),
                        d=len(data), n=len(warns), items=items),
            )
        else:
            messagebox.showinfo(
                self.t("import_ok_title"),
                self.t("import_ok", name=filename, o=len(obj), m=len(msg), d=len(data)),
            )

    def run_transform(self):
        if not self.current_xml_path:
            messagebox.showwarning(self.t("warn"), self.t("select_first"))
            return
        res = apply_rules_1_and_2(self.current_xml_path, self.version_var.get())
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, res)

    def run_ai_ctl(self):
        if not self.current_xml_path:
            messagebox.showwarning(self.t("warn"), self.t("select_first"))
            return
        self.text_ctl.delete("1.0", tk.END)
        self.text_ctl.insert(tk.END, "\n" + "="*50 + "\n")
        self.text_ctl.insert(tk.END, self.t("ai_analyzing"))
        self.text_ctl.see(tk.END)
        self.master.update_idletasks()
        try:
            base_name = extract_base_name_from_xml(self.current_xml_path)
            objects = extract_objects_from_xml(self.current_xml_path)
            edges = extract_detailed_sequence(self.current_xml_path)
            flows = [(f"{e['msg']}_{i}", e['sender'], e['receiver'])
                     for i, e in enumerate(edges, 1)]
            ctl_result = generate_ctl_with_ollama(base_name, objects, flows)
            self.text_ctl.insert(tk.END, f"\n✨ [AI Generated CTL Properties]:\n{ctl_result}\n")
            self.text_ctl.insert(tk.END, "="*50 + "\n")
            self.text_ctl.see(tk.END)
        except Exception as e:
            messagebox.showerror("AI Error", str(e))

    def export_rodin_zip(self):
        if not self.current_xml_path:
            messagebox.showwarning(self.t("warn"), self.t("select_first"))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Zip", "*.zip"), ("All", "*.*")],
            title="Save Rodin Project ZIP"
        )
        if not path: return
        try:
            data = generate_rodin_zip(self.current_xml_path, self.version_var.get())
            with open(path, 'wb') as f:
                f.write(data)
            messagebox.showinfo(self.t("success"), self.t("exported", path=path))
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
