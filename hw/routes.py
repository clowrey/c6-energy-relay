"""Hand-routed tracks for the ESP32-C5 energy relay board (76.4 x 80 mm).

net -> list of paths {"layer": "F"|"B", "w": mm, "pts": [...], "vias": [...]}. Points are board coordinates (mm,
origin top-left, y down, as gen_pcb.PLACE) or pad references ("U1", "13"); a pad number that occurs twice takes an
index ("SW1", "1", 1). t() draws legs at 0, 45 and 90 degrees between the points; route.py cuts each right-angle corner
into two 45-degree bends (radii: the arc the corner is cut to, so concentric radii keep lanes evenly spaced) and
rounds every bend with a small arc. Style: 0.2 mm signals, 0.3-0.6 mm power, 0.6 / 0.3 mm vias, ground poured on both layers, a solid 3V3
pour on the LDO tab, no tracks under the module. Mains nets stay on the top layer (ZP1 crosses L_F underneath), 1.0 mm
(L / N) and 0.5 mm (divider); the relay contacts are copper zones.

The module's signals leave it in three groups: its left side feeds a five-lane bus (3V3, I2C, UART) that dives under
the EN button and runs under the HLK-PM01 to the Qwiic port and the BL0939; four GPIOs and relay 1's drive drop beside
it to the header and the driver below; the USB pair takes one hop on the bottom layer up to the USB-C socket. Its right
side fans down to the BOOT button, the LED and eight header pins; relay 2's drive runs down the right edge underneath.
"""
from __future__ import annotations

from hw.gen_pcb import HOLES, HX, HY, JX, PLACE, PX, U2X, U2Y, UX, UY, W  # noqa: E402

ROUTES: dict = {}


def t(net, *pts, w=0.2, layer="F", vias=(), radii=None, start=None, end=None):
    """Legs between the points at 0, 45 or 90 degrees (route.py splits any other leg into a straight and a 45-degree
    run), every bend rounded (radii: the radius at each point, None = default). start / end: the direction to leave
    the first point and to arrive at the last one, which picks the order of those two runs."""
    ROUTES.setdefault(net, []).append({"layer": layer, "w": w, "pts": list(pts), "vias": list(vias),
                                       "radii": list(radii) if radii else None, "start": start, "end": end})


def b(net, *pts, w=0.2, vias=()):
    t(net, *pts, w=w, layer="B", vias=vias)


def v(net, *pts):
    ROUTES.setdefault(net, []).append({"layer": "F", "w": 0.2, "pts": [], "vias": list(pts)})


def at(ref):
    return PLACE[ref][0], PLACE[ref][1]


def upin(n):
    """Board position of module pad n (1-14 down the left side, 15-28 up the right side)."""
    n = int(n)
    if n <= 14:
        return UX - 8.75, UY - 5.26 + (n - 1) * 1.27
    return UX + 8.75, UY - 5.26 + (28 - n) * 1.27


def hpin(k):
    """Board position of header pin k (odd pins in the lower row)."""
    col, row = divmod(k - 1, 2)
    return HX + col * 2.54, HY - 2.54 * row


def u2pin(n):
    """Board position of BL0939 pin n (1-8 down the left side, 9-16 up the right side)."""
    n = int(n)
    if n <= 8:
        return U2X - 2.475, U2Y - 4.445 + (n - 1) * 1.27
    return U2X + 2.475, U2Y - 4.445 + (16 - n) * 1.27


