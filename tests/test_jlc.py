"""JLC fabrication and assembly files in hw/out/jlc."""
import csv
import json
import re
import zipfile

import pytest
from conftest import HW

from hw import design
from hw.parts import PARTS

JLC = HW / "out" / "jlc"


def _rows(name):
    with open(JLC / name, newline="", encoding="utf8") as f:
        return list(csv.DictReader(f))


PLACED = [c for c in design.COMPONENTS if c.part and PARTS[c.part].footprint and not c.dnp]


def test_bom_designators_match_pcb():
    rows = _rows("bom.csv")
    got = sorted(d.strip() for r in rows for d in r["Designator"].split(","))
    assert got == sorted(c.ref for c in PLACED)
    for r in rows:
        assert re.fullmatch(r"C\d+", r["LCSC"]), r
        refs = [d.strip() for d in r["Designator"].split(",")]
        assert {design.comp(x).lcsc for x in refs} == {r["LCSC"]}


def test_cpl_has_every_placed_part():
    rows = _rows("cpl.csv")
    assert sorted(r["Designator"] for r in rows) == sorted(c.ref for c in PLACED)
    for r in rows:
        assert r["Layer"] == "Top"
        x, y = float(r["Mid X"].rstrip("mm")), float(r["Mid Y"].rstrip("mm"))
        assert 0 <= x <= 80 and 0 <= y <= 80, r          # origin at the board's lower-left corner


def test_rotation_table_covers_cpl_footprints():
    rows = {r["Designator"]: r for r in _rows("cpl.csv")}
    feats = json.loads((HW / "out" / "board_features.json").read_text())
    assert feats  # board generated
    for c in PLACED:
        rot = float(rows[c.ref]["Rotation"])
        assert 0 <= rot < 360
        assert isinstance(PARTS[c.part].rotation, int)


def test_gerber_zip_layers():
    with zipfile.ZipFile(JLC / "gerbers.zip") as z:
        names = " ".join(z.namelist()).lower()
    for part in ("f_cu", "b_cu", "f_mask", "b_mask", "f_silkscreen", "b_silkscreen", "f_paste", "edge_cuts"):
        assert part in names, part
    assert "pth" in names and "npth" in names


def test_cost_sheet_quantities():
    text = (JLC / "cost.md").read_text(encoding="utf8")
    for q in (10, 20, 30, 50, 100):
        assert re.search(rf"^\|\s*{q}\s*\|", text, re.M), q


def test_plugs_listed():
    rows = _rows("plugs.csv")
    lcsc = {r["LCSC"] for r in rows}
    assert lcsc == {PARTS["term508_plug"].lcsc, PARTS["term381_plug"].lcsc}


def test_cpl_positions_are_part_centres():
    """JLC places by the part centre: CPL Mid X/Y = centre of the footprint's pads (not its anchor,
    which is pin 1 on the through-hole parts)."""
    feats = json.loads((HW / "out" / "board_features.json").read_text())
    centres = feats["part_centres"]
    for r in _rows("cpl.csv"):
        x, y = float(r["Mid X"].rstrip("mm")), float(r["Mid Y"].rstrip("mm"))
        cx, cy = centres[r["Designator"]]
        assert abs(x - cx) < 0.01 and abs(y - cy) < 0.01, (r["Designator"], x, y, cx, cy)
