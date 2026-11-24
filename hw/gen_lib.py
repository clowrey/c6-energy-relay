"""Write the project-local KiCad library hw/lib (symbols c6er.kicad_sym, footprints c6er.pretty).

Run with KiCad's Python:  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" hw/gen_lib.py

Dimensions are from the datasheets in hw/datasheets (fetched by hw/tools/fetch_datasheets.py):
  HF32FV-16      Hongfa, 18.4 x 10.2 x 15.5, coil pins 7.6 apart, COM/NO blades 12.7 / 15.24 from the coil
                 row (bottom-view drawing mirrored to top view here)
  ZMPT107-1      19 x 10 x 18.2, pins 0.8 round, 16.3 x 7.2 grid
  DB2ER-5.08     Dorabo right-angle pluggable header, drill 1.7, body 12 deep, pins 2.0 from the back
  WJ15EDGRC-3.81 Kangnex right-angle pluggable header, drill 1.4, body 7.25 deep, pins 1.2 from the back
  Fuse 10.1x3.1  Hongda 40T (10.5 x 3.2 x 3.2) or Littelfuse 443 (10.1 x 3.1 x 3.1) ceramic SMD fuse
  ESPC5-32       DOIT ESP32-C5 module, 18 x 25.5 x 3, WROOM-1 land pattern (DOIT user manual V1.0, fig. 2.1 / 3.3)
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
def _prop(name, value, x, y, hide=False, justify=""):
    h = " (hide yes)" if hide else ""
    j = f" (justify {justify})" if justify else ""
    return (f'\t\t(property "{name}" "{value}" (at {x} {y} 0)\n'
            f'\t\t\t(effects (font (size 1.27 1.27)){j}{h})\n\t\t)\n')


def _pin(num, name, kind, x, y, angle, length=2.54):
    return (f'\t\t\t(pin {kind} line (at {x} {y} {angle}) (length {length})\n'
            f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)\n')


def _symbol(name, ref, value, desc, footprint, body, pins, graphics="", show_pin_names=True, fields_right=False):
    (x0, y0, x1, y1) = body
    s = f'\t(symbol "{name}"\n'
    if not show_pin_names:
        s += "\t\t(pin_names (hide yes))\n"
    s += "\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)\n"
    if fields_right:            # beside the body: pins on top and bottom leave no room there
        s += _prop("Reference", ref, x1 + 1.27, 1.27, justify="left")
        s += _prop("Value", value, x1 + 1.27, -1.27, justify="left")
    else:
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
                       "c6er:HF32FV-16", (-6.35, -5.08, 6.35, 5.08), pins, g, show_pin_names=False,
                       fields_right=True))

    # DOIT ESPC5-32 (ESP32-C5, WROOM-1 format): pin names from the DOIT user manual V1.0, table 2.2
    L, R = -15.24, 15.24
    left = [("3", "EN", "input"), ("6", "IO0", "bidirectional"), ("7", "IO1", "bidirectional"),
            ("4", "IO2", "bidirectional"), ("5", "IO3", "bidirectional"), ("17", "IO4", "bidirectional"),
            ("16", "IO5", "bidirectional"), ("8", "IO6", "bidirectional"), ("9", "IO7", "bidirectional"),
            ("10", "IO8", "bidirectional"), ("11", "IO9", "bidirectional"), ("12", "IO10", "bidirectional")]
    right = [("25", "IO11/TXD0", "bidirectional"), ("24", "IO12/RXD0", "bidirectional"),
             ("13", "IO13/USB_D-", "bidirectional"), ("14", "IO14/USB_D+", "bidirectional"),
             ("19", "IO15", "bidirectional"), ("21", "IO23", "bidirectional"), ("23", "IO24", "bidirectional"),
             ("26", "IO25", "bidirectional"), ("27", "IO26", "bidirectional"), ("18", "IO27", "bidirectional"),
             ("15", "IO28/BOOT", "bidirectional"), ("20", "NC", "no_connect"), ("22", "NC", "no_connect")]
    pins = [("2", "3V3", "power_in", 0, 20.32, 270)]
    pins += [(n, nm, k, L, 13.97 - 2.54 * i, 0) for i, (n, nm, k) in enumerate(left)]
    pins += [(n, nm, k, R, 13.97 - 2.54 * i, 180) for i, (n, nm, k) in enumerate(right)]
    pins += [("1", "GND", "power_in", -2.54, -20.32, 90), ("28", "GND", "passive", 0, -20.32, 90),
             ("29", "EPAD", "passive", 2.54, -20.32, 90)]
    out.append(_symbol("ESPC5-32", "U", "ESPC5-32-H4",
                       "DOIT ESPC5-32-H4: ESP32-C5 module, 2.4 + 5 GHz Wi-Fi 6, BLE 5, 802.15.4, 4 MB flash, PCB antenna",
                       "c6er:ESPC5-32", (-12.7, -17.78, 12.7, 17.78), pins))
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
    _pad(fp, 3, -5.08, -3.45, (2.2, 2.8), None, "oval", drill_oval=(0.9, 2.1))  # COM
    _pad(fp, 4, -7.62, 3.45, (2.2, 2.8), None, "oval", drill_oval=(0.9, 2.1))   # NO (4 mm to COM)
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


def fp_fuse():
    fp = _new_fp("Fuse_SMD_10.1x3.1", "Ceramic SMD fuse 10.1 x 3.1 mm: Hongda 40T (10.5 x 3.2), Littelfuse 443")
    fp.SetAttributes(pcbnew.FP_SMD)
    for num, x in (("1", -4.6), ("2", 4.6)):
        p = pcbnew.PAD(fp)
        p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        p.SetLayerSet(p.SMDMask())
        p.SetNumber(num)
        p.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_ROUNDRECT)
        p.SetRoundRectRadiusRatio(pcbnew.PADSTACK.ALL_LAYERS, 0.1)
        p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, _v(2.8, 3.2))
        p.SetPosition(_v(x, 0))
        fp.Add(p)
    _rect(fp, pcbnew.F_Fab, -5.25, -1.6, 5.25, 1.6, 0.1)
    for y in (-1.75, 1.75):                        # silk along the sides only, between the pads
        _line(fp, pcbnew.F_SilkS, -2.9, y, 2.9, y, 0.12)
    _rect(fp, pcbnew.F_CrtYd, -6.25, -1.9, 6.25, 1.9, 0.05)
    fp.Reference().SetPosition(_v(0, -3.0))
    fp.Value().SetPosition(_v(0, 0))
    return fp


def _smd(fp, num, x, y, w, h, paste_margin=None):
    p = pcbnew.PAD(fp)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetLayerSet(p.SMDMask())
    p.SetNumber(str(num))
    p.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_ROUNDRECT)
    p.SetRoundRectRadiusRatio(pcbnew.PADSTACK.ALL_LAYERS, 0.2)
    p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, _v(w, h))
    p.SetPosition(_v(x, y))
    if paste_margin is not None:
        p.SetLocalSolderPasteMargin(MM(paste_margin))
    fp.Add(p)
    return p


def fp_espc5():
    """DOIT ESPC5-32 (18 x 25.5 x 3 mm, the WROOM-1 outline), origin at the body centre, antenna toward -y.
    Castellated pads at 1.27 mm, pad 1 / 28 7.49 mm from the antenna end, pad 14 / 15 1.5 mm from the other end
    (DOIT fig. 3.3; the same as Espressif's ESP32-C6-WROOM-1 land pattern). Pads 1.5 x 0.9, 0.5 mm outside the body.
    Ground pad 29: DOIT draws it 4.5 mm square but places it differently in its two figures (and Espressif's WROOM-1
    pad sits elsewhere again), so the copper is 5.0 mm square over both readings, with paste only in its middle."""
    fp = _new_fp("ESPC5-32", "DOIT ESPC5-32 ESP32-C5 module, 18 x 25.5 mm, 28 castellated pads + ground pad, PCB antenna")
    fp.SetAttributes(pcbnew.FP_SMD)
    for n in range(1, 15):
        _smd(fp, n, -8.75, -5.26 + (n - 1) * 1.27, 1.5, 0.9)
        _smd(fp, 29 - n, 8.75, -5.26 + (n - 1) * 1.27, 1.5, 0.9)
    _smd(fp, 29, -0.35, 1.15, 5.0, 5.0, paste_margin=-1.2)
    _rect(fp, pcbnew.F_Fab, -9.0, -12.75, 9.0, 12.75, 0.1)
    _line(fp, pcbnew.F_Fab, -9.0, -6.75, 9.0, -6.75, 0.1)          # end of the antenna area
    # silk: the antenna end and the far end only (the sides are all pads)
    for y in (-12.87, 12.87):
        _line(fp, pcbnew.F_SilkS, -9.12, y, 9.12, y, 0.12)
    for x in (-9.12, 9.12):
        _line(fp, pcbnew.F_SilkS, x, -12.87, x, -6.3, 0.12)
        _line(fp, pcbnew.F_SilkS, x, 12.87, x, 12.2, 0.12)
    _line(fp, pcbnew.F_SilkS, -10.2, -5.26, -9.9, -5.26, 0.3)       # pin 1
    _rect(fp, pcbnew.F_CrtYd, -9.75, -13.0, 9.75, 13.0, 0.05)
    fp.Reference().SetPosition(_v(0, -9.0))
    fp.Value().SetPosition(_v(0, 4.0))
    return fp


def add_model(fp, name):
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = "${KIPRJMOD}/lib/c6er.3dshapes/" + name + ".step"
    fp.Models().append(m)


def main():
    LIB.mkdir(exist_ok=True)
    SYM.write_text(symbols(), encoding="utf8", newline="\n")
    if PRETTY.exists():
        shutil.rmtree(PRETTY)
    PRETTY.mkdir()
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    for f in (fp_relay(), fp_zmpt(), fp_db2er(), fp_wj15(), fp_fuse(), fp_espc5()):
        add_model(f, f.GetFPID().GetLibItemName().c_str())
        io.FootprintSave(str(PRETTY), f)
    print("wrote", SYM, "and", sorted(os.listdir(PRETTY)))


if __name__ == "__main__":
    main()
