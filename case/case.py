"""3D-printed DIN-rail case for the C6 energy relay board, in build123d.

    python case/case.py            # reads hw/out/board_features.json, writes case/out/*.step|stl

Three parts:
  cover  the front shell: closed front face, four walls, a pillar at each of the board's mounting
         holes (H3's is fused to the bottom wall above the board: the gap is too thin to print), and a hollow light tube
         behind the 0.6 mm LED window. Wall openings: the plug row along the bottom edge, USB-C in
         the top edge, vents.
  base   the sealed back plate: no openings except the four screw holes, so nothing (a screwdriver, the
         metal DIN rail) can reach the mains parts behind the board. A standoff rises to each mounting
         hole, a 1.4 mm rim locates the plate inside the cover's walls, and a 0.4 mm chamfered relief
         pocket in the back face gives the clip's moving latch parts running clearance while keeping
         1.8 mm of solid plastic.
  clip   the DIN-rail clip, screwed under the base: a fixed hook at the top (65 mm long, 3.5 mm wall,
         2 mm lip over the flange, five ribs behind it) and a sprung latch at the bottom. The latch
         block rides on four 1.6 mm spring beams cut in the clip plate, which bend in the plate's own
         plane, and has 3.2 mm of free travel. Two bridged straps on the outer face retain the pull
         tab in -z without supports. To take the case off the rail, pull the tab at the clip's bottom
         edge down (a screwdriver in its slot levers it).
Four screws hold everything: M3 x 16 countersunk, from the back through the clip, the base, its
standoff and the board, self-tapping into 2.8 mm pilots in the cover's pillars. The board is clamped
between the standoffs and the pillars. Nothing inside the walls sits between the board and the open
back, so the board drops straight in. The screw heads sit flush in the clip; the holes keep 6.5 mm
from mains copper, so a screw you can touch is as far from mains as the low-voltage side.
Assembly: cover face down, board in (components down) onto the pillars, base on, clip on, four screws.
Nothing opens on the front face: the status LED shows through a 0.6 mm thin window. The front face says
what each opening is (MAINS L N, RELAY 1 / 2 COM NO, CT1 / CT2 + -, USB), cut 0.4 mm deep.

Printing, PETG (the latch flexes); 0.2 mm layers, 3 walls:
  cover  on its front face (walls and LED tube up), no supports
  base   on its back face (standoffs up, chamfered relief pocket bridging short spans), no supports
  clip   on its flat face against the base (hook, latch and bridged straps up), supports under the
         hook and latch lips only; the spring beams print flat, so they bend along the layers.

Coordinates: x, y as the board (origin at its lower-left corner, y up), z = 0 at the PCB's bottom
face, +z toward the front; the same frame as `kicad-cli pcb export step --drill-origin`.
"""
from __future__ import annotations

import json
from pathlib import Path

from build123d import (Align, Axis, Box, Cone, Cylinder, FontStyle, Location, Plane, Polygon, Pos, Rectangle,
                       RectangleRounded, Rot, Text, export_step, export_stl, extrude, loft)

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
PILLAR_WALL_FUSE = 0.5        # fuse a cover pillar this close to a wall: the gap wouldn't print (H2's 0.8 mm stays
                              # open, it is the way out for the side vents behind it)
STANDOFF_D = 6.0
LED_WINDOW = 0.6
LED_WINDOW_D = 3.5            # thinned window diameter in the front face
LED_TUBE_ID = 5.0             # hollow light tube inner diameter behind the LED window
LED_TUBE_WALL = 1.2           # hollow light tube wall thickness
LED_TUBE_Z0 = 5.0             # bottom of the light tube (clear above the status LED)
LABEL_DEPTH = 0.4             # labels are cut this deep into the front face (two layers; it prints face down)
LABEL_FONT = "Arial"
LABEL_PIN, LABEL_NAME, LABEL_NOTE = 3.0, 3.2, 2.8   # font sizes: pin names, plug names, the mains rating
LABEL_GAP = 0.8               # least space between two labels in a row
LABEL_ROWS = (2.2, 6.0, 9.6)  # y of the pin names, the plug names and the mains rating, above the plug row
# plug -> (names: (text, first pin, last pin) centred over those pins; pin names left to right; pitch)
LABELS = {
    "J1": ((("MAINS", 0, 1),), ("L", "N"), 5.08),
    "J2": ((("RELAY 1", 0, 1),), ("COM", "NO"), 5.08),
    "J3": ((("RELAY 2", 0, 1),), ("COM", "NO"), 5.08),
    "J4": ((("CT1", 0, 1), ("CT2", 2, 3)), ("+", "-", "+", "-"), 3.81),
}

