"""Extract two trees from each converted Event-B model: an event tree and a guard tree.

    python tools/extract_trees.py

Guard tree: only the condition guards that come from the diagram (loop / alt / opt conditions), not the
guards the converter adds for message order. Guards on the same expression share a letter and are numbered
by branch: mode = GOLD → b1, mode = SILVER → b2. An event's guards are listed outer to inner, so each event
gives one path (a1 -> b1 -> c1) and the paths together form the tree.

Event tree: send m → receive m, and receive p → send m when send m has the guard p ∈ receivedMessages.
A loop-counter event hangs under the last event of its loop body. Events are coded like guards: the letter is
the step, the number the alternative where the tree branches (an alt, or loop-again vs. go on). Events at the
same step of sibling branches share a letter (m1 / m2 / m3); an event where branches merge starts a new letter.

Writes, per model: guard_tree.txt and event_tree.txt (the paths only, one per line: a1,b1), guard_codes.txt and
event_codes.txt (what each code means, with the tree drawn), and guard_tree.json / event_tree.json (all of it as
data). The event files name conditions by their text, never by guard code, so the two code sets never mix. model_001's model.txt has event names only, so its events and guards
are read from the Rodin proof-obligation file (.bpo) instead; one of its events has no name there.
"""
import glob, html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
OPS = re.compile(r"\s(≤|≥|<|>|=|≠|∈|∉|⊆)\s")
STRUCT = re.compile(r"(∉|∈) sentMessages$|↦ \w+ ∈ (sender|receiver)$|∉ receivedMessages$|^currentMessage = "
                    r"|∈ receivedMessages")


def parse(path):
    """Events in file order: [(name, [guard, ...])]."""
    events, cur, in_guard, started = [], None, False, False
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s == "EVENTS":
            started = True
        elif not started:
            continue
        elif re.fullmatch(r"[A-Za-z_]\w*", s) and s not in ("WHEN", "THEN", "END", "BEGIN", "EVENTS", "ANY", "WHERE"):
            cur = (s, [])
            events.append(cur)
        elif s == "WHEN":
            in_guard = True
        elif s in ("THEN", "END"):
            in_guard = False
        elif in_guard and cur:
            m = re.match(r"grd\d+:\s*(.*)$", s)
            if m:
                cur[1].append(m.group(1).strip())
    return events


def from_bpo(path):
    """Events and guards as Rodin stored them in a .bpo (used when model.txt has no guards)."""
    s = open(path, encoding="utf-8").read()
    names = {}
    for m in re.finditer(r'<org.eventb.core.poSequent name="([^"]+)".*?</org.eventb.core.poSequent>', s, re.S):
        for eid in re.findall(r'poRole="DEFAULT" org.eventb.core.source="[^"]*event#([^"|]+)"', m.group(0)):
            names.setdefault(html.unescape(eid), html.unescape(m.group(1)).split("/")[0])
    guards = {}
    for m in re.finditer(r'predicate="([^"]*)" org.eventb.core.source="[^"]*event#([^"|]+)\|org.eventb.core.guard#([^"]+)"', s):
        g = html.unescape(m.group(1)).replace("(∅ ⦂ ℙ(Messages))", "∅")
        g = re.sub(r"\s*(∉|∈|∨|≥|≤|≠|=|<|>)\s*", r" \1 ", g).strip()
        guards.setdefault(html.unescape(m.group(2)), {})[html.unescape(m.group(3))] = g
    return [(names.get(e, f"unnamed_event_{e}"), [gs[k] for k in sorted(gs)]) for e, gs in sorted(guards.items())]


def lhs(g):
    m = OPS.search(g)
    return g[:m.start()].strip() if m else g


def letters(k):
    s = ""
    k += 1
    while k:
        k, r = divmod(k - 1, 26)
        s = chr(97 + r) + s
    return s


def guard_codes(events):
    """Code every diagram condition: same left-hand expression → same letter, branches numbered."""
    letter, codes = {}, {}
    for _, guards in events:
        for g in guards:
            if STRUCT.search(g) or g in codes:
                continue
            key = lhs(g)
            if key not in letter:
                letter[key] = [letters(len(letter)), 0]
            letter[key][1] += 1
            codes[g] = f"{letter[key][0]}{letter[key][1]}"
    return codes


