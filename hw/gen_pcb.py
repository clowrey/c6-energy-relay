"""Write hw/c6-energy-relay.kicad_pcb (outline, placement, rules, zones) and hw/out/board_features.json.

Run with KiCad's Python, after gen_sch.py:
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" hw/gen_pcb.py
then hw/route.py adds the tracks and fills the zones.

Coordinates in this file: mm, origin at the board's top-left corner, y down (KiCad's sense); the board
sits at (OX, OY) on the KiCad page. board_features.json uses origin lower-left, y up (for the case).

Floor plan (board 74.5 x 78, mounted upright: bottom edge = terminals, top edge = Qwiic, USB-C, antenna):
  left column   CT terminal J4 and burdens at the bottom, the ZMPT107 T1 above them (secondary on the left), then
                the bead row, the BL0939 U2 with its RC filters on the far left, Qwiic J7 at the top-left corner
  middle        mains input J1 between its fuses F1 / F2, the divider between the fuses, the MOV above them and the
                HLK-PM01 PS1 standing on top: L_F runs straight up the fuse, MOV and supply pins. Above PS1 the
                top band: USB-C J5, OR-ing diode D1, AMS1117 U3 and the module's decoupling, in a row
  right         ESP32-C5 module U1 at the top-right corner, its antenna over a cut-out in the board; EN button
                beside its left pins, BOOT button and LED under it, the 2 x 8 GPIO header J6 centred under it, the
                relay drivers on either side below the header, relays K1 / K2 over their terminals J2 / J3
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

W, H = 76.4, 80.0
OX, OY = 100.0, 50.0
CORNER_R = 3.0
# the antenna cut-out: the module's antenna end hangs over air in the top-right corner of the board
NOTCH_Y, NOTCH_R = 6.3, 1.0                     # its depth and inner corner radius

# The plug headers along the bottom edge stick out TERM_OUT past it, so their mouths sit flush with the outside of
# the case wall (0.8 mm gap + 2.2 mm wall) and a plug finds them easily. USB-C sticks out USB_OUT: as far as its
# front shell legs allow (their pads keep 0.6 mm from the edge).
TERM_OUT = 3.0
USB_OUT = 1.25
TERM_Y = H - 10.0 + TERM_OUT   # pin row of the 5.08 mm headers
K1_X, K2_X = 50.3, 68.7        # relay centres: 18.4 apart (contact copper 4 mm apart, room for a screw between)
K_Y = H - 19.5                 # relay centre row: the relay body ends just above its terminal
UX, UY = (K1_X + K2_X) / 2, 12.75   # module centre: antenna end on the top edge, centred over the relay pair
NOTCH_X = UX - 9.6                  # the cut-out's left edge, just outside the module body
HX, HY = UX - 3.5 * 2.54, 41.84     # GPIO header: pin 1 and the lower (odd) row
U2X, U2Y = 11.9, 36.0               # BL0939
JX = 21.5                          # USB-C centre
FX1, FX2, F_Y = 23.8, 37.6, H - 16.0     # fuses
PX, PY = 23.8, H - 32.6             # HLK-PM01 L pin (its N pin is 5 mm right); L_F runs straight up x = PX

# ref: (x, y, rotation) in board coordinates (y down)
PLACE = {
    # ---- mains: input, fuses, divider, MOV, supply -----------------------------------------------
    "J1": (28.4, TERM_Y, 0), "F1": (FX1, F_Y, 90), "F2": (FX2, F_Y, 90),
    # divider between the fuses, two columns 5.8 mm apart: ZP1 (at L) enters top-left, N_F leaves top-right under the
    # MOV's N pin, 4 mm away
    "R1": (27.8, F_Y - 4.0, 270), "R2": (27.8, F_Y + 1.0, 270),
    "R3": (33.6, F_Y + 1.0, 90), "R4": (33.6, F_Y - 4.0, 90),
    "RV1": (PX + 2.2, PY + 5.3, 0), "PS1": (PX, PY, 90),
    "T1": (10.5, H - 23.1, 180),
    "K1": (K1_X, K_Y, 90), "J2": (K1_X - 2.54, TERM_Y, 0),
    "K2": (K2_X, K_Y, 90), "J3": (K2_X - 2.54, TERM_Y, 0),
    # ---- CT input and metering -----------------------------------------------------------------
    "J4": (3.2, H - 6.05 + TERM_OUT, 0),
    "R8": (3.2, H - 7.9, 90), "R9": (7.01, H - 7.9, 90), "R10": (10.82, H - 7.9, 90), "R11": (14.63, H - 7.9, 90),
    # beads in a row above T1, in CT order; the filtered lines then run up the left edge to their RC rows
    "R6": (3.0, H - 30.4, 90),   # the ZMPT107 load, right at its secondary
    "FB1": (5.4, H - 30.5, 90), "FB2": (7.2, H - 30.5, 90), "FB3": (9.0, H - 30.5, 90), "FB4": (10.8, H - 30.5, 90),
    "U2": (U2X, U2Y, 0),
    # RC filters: one row per input, R (CT side left) then C to GND
    "R12": (3.6, U2Y - 5.125, 0), "R13": (3.6, U2Y - 3.225, 0),
    "R14": (3.6, U2Y + 1.775, 0), "R15": (3.6, U2Y + 3.675, 0), "R7": (3.6, U2Y + 8.675, 0),
    "C1": (6.1, U2Y - 5.9, 90), "C2": (6.1, U2Y - 2.45, 270),
    "C3": (6.1, U2Y + 1.0, 90), "C4": (6.1, U2Y + 4.45, 270), "C5": (6.1, U2Y + 7.9, 90),
    "C6": (U2X - 1.3, U2Y - 6.6, 0), "R17": (U2X - 0.3, U2Y - 8.5, 0),
    # SEL pull-down and the CF / I_LEAK / ZX test pads in a row under the chip, fed from under its body
    "R16": (U2X - 3.0, U2Y + 7.9, 270),
    "TP1": (U2X - 0.9, U2Y + 7.6, 0), "TP3": (U2X + 1.2, U2Y + 8.4, 0), "TP2": (U2X + 2.7, U2Y + 6.6, 0),
    # ---- top band: Qwiic, USB-C, power ---------------------------------------------------------
    "J7": (9.75, 3.3, 180), "R30": (12.6, 11.0, 180), "R31": (9.0, 11.0, 0),
    "J5": (JX, 3.7 - USB_OUT, 180),
    "R21": (JX - 3.3, 9.6, 270), "R28": (JX - 1.05, 9.6, 270), "R29": (JX + 1.2, 9.6, 270), "R20": (JX + 3.45, 9.6, 270),
    "D1": (29.8, 11.6, 180), "R27": (24.2, 13.7, 180),
    "U3": (35.43, 4.8, 270), "C12": (30.31, 3.0, 90), "C8": (28.05, 3.0, 90),
    "C10": (UX - 18.945, 6.6, 90), "C11": (UX - 16.445, 6.6, 90), "C7": (UX - 14.2, 6.4, 90),
    "C14": (UX - 16.6, 27.0, 90),
    # ---- MCU: ESP32-C5 at the top-right corner ----------------------------------------------------
    "U1": (UX, UY, 0),
    "R18": (UX - 11.2, 9.4, 270), "SW1": (UX - 15.5, 13.2, 270), "C9": (UX - 15.5, 18.15, 180),
    "SW2": (UX + 1.0, 29.8, 0), "R22": (UX + 7.3, 27.9, 180), "D4": (UX + 7.3, 30.2, 180),
    "J6": (HX, HY, 90), "R19": (HX + 4 * 2.54, HY + 3.9, 90),
    # ---- relay drivers below the header, one group over each relay's coil pins -------------------
    "D2": (K1_X - 0.8, HY + 7.06, 0), "Q1": (K1_X + 3.8, HY + 5.86, 270),
    "R23": (K1_X + 0.4, HY + 3.96, 0), "R25": (K1_X + 7.0, HY + 5.26, 90),
    "D3": (K2_X - 0.8, HY + 7.06, 0), "Q2": (K2_X + 3.8, HY + 5.86, 270),
    "R24": (K2_X + 0.2, HY + 3.96, 0), "R26": (K2_X + 6.65, HY + 6.06, 90),
    "C13": (K2_X - 5.2, HY + 5.26, 90),
}
# the case's four screws run from the back plate through these holes into the cover, so each screw is reachable from
# outside: every hole edge keeps 6.5 mm from mains copper. One between the relays, below their coil pins
HOLES = [(3.4, 10.7), (3.4, H - 13.9), ((K1_X + K2_X) / 2, H - 27.4), (W - 2.7, 40.2)]
ANTENNA_KEEPOUT = (UX - 13.4, 0.0, W, 7.6)     # x0, y0, x1, y1 (y down): no copper under or beside U1's antenna,
                                                # reaching 3.8 mm past the module's left side
# solid 3V3 heat spreader on U3's SOT-223 tab, up to the module's decoupling capacitors
LDO_3V3_ZONE = [(32.6, 0.7), (UX - 13.6, 0.7), (UX - 13.6, 8.1), (UX - 12.0, 8.1), (UX - 12.0, 9.7), (32.6, 9.7)]


def _relay_copper(k):
    """COM and NO contact copper for relay k: 5 mm wide, 4 mm apart (the open contact sees line
    voltage), from the relay pin down to the terminal pin."""
    cx, cy, _ = PLACE[f"K{k}"]
    y1 = TERM_Y + 2.4
    com = [(cx - 7.0, cy + 2.9), (cx - 2.0, cy + 2.9), (cx - 2.0, y1), (cx - 7.0, y1)]
    no = [(cx + 2.0, cy + 5.4), (cx + 7.0, cy + 5.4), (cx + 7.0, y1), (cx + 2.0, y1)]
    return ({f"K{k}_COM": com, f"K{k}_NO": no},
            {f"K{k}_COM": [(cx - 5.5, cy + 9.0), (cx - 5.5, cy + 12.0)],
             f"K{k}_NO": [(cx + 5.5, cy + 10.5), (cx + 5.5, cy + 13.5)]})


RELAY_ZONES, STITCH = {}, {}  # net: polygon (y down); net: stitching vias
for _k in (1, 2):
    _z, _s = _relay_copper(_k)
    RELAY_ZONES.update(_z)
    STITCH.update(_s)
FUSE_GAP = (1.6, 3.1)   # half width, half length of the copper-free area under each fuse, between its pads

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


# stock footprints whose KiCad 3D model isn't installed with every KiCad: use the project's own body
# (hw/gen_3d.py) so the renders, the board STEP and the case fit test all see the part
LOCAL_MODELS = {"SW_Push_1P1T_XKB_TS-1187A": "TS-1187A",
                "USB_C_Receptacle_HRO_TYPE-C-31-M-12": "USB-C-HRO-TYPE-C-31-M-12"}


def load_fp(fpid: str) -> pcbnew.FOOTPRINT:
    lib, name = fpid.split(":")
    path = HERE / "lib" / "c6er.pretty" if lib == "c6er" else KICAD_FP / f"{lib}.pretty"
    fp = _io.FootprintLoad(str(path), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    if name in LOCAL_MODELS:
        fp.Models().clear()
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = "${KIPRJMOD}/lib/c6er.3dshapes/" + LOCAL_MODELS[name] + ".step"
        fp.Models().append(m)
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
    """Rounded rectangle with the antenna cut-out at the top-right corner: the module's antenna end hangs over it."""
    r, nr, k = CORNER_R, NOTCH_R, 1 - math.sqrt(0.5)
    e = pcbnew.Edge_Cuts
    seg(board, e, (r, 0), (NOTCH_X - nr, 0))
    arc(board, e, (NOTCH_X - nr, 0), (NOTCH_X - nr * k, nr * k), (NOTCH_X, nr))
    seg(board, e, (NOTCH_X, nr), (NOTCH_X, NOTCH_Y - nr))
    arc(board, e, (NOTCH_X, NOTCH_Y - nr), (NOTCH_X + nr * k, NOTCH_Y - nr * k), (NOTCH_X + nr, NOTCH_Y))
    seg(board, e, (NOTCH_X + nr, NOTCH_Y), (W - r, NOTCH_Y))
    arc(board, e, (W - r, NOTCH_Y), (W - r * k, NOTCH_Y + r * k), (W, NOTCH_Y + r))
    seg(board, e, (W, NOTCH_Y + r), (W, H - r))
    arc(board, e, (W, H - r), (W - r * k, H - r * k), (W - r, H))
    seg(board, e, (W - r, H), (r, H))
    arc(board, e, (r, H), (r * k, H - r * k), (0, H - r))
    seg(board, e, (0, H - r), (0, r))
    arc(board, e, (0, r), (r * k, r * k), (r, 0))


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
        # divider rules: clearance only. The board is flat around the divider (no slots), so creepage
        # equals clearance there, and KiCad's creepage check gives random false hits on these pairs
        ("divider to L or N", pair(["MAINS_DIV"], ["MAINS_L", "MAINS_N"]), "1.5mm", None),
        ("divider nodes (two resistors apart see ~120 V)", pair(["MAINS_DIV"], ["MAINS_DIV"]), "1.5mm", None),
        ("input to relays", pair(["MAINS_L", "MAINS_N", "MAINS_DIV"], ["RELAY1", "RELAY2"]), "4mm", "4mm"),
        ("relay 1 to relay 2", pair(["RELAY1"], ["RELAY2"]), "4mm", "4mm"),
    ]
    # clearance only, as for the divider: flat board here, and KiCad's creepage check misreports these pairs
    for ref, pre, posts in (("F1", "/L_IN", ("/L_F", "/ZP1")), ("F2", "/N_IN", ("/N_F",))):
        cond = " || ".join(f"(A.NetName == '{a}' && B.NetName == '{b}')" for post in posts
                          for a, b in ((pre, post), (post, pre)))
        rules.append((f"across {ref} (an open fuse sees line voltage)", f"({cond})", "3mm", None))
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
    out.append('(rule "mains copper to board edge"\n  (condition "' + any_of("A", mains) + '")\n'
               "  (constraint edge_clearance (min 0.7mm))\n)\n")
    DRU.write_text("".join(out), encoding="utf8", newline="\n")


