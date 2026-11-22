"""Simple 3D bodies (STEP) for the project-local footprints, so renders, the board STEP and the case
fit test see the real envelopes. build123d (system Python):  python -m hw.gen_3d

Coordinates match the footprints in gen_lib.py: origin = footprint origin, x right, y = -KiCad y
(KiCad's y points down, a 3D model's y up), z up from the board's top surface. Body sizes from the
datasheets (see gen_lib.py).
"""
from pathlib import Path

from build123d import Axis, Box, Color, Compound, Cylinder, Location, Pos, export_step, fillet

OUT = Path(__file__).resolve().parent / "lib" / "c6er.3dshapes"

BLACK = Color(0.08, 0.08, 0.09)
GREEN = Color(0.13, 0.45, 0.25)      # pluggable terminal housings
METAL = Color(0.78, 0.78, 0.74)
WHITE = Color(0.92, 0.91, 0.88)      # ceramic


def box(x0, y0, x1, y1, z0, z1):
    """Axis-aligned box from KiCad-style corners (y down) -> model coordinates (y up)."""
    return Pos((x0 + x1) / 2, -(y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def rounded(shape, r):
    """Round the vertical edges and the top edges."""
    top = shape.edges().group_by(Axis.Z)[-1]
    return fillet(shape.edges().filter_by(Axis.Z) + top, r)


def pins(points, length=3.5, d=0.8):
    s = None
    for x, y in points:
        c = Location((x, -y, -length / 2)) * Cylinder(d / 2, length)
        s = c if s is None else s + c
    return s


def part(body, colour, metal=None):
    """Body and pins as one compound of coloured solids (KiCad reads STEP colours)."""
    children = []
    for shape, c in ((body, colour), (metal, METAL)):
        if shape is None:
            continue
        for solid in shape.solids():
            solid.color = c
            children.append(solid)
    return Compound(children=children)


def socket_header(x0, y0, x1, y1, h, pitch, n, mouth):
    """Pluggable-terminal header: housing open toward +y (the board edge), contacts inside."""
    body = rounded(box(x0, y0, x1, y1, 0.0, h), 0.4)
    cx0, cx1, depth = x0 + mouth, x1 - mouth, (y1 - y0) * 0.55
    body = body - box(cx0, y1 - depth, cx1, y1 + 0.1, 1.0, h - 1.2)
    metal = pins([(i * pitch, 0) for i in range(n)], d=1.0 if pitch > 4 else 0.8)
    for i in range(n):
        metal += box(i * pitch - 0.5, y1 - depth, i * pitch + 0.5, y1 - 1.0, (h - 0.2) / 2 - 0.5, (h - 0.2) / 2 + 0.5)
    return part(body, GREEN, metal)


MODELS = {
    # HF32FV-16: 18.4 x 10.2 x 15.5, centred
    "HF32FV-16": part(rounded(box(-9.2, -5.1, 9.2, 5.1, 0.0, 15.5), 0.6), BLACK,
                      pins([(7.62, -3.8), (7.62, 3.8), (-5.08, -3.45), (-7.62, 3.45)])),
    # ZMPT107-1: 19 x 10 x 18.2, centred
    "ZMPT107-1": part(rounded(box(-9.5, -5.0, 9.5, 5.0, 0.0, 18.2), 0.6), BLACK,
                      pins([(-8.15, 3.6), (-8.15, -3.6), (8.15, 3.6), (8.15, -3.6)])),
    # DB2ER-5.08-2P: body x -2.54..7.62, y -2.0..10.0 (mating face toward +y), 7.8 high
    "DB2ER-5.08-02P": socket_header(-2.54, -2.0, 7.62, 10.0, 7.8, 5.08, 2, 0.8),
    # WJ15EDGRC-3.81-4P: x -2.345..13.775, y -1.2..6.05, 9.2 high
    "WJ15EDGRC-3.81-04P": socket_header(-2.345, -1.2, 3 * 3.81 + 2.345, 6.05, 9.2, 3.81, 4, 0.7),
    # ceramic SMD fuse 10.5 x 3.2 x 3.2 with 2 mm metal end caps
    "Fuse_SMD_10.1x3.1": part(box(-3.2, -1.5, 3.2, 1.5, 0.1, 3.1), WHITE,
                             box(-5.25, -1.6, -3.2, 1.6, 0.0, 3.2) + box(3.2, -1.6, 5.25, 1.6, 0.0, 3.2)),
    # stock footprints whose KiCad model isn't installed everywhere (gen_pcb.py points them here)
    # ESP32-C6-MINI-1: 13.2 x 16.6 x 2.4 module, antenna end toward KiCad -y; shield over the rest
    "ESP32-C6-MINI-1": part(box(-6.6, -11.0, 6.6, 5.6, 0.0, 0.8), GREEN,
                            box(-6.1, -4.7, 6.1, 5.1, 0.8, 2.4)),
    # TS-1187A: 5.1 x 5.1 x 1.5 tact switch with a round actuator
    "TS-1187A": part(box(-2.55, -2.55, 2.55, 2.55, 0.0, 1.2), BLACK,
                     Pos(0, 0, 1.35) * Cylinder(1.3, 0.3)),
    # HRO TYPE-C-31-M-12: 8.94 x 7.3 x 3.26 receptacle shell, mouth toward KiCad +y
    "USB-C-HRO-TYPE-C-31-M-12": part(None, BLACK, box(-4.47, -3.65, 4.47, 3.65, 0.0, 3.26)),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, shape in MODELS.items():
        export_step(shape, str(OUT / f"{name}.step"))
        print("wrote", OUT / f"{name}.step")


if __name__ == "__main__":
    main()
