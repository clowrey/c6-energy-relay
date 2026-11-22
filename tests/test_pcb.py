"""The board: KiCad DRC (with schematic parity and the project's creepage rules), plus layout rules
from the spec that DRC can't express."""
import json
import re

import pytest
from conftest import HW, kcli, kpy

from hw.parts import PARTS

PCB = HW / "c6-energy-relay.kicad_pcb"
FEATURES = HW / "out" / "board_features.json"
SPACING_TYPES = {"clearance", "creepage", "hole_clearance", "copper_edge_clearance"}


@pytest.fixture(scope="module")
def drc(tmp_path_factory):
    out = tmp_path_factory.mktemp("drc") / "drc.json"
    kcli("pcb", "drc", "--schematic-parity", "--severity-all", "--format", "json", "--units", "mm", "-o", out, PCB,
         check=False)
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
    """The case screws pass through these holes and can be touched from the back of the case: each
    hole's edge (3.2 mm) keeps 6.5 mm from any mains copper, measured to the exact track and arc
    geometry (the case tests' copper boxes are too coarse for this)."""
    mains = [i for i in board_dump["copper"] if i["netclass"].startswith(("MAINS", "RELAY"))]
    for h in (f for f in board_dump["footprints"] if f["ref"].startswith("H")):
        for m in mains:
            if m["kind"] == "zone":
                d = min(((p[0] - h["x"]) ** 2 + (p[1] - h["y"]) ** 2) ** 0.5 for p in m["points"])
                assert d >= 1.6 + 6.5, (h["ref"], m["net"])
                continue
            if m["kind"] == "PCB_TRACK":
                d = _seg_dist((h["x"], h["y"]), m["start"], m["end"]) - m["width"] / 2
            elif m["kind"] == "PCB_ARC":
                pts = _arc_points(m["start"], m["mid"], m["end"])
                d = min(_seg_dist((h["x"], h["y"]), a, b) for a, b in zip(pts, pts[1:])) - m["width"] / 2
            else:
                bx0, by0, bx1, by1 = m["bbox"]
                dx = max(bx0 - h["x"], 0, h["x"] - bx1)
                dy = max(by0 - h["y"], 0, h["y"] - by1)
                d = (dx * dx + dy * dy) ** 0.5
            assert d >= 1.6 + 6.5, (h["ref"], m["net"], round(d, 2))


def _arc_points(start, mid, end, n=24):
    """Points along the circular arc through start, mid and end."""
    import math
    (ax, ay), (bx, by), (cx, cy) = start, mid, end
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [start, end]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, a1, am = (math.atan2(p[1] - uy, p[0] - ux) for p in (start, end, mid))
    sweep = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sweep:      # the arc runs the other way round
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(a0 + sweep * i / n), uy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


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
    """L/N and divider tracks are on the top layer only (the bottom side is a plain warning area), except
    ZP1: it has to cross L_F, and must not run under the fuse."""
    for item in board_dump["copper"]:
        if item["kind"] == "PCB_TRACK" and item["netclass"].startswith("MAINS") and item["net"] != "/ZP1":
            assert item["layer"] == "F.Cu", item


def test_screw_bridge_mains_to_lv(board_dump):
    """A mounting screw is metal: the path mains copper -> screw -> low-voltage copper must still add
    up to 6.5 mm (screw head radius 2.75 mm)."""
    head = 2.75

    def dist(h, item):
        if item["kind"] == "zone":
            return min(((p[0] - h["x"]) ** 2 + (p[1] - h["y"]) ** 2) ** 0.5 for p in item["points"])
        if item["kind"] == "PCB_TRACK":
            return _seg_dist((h["x"], h["y"]), item["start"], item["end"]) - item["width"] / 2
        if item["kind"] == "PCB_ARC":
            pts = _arc_points(item["start"], item["mid"], item["end"])
            return min(_seg_dist((h["x"], h["y"]), a, b) for a, b in zip(pts, pts[1:])) - item["width"] / 2
        bx0, by0, bx1, by1 = item["bbox"]
        dx = max(bx0 - h["x"], 0, h["x"] - bx1)
        dy = max(by0 - h["y"], 0, h["y"] - by1)
        return (dx * dx + dy * dy) ** 0.5

    copper = [i for i in board_dump["copper"] if i["net"]]
    for h in (f for f in board_dump["footprints"] if f["ref"].startswith("H")):
        d_m = min(dist(h, i) for i in copper if i["netclass"].startswith(("MAINS", "RELAY")))
        d_l = min(dist(h, i) for i in copper if not i["netclass"].startswith(("MAINS", "RELAY")))
        assert (d_m - head) + (d_l - head) >= 6.5, (h["ref"], round(d_m, 2), round(d_l, 2))


def test_silkscreen_readable(drc):
    """No silk on silk, no text over pads (JLC clips it), no text under 0.8 mm."""
    bad = [v for v in drc["violations"] if v["type"] in ("silk_overlap", "text_height")]
    bad += [v for v in drc["violations"] if v["type"] == "silk_over_copper"
            and any(i["description"].startswith(("PCB text", "Reference field")) for i in v["items"])]
    assert bad == [], _fmt(bad)


