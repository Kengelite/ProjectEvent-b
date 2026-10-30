"""Check every extracted tree against the sequence diagram it came from.

    python tools/verify_trees.py [--release ../EventB_PO_Training]

The diagram (.drawio.xml) is read with its own small parser, independent of the converter and of
extract_trees.py: frames (alt / opt / loop / par), the dashed lines that split alt operands, condition texts
and messages, all by position. From that it derives what the trees must contain and compares:

    C1 messages      diagram messages = send/receive events in Event-B, same order
    C2 guards        conditions around each message = guards of its send and receive events
    C3 guard codes   one code per diagram condition, nothing extra
    C4 event order   parents of every send/receive event = what the diagram order gives
    C5 loops         one loop-counter event per loop: right guards, under the end of the body, back to its start
    C6 event codes   one code per event; at a branch the children share a letter, numbered 1..k;
                     a straight run never repeats a letter
    C7 guard paths   = the condition sequences of every way through the diagram
    C8 files         release copies (models/, data/guard_trees.jsonl, data/event_trees.jsonl,
                     trees/guard/guard_codes.csv, trees/event/event_codes.csv) = the dataset

model_001 has no diagram; its tree is checked against the Rodin .bpo instead (C1, C3, C6, C8).
A self-test breaks correct trees in ten ways and confirms the checks catch each one.
Writes trees_check.json next to this dataset and prints a summary.
"""
import argparse, csv, glob, html, itertools, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from extract_trees import load_tree     # noqa: E402


# ── diagram ────────────────────────────────────────────────────────────────
def cells(path):
    s = open(path, encoding="utf-8").read()
    for m in re.finditer(r"<mxCell ([^>]*?)/?>(.*?)(?:</mxCell>|(?=<mxCell)|$)", s, re.S):
        a, body = m.group(1), m.group(2)
        get = lambda k: (re.search(rf'{k}="([^"]*)"', a) or [None, ""])[1]
        g = re.search(r'<mxGeometry ([^>]*)', body)
        geo = {k: float(v) for k, v in re.findall(r'(x|y|width|height)="([-\d.]+)"', g.group(1))} if g else {}
        pts = [(float(x), float(y)) for x, y in re.findall(r'<mxPoint x="([-\d.]+)" y="([-\d.]+)"', body)]
        yield {"id": get("id"), "value": html.unescape(get("value")), "style": get("style"),
               "edge": get("edge") == "1", "geo": geo, "pts": pts}


def norm_cond(v):
    v = v.strip()[1:-1].strip()
    for a, b in (("==", "="), ("!=", "≠"), (">=", "≥"), ("<=", "≤")):
        v = v.replace(a, b)
    return re.sub(r"\s+", " ", v)


