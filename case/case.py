"""3D-printed DIN-rail case for the C6 energy relay board, in build123d.

    python case/case.py            # reads hw/out/board_features.json, writes case/out/*.step|stl

Two parts:
  cover  the front shell: closed front face, four walls, pillars that hold the board. The board is
         screwed to the pillars from its solder side (4 x M3 x 8, self-tapping into 2.8 mm pilots).
         Wall openings: the plug row along the bottom edge, USB-C in the top edge, vents.
  base   the back plate that clips onto a TS35 rail: a fixed hook at the top and a sprung latch at the
         bottom (a 50 mm beam freed by two slots; lever it with a screwdriver in the lower slot to
         release). Four M3 x 4 screws from the back self-tap into 2.8 mm pilots in the cover's corner
         bosses.
Nothing opens on the front face: the status LED shows through a 0.6 mm thin window.

Printing: the base flat on its inside face (clip up), the cover on its front face (walls up). No
supports. PETG recommended (the latch flexes); 0.2 mm layers, 3 walls.

Coordinates: x, y as the board (origin at its lower-left corner, y up), z = 0 at the PCB's bottom
face, +z toward the front; the same frame as `kicad-cli pcb export step --drill-origin`.
"""
from __future__ import annotations

import json
from pathlib import Path

from build123d import (Axis, Box, Cylinder, Location, Plane, Pos, Rot, RectangleRounded, export_step,
                       export_stl, extrude)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"

WALL = 2.2
GAP = 0.8                     # board edge to the inside of the wall
CORNER_R = 3.0
Z_BOARD_TOP = 1.6
Z_BACK_IN = -4.0              # room behind the board for leads and the board-screw heads
Z_BACK_OUT = Z_BACK_IN - WALL
FRONT_CLEAR = 1.5             # above the tallest part
M3_PILOT_D, M3_PILOT_DEPTH = 2.8, 6.0
M3_LEAD_IN_D, M3_LEAD_IN = 3.4, 0.8
M3_CLEAR_D, M3_HEAD_D, M3_HEAD_H = 3.4, 6.0, 2.6
M3_HEAD_RECESS = 1.2          # counterbore depth for the base screws' heads
BASE_SCREW_LEN = 4.0          # M3 x 4: ends 1 mm short of the board
PILLAR_D = 6.0
BOSS_D = 5.8
LED_WINDOW = 0.6

# TS35 rail: flanges 35 mm apart (outer edges), 1.0 mm thick
RAIL_SPAN = 35.2              # hook face to latch face
FLANGE_T = 1.0
LIP_T, LIP_W = 1.5, 1.5       # lip thickness (z) and reach over the flange (y)
HOOK_W = 2.5                  # hook / latch wall thickness (y)

# filled in by build_case() from the board features
RAIL_Y = 0.0
RAIL_PROBE_X = 0.0
Z_FRONT_IN = Z_FRONT_OUT = 0.0


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def cyl(x, y, d, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, z1 - z0)


def slab(x0, x1, y0, y1, z0, z1, r):
    sk = Plane.XY.offset(z0) * Pos((x0 + x1) / 2, (y0 + y1) / 2) * RectangleRounded(x1 - x0, y1 - y0, r)
    return extrude(sk, z1 - z0)


def one_solid(shape):
    """Boolean results sometimes come back as a ShapeList; the case parts are single solids."""
    solids = shape.solids() if hasattr(shape, "solids") else list(shape)
    assert len(solids) == 1, f"expected one solid, got {len(solids)}"
    return solids[0]


def corner_bosses(w, h):
    # clear of the plugs (bottom), the USB-C (top-left) and the antenna keep-out (top-right)
    # and >= 6.5 mm (plus the screw's radius) from the relay contact copper, clear of the board-screw
    # heads
    return [(0.0, 9.0), (0.0, h - 9.0), (w, 27.0), (w * 0.625, h)]