# ======================================================================== mains (top layer) ====
# L and N leave their terminal pins on the outer sides (4 mm apart), up and then 45 degrees to the fuses
FPY = at("F1")[1] + 4.6             # the fuses' input pins (their outputs are 4.6 mm above the centre)
J1L, J1N = (at("J1")[0] - 0.8, at("J1")[1]), (at("J1")[0] + 5.08 + 0.8, at("J1")[1])
t("L_IN", J1L, (J1L[0], FPY + (J1L[0] - at("F1")[0])), ("F1", "1"), w=1.0)
t("N_IN", J1N, (J1N[0], FPY + (at("F2")[0] - J1N[0])), ("F2", "1"), w=1.0)
# L_F: one straight run from inside the fuse's pin up into the supply's L pin, on the pins' left side (4 mm from its
# N pin); the MOV and T1's primary branch off it
LX = PX - 0.6
RVL = at("RV1")                     # the MOV's L pin
LFM = (LX, RVL[1] + (RVL[0] - LX))  # 45 degrees from here to the MOV's L pin
LFT = (LX, at("T1")[1] - 3.6)       # level with T1's primary pin
t("L_F", (LX, at("F1")[1] - 4.6), LFM, LFT, (LX, at("PS1")[1]), w=1.0)
t("L_F", LFM, ("RV1", "1"), w=1.0)
t("L_F", LFT, ("T1", "1"), w=1.0)
# N_F: 45 degrees from the fuse into the MOV's N pin, then the divider's end below it and the supply's N pin above
RVN = (RVL[0] + 7.5, RVL[1] + 2.9)                        # the MOV's N pin
t("N_F", ("F2", "2"), (at("F2")[0] - (FPY - 9.2 - RVN[1]), RVN[1]), w=1.0)
t("N_F", (at("R4")[0], RVN[1]), ("R4", "2"), w=0.6)
PSN = (at("PS1")[0] + 5.6, at("PS1")[1])   # inside the supply's N pin, on its right side
t("N_F", RVN, (RVN[0], PSN[1] + (RVN[0] - PSN[0])), PSN, w=1.0)
# ZP1 crosses L_F underneath, above the fuse's pin, and comes up 45 degrees to the divider's first resistor
ZPY = at("R1")[1] - 1.46 - 1.94     # R1's ZP1 pin less the via's 45-degree run
ZPV = (at("R1")[0] - 1.94, ZPY)
T1Z = (at("T1")[0] + 8.15, at("T1")[1] + 3.6)            # T1's primary return pin (ZP1)
b("ZP1", ("T1", "2"), (T1Z[0] + (T1Z[1] - ZPY), ZPY), ZPV, w=0.5, vias=[ZPV])
t("ZP1", ZPV, ("R1", "1"), w=0.5)
t("VD1", ("R1", "2"), ("R2", "1"), w=0.5)
t("VD2", ("R2", "2"), ("R3", "1"), w=0.5)
t("VD3", ("R3", "2"), ("R4", "1"), w=0.5)

# ======================================================================== CT inputs & BL0939 ===
# terminal -> burden; then each line leaves its burden through the gap beside it and runs up under T1's body
# (between its secondary pins and 6.5 mm from its primary) to its bead
for pin, rb, ct in (("1", "R8", "CT1P"), ("2", "R9", "CT1N"), ("3", "R10", "CT2P"), ("4", "R11", "CT2N")):
    t(ct, ("J4", pin), (rb, "1"), w=0.4)
BY = at("R8")[1]                    # burden row
FBY = at("FB1")[1]                  # bead row
t("CT1P", ("R8", "1"), (at("FB1")[0], BY + 1.46), ("FB1", "1"), w=0.25)
t("CT1N", ("R9", "1"), (8.9, BY + 1.46), (8.9, BY - 3.0), (7.2, BY - 4.7), (7.2, FBY + 2.4), ("FB2", "1"), w=0.25)
t("CT2P", ("R10", "1"), (12.35, BY + 1.46), (12.35, BY - 3.0), (9.0, BY - 6.35), (9.0, FBY + 2.4), ("FB3", "1"),
  w=0.25)
t("CT2N", ("R11", "1"), (13.15, BY + 1.46), (13.15, BY - 3.0), (10.8, BY - 5.35), (10.8, FBY + 2.4), ("FB4", "1"),
  w=0.25)
for r in ("R8", "R9", "R10", "R11"):
    t("GND", (r, "2"), (at(r)[0], BY - 2.8), w=0.4, vias=[(at(r)[0], BY - 2.8)])

# filtered lines: from each bead a staircase to the left edge, then up to its RC row (the first input outermost)
for fb, net, lane, level, rr in (("FB1", "CT1P_B", 0.7, FBY - 1.9, "R12"), ("FB2", "CT1N_B", 1.1, FBY - 2.5, "R13"),
                                 ("FB3", "CT2P_B", 1.5, FBY - 3.1, "R14"), ("FB4", "CT2N_B", 1.9, FBY - 3.7, "R15")):
    t(net, (fb, "2"), (at(fb)[0], level), (lane, level), (lane, at(rr)[1]), (rr, "1"))