# ----------------------------------------------------------------------------------------------
def tight_courtyard(fp):
    """Replace a footprint's courtyard with its fab-layer body + 0.25 mm and its silkscreen with the body outline + 0.12
    mm. Used for the HLK-PM01 (the stock outlines are for the larger HLK-PMxx family)."""
    for item in list(fp.GraphicalItems()):
        if item.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd, pcbnew.F_SilkS):
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
    silk = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    silk.SetLayer(pcbnew.F_SilkS)
    silk.SetWidth(MM(0.12))
    silk.SetStart(pcbnew.VECTOR2I(min(xs) - MM(0.12), min(ys) - MM(0.12)))
    silk.SetEnd(pcbnew.VECTOR2I(max(xs) + MM(0.12), max(ys) + MM(0.12)))
    fp.Add(silk)


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
        if c.ref in ("J5", "J6", "J7"):   # J6: tracks leave its ground pins too few spokes for a thermal relief
            fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        if c.ref == "J6":       # the pin labels frame the header; its outline would cross them
            for it in list(fp.GraphicalItems()):
                if it.GetLayer() == pcbnew.F_SilkS:
                    fp.Remove(it)
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
        if c.ref == "PS1":
            tight_courtyard(fp)
        if c.ref == "PS1":      # beside the body, where nothing else wants the space
            fp.Reference().SetPosition(P(PX + 13.8, PY - 8.0))
            fp.Reference().SetTextAngleDegrees(90)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        fp.Reference().SetTextThickness(MM(0.12))
        if c.ref in ("J1", "J2", "J3", "J4", "J5", "J7"):      # these carry what they are for instead (labels())
            fp.Reference().SetVisible(False)

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

    # no copper under the fuses: an open, charred fuse must not find a bridge below it
    fw, fl = FUSE_GAP
    for ref in ("F1", "F2"):
        fx, fy, _ = PLACE[ref]
        zone(board, None, [pcbnew.F_Cu, pcbnew.B_Cu],
             [(fx - fw, fy - fl), (fx + fw, fy - fl), (fx + fw, fy + fl), (fx - fw, fy + fl)],
             rule_area=True, name=f"{ref} keep-out")

    # ground pour, both layers, whole board; DRU clearances keep it 6.5 mm off mains copper
    inset = 0.3
    gnd_poly = [(inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)]
    zone(board, nets["GND"], [pcbnew.F_Cu], gnd_poly, priority=0, name="GND top")
    zone(board, nets["GND"], [pcbnew.B_Cu], gnd_poly, priority=0, name="GND bottom")
    # 3V3 heat spreader on U3's SOT-223 tab (~46 mm^2 solid copper, directly feeding C10 and U1)
    zone(board, nets["3V3"], [pcbnew.F_Cu], LDO_3V3_ZONE, priority=5, full=True, name="LDO 3V3 heat spreader")

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
    place_references(board)
    return board


