"""Apply the same edit to the Event-B display text (`:=`) and to the Rodin .bum (`≔`),
so the text the LLM reads is exactly the model Rodin proves.

ops = {
  "add_inv":          [predicate, ...]                 appended after the last invariant
  "set_init":         {var: value}                     INITIALISATION action for var
  "replace_in_event": [(event, old, new), ...]         first occurrence inside that event
  "remove_guard":     [(event, "grdN"), ...]           guards are relabelled contiguously
}
Minus must be written "−" (U+2212): Rodin's parser rejects ASCII operator spellings.
"""
import re


def xml_attr(value):
    return (value.replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _text_block(lines, header):
    s = next(i for i, l in enumerate(lines) if l.strip() == header)
    e = next(i for i in range(s + 1, len(lines)) if lines[i].strip() == "END")
    return s, e


def mutate_text(txt, ops, new_labels):
    lines = txt.split("\n")
    last_inv = max(i for i, l in enumerate(lines) if re.match(r"^ {4}inv\d+:", l))
    for k, pred in enumerate(ops.get("add_inv", [])):
        lines.insert(last_inv + 1 + k, f"    {new_labels[k]}: {pred}")
    for var, val in ops.get("set_init", {}).items():
        s, e = _text_block(lines, "INITIALISATION BEGIN")
        i = next(i for i in range(s, e) if re.match(rf"^\s+act\d+: {re.escape(var)} :[=∈]", lines[i]))
        lines[i] = re.sub(rf"({re.escape(var)}) :[=∈].*$", lambda m: f"{m.group(1)} := {val}", lines[i])
    for ev, old, new in ops.get("replace_in_event", []):
        s, e = _text_block(lines, ev)
        i = next(i for i in range(s, e) if old in lines[i])
        lines[i] = lines[i].replace(old, new, 1)
    for ev, grd in ops.get("remove_guard", []):
        s, e = _text_block(lines, ev)
        i = next(i for i in range(s, e) if lines[i].strip().startswith(f"{grd}:"))
        del lines[i]
        s, e = _text_block(lines, ev)
        n = 1
        for j in range(s, e):
            if re.match(r"^\s+grd\d+:", lines[j]):
                lines[j] = re.sub(r"grd\d+:", f"grd{n}:", lines[j], count=1)
                n += 1
    return "\n".join(lines)


def mutate_bum(bum, ops, new_labels):
    lines = bum.split("\n")
    last_inv = max(i for i, l in enumerate(lines) if "<org.eventb.core.invariant " in l)
    for k, pred in enumerate(ops.get("add_inv", [])):
        lines.insert(last_inv + 1 + k,
                     f'<org.eventb.core.invariant name="internal_mut{k + 1}" '
                     f'org.eventb.core.label="{new_labels[k]}" '
                     f'org.eventb.core.predicate="{xml_attr(pred)}" '
                     f'org.eventb.core.theorem="false"/>')

    def ev_block(label):
        s = next(i for i, l in enumerate(lines)
                 if "<org.eventb.core.event " in l and f'org.eventb.core.label="{label}"' in l)
        e = next(i for i in range(s, len(lines)) if lines[i].startswith("</org.eventb.core.event>"))
        return s, e

    for var, val in ops.get("set_init", {}).items():
        s, e = ev_block("INITIALISATION")
        i = next(i for i in range(s, e) if f'org.eventb.core.assignment="{var} ' in lines[i])
        new_attr = f'org.eventb.core.assignment="{xml_attr(f"{var} ≔ {val}")}"'
        lines[i] = re.sub(r'org\.eventb\.core\.assignment="[^"]*"', lambda m: new_attr, lines[i])
    for ev, old, new in ops.get("replace_in_event", []):
        old_b, new_b = xml_attr(old.replace(":=", "≔")), xml_attr(new.replace(":=", "≔"))
        s, e = ev_block(ev)
        i = next(i for i in range(s, e) if old_b in lines[i])
        lines[i] = lines[i].replace(old_b, new_b, 1)
    for ev, grd in ops.get("remove_guard", []):
        s, e = ev_block(ev)
        i = next(i for i in range(s, e)
                 if "<org.eventb.core.guard " in lines[i] and f'org.eventb.core.label="{grd}"' in lines[i])
        del lines[i]
        s, e = ev_block(ev)
        n = 1
        for j in range(s, e):
            if "<org.eventb.core.guard " in lines[j]:
                lines[j] = re.sub(r'org\.eventb\.core\.label="grd\d+"',
                                  f'org.eventb.core.label="grd{n}"', lines[j])
                n += 1
    return "\n".join(lines)


def init_action_label(bum, var):
    """Label (actN) of the INITIALISATION action that assigns var."""
    m = re.search(rf'assignment="{re.escape(var)} [^"]*" org\.eventb\.core\.label="(act\d+)"', bum)
    return m.group(1)


def checkloop_event(txt, var, bound):
    """Name of the checkloop event that counts var up to bound."""
    lines = txt.split("\n")
    for i, l in enumerate(lines):
        if re.match(r"^ {4}checkloop\S*$", l):
            s, e = _text_block(lines, l.strip())
            if any(f"{var} < {bound}" in x for x in lines[s:e]):
                return l.strip()
    raise KeyError(f"no checkloop for {var} < {bound}")


def count_consistency(txt, bum):
    """(invariants, guards) counted in the text and in the .bum — must agree."""
    return ((len(re.findall(r"^ {4}inv\d+:", txt, re.M)), bum.count("<org.eventb.core.invariant ")),
            (len(re.findall(r"^\s+grd\d+:", txt, re.M)), bum.count("<org.eventb.core.guard ")))
