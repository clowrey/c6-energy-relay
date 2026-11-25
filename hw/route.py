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


def _turn(u, v):
    """Angle in radians between two directions (0 = straight on)."""
    import math
    if u is None or v is None:
        return 0.0
    return abs(math.remainder(math.atan2(v[1], v[0]) - math.atan2(u[1], u[0]), 2 * math.pi))


def octilinear(pts, start=None, end=None, inside=None):
    """Give every leg of a polyline (points in nm) a direction at a multiple of 45 degrees: a leg at any
    other angle becomes a straight run plus a 45-degree run. Of the two orders, take the one that turns
    least where it meets the legs before and after (start / end: the direction to leave the first point
    and to arrive at the last one); a bend point that would land in the start or end pad (inside(i, q))
    is avoided. -> [(point, index of the source point or None for an inserted bend)]."""
    import math
    out = [(pts[0], 0)]
    prev = tuple(start) if start else None
    for i in range(1, len(pts)):
        a, c = out[-1][0], pts[i]
        dx, dy = c[0] - a[0], c[1] - a[1]
        if math.hypot(dx, dy) < 1:
            continue
        off = abs(math.remainder(math.degrees(math.atan2(dy, dx)), 45))
        nxt = None
        if i + 1 < len(pts):
            nxt = (pts[i + 1][0] - c[0], pts[i + 1][1] - c[1])
        elif end:
            nxt = tuple(end)
        # a leg that misses the 45-degree grid by a few hundredths of a mm (pads of different sizes) stays one leg
        if math.hypot(dx, dy) * math.sin(math.radians(off)) > MM(0.03):
            m = min(abs(dx), abs(dy))
            diag = (math.copysign(m, dx), math.copysign(m, dy))
            straight = (dx - diag[0], dy - diag[1])
            best = None
            for first, second in ((straight, diag), (diag, straight)):
                q = (a[0] + first[0], a[1] + first[1])
                cost = _turn(prev, first) + _turn(first, second) + _turn(second, nxt)
                if inside and (inside(0, q) and i == 1 or inside(len(pts) - 1, q) and i == len(pts) - 1):
                    cost += 10
                if best is None or cost < best[0] - 1e-6:
                    best = (cost, q, second)
            out.append((best[1], None))
            prev = best[2]
        else:
            prev = (dx, dy)
        out.append((c, i))
    return out


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
    """Tracks as planned in routes.py: every leg at 0, 45 or 90 degrees (octilinear()), every bend rounded into an
    arc. Corners where other copper
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
            pts = []            # (source point, nm point, index in raw)
            for j, (p, q) in enumerate(zip(raw, [res(p) for p in raw])):
                if not pts or key(q) != pts[-1][1]:
                    pts.append((p, key(q), j))
            import math
            first = res.pad(pts[0][0], net.GetNetname()) if pts else None
            last = res.pad(pts[-1][0], net.GetNetname()) if pts else None

            def inside(i, q):
                pad = first if i == 0 else last
                return pad is not None and pad.HitTest(pcbnew.VECTOR2I(int(q[0]), int(q[1])))

            oct_pts = octilinear([q for _, q, _ in pts], path.get("start"), path.get("end"), inside) if pts else []
            xy = [q for q, _ in oct_pts]
            others = [a for a, owner in anchors[net_name] if owner != id(path)]   # other paths, vias
            fixed, max_d, radii = [], [], []
            for i, (q, src_i) in enumerate(oct_pts):
                src = pts[src_i][0] if src_i is not None else None
                dists = [math.dist(a, q) for a in others]
                fixed.append((src is not None and isinstance(src[0], str)) or i in (0, len(oct_pts) - 1) or
                             any(dd < MM(0.05) for dd in dists))
                # a branch joining a leg near the bend: the arc must end before it
                max_d.append(min([dd - MM(width) for dd in dists if dd < MM(3 * bend_radius(width))],
                                 default=float("inf")))
                r = path.get("radii")
                radii.append(r[pts[src_i][2]] if r and src_i is not None and pts[src_i][2] < len(r) else None)
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