SILK_GAP = 0.2          # silk to silk, silk to pads


def _silk_obstacles(board, skip=None):
    """Shapes a silkscreen label must not touch: other silk (footprint graphics, board text, labels
    already placed), every pad and hole (JLC clips silk off copper), the board edge."""
    shapes = []
    for d in board.Drawings():
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.Edge_Cuts) and (skip is None or d.m_Uuid != skip.m_Uuid):
            shapes.append(d.GetEffectiveShape())
    for fp in board.GetFootprints():
        for it in fp.GraphicalItems():
            # footprint graphics (the reference is a field) and footprint cut-outs (terminal slots)
            if it.GetLayer() in (pcbnew.F_SilkS, pcbnew.Edge_Cuts):
                shapes.append(it.GetEffectiveShape())
        for pad in fp.Pads():
            shapes.append(pad.GetEffectiveShape(pcbnew.F_Cu))
            if pad.GetDrillSizeX():
                shapes.append(pad.GetEffectiveHoleShape())
    return shapes


def _clear(item, obstacles, gap=SILK_GAP, margin=0.5):
    bb = item.GetBoundingBox()
    if bb.GetLeft() < MM(OX + margin) or bb.GetRight() > MM(OX + W - margin)             or bb.GetTop() < MM(OY + margin) or bb.GetBottom() > MM(OY + H - margin):
        return False
    me = item.GetEffectiveShape()
    return not any(me.Collide(o, MM(gap)) for o in obstacles)