def test_tracks_rounded(board_dump):
    """Every bend in a track is an arc: no point where exactly two straight segments of one net meet
    at an angle, away from pads and vias (junctions of three or more keep their corner)."""
    import math
    from collections import defaultdict
    cu = board_dump["copper"]
    ends = defaultdict(list)          # (net, layer, x, y) -> [(kind, other end)]
    vias = {(c["net"], round(c["start"][0], 3), round(c["start"][1], 3)) for c in cu if c["kind"] == "PCB_VIA"}
    pads = [c for c in cu if c["kind"] == "pad"]
    for c in cu:
        if c["kind"] not in ("PCB_TRACK", "PCB_ARC"):
            continue
        s, e = c["start"], c["end"]
        for p, q in ((s, e), (e, s)):
            ends[(c["net"], c["layer"], round(p[0], 3), round(p[1], 3))].append((c["kind"], q))
    sharp = []
    for (net, layer, x, y), items in ends.items():
        if len(items) != 2 or any(k != "PCB_TRACK" for k, _ in items) or (net, x, y) in vias:
            continue
        if any(p["net"] == net and p["bbox"][0] <= x <= p["bbox"][2] and p["bbox"][1] <= y <= p["bbox"][3]
               for p in pads):
            continue
        (_, a), (_, b) = items
        ang = math.degrees(math.atan2(a[1] - y, a[0] - x) - math.atan2(b[1] - y, b[0] - x)) % 360
        if abs(ang - 180) > 1:
            sharp.append((net, layer, x, y, round(ang)))
    assert sharp == [], f"{len(sharp)} sharp corners, e.g. {sharp[:8]}"


# ---- Second audit --------------------------------------------------------------------------------
def _track_pts(c):
    if c["kind"] == "PCB_ARC":
        return _arc_points(c["start"], c["mid"], c["end"])
    return [(c["start"][0] + (c["end"][0] - c["start"][0]) * k / 40,
             c["start"][1] + (c["end"][1] - c["start"][1]) * k / 40) for k in range(41)]


def test_nothing_under_the_fuses(board_dump):
    """No copper on either layer under F1 / F2 between their pads: an open, charred fuse must not be
    bridged by a track below it."""
    pads = [p for p in board_dump["copper"] if p["kind"] == "pad"]
    for ref in ("F1", "F2"):
        bb = [p["bbox"] for p in pads if p["ref"] == ref]
        assert len(bb) == 2, ref
        x0, x1 = min(b[0] for b in bb), max(b[2] for b in bb)
        lo, hi = sorted(bb, key=lambda b: b[1])
        y0, y1 = lo[3], hi[1]                              # between the two pads
        assert y1 - y0 >= 5.0, ref
        for c in board_dump["copper"]:
            if c["kind"] in ("PCB_TRACK", "PCB_ARC"):
                w = c["width"] / 2
                hits = [p for p in _track_pts(c) if x0 - w < p[0] < x1 + w and y0 + 0.05 < p[1] < y1 - 0.05]
            elif c["kind"] == "zone":
                hits = [p for p in c["points"] if x0 < p[0] < x1 and y0 < p[1] < y1]
            else:
                continue
            assert hits == [], (ref, c["net"], c["layer"], hits[:3])


def test_dru_covers_fuses_and_edges():
    dru = (HW / "c6-energy-relay.kicad_dru").read_text(encoding="utf8")
    for pre, post in (("/L_IN", "/L_F"), ("/L_IN", "/ZP1"), ("/N_IN", "/N_F")):
        assert f"A.NetName == '{pre}' && B.NetName == '{post}'" in dru or \
            (f"'{pre}'" in dru and f"'{post}'" in dru), (pre, post)
    edge = dru[dru.index('"mains copper to board edge"'):]
    for cls in ("MAINS_L", "MAINS_N", "MAINS_DIV", "RELAY1", "RELAY2"):
        assert f"'{cls}'" in edge, cls


def test_ceramics_off_the_edge(board_dump, features):
    """No ceramic capacitor pad within 1.5 mm of the board edge (flexing cracks them)."""
    w, h = features["outline_mm"]
    for p in board_dump["copper"]:
        if p["kind"] == "pad" and p["ref"].startswith("C") and p["ref"] != "C14":
            x0, y0, x1, y1 = p["bbox"]
            assert min(x0, y0, w - x1, h - y1) >= 1.5, p["ref"]


def test_mov_footprint_fits_the_part():
    """10D561K is up to 6.0 mm thick (datasheet table 2): the leads sit further apart than on a thin disc."""
    import re
    m = re.search(r"_W([\d.]+)mm_", PARTS["mov"].footprint)
    assert float(m.group(1)) >= 6.0


def test_plug_openings_start_at_the_board(features):
    """The plugs sit on the component side: no opening below the board face (that slot would lead under
    the board to mains pins), and the tops clear the 15.2 mm / 12 mm plugs."""
    for c in features["connectors"]:
        if c["edge"] == "bottom":
            z0, z1 = c["plug_envelope"][2], c["plug_envelope"][5]
            assert z0 >= 1.5, c["ref"]
            assert z1 >= (17.2 if c["kind"] == "term508" else 13.6), c["ref"]
