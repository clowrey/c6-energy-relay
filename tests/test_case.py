"""build123d DIN-rail case (base, cover, DIN clip): valid solids, the board and the mated plugs fit, the
front stays closed, the back is sealed, every part prints flat and the DIN latch really moves."""
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
    base, cover, clip = parts
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
    base, lid, clip = parts
    for x, y, _ in FEATURES["holes"]:
        # self-tap pilot: open at its axis, plastic 1.6 mm out (2.8 mm hole, 6 mm deep, in the cover pillar)
        z = case.Z_BOARD_TOP + 3.0
        assert not lid.is_inside(Vector(x, y, z))
        assert lid.is_inside(Vector(x + 1.6, y, z))
        assert not lid.is_inside(Vector(x + 1.3, y, z))
    assert case.M3_PILOT_D == 2.8


def test_front_face_closed(parts):
    _, lid, _ = parts
    w, h = FEATURES["outline_mm"]
    z = case.Z_FRONT_OUT - 0.3
    for i in range(0, int(w) + 1, 2):
        for j in range(0, int(h) + 1, 2):
            assert lid.is_inside(Vector(i, j, z)), (i, j)


def test_din_clip_span(parts):
    assert abs(case.RAIL_SPAN - 35.0) <= 0.3
    clip = parts[2]
    # the hook's catching face and the latch's catching face are RAIL_SPAN apart
    yc = case.RAIL_Y
    zl = case.Z_CLIP_OUT - case.FLANGE_GAP / 2        # in the gap the rail flange sits in
    assert case.FLANGE_GAP > case.FLANGE_T
    x = case.RAIL_PROBE_X
    assert not clip.is_inside(Vector(x, yc + case.RAIL_SPAN / 2 - 0.1, zl))
    assert clip.is_inside(Vector(x, yc + case.RAIL_SPAN / 2 + 0.3, zl))
    assert not clip.is_inside(Vector(x, yc - case.RAIL_SPAN / 2 + 0.1, zl))
    assert clip.is_inside(Vector(x, yc - case.RAIL_SPAN / 2 - 0.3, zl))


def test_board_goes_in(parts):
    """The board drops into the cover from the open back: nothing inside the walls stands in the
    path its outline sweeps from the back edge down to its seat on the pillars."""
    _, cover, _ = parts
    w, h = FEATURES["outline_mm"]
    path = case.slab(0, w, 0, h, case.Z_BACK_IN - 1.0, case.Z_BOARD_TOP - 0.05, FEATURES["corner_r"])
    assert _overlap(cover, path) < 0.01, _overlap(cover, path)
    # and it seats on the pillars
    for x, y, _ in FEATURES["holes"]:
        assert cover.is_inside(Vector(x + 2.5, y, case.Z_BOARD_TOP + 0.2))


def test_screws_fit(parts):
    """One M3 x 16 countersunk screw per hole: flush in the clip's back face, through the clip, the base,
    its standoff and the board, at least 5 mm into the pillar's pilot and short of its end."""
    base, cover, clip = parts
    assert case.CSK_D >= 6.0                                      # M3 flat head is 5.5-6.0 mm
    tip = case.Z_CLIP_OUT + case.SCREW_LEN
    assert tip - case.Z_BOARD_TOP >= 5.0
    assert tip <= case.Z_BOARD_TOP + case.M3_PILOT_DEPTH - 0.5
    for x, y, _ in FEATURES["holes"]:
        # standoff clamps the board: plastic up to the board's solder side, clear hole down its middle
        assert base.is_inside(Vector(x + 2.5, y, -0.2))
        for z in (case.Z_BACK_OUT + 0.1, -2.0, -0.2):
            assert not base.is_inside(Vector(x + 1.6, y, z)), ((x, y), z)
        # through the clip, countersunk at its back face: open 3.2 mm out at the face, plastic beside it
        assert not clip.is_inside(Vector(x + 1.6, y, case.Z_BACK_OUT - 0.2))
        assert not clip.is_inside(Vector(x + 3.1, y, case.Z_CLIP_OUT + 0.1))
        assert clip.is_inside(Vector(x + 3.6, y, case.Z_CLIP_OUT + 0.1))
        # the head and a driver get in from behind: nothing of the clip (hook, ribs) behind the face
        for dx in (-3.0, 0.0, 3.0):
            assert not clip.is_inside(Vector(x + dx, y, case.Z_CLIP_OUT - 1.0)), ((x, y), dx)
        # the screw path through the cover: pilot only, no plastic in the board's hole or behind it
        assert not cover.is_inside(Vector(x, y, -2.0))