def place_references(board):
    """Move each visible reference designator to the first spot next to its part where it touches no
    other silk, pad or the board edge (KiCad's silk_overlap / silk_over_copper / silk_edge rules);
    hide it if there is none. Labels placed earlier count as obstacles for later ones."""
    fps = sorted((fp for fp in board.GetFootprints() if fp.Reference().IsVisible()),
                 key=lambda f: f.GetBoundingBox(False).GetArea())
    obstacles = _silk_obstacles(board)
    placed = []
    hidden = []
    for fp in fps:
        ref = fp.Reference()
        if _clear(ref, obstacles + placed):
            placed.append(ref.GetEffectiveShape())
            continue
        bb = fp.GetBoundingBox(False)           # pads and graphics, not the texts
        cx, cy = bb.GetCenter().x, bb.GetCenter().y
        hw, hh = bb.GetWidth() / 2, bb.GetHeight() / 2
        ok = False
        for d in (0.1, 0.4, 0.8, 1.3, 2.0):
            gap = MM(d + 0.5)
            spots = [(cx, cy - hh - gap, 0), (cx, cy + hh + gap, 0), (cx - hw - gap, cy, 90), (cx + hw + gap, cy, 90),
                     (cx - hw - gap - MM(0.8), cy, 0), (cx + hw + gap + MM(0.8), cy, 0),
                     (cx - hw, cy - hh - gap, 0), (cx + hw, cy - hh - gap, 0),
                     (cx - hw, cy + hh + gap, 0), (cx + hw, cy + hh + gap, 0)]
            for x, y, rot in spots:
                ref.SetTextAngleDegrees(rot)
                ref.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                if _clear(ref, obstacles + placed):
                    ok = True
                    break
            if ok:
                break
        if ok:
            placed.append(ref.GetEffectiveShape())
        else:
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    if hidden:
        print("references hidden (no free spot):", ", ".join(sorted(hidden)))


