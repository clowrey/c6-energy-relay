"""Simple 3D bodies (STEP) for the project-local footprints, so renders, the board STEP and the case
fit test see the real envelopes. build123d (system Python):  python -m hw.gen_3d

Coordinates match the footprints in gen_lib.py: origin = footprint origin, x right, y = -KiCad y
(KiCad's y points down, a 3D model's y up), z up from the board's top surface. Body sizes from the
datasheets (see gen_lib.py).
"""
from pathlib import Path

from build123d import Box, Cylinder, Location, Pos, export_step

OUT = Path(__file__).resolve().parent / "lib" / "c6er.3dshapes"


def box(x0, y0, x1, y1, z0, z1):
    """Axis-aligned box from KiCad-style corners (y down) -> model coordinates (y up)."""
    return Pos((x0 + x1) / 2, -(y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def pins(points, length=3.5, d=0.8):
    s = None
    for x, y in points:
        c = Location((x, -y, -length / 2)) * Cylinder(d / 2, length)
        s = c if s is None else s + c
    return s


MODELS = {
    # HF32FV-16: 18.4 x 10.2 x 15.5, centred
    "HF32FV-16": box(-9.2, -5.1, 9.2, 5.1, 0.0, 15.5) + pins([(7.62, -3.8), (7.62, 3.8), (-5.08, -3.45),
                                                             (-7.62, 3.45)]),
    # ZMPT107-1: 19 x 10 x 18.2, centred
    "ZMPT107-1": box(-9.5, -5.0, 9.5, 5.0, 0.0, 18.2) + pins([(-8.15, 3.6), (-8.15, -3.6), (8.15, 3.6),
                                                             (8.15, -3.6)]),
    # DB2ER-5.08-2P: body x -2.54..7.62, y -2.0..10.0 (mating face toward +y), 7.8 high
    "DB2ER-5.08-02P": box(-2.54, -2.0, 7.62, 10.0, 0.0, 7.8) + pins([(0, 0), (5.08, 0)], d=1.0),
    # WJ15EDGRC-3.81-4P: x -2.345..13.775, y -1.2..6.05, 9.2 high
    "WJ15EDGRC-3.81-04P": box(-2.345, -1.2, 3 * 3.81 + 2.345, 6.05, 0.0, 9.2)
    + pins([(i * 3.81, 0) for i in range(4)], d=0.8),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, shape in MODELS.items():
        export_step(shape, str(OUT / f"{name}.step"))
        print("wrote", OUT / f"{name}.step")


if __name__ == "__main__":
    main()
