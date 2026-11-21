"""Hand-routed tracks for the C6 energy relay board.

net -> list of paths {"layer": "F"|"B", "w": mm, "pts": [...], "vias": [...]}. Points are board
coordinates (mm, origin top-left, y down, as gen_pcb.PLACE) or pad references ("U1", "17").
Routing style follows the CellKeeper boards: 45-degree corners, 0.2 mm signals, 0.3-0.6 mm power,
0.6/0.3 mm vias, ground poured on both layers. Mains nets stay on the top layer, 1.0 mm (L/N) and
0.5 mm (divider); relay contacts are copper zones (gen_pcb.RELAY_ZONES).
"""
from __future__ import annotations

ROUTES: dict = {}


def t(net, *pts, w=0.2, layer="F", vias=()):
    ROUTES.setdefault(net, []).append({"layer": layer, "w": w, "pts": list(pts), "vias": list(vias)})


def b(net, *pts, w=0.2, vias=()):
    t(net, *pts, w=w, layer="B", vias=vias)


def v(net, *pts):
    ROUTES.setdefault(net, []).append({"layer": "F", "w": 0.2, "pts": [], "vias": list(pts)})


# ======================================================================== mains (top layer) ====
t("L_IN", (29.2, 70.0), (25.5, 70.0), ("F1", "1"), w=1.0)  # starts inside the pad, 4 mm from N
t("N_IN", (35.9, 70.0), (39.5, 70.0), ("F2", "1"), w=1.0)
t("L_F", ("F1", "2"), ("T1", "1"), w=1.0)
t("L_F", ("F1", "2"), (24.2, 56.0), ("RV1", "1"), w=1.0)
t("L_F", ("F1", "2"), (28.8, 49.0), (29.5, 49.3), w=1.0)  # ends inside the HLK pad
t("N_F", ("F2", "2"), (36.2, 49.0), (35.5, 49.3), w=1.0)
t("N_F", ("F2", "2"), (39.17, 57.63), ("RV1", "2"), w=1.0)
t("N_F", (39.17, 57.63), ("R5", "2"), w=0.6)
t("ZP1", ("T1", "2"), (22.59, 61.54), ("R1", "1"), w=0.5)
t("VD1", ("R1", "2"), ("R2", "1"), w=0.5)
t("VD2", ("R2", "2"), ("R3", "1"), w=0.5)
t("VD3", ("R3", "2"), ("R4", "1"), w=0.5)
t("VD4", ("R4", "2"), ("R5", "1"), w=0.5)

# ======================================================================== CT inputs ============
# terminal -> bead -> burden node; a via beside each node drops the signal to the bottom layer
CT_X = {"CT1P": 3.2, "CT1N": 7.01, "CT2P": 10.82, "CT2N": 14.63}
for i, (ct, x) in enumerate(CT_X.items()):
    fb, rb = f"FB{i + 1}", f"R{8 + i}"
    t(ct, ("J4", str(i + 1)), (fb, "1"), w=0.4)
    t(f"{ct}_B", (fb, "2"), (rb, "1"), w=0.3)
    t(f"{ct}_B", (x, 68.95), (x - 1.5, 68.95), w=0.3, vias=[(x - 1.5, 68.95)])

# bottom-layer bundle from the burden nodes up to the RC filters (stays >= 6.5 mm from T1's primary)
#   via at the filter (under the resistor's left pad) -> down -> 45-degree into a 0.8 mm-pitch bundle
#   -> down beside T1's secondary -> fan out to the node vias above the terminal
BUNDLE = [  # net, filter via, bend-start y, bundle x, fan bend y, node via
    ("CT1P_B", (1.19, 32.35), 46.7, 7.0, 60.5, (1.7, 68.95)),
    ("CT1N_B", (1.89, 35.55), 46.2, 7.8, 61.5, (5.51, 68.95)),
    ("CT2P_B", (2.59, 38.75), 45.7, 8.6, 62.0, (9.32, 68.95)),
    ("CT2N_B", (3.30, 41.95), 45.2, 9.4, 62.0, (13.13, 68.95)),
]
for net, (fx, fy), y_bend, bx, y_fan, (nx, ny) in BUNDLE:
    d1 = bx - fx                       # 45-degree run into the bundle
    d2 = abs(nx - bx)                  # 45-degree run out to the node via
    b(net, (fx, fy), (fx, y_bend), (bx, y_bend + d1), (bx, y_fan), (nx, y_fan + d2), (nx, ny),
      w=0.25, vias=[(fx, fy)])