def diagram(path):
    """Structure: nested blocks. A block is a list of items in y order: ("msg", name), or
    {"kind", "cond", "operands": [{"cond", "items"}]} for a frame."""
    frames, seps, conds, msgs = [], [], [], []
    for c in cells(path):
        g = c["geo"]
        if "umlFrame" in c["style"]:
            frames.append({"kind": c["value"].strip(), "x": g["x"], "y": g["y"], "x2": g["x"] + g["width"],
                           "y2": g["y"] + g["height"]})
        elif c["style"].startswith("line;") and "dashed=1" in c["style"]:
            seps.append((g["x"], g["y"] + g.get("height", 0) / 2))
        elif c["value"].strip().startswith("[") and c["value"].strip().endswith("]"):
            conds.append((g["x"], g["y"], norm_cond(c["value"])))
        elif c["edge"] and c["value"].strip() and len(c["pts"]) >= 2:
            name = re.match(r"\s*([A-Za-z_]\w*)", c["value"]).group(1)
            msgs.append((c["pts"][0][1], min(c["pts"][0][0], c["pts"][1][0]), name))
    msgs.sort()
    # operands: an alt is split by the dashed lines inside it; other frames have one operand
    regions = []
    for f in frames:
        cuts = sorted(y for x, y in seps if f["x"] <= x < f["x2"] and f["y"] < y < f["y2"]
                      and not any(o is not f and o["x"] > f["x"] and o["y"] < y < o["y2"] for o in frames))
        bounds = [f["y"]] + cuts + [f["y2"]]
        f["operands"] = [{"y": bounds[k], "y2": bounds[k + 1], "x": f["x"], "x2": f["x2"], "frame": f,
                          "cond": None, "items": []} for k in range(len(bounds) - 1)]
        regions += f["operands"]
    def innermost(x, y):
        inside = [r for r in regions if r["x"] <= x <= r["x2"] and r["y"] <= y <= r["y2"]]
        return min(inside, key=lambda r: (r["y2"] - r["y"]) * (r["x2"] - r["x"])) if inside else None
    for x, y, c in conds:
        r = innermost(x, y + 1)
        r["cond"] = c
    root = {"items": []}
    def container(r):
        f = r["frame"]
        return innermost(f["x"] - 0.5, f["y"] - 0.5) if innermost(f["x"] - 0.5, f["y"] - 0.5) else None
    for f in sorted(frames, key=lambda f: f["y"]):
        outer = [r for r in regions if r["frame"] is not f and r["x"] <= f["x"] and f["x2"] <= r["x2"]
                 and r["y"] <= f["y"] and f["y2"] <= r["y2"]]
        par = min(outer, key=lambda r: (r["y2"] - r["y"]) * (r["x2"] - r["x"])) if outer else root
        par["items"].append((f["y"], "frame", f))
    for y, x, name in msgs:
        inside = [r for r in regions if r["y"] <= y <= r["y2"] and r["x"] <= x + 1 <= r["x2"]]
        r = min(inside, key=lambda r: (r["y2"] - r["y"]) * (r["x2"] - r["x"])) if inside else root
        r["items"].append((y, "msg", name))
    def tidy(node):
        out = []
        for y, kind, v in sorted(node["items"], key=lambda t: t[0]):
            if kind == "msg":
                out.append(("msg", v))
            else:
                out.append({"kind": v["kind"], "operands": [{"cond": o["cond"], "items": tidy(o)} for o in v["operands"]]})
        return out
    return tidy(root), [n for _, _, n in msgs]


def expect(block):
    """From the diagram structure: guards of each message, predecessors of each message, loops, condition paths."""
    guards, preds, loops = {}, {}, []
    def walk(items, frontier, ctx):
        for it in items:
            if isinstance(it, tuple):
                m = it[1]
                guards[m] = list(ctx)
                preds[m] = set(frontier)
                frontier = {m}
            elif it["kind"] == "alt":
                out = set()
                for op in it["operands"]:
                    out |= walk(op["items"], frontier, ctx + ([op["cond"]] if op["cond"] else []))
                frontier = out
            else:   # opt / loop / par: the converter runs every operand in order
                op = it["operands"][0]
                inner = ctx + ([op["cond"]] if op["cond"] else [])
                start = len(guards)
                end = walk([x for o in it["operands"] for x in o["items"]], frontier, inner)
                if it["kind"] == "loop":
                    first = [m for m in guards][start] if len(guards) > start else None
                    loops.append({"guards": inner, "ends": end, "first": first})
                frontier = end
        return frontier
    walk(block, set(), [])
    def ways(items, pre):
        seqs = [pre]
        for it in items:
            if isinstance(it, tuple):
                continue
            new = []
            for s in seqs:
                ops = it["operands"] if it["kind"] == "alt" else \
                    [{"cond": it["operands"][0]["cond"], "items": [x for o in it["operands"] for x in o["items"]]}]
                for op in ops:
                    add = [op["cond"]] if op["cond"] and op["cond"] not in s else []
                    new += ways(op["items"], s + add)
            seqs = new
        return seqs
    paths = []
    for p in ways(block, []):
        if p and p not in paths:
            paths.append(p)
    return guards, preds, loops, paths