def _bottom_obstacles(board, skip=None):
    """What bottom-side text must not touch: through-hole pads and holes, the relay contacts' mask openings, other
    bottom silk and the board edge."""
    shapes = [p.GetEffectiveShape(pcbnew.B_Cu) for fp in board.GetFootprints() for p in fp.Pads()
              if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
    shapes += [p.GetEffectiveHoleShape() for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSizeX()]
    shapes += [d.GetEffectiveShape() for d in board.Drawings()
               if d.GetLayer() in (pcbnew.B_Mask, pcbnew.B_SilkS, pcbnew.Edge_Cuts)
               and (skip is None or d.m_Uuid != skip.m_Uuid)]
    return shapes


def fit(board, t, spots, what):
    """Move text t to the first (x, y, rotation, size) spot where it touches no silk, pad, hole or edge."""
    bottom = t.GetLayer() == pcbnew.B_SilkS
    obstacles = _bottom_obstacles(board, skip=t) if bottom else _silk_obstacles(board, skip=t)
    for x, y, rot, size in spots:
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * (0.2 if t.IsBold() else 0.15)))
        t.SetTextAngleDegrees(rot)
        t.SetPosition(P(x, y))
        if _clear(t, obstacles):
            return
    if os.environ.get("SILK_DEBUG"):
        x, y, rot, size = spots[0]
        t.SetTextAngleDegrees(rot)
        t.SetPosition(P(x, y))
        me = t.GetEffectiveShape()
        for o in obstacles:
            if me.Collide(o, MM(SILK_GAP)):
                bb = o.BBox()
                print("  blocked by", [round(v / 1e6 - d, 2) for v, d in ((bb.GetLeft(), OX), (bb.GetTop(), OY),
                                                                           (bb.GetRight(), OX), (bb.GetBottom(), OY))])
    raise AssertionError(f"no free spot for {what}")