# TS35 rail: flanges 35 mm apart (outer edges), 1.0 mm thick
RAIL_SPAN = 35.2              # hook face to latch face
FLANGE_T = 1.0
FLANGE_GAP = FLANGE_T + 0.6   # room for the flange under each lip (1.6 mm for lips printed with supports)
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
TAB_W = 10.0                  # pull tab: from the shuttle down past the clip's bottom edge
TAB_OUT = 5.5                 # how far the tab sticks out below the case
PRY_SLOT = (5.0, 1.8)         # screwdriver slot in the tab (x, y)
TAB_BAR = 2.5                 # solid plastic below the screwdriver slot (at least 2.2 mm on every side)
BASE_RELIEF = 0.4             # shallow pocket depth in the base back face under the moving clip parts
RELIEF_MARGIN = 1.5           # margin around the moving parts and slots for the base relief pocket
STRAP_W = 4.0                 # width (y) of each retention strap bridging over the tab channel
STRAP_GAP = 0.4               # z play between the tab outer face and the retention strap
STRAP_T = 1.2                 # retention strap thickness (STRAP_GAP + STRAP_T = 1.6 mm past Z_CLIP_OUT)
STRAP_POST = 3.0              # anchor post width (x) on the fixed plate beside the tab channel
STRAP_YS = (1.0, 11.0)        # y centres of the two retention straps over the tab channel

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


def chamfer_pocket(x0, x1, y0, y1, z_bot, z_top):
    """Rectangular pocket tool with 45-degree walls sloping outward from (x0..x1, y0..y1) at z_top
    down to z_bot."""
    dz = z_top - z_bot
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sk_bot = Plane.XY.offset(z_bot) * Pos(cx, cy) * Rectangle(x1 - x0 + 2 * dz, y1 - y0 + 2 * dz)
    sk_top = Plane.XY.offset(z_top) * Pos(cx, cy) * Rectangle(x1 - x0, y1 - y0)
    return one_solid(loft([sk_bot, sk_top], ruled=True))


def one_solid(shape):
    """Boolean results sometimes come back as a ShapeList; the case parts are single solids."""
    solids = shape.solids() if hasattr(shape, "solids") else list(shape)
    assert len(solids) == 1, f"expected one solid, got {len(solids)}"
    return solids[0]


def _text(s, size):
    return Text(s, font_size=size, font=LABEL_FONT, font_style=FontStyle.BOLD)


def lid_labels(f):
    """-> [(text, x, y, font size, width)]: what each opening is, on the front face beside it. Pin names sit
    over their pins; two that would touch are pushed apart by the same amount."""
    w, h = f["outline_mm"]
    out = []
    for c in f["connectors"]:
        if c["ref"] not in LABELS:
            continue
        names, pins, pitch = LABELS[c["ref"]]
        xs = [c["x"] + i * pitch for i in range(len(pins))]
        ws = [_text(p, LABEL_PIN).bounding_box().size.X for p in pins]
        for _ in range(8):
            for i in range(len(xs) - 1):
                lack = LABEL_GAP - ((xs[i + 1] - ws[i + 1] / 2) - (xs[i] + ws[i] / 2))
                if lack > 0:
                    xs[i] -= lack / 2
                    xs[i + 1] += lack / 2
        out += [(p, x, LABEL_ROWS[0], LABEL_PIN, wd) for p, x, wd in zip(pins, xs, ws)]
        for name, a, b in names:
            out.append((name, c["x"] + (a + b) / 2 * pitch, LABEL_ROWS[1], LABEL_NAME, None))
        if c["ref"] == "J1":
            out.append(("100-240V~", c["x"] + pitch / 2, LABEL_ROWS[2], LABEL_NOTE, None))
    usb = next(c for c in f["connectors"] if c["kind"] == "usbc")
    out.append(("USB", usb["x"], h - LABEL_ROWS[0], LABEL_NAME, None))
    qwiic = next((c for c in f["connectors"] if c["kind"] == "qwiic"), None)
    if qwiic:
        out.append(("QWIIC", qwiic["x"], h - LABEL_ROWS[0], LABEL_NAME, None))
    return [(s, x, y, size, wd if wd is not None else _text(s, size).bounding_box().size.X)
            for s, x, y, size, wd in out]