# RC filters into the BL0939: from each capacitor a step to its own level, then across to its pin
# each line steps down (or up) on its own vertical level between the capacitors and the chip
for r, c, pin, net, lv in (("R12", "C1", "3", "IP1", 8.0), ("R13", "C2", "4", "IN1", 7.5),
                           ("R14", "C3", "5", "IP2", 7.0), ("R15", "C4", "6", "IN2", 7.5), ("R7", "C5", "7", "VP", 8.0)):
    t(net, (r, "2"), (c, "1"))
    cy = at(c)[1] + (0.775 if c in ("C1", "C3", "C5") else -0.775)
    t(net, (c, "1"), (lv, cy), (lv, u2pin(pin)[1]), ("U2", pin), radii=[None, 0.4, 0.4])
CX = at("C1")[0]
for y, cs in ((U2Y - 7.7, ("C1",)), (U2Y - 0.725, ("C2", "C3")), (U2Y + 6.175, ("C4", "C5"))):
    v("GND", (CX, y))
    for c in cs:
        t("GND", (c, "2"), (CX, y), w=0.3)
U8V = (u2pin(8)[0], u2pin(8)[1] + 1.3)
t("GND", ("U2", "8"), U8V, w=0.3, vias=[U8V])

# ZMPT107 secondary: its load R6 right at the pins; the signal hops under the filtered lines to R7
t("VS", ("T1", "3"), ("R6", "1"), w=0.3)
R6V = (1.6, at("R6")[1] - 0.8)
t("GND", ("R6", "2"), R6V, w=0.3, vias=[R6V])
VSV = (at("R7")[0] - 0.825, U2Y + 6.2)
b("VS", ("T1", "3"), VSV, w=0.3, vias=[VSV])
t("VS", VSV, ("R7", "1"), w=0.3)

# BL0939 control pins: out under the chip's body and down to the SEL pull-down and the three test pads
for i, (pin, net, target) in enumerate((("12", "SEL", ("R16", "1")), ("11", "CF", ("TP1", "1")),
                                        ("10", "I_LEAK", ("TP3", "1")), ("9", "ZX", ("TP2", "1")))):
    lx = U2X - 0.95 + 0.6 * i
    px, py = u2pin(pin)
    # SEL goes a little further down first, so its 45-degree run clears pin 8's ground via
    t(net, ("U2", pin), (lx, py), (lx, U2Y + (5.7 if net == "SEL" else 5.3)), target, radii=[None, 0.4],
      end=(-1, 0) if net == "SEL" else None)
R16V = (at("R16")[0] + 1.1, at("R16")[1] + 0.825)
t("GND", ("R16", "2"), R16V, vias=[R16V])

# BL0939 supply: 3V3 arrives from above (the Qwiic branch), decoupled by C6, and feeds R17 (TX pull-up)
U3N = (U2X - 2.475, U2Y - 8.5)
t("3V3", U3N, ("C6", "1"), ("U2", "1"), w=0.3)
t("3V3", U3N, ("R17", "1"), w=0.3)
C6V = (at("C6")[0] + 1.9, at("C6")[1])
t("GND", ("C6", "2"), C6V, w=0.3, vias=[C6V])

# ======================================================================== the left-side bus ===
# 3V3 (out of the LDO pour), SDA, SCL, UART RX, TX: west under the EN button, down beside the HLK-PM01, then along
# under it to the left column, where 3V3 and I2C turn up to the Qwiic port and the UART turns down to the BL0939.
# The lanes keep 0.65 mm apart; every corner they share is concentric
BP = 0.65
BUS_Y = 19.6                        # 3V3's run under the HLK-PM01; the others below it
DX0 = 35.8                          # 3V3's descent beside the HLK-PM01; the others east of it
RB0 = 1.0                           # inner radius at the corner into the run
QC = at("R30")[0] + 0.825            # 3V3's column up the left: straight into R30's 3V3 pin
t("3V3", (DX0, 9.2), (DX0, BUS_Y), (QC, BUS_Y), ("R30", "1"), w=0.4, radii=[None, RB0, 1.2])
for pin, net, k, target in (("4", "IO2", 1, "R30"), ("5", "IO3", 2, "R31")):
    x0, y0 = upin(pin)
    d, run, br = DX0 + BP * k, BUS_Y + BP * k, QC - BP * k
    tx = at(target)[0] + (-0.825 if target == "R30" else 0.825)
    t(net, ("U1", pin), (d, y0), (d, run), (br, run), (br, 16.4 + 0.3 * k), (tx, 13.2), (target, "2"),
      radii=[None, 1.0, RB0 + BP * k, 1.2 + BP * k])