def event_codes(children):
    """Letter = step, number = alternative. Walk depth-first from the root. The children of a branch point share
    a letter; if one of them is a merge point (several parents) they all take that merge point's letter, so the
    code does not depend on which branch is walked first. The k-th event of a straight run after a branch keeps
    the slot of that branch (m1 → n1, m2 → n2); any other event starts a letter of its own."""
    parents = {}
    for p, cs in children.items():
        for c in cs:
            parents.setdefault(c, []).append(p)
    merge = lambda x: len(parents.get(x, [])) > 1
    slot, letter, count, code = {}, {}, {}, {}
    def visit(n):
        for c in children[n]:
            if c in code:
                continue
            if len(children[n]) > 1:
                m = [x for x in children[n] if merge(x)]
                key = (("merge", m[0]), 0) if m else ((n,), 0)
            elif merge(c):
                key = (("merge", c), 0)
            elif n in slot and slot[n][0][0] != "own" and not merge(n):
                key = (slot[n][0], slot[n][1] + 1)
            else:
                key = (("own", c), 0)
            slot[c] = key
            if key not in letter:
                letter[key] = letters(len(letter))
            count[key] = count.get(key, 0) + 1
            code[c] = f"{letter[key]}{count[key]}"
            visit(c)
    visit("ROOT")
    return code


def code_order(c):
    m = re.fullmatch(r"([a-z]+)(\d+)", c)
    return (len(m.group(1)), m.group(1), int(m.group(2)))


def build(events):
    codes = guard_codes(events)
    path = {name: [codes[g] for g in guards if g in codes] for name, guards in events}

    # event tree
    send, recv, kind = {}, {}, {}
    for name, guards in events:
        for g in guards:
            if m := re.fullmatch(r"(\w+) ∉ sentMessages", g):
                send[m.group(1)] = name; kind[name] = ("send", m.group(1))
            elif (m := re.fullmatch(r"(\w+) ∉ receivedMessages", g)):
                recv[m.group(1)] = name; kind[name] = ("receive", m.group(1))
        if name not in kind and any("∈ receivedMessages" in g for g in guards):
            kind[name] = ("other", None)
    children = {n: [] for n, _ in events}
    children["ROOT"] = []
    for name, guards in events:
        k = kind.get(name)
        if not k:
            continue
        if k[0] == "receive":
            parents = [send[k[1]]] if k[1] in send else ["ROOT"]
        else:
            prev = [p for g in guards if "∈ receivedMessages" in g for p in re.findall(r"(\w+) ∈ receivedMessages", g)]
            sent = [p for g in guards for p in re.findall(r"^(\w+) ∈ sentMessages$", g) if p != k[1]]
            parents = [recv[p] for p in prev if p in recv] + [send[p] for p in sent if p in send] or ["ROOT"]
        for p in parents:
            children[p].append(name)
    # loop-counter events: under the last event(s) of the loop body
    loops = {}
    for name, _ in events:
        if name in kind or not path[name]:
            continue
        body = [n for n, _ in events if n in kind and path[n][:len(path[name])] == path[name]]
        ends = [n for n in body if not any(c in body for c in children[n])]
        m = re.match(r"checkloop_(\w+?_\d+)_", name)
        back = send.get(m.group(1)) if m else None
        loops[name] = back or (body[0] if body else None)
        for n in ends:
            children[n].append(name)
    ev_code = event_codes(children)
    def expand(n):
        return {"event": n, "code": ev_code.get(n, "root"), "guards": path.get(n, []),
                **({"loop_back_to": loops[n], "loop_back_to_code": ev_code.get(loops[n])} if n in loops else {}),
                "children": [] if n in loops else [expand(c) for c in children[n]]}
    etree = expand("ROOT")
    def e_paths(t, pre):
        here = pre + ([t] if t["code"] != "root" else [])
        if not t["children"]:
            return [here]
        return [p for c in t["children"] for p in e_paths(c, here)]
    runs = e_paths(etree, [])
    event_paths = [" -> ".join(n["code"] for n in run)
                   + (f" ↺ {ev_code[run[-1]['loop_back_to']]}" if "loop_back_to" in run[-1] else "") for run in runs]

    # guard tree: walk each complete run (not a loop-back) and record conditions in the order they are met
    guard_runs = []
    for run in runs:
        if "loop_back_to" in run[-1]:
            continue
        seq = []
        for n in run:
            seq += [c for c in n["guards"] if c not in seq]
        if seq and seq not in guard_runs:
            guard_runs.append(seq)
    root = {}
    for seq in guard_runs:
        node = root
        for c in seq:
            node = node.setdefault(c, {})
    guard_paths = [" -> ".join(seq) for seq in guard_runs]
    unplaced = [n for n, _ in events if n not in ev_code]
    order = sorted(ev_code.values(), key=code_order)
    name_of = {c: n for n, c in ev_code.items()}
    return {"guard_codes": {c: g for g, c in codes.items()},
            "event_codes": {c: name_of[c] for c in order},
            "event_guards": {c: path[name_of[c]] for c in order},
            "guard_tree": root, "guard_paths": guard_paths,
            "event_tree": etree, "event_paths": event_paths, "unplaced_events": unplaced}