for r, net in (("R12", "CT1P_B"), ("R13", "CT1N_B"), ("R14", "CT2P_B"), ("R15", "CT2N_B")):
    x, y = {"R12": (1.19, 31.10), "R13": (1.89, 34.30), "R14": (2.59, 37.50), "R15": (3.30, 40.70)}[r]
    t(net, (r, "1"), (x, y + 1.25))

# RC filter rows -> BL0939 pins (rows 3.2 mm apart, jogs staggered so nothing crosses)
t("IP1", ("R12", "2"), ("C1", "1"), ("U2", "3"))
t("IN1", ("R13", "2"), ("C2", "1"), (8.2, 34.30), (8.2, 32.36), ("U2", "4"))
t("IP2", ("R14", "2"), ("C3", "1"), (8.8, 37.50), (8.8, 33.64), ("U2", "5"))
t("IN2", ("R15", "2"), ("C4", "1"), (9.4, 40.70), (9.4, 34.91), ("U2", "6"))
t("VP", ("R7", "2"), ("C5", "1"), (10.0, 43.90), (10.0, 36.17), ("U2", "7"))
t("VS", ("R7", "1"), (2.58, 46.2), ("R6", "1"), (2.35, 48.83), ("T1", "3"), w=0.3)
for c, y in (("C1", 32.65), ("C2", 35.85), ("C3", 39.05), ("C4", 42.25), ("C5", 45.45)):
    t("GND", (c, "2"), (5.3, y), vias=[(5.3, y)])
t("GND", ("R6", "2"), (6.9, 47.4), (7.6, 46.7), w=0.3, vias=[(7.6, 46.7)])
t("GND", ("U2", "8"), (11.53, 38.75), w=0.3, vias=[(11.53, 38.75)])

# BL0939 supply, control, test pads, UART
t("3V3", (23.0, 24.6), (19.2, 24.6), ("R17", "1"), w=0.3)
t("3V3", (19.2, 24.6), (10.22, 24.6), ("C6", "1"), (10.22, 27.9), ("U2", "1"), w=0.3)
t("GND", ("C6", "2"), (12.9, 26.0), w=0.3, vias=[(12.9, 26.0)])
t("SEL", ("U2", "12"), ("R16", "1"))
t("GND", ("R16", "2"), (20.3, 32.2), vias=[(20.3, 32.2)])
t("ZX", ("U2", "9"), (18.2, 37.44), (18.2, 38.6), (17.2, 39.6), ("TP2", "1"))
t("I_LEAK", ("U2", "10"), (18.8, 36.17), (18.8, 40.0), (17.4, 41.4), ("TP3", "1"))
t("CF", ("U2", "11"), (19.4, 34.91), (19.4, 40.1), (16.6, 42.9), ("TP1", "1"))
t("UART_RX", ("U2", "15"), (18.2, 29.83), (19.2, 28.83), ("R17", "2"))
t("UART_RX", (19.2, 28.83), (20.5, 28.83), vias=[(20.5, 28.83)])
t("UART_TX", ("U2", "14"), (18.2, 31.09), (18.9, 30.4), (20.5, 30.4), vias=[(20.5, 30.4)])
# UART on the bottom: module pins -> west under everything -> down to the BL0939 vias
b("UART_RX", (68.8, 19.3), (65.5, 22.6), (21.6, 22.6), (20.5, 23.7), (20.5, 28.83), vias=[(68.8, 19.3)])
b("UART_TX", (69.6, 20.1), (66.5, 23.2), (22.4, 23.2), (21.3, 24.3), (21.3, 29.6), (20.5, 30.4),
  vias=[(69.6, 20.1)])
t("UART_RX", ("U1", "30"), (68.8, 19.3))
t("UART_TX", ("U1", "31"), (69.6, 20.1))