# the Qwiic lines leave the pull-ups' row together at QY, run 45 degrees over to their pins and up into them
QY = 10.2
for net, r, pad, jp, w in (("IO2", "R30", -0.825, "3", 0.2), ("IO3", "R31", 0.825, "4", 0.2),
                           ("3V3", "R30", 0.825, "2", 0.3)):
    fx, px = at(r)[0] + pad, at("J7")[0] + {"2": 0.5, "3": -0.5, "4": -1.5}[jp]
    t(net, (r, "1" if net == "3V3" else "2"), (fx, QY), (px, QY - (fx - px)), ("J7", jp), w=w)
SOUTH_X = 17.4                      # TX's turn down to the BL0939; RX turns 0.65 mm further west
for pin, net, k, upad in (("6", "UART_RX", 3, "15"), ("7", "UART_TX", 4, "14")):
    x0, y0 = upin(pin)
    d, run = DX0 + BP * k, BUS_Y + BP * k
    south = SOUTH_X - BP * (4 - k)
    px, py = u2pin(upad)
    t(net, ("U1", pin), (d, y0), (d, run), (south, run), (south, py), ("U2", upad),
      radii=[None, 1.0, RB0 + BP * k, 1.0 + BP * (4 - k), 0.5])
t("UART_RX", ("R17", "2"), (SOUTH_X - BP, at("R17")[1]))

# 3V3 for the Qwiic pull-ups and the BL0939: from the Qwiic's 3V3 pin under its body to the left of it, down
# between its pins and the corner screw, then down the left column
L3X = at("R31")[0] - 1.6            # the left column, with a stub to R31's 3V3 pin
t("3V3", ("J7", "2"), (at("J7")[0] + 0.5, 3.5), (L3X + 0.8, 3.5), (L3X, 4.3), (L3X, at("R31")[1]),
  (L3X, U3N[1] - (U3N[0] - 1.0 - L3X)), (U3N[0] - 1.0, U3N[1]), U3N, w=0.3)
t("3V3", (L3X, at("R31")[1]), ("R31", "1"), w=0.3)
J7V = (at("J7")[0] + 1.5 + 1.6, 3.7)
t("GND", ("J7", "1"), J7V, w=0.3, vias=[J7V])

# ======================================================================== USB-C & power ======
UY5 = PLACE["J5"][1]
# D+ (A6, B6) joined underneath, D- (A7, B7) on top below the pads; 22 ohm in series; CC pull-downs
t("USB_CDP", ("J5", "B6"), (JX - 0.75, UY5 + 2.4), vias=[(JX - 0.75, UY5 + 2.4)])
t("USB_CDP", ("J5", "A6"), (JX + 0.25, UY5 + 2.4), vias=[(JX + 0.25, UY5 + 2.4)])
b("USB_CDP", (JX - 0.75, UY5 + 2.4), (JX + 0.25, UY5 + 2.4))
t("USB_CDP", ("J5", "B6"), (JX - 0.75, UY5 + 5.45), ("R28", "1"))
t("USB_CDN", ("J5", "A7"), (JX - 0.25, UY5 + 5.4), (JX + 0.75, UY5 + 5.4), ("J5", "B7"))
t("USB_CDN", (JX + 0.75, UY5 + 5.4), ("R29", "1"))
CCY, RRY = UY5 + 5.5, at("R20")[1] - 0.825        # the CC lines' level, the resistors' upper pads
t("CC1", ("J5", "A5"), (JX + 1.25, CCY), (at("R20")[0] - (RRY - CCY), CCY), ("R20", "1"))
t("CC2", ("J5", "B5"), (JX - 1.75, CCY), (at("R21")[0] + (RRY - CCY), CCY), ("R21", "1"))
t("GND", ("R21", "2"), (at("R21")[0], at("R21")[1] + 1.85), vias=[(at("R21")[0], at("R21")[1] + 1.85)])
R20V = (at("R20")[0] + 0.95, at("R20")[1] + 0.825)     # beside the pad: the label goes below
t("GND", ("R20", "2"), R20V, vias=[R20V])

