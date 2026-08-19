# ChronoSeq-B

**ChronoSeq-B** is a desktop tool that transforms UML **Sequence Diagrams**
(drawn in [draw.io](https://app.diagrams.net) / diagrams.net) into formal
**Event-B** models ready for import into **Rodin**, and uses a local LLM
(via [Ollama](https://ollama.com)) to synthesise temporal-logic properties
(CTL/LTL) for checking in **ProB**.

It was built as part of a master's thesis on automated
sequence-diagram-to-Event-B transformation.

```
Sequence Diagram (.xml)  ─▶  Event-B model  ─▶  Rodin project (.zip)
        │                                              │
        └────────────▶  CTL/LTL properties  ──▶  ProB verification
                         (Ollama, local LLM)
```

---

## Features

- **SD → Event-B transformation** following 10 transformation rules
  (objects, messages, data, returns, `opt` / `alt` / `loop` / `par`
  fragments, nested fragments, and time constraints).
- **Rodin export** as a ready-to-import `.zip` containing a context
  (`.buc`), a machine (`.bum`), and a `.project` descriptor, using
  Rodin-correct Unicode operators and `partition` axioms.
- **Time modelling** — duration constraints `{0..n}` and delay windows
  `{t..t+δ}` become integer clock variables (`t_time`, `t_delay`,
  `t_success`).
- **AI property synthesis** — generates reachability / response / safety
  properties grounded in the actual generated machine, plus an interactive
  chat that is aware of the loaded model.
- **Import validation** — rejects files that are not real sequence diagrams
  and warns about unlabelled arrows.
- **Bilingual UI** (Thai ⇄ English) with copyable output.

---

## Requirements

- **Python ≥ 3.12**
- [`customtkinter`](https://pypi.org/project/customtkinter/) — GUI widgets
- [`ollama`](https://pypi.org/project/ollama/) — Python client for the local LLM
- `Pillow` *(optional)* — renders the app logo/icon (the app still runs without it)
- **[Ollama](https://ollama.com)** running locally, with a model pulled
  (default: `gemma2:2b`)
- **[Rodin](https://www.rodin-b-sharp.org/)** + **ProB** to open the exported
  model and run verification

`tkinter` ships with the Python standard library.

---

## Installation

```bash
# clone
git clone https://github.com/Kengelite/ProjectEvent-b.git
cd ProjectEvent-b

# install dependencies
pip install customtkinter ollama pillow

# start Ollama and pull the default model (in a separate terminal)
ollama serve
ollama pull gemma2:2b
```

> The LLM endpoint and model are set in [`ai_service.py`](ai_service.py)
> (`OLLAMA_HOST`, `DEFAULT_MODEL`).

---

## Usage

```bash
python index.py
```

Then, in the app:

1. **Import** a sequence-diagram `.xml` exported from draw.io.
   Invalid files are rejected; a summary (objects / messages / data) is shown.
2. **Transform** — view the generated Event-B model (context + machine).
3. **Generate CTL** — synthesise temporal properties with the local LLM,
   or ask follow-up questions in the chat.
4. **Export Rodin** — save a `.zip` project.
5. In **Rodin**: *File → Import → Existing Projects into Workspace →
   Select archive file*, pick the `.zip`. The static checker and proof
   obligation generator run automatically.
6. Run temporal properties in **ProB** (paste the ASCII form, e.g.
   `G({m_1 : sentMessages} => F({m_2 : sentMessages}))`).

Each export is named with a running identifier `M1`, `M2`, … (logged under
`logs/`) so re-imports never clash with an existing Rodin project.

---

## Project layout

| File | Responsibility |
|------|----------------|
| [`index.py`](index.py) | Entry point — launches the Tk app |
| [`ui.py`](ui.py) | GUI, i18n, import validation, chat, clipboard |
| [`xml_parser.py`](xml_parser.py) | Parse draw.io SD → objects, messages, data, fragments, time; build fragment/loop/time models |
| [`eventb_generator.py`](eventb_generator.py) | Render the Event-B model as text (on-screen display) |
| [`rodin_exporter.py`](rodin_exporter.py) | Emit the Rodin `.buc` / `.bum` / `.project` and pack the `.zip` |
| [`ai_service.py`](ai_service.py) | Prompt construction + Ollama calls (property synthesis and chat) |
| [`constants.py`](constants.py) | Shared constants |
| `assets/` | Logo and window icon |

---

## How the transformation works

Each **message** becomes a pair of Event-B events — a `send` and a
`receive` — coordinated through a small set of state variables:

- `sentMessages` — messages already dispatched (grows monotonically)
- `receivedMessages` — messages already received (⊆ `sentMessages`)
- `sender`, `receiver` — the message ↦ object relations
- `senderdataMessages`, `receiverdataMessages` — attached data payloads
- `currentMessage` — enforces one in-flight message at a time

A `receive` event is enabled only after its `send`; a subsequent message is
guarded by the reception of its predecessor, preserving the diagram's order.

**Combined fragments** contribute control variables and guards:

| Fragment | Effect on the machine |
|----------|-----------------------|
| `opt`  | condition variable + guard on body events (`_optX` suffix) |
| `alt`  | mutually exclusive branch guards (symbolic values become enumerated constants) |
| `loop` | counter variable + `checkloop_*` event that increments it under the bound |
| `par`  | bookkeeping counter; regions linearised by completion guards |
| nested | guards of every enclosing fragment are conjoined (band containment) |

**Time constraints** on a message emit `t_time_<id>` (duration),
`t_delay_<id>` (delay), and `t_success_<id> = t_time + t_delay` (realised
delivery instant).

---

## Notes

- The exported `.zip` contains only the source files; Rodin generates the
  static-checker output (`.bcc`/`.bcm`) and proof obligations on import.
- Proof obligations are discharged in **Rodin**; temporal (CTL/LTL)
  properties are checked in **ProB**.
- Property formulas are shown in mathematical notation for readability; when
  pasting into ProB, use its ASCII syntax (`:` for `∈`, `=>` for `⇒`,
  `or` for `∨`).
