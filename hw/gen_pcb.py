"""Write hw/c6-energy-relay.kicad_pcb (outline, placement, rules, zones) and hw/out/board_features.json.

Run with KiCad's Python, after gen_sch.py:
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" hw/gen_pcb.py
then hw/route.py adds the tracks and fills the zones.

Coordinates in this file: mm, origin at the board's top-left corner, y down (KiCad's sense); the board
sits at (OX, OY) on the KiCad page. board_features.json uses origin lower-left, y up (for the case).

Floor plan (board 80 x 80, mounted upright: bottom edge = terminals, top edge = USB-C + antenna):
  bottom-left   CT terminal J4, burdens, BL0939 filters above it, ZMPT secondary
  bottom-middle input J1 between its two fusible resistors F1 (L) / F2 (N); MOV and the ZMPT divider
                between the fuses; HLK-PM01 standing above with its AC pins at the bottom
  bottom-right  relays K1, K2 (coil up, contacts down) over their terminals J2, J3
  top           USB-C (left), GPIO header, LDO, LED, ESP32-C6 module with the antenna in the top-right
                corner, relay drivers under the module
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hw import design  # noqa: E402
from hw.parts import PARTS  # noqa: E402

PCB = HERE / "c6-energy-relay.kicad_pcb"
DRU = HERE / "c6-energy-relay.kicad_dru"
FEATURES = HERE / "out" / "board_features.json"
KICAD_FP = Path(r"C:\Program Files\KiCad\10.0\share\kicad\footprints")

W, H = 80.0, 80.0
OX, OY = 100.0, 50.0
CORNER_R = 2.0

# ref: (x, y, rotation) in board coordinates (y down)
PLACE = {
    # ---- mains ---------------------------------------------------------------------------------
    "J1": (30.0, 70.0, 0), "F1": (23.0, 67.5, 90), "F2": (42.0, 67.5, 90),
    "RV1": (28.5, 56.0, 0), "PS1": (30.0, 49.0, 90),
    "T1": (10.5, 54.0, 180),
    "R1": (26.6, 63.0, 270), "R2": (29.1, 63.0, 90), "R3": (31.6, 63.0, 270), "R4": (34.1, 63.0, 90),
    "R5": (37.7, 61.54, 0),
    "K1": (53.9, 57.5, 90), "J2": (53.9 - 2.54, 70.0, 0),
    "K2": (72.48, 57.5, 90), "J3": (72.48 - 2.54, 70.0, 0),
    # ---- CT input and metering -----------------------------------------------------------------
    "J4": (3.2, 73.95, 0),
    "FB1": (3.2, 70.6, 90), "FB2": (7.01, 70.6, 90), "FB3": (10.82, 70.6, 90), "FB4": (14.63, 70.6, 90),
    "R8": (3.2, 66.6, 90), "R9": (7.01, 66.6, 90), "R10": (10.82, 66.6, 90), "R11": (14.63, 66.6, 90),
    "U2": (14.0, 33.0, 0),
    # RC filters: one row per input, R (CT side left) then C to GND, rows 3.2 apart
    "R12": (2.02, 31.1, 0), "R13": (2.72, 34.3, 0), "R14": (3.42, 37.5, 0), "R15": (4.12, 40.7, 0),
    "R7": (3.4, 43.9, 0),
    "C1": (6.5, 31.875, 270), "C2": (6.5, 35.075, 270), "C3": (6.5, 38.275, 270), "C4": (6.5, 41.475, 270),
    "C5": (6.5, 44.675, 270),
    "R6": (4.6, 47.4, 0),
    "C6": (11.0, 26.0, 0), "R16": (19.2, 32.8, 90), "R17": (19.2, 27.0, 270),
    "TP1": (12.6, 42.9, 0), "TP2": (13.0, 39.6, 0), "TP3": (15.6, 41.4, 0),
    # ---- USB, power ----------------------------------------------------------------------------
    "J5": (11.0, 4.2, 180), "U4": (11.0, 11.8, 0), "R20": (3.6, 6.0, 180), "R21": (5.6, 11.6, 270),
    "D1": (20.0, 11.5, 180),
    "U3": (44.0, 7.8, 0), "C8": (41.0, 10.5, 90), "C10": (46.4, 3.6, 0), "C12": (44.6, 12.6, 90),
    "C13": (61.6, 46.8, 270),
    # ---- MCU: module turned so the antenna points out of the right edge ---------------------------
    "U1": (68.8, 12.0, 270),
    "C11": (72.4, 1.3, 0), "C7": (72.6, 3.6, 0), "R22": (66.5, 2.3, 180), "D4": (63.3, 2.3, 0),
    "SW1": (37.0, 6.0, 0), "R18": (42.5, 2.9, 270), "C9": (37.0, 2.2, 0),
    "SW2": (50.5, 17.5, 0), "R19": (59.0, 36.2, 180),
    "J6": (45.0, 33.54, 90),
    # ---- relay drivers -------------------------------------------------------------------------
    "Q1": (54.5, 41.5, 0), "D2": (54.5, 45.8, 0), "R23": (50.4, 40.5, 0), "R25": (50.4, 42.7, 0),
    "Q2": (70.5, 41.5, 0), "D3": (70.5, 45.8, 0), "R24": (66.4, 40.5, 0), "R26": (66.4, 42.7, 0),
}
HOLES = [(3.5, 21.0), (77.0, 37.5), (22.3, 77.5), (28.5, 4.5)]
ANTENNA_KEEPOUT = (74.4, 0.0, W, 33.6)          # x0, y0, x1, y1 (y down); = the module footprint's own keep-out
def _relay_copper(k):
    """COM and NO contact copper for relay k: 5 mm wide, 4 mm apart (the open contact sees line
    voltage), from the relay pin down to the terminal pin."""
    cx = PLACE[f"K{k}"][0]
    com = [(cx - 7.0, 60.4), (cx - 2.0, 60.4), (cx - 2.0, 72.4), (cx - 7.0, 72.4)]
    no = [(cx + 2.0, 62.9), (cx + 7.0, 62.9), (cx + 7.0, 72.4), (cx + 2.0, 72.4)]
    return ({f"K{k}_COM": com, f"K{k}_NO": no},
            {f"K{k}_COM": [(cx - 5.5, 66.5), (cx - 5.5, 69.5)], f"K{k}_NO": [(cx + 5.5, 68.0), (cx + 5.5, 71.0)]})


RELAY_ZONES, STITCH = {}, {}  # net: polygon (y down); net: stitching vias
for _k in (1, 2):
    _z, _s = _relay_copper(_k)
    RELAY_ZONES.update(_z)
    STITCH.update(_s)
H3_RING = 4.5   # no copper around H3: its screw sits between L_IN and the CT / ground area

MM = pcbnew.FromMM


def NET(name: str) -> str:
    """Board net name for a design net (schematic local labels on the root sheet give "/NAME")."""
    return "/" + name


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def to_features(x, y):
    """board (y down) -> case/features coordinates (origin lower-left, y up)"""
    return round(x, 3), round(H - y, 3)


# ----------------------------------------------------------------------------------------------
_io = pcbnew.PCB_IO_KICAD_SEXPR()


def load_fp(fpid: str) -> pcbnew.FOOTPRINT:
    lib, name = fpid.split(":")
    path = HERE / "lib" / "c6er.pretty" if lib == "c6er" else KICAD_FP / f"{lib}.pretty"
    fp = _io.FootprintLoad(str(path), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def seg(board, layer, a, b, w=0.1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(layer)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetWidth(MM(w))
    board.Add(s)
    return s


def arc(board, layer, start, mid, end, w=0.1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    s.SetLayer(layer)
    s.SetArcGeometry(P(*start), P(*mid), P(*end))
    s.SetWidth(MM(w))
    board.Add(s)


def outline(board):
    r = CORNER_R
    seg(board, pcbnew.Edge_Cuts, (r, 0), (W - r, 0))
    seg(board, pcbnew.Edge_Cuts, (W, r), (W, H - r))
    seg(board, pcbnew.Edge_Cuts, (W - r, H), (r, H))
    seg(board, pcbnew.Edge_Cuts, (0, H - r), (0, r))
    k = r * (1 - math.sqrt(0.5))
    arc(board, pcbnew.Edge_Cuts, (0, r), (k, k), (r, 0))
    arc(board, pcbnew.Edge_Cuts, (W - r, 0), (W - k, k), (W, r))
    arc(board, pcbnew.Edge_Cuts, (W, H - r), (W - k, H - k), (W - r, H))
    arc(board, pcbnew.Edge_Cuts, (r, H), (k, H - k), (0, H - r))


def text(board, s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * (0.2 if bold else 0.15)))
    t.SetTextAngleDegrees(rot)
    if layer in (pcbnew.B_SilkS, pcbnew.B_Fab):
        t.SetMirrored(True)
    board.Add(t)
    return t


def zone(board, net, layers, pts, priority=0, rule_area=False, full=False, name=""):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    z.SetLayerSet(ls)
    poly = z.Outline()
    poly.NewOutline()
    for x, y in pts:
        poly.Append(MM(OX + x), MM(OY + y))
    if rule_area:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(net)
        z.SetAssignedPriority(priority)
        z.SetMinThickness(MM(0.25))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if full else pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(MM(0.4))
        z.SetThermalReliefSpokeWidth(MM(0.5))
        z.SetLocalClearance(MM(0.3))
    if name:
        z.SetZoneName(name)
    board.Add(z)
    return z


def via(board, net, x, y, size=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y))
    v.SetWidth(MM(size))
    v.SetDrill(MM(drill))
    v.SetNet(net)
    board.Add(v)
    return v


# ----------------------------------------------------------------------------------------------
def write_dru():
    mains = ["MAINS_L", "MAINS_N", "MAINS_DIV", "RELAY1", "RELAY2"]

    def any_of(item, classes):
        return "(" + " || ".join(f"{item}.NetClass == '{c}'" for c in classes) + ")"

    def pair(a, b):
        return f"(({any_of('A', a)} && {any_of('B', b)}) || ({any_of('A', b)} && {any_of('B', a)}))"

    mains_any = f"(({any_of('A', mains)} && !{any_of('B', mains)}) || ({any_of('B', mains)} && !{any_of('A', mains)}))"
    rated = "((A.memberOfFootprint('J1') && B.memberOfFootprint('J1')) || " \
            "(A.memberOfFootprint('PS1') && B.memberOfFootprint('PS1')))"
    rules = [
        ("mains to low voltage", mains_any, "6.5mm", "6.5mm"),
        ("L to N", pair(["MAINS_L"], ["MAINS_N"]), "4mm", "4mm"),
        ("L to N inside rated parts (5.08 mm terminal, HLK-PM01 pins)",
         f"{pair(['MAINS_L'], ['MAINS_N'])} && {rated}", "2mm", "2mm"),
        ("divider to L or N", pair(["MAINS_DIV"], ["MAINS_L", "MAINS_N"]), "1.5mm", None),
        ("input to relays", pair(["MAINS_L", "MAINS_N", "MAINS_DIV"], ["RELAY1", "RELAY2"]), "4mm", "4mm"),
        ("relay 1 to relay 2", pair(["RELAY1"], ["RELAY2"]), "4mm", "4mm"),
    ]
    for k in (1, 2):
        com, no = f"/K{k}_COM", f"/K{k}_NO"
        cond = f"((A.NetName == '{com}' && B.NetName == '{no}') || (A.NetName == '{no}' && B.NetName == '{com}'))"
        rules.append((f"relay {k} COM to NO (the open contact sees line voltage)", cond, "3mm", "4mm"))
        rules.append((f"relay {k} COM to NO inside its 5.08 mm terminal (slot between the pins)",
                      f"{cond} && A.memberOfFootprint('J{k + 1}') && B.memberOfFootprint('J{k + 1}')", "2mm", "2mm"))
    out = ["(version 1)\n",
           "# Generated by hw/gen_pcb.py. Mains creepage/clearance from the design spec.\n"]
    for name, cond, clr, crp in rules:
        out.append(f'(rule "{name}"\n  (condition "{cond}")\n  (constraint clearance (min {clr}))\n')
        if crp:
            out.append(f"  (constraint creepage (min {crp}))\n")
        out.append(")\n")
    out.append('(rule "relay contact copper"\n  (condition "A.NetClass == \'RELAY1\' || A.NetClass == \'RELAY2\'")\n'
               "  (constraint track_width (min 2.5mm))\n)\n")
    out.append('(rule "mains copper to board edge"\n  (condition "A.NetClass == \'MAINS_L\' || A.NetClass == \'MAINS_N\'"'
               ")\n  (constraint edge_clearance (min 0.5mm))\n)\n")
    DRU.write_text("".join(out), encoding="utf8", newline="\n")


# ----------------------------------------------------------------------------------------------
def tight_courtyard(fp):
    """Replace a footprint's courtyard with its fab-layer body + 0.25 mm. Used for the ESP32-C6 module
    (the stock courtyard includes Espressif's 43 x 31 mm antenna clearance, which is a rule area here)
    and the HLK-PM01 (the stock one is for the larger HLK-PMxx family outline)."""
    for item in list(fp.GraphicalItems()):
        if item.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            fp.Remove(item)
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.F_Fab:
            b = g.GetBoundingBox()
            xs += [b.GetLeft(), b.GetRight()]
            ys += [b.GetTop(), b.GetBottom()]
    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    s.SetLayer(pcbnew.F_CrtYd)
    s.SetWidth(MM(0.05))
    s.SetStart(pcbnew.VECTOR2I(min(xs) - MM(0.25), min(ys) - MM(0.25)))
    s.SetEnd(pcbnew.VECTOR2I(max(xs) + MM(0.25), max(ys) + MM(0.25)))
    fp.Add(s)


def schematic_nets() -> dict:
    """(ref, pin) -> net name, from KiCad's own netlist export (includes the "unconnected-(...)" nets
    KiCad gives unused pins, so the board matches the schematic exactly)."""
    import re
    import subprocess
    import tempfile
    out = Path(tempfile.gettempdir()) / "c6er_netlist.net"
    subprocess.run([str(Path(sys.executable).parent / "kicad-cli.exe"), "sch", "export", "netlist",
                    "--format", "kicadsexpr", "-o", str(out), str(HERE / "c6-energy-relay.kicad_sch")],
                   check=True, capture_output=True)
    text = out.read_text(encoding="utf8")
    pins = {}
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\n\s*\(net\s|\Z)', text, re.S):
        for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
            pins[(ref, pin)] = m.group(1)
    return pins


def build() -> pcbnew.BOARD:
    board = pcbnew.NewBoard(str(PCB))
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    ds.SetAuxOrigin(P(0, H))  # lower-left corner: origin for the gerbers, drill and CPL files

    pin_nets = schematic_nets()
    nets = {}
    for name in sorted(set(pin_nets.values())):
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name.lstrip("/")] = n

    outline(board)

    for c in design.COMPONENTS:
        x, y, rot = PLACE[c.ref]
        fp = load_fp(c.footprint)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH(f"/{design.ROOT_UUID}/{c.uuid}"))
        for key, val in (("LCSC", c.lcsc), ("MPN", PARTS[c.part].mpn if c.part else "")):
            if c.part:
                fp.SetField(key, val)
                fp.GetField(key).SetVisible(False)
        if c.ref in ("J5", "J6"):
            fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        attrs = fp.GetAttributes()
        if c.dnp:
            attrs |= pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_DNP
        fp.SetAttributes(attrs)
        if c.dnp:
            fp.SetDNP(True)
        for pad in fp.Pads():
            net = pin_nets.get((c.ref, pad.GetNumber()))
            if net:
                assert net.lstrip("/") == c.pins.get(pad.GetNumber(), net.lstrip("/")), (c.ref, pad.GetNumber())
                pad.SetNet(nets[net.lstrip("/")])
        board.Add(fp)
        if c.ref in ("U1", "PS1"):
            tight_courtyard(fp)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        fp.Reference().SetTextThickness(MM(0.12))

    for i, (x, y) in enumerate(HOLES, start=1):
        fp = load_fp("MountingHole:MountingHole_3.2mm_M3")
        fp.SetReference(f"H{i}")
        fp.SetPosition(P(x, y))
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM
                         | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        fp.Reference().SetVisible(False)
        board.Add(fp)

    # antenna keep-out (both layers): no copper, tracks or vias beside/under the PCB antenna
    x0, y0, x1, y1 = ANTENNA_KEEPOUT
    zone(board, None, [pcbnew.F_Cu, pcbnew.B_Cu], [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], rule_area=True,
         name="antenna keep-out")

    # no copper around H3 (its screw would otherwise bridge L_IN to the ground pour)
    hx, hy = HOLES[2]
    ring = [(hx + H3_RING * math.cos(a * math.pi / 16), hy + H3_RING * math.sin(a * math.pi / 16))
            for a in range(32)]
    zone(board, None, [pcbnew.F_Cu, pcbnew.B_Cu], ring, rule_area=True, name="H3 screw keep-out")

    # ground pour, both layers, whole board; DRU clearances keep it 6.5 mm off mains copper
    inset = 0.3
    gnd_poly = [(inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)]
    zone(board, nets["GND"], [pcbnew.F_Cu], gnd_poly, priority=0, name="GND top")
    zone(board, nets["GND"], [pcbnew.B_Cu], gnd_poly, priority=0, name="GND bottom")

    # relay contact copper: both layers, solid pad connection, solder mask open
    for net, pts in RELAY_ZONES.items():
        zone(board, nets[net], [pcbnew.F_Cu, pcbnew.B_Cu], pts, priority=10, full=True, name=net)
        for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
            m = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
            m.SetLayer(layer)
            m.SetFilled(True)
            m.SetWidth(0)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            m.SetPolyPoints([P(min(xs) + 0.6, min(ys) + 0.6), P(max(xs) - 0.6, min(ys) + 0.6),
                             P(max(xs) - 0.6, max(ys) - 0.6), P(min(xs) + 0.6, max(ys) - 0.6)])
            board.Add(m)
        for x, y in STITCH[net]:
            via(board, nets[net], x, y, size=1.2, drill=0.6)

    silkscreen(board)
    return board


def silkscreen(board):
    B = pcbnew.B_SilkS
    text(board, "C6 ENERGY RELAY v1.0", 32.0, 11.6, 1.0, bold=True)
    text(board, "MAINS 100-240V~", 45.6, 72.6, 0.9, rot=90, bold=True)
    # the bottom side under the mains area is bare, so the full warning goes there
    text(board, "DANGER: MAINS VOLTAGE", 34.0, 57.5, 1.5, layer=B, bold=True)
    text(board, "keep 6.5 mm clear, no metal near", 34.0, 60.0, 1.0, layer=B)
    text(board, "C6 ENERGY RELAY v1.0", 40.0, 26.0, 1.5, layer=B, bold=True)
    text(board, "USB-C: power and flashing (isolated from mains)", 40.0, 29.0, 1.0, layer=B)
    # terminal names on the bottom silk (the header bodies cover the top side) and short ones on top
    for ref, labels in (("J1", ["L", "N/L2"]), ("J2", ["COM", "NO"]), ("J3", ["COM", "NO"]),
                        ("J4", ["CT1+", "CT1-", "CT2+", "CT2-"])):
        x, y, _ = PLACE[ref]
        pitch = 3.81 if ref == "J4" else 5.08
        for i, lab in enumerate(labels):
            text(board, lab, x + i * pitch, 78.4, 0.9, layer=B)
    text(board, "L", 30.0, 66.3, 1.0, bold=True)
    text(board, "N/L2", 35.08, 66.3, 0.8, bold=True)
    text(board, "RELAY 1", PLACE["K1"][0], 75.8, 1.0, layer=B, bold=True)
    text(board, "RELAY 2", PLACE["K2"][0], 75.8, 1.0, layer=B, bold=True)
    text(board, "CT", 9.0, 62.6, 0.9, bold=True)
    # GPIO header pin names: odd row (y0) labelled below it, even row (y0 - 2.54) above it
    x0, y0, _ = PLACE["J6"]
    strap = {"IO4", "IO5", "IO8", "IO15"}
    for i, net in enumerate(design.HEADER_PINS):
        col, row = divmod(i, 2)
        x = x0 + col * 2.54
        lab = net.replace("IO", "") + ("*" if net in strap else "")
        if row == 0:
            text(board, lab, x, y0 + 1.75, 0.6)
        else:
            text(board, lab, x, y0 - 2.54 - 1.6, 0.6)
    text(board, "GPIO   * = strapping pin", 50.5, 36.2, 0.6)
    text(board, "EN", PLACE["SW1"][0], PLACE["SW1"][1] - 3.6, 0.8)
    text(board, "BOOT", PLACE["SW2"][0], PLACE["SW2"][1] + 3.6, 0.8)


def features(board) -> dict:
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def conn(ref, kind, edge, n, pitch, depth, plug_len, z_span):
        """plug_envelope = box the mated plug (or USB cable plug) may occupy, case coordinates:
        x/y as the board (origin lower-left), z = 0 at the PCB's bottom face. Datasheet sizes plus margin:
        DB2EK 5.08 plug 18.2 long x 15.2 high, WJ15EDGK 3.81 plug ~15 x 12, USB-C cable overmould 12 x 7."""
        x, y, _ = PLACE[ref]
        fx, fy = to_features(x, y)
        body_w = n * pitch + (0.88 if kind == "term381" else 0)
        x0 = x - (pitch / 2 + (0.44 if kind == "term381" else 0))
        if edge == "bottom":
            env = [x0 - 0.5, -plug_len, z_span[0], x0 + body_w + 0.5, 0.0, z_span[1]]
        else:
            env = [fx - 6.0, H, z_span[0], fx + 6.0, H + plug_len, z_span[1]]
        return {"ref": ref, "kind": kind, "edge": edge, "x": fx, "y": fy, "w": round(body_w, 3),
                "h": depth, "plug_envelope": [round(v, 3) for v in env]}

    cons = [
        conn("J1", "term508", "bottom", 2, 5.08, 12.0, 19.0, (-2.5, 15.5)),
        conn("J2", "term508", "bottom", 2, 5.08, 12.0, 19.0, (-2.5, 15.5)),
        conn("J3", "term508", "bottom", 2, 5.08, 12.0, 19.0, (-2.5, 15.5)),
        conn("J4", "term381", "bottom", 4, 3.81, 7.25, 16.0, (-2.0, 12.5)),
        conn("J5", "usbc", "top", 1, 9.0, 7.35, 20.0, (-0.5, 7.0)),
    ]
    hot = []
    for ref in ("PS1", "K1", "K2", "F1", "F2"):
        bb = fps[ref].GetCourtyard(pcbnew.F_CrtYd).BBox()
        x0, y1 = (bb.GetLeft() / 1e6 - OX, H - (bb.GetTop() / 1e6 - OY))
        x1, y0 = (bb.GetRight() / 1e6 - OX, H - (bb.GetBottom() / 1e6 - OY))
        hot.append([round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)])
    centres = {}
    for ref, fp in fps.items():
        pads = list(fp.Pads())
        if not pads:
            continue
        xs = [b for p in pads for b in (p.GetBoundingBox().GetLeft(), p.GetBoundingBox().GetRight())]
        ys = [b for p in pads for b in (p.GetBoundingBox().GetTop(), p.GetBoundingBox().GetBottom())]
        centres[ref] = list(to_features((min(xs) + max(xs)) / 2e6 - OX, (min(ys) + max(ys)) / 2e6 - OY))
    ax0, ay0, ax1, ay1 = ANTENNA_KEEPOUT
    return {
        "part_centres": centres,
        "outline_mm": [W, H], "thickness": 1.6, "corner_r": CORNER_R,
        "holes": [[*to_features(x, y), 3.2] for x, y in HOLES],
        "connectors": cons,
        "led": list(to_features(*PLACE["D4"][:2])),
        "buttons": [list(to_features(*PLACE[r][:2])) for r in ("SW1", "SW2")],
        "antenna_keepout": [ax0, H - ay1, ax1, H - ay0],
        "hot_parts": hot,
        "max_component_height": 18.5,  # ZMPT107-1 18.2 mm; relay 15.5; HLK-PM01 15
    }


def main():
    write_dru()
    board = build()
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(PCB), board)
    FEATURES.parent.mkdir(exist_ok=True)
    FEATURES.write_text(json.dumps(features(board), indent=1), encoding="utf8")
    print("wrote", PCB, "and", FEATURES)


if __name__ == "__main__":
    main()