# the USB pair: one hop on the bottom layer, from beside the module's pads 13 / 14 up to the 22 ohm resistors
DN_V, DP_V = (UX - 10.0, upin(13)[1]), (UX - 10.0, upin(14)[1])
DNR, DPR = (at("R29")[0], 11.6), (at("R28")[0], 11.6)
t("USB_DN", ("U1", "13"), DN_V, vias=[DN_V])
t("USB_DP", ("U1", "14"), DP_V, vias=[DP_V])
t("USB_DN", ("R29", "2"), DNR, vias=[DNR])
t("USB_DP", ("R28", "2"), DPR, vias=[DPR])
UXB, UYB = 38.95, 12.7              # the pair's turn north beside the HLK-PM01 and its run west, underneath
t("USB_DN", DN_V, (UXB, DN_V[1]), (UXB, UYB), (DNR[0], UYB), DNR, layer="B", radii=[None, 2.0, 2.55, 0.6])
t("USB_DP", DP_V, (UXB - 0.55, DP_V[1]), (UXB - 0.55, UYB + 0.55), (DPR[0], UYB + 0.55), DPR, layer="B",
  radii=[None, 2.55, 2.0, 0.6])

# VBUS: both pairs of pads joined underneath, over to D1 (5 V OR-ing) and its bleed resistor R27
t("VBUS", (JX - 2.20, UY5 + 3.8), (JX - 2.20, UY5 + 1.4), vias=[(JX - 2.20, UY5 + 1.4)])
t("VBUS", (JX + 2.20, UY5 + 3.8), (JX + 2.20, UY5 + 1.4), vias=[(JX + 2.20, UY5 + 1.4)])
b("VBUS", (JX - 2.20, UY5 + 1.4), (JX + 2.20, UY5 + 1.4), w=0.4)
VBV = (27.0, 9.6)
b("VBUS", (JX + 2.20, UY5 + 1.4), (26.0, UY5 + 1.4), (27.0, UY5 + 2.4), VBV, w=0.4, vias=[VBV])
t("VBUS", VBV, ("D1", "2"), ("R27", "1"), w=0.4)
R27V = (at("R27")[0] - 0.825 - 0.9, at("R27")[1] + 0.9)
t("GND", ("R27", "2"), R27V, w=0.3, vias=[R27V])

# +5V: LDO input with C12 / C8, D1's cathode, down to the HLK-PM01's +5V pin
U3J = (at("D1")[0] + 2.0, at("C12")[1] + 0.95)   # where the LDO's input meets C12 and the run down to D1
U3P = (at("U3")[0] - 2.3, 1.65)                  # the LDO's input pin
t("+5V", ("U3", "3"), (U3P[0], U3J[1] - (U3P[0] - U3J[0])), U3J, ("C12", "1"), w=0.5)
t("+5V", ("C12", "1"), ("C8", "1"), w=0.5)
t("+5V", U3J, ("D1", "1"), w=0.5)
t("+5V", ("D1", "1"), ("PS1", "4"), w=0.6, end=(0, 1))
for c in ("C12", "C8"):
    t("GND", (c, "2"), (at(c)[0], 0.95), w=0.3, vias=[(at(c)[0], 0.95)])
U3V = (at("U3")[0] + 3.8, 1.65)
t("GND", ("U3", "1"), U3V, w=0.4, vias=[U3V])

# 3V3 out of the LDO: the pour covers the tab and the decoupling capacitors; the module's 3V3 pin joins it
t("3V3", ("U1", "2"), (at("R18")[0], upin(2)[1]), (UX - 12.4, upin(2)[1]), w=0.5)   # over R18's 3V3 pad
for c in ("C10", "C11", "C7"):
    t("GND", (c, "2"), (at(c)[0], 4.3), w=0.3, vias=[(at(c)[0], 4.3)])

# EN: R18 pull-up at the pin, the button beside it, C9 under the button
# EN runs level from the module pin through R18 and a via into the button's upper pad; underneath, down to a via
# between the button's lower pad and C9
ENY = upin(3)[1]
ENA = (at("SW1")[0] + 2.95, ENY)
ENB = (at("C9")[0] + 0.775 + 0.95, at("C9")[1] - 0.95)
t("EN", ("U1", "3"), ("R18", "2"), ENA, (at("SW1")[0] + 1.875, ENY), vias=[ENA])
b("EN", ENA, (ENA[0], ENB[1] - (ENA[0] - ENB[0])), ENB, vias=[ENB])
t("EN", ENB, (ENB[0], at("SW1")[1] + 3.0))
t("EN", ENB, ("C9", "1"))
t("GND", ("C9", "2"), ("SW1", "2", 1), w=0.3)
SW1V = (at("SW1")[0] - 3.0, at("SW1")[1] - 3.0)   # the button's other ground pad, between the LDO pour and the bus
t("GND", ("SW1", "2", 0), SW1V, w=0.3, vias=[SW1V])
C9V = (at("C9")[0] - 0.775, at("C9")[1] + 1.3)
t("GND", ("C9", "2"), C9V, w=0.3, vias=[C9V])

