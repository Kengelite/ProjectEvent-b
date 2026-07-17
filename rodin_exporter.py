import io
import os
import zipfile
from datetime import datetime

from xml_parser import (
    extract_detailed_sequence,
    extract_fragments_from_xml,
    build_time_model,
    build_loop_model,
    build_frag_vars,
    edge_guard_conditions,
    sanitize_conditions,
)

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def _next_export_name(xml_path: str = "") -> str:
    """Return a running project name M1, M2, M3, ... and append a log line.

    Using a fresh name on every export avoids Rodin's "nature (missing)" issue
    that appears when re-importing over a project of the same name.
    """
    os.makedirs(_LOG_DIR, exist_ok=True)
    counter = os.path.join(_LOG_DIR, "counter.txt")
    try:
        n = int(open(counter, encoding="utf-8").read().strip()) + 1
    except Exception:
        n = 1
    with open(counter, "w", encoding="utf-8") as f:
        f.write(str(n))
    name = f"M{n}"
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        ts = "?"
    with open(os.path.join(_LOG_DIR, "export_log.txt"), "a", encoding="utf-8") as f:
        f.write(f"{ts}\t{name}\t{os.path.basename(xml_path)}\n")
    return name


def _data_items(data):
    """Split a message's data 'success,transactionID' into ['success','transactionID']."""
    return [d.strip() for d in (data or '').split(',') if d.strip()]


def _data_map(m, data):
    """Build 'm ↦ d1, m ↦ d2' for a (possibly multi-value) data message."""
    return ", ".join(f"{m} ↦ {d}" for d in _data_items(data))


