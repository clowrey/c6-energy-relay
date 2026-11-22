"""Part catalogue: one entry per distinct orderable part.

`rotation` is added to the KiCad footprint rotation in the JLC CPL (JLC's reel orientation differs
from KiCad's for some packages; values follow the kicad-jlcpcb-tools table, check them in JLC's
placement preview before paying). `per_board` is the count per board (test_design checks it
against design.COMPONENTS). Datasheet-backed ratings live in `extra`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Part:
    key: str
    lcsc: str
    symbol: str
    footprint: str          # "" = not placed on the board (loose plugs)
    value: str
    rotation: int = 0
    tht: bool = False
    per_board: int = 1
    mpn: str = ""
    extra: dict = field(default_factory=dict)


_R0603 = "Resistor_SMD:R_0603_1608Metric"
_C0603 = "Capacitor_SMD:C_0603_1608Metric"
_C0805 = "Capacitor_SMD:C_0805_2012Metric"

_LIST = [
    # --- active / special parts ---------------------------------------------------------------
    Part("esp", "C5736265", "RF_Module:ESP32-C6-MINI-1", "RF_Module:ESP32-C6-MINI-1",
         "ESP32-C6-MINI-1-N4", mpn="ESP32-C6-MINI-1-N4"),
    Part("bl0939", "C2836697", "c6er:BL0939", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", "BL0939",
         rotation=270, mpn="BL0939"),
    Part("psu", "C209903", "Converter_ACDC:HLK-PM01", "Converter_ACDC:Converter_ACDC_Hi-Link_HLK-PMxx",
         "HLK-PM01", tht=True, mpn="HLK-PM01",
         extra={"body_mm": (34.0, 20.0, 15.0), "out": "5V 600mA, 3kV isolation, potted"}),
    Part("zmpt", "C125191", "c6er:ZMPT107-1", "c6er:ZMPT107-1", "ZMPT107-1", tht=True, mpn="ZMPT107-1",
         extra={"body_mm": (19.0, 10.0, 18.2), "ratio": "2mA:2mA", "hipot_kv": 4}),
    Part("relay", "C2976831", "c6er:HF32FV-16", "c6er:HF32FV-16", "HF32FV-16/5-HLTF", tht=True,
         per_board=2, mpn="HF32FV-16/5-HLTF(590)",
         extra={"body_mm": (18.4, 10.2, 15.5), "coil_mw": 400, "contact_a": 16, "hipot_kv": 4}),
    Part("usbc", "C165948", "Connector:USB_C_Receptacle_USB2.0_16P",
         "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "USB-C", mpn="TYPE-C-31-M-12"),
    Part("esd", "C2687116", "Power_Protection:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "USBLC6-2SC6",
         rotation=180, mpn="USBLC6-2SC6"),
    Part("ldo", "C51118", "Regulator_Linear:AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5", "AP2112K-3.3",
         rotation=180, mpn="AP2112K-3.3TRG1",
         extra={"dropout_mv": 250, "dropout_at_ma": 600, "imax_ma": 600}),  # datasheet: 250 mV typ @ 600 mA
    Part("schottky", "C2480", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS14", mpn="SS14"),
    Part("npn", "C20526", "Transistor_BJT:MMBT3904", "Package_TO_SOT_SMD:SOT-23", "MMBT3904",
         rotation=180, per_board=2, mpn="MMBT3904"),
    Part("flyback", "C81598", "Device:D", "Diode_SMD:D_SOD-123", "1N4148W", per_board=2, mpn="1N4148W"),
    Part("mov", "C233178", "Device:Varistor", "Varistor:RV_Disc_D12mm_W6.1mm_P7.5mm", "10D561K", tht=True,
         mpn="10D561K"),  # up to 6.0 mm thick
    # ceramic-tube SMD fuse, 1 A slow (what the HLK-PM01 sheet asks for), breaks 1000 A at 250 V AC, UL
    # recognised. Same land pattern as Littelfuse 0443001.DR (C95352), which breaks only 50 A
    Part("fuse", "C48392807", "Device:Fuse", "c6er:Fuse_SMD_10.1x3.1", "1A 250V slow", per_board=2, mpn="40T 1A250V",
         extra={"amps": 1, "volts_ac": 250, "breaking_a": 1000, "body_mm": (10.5, 3.2, 3.2)}),
    Part("term508_hdr", "C395730", "Connector:Screw_Terminal_01x02", "c6er:DB2ER-5.08-02P", "DB2ER-5.08-2P",
         tht=True, per_board=3, mpn="DB2ER-5.08-2P-GN",
         extra={"rated_a": 15, "rated_v": 300, "pitch": 5.08}),  # UL 300 V 15 A (use group B)
    Part("term381_hdr", "C7245", "Connector:Screw_Terminal_01x04", "c6er:WJ15EDGRC-3.81-04P",
         "WJ15EDGRC-3.81-4P", tht=True, mpn="WJ15EDGRC-3.81-04P", extra={"rated_a": 8, "pitch": 3.81}),
    Part("button", "C318884", "Switch:SW_Push", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "TS-1187A",
         per_board=2, mpn="TS-1187A-B-A-B"),
    Part("led", "C2286", "Device:LED", "LED_SMD:LED_0603_1608Metric", "red", mpn="KT-0603R"),
    Part("ferrite", "C1002", "Device:FerriteBead_Small", "Inductor_SMD:L_0603_1608Metric", "600R@100MHz",
         per_board=4, mpn="GZ1608D601TF"),
    # --- resistors ----------------------------------------------------------------------------
    Part("r1k", "C21190", "Device:R", _R0603, "1k", per_board=5),
    Part("r470", "C23179", "Device:R", _R0603, "470R", per_board=3),
    Part("r10k", "C25804", "Device:R", _R0603, "10k", per_board=6),
    Part("r5k1", "C23186", "Device:R", _R0603, "5.1k", per_board=3),
    Part("r22", "C23345", "Device:R", _R0603, "22R 1%", per_board=1),
    Part("r27k", "C137340", "Device:R", "Resistor_SMD:R_1206_3216Metric", "27k 1206", per_board=4,
         mpn="RC1206FR-0727KL"),  # 200 V each; 4 x 27k = 108k feeds the ZMPT107 2.2 mA at 240 V
    Part("r0r3", "C59882", "Device:R", "Resistor_SMD:R_1206_3216Metric", "0.3R 1%", per_board=4),
    # --- capacitors ---------------------------------------------------------------------------
    Part("c33n", "C21117", "Device:C", _C0603, "33nF", per_board=5),
    Part("c100n", "C14663", "Device:C", _C0603, "100nF", per_board=3),
    Part("c1u", "C15849", "Device:C", _C0603, "1uF", per_board=1),
    Part("c10u", "C15850", "Device:C", _C0805, "10uF", per_board=2),
    Part("c22u", "C45783", "Device:C", _C0805, "22uF", per_board=2),
    # solid polymer, 21 mohm: the same maker and kind as the CellKeeper board's bulk capacitor
    Part("c220u", "C46550461", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_6.3x7.7", "220uF 16V polymer",
         rotation=180, mpn="MA16V220M6X8", extra={"polymer": True, "uf": 220, "volts": 16}),
    # --- loose (ordered with the boards, not placed) ------------------------------------------
    Part("term508_plug", "C395732", "", "", "DB2EK-5.08-2P plug", per_board=3, mpn="DB2EK-5.08-2P-GN-S",
         extra={"rated_a": 15}),
    Part("term381_plug", "C7244", "", "", "WJ15EDGK-3.81-4P plug", mpn="WJ15EDGK-3.81-04P"),
]

PARTS: dict[str, Part] = {p.key: p for p in _LIST}
