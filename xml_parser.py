import os
import re
import html
import base64
import zlib
import urllib.parse
import xml.etree.ElementTree as ET


def to_pascal_case(name: str) -> str:
    if not name: return "System"
    parts = re.split(r"[^A-Za-z0-9]+", name)
    parts = [p for p in parts if p]
    if not parts: return "System"
    result = "".join(p[0].upper() + p[1:] for p in parts)
    # Event-B component/identifier names must not start with a digit
    if result[0].isdigit():
        result = "M" + result
    return result


def clean_html(raw_html):
    if not raw_html: return ""
    # strip tags, then decode HTML entities (&gt; -> >, &amp; -> & ...) so that
    # conditions like [amount >= 1000] are not mangled into "amount &gt;= 1000".
    return html.unescape(re.sub(re.compile('<.*?>'), '', raw_html))


def extract_xml_root(xml_path: str):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        diagram_element = root.find(".//diagram")
        if diagram_element is not None and diagram_element.text:
            try:
                compressed_data = base64.b64decode(diagram_element.text)
                xml_content = zlib.decompress(compressed_data, -15).decode('utf-8')
                xml_content = urllib.parse.unquote(xml_content)
                return ET.fromstring(xml_content)
            except:
                return root
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


def validate_sequence_diagram(xml_path: str):
    """Check that the file is a draw.io Sequence Diagram.

    Returns (is_valid: bool, reason_code: str). reason_code is '' when valid,
    otherwise one of: read_error, not_drawio, no_object, no_message.
    """
    try:
        root = extract_xml_root(xml_path)
    except Exception:
        return False, "read_error"

    cells = list(root.iter('mxCell'))
    if not cells:
        return False, "not_drawio"

    try:
        objects = extract_objects_from_xml(xml_path)
        messages, _ = extract_messages_from_xml(xml_path)
    except Exception:
        return False, "read_error"

    # A sequence diagram must have at least one participant (lifeline/object)
    # and at least one message exchanged between them.
    if not objects:
        return False, "no_object"
    if not messages:
        return False, "no_message"

    return True, ""


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
    except:
        return []


def extract_messages_from_xml(xml_path: str) -> tuple:
    # Derive from the full sequence extraction so messages whose label sits on a
    # child edgeLabel (or a separate text box) are counted too — otherwise the
    # import validation wrongly reports "no message".
    try:
        edges = extract_detailed_sequence(xml_path)
        messages = sorted({e['msg'] for e in edges})
        data_messages = sorted({d.strip() for e in edges if e['data']
                                for d in e['data'].split(',') if d.strip()})
        return messages, data_messages
    except Exception as e:
        raise RuntimeError(f"ดึง messages ไม่ได้: {e}")


def extract_fragments_from_xml(xml_path: str) -> list:
    root = extract_xml_root(xml_path)
    fragments = []
    counts = {'opt': 1, 'loop': 1, 'par': 1, 'alt': 1}
    temp_frags = []

    cell_by_id = {c.get('id'): c for c in root.iter('mxCell')}

    def abs_oy(elem):   # absolute y offset contributed by parent groups
        oy = 0.0
        pid = elem.get('parent')
        seen = set()
        while pid and pid in cell_by_id and pid not in seen:
            seen.add(pid)
            pc = cell_by_id[pid]
            if pc.get('vertex') == '1':
                g = pc.find('mxGeometry')
                if g is not None:
                    oy += float(g.get('y') or 0)
            pid = pc.get('parent')
        return oy

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
                y = float(geo.get('y', 0)) + abs_oy(elem)
                h = float(geo.get('height', 0))
                cond = ""
                match = re.search(r'\[(.*?)\]', val)
                if match:
                    cond = match.group(1).strip()
                temp_frags.append({'type': f_type, 'condition': cond, 'y_start': y, 'y_end': y + h})

    for elem in root.iter('mxCell'):
        val = clean_html(elem.get('value', '')).strip()
        style = elem.get('style', '').lower()
        if 'text' in style and '[' in val and ']' in val:
            match = re.search(r'\[(.*?)\]', val)
            if match:
                cond_text = match.group(1).strip()
                geo = elem.find('mxGeometry')
                if geo is not None:
                    y = float(geo.get('y', 0)) + abs_oy(elem)
                    for f in temp_frags:
                        if not f['condition']:
                            if (f['y_start'] - 30) <= y <= (f['y_end'] + 30):
                                f['condition'] = cond_text
                                break

    for f in temp_frags:
        f['id'] = f"{f['type']}{counts[f['type']]}"
        counts[f['type']] += 1
        fragments.append(f)

    return fragments