def _x(value: str) -> str:
    """Escape XML attribute value."""
    return (value
            .replace('&', '&amp;')
            .replace('"', '&quot;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


# ── Context (.buc) ────────────────────────────────────────────────────────────

def _partition(set_name: str, elements) -> str:
    """Rodin-style partition axiom asserting all elements are distinct.
    Empty element list degrades to `set_name = ∅`."""
    if not elements:
        return f'{set_name} = ∅'
    parts = ", ".join(f'{{{e}}}' for e in elements)
    return f'partition({set_name}, {parts})'


def _build_context_buc(context_name, objects, raw_messages, msg_instances, data_messages,
                       enum_consts=None) -> str:
    enum_consts = enum_consts or []
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
             '<org.eventb.core.contextFile org.eventb.core.configuration="org.eventb.core.fwd" version="3">']
    idx = 1

    for set_name in ['Objects', 'Messages', 'DataMessages']:
        lines.append(f'<org.eventb.core.carrierSet name="internal_element{idx}" '
                     f'org.eventb.core.identifier="{set_name}"/>')
        idx += 1

    # Only message instances are referenced by the machine — raw message names
    # are unused, so they are intentionally not declared as constants.
    # enum_consts are symbolic guard values (e.g. VALID) modelled as integers.
    all_constants = objects + msg_instances + data_messages + list(enum_consts)
    for const in all_constants:
        lines.append(f'<org.eventb.core.constant name="internal_element{idx}" '
                     f'org.eventb.core.identifier="{_x(const)}"/>')
        idx += 1

    # axm1..axm3: partition() so the prover knows every element is distinct
    axioms = [
        ("axm1", _partition("Objects", objects)),
        ("axm2", _partition("Messages", msg_instances)),
        ("axm3", _partition("DataMessages", data_messages)),
    ]
    # Give each enumerated value a distinct concrete integer (VALID = 0, ...)
    for j, ev in enumerate(enum_consts):
        axioms.append((f"axm{len(axioms) + 1}", f"{ev} = {j}"))
    for label, pred in axioms:
        lines.append(f'<org.eventb.core.axiom name="internal_element{idx}" '
                     f'org.eventb.core.label="{label}" '
                     f'org.eventb.core.predicate="{_x(pred)}" '
                     f'org.eventb.core.theorem="false"/>')
        idx += 1

    lines.append('</org.eventb.core.contextFile>')
    return '\n'.join(lines)


# ── Machine (.bum) ────────────────────────────────────────────────────────────

def _build_machine_bum(machine_name, context_name, all_vars, frag_vars, edges, fragments,
                       time_model=None, loop_model=None) -> str:
    time_model = time_model or {"vars": [], "invs": [], "inits": [], "success": {}}
    loop_model = loop_model or {"counters": {}, "checks": []}
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
             '<org.eventb.core.machineFile org.eventb.core.configuration="org.eventb.core.fwd" version="5">']
    idx = 1

    # SEES
    lines.append(f'<org.eventb.core.seesContext name="internal_element{idx}" '
                 f'org.eventb.core.target="{context_name}"/>')
    idx += 1

    # VARIABLES
    for var in all_vars:
        lines.append(f'<org.eventb.core.variable name="internal_element{idx}" '
                     f'org.eventb.core.identifier="{var}"/>')
        idx += 1

    # INVARIANTS
    invs = [
        ("inv1", "sentMessages ⊆ Messages"),
        ("inv2", "currentMessage ⊆ Messages"),
        ("inv3", "sender ⊆ Messages × Objects"),
        ("inv4", "receiver ⊆ Messages × Objects"),
        ("inv5", "receivedMessages ⊆ sentMessages"),
        ("inv6", "senderdataMessages ⊆ Messages × DataMessages"),
        ("inv7", "receiverdataMessages ⊆ Messages × DataMessages"),
    ]
    inv_n = 8
    for v in frag_vars.keys():
        invs.append((f"inv{inv_n}", f"{v} ∈ ℤ"))
        inv_n += 1
    for pred in time_model["invs"]:        # t_time_i / t_delay_i / t_success_i ∈ ℤ
        invs.append((f"inv{inv_n}", pred))
        inv_n += 1

    for label, pred in invs:
        lines.append(f'<org.eventb.core.invariant name="internal_element{idx}" '
                     f'org.eventb.core.label="{label}" '
                     f'org.eventb.core.predicate="{_x(pred)}" '
                     f'org.eventb.core.theorem="false"/>')
        idx += 1

    # INITIALISATION
    lines.append(f'<org.eventb.core.event name="internal_element{idx}" '
                 f'org.eventb.core.convergence="0" org.eventb.core.extended="false" '
                 f'org.eventb.core.label="INITIALISATION">')
    idx += 1

    # IMPORTANT: assignments must use ≔ (U+2254), NOT ASCII ":=".
    # Rodin's parser only recognises the Unicode operator; ":=" is rejected,
    # the actions get dropped, and every variable ends up "not initialised".
    init_acts = [
        ("act1", "sentMessages ≔ ∅"),
        ("act2", "sender ≔ ∅"),
        ("act3", "receiver ≔ ∅"),
        ("act4", "receivedMessages ≔ ∅"),
        ("act5", "senderdataMessages ≔ ∅"),
        ("act6", "receiverdataMessages ≔ ∅"),
        ("act7", "currentMessage ≔ ∅"),
    ]
    a_idx = 8
    for v, details in frag_vars.items():
        val, kind = details['val'], details.get('kind', 'int')
        if kind == 'counter':       # loop counter starts at 0
            assignment = f"{v} ≔ 0"
        elif kind == 'free':        # inequality var -> any integer (both branches reachable)
            assignment = f"{v} :∈ ℤ"
        elif kind == 'range':       # bounded counter (Rodin interval ‥, not ..)
            assignment = f"{v} :∈ 0 ‥ {val}"
        else:
            assignment = f"{v} ≔ {val}"
        init_acts.append((f"act{a_idx}", assignment))
        a_idx += 1
    for var, kind, val in time_model["inits"]:
        rng = str(val).replace("..", " ‥ ")
        assignment = f"{var} :∈ {rng}" if kind == "range" else f"{var} ≔ {val}"
        init_acts.append((f"act{a_idx}", assignment))
        a_idx += 1

    for i, (label, assignment) in enumerate(init_acts, 1):
        lines.append(f'  <org.eventb.core.action name="internal_element{i}" '
                     f'org.eventb.core.assignment="{_x(assignment)}" '
                     f'org.eventb.core.label="{label}"/>')
    lines.append('</org.eventb.core.event>')

    # SEND / RECEIVE EVENTS
    for i, edge in enumerate(edges, 1):
        m = f"{edge['msg']}_{i}"
        snd, rcv, data = edge['sender'], edge['receiver'], edge['data']
        suffix = edge.get('opt_suffix', "")
        conds = edge_guard_conditions(edge)   # every enclosing fragment's guard

        # ── SEND ──
        lines.append(f'<org.eventb.core.event name="internal_element{idx}" '
                     f'org.eventb.core.convergence="0" org.eventb.core.extended="false" '
                     f'org.eventb.core.label="send{m}{suffix}">')
        idx += 1
        grds = [(f'{m} ∉ sentMessages', 'grd1'),
                ('currentMessage = ∅',   'grd2')]
        preds = edge.get('pred_idxs', [])
        if preds:   # OR over predecessors (an alt merges its branches with ∨)
            pred_g = " ∨ ".join(f"{edges[p]['msg']}_{p + 1} ∈ receivedMessages" for p in preds)
            grds.append((pred_g, 'grd3'))
        for cond in conds:
            grds.append((cond, f'grd{len(grds)+1}'))

        child = 1
        for pred, lbl in grds:
            lines.append(f'  <org.eventb.core.guard name="internal_element{child}" '
                         f'org.eventb.core.label="{lbl}" '
                         f'org.eventb.core.predicate="{_x(pred)}" '
                         f'org.eventb.core.theorem="false"/>')
            child += 1

        acts = [
            (f'sentMessages ≔ sentMessages ∪ {{{m}}}',       'act1'),
            (f'sender ≔ sender ∪ {{{m} ↦ {snd}}}',          'act2'),
            (f'receiver ≔ receiver ∪ {{{m} ↦ {rcv}}}',      'act3'),
            ('receivedMessages ≔ ∅',                          'act4'),
        ]
        dmap = _data_map(m, data)
        if dmap:
            acts.append((f'senderdataMessages ≔ senderdataMessages ∪ {{{dmap}}}', 'act5'))
            acts.append((f'currentMessage ≔ {{{m}}}', 'act6'))
        else:
            acts.append((f'currentMessage ≔ {{{m}}}', 'act5'))

        for assignment, lbl in acts:
            lines.append(f'  <org.eventb.core.action name="internal_element{child}" '
                         f'org.eventb.core.assignment="{_x(assignment)}" '
                         f'org.eventb.core.label="{lbl}"/>')
            child += 1
        lines.append('</org.eventb.core.event>')

        # ── RECEIVE ──
        lines.append(f'<org.eventb.core.event name="internal_element{idx}" '
                     f'org.eventb.core.convergence="0" org.eventb.core.extended="false" '
                     f'org.eventb.core.label="receive{m}{suffix}">')
        idx += 1
        rgrds = [
            (f'{m} ∈ sentMessages',         'grd1'),
            (f'{m} ↦ {snd} ∈ sender',       'grd2'),
            (f'{m} ↦ {rcv} ∈ receiver',     'grd3'),
            (f'{m} ∉ receivedMessages',      'grd4'),
            (f'currentMessage = {{{m}}}',    'grd5'),
        ]
        for cond in conds:
            rgrds.append((cond, f'grd{len(rgrds)+1}'))

        child = 1
        for pred, lbl in rgrds:
            lines.append(f'  <org.eventb.core.guard name="internal_element{child}" '
                         f'org.eventb.core.label="{lbl}" '
                         f'org.eventb.core.predicate="{_x(pred)}" '
                         f'org.eventb.core.theorem="false"/>')
            child += 1

        racts = [(f'receivedMessages ≔ receivedMessages ∪ {{{m}}}', 'act1')]
        dmap = _data_map(m, data)
        if dmap:
            racts.append((f'receiverdataMessages ≔ receiverdataMessages ∪ {{{dmap}}}', 'act2'))
            racts.append(('currentMessage ≔ ∅', 'act3'))
        else:
            racts.append(('currentMessage ≔ ∅', 'act2'))
        if i in time_model["success"]:      # completion time = start + delay
            ts, tt, td = time_model["success"][i]
            racts.append((f'{ts} ≔ {tt} + {td}', f'act{len(racts) + 1}'))

        for assignment, lbl in racts:
            lines.append(f'  <org.eventb.core.action name="internal_element{child}" '
                         f'org.eventb.core.assignment="{_x(assignment)}" '
                         f'org.eventb.core.label="{lbl}"/>')
            child += 1
        lines.append('</org.eventb.core.event>')

    # checkloop_* events — count the loop rounds (grd retry < N, act retry := retry + 1)
    for chk in loop_model["checks"]:
        v, n = chk["var"], chk["bound"]
        lines.append(f'<org.eventb.core.event name="internal_element{idx}" '
                     f'org.eventb.core.convergence="0" org.eventb.core.extended="false" '
                     f'org.eventb.core.label="{chk["name"]}">')
        idx += 1
        lines.append(f'  <org.eventb.core.guard name="internal_element1" '
                     f'org.eventb.core.label="grd1" org.eventb.core.predicate="{_x(f"{v} < {n}")}" '
                     f'org.eventb.core.theorem="false"/>')
        lines.append(f'  <org.eventb.core.action name="internal_element2" '
                     f'org.eventb.core.assignment="{_x(f"{v} ≔ {v} + 1")}" '
                     f'org.eventb.core.label="act1"/>')
        lines.append('</org.eventb.core.event>')

    lines.append('</org.eventb.core.machineFile>')
    return '\n'.join(lines)