# ======================================================================== USB ==================
# DP: B6 and A6 joined on the bottom above the pads; A6 runs under the ESD chip (between its pad
# rows) to pins 3 and 4. DN: A7 -> pin 1, B7 -> via that also takes pin 6; pin 1 joins on the bottom.
t("USB_DP", ("J5", "B6"), (10.25, 6.6), vias=[(10.25, 6.6)])
t("USB_DP", ("J5", "A6"), (11.25, 6.6), vias=[(11.25, 6.6)])
b("USB_DP", (10.25, 6.6), (11.25, 6.6))
t("USB_DP", ("J5", "A6"), (11.25, 9.6), (11.0, 9.85), (11.0, 12.75), ("U4", "4"))
t("USB_DP", (11.0, 12.75), ("U4", "3"))
t("USB_DN", ("J5", "A7"), (10.75, 9.2), (10.0, 9.95), (10.0, 10.55), ("U4", "1"))
t("USB_DN", ("J5", "B7"), (11.75, 9.25), (12.1, 9.6), vias=[(12.1, 9.6)])
t("USB_DN", ("U4", "6"), (12.14, 10.3), (12.1, 9.6))
t("USB_DN", ("U4", "1"), (8.6, 10.85), vias=[(8.6, 10.85)])
b("USB_DN", (8.6, 10.85), (10.85, 10.85), (12.1, 9.6))
# to the ESP32 (DP above DN on the bottom, both arrive at vias beside module pins 17/18)
t("USB_DP", ("U4", "4"), (13.4, 12.75), vias=[(13.4, 12.75)])
b("USB_DP", (13.4, 12.75), (15.25, 14.6), (60.0, 14.6), (62.3, 12.3), (62.3, 12.0), vias=[(62.3, 12.0)])
b("USB_DN", (10.85, 10.85), (11.0, 11.0), (11.0, 14.2), (12.0, 15.2), (60.8, 15.2), (62.9, 13.1), (62.9, 11.2),
  vias=[(62.9, 11.2)])
t("USB_DP", ("U1", "18"), (62.3, 12.0))
t("USB_DN", ("U1", "17"), (62.9, 11.2))
# CC pull-downs
t("CC1", ("J5", "A5"), (12.25, 4.6), vias=[(12.25, 4.6)])
b("CC1", (12.25, 4.6), (5.3, 4.6), vias=[(5.3, 4.6)])
t("CC1", (5.3, 4.6), (5.3, 5.13), ("R20", "1"))
t("GND", ("R20", "2"), (2.78, 7.3), vias=[(2.78, 7.3)])
t("CC2", ("J5", "B5"), (9.25, 9.6), (6.1, 9.6), (5.6, 10.1), ("R21", "1"))
t("GND", ("R21", "2"), (5.6, 13.4), vias=[(5.6, 13.4)])
# VBUS: both pad pairs joined on the bottom above the pads; on to the ESD and the Schottky
t("VBUS", (8.8, 8.0), (8.8, 5.6), vias=[(8.8, 5.6)])  # right edge of the pad, clear of the NPTH peg
t("VBUS", (13.2, 8.0), (13.2, 5.6), vias=[(13.2, 5.6)])
b("VBUS", (8.8, 5.6), (13.2, 5.6), (16.8, 5.6), (16.8, 9.0), w=0.4, vias=[(16.8, 9.0)])
t("VBUS", (16.8, 9.0), (17.4, 10.6), ("D1", "2"), w=0.4)
t("VBUS", ("J5", "A4"), (13.45, 11.8), ("U4", "5"), w=0.3)
# connector ground pads
t("GND", ("U4", "2"), (9.0, 11.8))