_MSG_RE = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?')


def _parse_message(val):
    """Parse 'name(data) {0..5}' -> (name, data, duration, delay) or None."""
    m = _MSG_RE.match(val)
    if not m or not m.group(1):
        return None
    name = sanitize_identifier(m.group(1).strip())
    data = None
    if m.group(2):
        items = [sanitize_identifier(d.strip()) for d in m.group(2).split(',') if d.strip()]
        data = ",".join(items) if items else None
    dur_m = re.search(r'\{\s*(\d+)\s*(?:\.\.|…)\s*(\d+)\s*\}', val)
    duration = f"{dur_m.group(1)}..{dur_m.group(2)}" if dur_m else None
    dly_m = re.search(r'\{\s*t\s*(?:\.\.|…)\s*t\s*\+\s*(\d+)\s*\}', val)
    delay = dly_m.group(1) if dly_m else None
    return name, data, duration, delay


def extract_detailed_sequence(xml_path: str, return_warnings: bool = False):
    root = extract_xml_root(xml_path)
    fragments = extract_fragments_from_xml(xml_path)
    cell_by_id = {c.get('id'): c for c in root.iter('mxCell')}

    def abs_offset(elem):
        # draw.io stores a child's coordinates relative to its parent group/
        # container. Accumulate parent vertex offsets to get absolute coords.
        ox = oy = 0.0
        pid = elem.get('parent')
        seen = set()
        while pid and pid in cell_by_id and pid not in seen:
            seen.add(pid)
            pc = cell_by_id[pid]
            if pc.get('vertex') == '1':
                g = pc.find('mxGeometry')
                if g is not None:
                    ox += float(g.get('x') or 0)
                    oy += float(g.get('y') or 0)
            pid = pc.get('parent')
        return ox, oy

    lifelines = {}
    lifelines_geo = []
    for elem in root.iter('mxCell'):
        style = elem.get('style', '')
        if 'umlLifeline' in style or 'shape=umlActor' in style or 'shape=rect' in style:
            val = clean_html(elem.get('value', ''))
            name = val.split(':')[-1].strip() if ':' in val else val.strip()
            name = sanitize_identifier(name if name else f"Obj_{elem.get('id')}")
            lifelines[elem.get('id')] = name
            geo = elem.find('mxGeometry')
            if geo is not None:
                ox, _ = abs_offset(elem)
                x = float(geo.get('x', 0)) + ox
                width = float(geo.get('width', 100))
                lifelines_geo.append({'id': elem.get('id'), 'name': name, 'center_x': x + width / 2})

    def get_nearest_lifeline(target_x):
        # always snap to the closest lifeline (a message endpoint always belongs
        # to one) -> avoids "Unknown" for arrows not perfectly connected.
        closest_name, min_dist = "Unknown", float('inf')
        for ll in lifelines_geo:
            dist = abs(ll['center_x'] - target_x)
            if dist < min_dist:
                min_dist, closest_name = dist, ll['name']
        return closest_name

    def resolve_ends(elem):
        """Return (sender, receiver, y_pos) in absolute coordinates."""
        ox, oy = abs_offset(elem)
        geo = elem.find('mxGeometry')
        sx = tx = sy = ty = None
        if geo is not None:
            sp = geo.find("./mxPoint[@as='sourcePoint']")
            tp = geo.find("./mxPoint[@as='targetPoint']")
            if sp is not None:
                if sp.get('x'): sx = float(sp.get('x')) + ox
                if sp.get('y'): sy = float(sp.get('y')) + oy
            if tp is not None:
                if tp.get('x'): tx = float(tp.get('x')) + ox
                if tp.get('y'): ty = float(tp.get('y')) + oy
        sender = lifelines.get(elem.get('source'))
        receiver = lifelines.get(elem.get('target'))
        if not sender and sx is not None: sender = get_nearest_lifeline(sx)
        if not receiver and tx is not None: receiver = get_nearest_lifeline(tx)
        # A reply/return message is drawn with its arrowhead at the SOURCE end
        # (startArrow set, endArrow=none), so the message actually flows
        # target -> source. The arrowhead always marks the receiver, so swap.
        style = elem.get('style', '') or ''
        sm = re.search(r'startArrow=([^;]+)', style)
        em = re.search(r'endArrow=([^;]+)', style)
        start_head = (sm.group(1).strip() if sm else 'none')
        end_head = (em.group(1).strip() if em else 'classic')   # drawio default has a head
        if start_head != 'none' and end_head == 'none':
            sender, receiver = receiver, sender
        y_pos = sy if sy is not None else (ty if ty is not None else
                (float(geo.get('y', 0)) + oy if geo is not None else 0))
        return (sender or "Unknown"), (receiver or "Unknown"), y_pos

    # Condition text boxes "[cond]" with absolute y — used to pick alt branches.
    cond_boxes = []
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1':
            continue
        cm = re.search(r'\[(.*?)\]', clean_html(elem.get('value', '') or ''))
        if cm:
            _, oy = abs_offset(elem)
            geo = elem.find('mxGeometry')
            y = (float(geo.get('y')) + oy) if (geo is not None and geo.get('y')) else oy
            cond_boxes.append({'text': cm.group(1).strip(), 'y': y})
    cond_boxes.sort(key=lambda c: c['y'])

    def frag_info(y_pos):
        """Return (fragments, conditions, opt_suffix) for a message at y_pos.

        Handles nesting: every fragment whose band contains y_pos is returned
        (outermost first). For an alt, the branch condition is the nearest
        condition box above the message; otherwise the fragment's own condition.
        """
        active = sorted(
            [f for f in fragments if (f['y_start'] - 20) <= y_pos <= (f['y_end'] + 20)],
            key=lambda x: x['y_end'] - x['y_start'], reverse=True)
        # A non-alt fragment annotation (e.g. the loop's [retry < 5]) is also a
        # "[...]" box; it must NOT be mistaken for an alt branch label when it sits
        # between the alt condition and a nested message.
        frag_conds = {f.get('condition', '').strip()
                      for f in fragments if f['type'] != 'alt' and f.get('condition')}
        conditions = []
        for f in active:
            if f['type'] == 'alt':
                above = [cb for cb in cond_boxes
                         if (f['y_start'] - 30) <= cb['y'] <= y_pos + 10
                         and cb['text'].strip() not in frag_conds]
                conditions.append(above[-1]['text'] if above else (f.get('condition') or ''))
            else:
                conditions.append(f.get('condition') or '')
        opts = [f for f in active if f['type'] == 'opt']
        opt_suffix = f"_{opts[-1]['id']}" if opts else ""   # innermost opt
        return active, conditions, opt_suffix

    # Separate delay text boxes: {t..t+N}  (t = current time / "now")
    time_delays = []
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1':
            continue
        dm = re.search(r'\{\s*t\s*(?:\.\.|…)\s*t\s*\+\s*(\d+)\s*\}',
                       clean_html(elem.get('value', '') or ''))
        if dm:
            _, oy = abs_offset(elem)
            geo = elem.find('mxGeometry')
            y = (float(geo.get('y')) + oy) if (geo is not None and geo.get('y')) else oy
            time_delays.append({'delay': dm.group(1), 'y': y})

    # Named time observations "<var> = now" written at a message endpoint. When
    # <var> also drives a branch guard (e.g. [t_desc <= 15]), it must equal the
    # realised time of the message it annotates, not a free integer (see
    # build_now_bindings).
    now_obs = []
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1':
            continue
        nm = re.match(r'([A-Za-z_]\w*)\s*=\s*now\b',
                      clean_html(elem.get('value', '') or '').strip())
        if nm:
            _, oy = abs_offset(elem)
            geo = elem.find('mxGeometry')
            y = (float(geo.get('y')) + oy) if (geo is not None and geo.get('y')) else oy
            now_obs.append({'var': nm.group(1), 'y': y})

    # A message label can be the edge's own `value` OR a child edgeLabel cell.
    child_labels = {}
    for elem in root.iter('mxCell'):
        if 'edgeLabel' in (elem.get('style', '') or '') and elem.get('value'):
            txt = clean_html(elem.get('value', '')).strip()
            if txt:
                child_labels.setdefault(elem.get('parent'), []).append(txt)

    def edge_message_text(elem):
        raw = clean_html(elem.get('value', '') or '').strip()
        if raw:
            return raw
        for lbl in child_labels.get(elem.get('id'), []):   # label on the arrow
            if _parse_message(lbl):
                return lbl
        return ""

    def is_time_annotation(elem):
        texts = list(child_labels.get(elem.get('id'), []))
        texts.append(clean_html(elem.get('value', '') or ''))
        return any('..' in t and re.search(r'\{\s*(?:t|\d)', t) for t in texts)

    edges = []
    valueless = []
    for elem in root.iter('mxCell'):
        if elem.get('edge') != '1':
            continue
        raw = edge_message_text(elem)
        parsed = _parse_message(raw) if raw else None
        if parsed:
            name, data, duration, delay = parsed
            snd, rcv, y_pos = resolve_ends(elem)
            frags, conds, opt_suffix = frag_info(y_pos)
            edges.append({'msg': name, 'data': data, 'sender': snd, 'receiver': rcv,
                          'y': y_pos, 'fragments': frags, 'conditions': conds,
                          'opt_suffix': opt_suffix, 'duration': duration, 'delay': delay})
        else:
            snd, rcv, y_pos = resolve_ends(elem)
            src, tgt = elem.get('source'), elem.get('target')
            valueless.append({'sender': snd, 'receiver': rcv, 'y': y_pos,
                              'selfloop': bool(src) and src == tgt,
                              'time': is_time_annotation(elem), 'consumed': False})

    valueless_arrows = [a for a in valueless
                        if a['sender'] != a['receiver']
                        and a['sender'] != "Unknown" and a['receiver'] != "Unknown"]

    # Orphan message labels: a standalone text box like "paymentStatus(..) {0..5}",
    # or a *detached* edgeLabel whose parent is not its edge (e.g. parent="1", a
    # drawio quirk), so the arrow carries no inline label. Bind it to the nearest
    # value-less arrow.
    edge_ids = {e.get('id') for e in root.iter('mxCell') if e.get('edge') == '1'}
    for elem in root.iter('mxCell'):
        if elem.get('edge') == '1':
            continue
        style = elem.get('style', '') or ''
        is_detached_label = 'edgeLabel' in style and elem.get('parent') not in edge_ids
        if 'text' not in style and not is_detached_label:
            continue
        raw = clean_html(elem.get('value', '') or '').strip()
        if not raw or raw.startswith('[') or '(' not in raw:
            continue
        parsed = _parse_message(raw)
        if not parsed or not valueless_arrows:
            continue
        name, data, duration, delay = parsed
        _, oy = abs_offset(elem)
        geo = elem.find('mxGeometry')
        ty = (float(geo.get('y')) + oy) if (geo is not None and geo.get('y')) else oy
        arr = min(valueless_arrows, key=lambda a: abs(a['y'] - ty))
        arr['consumed'] = True
        frags, conds, opt_suffix = frag_info(arr['y'])
        edges.append({'msg': name, 'data': data, 'sender': arr['sender'],
                      'receiver': arr['receiver'], 'y': arr['y'], 'fragments': frags,
                      'conditions': conds, 'opt_suffix': opt_suffix,
                      'duration': duration, 'delay': delay})

    edges.sort(key=lambda x: x['y'])

    # Predecessor(s) of each message for the ordering guard, as a list that the
    # guard OR-joins. An alt is a choice, not a sequence, so:
    #   * the first message of each branch depends on the message BEFORE the alt
    #     (both branches start from the same point — not chained to each other);
    #   * the message AFTER the alt depends on ANY branch finishing
    #     (last message of each branch, joined with ∨).
    def _alt_of(e):
        for f, c in zip(e.get('fragments', []), e.get('conditions', [])):
            if f['type'] == 'alt':
                return f, c
        return None, None

    def _alt_branch_lasts(alt, before_i):
        by_branch = {}                              # branch condition -> last index
        for j in range(before_i):
            jf, jc = _alt_of(edges[j])
            if jf is not None and jf.get('id') == alt.get('id'):
                by_branch[jc] = j                   # edges are y-sorted -> keeps last
        return list(by_branch.values())

    for i, e in enumerate(edges):
        alt_frag, alt_cond = _alt_of(e)
        preds = []
        if alt_frag is not None:                    # inside an alt branch
            for j in range(i - 1, -1, -1):          # previous msg in the same branch
                jf, jc = _alt_of(edges[j])
                if jf is not None and jf.get('id') == alt_frag.get('id') and jc == alt_cond:
                    preds = [j]
                    break
            if not preds:                           # first of the branch -> before the alt
                for j in range(i - 1, -1, -1):
                    if edges[j]['y'] < alt_frag['y_start']:
                        preds = [j]
                        break
        elif i > 0:
            palt, _ = _alt_of(edges[i - 1])
            preds = _alt_branch_lasts(palt, i) if palt is not None else [i - 1]
        e['pred_idxs'] = preds

    # Attach each separate delay box {t..t+n} to the message nearest to it by
    # vertical position. It need NOT be a duration-bearing message — a delay can
    # sit on a message that has no {0..n} duration of its own (e.g. LowerBarrier),
    # so binding to "the nearest message with a duration" would mis-route it.
    for td in time_delays:
        if not edges:
            continue
        closest = min(edges, key=lambda e: abs(e['y'] - td['y']))
        if abs(closest['y'] - td['y']) < 100:
            closest['delay'] = td['delay']

    # Attach each "<var> = now" observation to the nearest message.
    for ob in now_obs:
        if not edges:
            continue
        closest = min(edges, key=lambda e: abs(e['y'] - ob['y']))
        if abs(closest['y'] - ob['y']) < 120:
            closest['now_var'] = ob['var']

    # Warn about arrows that look like a message but carry no label at all.
    warnings = [
        f"{a['sender']} → {a['receiver']} (y≈{int(a['y'])})"
        for a in valueless
        if a['sender'] != a['receiver'] and a['sender'] != "Unknown"
        and a['receiver'] != "Unknown" and not a['selfloop']
        and not a['time'] and not a['consumed']
    ]

    if return_warnings:
        return edges, warnings
    return edges


