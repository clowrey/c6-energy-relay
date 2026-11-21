"""JLCPCB order files: hw/out/jlc/{gerbers.zip, bom.csv, cpl.csv, plugs.csv, cost.md}.

Run with KiCad's Python after route.py:
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" hw/export_jlc.py [--offline]

Gerbers and drill files come from kicad-cli with the board's lower-left corner as origin (the aux
origin set by gen_pcb.py); the CPL uses the same origin (y up), which is what JLC expects. CPL rotation
= KiCad rotation + parts.PARTS[...].rotation (check the parts in JLC's placement preview anyway).
Prices are live from JLC unless --offline; fees and PCB/shipping figures are estimates, labelled.
"""
from __future__ import annotations

import csv
import io
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hw import design  # noqa: E402
from hw.gen_pcb import H, OX, OY, PCB  # noqa: E402
from hw.parts import PARTS  # noqa: E402

OUT = HERE / "out" / "jlc"
KCLI = Path(sys.executable).parent / "kicad-cli.exe"
QTYS = (10, 20, 30, 50, 100)

# Estimates (USD, Nov 2026 JLC price list; check the live quote): labelled as such in cost.md
EXTENDED_FEE = 3.00          # per unique Extended part per order
PCBA_SETUP = 25.00           # Standard PCBA (needed for through-hole assembly)
STENCIL = 7.86
SMT_JOINT = 0.0017
THT_JOINT = 0.0173
PCB_FAB = {10: 5.0, 20: 9.0, 30: 13.0, 50: 20.0, 100: 35.0}      # 2-layer 80 x 80 mm, HASL
SHIPPING = {10: 20.0, 20: 25.0, 30: 30.0, 50: 40.0, 100: 60.0}   # DHL to the USA, rough


def placed():
    return [c for c in design.COMPONENTS if c.part and PARTS[c.part].footprint and not c.dnp]