# +5V to the bulk capacitor, the relays and the header: one hop underneath from the HLK-PM01's pin (the bus runs over
# it) to the bulk capacitor, down the strip to relay 1, across under the relays to relay 2
V5 = (at("C14")[0], at("C14")[1] + 5.2)
K1C = (at("K1")[0] - 3.8, at("K1")[1] - 7.62)   # relay 1's coil pin (+5V)
P4 = (at("PS1")[0] + 10.0, at("PS1")[1] - 29.08)  # the supply's +5V pin
t("+5V", ("PS1", "4"), (P4[0], V5[1] - (V5[0] - P4[0])), V5, w=0.6, layer="B", vias=[V5])
t("+5V", V5, ("C14", "1"), w=0.6)
t("+5V", V5, (V5[0], K1C[1] - (K1C[0] - V5[0])), ("K1", "1"), w=0.6)
t("+5V", ("D2", "1"), ("K1", "1"), w=0.5, start=(0, 1))
RB = at("K1")[1] - 5.3              # the run under the relays, between their coil pins and contact copper
t("+5V", ("K1", "1"), (at("K1")[0] - 3.8, RB), (at("K2")[0] - 3.8, RB), ("K2", "1"), w=0.6)
t("+5V", ("C13", "1"), ("K2", "1"), w=0.5, start=(0, 1))
t("+5V", ("D3", "1"), ("K2", "1"), w=0.5, start=(0, 1))
t("+5V", V5, (V5[0] + (hpin(2)[1] - V5[1]), hpin(2)[1]), w=0.5, layer="B")   # 45 degrees into header pin 2
t("GND", ("C14", "2"), (at("C14")[0], at("C14")[1] - 5.0), w=0.6,
  vias=[(at("C14")[0] - 0.6, at("C14")[1] - 5.0), (at("C14")[0] + 0.6, at("C14")[1] - 5.0)])
# 3V3 to the header and to GPIO27's pull-up R19: one trunk underneath from the bus
V3 = (30.0, BUS_Y)
t("3V3", V3, (V3[0], HY - (V5[0] - 1.2 - V3[0])), (V5[0] - 1.2, HY), hpin(1), w=0.4, layer="B", vias=[V3])
R19V = (at("R19")[0], at("R19")[1] + 1.9)
t("3V3", hpin(1), (hpin(1)[0] + 2.0, HY + 2.0), (R19V[0] - (R19V[1] - HY - 2.0), HY + 2.0), R19V, w=0.3,
  layer="B", vias=[R19V])
t("3V3", ("R19", "1"), R19V, w=0.3)
t("IO27", hpin(9), ("R19", "2"))

# ======================================================================== module, left side ===
# relay 1's drive (outermost) and four GPIOs drop beside the module; the GPIOs turn in together (concentric corners)
# under it to the header
LP = 0.5
K1L = UX - 12.6
t("RLY1_DRV", ("U1", "8"), (K1L, upin(8)[1]), (K1L, HY + 1.5), ("R23", "1"), radii=[None, 1.0, 1.5])
L1 = HY - 5.34                      # pin 12's level (innermost); the others 0.5 mm lower each
for i, (pin, hp, odd) in enumerate((("12", 8, False), ("11", 7, True), ("10", 6, False), ("9", 5, True))):
    lx = K1L + LP * (4 - i)
    level = L1 + LP * i
    px, py = upin(pin)
    hx, hy = hpin(hp)
    drop = hx - 1.27 if odd else hx
    net = f"IO{6 + int(pin) - 8}"
    pts = [("U1", pin), (lx, py), (lx, level), (drop, level)]
    if odd:
        t(net, *pts, (drop, hy - 1.27), ("J6", str(hp)), radii=[None, 1.0, 1.0 + LP * i, 0.6, 0.5])
    else:
        t(net, *pts, ("J6", str(hp)), radii=[None, 1.0, 1.0 + LP * i, 0.6])