def get_message_warnings(xml_path: str):
    """List arrows that look like messages but have no label (for UI alerts)."""
    try:
        _, warnings = extract_detailed_sequence(xml_path, return_warnings=True)
        return warnings
    except Exception:
        return []


# Event-B / Rodin predefined identifiers that must not be used as plain names.
RESERVED_WORDS = {
    "BOOL", "TRUE", "FALSE", "INTEGER", "NATURAL", "NATURAL1", "INT", "NAT", "NAT1",
    "POW", "POW1", "FIN", "FIN1", "card", "dom", "ran", "id", "prj1", "prj2",
    "min", "max", "bool", "mod", "union", "inter", "finite", "partition",
    "pred", "succ", "skip",
}


def sanitize_identifier(name):
    """Rename an identifier (object / message / data) that is a reserved word."""
    return f"{name}_v" if name in RESERVED_WORDS else name


def _rename_clashing(name, taken):
    new = name
    while new in taken:
        new += "_v"
    return new


def sanitize_conditions(edges, constants):
    """Rename a control variable that clashes with a constant or reserved word.

    A guard variable must not share a name with a data/object/message constant
    (e.g. data `amount` + guard `amount >= 1000` — Rodin rejects the clash) nor
    with a reserved word. The variable is renamed consistently in every guard.
    """
    taken = set(constants) | RESERVED_WORDS
    for e in edges:
        out = []
        for c in e.get('conditions', []):
            m = re.match(r'(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*(?:==|!=|<=|>=|=|<|>).*)$', c or '')
            if m and m.group(2) in taken:
                out.append(m.group(1) + _rename_clashing(m.group(2), taken) + m.group(3))
            else:
                out.append(c)
        e['conditions'] = out
    return edges