# ======================================================================== power ================
# +5V: USB Schottky -> bottom -> LDO/C12; HLK output -> trunk down the HLK's right edge -> relays
t("+5V", ("D1", "1"), (21.8, 13.6), w=0.5, vias=[(21.8, 13.6)])
b("+5V", (21.8, 13.6), (43.4, 13.6), w=0.6, vias=[(43.4, 13.6)])
t("+5V", (43.4, 13.6), ("C12", "1"), w=0.5)
t("+5V", (43.4, 13.6), (42.2, 12.4), (41.85, 12.05), (41.85, 8.75), ("U3", "3"), w=0.25)
t("+5V", (41.85, 8.75), (41.85, 6.85), ("U3", "1"), w=0.25)
t("+5V", (41.85, 12.05), ("C8", "1"), w=0.25)
t("+5V", ("PS1", "4"), (40.0, 18.0), (43.4, 14.6), (43.4, 13.6), w=0.6)
t("+5V", ("PS1", "4"), (43.0, 22.9), (43.0, 44.8), w=0.6, vias=[(43.0, 44.8)])
t("+5V", (43.0, 33.54), ("J6", "1"), w=0.4)
b("+5V", (43.0, 44.8), (68.85, 44.8), w=0.6)
b("+5V", (50.74, 44.8), ("K1", "1"), w=0.6)
b("+5V", (66.74, 44.8), ("K2", "1"), w=0.6)
t("+5V", (52.85, 44.8), ("D2", "1"), w=0.5, vias=[(52.85, 44.8)])
t("+5V", (68.85, 44.8), ("D3", "1"), w=0.5, vias=[(68.85, 44.8)])
t("+5V", (61.6, 44.8), ("C13", "1"), w=0.5, vias=[(61.6, 44.8)])
t("GND", ("C13", "2"), (62.7, 48.3), vias=[(62.7, 48.3)])
t("GND", ("C12", "2"), (45.6, 11.0), w=0.3, vias=[(45.6, 11.0)])
t("GND", ("C8", "2"), (40.0, 9.55), w=0.3, vias=[(40.0, 9.55)])
t("GND", ("U3", "2"), (43.9, 7.8), w=0.3, vias=[(43.9, 7.8)])

# 3V3: LDO -> along the top edge -> module; west to the BL0939; down to the header
t("3V3", ("U3", "5"), (45.14, 4.5), ("C10", "1"), (45.45, 0.95), w=0.4)
t("3V3", ("U1", "3"), (71.2, 4.4), ("C7", "1"), w=0.4)
t("3V3", ("C7", "1"), (71.6, 3.0), ("C11", "1"), (70.8, 0.95), (45.45, 0.95), w=0.4)
t("3V3", (45.45, 0.95), (24.3, 0.95), (24.3, 16.5), (23.0, 17.8), (23.0, 24.6), w=0.4)
t("3V3", ("U3", "5"), (46.3, 6.85), (46.3, 29.7), ("J6", "2"), w=0.3)
t("3V3", ("R18", "1"), (42.5, 0.95), w=0.3)
t("GND", ("C10", "2"), (48.3, 3.6), w=0.3, vias=[(48.3, 3.6)])
t("GND", ("C7", "2"), (73.4, 2.55), ("C11", "2"), w=0.3)
t("GND", (73.4, 2.55), (74.0, 2.55), w=0.3, vias=[(74.0, 2.55)])
t("GND", ("U1", "1"), (72.8, 5.0), ("C7", "2"), w=0.3)
t("GND", ("U1", "2"), (72.0, 5.4), (72.8, 5.4))
# IO8 pull-up: 3V3 from the header pin on the bottom
t("3V3", ("R19", "1"), (60.8, 36.2), vias=[(60.8, 36.2)])
b("3V3", (60.8, 36.2), (43.6, 36.2), (43.6, 31.6), (44.2, 31.0), ("J6", "2"), w=0.3)
t("IO8", ("J6", "11"), (57.7, 35.0), (58.18, 35.48), ("R19", "2"))

# ======================================================================== ESP32-C6 module ======
# top side: 3V3 (above), LED, EN and IO3 to vias, IO4/IO5 west then down
t("LED", ("U1", "5"), (69.6, 4.6), (68.1, 3.1), ("R22", "1"))
t("LED_A", ("R22", "2"), ("D4", "2"))
t("GND", ("D4", "1"), (61.6, 2.3), vias=[(61.6, 2.3)])
t("EN", ("U1", "8"), (67.2, 4.7), vias=[(67.2, 4.7)])
b("EN", (67.2, 4.7), (43.3, 4.7), vias=[(43.3, 4.7)])
t("EN", (43.3, 4.7), (40.9, 4.7), ("SW1", "1", 1))
t("EN", (42.5, 4.7), ("R18", "2"))
t("EN", ("SW1", "1", 0), ("SW1", "1", 1))
t("EN", (36.22, 4.12), ("C9", "1"))
t("GND", ("C9", "2"), (38.7, 2.2), vias=[(38.7, 2.2)])
t("IO3", ("U1", "6"), (68.8, 4.7), vias=[(68.8, 4.7)])
b("IO3", (68.8, 4.7), (70.6, 6.5), (70.6, 24.0), (48.0, 24.0), (47.54, 24.46), ("J6", "4"))

