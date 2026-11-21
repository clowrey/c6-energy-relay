"""build123d DIN-rail case: valid solids, the board and the mated plugs fit, the front stays closed."""
import json
import sys

import pytest
from conftest import HW, ROOT

sys.path.insert(0, str(ROOT / "case"))
import case  # noqa: E402
from build123d import Box, Pos, Vector, import_step  # noqa: E402

FEATURES = json.loads((HW / "out" / "board_features.json").read_text())


@pytest.fixture(scope="module")
def parts():
    return case.build_case(FEATURES)


@pytest.fixture(scope="module")
def board():
    shape = import_step(str(HW / "out" / "board.step"))
    return case.board_to_case(shape)


def _overlap(a, b):
    try:
        return (a & b).volume
    except Exception:
        return 0.0


def test_solids_valid(parts):
    for p in parts:
        assert p.is_valid
        assert p.volume > 1000


def test_board_fits(parts, board):
    for p in parts:
        assert _overlap(p, board) < 1.0, _overlap(p, board)   # contact faces at the screw bosses only


def test_plugs_clear(parts):
    for c in FEATURES["connectors"]:
        x0, y0, z0, x1, y1, z1 = c["plug_envelope"]
        env = Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)
        for p in parts:
            assert _overlap(p, env) < 0.01, (c["ref"], _overlap(p, env))


def test_pilot_holes(parts):
    base, lid = parts
    for x, y, _ in FEATURES["holes"]:
        # self-tap pilot: open at its axis, plastic 1.6 mm out (2.8 mm hole, 6 mm deep, in the cover pillar)
        z = case.Z_BOARD_TOP + 3.0
        assert not lid.is_inside(Vector(x, y, z))
        assert lid.is_inside(Vector(x + 1.6, y, z))
        assert not lid.is_inside(Vector(x + 1.3, y, z))
    assert case.M3_PILOT_D == 2.8


def test_front_face_closed(parts):
    _, lid = parts
    w, h = FEATURES["outline_mm"]
    z = case.Z_FRONT_OUT - 0.3
    for i in range(0, int(w) + 1, 2):
        for j in range(0, int(h) + 1, 2):
            assert lid.is_inside(Vector(i, j, z)), (i, j)


def test_din_clip_span(parts):
    assert abs(case.RAIL_SPAN - 35.0) <= 0.3
    base, _ = parts
    # the hook's catching face and the latch's catching face are RAIL_SPAN apart
    yc = case.RAIL_Y
    zl = case.Z_BACK_OUT - case.FLANGE_T / 2          # in the gap the rail flange sits in
    x = case.RAIL_PROBE_X
    assert not base.is_inside(Vector(x, yc + case.RAIL_SPAN / 2 - 0.1, zl))
    assert base.is_inside(Vector(x, yc + case.RAIL_SPAN / 2 + 0.3, zl))
    assert not base.is_inside(Vector(x, yc - case.RAIL_SPAN / 2 + 0.1, zl))
    assert base.is_inside(Vector(x, yc - case.RAIL_SPAN / 2 - 0.3, zl))
