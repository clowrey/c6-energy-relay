"""3D-printed DIN-rail case for the C6 energy relay board, in build123d.

    python case/case.py            # reads hw/out/board_features.json, writes case/out/*.step|stl

Three parts:
  cover  the front shell: closed front face, four walls, a pillar at each of the board's mounting
         holes. Wall openings: the plug row along the bottom edge, USB-C in the top edge, vents.
  base   the sealed back plate: no openings except the four screw holes, so nothing (a screwdriver, the
         metal DIN rail) can reach the mains parts behind the board. A standoff rises to each mounting
         hole, and a 1.4 mm rim locates the plate inside the cover's walls.
  clip   the DIN-rail clip, screwed under the base: a fixed hook at the top (65 mm long, 3.5 mm wall,
         2 mm lip over the flange, five ribs behind it) and a sprung latch at the bottom. The latch
         block rides on four 1.6 mm spring beams cut in the clip plate, which bend in the plate's own
         plane, and has 3.2 mm of free travel. To take the case off the rail, pull the tab at the
         clip's bottom edge down (a screwdriver in its slot levers it).
Four screws hold everything: M3 x 16 countersunk, from the back through the clip, the base, its
standoff and the board, self-tapping into 2.8 mm pilots in the cover's pillars. The board is clamped
between the standoffs and the pillars. Nothing inside the walls sits between the board and the open
back, so the board drops straight in. The screw heads sit flush in the clip; the holes keep 6.5 mm
from mains copper, so a screw you can touch is as far from mains as the low-voltage side.
Assembly: cover face down, board in (components down) onto the pillars, base on, clip on, four screws.
Nothing opens on the front face: the status LED shows through a 0.6 mm thin window.

Printing, no supports, PETG (the latch flexes); 0.2 mm layers, 3 walls:
  cover  on its front face (walls up)
  base   on its back face (standoffs up)
  clip   on its flat face, the one against the base (hook and latch up); the spring beams print flat,
         so they bend along the layers, never across them.

Coordinates: x, y as the board (origin at its lower-left corner, y up), z = 0 at the PCB's bottom
face, +z toward the front; the same frame as `kicad-cli pcb export step --drill-origin`.
"""
from __future__ import annotations

import json
from pathlib import Path

from build123d import (Align, Axis, Box, Cone, Cylinder, Location, Plane, Polygon, Pos, Rot,
                       RectangleRounded, export_step, export_stl, extrude)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"

WALL = 2.2
GAP = 0.8                     # board edge to the inside of the wall
CORNER_R = 3.0
Z_BOARD_TOP = 1.6
Z_BACK_IN = -4.0              # room behind the board for the through-hole leads
Z_BACK_OUT = Z_BACK_IN - WALL
RIM_H, RIM_W, RIM_GAP = 1.4, 1.2, 0.2   # base rim inside the cover walls (height, width, play)
CLIP_T = 2.4                  # clip plate thickness
Z_CLIP_OUT = Z_BACK_OUT - CLIP_T
FRONT_CLEAR = 1.5             # above the tallest part
M3_PILOT_D, M3_PILOT_DEPTH = 2.8, 8.0
M3_LEAD_IN_D, M3_LEAD_IN = 3.4, 0.8
M3_CLEAR_D = 3.4
CSK_D = 6.6                   # 90 degree countersink at the clip's back face (M3 flat head: 5.5-6.0 mm)
SCREW_LEN = 16.0              # M3 x 16 countersunk, overall length
PILLAR_D = 6.0
STANDOFF_D = 6.0
LED_WINDOW = 0.6

# TS35 rail: flanges 35 mm apart (outer edges), 1.0 mm thick
RAIL_SPAN = 35.2              # hook face to latch face
FLANGE_T = 1.0
FLANGE_GAP = FLANGE_T + 0.4   # room for the flange under each lip (a printed lip may droop a little)
LIP_T, LIP_W = 2.2, 2.0       # lip thickness (z) and reach over the flange (y; the flange is 5 mm)
HOOK_W = 3.5                  # hook / latch wall thickness (y)
HOOK_LEN = 65.0               # hook length along the rail, centred; ends clear of H1's screw head
HOOK_GUSSETS = (10.0, 25.0, 40.0, 55.0, 70.0)   # x of the ribs behind the hook
GUSSET_T, GUSSET_L = 2.0, 4.0
LATCH_W = 20.0                # latch block width along the rail
LATCH_TRAVEL = LIP_W + 0.4    # the block moves this far down to clear the flange
SHUTTLE_D = 4.4               # depth (y) of the clip plate under the latch block that moves with it
BEAM_H = 1.6                  # spring beam depth in the bending direction (y)
BEAM_GAP = 1.2                # slot between the two beams on each side
BEAM_X0, BEAM_X1 = 1.0, 79.0  # beam anchors (x); each beam is (span - LATCH_W) / 2 = 29 mm long
SLOT_PLAY = 0.8               # free gap beyond the travel, and above the shuttle
TAB_W = 6.0                   # pull tab: from the shuttle down past the clip's bottom edge
TAB_OUT = 2.0                 # how far the tab sticks out below the case
PRY_SLOT = (4.0, 1.4)         # screwdriver slot in the tab (x, y)

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