def test_din_clip_strong(parts):
    """A clip that holds: thick hook and latch walls, lips that reach well over the flange, a wide
    latch block, ribs behind the hook, and a hook that runs whole (no screw clearance bitten out)."""
    clip = parts[2]
    assert case.HOOK_W >= 3.5 and case.LIP_W >= 2.0 and case.LIP_T >= 2.0
    assert case.HOOK_LEN >= 60 and case.LATCH_W >= 20
    yc, x = case.RAIL_Y, case.RAIL_PROBE_X
    w, h = FEATURES["outline_mm"]
    ht = yc + case.RAIL_SPAN / 2
    z_tip = case.Z_CLIP_OUT - case.FLANGE_GAP - case.LIP_T
    # hook lip at full reach and thickness, gusset behind the hook wall, wall solid out to both ends
    assert clip.is_inside(Vector(x, ht - case.LIP_W + 0.2, z_tip + 0.2))
    gx = case.HOOK_GUSSETS[0]
    assert clip.is_inside(Vector(gx, ht + case.HOOK_W + 0.5, case.Z_CLIP_OUT - 0.5))
    for hx in (w / 2 - case.HOOK_LEN / 2 + 0.3, w / 2 + case.HOOK_LEN / 2 - 0.3):
        for hy in (ht - case.LIP_W + 0.2, ht + case.HOOK_W - 0.2):
            assert clip.is_inside(Vector(hx, hy, z_tip + 0.3)), (hx, hy)
    # latch lip across its full width
    lt = yc - case.RAIL_SPAN / 2
    for dx in (-case.LATCH_W / 2 + 0.5, case.LATCH_W / 2 - 0.5):
        assert clip.is_inside(Vector(x + dx, lt + 0.3, z_tip + 1.5))


def test_din_latch_moves(parts):
    """The latch block must move down by the lip's reach (plus margin) to clear the flange. It rides on
    spring beams that bend in the clip plate's own plane (their 1.6 mm side, not the plate thickness),
    so the bending strain is a guided beam's 3 d h / L^2: kept well under PETG's ~3 % yield. And the
    room is really there: the slot below the moving part is clear for the whole travel."""
    clip = parts[2]
    w, _ = FEATURES["outline_mm"]
    g = case.latch_geometry(w)
    assert case.LATCH_TRAVEL >= case.LIP_W + 0.3
    beam_len = (case.BEAM_X1 - case.BEAM_X0 - case.LATCH_W) / 2
    assert 3 * case.LATCH_TRAVEL * case.BEAM_H / beam_len ** 2 <= 0.015
    zm = (case.Z_CLIP_OUT + case.Z_BACK_OUT) / 2
    cx = w / 2
    # free slot under the shuttle and beside its tab for the full travel (+ 0.2)
    for px in (g["lx0"] + 0.5, cx - case.TAB_W / 2 - 0.4, g["lx1"] - 0.5):
        assert not clip.is_inside(Vector(px, g["s_lo"] - case.LATCH_TRAVEL - 0.2, zm)), px
    # the beams are free of the fixed plate along their length (slot above, between and below them)
    for bx in (case.BEAM_X0 + 3, case.BEAM_X1 - 3):
        assert clip.is_inside(Vector(bx, g["s_hi"] - case.BEAM_H / 2, zm))
        assert clip.is_inside(Vector(bx, g["s_hi"] - 1.5 * case.BEAM_H - case.BEAM_GAP, zm))
        for gy in (g["s_hi"] + 0.4, g["s_hi"] - case.BEAM_H - case.BEAM_GAP / 2, g["s_lo"] - 0.4):
            assert not clip.is_inside(Vector(bx, gy, zm)), (bx, gy)
    # the pull tab reaches past the case's bottom edge, with a screwdriver slot
    y_edge = -case.GAP - case.WALL
    assert clip.is_inside(Vector(cx + case.TAB_W / 2 - 0.5, y_edge - case.TAB_OUT + 0.3, zm))
    assert not clip.is_inside(Vector(cx, y_edge - case.TAB_OUT + case.TAB_BAR + case.PRY_SLOT[1] / 2, zm))