# ── tree side ──────────────────────────────────────────────────────────────
def tree_edges(t):
    parents, nodes = {}, {}
    def walk(n, parent):
        if n["code"] != "root":
            nodes[n["code"]] = n
            parents.setdefault(n["event"], set()).add(parent)
        for c in n["children"]:
            walk(c, n["event"] if n["code"] != "root" else "ROOT")
    walk(t["event_tree"], None)
    return parents, nodes


def msg_of(event_name):
    m = re.match(r"(?:send|receive|recive|received)(\w+?_\d+)(?:_(?:opt|alt|loop|par)\d+)?$", event_name)
    return m.group(1) if m else None


def check_model(mid, t, diag_path):
    errs = []
    gc = t["guard_codes"]
    ev = t["event_codes"]
    text = lambda codes: [gc[c] for c in codes]
    parents, nodes = tree_edges(t)
    # C6 event codes
    if len(set(ev.values())) != len(ev):
        errs.append("C6 an event has two codes")
    def c6(n):
        kids = n["children"]
        if len(kids) > 1:
            letters = {re.match(r"[a-z]+", k["code"]).group(0) for k in kids}
            nums = sorted(int(re.search(r"\d+", k["code"]).group(0)) for k in kids)
            if len(letters) != 1:
                errs.append(f"C6 branch under {n['code']} has letters {sorted(letters)}")
            if len(set(nums)) != len(nums):
                errs.append(f"C6 branch under {n['code']} repeats a number")
        for k in kids:
            if len(kids) == 1 and n["code"] != "root" and re.match(r"[a-z]+", k["code"]).group(0) == \
                    re.match(r"[a-z]+", n["code"]).group(0):
                errs.append(f"C6 {n['code']} -> {k['code']} repeats a letter in a straight run")
            c6(k)
    c6(t["event_tree"])
    if t["unplaced_events"]:
        errs.append(f"C6 events outside the tree: {t['unplaced_events']}")
    if diag_path is None:
        return errs, {}
    block, order = diagram(diag_path)
    guards, preds, loops, paths = expect(block)
    # C1 messages
    sends = {msg_of(n): n for n in ev.values() if n.startswith("send") and not n.startswith("checkloop")}
    recvs = {msg_of(n): n for n in ev.values() if re.match(r"rec", n)}
    numbered = sorted(sends, key=lambda m: int(m.rsplit("_", 1)[1]))
    if [m.rsplit("_", 1)[0].lower() for m in numbered] != [o.lower() for o in order]:
        errs.append(f"C1 messages differ: diagram {order} vs Event-B {numbered}")
        return errs, {}
    byname = dict(zip(order, numbered))
    if set(recvs) != set(sends):
        errs.append("C1 a message lacks its send or receive event")
    # C2 guards per message
    ev_guard = {name: text(t["event_guards"][code]) for code, name in ev.items()}
    for o, m in byname.items():
        for e in (sends[m], recvs.get(m)):
            if e and ev_guard[e] != guards[o]:
                errs.append(f"C2 {e}: tree {ev_guard[e]} vs diagram {guards[o]}")
    # C3 guard codes
    want = set(itertools.chain.from_iterable(guards.values())) | {g for l in loops for g in l["guards"]}
    if set(gc.values()) != want:
        errs.append(f"C3 codes {sorted(gc.values())} vs diagram {sorted(want)}")
    # C4 event order
    for o, m in byname.items():
        want_p = {recvs[byname[p]] for p in preds[o]} or {"ROOT"}
        if parents.get(sends[m]) != want_p:
            errs.append(f"C4 {sends[m]} after {sorted(parents.get(sends[m], []))}, diagram says {sorted(want_p)}")
        if parents.get(recvs[m]) != {sends[m]}:
            errs.append(f"C4 {recvs[m]} not right after {sends[m]}")
    # C5 loops
    loop_nodes = [n for n in nodes.values() if "loop_back_to" in n]
    if len(loop_nodes) != len(loops):
        errs.append(f"C5 {len(loop_nodes)} loop events vs {len(loops)} loops in diagram")
    for l in loops:
        hit = [n for n in loop_nodes if text(n["guards"]) == l["guards"]]
        if len(hit) != 1:
            errs.append(f"C5 no single loop event with guards {l['guards']}")
            continue
        n = hit[0]
        if parents.get(n["event"]) != {recvs[byname[e]] for e in l["ends"]}:
            errs.append(f"C5 {n['event']} under {sorted(parents.get(n['event'], []))}, want end of body")
        if n["loop_back_to"] != sends[byname[l["first"]]]:
            errs.append(f"C5 {n['event']} goes back to {n['loop_back_to']}, want {sends[byname[l['first']]]}")
    # C7 guard paths
    got = [text(p.split(" -> ")) for p in t["guard_paths"]]
    if sorted(got) != sorted(paths):
        errs.append(f"C7 guard paths {got} vs diagram {paths}")
    return errs, {"messages": len(order), "conditions": len(want), "loops": len(loops), "guard_paths": len(paths)}


