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
    """Each input terminal pin reaches the rest of the circuit only through its fusible resistor."""
    for pin, fuse in (("1", "F1"), ("2", "F2")):
        net = design.pin_net("J1", pin)
        refs = sorted(r for r, _ in design.NETS[net])
        assert refs == sorted(["J1", fuse]), (net, refs)
    assert design.comp("F1").part == "fuse_r" and design.comp("F2").part == "fuse_r"
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