def silkscreen(board):
    B = pcbnew.B_SilkS
    # ---- top: what each plug is ------------------------------------------------------------------
    # the CT pins above their burden resistors
    for i, lab in enumerate(("CT1+", "CT1-", "CT2+", "CT2-")):
        text(board, lab, PLACE["J4"][0] + i * 3.81, H - 11.3, 0.8, bold=True)
    # mains input: in the gap between the CT terminal and F1
    text(board, "MAINS", FX1 - 5.9, H - 10.5, 0.9, rot=90, bold=True)
    text(board, "100-240V~", FX1 - 4.4, H - 10.5, 0.9, rot=90, bold=True)
    # relays: relay 1 in the gap left of its contact copper, relay 2 between the relays
    for name, x in (("RELAY 1", K1_X - 9.6), ("RELAY 2", (K1_X + K2_X) / 2 - 0.8)):
        text(board, name, x, H - 12.0, 0.9, rot=90, bold=True)
        text(board, "COM NO", x + 1.45, H - 12.0, 0.8, rot=90, bold=True)
    # Qwiic pin names in the order of the pins: left to right on top, and left to right as read from the bottom
    qx = PLACE["J7"][0]
    i2c = {f"IO{design.GPIO['I2C_SDA']}": "SDA", f"IO{design.GPIO['I2C_SCL']}": "SCL"}
    names = [i2c.get(design.pin_net("J7", p), design.pin_net("J7", p)) for p in ("4", "3", "2", "1")]
    pins = text(board, " ".join(names), qx, 7.4, 0.8)
    fit(board, pins, [(qx + dx, y, 0, 0.8) for y in (7.4, 7.6, 7.8, 8.0) for dx in (0, -0.4, -0.8, -1.2, -1.6)],
        "Qwiic pins")
    q = text(board, "QWIIC", qx, 8.7, 0.9, bold=True)
    fit(board, q, [(qx + dx, y, 0, 0.9) for y in (8.7, 8.9, 9.1) for dx in (0, -0.5, -1.0, 0.5)], "QWIIC")
    # buttons
    en = text(board, "EN", 0, 0, 0.8, bold=True)
    sx, sy, _ = PLACE["SW1"]
    fit(board, en, [(sx - 3.3 - dx, sy, 90, 0.8) for dx in (0, 0.2, 0.4, 0.6)] +
        [(sx, sy + 6.2 + dy, 0, 0.8) for dy in (0, 0.3, 0.6)], "EN")
    boot = text(board, "BOOT", 0, 0, 0.8, bold=True)
    bx, by, _ = PLACE["SW2"]
    fit(board, boot, [(bx - 4.6 - dx, by, 90, 0.8) for dx in (0, 0.3, 0.6)] +
        [(bx, by + 3.7 + dy, 0, 0.8) for dy in (0, 0.3)], "BOOT")
    # GPIO header pin names: lower (odd) row labelled below it, upper (even) row above it
    x0, y0, _ = PLACE["J6"]
    strap = {f"IO{n}" for n in design.STRAPPING}
    for i, net in enumerate(design.HEADER_PINS):
        col, row = divmod(i, 2)
        lab = net.replace("IO", "").replace("+5V", "5V") + ("*" if net in strap else "")
        text(board, lab, x0 + col * 2.54, y0 + 1.6 if row == 0 else y0 - 2.54 - 1.75, 0.8)
    legend = text(board, "GPIO   * = strapping pin", 0, 0, 0.8)
    fit(board, legend, [(x0 + 8.9 + dx, y0 - 2.54 - 3.0 - dy, 0, 0.8) for dy in (0, 0.2, 0.4) for dx in (0, -1, 1)],
        "header legend")
    # board name: somewhere in the left column
    title = text(board, "C6 ENERGY RELAY v1.0", 0, 0, 1.0, bold=True)
    fit(board, title, [(x, y, 0, size) for size in (0.9, 0.8) for y in (23.5, 24.0, 23.0, 22.5, 22.0, 21.5)
                       for x in (7.7, 7.9, 7.5, 8.2)] +
        [(1.3, y, 90, size) for size in (0.9, 0.8) for y in (17.0, 18.0, 16.0)], "board title")

    # ---- bottom ----------------------------------------------------------------------------------
    # terminal names under the plugs (the header bodies cover the top side)
    for ref, labels in (("J1", ["L", "N/L2"]), ("J2", ["COM", "NO"]), ("J3", ["COM", "NO"]),
                        ("J4", ["CT1+", "CT1-", "CT2+", "CT2-"])):
        x, y, _ = PLACE[ref]
        pitch = 3.81 if ref == "J4" else 5.08
        for i, lab in enumerate(labels):
            text(board, lab, x + i * pitch, H - (5.4 if ref == "J4" else 1.6), 0.9, layer=B)
    for name, k in (("RELAY 1", K1_X), ("RELAY 2", K2_X)):
        text(board, name, k - 9.9, H - 3.4, 1.0, layer=B, bold=True)
    text(board, "QWIIC", qx, 2.0, 1.0, layer=B, bold=True)
    usb = text(board, "USB", JX, 12.5, 1.0, layer=B, bold=True)
    fit(board, usb, [(JX + dx, y, 0, 1.0) for y in (12.5, 13.5, 14.5) for dx in (0, -1, 1, -2, 2)], "USB")
    text(board, " ".join(reversed(names)), qx, 4.0, 0.9, layer=B)
    # the bottom side under the mains area: the full warning
    warn = text(board, "DANGER: MAINS VOLTAGE", 0, 0, 1.3, layer=B, bold=True)
    fit(board, warn, [(PX + 6 + dx, y, 0, size) for size in (1.3, 1.2, 1.1) for y in (40.0, 39.0, 38.0, 41.0, 37.0)
                      for dx in (0, -1, 1, -2, 2)], "mains warning")
    keep = text(board, "keep 6.5 mm clear, no metal near", 0, 0, 0.9, layer=B)
    wx, wy = warn.GetPosition().x / 1e6 - OX, warn.GetPosition().y / 1e6 - OY
    fit(board, keep, [(wx + dx, wy + dy, 0, 0.9) for dy in (2.2, 2.4, -2.2) for dx in (0, -1, 1, -2, 2)],
        "mains warning line 2")
    name = text(board, "C6 ENERGY RELAY v1.0", 0, 0, 1.4, layer=B, bold=True)
    fit(board, name, [(PX + 6 + dx, y, 0, size) for size in (1.4, 1.2) for y in (26.0, 27.0, 25.0, 28.0, 24.0)
                      for dx in (0, -1, 1, -2, 2)], "bottom title")
    note = text(board, "USB-C: power and flashing (isolated from mains)", 0, 0, 0.9, layer=B)
    nx, ny = name.GetPosition().x / 1e6 - OX, name.GetPosition().y / 1e6 - OY
    fit(board, note, [(nx + dx, ny + dy, 0, 0.9) for dy in (2.2, 2.4, -2.2) for dx in (0, -1, 1, -2, 2, 3)],
        "USB note")


