"""The board: KiCad DRC (with schematic parity and the project's creepage rules), plus layout rules
from the spec that DRC can't express."""
import json
import re

import pytest
from conftest import HW, kcli, kpy

PCB = HW / "c6-energy-relay.kicad_pcb"
FEATURES = HW / "out" / "board_features.json"
SPACING_TYPES = {"clearance", "creepage", "hole_clearance", "copper_edge_clearance"}


@pytest.fixture(scope="module")
def drc(tmp_path_factory):
    out = tmp_path_factory.mktemp("drc") / "drc.json"
    kcli("pcb", "drc", "--schematic-parity", "--format", "json", "--units", "mm", "-o", out, PCB, check=False)
    return json.loads(out.read_text(encoding="utf8"))


@pytest.fixture(scope="module")
def features():
    return json.loads(FEATURES.read_text(encoding="utf8"))


@pytest.fixture(scope="module")
def board_dump(tmp_path_factory):
    out = tmp_path_factory.mktemp("dump") / "dump.json"
    kpy(HW / "tools" / "dump_board.py", PCB, out)
    return json.loads(out.read_text(encoding="utf8"))


def _fmt(items):
    return "\n".join(f"{v['type']}: {v['description']} :: " +
                     "; ".join(i.get("description", "") for i in v.get("items", [])) for v in items[:15])


def test_parity(drc):
    assert drc.get("schematic_parity", []) == [], _fmt(drc["schematic_parity"])


def test_no_clearance_or_creepage_errors(drc):
    bad = [v for v in drc["violations"] if v["type"] in SPACING_TYPES]
    assert bad == [], _fmt(bad)


def test_no_courtyard_or_hole_errors(drc):
    bad = [v for v in drc["violations"] if v["severity"] == "error" and v["type"] in
           {"courtyards_overlap", "hole_to_hole", "drill_out_of_range", "invalid_outline", "malformed_courtyard",
            "items_not_allowed", "text_height", "silk_overlap", "starved_thermal"}]
    assert bad == [], _fmt(bad)


def test_antenna_keepout_clear(board_dump, features):
    x0, y0, x1, y1 = features["antenna_keepout"]
    for item in board_dump["copper"]:
        if item["ref"] == "U1":
            continue
        if item["kind"] == "zone":
            inside = [p for p in item["points"] if x0 < p[0] < x1 and y0 < p[1] < y1]
            assert inside == [], (item["net"], item["layer"], inside[:5])
            continue
        bx0, by0, bx1, by1 = item["bbox"]
        assert bx1 <= x0 or bx0 >= x1 or by1 <= y0 or by0 >= y1, item


def test_bottom_edge_connectors(features):
    kinds = {c["ref"]: c for c in features["connectors"]}
    for ref in ("J1", "J2", "J3", "J4"):
        assert kinds[ref]["edge"] == "bottom", ref
        assert kinds[ref]["y"] < 15, ref  # pin row within 15 mm of the bottom edge
    assert kinds["J5"]["edge"] == "top"
    assert kinds["J4"]["x"] < min(kinds[r]["x"] for r in ("J1", "J2", "J3"))  # CT at the low-voltage end


def test_features_json_matches_board(board_dump, features):
    fps = {f["ref"]: f for f in board_dump["footprints"]}
    holes = sorted((round(f["x"], 2), round(f["y"], 2)) for f in board_dump["footprints"] if f["ref"].startswith("H"))
    assert holes == sorted((round(h[0], 2), round(h[1], 2)) for h in features["holes"])
    for c in features["connectors"]:
        assert abs(fps[c["ref"]]["x"] - c["x"]) < 0.01 and abs(fps[c["ref"]]["y"] - c["y"]) < 0.01, c["ref"]


def test_size(features):
    w, h = features["outline_mm"]
    assert w <= 80 and h <= 80


def test_mounting_holes(board_dump):
    holes = [f for f in board_dump["footprints"] if f["ref"].startswith("H")]
    assert len(holes) == 4
    for h in holes:
        assert abs(h["drill"] - 3.2) < 0.01


def test_mains_far_from_holes(board_dump):
    """Screw heads (5.5 mm) keep 4 mm from any mains copper."""
    mains = [i for i in board_dump["copper"] if i["netclass"].startswith(("MAINS", "RELAY"))]
    for h in (f for f in board_dump["footprints"] if f["ref"].startswith("H")):
        for m in mains:
            if m["kind"] == "zone":
                d = min(((p[0] - h["x"]) ** 2 + (p[1] - h["y"]) ** 2) ** 0.5 for p in m["points"])
                assert d >= 2.75 + 4.0, (h["ref"], m["net"])
                continue
            if m["kind"] == "PCB_TRACK":
                d = _seg_dist((h["x"], h["y"]), m["start"], m["end"]) - m["width"] / 2
            else:
                bx0, by0, bx1, by1 = m["bbox"]
                dx = max(bx0 - h["x"], 0, h["x"] - bx1)
                dy = max(by0 - h["y"], 0, h["y"] - by1)
                d = (dx * dx + dy * dy) ** 0.5
            assert d >= 2.75 + 4.0, (h["ref"], m["net"], round(d, 2))


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    vx, vy = bx - ax, by - ay
    t = 0.0 if vx == vy == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
    return ((px - ax - t * vx) ** 2 + (py - ay - t * vy) ** 2) ** 0.5


# ---- Task 5: routed board -----------------------------------------------------------------------
def test_drc_clean(drc):
    errors = [v for v in drc["violations"] if v["severity"] == "error"]
    assert errors == [], _fmt(errors)
    assert drc["unconnected_items"] == [], _fmt(drc["unconnected_items"])


def test_relay_copper_width(board_dump):
    """Relay contacts carry 10 A: no thin tracks on them, and >= 5 mm wide copper on both layers from
    the relay pin to the terminal pin."""
    for item in board_dump["copper"]:
        if item["netclass"].startswith("RELAY") and item["kind"] == "PCB_TRACK":
            assert item["width"] >= 2.5, item
    pads = {(p["ref"], p["net"]): p for p in board_dump["copper"] if p["kind"] == "pad"}
    for k, j in ((1, "J2"), (2, "J3")):
        for contact in ("COM", "NO"):
            net = f"/K{k}_{contact}"
            for layer in ("F.Cu", "B.Cu"):
                zones = [z for z in board_dump["copper"] if z["kind"] == "zone" and z["net"] == net
                         and z["layer"] == layer]
                assert zones, (net, layer)
                xs = sorted({p[0] for z in zones for p in z["points"]})
                assert xs[-1] - xs[0] >= 5.0 - 0.5, (net, layer, xs[0], xs[-1])  # 0.5 mm sample grid
                for ref in (f"K{k}", j):
                    pad = pads[(ref, net)]
                    cx = (pad["bbox"][0] + pad["bbox"][2]) / 2
                    cy = (pad["bbox"][1] + pad["bbox"][3]) / 2
                    near = min(abs(p[0] - cx) + abs(p[1] - cy) for z in zones for p in z["points"])
                    assert near < 2.0, (net, layer, ref)


def test_mains_tracks_on_top(board_dump):
    """L/N and divider copper is on the top layer only (the bottom side is a plain warning area)."""
    for item in board_dump["copper"]:
        if item["kind"] == "PCB_TRACK" and item["netclass"].startswith("MAINS"):
            assert item["layer"] == "F.Cu", item