def gerbers():
    with tempfile.TemporaryDirectory() as tmp:
        layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
        subprocess.run([str(KCLI), "pcb", "export", "gerbers", "--layers", layers, "--use-drill-file-origin",
                        "--no-protel-ext", "-o", tmp + "/", str(PCB)], check=True, capture_output=True)
        subprocess.run([str(KCLI), "pcb", "export", "drill", "--drill-origin", "plot", "--excellon-separate-th",
                        "--generate-map", "--map-format", "gerberx2", "-o", tmp + "/", str(PCB)],
                       check=True, capture_output=True)
        OUT.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(OUT / "gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(Path(tmp).iterdir()):
                z.write(f, f.name)


def bom():
    groups = defaultdict(list)
    for c in placed():
        groups[c.part].append(c.ref)
    with open(OUT / "bom.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for key, refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            p = PARTS[key]
            w.writerow([p.mpn or p.value, ",".join(refs), p.footprint.split(":")[1], p.lcsc])
    return groups


def cpl():
    board = pcbnew.LoadBoard(str(PCB))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    with open(OUT / "cpl.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for c in placed():
            fp = fps[c.ref]
            # JLC places by the part's centre: the centre of its pads, not the footprint anchor
            # (pin 1 on the through-hole parts)
            xs = [b for p in fp.Pads() for b in (p.GetBoundingBox().GetLeft(), p.GetBoundingBox().GetRight())]
            ys = [b for p in fp.Pads() for b in (p.GetBoundingBox().GetTop(), p.GetBoundingBox().GetBottom())]
            x = (min(xs) + max(xs)) / 2e6 - OX
            y = OY + H - (min(ys) + max(ys)) / 2e6
            rot = (fp.GetOrientationDegrees() + PARTS[c.part].rotation) % 360
            w.writerow([c.ref, f"{x:.3f}mm", f"{y:.3f}mm", "Top", f"{rot:g}"])


def plugs():
    n_508 = sum(1 for c in design.COMPONENTS if c.part == "term508_hdr")
    with open(OUT / "plugs.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["Part", "MPN", "LCSC", "Qty per board", "Notes"])
        w.writerow(["5.08 mm 2-pole plug, 15 A", PARTS["term508_plug"].mpn, PARTS["term508_plug"].lcsc, n_508,
                    "mains input + 2 relays; order loose with the boards (not placed)"])
        w.writerow(["3.81 mm 4-pole plug", PARTS["term381_plug"].mpn, PARTS["term381_plug"].lcsc, 1,
                    "CT inputs; order loose"])


def joints():
    smt = tht = 0
    board = pcbnew.LoadBoard(str(PCB))
    refs = {c.ref for c in placed()}
    for fp in board.GetFootprints():
        if fp.GetReference() not in refs:
            continue
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                tht += 1
            elif p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                smt += 1
    return smt, tht


def cost(groups, offline=False):
    from hw.tools import jlc
    lines = []
    info = {}
    for key in list(groups) + ["term508_plug", "term381_plug"]:
        p = PARTS[key]
        try:
            info[key] = None if offline else jlc.lookup(p.lcsc)
        except Exception as e:  # network trouble: leave the row blank, flag it
            info[key] = None
            print("price lookup failed", key, e)
    per_board = {k: len(v) for k, v in groups.items()}
    per_board["term508_plug"] = PARTS["term508_plug"].per_board
    per_board["term381_plug"] = PARTS["term381_plug"].per_board
    extended = sorted(k for k in groups if info.get(k) and info[k]["lib"] != "base")
    smt, tht = joints()

    lines.append(f"# C6 Energy Relay: cost estimate ({date.today().isoformat()})\n")
    lines.append("Parts prices are live from JLC's parts search at the time of export; fees, PCB and shipping "
                 "are **estimates** from JLC's published list (check the real quote before paying).\n")
    lines.append(f"- Unique parts: {len(groups)} placed + 2 loose plugs; Extended parts: {len(extended)} "
                 f"(${EXTENDED_FEE:.2f} each per order)")
    lines.append(f"- Joints per board: {smt} SMT, {tht} through-hole")
    lines.append("- Standard PCBA (through-hole assembly needs it), one side\n")
    lines.append("| Boards | Parts | Plugs | Extended fees | Setup + stencil | Joints | PCB (est.) | Shipping (est.) "
                 "| Total | Per board |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for n in QTYS:
        parts_cost = plugs_cost = 0.0
        for key, qty in per_board.items():
            if not info.get(key):
                continue
            unit = jlc.price_at(info[key]["prices"], qty * n)
            if key.endswith("_plug"):
                plugs_cost += unit * qty * n
            else:
                parts_cost += unit * qty * n
        fees = EXTENDED_FEE * len(extended)
        setup = PCBA_SETUP + STENCIL
        jnt = (smt * SMT_JOINT + tht * THT_JOINT) * n
        total = parts_cost + plugs_cost + fees + setup + jnt + PCB_FAB[n] + SHIPPING[n]
        lines.append(f"| {n} | ${parts_cost:.2f} | ${plugs_cost:.2f} | ${fees:.2f} | ${setup:.2f} | ${jnt:.2f} "
                     f"| ${PCB_FAB[n]:.2f} | ${SHIPPING[n]:.2f} | ${total:.2f} | ${total / n:.2f} |")
    lines.append("\n## Parts\n")
    lines.append("| Part | LCSC | Per board | Library | Stock | Unit @30 boards |")
    lines.append("|---|---|---|---|---|---|")
    for key, qty in per_board.items():
        i = info.get(key)
        p = PARTS[key]
        if i:
            lines.append(f"| {p.mpn or p.value} | {p.lcsc} | {qty} | {'Basic' if i['lib'] == 'base' else 'Extended'} "
                         f"| {i['stock']} | ${jlc.price_at(i['prices'], qty * 30):.4f} |")
        else:
            lines.append(f"| {p.mpn or p.value} | {p.lcsc} | {qty} | ? | ? | (offline) |")
    (OUT / "cost.md").write_text("\n".join(lines) + "\n", encoding="utf8", newline="\n")


def main():
    offline = "--offline" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    gerbers()
    groups = bom()
    cpl()
    plugs()
    cost(groups, offline)
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
