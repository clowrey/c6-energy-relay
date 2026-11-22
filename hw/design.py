"""The circuit: every component and every connection. Single source of truth for the schematic
(gen_sch.py), the board (gen_pcb.py), the JLC files (export_jlc.py) and the firmware pin check.

Pin numbers are the KiCad symbol pin numbers (== footprint pad numbers).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from hw.parts import PARTS

NS = uuid.UUID("6c1d7a1e-2f0e-4c39-9a51-c6e0e4e1a7b2")
ROOT_UUID = str(uuid.uuid5(NS, "root-sheet"))


@dataclass
class Comp:
    ref: str
    part: str | None              # key into parts.PARTS; None for no-part items (header, test pads)
    pins: dict[str, str]          # pin number -> net
    value: str = ""
    symbol: str = ""              # override (parts without a catalogue entry)
    footprint: str = ""
    dnp: bool = False             # footprint only, nothing fitted (header holes, test pads)
    block: str = ""               # schematic grouping
    uuid: str = field(default="")

    def __post_init__(self):
        p = PARTS.get(self.part) if self.part else None
        if p:
            self.value = self.value or p.value
            self.symbol = self.symbol or p.symbol
            self.footprint = self.footprint or p.footprint
        self.uuid = str(uuid.uuid5(NS, self.ref))

    @property
    def lcsc(self) -> str:
        return PARTS[self.part].lcsc if self.part else ""


# ---- GPIO ------------------------------------------------------------------------------------
GPIO = {
    "USB_DN": 12, "USB_DP": 13,      # native USB Serial/JTAG
    "UART_TX": 16, "UART_RX": 17,    # to BL0939 RX / from BL0939 TX, 4800 baud
    "BOOT": 9,                       # BOOT button, usable as a button after boot
    "RELAY1": 22, "RELAY2": 23,      # relay drivers (not strapping pins)
    "LED": 2,                        # status LED
}
ESP_IO_PINS = {  # ESP32-C6-MINI-1 module pin -> GPIO (RXD0 = GPIO17, TXD0 = GPIO16)
    "5": 2, "6": 3, "9": 4, "10": 5, "12": 0, "13": 1, "15": 6, "16": 7, "17": 12, "18": 13, "19": 14,
    "20": 15, "22": 8, "23": 9, "24": 18, "25": 19, "26": 20, "27": 21, "28": 22, "29": 23, "30": 17, "31": 16,
}
ESP_GND_PINS = ["1", "2", "11", "14"] + [str(n) for n in range(36, 54)]

# 2 x 9 header (holes only): odd pins in one row, even in the other, ordered so the module's pins fan
# out to it without crossings. Strapping pins (IO4, IO5, IO8, IO15) are marked on the silkscreen.
HEADER_PINS = ["+5V", "3V3", "IO4", "IO3", "IO0", "IO5", "IO6", "IO1", "IO14", "IO7",
               "IO8", "IO15", "IO19", "IO18", "IO21", "IO20", "GND", "GND"]


def _gpio_net(n: int) -> str:
    named = {v: k for k, v in GPIO.items()}
    return {"USB_DN": "USB_DN", "USB_DP": "USB_DP", "UART_TX": "UART_TX", "UART_RX": "UART_RX",
            "BOOT": "BOOT", "RELAY1": "RLY1_DRV", "RELAY2": "RLY2_DRV", "LED": "LED"}.get(named.get(n), f"IO{n}")


def _esp_pins():
    pins = {"3": "3V3", "8": "EN"}
    for p in ESP_GND_PINS:
        pins[p] = "GND"
    for p, g in ESP_IO_PINS.items():
        pins[p] = _gpio_net(g)
    return pins


C = Comp
COMPONENTS: list[Comp] = [
    # ---- mains input, fuses, surge, isolated 5 V supply ----------------------------------------
    C("J1", "term508_hdr", {"1": "L_IN", "2": "N_IN"}, value="L  N/L2", block="mains"),
    C("F1", "fuse", {"1": "L_IN", "2": "L_F"}, block="mains"),
    C("F2", "fuse", {"1": "N_IN", "2": "N_F"}, block="mains"),
    C("RV1", "mov", {"1": "L_F", "2": "N_F"}, block="mains"),
    C("PS1", "psu", {"1": "L_F", "2": "N_F", "3": "GND", "4": "+5V"}, block="mains"),
    C("C12", "c22u", {"1": "+5V", "2": "GND"}, block="power"),
    C("C13", "c22u", {"1": "+5V", "2": "GND"}, block="power"),
    C("C14", "c220u", {"1": "+5V", "2": "GND"}, block="power"),     # HLK-PM01 sheet: 100-220 uF
    # ---- USB-C, ESD, 5 V OR-ing, 3.3 V LDO -----------------------------------------------------
    C("J5", "usbc", {"A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
                     "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
                     "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN"},
      block="usb"),
    C("R20", "r5k1", {"1": "CC1", "2": "GND"}, block="usb"),
    C("R21", "r5k1", {"1": "CC2", "2": "GND"}, block="usb"),
    C("U4", "esd", {"1": "USB_DN", "6": "USB_DN", "3": "USB_DP", "4": "USB_DP", "2": "GND", "5": "VBUS"},
      block="usb"),
    C("D1", "schottky", {"1": "+5V", "2": "VBUS"}, block="usb"),
    C("R27", "r5k1", {"1": "VBUS", "2": "GND"}, block="usb"),       # bleeds D1's reverse leakage
    C("U3", "ldo", {"1": "+5V", "3": "+5V", "2": "GND", "5": "3V3"}, block="power"),
    C("C8", "c100n", {"1": "+5V", "2": "GND"}, block="power"),
    C("C10", "c10u", {"1": "3V3", "2": "GND"}, block="power"),
    # ---- ESP32-C6 ------------------------------------------------------------------------------
    C("U1", "esp", _esp_pins(), block="mcu"),
    C("C7", "c100n", {"1": "3V3", "2": "GND"}, block="mcu"),
    C("C11", "c10u", {"1": "3V3", "2": "GND"}, block="mcu"),
    C("R18", "r10k", {"1": "3V3", "2": "EN"}, block="mcu"),
    C("C9", "c1u", {"1": "EN", "2": "GND"}, block="mcu"),
    C("SW1", "button", {"1": "EN", "2": "GND"}, value="EN", block="mcu"),
    C("SW2", "button", {"1": "BOOT", "2": "GND"}, value="BOOT", block="mcu"),
    C("R19", "r10k", {"1": "3V3", "2": "IO8"}, block="mcu"),  # GPIO8 high for serial download
    C("R22", "r470", {"1": "LED", "2": "LED_A"}, block="mcu"),
    C("D4", "led", {"1": "GND", "2": "LED_A"}, block="mcu"),
    C("J6", None, {str(i): n for i, n in enumerate(HEADER_PINS, start=1)}, value="GPIO",
      symbol="Connector_Generic:Conn_02x09_Odd_Even",
      footprint="Connector_PinHeader_2.54mm:PinHeader_2x09_P2.54mm_Vertical", dnp=True, block="mcu"),
    # ---- metering ------------------------------------------------------------------------------
    C("U2", "bl0939", {"1": "3V3", "8": "GND", "3": "IP1", "4": "IN1", "5": "IP2", "6": "IN2", "7": "VP",
                       "14": "UART_TX", "15": "UART_RX", "12": "SEL", "11": "CF", "9": "ZX", "10": "I_LEAK"},
      block="meter"),
    C("C6", "c100n", {"1": "3V3", "2": "GND"}, block="meter"),
    C("R16", "r10k", {"1": "SEL", "2": "GND"}, block="meter"),
    C("R17", "r10k", {"1": "3V3", "2": "UART_RX"}, block="meter"),  # BL0939 TX needs a pull-up
    C("TP1", None, {"1": "CF"}, value="CF", symbol="Connector:TestPoint",
      footprint="TestPoint:TestPoint_Pad_D1.0mm", dnp=True, block="meter"),
    C("TP2", None, {"1": "ZX"}, value="ZX", symbol="Connector:TestPoint",
      footprint="TestPoint:TestPoint_Pad_D1.0mm", dnp=True, block="meter"),
    C("TP3", None, {"1": "I_LEAK"}, value="I_LEAK", symbol="Connector:TestPoint",
      footprint="TestPoint:TestPoint_Pad_D1.0mm", dnp=True, block="meter"),
    # CT inputs: J4 = CT1+, CT1-, CT2+, CT2-; 0.6 ohm burden (2 x 0.3, centre GND) straight across the
    # terminal, then bead, 1k + 33n. The beads carry only the filter current: a failed bead can't open a CT
    C("J4", "term381_hdr", {"1": "CT1P", "2": "CT1N", "3": "CT2P", "4": "CT2N"}, value="CT1+ CT1- CT2+ CT2-",
      block="meter"),
]
for i, (ct, ip) in enumerate((("CT1P", "IP1"), ("CT1N", "IN1"), ("CT2P", "IP2"), ("CT2N", "IN2"))):
    COMPONENTS += [
        C(f"R{8 + i}", "r0r3", {"1": ct, "2": "GND"}, block="meter"),
        C(f"FB{i + 1}", "ferrite", {"1": ct, "2": f"{ct}_B"}, block="meter"),
        C(f"R{12 + i}", "r1k", {"1": f"{ct}_B", "2": ip}, block="meter"),
        C(f"C{1 + i}", "c33n", {"1": ip, "2": "GND"}, block="meter"),
    ]
COMPONENTS += [
    # voltage: ZMPT primary from L_F, then 4 x 27k back to N_F (chain on the N side keeps the layout
    # free of L/N crossings); 22R secondary load
    C("T1", "zmpt", {"1": "L_F", "2": "ZP1", "3": "VS", "4": "GND"}, block="vsense"),
    C("R1", "r27k", {"1": "ZP1", "2": "VD1"}, block="vsense"),
    C("R2", "r27k", {"1": "VD1", "2": "VD2"}, block="vsense"),
    C("R3", "r27k", {"1": "VD2", "2": "VD3"}, block="vsense"),
    C("R4", "r27k", {"1": "VD3", "2": "N_F"}, block="vsense"),
    C("R6", "r22", {"1": "VS", "2": "GND"}, block="vsense"),
    C("R7", "r1k", {"1": "VS", "2": "VP"}, block="vsense"),
    C("C5", "c33n", {"1": "VP", "2": "GND"}, block="vsense"),
]
for k, (q, d, rb, rp) in ((1, ("Q1", "D2", "R23", "R25")), (2, ("Q2", "D3", "R24", "R26"))):
    COMPONENTS += [
        C(f"K{k}", "relay", {"1": "+5V", "2": f"K{k}_COIL", "3": f"K{k}_COM", "4": f"K{k}_NO"}, block="relay"),
        C(q, "npn", {"1": f"Q{k}_B", "2": "GND", "3": f"K{k}_COIL"}, block="relay"),
        C(d, "flyback", {"1": "+5V", "2": f"K{k}_COIL"}, block="relay"),
        # 470R: ~5 mA base current, forced gain ~18 at the 93 mA worst-case coil current (MMBT3904
        # hFE is only 30 minimum at 100 mA), so the transistor saturates even from a weak GPIO high
        C(rb, "r470", {"1": f"RLY{k}_DRV", "2": f"Q{k}_B"}, block="relay"),
        C(rp, "r10k", {"1": f"Q{k}_B", "2": "GND"}, block="relay"),
        C(f"J{k + 1}", "term508_hdr", {"1": f"K{k}_COM", "2": f"K{k}_NO"}, value=f"RELAY{k} COM NO", block="relay"),
    ]

COMPONENTS.sort(key=lambda c: (c.ref.rstrip("0123456789"), int("".join(ch for ch in c.ref if ch.isdigit()))))

_BY_REF = {c.ref: c for c in COMPONENTS}


def comp(ref: str) -> Comp:
    return _BY_REF[ref]


def pin_net(ref: str, pin: str) -> str:
    return _BY_REF[ref].pins[pin]


NETS: dict[str, list[tuple[str, str]]] = {}
for _c in COMPONENTS:
    for _p, _n in _c.pins.items():
        NETS.setdefault(_n, []).append((_c.ref, _p))

NETCLASS: dict[str, str] = {}
for _n in NETS:
    if _n in ("L_IN", "L_F", "ZP1"):            # ZP1: after T1's low-impedance primary, so it sits at L
        NETCLASS[_n] = "MAINS_L"
    elif _n in ("N_IN", "N_F"):
        NETCLASS[_n] = "MAINS_N"
    elif _n in ("VD1", "VD2", "VD3"):
        NETCLASS[_n] = "MAINS_DIV"
    elif _n.startswith("K1_") and _n != "K1_COIL":
        NETCLASS[_n] = "RELAY1"
    elif _n.startswith("K2_") and _n != "K2_COIL":
        NETCLASS[_n] = "RELAY2"
    elif _n in ("+5V", "3V3", "GND", "VBUS"):
        NETCLASS[_n] = "POWER"
    else:
        NETCLASS[_n] = "LV"

MAINS_CLASSES = ("MAINS_L", "MAINS_N", "MAINS_DIV", "RELAY1", "RELAY2")