# ======================================================================== module, right side ===
rx = upin(15)[0]
t("BOOT", ("U1", "15"), (rx + 1.0, upin(15)[1]), (rx + 1.0, 26.4), (at("SW2")[0] + 3.0, 26.4), ("SW2", "1", 1),
  radii=[None, 0.6, 1.0, 0.6])
t("BOOT", ("SW2", "1", 0), ("SW2", "1", 1))
t("LED", ("U1", "16"), (rx + 1.6, upin(16)[1]), (rx + 1.6, at("R22")[1]), ("R22", "1"), radii=[None, 0.6, 0.6])
t("LED_A", ("R22", "2"), ("D4", "2"))
D4V = (at("D4")[0] + 1.9, at("D4")[1])
t("GND", ("D4", "1"), D4V, vias=[D4V])
SWV = (at("SW2")[0] - 4.2, at("SW2")[1] + 1.875)
t("GND", ("SW2", "2", 0), SWV, vias=[SWV])
# eight GPIOs to the header: the lanes run down the right side, then turn in together (concentric corners) and step
# down to their pins
RP = 0.5
RIGHT = (("17", "IO4", 10), ("18", "IO27", 9), ("19", "IO15", 12), ("21", "IO23", 11), ("23", "IO24", 14),
         ("25", "IO11", 13), ("26", "IO25", 16), ("27", "IO26", 15))
R0 = HY - 9.24                      # IO4's level (innermost); the others 0.5 mm lower each
for i, (pin, net, hp) in enumerate(RIGHT):
    lx = rx + 2.6 + RP * i
    level = R0 + RP * i
    px, py = upin(pin)
    hx, hy = hpin(hp)
    odd = hp % 2 == 1
    drop = hx + 1.27 if odd else hx
    pts = [("U1", pin), (lx, py), (lx, level), (drop, level)]
    if odd:
        t(net, *pts, (drop, hy - 1.27), ("J6", str(hp)), radii=[None, 1.0, 1.0 + RP * i, 0.6, 0.5])
    else:
        t(net, *pts, ("J6", str(hp)), radii=[None, 1.0, 1.0 + RP * i, 0.6])
# relay 2's drive: a via beside pad 24, down the right edge underneath, around the screw, up beside its base resistor
K2V = (rx + 1.25, upin(24)[1])
K2V2 = (at("R24")[0] - 0.825, at("R24")[1] - 0.9)
HX4, HY4 = HOLES[3]
EX, SX = W - 1.0, HX4 - 2.6         # the run down the right edge, then past the screw's left side
t("RLY2_DRV", ("U1", "24"), K2V, vias=[K2V])
t("RLY2_DRV", K2V, (EX, upin(24)[1]), (EX, HY4 - 1.1 - (EX - SX)), (SX, HY4 - 1.1),
  (SX, K2V2[1] - (SX - K2V2[0])), K2V2, layer="B", vias=[K2V2], radii=[None, 2.0, 1.5, 1.5, 1.5])
t("RLY2_DRV", K2V2, ("R24", "1"))

# ======================================================================== module ground ========
v("GND", (UX - 0.35, UY + 1.15), (UX - 1.85, UY - 0.35), (UX + 1.15, UY - 0.35), (UX - 1.85, UY + 2.65),
  (UX + 1.15, UY + 2.65))

# ======================================================================== relay drivers ========
for k, (q, d, rb, rp, kr) in ((1, ("Q1", "D2", "R23", "R25", "K1")), (2, ("Q2", "D3", "R24", "R26", "K2"))):
    qx, qy = at(q)
    t(f"Q{k}_B", (rb, "2"), (at(rb)[0] + 1.5, HY + 2.76), (qx + 0.4, HY + 2.76), (q, "1"))
    t(f"Q{k}_B", (q, "1"), (rp, "1"))
    t(f"K{k}_COIL", (q, "3"), (kr, "2"), w=0.4)
    t(f"K{k}_COIL", (d, "2"), (qx, qy + 2.6), w=0.4)
    QV = (qx - 0.95, HY + 3.71)
    t("GND", (q, "2"), QV, w=0.3, vias=[QV])
    RV = (at(rp)[0], at(rp)[1] - 1.75)
    t("GND", (rp, "2"), RV, vias=[RV])
C13V = (at("C13")[0], at("C13")[1] - 1.95)
t("GND", ("C13", "2"), C13V, vias=[C13V])
