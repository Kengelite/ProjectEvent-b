"""Render a sequence-diagram spec as a draw.io file that ChronoSeq-B can parse.

spec = {
  "name":    diagram name (becomes the Event-B context/machine prefix),
  "objects": lifeline names, left to right,
  "msgs":    [(label, from_idx, to_idx, y, kind)]  kind "f" forward | "r" reply
             (a reply is drawn dashed with its arrowhead at the source end),
  "frames":  [(type, y0, y1, level)]   level 0 = outermost; nested frames indent,
  "texts":   [(text, y, level[, x])]    "[cond]" boxes, "{t..t+n}" delays, "v = now",
  "seps":    [(y, level)]               dashed branch separators (vertices, not edges),
}
"""
from xml.sax.saxutils import escape

LL = ("shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;"
      "container=1;collapsible=0;recursiveResize=0;outlineConnect=0;")
FWD = "html=1;verticalAlign=bottom;endArrow=block;endFill=1;"
RET = "html=1;verticalAlign=bottom;endArrow=none;startArrow=block;startFill=1;dashed=1;"
FRAME = "shape=umlFrame;whiteSpace=wrap;html=1;pointerEvents=0;width=60;height=25;"
TXT = "text;html=1;align=left;verticalAlign=middle;"
SEP = "line;strokeWidth=1;dashed=1;html=1;fillColor=none;"
GAP, LW = 250, 100


def cx(i):
    return 40 + i * GAP + LW / 2


def build(spec):
    objs = spec["objects"]
    width = 40 + (len(objs) - 1) * GAP + LW + 20 - 20
    bottom = max(m[3] for m in spec["msgs"]) + 60
    cells, n = [], [0]

    def nid(p):
        n[0] += 1
        return f"{p}{n[0]}"

    def vertex(style, value, x, y, w, h, p):
        cells.append(f'        <mxCell id="{nid(p)}" parent="1" style="{style}" '
                     f'value="{escape(value, {chr(34): "&quot;"})}" vertex="1">\n'
                     f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
                     f'        </mxCell>')

    for t, y0, y1, d in spec.get("frames", []):
        vertex(FRAME, t, 20 + 25 * d, y0, width - 50 * d, y1 - y0, "f")
    for y, d in spec.get("seps", []):
        vertex(SEP, "", 20 + 25 * d, y, width - 50 * d, 10, "s")
    for item in spec.get("texts", []):
        text, y, d = item[:3]
        x = item[3] if len(item) > 3 else 45 + 25 * d + 60
        vertex(TXT, text, x, y, max(90, 9 * len(text)), 25, "t")
    for i, name in enumerate(objs):
        vertex(LL, name, 40 + i * GAP, 40, LW, bottom - 40, "ll")
    for label, a, b, y, kind in spec["msgs"]:
        sx, tx, style = (cx(a), cx(b), FWD) if kind == "f" else (cx(b), cx(a), RET)
        cells.append(f'        <mxCell id="{nid("m")}" edge="1" parent="1" style="{style}" '
                     f'value="{escape(label)}">\n'
                     f'          <mxGeometry relative="1" as="geometry">\n'
                     f'            <mxPoint x="{sx}" y="{y}" as="sourcePoint" />\n'
                     f'            <mxPoint x="{tx}" y="{y}" as="targetPoint" />\n'
                     f'          </mxGeometry>\n        </mxCell>')

    name = spec["name"]
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net">\n'
            f'  <diagram name="{name}" id="{name.lower()}">\n'
            f'    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" '
            f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" '
            f'pageHeight="827" math="0" shadow="0">\n      <root>\n'
            f'        <mxCell id="0" />\n        <mxCell id="1" parent="0" />\n'
            + "\n".join(cells) +
            '\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n')