def edge_guard_conditions(edge):
    """Deduplicated guard conditions with Rodin's Unicode comparison operators.

    ASCII == <= >= != are not recognised by Rodin's parser; map them to = ≤ ≥ ≠.
    """
    seen, out = set(), []
    for c in edge.get('conditions', []):
        c = (c or '')
        for a, b in (("==", "="), ("!=", "≠"), ("<=", "≤"), (">=", "≥")):
            c = c.replace(a, b)
        c = c.strip()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def build_frag_vars(conditions, fragments):
    """Extract control variables from a list of condition strings.

    Returns (frag_vars, enum_consts):
      frag_vars   {name: {'op','val','kind'}}  kind ∈ 'range' | 'int' | 'enum'
      enum_consts sorted list of symbolic RHS values (e.g. VALID, CORRUPTED)

    A condition compares an identifier to a number ([retry <= 3]) or to a
    symbolic value ([integrity_status == VALID]). The identifier is always the
    variable; symbolic right-hand sides become enumerated constants so we never
    build an invalid variable name like "integrity_status == VALID".
    """
    frag_vars = {}
    enum_consts = set()
    for cond in conditions:
        if not cond:
            continue
        m = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(==|!=|<=|>=|=|<|>)\s*([A-Za-z0-9_]+)', cond)
        if not m:
            continue
        name, op, rhs = m.group(1), m.group(2), m.group(3)
        if rhs.isdigit():
            # inequality (< <= > >=) -> free integer chosen non-deterministically
            # so both alt branches stay reachable; equality (= ==) -> fixed value.
            kind = 'free' if op in ('<', '<=', '>', '>=') else 'int'
            frag_vars[name] = {'op': op, 'val': rhs, 'kind': kind}
        else:
            enum_consts.add(rhs)
            frag_vars[name] = {'op': op, 'val': rhs, 'kind': 'enum'}
    for f in fragments:
        # Loop counters are added later from build_loop_model() using the real
        # annotation variable name (e.g. RetryCount), so we must NOT inject a
        # hardcoded 'retry' here — that produced a dead, unused variable whenever
        # the loop was annotated with any name other than "retry".
        if f['type'] == 'par':
            pv = f"par_{f['id'].replace('par', '')}"
            if pv not in frag_vars:
                frag_vars[pv] = {'op': '=', 'val': '0', 'kind': 'int'}
    return frag_vars, sorted(enum_consts)