def check_bpo(t, meta):
    """model_001: every event name the .bpo knows is in the tree, and every guard is coded."""
    import extract_trees
    errs = []
    bpo = glob.glob(os.path.join(DATASET, meta["rodin_raw_dir"], "*.bpo"))[0]
    events = extract_trees.from_bpo(bpo)
    if sorted(n for n, _ in events) != sorted(t["event_codes"].values()):
        errs.append("C1 events differ from the .bpo")
    conds = {g for _, gs in events for g in gs if not extract_trees.STRUCT.search(g)}
    if conds != set(t["guard_codes"].values()):
        errs.append("C3 codes differ from the .bpo guards")
    return errs


def check_files(release, ids):
    errs = []
    rows = {}
    for kind in ("guard", "event"):
        path = os.path.join(release, "data", f"{kind}_trees.jsonl")
        rows[kind] = {json.loads(l)["id"]: json.loads(l) for l in open(path, encoding="utf-8")}
        if set(rows[kind]) != set(ids):
            errs.append(f"C8 data/{kind}_trees.jsonl has {len(rows[kind])} models, dataset has {len(ids)}")
    codes = {"guard": {}, "event": {}}
    for kind in ("guard", "event"):
        for r in csv.DictReader(open(os.path.join(release, "trees", kind, f"{kind}_codes.csv"), encoding="utf-8-sig")):
            codes[kind].setdefault(r["model_id"], {})[r["code"]] = r[kind]
    for mid in ids:
        src = os.path.join(DATASET, "models", mid)
        t = load_tree(src)
        for f in ("guard_tree.json", "guard_tree.txt", "event_tree.json", "event_tree.txt"):
            if open(os.path.join(src, f), "rb").read() != open(os.path.join(release, "models", mid, f), "rb").read():
                errs.append(f"C8 {mid}/{f} differs in release")
        for kind, keys in (("guard", ("guard_codes", "guard_paths")), ("event", ("event_codes", "event_paths"))):
            for k in keys:
                if rows[kind].get(mid, {}).get(k) != t[k]:
                    errs.append(f"C8 {mid} {k} differs in data/{kind}_trees.jsonl")
            if codes[kind].get(mid, {}) != t[f"{kind}_codes"]:
                errs.append(f"C8 {mid} differs in trees/{kind}/{kind}_codes.csv")
    return errs