def test_back_sealed(parts):
    """Under the whole board the base plate is solid: the only openings are the four screw holes, so
    nothing pushed in from the back (a screwdriver at the latch, the metal rail) reaches the mains
    parts. The clip's latch slots open only onto this plate."""
    base = parts[0]
    w, h = FEATURES["outline_mm"]
    zm = (case.Z_BACK_OUT + case.Z_BACK_IN) / 2
    holes = FEATURES["holes"]
    for i in range(1, int(w)):
        for j in range(1, int(h)):
            if any((i - hx) ** 2 + (j - hy) ** 2 < 2.0 ** 2 for hx, hy, _ in holes):
                continue
            assert base.is_inside(Vector(i, j, zm)), (i, j)


def test_parts_print_flat(parts):
    """Base prints on its flat back face, clip on its flat base-side face, cover on its flat front face."""
    base, cover, clip = parts
    assert abs(base.bounding_box().min.Z - case.Z_BACK_OUT) < 1e-3
    assert abs(clip.bounding_box().max.Z - case.Z_BACK_OUT) < 1e-3
    assert abs(cover.bounding_box().max.Z - case.Z_FRONT_OUT) < 1e-3
    w, h = FEATURES["outline_mm"]
    for i in range(0, int(w) + 1, 4):            # the clip's base-side face is a full flat face
        for j in (0, int(h)):
            assert clip.is_inside(Vector(i, j, case.Z_BACK_OUT - 0.1)), (i, j)


def test_parts_dont_collide(parts):
    base, cover, clip = parts
    assert _overlap(base, cover) < 0.01, _overlap(base, cover)
    assert _overlap(clip, base) < 0.01, _overlap(clip, base)
    assert _overlap(clip, cover) < 0.01, _overlap(clip, cover)


def test_pull_tab_strong(parts):
    """Pull tab is at least 10 mm wide, projects at least 4.5 mm past the bottom edge, and keeps at
    least 2.2 mm of solid plastic around the screwdriver slot on every side."""
    clip = parts[2]
    w, _ = FEATURES["outline_mm"]
    cx = w / 2
    sx, sy = case.PRY_SLOT
    assert case.TAB_W >= 10.0
    assert case.TAB_OUT >= 4.5
    assert sx >= 4.5 and sy >= 1.6
    assert case.TAB_BAR >= 2.2
    assert (case.TAB_W - sx) / 2 >= 2.2
    zm = (case.Z_CLIP_OUT + case.Z_BACK_OUT) / 2
    y_edge = -case.GAP - case.WALL
    slot_y0 = y_edge - case.TAB_OUT + case.TAB_BAR
    slot_y1 = slot_y0 + sy
    slot_ym = (slot_y0 + slot_y1) / 2
    # screwdriver slot is open across its width
    for dx in (-sx / 2 + 0.3, 0.0, sx / 2 - 0.3):
        assert not clip.is_inside(Vector(cx + dx, slot_ym, zm)), dx
    # at least 2.2 mm of solid plastic around the slot on every side
    for d in (0.3, 2.0):
        assert clip.is_inside(Vector(cx, slot_y0 - d, zm)), ("below", d)
        assert clip.is_inside(Vector(cx, slot_y1 + d, zm)), ("above", d)
        assert clip.is_inside(Vector(cx - sx / 2 - d, slot_ym, zm)), ("left", d)
        assert clip.is_inside(Vector(cx + sx / 2 + d, slot_ym, zm)), ("right", d)