def build_loop_model(edges, fragments):
    """Loop counters + one checkloop event per loop fragment (Rule-5 style).

    Returns:
      counters {var: bound}              -> loop counter variables (init var := 0)
      checks   [{'name','var','bound'}]  -> extra `checkloop_*` events that count
                                            the rounds (grd retry < N, act retry+1)
    Loop-body messages already reference the counter through the loop condition
    guard (retry ≤ N), so nothing extra is needed there.
    """
    loops = {}
    for f in fragments:
        if f['type'] != 'loop':
            continue
        m = re.search(r'([A-Za-z_]\w*)\s*(?:<=|<|>=|>|==|=)\s*(\d+)', f.get('condition') or '')
        loops[f['id']] = {'var': m.group(1) if m else 'retry',
                          'bound': int(m.group(2)) if m else 3, 'idxs': []}
    for idx, e in enumerate(edges):
        for f in e.get('fragments', []):
            if f['type'] == 'loop' and f['id'] in loops:
                loops[f['id']]['idxs'].append(idx)
    counters, checks = {}, []
    frag_by_id = {f['id']: f for f in fragments}
    for lid, d in loops.items():
        if not d['idxs']:
            continue
        counters[d['var']] = d['bound']
        first = min(d['idxs'])
        fe = edges[first]
        lf = frag_by_id.get(lid, {})
        ls, le = lf.get('y_start', 0), lf.get('y_end', 0)
        # Nested fragments: the checkloop counter inherits the guards of fragments
        # that ENCLOSE the loop (their band contains it) — e.g. an outer alt branch
        # [Moisture >= 720]. A fragment nested INSIDE the loop (e.g. an alt below a
        # loop header) must NOT be pulled in, so filter by band containment.
        enclosing = [c for f, c in zip(fe.get('fragments', []), fe.get('conditions', []))
                     if f.get('id') != lid and c
                     and f.get('y_start', le) <= ls and f.get('y_end', ls) >= le]
        checks.append({'name': f"checkloop_{fe['msg']}_{first + 1}_{lid}",
                       'var': d['var'], 'bound': d['bound'],
                       'guards': edge_guard_conditions({'conditions': enclosing})})
    return {'counters': counters, 'checks': checks}