def build_cover(f):
    w, h = f["outline_mm"]
    x0, x1, y0, y1 = -GAP - WALL, w + GAP + WALL, -GAP - WALL, h + GAP + WALL
    shell = slab(x0, x1, y0, y1, Z_BACK_IN, Z_FRONT_OUT, CORNER_R)
    inner = slab(x0 + WALL, x1 - WALL, y0 + WALL, y1 - WALL, Z_BACK_IN - 1, Z_FRONT_IN, max(CORNER_R - WALL, 0.5))
    cover = shell - inner
    # pillars at the board's mounting holes, pilot from the board side
    for x, y, _ in f["holes"]:
        cover += cyl(x, y, PILLAR_D, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
        cover -= cyl(x, y, M3_PILOT_D, Z_BOARD_TOP - 0.1, Z_BOARD_TOP + M3_PILOT_DEPTH)
        cover -= cyl(x, y, M3_LEAD_IN_D, Z_BOARD_TOP - 0.1, Z_BOARD_TOP + M3_LEAD_IN)
    # corner bosses for the base screws (behind the board, below z = -0.6)
    for x, y in corner_bosses(w, h):
        cover += cyl(x, y, BOSS_D, Z_BACK_IN, -0.6)
        cover -= cyl(x, y, M3_PILOT_D, Z_BACK_IN - 0.1, Z_BACK_IN + 3.4)
    # trim the boss overhang. one_solid: `&` can return a ShapeList, and `ShapeList -= shape` is a
    # silent no-op (list difference), which once left every opening below uncut
    cover = one_solid(cover & slab(x0, x1, y0, y1, Z_BACK_IN, Z_FRONT_OUT, CORNER_R))
    # openings: plugs (bottom edge) and USB-C (top edge), 1 mm around each envelope
    for c in f["connectors"]:
        ex0, ey0, ez0, ex1, ey1, ez1 = c["plug_envelope"]
        if c["edge"] == "bottom":
            cover -= box(ex0 - 1.0, ex1 + 1.0, y0 - 1, -GAP + 0.5, max(ez0 - 1.0, Z_BACK_IN - 1), ez1 + 1.0)
        else:
            cover -= box(ex0 - 1.0, ex1 + 1.0, h + GAP - 0.5, y1 + 1, ez0 - 1.0, ez1 + 1.0)
    # vents: top edge over the HLK, right edge beside the relays
    hot = f["hot_parts"][0]                          # PS1: x, y, w, h
    for i in range(6):
        vx = hot[0] + 3.0 + i * 3.2
        cover -= box(vx, vx + 1.6, h + GAP - 0.5, y1 + 1, 5.0, Z_FRONT_IN - 3.0)
    for i in range(5):                               # above relay 2's contacts, not beside them
        vy = 31.0 + i * 3.2
        cover -= box(w + GAP - 0.5, x1 + 1, vy, vy + 1.6, 4.0, Z_FRONT_IN - 3.0)
    # LED window: thin the front face from the inside
    lx, ly = f["led"]
    cover -= cyl(lx, ly, 3.5, Z_FRONT_IN - 0.1, Z_FRONT_OUT - LED_WINDOW)
    return one_solid(cover)


def build_base(f):
    global RAIL_PROBE_X
    w, h = f["outline_mm"]
    x0, x1, y0, y1 = -GAP - WALL, w + GAP + WALL, -GAP - WALL, h + GAP + WALL
    base = slab(x0, x1, y0, y1, Z_BACK_OUT, Z_BACK_IN, CORNER_R)
    # screws into the cover's corner bosses: clearance + counterbore from the back
    for x, y in corner_bosses(w, h):
        base -= cyl(x, y, M3_CLEAR_D, Z_BACK_OUT - 1, Z_BACK_IN + 1)
        base -= cyl(x, y, M3_HEAD_D, Z_BACK_OUT - 1, Z_BACK_OUT + M3_HEAD_RECESS)
    yc = RAIL_Y
    z_lip0 = Z_BACK_OUT - FLANGE_T - 0.2           # lip's face toward the rail flange
    z_tip = z_lip0 - LIP_T
    # fixed hook at the top: wall + lip reaching down over the upper flange
    ht = yc + RAIL_SPAN / 2
    hx0, hx1 = 12.0, w - 12.0
    base += box(hx0, hx1, ht, ht + HOOK_W, z_tip, Z_BACK_OUT)
    base += box(hx0, hx1, ht - LIP_W, ht, z_tip, z_lip0)
    # sprung latch at the bottom: a 50 mm beam between two through-slots, latch block at its middle
    lt = yc - RAIL_SPAN / 2
    bx0, bx1 = w / 2 - 25.0, w / 2 + 25.0
    base -= box(bx0, bx1, lt - HOOK_W - 2.4, lt - HOOK_W - 1.2, Z_BACK_OUT - 1, Z_BACK_IN + 1)   # lower slot
    base -= box(bx0, bx1, lt + LIP_W + 0.4, lt + LIP_W + 1.6, Z_BACK_OUT - 1, Z_BACK_IN + 1)     # upper slot
    lx0, lx1 = w / 2 - 6.0, w / 2 + 6.0
    base += box(lx0, lx1, lt - HOOK_W, lt, z_tip, Z_BACK_OUT)
    lip = box(lx0, lx1, lt, lt + LIP_W, z_tip, z_lip0)
    # ramp on the lip so the flange pushes the latch aside when the case is rocked onto the rail
    ramp = Pos(w / 2, lt + LIP_W, z_tip) * Rot(45, 0, 0) * Box(lx1 - lx0 + 2, 1.5, 1.5)
    base += lip - ramp
    RAIL_PROBE_X = w / 2
    return one_solid(base)


def build_case(features: dict):
    """-> (base, cover), solids in case coordinates."""
    global RAIL_Y, Z_FRONT_IN, Z_FRONT_OUT
    w, h = features["outline_mm"]
    Z_FRONT_IN = Z_BOARD_TOP + features["max_component_height"] + FRONT_CLEAR
    Z_FRONT_OUT = Z_FRONT_IN + WALL
    RAIL_Y = h / 2
    return build_base(features), build_cover(features)


def board_to_case(shape):
    """The board STEP is exported with --drill-origin (lower-left corner), so it is already in case
    coordinates."""
    return shape


def main():
    features = json.loads((ROOT / "hw" / "out" / "board_features.json").read_text())
    base, cover = build_case(features)
    OUT.mkdir(exist_ok=True)
    export_step(base, str(OUT / "base.step"))
    export_step(cover, str(OUT / "cover.step"))
    # print orientation: base on its inside face (clip up), cover on its front face (walls up)
    export_stl(Rot(180, 0, 0) * base, str(OUT / "base.stl"))
    export_stl(Rot(180, 0, 0) * cover, str(OUT / "cover.stl"))
    print("base", round(base.volume / 1000, 1), "cm3; cover", round(cover.volume / 1000, 1), "cm3")


if __name__ == "__main__":
    main()
