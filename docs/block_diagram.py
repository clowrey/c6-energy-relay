"""docs/img/block-diagram.svg: how the board's parts connect, and where the isolation barrier runs.

    python docs/block_diagram.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "img" / "block-diagram.svg"
W, H = 900, 500
BARRIER = 330
MAINS_BG, LV_BG = "#fdecea", "#e8f0fb"
MAINS_BOX, LV_BOX, BRIDGE_BOX = "#f6c9c4", "#c9dcf5", "#e9e1f7"
INK = "#1d2330"

parts = []


def box(x, y, w, h, lines, fill):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" stroke="{INK}" stroke-width="1.3"/>')
    y0 = y + h / 2 - (len(lines) - 1) * 8
    for i, line in enumerate(lines):
        weight = "600" if i == 0 else "400"
        parts.append(f'<text x="{x + w / 2}" y="{y0 + i * 16 + 4}" text-anchor="middle" font-weight="{weight}">{line}</text>')


def arrow(points, label="", at=None, both=False):
    pts = " ".join(f"{x},{y}" for x, y in points)
    start = ' marker-start="url(#a0)"' if both else ""
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{INK}" stroke-width="1.5" marker-end="url(#a1)"{start}/>')
    if label:
        lx, ly = at or ((points[0][0] + points[-1][0]) / 2, (points[0][1] + points[-1][1]) / 2 - 6)
        parts.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="12" fill="#4a5163">{label}</text>')


def main():
    # mains side / low-voltage side, barrier
    parts.append(f'<rect width="{BARRIER}" height="{H}" fill="{MAINS_BG}"/>')
    parts.append(f'<rect x="{BARRIER}" width="{W - BARRIER}" height="{H}" fill="{LV_BG}"/>')
    parts.append(f'<text x="14" y="22" font-weight="700" fill="#a3261b">MAINS</text>')
    parts.append(f'<text x="{W - 14}" y="22" text-anchor="end" font-weight="700" fill="#1f4e99">LOW VOLTAGE (isolated)</text>')
    parts.append(f'<line x1="{BARRIER}" y1="30" x2="{BARRIER}" y2="{H - 10}" stroke="#a3261b" stroke-width="2" stroke-dasharray="7 5"/>')
    parts.append(f'<text x="{BARRIER - 8}" y="{H - 16}" text-anchor="end" font-size="12" fill="#a3261b">'
                 '6.5 mm isolation barrier</text>')

    # power
    box(20, 40, 120, 60, ["J1", "L, N/L2", "100–240 V"], MAINS_BOX)
    box(160, 40, 100, 60, ["F1, F2, RV1", "fuses + MOV"], MAINS_BOX)
    box(275, 40, 110, 60, ["PS1 HLK-PM01", "isolated 5 V"], BRIDGE_BOX)
    box(440, 40, 120, 60, ["U3 AMS1117-3.3", "3.3 V LDO"], LV_BOX)
    box(760, 40, 120, 60, ["J5 USB-C", "bench power,", "flashing, logs"], LV_BOX)
    arrow([(140, 70), (160, 70)])
    arrow([(260, 70), (275, 70)])
    arrow([(385, 70), (440, 70)], "+5 V")
    arrow([(760, 70), (560, 70)], "VBUS via SS14 → +5 V")

    # voltage sense
    box(160, 170, 100, 60, ["R1–R4", "4 × 51 kΩ"], MAINS_BOX)
    box(275, 170, 110, 60, ["T1 ZMPT107-1", "2 mA : 2 mA CT"], BRIDGE_BOX)
    arrow([(210, 100), (210, 170)])
    arrow([(260, 200), (275, 200)])
    arrow([(385, 200), (420, 200)], "VP")

    # metering and MCU
    box(420, 160, 150, 120, ["U2 BL0939", "energy metering", "V, 2 × I, 2 × P,", "energy"], LV_BOX)
    box(620, 160, 260, 120, ["U1 ESP32-C5 (ESPC5-32-H4)", "2.4 + 5 GHz Wi-Fi 6, BLE, 802.15.4", "PCB antenna", "ESPHome / Home Assistant"], LV_BOX)
    arrow([(500, 100), (500, 160)], "3.3 V", at=(522, 136))
    arrow([(540, 100), (540, 125), (680, 125), (680, 160)])
    arrow([(820, 100), (820, 160)], "USB D+/D−", at=(852, 136))
    arrow([(570, 220), (620, 220)], "UART", both=True)
    box(440, 310, 130, 60, ["J4 CT1, CT2", "0.6 Ω burdens"], LV_BOX)
    arrow([(505, 310), (505, 280)], "IP/IN", at=(530, 300))
    box(770, 320, 110, 60, ["J7 Qwiic", "3.3 V I2C"], LV_BOX)
    arrow([(825, 280), (825, 320)], "GPIO0, 1", at=(855, 304), both=True)

    # relays
    box(20, 400, 120, 60, ["J2, J3", "COM / NO", "dry contacts"], MAINS_BOX)
    box(275, 400, 110, 60, ["K1, K2", "HF32FV-16", "16 A relays"], BRIDGE_BOX)
    box(440, 400, 130, 60, ["Q1, Q2 MMBT3904", "+ flyback diodes"], LV_BOX)
    arrow([(750, 280), (750, 430), (570, 430)], "GPIO23, GPIO24", at=(660, 422))
    arrow([(440, 430), (385, 430)], "coil")
    arrow([(275, 430), (140, 430)], "contacts")

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" font-size="13" fill="{INK}">\n'
           '<defs>'
           f'<marker id="a1" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
           f'<marker id="a0" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
           f'<path d="M10,0 L0,5 L10,10 z" fill="{INK}"/></marker>'
           '</defs>\n' + "\n".join(parts) + "\n</svg>\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