def test_base_relief_pocket(parts):
    """The base's back face has a 0.4 mm relief pocket across the whole area swept by the clip's moving
    parts (+ 1.5 mm margin), while staying solid behind the pocket and flat everywhere else."""
    base = parts[0]
    w, _ = FEATURES["outline_mm"]
    g = case.latch_geometry(w)
    cx = w / 2
    assert case.BASE_RELIEF >= 0.4
    assert case.RELIEF_MARGIN >= 1.5
    z_clear = case.Z_BACK_OUT + 0.2
    z_solid = case.Z_BACK_OUT + case.BASE_RELIEF + 0.2
    swept_points = (
        (case.BEAM_X0 + 3.0, g["s_hi"] - 1.0),                              # left beam
        (case.BEAM_X1 - 3.0, g["s_lo"] + 1.0),                              # right beam
        (cx, (g["s_lo"] + g["s_hi"]) / 2),                                  # shuttle at rest
        (cx, g["s_lo"] - case.LATCH_TRAVEL),                                # shuttle at full travel
        (cx, 5.0),                                                          # pull tab mid-channel
        (cx, -1.0),                                                         # pull tab at bottom edge
        (case.BEAM_X0 - 1.0, g["cut_hi"] + 1.0),                            # beam + slot margin
        (cx + case.TAB_W / 2 + case.SLOT_PLAY + 1.0, 5.0),                  # tab channel margin
    )
    for px, py in swept_points:
        assert not base.is_inside(Vector(px, py, z_clear)), (px, py)
        assert base.is_inside(Vector(px, py, z_solid)), (px, py)
    # fixed areas outside the pocket stay flush at Z_BACK_OUT so the base prints flat
    for px, py in ((10.0, 50.0), (10.0, 5.0), (70.0, 5.0)):
        assert base.is_inside(Vector(px, py, z_clear)), (px, py)


def test_z_retention(parts):
    """Two bridged straps retain the pull tab in -z with >= 0.4 mm play in every direction, full latch
    travel, <= 1.6 mm protrusion past Z_CLIP_OUT, and clear of the DIN rail and screws."""
    clip = parts[2]
    w, _ = FEATURES["outline_mm"]
    g = case.latch_geometry(w)
    cx = w / 2
    assert case.STRAP_GAP >= 0.4
    assert case.STRAP_GAP + case.STRAP_T <= 1.6 + 1e-6
    assert case.STRAP_W <= 10.0
    z_strap = case.Z_CLIP_OUT - case.STRAP_GAP - case.STRAP_T / 2
    for sy in case.STRAP_YS:
        # strap sits behind the tab in -z, without exceeding 1.6 mm beyond Z_CLIP_OUT
        assert clip.is_inside(Vector(cx, sy, z_strap)), sy
        assert not clip.is_inside(Vector(cx, sy, case.Z_CLIP_OUT - 1.7)), sy
        # at least 0.4 mm of z-play between tab outer face and strap underside
        assert clip.is_inside(Vector(cx, sy, case.Z_CLIP_OUT + 0.5)), sy
        assert not clip.is_inside(Vector(cx, sy, case.Z_CLIP_OUT - 0.1)), sy
        assert not clip.is_inside(Vector(cx, sy, case.Z_CLIP_OUT - 0.35)), sy
        # at least 0.4 mm of x-play on each side of the tab inside the strap arch
        for side in (-1, 1):
            assert not clip.is_inside(Vector(cx + side * (case.TAB_W / 2 + 0.2), sy, case.Z_CLIP_OUT - 0.2))
            assert not clip.is_inside(Vector(cx + side * (case.TAB_W / 2 + 0.35), sy, case.Z_CLIP_OUT - 0.2))
        # clear of the rail lower flange and of the shuttle over its full travel
        assert sy + case.STRAP_W / 2 < case.RAIL_Y - 17.5
        assert sy + case.STRAP_W / 2 < g["s_lo"] - case.LATCH_TRAVEL - 0.4
    assert not clip.is_inside(Vector(cx, g["s_lo"] - case.LATCH_TRAVEL, z_strap))


def test_flange_gap(parts):
    """FLANGE_GAP is 1.6 mm so lips printed with supports clear a 1.0 mm TS35 rail flange."""
    clip = parts[2]
    assert abs(case.FLANGE_GAP - 1.6) < 1e-6
    x, yc = case.RAIL_PROBE_X, case.RAIL_Y
    ht = yc + case.RAIL_SPAN / 2
    lt = yc - case.RAIL_SPAN / 2
    for py in (ht - case.LIP_W / 2, lt + 0.4):
        assert not clip.is_inside(Vector(x, py, case.Z_CLIP_OUT - 0.2)), py
        assert not clip.is_inside(Vector(x, py, case.Z_CLIP_OUT - 1.4)), py
        assert clip.is_inside(Vector(x, py, case.Z_CLIP_OUT - case.FLANGE_GAP - 0.3)), py