def features(board) -> dict:
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def conn(ref, kind, edge, n, pitch, depth, plug_len, z_span):
        """plug_envelope = box the mated plug (or USB cable plug) may occupy, case coordinates:
        x/y as the board (origin lower-left), z = 0 at the PCB's bottom face. Datasheet sizes plus margin:
        DB2EK 5.08 plug 18.2 long x 15.2 high, WJ15EDGK 3.81 plug ~15 x 12, USB-C cable overmould 12 x 7.
        The plugs stand on the component side (z = 1.6, PCB top): nothing opens below the board."""
        x, y, _ = PLACE[ref]
        fx, fy = to_features(x, y)
        body_w = n * pitch + (0.88 if kind == "term381" else 2.0 if kind == "qwiic" else 0)
        x0 = x - (pitch / 2 + (0.44 if kind == "term381" else 0))
        if edge == "bottom":
            env = [x0 - 0.5, -plug_len - TERM_OUT, z_span[0], x0 + body_w + 0.5, 0.0, z_span[1]]
        elif kind == "qwiic":
            # SHR-04V-S-B plug: 7.0 mm wide with its ears, 2.8 mm high, on z = 1.6..4.5, and it ends inside the
            # wall. 11 x 6 mm envelope (the cover adds 1 mm all round: a 13 x 8 mm opening) leaves 3 mm each side
            # to grip the ears, and stays too low for a finger to pass
            env = [fx - 5.5, H, z_span[0], fx + 5.5, H + plug_len, z_span[1]]
        else:
            env = [fx - 6.0, H, z_span[0], fx + 6.0, H + plug_len, z_span[1]]
        return {"ref": ref, "kind": kind, "edge": edge, "x": fx, "y": fy, "w": round(body_w, 3),
                "h": depth, "plug_envelope": [round(v, 3) for v in env]}

    cons = [
        conn("J1", "term508", "bottom", 2, 5.08, 12.0, 19.0, (1.6, 17.6)),
        conn("J2", "term508", "bottom", 2, 5.08, 12.0, 19.0, (1.6, 17.6)),
        conn("J3", "term508", "bottom", 2, 5.08, 12.0, 19.0, (1.6, 17.6)),
        conn("J4", "term381", "bottom", 4, 3.81, 7.25, 16.0, (1.6, 14.2)),
        conn("J5", "usbc", "top", 1, 9.0, 7.35, 20.0, (-0.5, 7.0)),
        conn("J7", "qwiic", "top", 4, 1.0, 4.25, 16.0, (1.0, 7.0)),
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