def draw(node, label, pre=""):
    out = []
    items = list(node.items()) if isinstance(node, dict) else node
    for k, (key, sub) in enumerate(items):
        last = k == len(items) - 1
        out.append(f"{pre}{'└── ' if last else '├── '}{label(key)}")
        out += draw(sub, label, pre + ("    " if last else "│   "))
    return out


def draw_events(t, pre="", show_guards=False):
    out = []
    for k, c in enumerate(t["children"]):
        last = k == len(t["children"]) - 1
        g = f"  (guard {' '.join(c['guards'])})" if show_guards and c["guards"] else ""
        back = f"  ↺ วนกลับไป {c['loop_back_to']}" if "loop_back_to" in c else ""
        out.append(f"{pre}{'└── ' if last else '├── '}{c['code']} {c['event']}{g}{back}")
        out += draw_events(c, pre + ("    " if last else "│   "), show_guards)
    return out


def draw_events_compact(t, pre="", width=None):
    """Same tree, but a run of single-child events is one line: e1 → e2 → e3; it splits only at a branch.
    width: wrap a long run every `width` events."""
    out = []
    for k, c in enumerate(t["children"]):
        chain = [c]
        while len(chain[-1]["children"]) == 1:
            chain.append(chain[-1]["children"][0])
        last = k == len(t["children"]) - 1
        back = f" ↺ {c_back}" if (c_back := chain[-1].get("loop_back_to_code")) else ""
        codes = [n["code"] for n in chain]
        step = width or len(codes)
        parts = [" → ".join(codes[i:i + step]) for i in range(0, len(codes), step)]
        lane = pre + ("    " if last else "│   ")
        out.append(f"{pre}{'└── ' if last else '├── '}{parts[0]}" + (" →" if len(parts) > 1 else back))
        out += [f"{lane}  {p}" + (" →" if i < len(parts) - 2 else back) for i, p in enumerate(parts[1:])]
        out += draw_events_compact(chain[-1], lane, width)
    return out


def split_tree(t):
    """The combined result as two independent parts; event nodes carry condition text, not guard codes."""
    gc = t["guard_codes"]
    def conv(n):
        m = {k: v for k, v in n.items() if k not in ("guards", "children")}
        m["conditions"] = [gc[c] for c in n["guards"]]
        m["children"] = [conv(c) for c in n["children"]]
        return m
    guard = {k: t[k] for k in ("guard_codes", "guard_tree", "guard_paths", "source")}
    event = {"event_codes": t["event_codes"],
             "event_conditions": {c: [gc[g] for g in gs] for c, gs in t["event_guards"].items()},
             "event_tree": conv(t["event_tree"]), "event_paths": t["event_paths"],
             "unplaced_events": t["unplaced_events"], "source": t["source"]}
    return guard, event


