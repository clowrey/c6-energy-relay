"""Dump footprints and copper items of a board to JSON (board coordinates: mm, origin lower-left, y up).

    KiCad python: dump_board.py board.kicad_pcb out.json
"""
import json
import sys

import pcbnew

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from hw.gen_pcb import ANTENNA_KEEPOUT, OX, OY, W, H  # noqa: E402


def to_board(x_nm, y_nm):
    return round(x_nm / 1e6 - OX, 4), round(OY + H - y_nm / 1e6, 4)


def bbox(item):
    b = item.GetBoundingBox()
    x0, y1 = to_board(b.GetLeft(), b.GetTop())
    x1, y0 = to_board(b.GetRight(), b.GetBottom())
    return [x0, y0, x1, y1]


def main(pcb, out):
    board = pcbnew.LoadBoard(pcb)
    fps, copper = [], []
    for fp in board.GetFootprints():
        x, y = to_board(fp.GetPosition().x, fp.GetPosition().y)
        drill = max((p.GetDrillSize().x / 1e6 for p in fp.Pads()), default=0)
        fps.append({"ref": fp.GetReference(), "x": x, "y": y, "rot": fp.GetOrientationDegrees(), "drill": drill})
        for p in fp.Pads():
            if p.IsOnCopperLayer():
                copper.append({"kind": "pad", "ref": fp.GetReference(), "net": p.GetNetname(),
                               "netclass": p.GetNetClassName() if p.GetNetname() else "", "bbox": bbox(p)})
    for t in board.GetTracks():
        copper.append({"kind": t.GetClass(), "ref": "", "net": t.GetNetname(), "netclass": t.GetNetClassName(),
                       "start": to_board(t.GetStart().x, t.GetStart().y), "end": to_board(t.GetEnd().x, t.GetEnd().y),
                       "bbox": bbox(t), "layer": t.GetLayerName(),
                       "width": (t.GetWidth(pcbnew.F_Cu) if t.GetClass() == "PCB_VIA" else t.GetWidth()) / 1e6})
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        if z.GetNetname() == "/GND":
            # ground matters near the antenna and around the mounting holes (screw bridges)
            kx0, ky0, kx1, ky1 = ANTENNA_KEEPOUT                     # y down
            regions = [(kx0 - 2, H - ky1 - 2, kx1, H - ky0)]          # x0, y0, x1, y1 (y up)
            for f in fps:
                if f["ref"].startswith("H"):
                    regions.append((f["x"] - 9, f["y"] - 9, f["x"] + 9, f["y"] + 9))
        else:
            regions = [tuple(bbox(z))]
        for layer in z.GetLayerSet().CuStack():
            polys = z.GetFilledPolysList(layer)
            pts = []  # 0.5 mm grid points covered by the fill (board coordinates, y up)
            for region in regions:
                x = max(0.0, round(region[0] * 2) / 2)
                while x <= min(W, region[2]):
                    y = max(0.0, round(region[1] * 2) / 2)
                    while y <= min(H, region[3]):
                        if polys.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x + OX), pcbnew.FromMM(OY + H - y))):
                            pts.append([x, y])
                        y += 0.5
                    x += 0.5
            if pts:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                copper.append({"kind": "zone", "ref": "", "net": z.GetNetname(), "netclass": z.GetNetClassName(),
                               "layer": board.GetLayerName(layer), "points": pts,
                               "bbox": [min(xs), min(ys), max(xs), max(ys)]})
    json.dump({"footprints": fps, "copper": copper}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
