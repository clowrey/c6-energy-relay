"""Write the project-local KiCad library hw/lib (symbols c6er.kicad_sym, footprints c6er.pretty).

Run with KiCad's Python:  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" hw/gen_lib.py

Dimensions are from the datasheets in hw/datasheets (fetched by hw/tools/fetch_datasheets.py):
  HF32FV-16      Hongfa, 18.4 x 10.2 x 15.5, coil pins 7.6 apart, COM/NO blades 12.7 / 15.24 from the coil
                 row (bottom-view drawing mirrored to top view here)
  ZMPT107-1      19 x 10 x 18.2, pins 0.8 round, 16.3 x 7.2 grid
  DB2ER-5.08     Dorabo right-angle pluggable header, drill 1.7, body 12 deep, pins 2.0 from the back
  WJ15EDGRC-3.81 Kangnex right-angle pluggable header, drill 1.4, body 7.25 deep, pins 1.2 from the back
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
LIB = HERE / "lib"
PRETTY = LIB / "c6er.pretty"
SYM = LIB / "c6er.kicad_sym"


# ----------------------------------------------------------------------------------------------
# symbols (written as S-expressions)
# ----------------------------------------------------------------------------------------------
def _prop(name, value, x, y, hide=False):
    h = " (hide yes)" if hide else ""
    return (f'\t\t(property "{name}" "{value}" (at {x} {y} 0)\n'
            f'\t\t\t(effects (font (size 1.27 1.27)){h})\n\t\t)\n')


def _pin(num, name, kind, x, y, angle, length=2.54):
    return (f'\t\t\t(pin {kind} line (at {x} {y} {angle}) (length {length})\n'
            f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)\n')


def _symbol(name, ref, value, desc, footprint, body, pins, graphics="", show_pin_names=True):
    (x0, y0, x1, y1) = body
    s = f'\t(symbol "{name}"\n'
    if not show_pin_names:
        s += "\t\t(pin_names (hide yes))\n"
    s += "\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)\n"
    s += _prop("Reference", ref, x0, y1 + 1.27)
    s += _prop("Value", value, x0, y0 - 1.27)
    s += _prop("Footprint", footprint, 0, 0, hide=True)
    s += _prop("Datasheet", "", 0, 0, hide=True)
    s += _prop("Description", desc, 0, 0, hide=True)
    s += f'\t\t(symbol "{name}_0_1"\n'
    s += (f"\t\t\t(rectangle (start {x0} {y0}) (end {x1} {y1})\n"
          "\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background))\n\t\t\t)\n")
    s += graphics
    s += "\t\t)\n"
    s += f'\t\t(symbol "{name}_1_1"\n'
    for p in pins:
        s += _pin(*p)
    s += "\t\t)\n\t\t(embedded_fonts no)\n\t)\n"
    return s


def _poly(points, width=0.254):
    pts = " ".join(f"(xy {x} {y})" for x, y in points)
    return (f"\t\t\t(polyline (pts {pts})\n"
            f"\t\t\t\t(stroke (width {width}) (type default)) (fill (type none))\n\t\t\t)\n")


def symbols() -> str:
    out = ['(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "c6er_gen_lib")\n\t(generator_version "10.0")\n']
    # BL0939, SOP-16 (datasheet pin table "管脚描述（SOP16L）")
    L, R = -12.7, 12.7
    pins = [
        ("1", "VDD", "power_in", 0, 15.24, 270),
        ("8", "GND", "power_in", 0, -15.24, 90),
        ("3", "IP1", "input", L, 7.62, 0), ("4", "IN1", "input", L, 5.08, 0),
        ("5", "IP2", "input", L, 0, 0), ("6", "IN2", "input", L, -2.54, 0),
        ("7", "VP", "input", L, -7.62, 0), ("2", "VT", "input", L, -10.16, 0),
        ("14", "RX", "input", R, 7.62, 180), ("15", "TX", "output", R, 5.08, 180),
        ("12", "SEL", "input", R, 2.54, 180), ("13", "SCLK", "input", R, 0, 180),
        ("11", "CF", "output", R, -2.54, 180), ("9", "ZX", "output", R, -5.08, 180),
        ("10", "I_LEAK", "output", R, -7.62, 180), ("16", "VPP", "no_connect", R, -10.16, 180),
    ]
    out.append(_symbol("BL0939", "U", "BL0939", "Belling BL0939 2-channel energy metering IC, UART/SPI",
                       "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", (-10.16, -12.7, 10.16, 12.7), pins))

    # ZMPT107-1: 1* / 2 primary, 3* / 4 secondary ("*" = same polarity)
    g = ""
    for cx in (-1.27, 1.27):
        g += _poly([(cx, -3.81), (cx, 3.81)])
    pins = [("1", "P1", "passive", -7.62, 2.54, 0), ("2", "P2", "passive", -7.62, -2.54, 0),
            ("3", "S1", "passive", 7.62, 2.54, 180), ("4", "S2", "passive", 7.62, -2.54, 180)]
    out.append(_symbol("ZMPT107-1", "T", "ZMPT107-1", "2mA:2mA current-type voltage transformer, 4 kV isolation",
                       "c6er:ZMPT107-1", (-5.08, -5.08, 5.08, 5.08), pins, g))

    # HF32FV-16: 1/2 coil, 3 COM, 4 NO
    g = (_poly([(-5.08, -1.27), (-2.54, -1.27), (-2.54, 1.27), (-5.08, 1.27), (-5.08, -1.27)])
         + _poly([(-3.81, -5.08), (-3.81, -1.27)]) + _poly([(-3.81, 1.27), (-3.81, 5.08)])
         + _poly([(3.81, -5.08), (3.81, -1.27), (5.08, 2.54)]) + _poly([(5.08, 5.08), (5.08, 3.81)])
         + _poly([(-2.54, 0), (-1.27, 0), (0, 0), (1.27, 0), (4.0, 0.0)], 0.1524))
    pins = [("1", "A1", "passive", -3.81, 7.62, 270), ("2", "A2", "passive", -3.81, -7.62, 90),
            ("3", "COM", "passive", 3.81, -7.62, 90), ("4", "NO", "passive", 5.08, 7.62, 270)]
    out.append(_symbol("HF32FV-16", "K", "HF32FV-16", "Hongfa HF32FV-16 16 A SPST-NO relay, 4 kV coil-contact",
                       "c6er:HF32FV-16", (-6.35, -5.08, 6.35, 5.08), pins, g, show_pin_names=False))
    out.append(")\n")
    return "".join(out)


# ----------------------------------------------------------------------------------------------
# footprints (built with pcbnew, saved with KiCad's own writer)
# ----------------------------------------------------------------------------------------------
MM = pcbnew.FromMM


def _v(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def _new_fp(name, descr):
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID("c6er", name))
    fp.SetLibDescription(descr)
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE)
    fp.Reference().SetText("REF**")
    fp.Value().SetText(name)
    fp.Value().SetLayer(pcbnew.F_Fab)
    return fp


def _pad(fp, num, x, y, size, drill, shape="circle", drill_oval=None):
    p = pcbnew.PAD(fp)
    p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    p.SetLayerSet(p.PTHMask())
    p.SetNumber(str(num))
    shapes = {"circle": pcbnew.PAD_SHAPE_CIRCLE, "rect": pcbnew.PAD_SHAPE_RECT,
              "oval": pcbnew.PAD_SHAPE_OVAL, "roundrect": pcbnew.PAD_SHAPE_ROUNDRECT}
    p.SetShape(pcbnew.PADSTACK.ALL_LAYERS, shapes[shape])
    if isinstance(size, tuple):
        p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, _v(*size))
    else:
        p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, _v(size, size))
    if drill_oval:
        p.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_OBLONG)
        p.SetDrillSize(_v(*drill_oval))
    else:
        p.SetDrillSize(_v(drill, drill))
    p.SetPosition(_v(x, y))
    fp.Add(p)
    return p


def _rect(fp, layer, x0, y0, x1, y1, w):
    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    s.SetLayer(layer)
    s.SetStart(_v(x0, y0))
    s.SetEnd(_v(x1, y1))
    s.SetWidth(MM(w))
    fp.Add(s)


def _line(fp, layer, x0, y0, x1, y1, w):
    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(layer)
    s.SetStart(_v(x0, y0))
    s.SetEnd(_v(x1, y1))
    s.SetWidth(MM(w))
    fp.Add(s)


def _slot(fp, x, y0, y1, width):
    """Closed routed slot (stadium) on Edge.Cuts, vertical, centred on x."""
    r = width / 2
    for sx in (x - r, x + r):
        _line(fp, pcbnew.Edge_Cuts, sx, y0, sx, y1, 0.05)
    for cy, (a, b) in ((y0, (x - r, x + r)), (y1, (x + r, x - r))):
        arc = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_ARC)
        arc.SetLayer(pcbnew.Edge_Cuts)
        arc.SetWidth(MM(0.05))
        mid_y = cy - r if cy == y0 else cy + r
        arc.SetArcGeometry(_v(a, cy), _v(x, mid_y), _v(b, cy))
        fp.Add(arc)


def _body(fp, x0, y0, x1, y1, silk_gap=0.12):
    _rect(fp, pcbnew.F_Fab, x0, y0, x1, y1, 0.1)
    _rect(fp, pcbnew.F_SilkS, x0 - silk_gap, y0 - silk_gap, x1 + silk_gap, y1 + silk_gap, 0.12)
    _rect(fp, pcbnew.F_CrtYd, x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5, 0.05)
    fp.Reference().SetPosition(_v((x0 + x1) / 2, y0 - 1.5))
    fp.Value().SetPosition(_v((x0 + x1) / 2, (y0 + y1) / 2))


def fp_relay():
    fp = _new_fp("HF32FV-16", "Hongfa HF32FV-16 SPST-NO relay, 18.4x10.2 mm, top view")
    # centre of the body at the origin
    _pad(fp, 1, 7.62, -3.8, 2.2, 1.3, "rect")
    _pad(fp, 2, 7.62, 3.8, 2.2, 1.3)
    _pad(fp, 3, -5.08, -3.45, (2.6, 3.6), None, "oval", drill_oval=(0.9, 2.1))  # COM
    _pad(fp, 4, -7.62, 3.45, (2.6, 3.6), None, "oval", drill_oval=(0.9, 2.1))   # NO
    _body(fp, -9.2, -5.1, 9.2, 5.1)
    return fp


def fp_zmpt():
    fp = _new_fp("ZMPT107-1", "ZMPT107-1 voltage transformer, 19x10 mm, pins 16.3 x 7.2")
    _pad(fp, 1, -8.15, 3.6, 1.9, 1.1, "rect")
    _pad(fp, 2, -8.15, -3.6, 1.9, 1.1)
    _pad(fp, 3, 8.15, 3.6, 1.9, 1.1)
    _pad(fp, 4, 8.15, -3.6, 1.9, 1.1)
    _body(fp, -9.5, -5.0, 9.5, 5.0)
    return fp


def fp_db2er():
    fp = _new_fp("DB2ER-5.08-02P",
                 "Dorabo DB2ER-5.08-2P right-angle pluggable header, 15 A; mating face toward +Y; slot between pins")
    for i in range(2):
        _pad(fp, i + 1, i * 5.08, 0, 2.6, 1.7, "rect" if i == 0 else "circle")
    _body(fp, -2.54, -2.0, 7.62, 10.0)
    _slot(fp, 2.54, -2.6, 3.4, 1.0)
    return fp


def fp_wj15():
    fp = _new_fp("WJ15EDGRC-3.81-04P", "Kangnex WJ15EDGRC-3.81-4P right-angle pluggable header; mating face toward +Y")
    for i in range(4):
        _pad(fp, i + 1, i * 3.81, 0, 2.1, 1.4, "rect" if i == 0 else "circle")
    _body(fp, -2.345, -1.2, 3 * 3.81 + 2.345, 6.05)
    return fp


def main():
    LIB.mkdir(exist_ok=True)
    SYM.write_text(symbols(), encoding="utf8", newline="\n")
    if PRETTY.exists():
        shutil.rmtree(PRETTY)
    PRETTY.mkdir()
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    for f in (fp_relay(), fp_zmpt(), fp_db2er(), fp_wj15()):
        io.FootprintSave(str(PRETTY), f)
    print("wrote", SYM, "and", sorted(os.listdir(PRETTY)))


if __name__ == "__main__":
    main()