def build_now_bindings(edges):
    """Named observations '<var> = now' that also drive a branch condition.

    Returns {var: (index_1based, expr)} where expr computes the realised time of
    the annotated message (t_time_i + t_delay_i). Such a variable is initialised
    to 0 and assigned at the message's receive event, so an alt guarded by e.g.
    [t_desc <= 15] decides on the actual observed time rather than a free integer
    (which would leave the state space unbounded and the branch meaningless).
    """
    cond_vars = set()
    for e in edges:
        for c in edge_guard_conditions(e):
            m = re.match(r'([A-Za-z_]\w*)', c)
            if m:
                cond_vars.add(m.group(1))
    bindings = {}
    for i, e in enumerate(edges, 1):
        v = e.get('now_var')
        if v and v in cond_vars and (e.get('duration') or e.get('delay')):
            bindings[v] = (i, f"t_time_{i} + t_delay_{i}")
    return bindings


def build_time_model(edges):
    """Build the Event-B time variables from edges carrying duration/delay.

    A message with a Duration Constraint {0..5} and/or Time Constraint {t..t+5}
    yields three integer variables:
        t_time_i    :∈ 0..5     (when the message occurs, within its duration)
        t_delay_i   := 5        (the delay from "now")
        t_success_i := 0        (completion time, later t_time_i + t_delay_i)

    Returns a dict:
        vars    -> list of variable names
        invs    -> list of "<var> ∈ ℤ" predicates
        inits   -> list of (var, kind, value); kind is "range" or "assign"
        success -> {edge_index(1-based): (t_success, t_time, t_delay)}
    """
    vars_, invs, inits, success = [], [], [], {}
    for i, e in enumerate(edges, 1):
        if e.get('duration') or e.get('delay'):
            dur = e.get('duration') or "0..0"
            dly = e.get('delay') or "0"
            tt, td, ts = f"t_time_{i}", f"t_delay_{i}", f"t_success_{i}"
            vars_ += [tt, td, ts]
            invs += [f"{tt} ∈ ℤ", f"{td} ∈ ℤ", f"{ts} ∈ ℤ"]
            inits += [(tt, "range", dur), (td, "assign", dly), (ts, "assign", "0")]
            success[i] = (ts, tt, td)
    return {"vars": vars_, "invs": invs, "inits": inits, "success": success}