def test_pillars_fused_to_near_walls(parts):
    """H3's pillar is too close to the bottom wall (0.3 mm) to print as a gap: it is fused to the wall above
    the board and open below it, so the board drops in. H2's stays open: side vents are behind it."""
    _, cover, _ = parts
    w, _ = FEATURES["outline_mm"]
    for z in (case.Z_BOARD_TOP + 0.4, 10.0, case.Z_FRONT_IN - 0.5):
        assert cover.is_inside(Vector(21.0, -0.65, z)), z
    for z in (0.0, case.Z_BOARD_TOP - 0.4):
        assert not cover.is_inside(Vector(21.0, -0.65, z)), z
    assert not cover.is_inside(Vector(w + case.GAP - 0.4, 43.0, 5.0))
    for i in range(5):                                # every side vent reaches the inside, past H2's pillar
        vy = 31.0 + i * 3.2 + 0.8
        for x in (w + case.GAP - 0.4, w + case.GAP + case.WALL / 2):
            assert not cover.is_inside(Vector(x, vy, 10.0)), (x, vy)


def test_no_gap_below_the_board(parts):
    """Below the board's component side the bottom wall is solid behind every plug opening: nothing pushed in
    beside a plug gets under the board to the mains solder joints. And the plugs' tops clear the openings."""
    _, cover, _ = parts
    for c in FEATURES["connectors"]:
        if c["edge"] != "bottom":
            continue
        x0, _, _, x1, _, z1 = c["plug_envelope"]
        wy = -case.GAP - case.WALL / 2
        for k in range(11):
            x = x0 + (x1 - x0) * k / 10
            for z in (case.Z_BACK_IN + 0.2, -2.0, 0.0, 0.4):
                assert cover.is_inside(Vector(x, wy, z)), (c["ref"], x, z)
            assert not cover.is_inside(Vector(x, wy, z1 + 0.5)), c["ref"]


def test_led_light_tube(parts):
    """Hollow 5.0 mm ID, 1.2 mm wall LED light tube runs from Z_FRONT_IN down to z = 5.0, fused to
    the top wall, open down its bore, clear below z = 5.0, and closed by the 0.6 mm front window."""
    _, cover, _ = parts
    _, h = FEATURES["outline_mm"]
    lx, ly = FEATURES["led"]
    assert case.LED_TUBE_ID == 5.0
    assert case.LED_TUBE_WALL == 1.2
    assert case.LED_TUBE_Z0 == 5.0
    r_in = case.LED_TUBE_ID / 2
    r_mid = r_in + case.LED_TUBE_WALL / 2
    r_out = r_in + case.LED_TUBE_WALL
    for z in (case.LED_TUBE_Z0 + 0.5, 13.0, case.Z_FRONT_IN - 0.5):
        # bore is open
        assert not cover.is_inside(Vector(lx, ly, z)), z
        assert not cover.is_inside(Vector(lx + r_in - 0.3, ly, z)), z
        # solid 1.2 mm tube wall on all four sides
        for dx, dy in ((r_mid, 0.0), (-r_mid, 0.0), (0.0, r_mid), (0.0, -r_mid)):
            assert cover.is_inside(Vector(lx + dx, ly + dy, z)), (dx, dy, z)
        # clear outside the tube on the board-facing side
        assert not cover.is_inside(Vector(lx, ly - r_out - 0.5, z)), z
    # clear below z = 5.0 above the LED, fused to the top wall, and 0.6 mm front window intact
    assert not cover.is_inside(Vector(lx, ly - r_mid, case.LED_TUBE_Z0 - 0.5))
    assert cover.is_inside(Vector(lx, h + case.GAP - 0.1, 13.0))
    assert cover.is_inside(Vector(lx, h + case.GAP + 0.1, 13.0))
    assert not cover.is_inside(Vector(lx, ly, case.Z_FRONT_OUT - case.LED_WINDOW - 0.2))
    assert cover.is_inside(Vector(lx, ly, case.Z_FRONT_OUT - case.LED_WINDOW / 2))