def selftest():
    """Break correct trees on purpose and confirm the checks catch every break."""
    import copy
    def load(mid):
        meta = json.load(open(os.path.join(DATASET, "models", mid, "meta.json")))
        return (load_tree(os.path.join(DATASET, "models", mid)),
                glob.glob(os.path.join(DATASET, meta["source_dir"], "*.drawio.xml"))[0])
    def node(t, code):
        found = []
        def walk(n):
            found.extend([n] if n["code"] == code else [])
            [walk(c) for c in n["children"]]
        walk(t["event_tree"])
        return found[0]
    def drop_guard(t): t["event_guards"]["g1"] = ["a1"]
    def wrong_text(t): t["guard_codes"]["b2"] = "cycleNo mod 3 = 1"
    def extra_code(t): t["guard_codes"]["z9"] = "foo = 1"
    def drop_branch(t): node(t, "f1")["children"].pop()
    def wrong_loop(t): node(t, "o2")["loop_back_to"] = "sendcheckOrder_1"
    def other_letter(t): node(t, "g2")["code"] = "x1"
    def lose_path(t): t["guard_paths"] = t["guard_paths"][:1]
    def cut_chain(t): node(t, "c1")["children"][0]["children"] = []
    def path_order(t): t["guard_paths"] = ["a1 -> b1", "a1 -> b2", "b3"]
    def same_number(t): node(t, "m2")["code"] = "m1"
    cases = [("ลบ guard ของ event", "model_109", drop_guard), ("เปลี่ยนข้อความของ guard", "model_109", wrong_text),
             ("เพิ่มรหัส guard ที่ไม่มีในแผนภาพ", "model_109", extra_code), ("ตัดกิ่ง alt ออก", "model_109", drop_branch),
             ("ให้ loop วนกลับผิด event", "model_109", wrong_loop), ("ให้ทางเลือกที่จุดแยกใช้คนละตัวอักษร", "model_109", other_letter),
             ("ลบเส้นทาง guard", "model_109", lose_path), ("ตัดลำดับ event", "model_109", cut_chain),
             ("สลับลำดับในเส้นทาง guard", "model_141", path_order), ("ใช้ตัวเลขทางเลือกซ้ำ", "model_141", same_number)]
    out = []
    for name, mid, breaker in cases:
        t, diag = load(mid)
        t = copy.deepcopy(t)
        breaker(t)
        errs, _ = check_model(mid, t, diag)
        out.append({"case": name, "model": mid, "caught": bool(errs), "by": errs[0][:2] if errs else ""})
    return out


def main(release):
    results, ids = {}, []
    for d in sorted(glob.glob(os.path.join(DATASET, "models", "model_*"))):
        mid = os.path.basename(d)
        ids.append(mid)
        meta = json.load(open(os.path.join(d, "meta.json")))
        t = load_tree(d)
        diag = glob.glob(os.path.join(DATASET, meta["source_dir"], "*.drawio.xml")) if meta.get("source_dir") else []
        if diag:
            errs, info = check_model(mid, t, diag[0])
        else:
            errs, info = check_model(mid, t, None)
            errs += check_bpo(t, meta)
            info = {"checked_against": "rodin .bpo"}
        results[mid] = {"case": meta["case"], "errors": errs, **info}
    file_errs = check_files(release, ids)
    out = {"models": len(ids), "models_with_errors": sum(bool(r["errors"]) for r in results.values()),
           "file_errors": file_errs, "selftest": selftest(), "results": results}
    json.dump(out, open(os.path.join(DATASET, "trees_check.json"), "w"), ensure_ascii=False, indent=1)
    for mid, r in results.items():
        for e in r["errors"]:
            print(mid, e)
    for e in file_errs:
        print(e)
    caught = sum(x["caught"] for x in out["selftest"])
    print(f"checked {len(ids)} models · with errors {out['models_with_errors']} · file errors {len(file_errs)} "
          f"· self-test caught {caught}/{len(out['selftest'])}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default=os.path.join(os.path.dirname(DATASET), "EventB_PO_Training"))
    main(os.path.abspath(ap.parse_args().release))