# ── .project file ─────────────────────────────────────────────────────────────

def _build_project_file(project_name: str) -> str:
    # NOTE: the Rodin nature/builder IDs are lowercase and case-sensitive.
    # Using camelCase (rodinNature/rodinBuilder) makes Rodin report the
    # nature as "(missing)" so the builder never runs and no POs are produced.
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
    <name>{project_name}</name>
    <comment></comment>
    <projects/>
    <buildSpec>
        <buildCommand>
            <name>org.rodinp.core.rodinbuilder</name>
            <arguments/>
        </buildCommand>
    </buildSpec>
    <natures>
        <nature>org.rodinp.core.rodinnature</nature>
    </natures>
</projectDescription>"""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_rodin_zip(xml_path: str, version: int = 1) -> bytes:
    """Return bytes of a zip file ready to import into Rodin."""
    base_name = _next_export_name(xml_path)   # M1, M2, M3, ... (logged)
    fragments = extract_fragments_from_xml(xml_path)
    edges = extract_detailed_sequence(xml_path)

    objects      = sorted(set(e['sender'] for e in edges) | set(e['receiver'] for e in edges))
    msg_instances = [f"{e['msg']}_{i}" for i, e in enumerate(edges, 1)]
    raw_messages  = sorted(set(e['msg'] for e in edges))
    data_messages = sorted({d for e in edges for d in _data_items(e['data'])})

    context_name = f"{base_name}Context"
    machine_name = f"{base_name}InteractionMachine_{version}"
    project_name = f"{base_name}_Project"

    # Rename control variables that clash with a constant/reserved word, then
    # take the (now safe) guard conditions straight from the edges.
    sanitize_conditions(edges, set(objects) | set(msg_instances)
                        | set(raw_messages) | set(data_messages))
    conditions = [c for e in edges for c in e.get('conditions', [])]
    frag_vars, enum_consts = build_frag_vars(conditions, fragments)
    time_model = build_time_model(edges)
    loop_model = build_loop_model(edges, fragments)
    for v in loop_model["counters"]:            # loop counters start at 0
        frag_vars[v] = {'op': '=', 'val': '0', 'kind': 'counter'}

    base_vars = ["sentMessages", "sender", "receiver", "receivedMessages",
                 "senderdataMessages", "currentMessage", "receiverdataMessages"]
    all_vars = base_vars + list(frag_vars.keys()) + time_model["vars"]

    buc     = _build_context_buc(context_name, objects, raw_messages, msg_instances,
                                 data_messages, enum_consts)
    bum     = _build_machine_bum(machine_name, context_name, all_vars, frag_vars, edges,
                                 fragments, time_model, loop_model)
    project = _build_project_file(project_name)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{project_name}/.project",              project.encode('utf-8'))
        zf.writestr(f"{project_name}/{context_name}.buc",    buc.encode('utf-8'))
        zf.writestr(f"{project_name}/{machine_name}.bum",    bum.encode('utf-8'))

    return buf.getvalue()
