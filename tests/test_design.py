"""The circuit in hw/design.py: connectivity rules from the spec."""
from collections import Counter

from hw import design
from hw.parts import PARTS

ESP_GPIO = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}  # ESP32-C6-MINI-1
STRAPPING = {4, 5, 8, 9, 15}


def test_every_net_has_two_nodes():
    for net, nodes in design.NETS.items():
        assert len(nodes) >= 2, net


def test_no_pin_twice():
    seen = Counter((r, p) for nodes in design.NETS.values() for r, p in nodes)
    assert [k for k, n in seen.items() if n > 1] == []


def test_refs_unique_and_pins_exist():
    refs = [c.ref for c in design.COMPONENTS]
    assert len(refs) == len(set(refs))
    known = {c.ref for c in design.COMPONENTS}
    for nodes in design.NETS.values():
        for ref, _ in nodes:
            assert ref in known, ref


def test_header_has_all_unused_gpio():
    used = set(design.GPIO.values())
    want = {f"IO{n}" for n in ESP_GPIO - used} | {"3V3", "+5V", "GND"}
    assert want <= set(design.HEADER_PINS)
    assert set(design.HEADER_PINS) <= want


def test_header_pins_are_nets():
    hdr = design.comp("J6")
    for i, net in enumerate(design.HEADER_PINS, start=1):
        assert design.pin_net("J6", str(i)) == net
    assert hdr.dnp


def test_no_strapping_for_outputs():
    for name in ("RELAY1", "RELAY2", "LED"):
        assert design.GPIO[name] not in STRAPPING | {12, 13, 16, 17}


def test_fixed_gpio():
    g = design.GPIO
    assert (g["UART_TX"], g["UART_RX"], g["USB_DN"], g["USB_DP"], g["BOOT"]) == (16, 17, 12, 13, 9)


def test_both_inputs_fused():
    """Each input terminal pin reaches the rest of the circuit only through its fuse."""
    for pin, fuse in (("1", "F1"), ("2", "F2")):
        net = design.pin_net("J1", pin)
        refs = sorted(r for r, _ in design.NETS[net])
        assert refs == sorted(["J1", fuse]), (net, refs)
    for ref in ("F1", "F2"):
        x = PARTS[design.comp(ref).part].extra
        # 1 A slow fuse at 250 V AC as the HLK-PM01 sheet asks; the MOV can fail short across the
        # line, so the fuse must break a real mains fault current
        assert x["amps"] == 1 and x["volts_ac"] >= 250 and x["breaking_a"] >= 1000
    mov = {design.pin_net("RV1", "1"), design.pin_net("RV1", "2")}
    assert mov == {"L_F", "N_F"}


def test_per_board_counts_match_catalogue():
    counts = Counter(c.part for c in design.COMPONENTS if c.part)
    for key, p in PARTS.items():
        if p.footprint:
            assert counts[key] == p.per_board, (key, counts[key], p.per_board)
    assert counts["term508_hdr"] == PARTS["term508_plug"].per_board


def test_netclasses_cover_mains():
    nc = design.NETCLASS
    for net in ("L_IN", "L_F"):
        assert nc[net] == "MAINS_L"
    for net in ("N_IN", "N_F"):
        assert nc[net] == "MAINS_N"
    for k in (1, 2):
        assert nc[f"K{k}_COM"] == nc[f"K{k}_NO"] == f"RELAY{k}"
    assert nc["3V3"] == nc["+5V"] == nc["GND"] == "POWER"
    mains = {n for n, c in nc.items() if c.startswith(("MAINS", "RELAY"))}
    # every pin on a mains net belongs to a part that is either mains-only or isolating
    for net in mains:
        for ref, _ in design.NETS[net]:
            assert ref[:1] in "JFRTPK" or ref.startswith("RV"), (net, ref)


def test_bulk_capacitor():
    """Solid polymer bulk capacitor on +5V: the HLK-PM01 sheet asks for 100-220 uF, derated to 75 %."""
    bulk = [c for c in design.COMPONENTS if c.part and PARTS[c.part].extra.get("polymer")]
    assert len(bulk) == 1
    c, x = bulk[0], PARTS[bulk[0].part].extra
    assert set(c.pins.values()) == {"+5V", "GND"} and c.pins["1"] == "+5V"     # pin 1 is the positive one
    assert 100 <= x["uf"] <= 220 and x["volts"] * 0.75 >= 5.5


def test_vbus_bleed():
    """The Schottky leaks +5V back into VBUS: a resistor keeps an unplugged USB port's VBUS near 0 V."""
    bleeds = [c for c in design.COMPONENTS if c.ref.startswith("R") and set(c.pins.values()) == {"VBUS", "GND"}]
    assert len(bleeds) == 1 and PARTS[bleeds[0].part].value == "5.1k"


def test_usb_series_resistors():
    """Each USB data line reaches the module through one 22-33 ohm resistor (Espressif's guideline); no ESD chip."""
    for sock, chip in (("USB_CDP", "USB_DP"), ("USB_CDN", "USB_DN")):
        rs = [c for c in design.COMPONENTS if set(c.pins.values()) == {sock, chip}]
        assert len(rs) == 1 and PARTS[rs[0].part].value.startswith("22R")
        assert {r for r, _ in design.NETS[sock]} == {"J5", rs[0].ref}
        assert {r for r, _ in design.NETS[chip]} == {"U1", rs[0].ref}
    assert "esd" not in PARTS


def test_voltage_divider_power_and_signal():
    """At 264 V (240 V + 10 %) each divider resistor stays under half its power and voltage rating, and the
    signal on VP stays under the BL0939's 70 mV rms."""
    chain = [design.comp(r) for r in ("R1", "R2", "R3", "R4")]
    assert len({c.part for c in chain}) == 1
    part = PARTS[chain[0].part]
    ohms = float(part.value.split("k")[0]) * 1e3
    amps = 264 / (4 * ohms)
    assert amps * amps * ohms * 1e3 <= 0.5 * part.extra["mw"]
    assert amps * ohms <= 0.5 * part.extra["volts"]
    burden = float(PARTS[design.comp("R6").part].value.split("R")[0])
    assert 30 <= amps * burden * 1e3 <= 0.7 * 70          # mV rms on VP
    assert amps <= 2e-3                                    # ZMPT107-1: 2 mA rated