def label_solids(f):
    """The labels as cutting tools: LABEL_DEPTH into the front face, read from the front."""
    return [extrude(Plane.XY.offset(Z_FRONT_OUT - LABEL_DEPTH) * Pos(x, y) * _text(s, size), LABEL_DEPTH + 0.5)
            for s, x, y, size, _ in lid_labels(f)]


def build_cover(f):
    w, h = f["outline_mm"]
    x0, x1, y0, y1 = -GAP - WALL, w + GAP + WALL, -GAP - WALL, h + GAP + WALL
    shell = slab(x0, x1, y0, y1, Z_BACK_IN, Z_FRONT_OUT, CORNER_R)
    inner = slab(x0 + WALL, x1 - WALL, y0 + WALL, y1 - WALL, Z_BACK_IN - 1, Z_FRONT_IN, max(CORNER_R - WALL, 0.5))
    cover = shell - inner
    # pillars at the board's mounting holes, fused to any inner wall closer than PILLAR_WALL_FUSE for
    # z >= Z_BOARD_TOP. Nothing stands inside the walls behind the board's seat, so it drops in from the back
    r = PILLAR_D / 2
    x_in0, x_in1, y_in0, y_in1 = -GAP, w + GAP, -GAP, h + GAP
    for x, y, _ in f["holes"]:
        cover += cyl(x, y, PILLAR_D, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
        if (x - r) - x_in0 < PILLAR_WALL_FUSE:
            cover += box(x_in0 - 0.5, x, y - r, y + r, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
        if x_in1 - (x + r) < PILLAR_WALL_FUSE:
            cover += box(x, x_in1 + 0.5, y - r, y + r, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
        if (y - r) - y_in0 < PILLAR_WALL_FUSE:
            cover += box(x - r, x + r, y_in0 - 0.5, y, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
        if y_in1 - (y + r) < PILLAR_WALL_FUSE:
            cover += box(x - r, x + r, y, y_in1 + 0.5, Z_BOARD_TOP, Z_FRONT_IN + 0.5)
    # hollow LED light tube from the front face inner side down to LED_TUBE_Z0, fused to the top wall
    lx, ly = f["led"]
    cover += cyl(lx, ly, LED_TUBE_ID + 2 * LED_TUBE_WALL, LED_TUBE_Z0, Z_FRONT_IN + 0.5)
    # one_solid: a boolean can return a ShapeList, and `ShapeList -= shape` is a silent no-op (list
    # difference), which once left every opening below uncut
    cover = one_solid(cover)
    for x, y, _ in f["holes"]:
        cover -= cyl(x, y, M3_PILOT_D, Z_BOARD_TOP - 0.1, Z_BOARD_TOP + M3_PILOT_DEPTH)
        cover -= cyl(x, y, M3_LEAD_IN_D, Z_BOARD_TOP - 0.1, Z_BOARD_TOP + M3_LEAD_IN)
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
        vx = hot[0] + 3.0 + i * 3.0
        cover -= box(vx, vx + 1.6, h + GAP - 0.5, y1 + 1, 5.0, Z_FRONT_IN - 3.0)
    for i in range(5):                               # above relay 2's contacts, not beside them
        vy = 31.0 + i * 3.2
        cover -= box(w + GAP - 0.5, x1 + 1, vy, vy + 1.6, 4.0, Z_FRONT_IN - 3.0)
    # LED tube bore and 0.6 mm thinned window in the front face
    cover -= cyl(lx, ly, LED_TUBE_ID, LED_TUBE_Z0 - 0.5, Z_FRONT_IN)
    cover -= cyl(lx, ly, LED_WINDOW_D, Z_FRONT_IN - 0.1, Z_FRONT_OUT - LED_WINDOW)
    cover = one_solid(cover)
    for label in label_solids(f):
        cover = one_solid(cover - label)
    return cover


def build_base(f):
    """Sealed back plate: standoffs up to the board, a locating rim inside the cover's walls, a
    0.4 mm chamfered relief pocket under the clip's moving parts, and only the four screw holes
    through it."""
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
    base = one_solid(base)
    for x, y, _ in f["holes"]:
        base -= cyl(x, y, M3_CLEAR_D, Z_BACK_OUT - 1, 0.1)
    # 0.4 mm back-face relief pocket over the swept area of the clip's moving parts + margin;
    # T-shaped with 45-degree chamfered walls so the base prints flat on its back face with short bridges
    g = latch_geometry(w)
    cx = w / 2
    z_rel = Z_BACK_OUT + BASE_RELIEF
    base -= chamfer_pocket(
        BEAM_X0 - RELIEF_MARGIN, BEAM_X1 + RELIEF_MARGIN,
        g["cut_lo"] - RELIEF_MARGIN, g["cut_hi"] + RELIEF_MARGIN,
        Z_BACK_OUT - 0.5, z_rel,
    )
    base -= chamfer_pocket(
        cx - TAB_W / 2 - SLOT_PLAY - RELIEF_MARGIN, cx + TAB_W / 2 + SLOT_PLAY + RELIEF_MARGIN,
        y0 - 1.0, g["cut_lo"] + 1.0,
        Z_BACK_OUT - 0.5, z_rel,
    )
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
    clip = one_solid(clip)

    # latch: cut a band through the plate, then put back the shuttle, the four beams and the pull tab
    g = latch_geometry(w)
    cx = w / 2
    ch_x0, ch_x1 = cx - TAB_W / 2 - SLOT_PLAY, cx + TAB_W / 2 + SLOT_PLAY
    clip -= box(BEAM_X0, BEAM_X1, g["cut_lo"], g["cut_hi"], Z_CLIP_OUT - 1, Z_BACK_OUT + 1)
    clip -= box(ch_x0, ch_x1, y0 - 1, g["cut_lo"] + 0.1,
                Z_CLIP_OUT - 1, Z_BACK_OUT + 1)                       # channel for the tab
    # the latch pieces float in the cut until the beams join them, so fuse them all in one go
    # (adding them one by one would leave a ShapeList, and `ShapeList += s` just appends)
    adds = [box(g["lx0"], g["lx1"], g["s_lo"], g["s_hi"], Z_CLIP_OUT, Z_BACK_OUT)]   # shuttle
    for by0 in (g["s_hi"] - BEAM_H, g["s_hi"] - 2 * BEAM_H - BEAM_GAP):             # two beams a side
        adds.append(box(BEAM_X0 - 0.5, BEAM_X1 + 0.5, by0, by0 + BEAM_H, Z_CLIP_OUT, Z_BACK_OUT))
    tab = box(cx - TAB_W / 2, cx + TAB_W / 2, y0 - TAB_OUT, g["s_lo"] + 0.1, Z_CLIP_OUT, Z_BACK_OUT)
    px, py = PRY_SLOT
    slot_y0 = y0 - TAB_OUT + TAB_BAR
    tab -= box(cx - px / 2, cx + px / 2, slot_y0, slot_y0 + py, Z_CLIP_OUT - 1, Z_BACK_OUT + 1)
    adds.append(one_solid(tab))
    # latch block on the shuttle: wall + lip over the lower flange, its underside one 45-degree ramp so
    # the flange pushes the block down when the case is rocked onto the rail
    lt = g["lt"]
    adds.append(box(g["lx0"], g["lx1"], lt - HOOK_W, lt, z_tip, Z_CLIP_OUT + 0.1))
    lip = box(g["lx0"], g["lx1"], lt, lt + LIP_W, z_tip, z_lip0)
    ramp = Pos(cx, lt + LIP_W, z_tip) * Rot(45, 0, 0) * Box(LATCH_W + 2, LIP_W * 2 ** 0.5, LIP_W * 2 ** 0.5)
    adds.append(one_solid(lip - ramp))
    # -z retention straps: two small bridges across the tab channel on the clip's outer face,
    # anchored on the fixed plate on both sides with STRAP_GAP z-play above the tab (no supports)
    z_strap_in = Z_CLIP_OUT - STRAP_GAP
    z_strap_out = z_strap_in - STRAP_T
    for sy in STRAP_YS:
        sy0, sy1 = sy - STRAP_W / 2, sy + STRAP_W / 2
        strap = box(ch_x0 - STRAP_POST, ch_x1 + STRAP_POST, sy0, sy1, z_strap_out, Z_CLIP_OUT + 0.1)
        strap -= box(ch_x0, ch_x1, sy0 - 1, sy1 + 1, z_strap_in, Z_CLIP_OUT + 1)
        adds.append(one_solid(strap))
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
    global HOOK_GUSSETS, BEAM_X0, BEAM_X1, RAIL_Y, Z_FRONT_IN, Z_FRONT_OUT
    w, h = features["outline_mm"]
    HOOK_GUSSETS = tuple(w / 2 + d for d in (-30.0, -15.0, 0.0, 15.0, 30.0))
    BEAM_X0, BEAM_X1 = 1.0, w - 1.0
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