def build_cover(f):
    w, h = f["outline_mm"]
    x0, x1, y0, y1 = -GAP - WALL, w + GAP + WALL, -GAP - WALL, h + GAP + WALL
    shell = slab(x0, x1, y0, y1, Z_BACK_IN, Z_FRONT_OUT, CORNER_R)
    inner = slab(x0 + WALL, x1 - WALL, y0 + WALL, y1 - WALL, Z_BACK_IN - 1, Z_FRONT_IN, max(CORNER_R - WALL, 0.5))
    cover = shell - inner
    # pillars at the board's mounting holes, pilot from the board side. Nothing else stands inside the
    # walls behind the board's seat, so the board drops in from the back
    for x, y, _ in f["holes"]:
        cover += cyl(x, y, PILLAR_D, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
        cover -= cyl(x, y, M3_PILOT_D, Z_BOARD_TOP - 0.1, Z_BOARD_TOP + M3_PILOT_DEPTH)
        cover -= cyl(x, y, M3_LEAD_IN_D, Z_BOARD_TOP - 0.1, Z_BOARD_TOP + M3_LEAD_IN)
    # one_solid: a boolean can return a ShapeList, and `ShapeList -= shape` is a silent no-op (list
    # difference), which once left every opening below uncut
    cover = one_solid(cover)
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
    """Sealed back plate: standoffs up to the board, a locating rim inside the cover's walls, and
    only the four screw holes through it."""
    w, h = f["outline_mm"]
    x0, x1, y0, y1 = -GAP - WALL, w + GAP + WALL, -GAP - WALL, h + GAP + WALL
    base = slab(x0, x1, y0, y1, Z_BACK_OUT, Z_BACK_IN, CORNER_R)
    # rim just inside the cover's walls: locates the plate, and lengthens any path through the seam
    rx0, rx1, ry0, ry1 = -GAP + RIM_GAP, w + GAP - RIM_GAP, -GAP + RIM_GAP, h + GAP - RIM_GAP
    rim = slab(rx0, rx1, ry0, ry1, Z_BACK_IN - 0.1, Z_BACK_IN + RIM_H, 0.6)
    rim -= slab(rx0 + RIM_W, rx1 - RIM_W, ry0 + RIM_W, ry1 - RIM_W, Z_BACK_IN - 1, Z_BACK_IN + RIM_H + 1, 0.5)
    base += rim
    for x, y, _ in f["holes"]:
        base += cyl(x, y, STANDOFF_D, Z_BACK_IN - 0.1, 0.0)
    for x, y, _ in f["holes"]:
        base -= cyl(x, y, M3_CLEAR_D, Z_BACK_OUT - 1, 0.1)
    return one_solid(base)


def latch_geometry(w):
    """-> dict of the latch's y levels and x extents (case coordinates)."""
    lt = RAIL_Y - RAIL_SPAN / 2                       # latch catching face
    s_hi = lt                                         # shuttle (the plate under the block) top ...
    s_lo = lt - SHUTTLE_D                             # ... and bottom
    return {"lt": lt, "s_hi": s_hi, "s_lo": s_lo,
            "cut_lo": s_lo - LATCH_TRAVEL - SLOT_PLAY, "cut_hi": s_hi + SLOT_PLAY,
            "lx0": w / 2 - LATCH_W / 2, "lx1": w / 2 + LATCH_W / 2}


def build_clip(f):
    """DIN clip plate under the base: fixed hook (top), latch on in-plane spring beams (bottom)."""
    global RAIL_PROBE_X
    w, h = f["outline_mm"]
    x0, x1, y0, y1 = -GAP - WALL, w + GAP + WALL, -GAP - WALL, h + GAP + WALL
    clip = slab(x0, x1, y0, y1, Z_CLIP_OUT, Z_BACK_OUT, CORNER_R)
    z_lip0 = Z_CLIP_OUT - FLANGE_GAP                 # lip's face toward the rail flange
    z_tip = z_lip0 - LIP_T

    # fixed hook at the top: wall + lip reaching down over the upper flange
    ht = RAIL_Y + RAIL_SPAN / 2
    hx0, hx1 = w / 2 - HOOK_LEN / 2, w / 2 + HOOK_LEN / 2
    clip += box(hx0, hx1, ht, ht + HOOK_W, z_tip, Z_CLIP_OUT + 0.1)
    clip += box(hx0, hx1, ht - LIP_W, ht, z_tip, z_lip0)
    # triangular ribs behind the hook wall, down to the plate: the hook can't fold back off the rail
    yw = ht + HOOK_W
    for gx in HOOK_GUSSETS:
        tri = Polygon((yw - 0.1, z_tip), (yw - 0.1, Z_CLIP_OUT + 0.1), (yw + GUSSET_L, Z_CLIP_OUT + 0.1), align=None)
        clip += extrude(Plane.YZ.offset(gx) * tri, GUSSET_T / 2, both=True)

    # latch: cut a band through the plate, then put back the shuttle, the four beams and the pull tab
    g = latch_geometry(w)
    cx = w / 2
    clip -= box(BEAM_X0, BEAM_X1, g["cut_lo"], g["cut_hi"], Z_CLIP_OUT - 1, Z_BACK_OUT + 1)
    clip -= box(cx - TAB_W / 2 - SLOT_PLAY, cx + TAB_W / 2 + SLOT_PLAY, y0 - 1, g["cut_lo"] + 0.1,
                Z_CLIP_OUT - 1, Z_BACK_OUT + 1)                       # channel for the tab
    # the latch pieces float in the cut until the beams join them, so fuse them all in one go
    # (adding them one by one would leave a ShapeList, and `ShapeList += s` just appends)
    adds = [box(g["lx0"], g["lx1"], g["s_lo"], g["s_hi"], Z_CLIP_OUT, Z_BACK_OUT)]   # shuttle
    for by0 in (g["s_hi"] - BEAM_H, g["s_hi"] - 2 * BEAM_H - BEAM_GAP):             # two beams a side
        adds.append(box(BEAM_X0 - 0.5, BEAM_X1 + 0.5, by0, by0 + BEAM_H, Z_CLIP_OUT, Z_BACK_OUT))
    tab = box(cx - TAB_W / 2, cx + TAB_W / 2, y0 - TAB_OUT, g["s_lo"] + 0.1, Z_CLIP_OUT, Z_BACK_OUT)
    px, py = PRY_SLOT
    tab -= box(cx - px / 2, cx + px / 2, y0 - TAB_OUT + 0.6, y0 - TAB_OUT + 0.6 + py, Z_CLIP_OUT - 1, Z_BACK_OUT + 1)
    adds.append(one_solid(tab))
    # latch block on the shuttle: wall + lip over the lower flange, its underside one 45-degree ramp so
    # the flange pushes the block down when the case is rocked onto the rail
    lt = g["lt"]
    adds.append(box(g["lx0"], g["lx1"], lt - HOOK_W, lt, z_tip, Z_CLIP_OUT + 0.1))
    lip = box(g["lx0"], g["lx1"], lt, lt + LIP_W, z_tip, z_lip0)
    ramp = Pos(cx, lt + LIP_W, z_tip) * Rot(45, 0, 0) * Box(LATCH_W + 2, LIP_W * 2 ** 0.5, LIP_W * 2 ** 0.5)
    adds.append(one_solid(lip - ramp))
    clip = one_solid(one_solid(clip).fuse(*adds))

    # the case screws: clearance hole, flush countersink, and a clear path behind it for the head
    for x, y, _ in f["holes"]:
        clip -= cyl(x, y, M3_CLEAR_D, Z_CLIP_OUT - 1, Z_BACK_OUT + 1)
        clip -= Pos(x, y, Z_CLIP_OUT) * Cone(CSK_D / 2, M3_CLEAR_D / 2, (CSK_D - M3_CLEAR_D) / 2,
                                             align=(Align.CENTER, Align.CENTER, Align.MIN))
        clip -= cyl(x, y, CSK_D + 0.4, z_tip - 1, Z_CLIP_OUT)
    RAIL_PROBE_X = w / 2
    return one_solid(clip)


def build_case(features: dict):
    """-> (base, cover, clip), solids in case coordinates."""
    global RAIL_Y, Z_FRONT_IN, Z_FRONT_OUT
    w, h = features["outline_mm"]
    Z_FRONT_IN = Z_BOARD_TOP + features["max_component_height"] + FRONT_CLEAR
    Z_FRONT_OUT = Z_FRONT_IN + WALL
    RAIL_Y = h / 2
    return build_base(features), build_cover(features), build_clip(features)


def board_to_case(shape):
    """The board STEP is exported with --drill-origin (lower-left corner), so it is already in case
    coordinates."""
    return shape


def main():
    features = json.loads((ROOT / "hw" / "out" / "board_features.json").read_text())
    base, cover, clip = build_case(features)
    OUT.mkdir(exist_ok=True)
    for name, part in (("base", base), ("cover", cover), ("clip", clip)):
        export_step(part, str(OUT / f"{name}.step"))
    # print orientation (see the docstring): base as is, cover and clip flipped onto their flat faces
    export_stl(base, str(OUT / "base.stl"))
    export_stl(Rot(180, 0, 0) * cover, str(OUT / "cover.stl"))
    export_stl(Rot(180, 0, 0) * clip, str(OUT / "clip.stl"))
    print(", ".join(f"{n} {round(p.volume / 1000, 1)} cm3" for n, p in (("base", base), ("cover", cover), ("clip", clip))))


if __name__ == "__main__":
    main()
