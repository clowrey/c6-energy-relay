"""Write hw/c6-energy-relay.kicad_sch from hw/design.py.

One sheet. Components are laid out in functional blocks; every connected pin gets a short wire and a
local label with its net name, unconnected pins get a no-connect flag. KiCad's ERC and netlist export
are the tests (tests/test_sch.py).

    python -m hw.gen_sch
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from hw import design

HERE = Path(__file__).resolve().parent
SCH = HERE / "c6-energy-relay.kicad_sch"
KICAD_SYMBOLS = Path(os.environ.get("KICAD_SYMBOL_DIR", r"C:\Program Files\KiCad\10.0\share\kicad\symbols"))
LOCAL = {"c6er": HERE / "lib" / "c6er.kicad_sym"}
PROJECT = "c6-energy-relay"
G = 1.27  # grid


def _uid(*parts) -> str:
    return str(uuid.uuid5(design.NS, "/".join(map(str, parts))))


def _snap(v: float) -> float:
    return round(round(v / G) * G, 4)


# ---- symbol library access -------------------------------------------------------------------
_lib_cache: dict[str, str] = {}


def _lib_text(lib: str) -> str:
    if lib not in _lib_cache:
        path = LOCAL.get(lib, KICAD_SYMBOLS / f"{lib}.kicad_sym")
        _lib_cache[lib] = path.read_text(encoding="utf8")
    return _lib_cache[lib]


def _block(text: str, start: int) -> str:
    depth = 0
    for j in range(start, len(text)):
        ch = text[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    raise ValueError("unbalanced")


def _raw_symbol(lib: str, name: str) -> str:
    text = _lib_text(lib)
    m = re.search(r'\n\s*\(symbol "' + re.escape(name) + r'"\s', text)
    if not m:
        raise KeyError(f"{lib}:{name}")
    return _block(text, m.start() + text[m.start():].index("("))


def _prop_block(sym: str, prop: str) -> str | None:
    m = re.search(r'\(property "' + re.escape(prop) + r'"', sym)
    return _block(sym, m.start()) if m else None


def flat_symbol(lib_id: str) -> str:
    """Symbol text with `extends` resolved, top-level name "lib:name" (as schematic lib_symbols want)."""
    lib, name = lib_id.split(":")
    sym = _raw_symbol(lib, name)
    ext = re.search(r'\(extends "([^"]+)"\)', sym)
    if ext:
        parent = ext.group(1)
        base = _raw_symbol(lib, parent)
        base = base.replace(f'(symbol "{parent}"', f'(symbol "{name}"', 1)
        base = re.sub(r'\(symbol "' + re.escape(parent) + r'_(\d+)_(\d+)"', rf'(symbol "{name}_\1_\2"', base)
        for prop in re.findall(r'\(property "([^"]+)"', sym):
            new, old = _prop_block(sym, prop), _prop_block(base, prop)
            if old:
                base = base.replace(old, new, 1)
            else:
                i = base.index("(property")
                base = base[:i] + new + "\n\t\t" + base[i:]
        sym = base
    return sym.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)


def symbol_pins(lib_id: str) -> list[tuple[str, float, float, int]]:
    """(number, x, y, angle) for every pin of unit 1 / body style 1 (symbol coordinates, y up)."""
    sym = flat_symbol(lib_id)
    name = lib_id.split(":")[1]
    pins = []
    for m in re.finditer(r'\(symbol "' + re.escape(name) + r'_(\d+)_(\d+)"', sym):
        unit, style = int(m.group(1)), int(m.group(2))
        if unit not in (0, 1) or style not in (0, 1):
            continue
        sub = _block(sym, m.start())
        for pm in re.finditer(r"\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)", sub):
            pblock = _block(sub, pm.start())
            num = re.search(r'\(number "([^"]*)"', pblock).group(1)
            pins.append((num, float(pm.group(1)), float(pm.group(2)), int(pm.group(3))))
    return pins


# ---- layout ----------------------------------------------------------------------------------
BLOCKS = [  # (block, origin x, origin y, width)
    ("mains", 25.4, 30.48, 170.0),
    ("vsense", 25.4, 120.0, 170.0),
    ("relay", 25.4, 175.0, 170.0),
    ("power", 210.0, 30.48, 160.0),
    ("usb", 210.0, 90.0, 160.0),
    ("mcu", 210.0, 160.0, 160.0),
    ("meter", 380.0, 30.48, 190.0),
]
OUTWARD = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}  # schematic coords (y down)
STUB = 2.54


def _bbox(pins, nets_by_pin):
    xs, ys = [0.0], [0.0]
    for num, x, y, ang in pins:
        dx, dy = OUTWARD[ang]
        reach = STUB + (len(nets_by_pin.get(num, "")) * 1.0 + 1.5 if dx else 1.5)
        xs += [x, x + dx * reach]
        ys += [-y, -y + dy * (STUB + (len(nets_by_pin.get(num, "")) * 1.0 + 1.5 if dy else 0))]
    x0, x1 = min(xs) - 2.54, max(xs) + 2.54
    if x1 - x0 < 12.7:  # room for the value text under 2-pin parts
        x0, x1 = -6.35, 6.35
    return x0, min(ys) - 5.08, x1, max(ys) + 5.08


def layout(items):
    """items: list of (key, block, pins, nets_by_pin) -> {key: (x, y)}"""
    pos = {}
    for block, ox, oy, width in BLOCKS:
        x, y, row_h = ox, oy, 0.0
        for key, b, pins, nets in items:
            if b != block:
                continue
            x0, y0, x1, y1 = _bbox(pins, nets)
            w, h = x1 - x0, y1 - y0
            if x + w > ox + width and x > ox:
                x, y, row_h = ox, y + row_h, 0.0
            pos[key] = (_snap(x - x0), _snap(y - y0))
            x += w
            row_h = max(row_h, h)
    return pos


# ---- writers ---------------------------------------------------------------------------------
def _eff(hide=False, justify=""):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return f"(effects (font (size 1.27 1.27)){j}{h})"


def _prop(name, value, x, y, hide=False, ang=0):
    return f'\t\t(property "{name}" "{value}" (at {x} {y} {ang}) {_eff(hide)})\n'


def place_symbol(ref, lib_id, value, footprint, lcsc, x, y, pins, dnp=False, extra_props=()):
    in_bom = "no" if (dnp or ref.startswith("#")) else "yes"
    s = (f'\t(symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit 1)\n'
         f'\t\t(exclude_from_sim no) (in_bom {in_bom}) (on_board {"no" if ref.startswith("#") else "yes"})'
         f' (in_pos_files {in_bom}) (dnp {"yes" if dnp else "no"})\n'
         f'\t\t(uuid "{_uid("sym", ref)}")\n')
    hide_ref = ref.startswith("#")
    s += _prop("Reference", ref, x, _snap(y - 3.81), hide=hide_ref)
    s += _prop("Value", value, x, _snap(y + 3.81), hide=hide_ref and lib_id != "power:PWR_FLAG")
    s += _prop("Footprint", footprint, x, y, hide=True)
    s += _prop("Datasheet", "", x, y, hide=True)
    if lcsc:
        s += _prop("LCSC", lcsc, x, y, hide=True)
    for k, v in extra_props:
        s += _prop(k, v, x, y, hide=True)
    for num in dict.fromkeys(p[0] for p in pins):
        s += f'\t\t(pin "{num}" (uuid "{_uid("pin", ref, num)}"))\n'
    s += (f'\t\t(instances (project "{PROJECT}" (path "/{design.ROOT_UUID}" (reference "{ref}") (unit 1))))\n'
          "\t)\n")
    return s


def wire(x0, y0, x1, y1, key):
    return (f"\t(wire (pts (xy {x0} {y0}) (xy {x1} {y1})) (stroke (width 0) (type default))"
            f' (uuid "{_uid("wire", key)}"))\n')


def label(net, x, y, ang, key):
    just = {0: "left bottom", 180: "right bottom", 90: "left bottom", 270: "right bottom"}[ang]
    return f'\t(label "{net}" (at {x} {y} {ang}) {_eff(justify=just)} (uuid "{_uid("label", key)}"))\n'


def no_connect(x, y, key):
    return f'\t(no_connect (at {x} {y}) (uuid "{_uid("nc", key)}"))\n'


def connect_pins(ref, sx, sy, pins, nets_by_pin):
    out, done = [], {}
    for num, px, py, ang in pins:
        cx, cy = _snap(sx + px), _snap(sy - py)
        net = nets_by_pin.get(num)
        if (cx, cy) in done:
            if net and done[(cx, cy)] and net != done[(cx, cy)]:
                raise ValueError(f"{ref} stacked pins on different nets: {net} / {done[(cx, cy)]}")
            continue
        done[(cx, cy)] = net
        if not net:
            out.append(no_connect(cx, cy, f"{ref}.{num}"))
            continue
        dx, dy = OUTWARD[ang]
        ex, ey = _snap(cx + dx * STUB), _snap(cy + dy * STUB)
        out.append(wire(cx, cy, ex, ey, f"{ref}.{num}"))
        lang = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[(dx, dy)]
        out.append(label(net, ex, ey, lang, f"{ref}.{num}"))
    return out


PWR_FLAGS = ["L_F", "N_F"]


def build() -> str:
    comps = design.COMPONENTS
    lib_ids = sorted({c.symbol for c in comps} | {"power:PWR_FLAG"})
    pins_of = {lid: symbol_pins(lid) for lid in lib_ids}
    items = [(c.ref, c.block, pins_of[c.symbol], c.pins) for c in comps]
    items += [(f"#FLG{i + 1:02d}", "mains", pins_of["power:PWR_FLAG"], {"1": net})
              for i, net in enumerate(PWR_FLAGS)]
    pos = layout(items)

    out = [f'(kicad_sch\n\t(version 20260306)\n\t(generator "c6er_gen_sch")\n\t(generator_version "10.0")\n'
           f'\t(uuid "{design.ROOT_UUID}")\n\t(paper "A2")\n'
           '\t(title_block (title "C6 Energy Relay") (rev "1.0") (company "c6-energy-relay")\n'
           '\t\t(comment 1 "Generated by hw/gen_sch.py from hw/design.py - edit design.py, not this file")\n'
           '\t\t(comment 2 "MAINS: L, N/L2, relay contacts. Keep 6.5 mm from low voltage.")\n\t)\n']
    out.append("\t(lib_symbols\n")
    for lid in lib_ids:
        out.append(flat_symbol(lid) + "\n")
    out.append("\t)\n")

    for c in comps:
        x, y = pos[c.ref]
        out.append(place_symbol(c.ref, c.symbol, c.value, c.footprint, c.lcsc, x, y, pins_of[c.symbol],
                                dnp=c.dnp, extra_props=[("MPN", design.PARTS[c.part].mpn)] if c.part else []))
        out += connect_pins(c.ref, x, y, pins_of[c.symbol], c.pins)
    for i, net in enumerate(PWR_FLAGS):
        ref = f"#FLG{i + 1:02d}"
        x, y = pos[ref]
        out.append(place_symbol(ref, "power:PWR_FLAG", "PWR_FLAG", "", "", x, y, pins_of["power:PWR_FLAG"]))
        out += connect_pins(ref, x, y, pins_of["power:PWR_FLAG"], {"1": net})

    # block titles
    for block, ox, oy, _ in BLOCKS:
        title = {"mains": "Mains input, fuses, MOV, isolated 5 V", "vsense": "Voltage sense (ZMPT107-1)",
                 "relay": "Relays (dry contacts, 10 A use)", "power": "5 V / 3.3 V", "usb": "USB-C (native USB)",
                 "mcu": "ESP32-C6-MINI-1, buttons, LED, GPIO header", "meter": "BL0939 metering, CT inputs"}[block]
        out.append(f'\t(text "{title}" (exclude_from_sim no) (at {_snap(ox)} {_snap(oy - 7.62)} 0)'
                   f' (effects (font (size 2.54 2.54) (bold yes)) (justify left bottom))'
                   f' (uuid "{_uid("title", block)}"))\n')
    out.append(f'\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')
    return "".join(out)


NETCLASS_RULES = {  # class: (track width, clearance within the class), mm
    "Default": (0.2, 0.2), "LV": (0.2, 0.2), "POWER": (0.5, 0.2),
    "MAINS_L": (1.0, 0.5), "MAINS_N": (1.0, 0.5), "MAINS_DIV": (0.5, 0.5),
    "RELAY1": (2.5, 0.5), "RELAY2": (2.5, 0.5),
}


def write_project():
    """hw/c6-energy-relay.kicad_pro: net classes and JLC-friendly board limits (KiCad fills the rest)."""
    import json
    classes = []
    for i, (name, (w, c)) in enumerate(NETCLASS_RULES.items()):
        classes.append({"name": name, "clearance": c, "track_width": w, "via_diameter": 0.6, "via_drill": 0.3,
                        "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2,
                        "diff_pair_gap": 0.2, "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12,
                        "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
                        "schematic_color": "rgba(0, 0, 0, 0.000)",
                        "priority": 2147483647 if name == "Default" else i})
    patterns = [{"netclass": cls, "pattern": "/" + net} for net, cls in sorted(design.NETCLASS.items())]
    proj = {
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 3},
        "board": {"design_settings": {
            "rules": {"min_clearance": 0.15, "min_copper_edge_clearance": 0.5, "min_hole_clearance": 0.25,
                      "min_hole_to_hole": 0.25, "min_through_hole_diameter": 0.3, "min_track_width": 0.15,
                      "min_via_annular_width": 0.13, "min_via_diameter": 0.5, "min_silk_clearance": 0.0,
                      "solder_mask_to_copper_clearance": 0.0, "use_height_for_length_calcs": True},
            "track_widths": [0.0, 0.2, 0.3, 0.5, 1.0, 2.5],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}],
        }},
        "net_settings": {"classes": classes, "meta": {"version": 5}, "net_colors": {},
                         "netclass_assignments": {}, "netclass_patterns": patterns},
        "sheets": [[design.ROOT_UUID, "Root"]],
        "text_variables": {},
    }
    (HERE / f"{PROJECT}.kicad_pro").write_text(json.dumps(proj, indent=2) + "\n", encoding="utf8", newline="\n")


def main():
    write_project()
    SCH.write_text(build(), encoding="utf8", newline="\n")
    print("wrote", SCH)


if __name__ == "__main__":
    main()