def load_tree(model_dir):
    """Both files of a model joined back into one dict (event conditions mapped to guard codes again)."""
    guard = json.load(open(os.path.join(model_dir, "guard_tree.json"), encoding="utf-8"))
    event = json.load(open(os.path.join(model_dir, "event_tree.json"), encoding="utf-8"))
    code = {g: c for c, g in guard["guard_codes"].items()}
    def conv(n):
        m = {k: v for k, v in n.items() if k not in ("conditions", "children")}
        m["guards"] = [code[g] for g in n["conditions"]]
        m["children"] = [conv(c) for c in n["children"]]
        return m
    return {**guard, "event_codes": event["event_codes"],
            "event_guards": {c: [code[g] for g in gs] for c, gs in event["event_conditions"].items()},
            "event_tree": conv(event["event_tree"]), "event_paths": event["event_paths"],
            "unplaced_events": event["unplaced_events"]}


def as_csv_path(p):
    """'a1 -> b1 ↺ e1' → 'a1,b1,↺e1'."""
    p = p.replace(" ↺ ", " -> ↺")
    return ",".join(x.strip() for x in p.split("->"))


def guard_tree_text(t):
    """guard_tree.txt: the paths only, one per line (a1,b1). Empty when the diagram has no condition."""
    return "".join(as_csv_path(p) + "\n" for p in t["guard_paths"])


def event_tree_text(t):
    """event_tree.txt: the paths only, one per line; ↺x ends a path that loops back to event x."""
    return "".join(as_csv_path(p) + "\n" for p in t["event_paths"])


def guard_codes_text(model_id, case, t):
    gc = t["guard_codes"]
    lines = [f"{model_id}  {case}  —  รหัส guard", "", "1) ความหมายของรหัส"]
    lines += [f"   {c:<4} {g}" for c, g in gc.items()] or ["   (ไม่มีเงื่อนไขจากแผนภาพ)"]
    if gc:
        lines += ["", "2) Guard tree", "   (root)"]
        lines += ["   " + l for l in draw(t["guard_tree"], lambda c: f"{c}  {gc[c]}")]
    lines += ["", "เส้นทางอยู่ในไฟล์ guard_tree.txt"]
    return "\n".join(lines) + "\n"


def event_codes_text(model_id, case, t):
    lines = [f"{model_id}  {case}  —  รหัส event", "", "1) ความหมายของรหัส"]
    lines += [f"   {c:<4} {n}" for c, n in t["event_codes"].items()]
    lines += ["", "2) Event tree แบบย่อ (event ที่ต่อกันเป็นเส้นตรงอยู่ในบรรทัดเดียว)", "   (root) INITIALISATION"]
    lines += ["   " + l for l in draw_events_compact(t["event_tree"])]
    lines += ["", "3) Event tree แบบเต็ม", "   (root) INITIALISATION"] + ["   " + l for l in draw_events(t["event_tree"])]
    lines += ["", "เส้นทางอยู่ในไฟล์ event_tree.txt (↺x = วนกลับไปที่ event x)"]
    return "\n".join(lines) + "\n"


TREE_FILES = ("guard_tree.txt", "guard_codes.txt", "guard_tree.json", "event_tree.txt", "event_codes.txt", "event_tree.json")


def main():
    n = 0
    for d in sorted(glob.glob(os.path.join(DATASET, "models", "model_*"))):
        meta = json.load(open(os.path.join(d, "meta.json")))
        events = parse(os.path.join(d, "model.txt"))
        source = "model.txt"
        if not any(g for _, g in events):
            bpo = glob.glob(os.path.join(DATASET, meta.get("rodin_raw_dir") or "-", "*.bpo"))
            if not bpo:
                print("skip (no guards):", meta["model_id"])
                continue
            events, source = from_bpo(bpo[0]), "rodin .bpo (model.txt has event names only)"
        t = build(events)
        t["source"] = source
        guard, event = split_tree(t)
        for kind, part in (("guard", guard), ("event", event)):
            json.dump(part, open(os.path.join(d, f"{kind}_tree.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        files = {"guard_tree.txt": guard_tree_text(t), "event_tree.txt": event_tree_text(t),
                 "guard_codes.txt": guard_codes_text(meta["model_id"], meta["case"], t),
                 "event_codes.txt": event_codes_text(meta["model_id"], meta["case"], t)}
        for name, body in files.items():
            open(os.path.join(d, name), "w", encoding="utf-8").write(body)
        for old in ("tree.json", "tree.txt"):
            if os.path.exists(os.path.join(d, old)):
                os.remove(os.path.join(d, old))
        n += 1
    print("trees written:", n)


if __name__ == "__main__":
    main()
