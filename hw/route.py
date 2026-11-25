"""Add the hand-planned tracks (hw/routes.py) to the board, fill the zones and save.

    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" hw/route.py

Route points are board coordinates (mm, origin top-left, y down) or pad references:
("U1", "17") = the centre of pad 17 of U1; ("SW1", "1", 1) = the second pad numbered 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hw.gen_pcb import NET, OX, OY, PCB  # noqa: E402
from hw.spline import spline_path  # noqa: E402

MM = pcbnew.FromMM
LAYERS = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}


class Resolver:
    def __init__(self, board):
        self.pads = {}
        self.objs = {}
        for fp in board.GetFootprints():
            for p in fp.Pads():
                key = (fp.GetReference(), p.GetNumber())
                self.pads.setdefault(key, []).append(p.GetPosition())
                self.objs.setdefault(key, []).append(p)

    def pad(self, pt, net):
        """The pad a path point lands on: the one it names, or a pad of the net under a coordinate."""
        if isinstance(pt[0], str):
            return self.objs[(pt[0], pt[1])][pt[2] if len(pt) > 2 else 0]
        q = self(pt)
        for pads in self.objs.values():
            for p in pads:
                if p.GetNetname() == net and p.HitTest(q):
                    return p
        return None

    def __call__(self, pt):
        if isinstance(pt[0], str):
            ref, num = pt[0], pt[1]
            idx = pt[2] if len(pt) > 2 else 0
            pos = self.pads[(ref, num)][idx]
            return pcbnew.VECTOR2I(pos.x, pos.y)
        return pcbnew.VECTOR2I(MM(OX + pt[0]), MM(OY + pt[1]))


def bend_radius(width_mm: float) -> float:
    """Target radius of a track bend: 1 mm for signals, 2.5 x the width for wider tracks."""
    return max(1.0, 2.5 * width_mm)


def _fillets(pts, width, fixed, max_d=None, radii=None):
    """Corner fillets for one polyline (points in nm). fixed[i]: keep corner i sharp (a junction);
    max_d[i]: the longest tangent allowed at corner i (other copper joins the legs further out);
    radii[i]: the radius wanted at corner i in mm (None: bend_radius); parallel lanes take concentric radii.
    -> {i: (t1, mid, t2)} tangent points and arc midpoint, as float (x, y) in nm."""
    import math
    n = len(pts)
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(n - 1)]
    plan = {}
    for i in range(1, n - 1):
        if fixed[i]:
            continue
        p = pts[i]
        u1 = ((pts[i - 1][0] - p[0]) / seg[i - 1], (pts[i - 1][1] - p[1]) / seg[i - 1])
        u2 = ((pts[i + 1][0] - p[0]) / seg[i], (pts[i + 1][1] - p[1]) / seg[i])
        cos_phi = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        phi = math.acos(cos_phi)                      # angle between the two legs
        if phi > math.radians(179):                   # straight through
            continue
        tan_half_turn = math.tan((math.pi - phi) / 2)
        # each leg is shared with the corner at its other end (if that one is rounded too)
        room1 = seg[i - 1] * (0.5 if i - 1 > 0 and not fixed[i - 1] else 0.9)
        room2 = seg[i] * (0.5 if i + 1 < n - 1 and not fixed[i + 1] else 0.9)
        room = min(room1, room2, max_d[i] if max_d else float("inf"))
        want = radii[i] if radii and i < len(radii) and radii[i] is not None else bend_radius(width)
        r = min(MM(want), room / tan_half_turn)
        d = r * tan_half_turn
        t1 = (p[0] + u1[0] * d, p[1] + u1[1] * d)
        t2 = (p[0] + u2[0] * d, p[1] + u2[1] * d)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        bl = math.hypot(*bis)
        to_mid = r / math.sin(phi / 2) - r            # corner to the arc's midpoint, along the bisector
        mid = (p[0] + bis[0] / bl * to_mid, p[1] + bis[1] / bl * to_mid)
        plan[i] = (t1, mid, t2)
    return plan


def add_routes(board, routes):
    """Tracks as planned in routes.py, with every bend rounded into an arc. Corners where other copper
    of the net joins (another path's end or vertex, a via, a pad) stay sharp so the joint is kept."""
    nets = board.GetNetsByName()
    res = Resolver(board)

    def key(v):
        return (v.x, v.y)

    # where each net's paths, vias and pads touch: a corner there is a junction
    anchors = {}
    for net_name, paths in routes.items():
        a = anchors.setdefault(net_name, [])
        for path in paths:
            pts = [key(res(p)) for p in path.get("pts", [])]
            a += [(pts[0], id(path)), (pts[-1], id(path))] if pts else []
            a += [(q, id(path)) for q in pts[1:-1]]
            a += [(key(res(v)), None) for v in path.get("vias", [])]
    for net_name, paths in routes.items():
        net = nets[NET(net_name)]
        for path in paths:
            layer, width = path.get("layer", "F"), path.get("w", 0.2)
            raw = path.get("pts", [])
            pts = []
            for p, q in zip(raw, [res(p) for p in raw]):
                if not pts or key(q) != pts[-1][1]:
                    pts.append((p, key(q)))
            xy = [q for _, q in pts]
            import math
            others = [a for a, owner in anchors[net_name] if owner != id(path)]   # other paths, vias
            fixed, max_d = [], []
            for i, (src, q) in enumerate(pts):
                dists = [math.dist(a, q) for a in others]
                fixed.append(isinstance(src[0], str) or i in (0, len(pts) - 1) or
                             any(dd < MM(0.05) for dd in dists))
                # a branch joining a leg near the bend: the arc must end before it
                max_d.append(min([dd - MM(width) for dd in dists if dd < MM(3 * bend_radius(width))],
                                 default=float("inf")))
            radii = path.get("radii")
            if radii:       # given per point of the path as written: map onto the de-duplicated points
                keep = []
                for j, p in enumerate(raw):
                    if not keep or key(res(p)) != key(res(raw[keep[-1]])):
                        keep.append(j)
                radii = [radii[j] if j < len(radii) else None for j in keep]
            plan = _fillets(xy, width, fixed, max_d, radii)

            def vec(p):
                return pcbnew.VECTOR2I(int(round(p[0])), int(round(p[1])))

            def add(item):
                item.SetWidth(MM(width))
                item.SetLayer(LAYERS[layer])
                item.SetNet(net)
                board.Add(item)

            def line(a, b):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(vec(a))
                t.SetEnd(vec(b))
                add(t)

            def arc(a, m, b):
                t = pcbnew.PCB_ARC(board)
                t.SetStart(vec(a))
                t.SetMid(vec(m))
                t.SetEnd(vec(b))
                add(t)

            if path.get("spline") and len(xy) > 1:
                pieces = spline_path(xy, path.get("start"), path.get("end"))

                def inside(pad, q):
                    return pad is not None and pad.HitTest(vec(q))

                # inside the pad a path starts or ends on, the curve becomes one straight piece to the pad's centre:
                # pieces lying wholly inside a pad count as dangling in KiCad's DRC
                first, last = res.pad(pts[0][0], net.GetNetname()), res.pad(pts[-1][0], net.GetNetname())
                if last is not None:
                    k = next((i for i, pc in enumerate(pieces) if inside(last, pc[-1])), len(pieces) - 1)
                    if k < len(pieces) - 1 or pieces[k][0] == "arc":
                        pieces = pieces[:k] + [("line", pieces[k][1], xy[-1])]
                if first is not None:
                    k = max((i for i, pc in enumerate(pieces) if inside(first, pc[1])), default=0)
                    if k > 0 or pieces[k][0] == "arc":
                        pieces = [("line", xy[0], pieces[k][-1])] + pieces[k + 1:]
                # straight pieces in a row that bend by a few degrees at most become one (no hidden kinks)
                merged = []
                for pc in pieces:
                    if merged and pc[0] == merged[-1][0] == "line":
                        a, b, c = merged[-1][1], merged[-1][2], pc[2]
                        turn = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])
                        if abs(math.remainder(turn, 2 * math.pi)) < math.radians(3):
                            merged[-1] = ("line", a, c)
                            continue
                    merged.append(pc)
                pieces = merged
                for kind, *p in pieces:
                    (line if kind == "line" else arc)(*p)
                xy = []
            cur = xy[0] if xy else None
            for i in range(1, len(xy)):
                end = plan[i][0] if i in plan else xy[i]
                if vec(cur) != vec(end):
                    line(cur, end)
                if i in plan:
                    t1, mid, t2 = plan[i]
                    arc(t1, mid, t2)
                    cur = t2
                else:
                    cur = xy[i]
            size, drill = path.get("via", (0.6, 0.3))
            for v in path.get("vias", []):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(res(v))
                via.SetWidth(MM(size))
                via.SetDrill(MM(drill))
                via.SetNet(net)
                board.Add(via)