# header fan-out: lanes leave the module, step down a staircase (leftmost lane turns highest),
# run west and drop onto the header; "odd" targets pass between the even-row pads
LANES = [  # net, start (pad), lane x, turn y, target x, header pad
    ("IO4", ("U1", "9"), 57.0, 20.8, 48.81, "3"),
    ("IO5", ("U1", "10"), 57.6, 21.4, 50.08, "6"),
    ("IO0", ("U1", "12"), 58.2, 22.0, 51.35, "5"),
    ("IO1", ("U1", "13"), 58.8, 22.6, 52.62, "8"),
    ("IO6", ("U1", "15"), 59.4, 23.2, 53.89, "7"),
    ("IO7", ("U1", "16"), 60.0, 23.8, 55.16, "10"),
    ("IO14", ("U1", "19"), 60.6, 24.4, 56.43, "9"),
    ("IO15", ("U1", "20"), 61.2, 25.0, 57.70, "12"),
    ("IO8", ("U1", "22"), 61.8, 25.6, 58.97, "11"),
    ("IO18", ("U1", "24"), 63.0, 26.2, 60.24, "14"),
    ("IO19", ("U1", "25"), 64.8, 26.8, 61.51, "13"),
    ("IO20", ("U1", "26"), 65.6, 27.4, 62.78, "16"),
    ("IO21", ("U1", "27"), 66.4, 28.0, 64.05, "15"),
]
TOP_EXIT = {"IO4": 4.4, "IO5": 5.0}                  # top-side pins: up, then west at this y
for net, pad, lx, ty, tx, hp in LANES:
    pts = [pad]
    if net in TOP_EXIT:
        px = {"IO4": 66.4, "IO5": 65.6}[net]
        pts += [(px, TOP_EXIT[net]), (lx, TOP_EXIT[net])]
    elif pad[1] in {str(n) for n in range(12, 25)}:       # left side: west to the lane
        py = 7.2 + 0.8 * (int(pad[1]) - 12)
        pts += [(lx, py)]
    pts += [(lx, ty), (tx, ty)]
    odd = int(hp) % 2 == 1
    if odd:
        pts += [(tx, 33.54), ("J6", hp)]
    else:
        pts += [("J6", hp)]
    t(net, *pts)

# relay drives run under the header to the drivers
t("RLY1_DRV", ("U1", "28"), (67.2, 37.6), (50.4, 37.6), (49.57, 38.43), ("R23", "1"))
t("RLY2_DRV", ("U1", "29"), (68.0, 39.5), (65.57, 39.5), ("R24", "1"))
# BOOT to its button through the bottom
t("BOOT", ("U1", "23"), (62.9, 16.0), vias=[(62.9, 16.0)])
b("BOOT", (62.9, 16.0), (54.6, 16.0), vias=[(54.6, 16.0)])
t("BOOT", (54.6, 16.0), ("SW2", "1", 1))
t("BOOT", ("SW2", "1", 0), ("SW2", "1", 1))
t("GND", ("U1", "14"), (62.9, 8.8), vias=[(62.9, 8.8)])

# ======================================================================== relay drivers ========
for k, (q, d, rb, rp, kr, x0) in ((1, ("Q1", "D2", "R23", "R25", "K1", 49.57)),
                                  (2, ("Q2", "D3", "R24", "R26", "K2", 65.57))):
    xb = x0 + 1.65                                     # R23/R24 pad 2 x
    t(f"Q{k}_B", (rb, "2"), (q, "1"))
    t(f"Q{k}_B", (rp, "1"), (x0 + 0.58, 42.12), (xb - 0.42, 41.47), (xb, 41.05), (rb, "2"))
    t(f"K{k}_COIL", (q, "3"), (x0 + 6.58, 42.2), (d, "2"), (x0 + 8.77, 47.99), (kr, "2"), w=0.4)
    t("GND", (rp, "2"), (x0 + 2.83, 43.6), vias=[(x0 + 2.83, 43.6)])
    t("GND", (q, "2"), (x0 + 2.83, 43.6), w=0.3)

# ground island between the IO18 / IO19 lanes under the module's corner pad
v("GND", (63.9, 21.0))
