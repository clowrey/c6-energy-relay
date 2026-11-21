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
        for fp in board.GetFootprints():
            for p in fp.Pads():
                key = (fp.GetReference(), p.GetNumber())
                self.pads.setdefault(key, []).append(p.GetPosition())

    def __call__(self, pt):
        if isinstance(pt[0], str):
            ref, num = pt[0], pt[1]
            idx = pt[2] if len(pt) > 2 else 0
            pos = self.pads[(ref, num)][idx]
            return pcbnew.VECTOR2I(pos.x, pos.y)
        return pcbnew.VECTOR2I(MM(OX + pt[0]), MM(OY + pt[1]))


def add_routes(board, routes):
    nets = board.GetNetsByName()
    res = Resolver(board)
    for net_name, paths in routes.items():
        net = nets[NET(net_name)]
        for path in paths:
            layer, width = path.get("layer", "F"), path.get("w", 0.2)
            pts = [res(p) for p in path.get("pts", [])]
            for a, b in zip(pts, pts[1:]):
                if a == b:
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a)
                t.SetEnd(b)
                t.SetWidth(MM(width))
                t.SetLayer(LAYERS[layer])
                t.SetNet(net)
                board.Add(t)
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
