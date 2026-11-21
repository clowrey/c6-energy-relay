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
    """Volume of a & b, solid by solid (a Compound & Solid is unreliable; build123d may return a
    ShapeList with None for no overlap). Errors must surface, never count as 'no overlap'."""
    total = 0.0
    for sb in b.solids():
        r = a & sb
        total += sum(s.volume for s in (r if isinstance(r, list) else [r]) if s is not None)
    return total


def test_openings_cut(parts):
    """Each plug, USB-C, vent and the LED window is a hole through the cover, not solid plastic."""
    base, cover = parts
    w, h = FEATURES["outline_mm"]
    wall_y_bottom = -case.GAP - case.WALL / 2
    for c in FEATURES["connectors"]:
        x0, y0, z0, x1, y1, z1 = c["plug_envelope"]
        wy = wall_y_bottom if c["edge"] == "bottom" else h + case.GAP + case.WALL / 2
        assert not cover.is_inside(Vector((x0 + x1) / 2, wy, (z0 + z1) / 2)), c["ref"]
    hot = FEATURES["hot_parts"][0]
    assert not cover.is_inside(Vector(hot[0] + 3.8, h + case.GAP + case.WALL / 2, 10))      # top vent
    assert not cover.is_inside(Vector(w + case.GAP + case.WALL / 2, 31.8, 10))              # side vent
    lx, ly = FEATURES["led"]
    assert not cover.is_inside(Vector(lx, ly, case.Z_FRONT_OUT - case.LED_WINDOW - 0.2))
    assert cover.is_inside(Vector(lx, ly, case.Z_FRONT_OUT - case.LED_WINDOW / 2))


def test_solids_valid(parts):
    for p in parts:
        assert p.is_valid
        assert p.volume > 1000


def test_board_fits(parts, board):
    for p in parts:
        assert _overlap(p, board) < 1.0, _overlap(p, board)   # contact faces at the pillars and standoffs only


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


def test_board_goes_in(parts):
    """The board drops into the cover from the open back: nothing inside the walls stands in the
    path its outline sweeps from the back edge down to its seat on the pillars."""
    _, cover = parts
    w, h = FEATURES["outline_mm"]
    path = case.slab(0, w, 0, h, case.Z_BACK_IN - 1.0, case.Z_BOARD_TOP - 0.05, FEATURES["corner_r"])
    assert _overlap(cover, path) < 0.01, _overlap(cover, path)
    # and it seats on the pillars
    for x, y, _ in FEATURES["holes"]:
        assert cover.is_inside(Vector(x + 2.5, y, case.Z_BOARD_TOP + 0.2))


def test_screws_fit(parts):
    """One M3 x 14 countersunk screw per hole: flush in the back face, through the base standoff and
    the board, at least 5 mm into the pillar's pilot and short of its end."""
    base, cover = parts
    assert case.CSK_D >= 6.0                                      # M3 flat head is 5.5-6.0 mm
    tip = case.Z_BACK_OUT + case.SCREW_LEN
    assert tip - case.Z_BOARD_TOP >= 5.0
    assert tip <= case.Z_BOARD_TOP + case.M3_PILOT_DEPTH - 0.5
    for x, y, _ in FEATURES["holes"]:
        # standoff clamps the board: plastic up to the board's solder side, clear hole down its middle
        assert base.is_inside(Vector(x + 2.5, y, -0.2))
        for z in (case.Z_BACK_OUT + 0.1, -2.0, -0.2):
            assert not base.is_inside(Vector(x + 1.6, y, z)), ((x, y), z)
        # countersink: open at 3.2 mm out at the back face, plastic beside it
        assert not base.is_inside(Vector(x + 3.1, y, case.Z_BACK_OUT + 0.1))
        assert base.is_inside(Vector(x + 3.6, y, case.Z_BACK_OUT + 0.1))
        # the head and a driver get in from behind: nothing of the base behind the back face
        for dx in (-3.0, 0.0, 3.0):
            assert not base.is_inside(Vector(x + dx, y, case.Z_BACK_OUT - 1.0)), ((x, y), dx)
        # the screw path through the cover: pilot only, no plastic in the board's hole or behind it
        assert not cover.is_inside(Vector(x, y, -2.0))


def test_din_clip_strong(parts):
    """A clip that holds: thick hook and latch walls, lips that reach well over the flange, a wide
    latch block, gussets behind the hook, and a latch beam long enough that releasing it (bending it
    by the lip's reach) strains the PETG well under its ~3 % yield (fixed-fixed beam: 12 d t / L^2)."""
    base, _ = parts
    assert case.HOOK_W >= 3.5 and case.LIP_W >= 2.0 and case.LIP_T >= 2.0
    assert case.HOOK_LEN >= 60 and case.LATCH_W >= 20
    release = case.LIP_W + 0.2
    assert 12 * release * case.WALL / case.BEAM_L ** 2 <= 0.015
    yc, x = case.RAIL_Y, case.RAIL_PROBE_X
    ht = yc + case.RAIL_SPAN / 2
    z_tip = case.Z_BACK_OUT - case.FLANGE_T - 0.2 - case.LIP_T
    # hook lip at full reach and thickness, gusset behind the hook wall
    assert base.is_inside(Vector(x, ht - case.LIP_W + 0.2, z_tip + 0.2))
    gx = case.HOOK_GUSSETS[0]
    assert base.is_inside(Vector(gx, ht + case.HOOK_W + 0.5, case.Z_BACK_OUT - 0.5))
    # latch lip across its full width
    lt = yc - case.RAIL_SPAN / 2
    for dx in (-case.LATCH_W / 2 + 0.5, case.LATCH_W / 2 - 0.5):
        assert base.is_inside(Vector(x + dx, lt + 0.5, z_tip + 1.0))
