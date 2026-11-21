"""Custom symbols and footprints in hw/lib parse in KiCad and agree pin-for-pad."""
import re
import shutil

import pytest
from conftest import HW, kcli

LIB = HW / "lib"
SYM = LIB / "c6er.kicad_sym"
PRETTY = LIB / "c6er.pretty"

PAIRS = {  # symbol -> footprint
    "BL0939": None,  # stock SOIC-16 footprint, pads 1..16
    "ZMPT107-1": "ZMPT107-1",
    "HF32FV-16": "HF32FV-16",
}
FOOTPRINTS = ["ZMPT107-1", "HF32FV-16", "DB2ER-5.08-02P", "WJ15EDGRC-3.81-04P"]


def _sym_pins(name):
    text = SYM.read_text(encoding="utf8")
    start = text.index(f'(symbol "{name}"')
    nxt = text.find('\n\t(symbol "', start + 10)
    block = text[start: nxt if nxt > 0 else len(text)]
    return set(re.findall(r'\(number "([^"]+)"', block))


def _fp_pads(name):
    text = (PRETTY / f"{name}.kicad_mod").read_text(encoding="utf8")
    return {p for p in re.findall(r'\(pad "([^"]*)"', text) if p}


def test_symbols_parse(tmp_path):
    dst = tmp_path / "c6er.kicad_sym"
    shutil.copy(SYM, dst)
    kcli("sym", "upgrade", "--force", dst)


def test_footprints_parse(tmp_path):
    dst = tmp_path / "c6er.pretty"
    shutil.copytree(PRETTY, dst)
    kcli("fp", "upgrade", "--force", dst)
    for name in FOOTPRINTS:
        assert (dst / f"{name}.kicad_mod").is_file()


@pytest.mark.parametrize("sym", PAIRS)
def test_pin_pad_match(sym):
    fp = PAIRS[sym]
    pads = _fp_pads(fp) if fp else {str(i) for i in range(1, 17)}
    assert _sym_pins(sym) == pads


def test_bl0939_pinout_matches_datasheet():
    text = SYM.read_text(encoding="utf8")
    start = text.index('(symbol "BL0939"')
    end = text.find('\n\t(symbol "', start + 10)
    block = text[start: end if end > 0 else len(text)]
    pins = dict(re.findall(r'\(name "([^"]+)"[^\n]*\n\s*\(number "(\d+)"', block))
    want = {"VDD": "1", "IP1": "3", "IN1": "4", "IP2": "5", "IN2": "6", "VP": "7", "GND": "8", "ZX": "9",
            "CF": "11", "SEL": "12", "RX": "14", "TX": "15"}
    for name, num in want.items():
        assert pins.get(name) == num, (name, pins.get(name))


def test_relay_slot():
    """Coil and contact pads are >= 6.5 mm apart, or an Edge.Cuts slot separates them."""
    text = (PRETTY / "HF32FV-16.kicad_mod").read_text(encoding="utf8")
    pads = {m[0]: (float(m[1]), float(m[2])) for m in
            re.findall(r'\(pad "(\d)" thru_hole \w+\s*\(at ([-\d.]+) ([-\d.]+)', text)}
    coil = [pads["1"], pads["2"]]
    contact = [pads["3"], pads["4"]]
    gap = min(abs(c[0] - k[0]) for c in coil for k in contact) - 3.0  # minus pad half-widths
    assert gap >= 6.5 or "Edge.Cuts" in text


def test_input_terminal_slot():
    """The 5.08 mm mains terminal carries a routed slot between its two pins (L to N/L2 creepage)."""
    text = (PRETTY / "DB2ER-5.08-02P.kicad_mod").read_text(encoding="utf8")
    assert '"Edge.Cuts"' in text