def stitch_ground(board, pitch=4.0, margin=0.75):
    """GND vias on a grid wherever both ground pours cover a disc around the point, so the two pours
    (and any top-layer islands) are tied together. Returns the number of vias added."""
    import math
    gnd = board.GetNetsByName()[NET("GND")]
    fills = {}
    for z in board.Zones():
        if z.GetNetname() == NET("GND") and not z.GetIsRuleArea():
            for layer in z.GetLayerSet().CuStack():
                fills[layer] = z.GetFilledPolysList(layer)
    if pcbnew.F_Cu not in fills or pcbnew.B_Cu not in fills:
        return 0
    ring = [(0, 0)] + [(margin * math.cos(a * math.pi / 4), margin * math.sin(a * math.pi / 4)) for a in range(8)]
    vias = [(t.GetPosition().x, t.GetPosition().y) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    keep_out = []   # pads and holes grown by 1 mm: no stitching via next to them
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            bb.Inflate(MM(1.0))
            keep_out.append(bb)
    added = 0
    from hw.gen_pcb import W, H
    y = pitch / 2
    while y < H:
        x = pitch / 2
        while x < W:
            pts = [pcbnew.VECTOR2I(MM(OX + x + dx), MM(OY + y + dy)) for dx, dy in ring]
            if all(fills[pcbnew.F_Cu].Contains(p) and fills[pcbnew.B_Cu].Contains(p) for p in pts):
                cx, cy = MM(OX + x), MM(OY + y)
                if all((cx - vx) ** 2 + (cy - vy) ** 2 > MM(1.2) ** 2 for vx, vy in vias) and \
                        not any(bb.Contains(pcbnew.VECTOR2I(cx, cy)) for bb in keep_out):
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(pcbnew.VECTOR2I(cx, cy))
                    v.SetWidth(MM(0.6))
                    v.SetDrill(MM(0.3))
                    v.SetNet(gnd)
                    board.Add(v)
                    vias.append((cx, cy))
                    added += 1
            x += pitch
        y += pitch
    return added


def main():
    from hw import routes
    board = pcbnew.LoadBoard(str(PCB))
    add_routes(board, routes.ROUTES)
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    n = stitch_ground(board)
    board.BuildConnectivity()
    filler.Fill(board.Zones())
    print("stitching vias:", n)
    pcbnew.SaveBoard(str(PCB), board)
    write_mains_copper(board)
    print("routed and filled", PCB)


def write_mains_copper(board):
    """Add the bounding boxes of all mains copper to board_features.json (case coordinates), so the
    case keeps its screws away from it."""
    import json
    from hw.gen_pcb import FEATURES, H
    boxes = []

    def add(bb):
        x0, x1 = bb.GetLeft() / 1e6 - OX, bb.GetRight() / 1e6 - OX
        y0, y1 = H - (bb.GetBottom() / 1e6 - OY), H - (bb.GetTop() / 1e6 - OY)
        boxes.append([round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)])

    mains = ("MAINS", "RELAY")
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() and p.GetNetClassName().startswith(mains):
                add(p.GetBoundingBox())
    for t in board.GetTracks():
        if t.GetNetClassName().startswith(mains):
            add(t.GetBoundingBox())
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetClassName().startswith(mains):
            add(z.GetBoundingBox())
    feats = json.loads(FEATURES.read_text())
    feats["mains_copper"] = boxes
    FEATURES.write_text(json.dumps(feats, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()
