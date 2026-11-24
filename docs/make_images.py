"""README images: docs/img/*.png.

    python docs/make_images.py [sch] [layers] [render] [case]     (no argument: all of them)

Runs with the system Python (PyMuPDF, Pillow, VTK, build123d) and calls KiCad 10's kicad-cli:
  sch     schematic sections, cropped from the schematic PDF
  layers  copper, silkscreen and mask layers (kicad-cli SVG, drawn on a dark background)
  render  3D views of the board (kicad-cli pcb render, raytraced)
  case    3D views of the case with the board (VTK, offscreen)
Run after the board and case scripts, so the images match the committed design.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
KCLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
PCB = ROOT / "hw" / "c6-energy-relay.kicad_pcb"
SCH = ROOT / "hw" / "c6-energy-relay.kicad_sch"
BG = (16, 20, 28)               # dark background for the layer plots


def kcli(*args):
    subprocess.run([str(KCLI), *map(str, args)], check=True, capture_output=True)


# ---------------------------------------------------------------- schematic
SECTIONS = {  # title on the sheet -> image name
    "Mains input, fuses, MOV, isolated 5 V": "sch_mains",
    "Voltage sense (ZMPT107-1)": "sch_vsense",
    "Relays (dry contacts, 10 A use)": "sch_relays",
    "5 V / 3.3 V": "sch_power",
    "USB-C (native USB)": "sch_usb",
    "ESP32-C5 (ESPC5-32-H4), buttons, LED, Qwiic, GPIO header": "sch_mcu",
    "BL0939 metering, CT inputs": "sch_metering",
}


def schematic():
    import pymupdf
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "sch.pdf"
        kcli("sch", "export", "pdf", "--exclude-drawing-sheet", "-o", pdf, SCH)
        doc = pymupdf.open(pdf)
        page = doc[0]
        titles = {}
        for title, name in SECTIONS.items():
            hits = page.search_for(title)
            assert hits, f"section title not found: {title}"
            titles[name] = hits[0]
        # everything drawn on the page, as small boxes
        items = [d["rect"] for d in page.get_drawings()]
        items += [pymupdf.Rect(b[:4]) for b in page.get_text("blocks")]
        xs = sorted({round(r.x0) for r in titles.values()})
        out = {}
        whole = None
        for name, t in titles.items():
            col_right = min([x for x in xs if x > t.x0 + 5] + [page.rect.x1])
            below = [r.y0 for n, r in titles.items() if abs(r.x0 - t.x0) < 5 and r.y0 > t.y0 + 5]
            region = pymupdf.Rect(t.x0 - 15, t.y0 - 5, col_right - 15, min(below + [page.rect.y1]) - 5)
            box = pymupdf.Rect(t)
            for r in items:
                if r.is_empty or r.width > 400 or r.height > 400:
                    continue
                if region.contains(r):
                    box |= r
            box = box + (-8, -8, 8, 8)
            whole = pymupdf.Rect(box) if whole is None else whole | box
            pix = page.get_pixmap(dpi=200, clip=box)
            pix.save(IMG / f"{name}.png")
            out[name] = (pix.width, pix.height)
        # whole sheet: the union of the sections
        pix = page.get_pixmap(dpi=110, clip=whole + (-10, -10, 10, 10))
        pix.save(IMG / "schematic.png")
        out["schematic"] = (pix.width, pix.height)
        doc.close()
    for k, v in out.items():
        print(k, v)


# ---------------------------------------------------------------- layers
LAYERS = {  # image -> layers, in drawing order (later on top)
    "layer_top": "B.Cu,F.Cu,F.Silkscreen,Edge.Cuts",
    "layer_f_cu": "F.Cu,Edge.Cuts",
    "layer_b_cu": "B.Cu,Edge.Cuts",
    "layer_f_silk": "F.Silkscreen,Edge.Cuts",
    "layer_f_mask": "F.Mask,Edge.Cuts",
}


def layers(width=1100):
    import pymupdf
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        for name, lay in LAYERS.items():
            svg = Path(tmp) / f"{name}.svg"
            kcli("pcb", "export", "svg", "--mode-single", "--layers", lay, "--page-size-mode", "2",
                 "--exclude-drawing-sheet", "--drill-shape-opt", "2", "-o", svg, PCB)
            doc = pymupdf.open(svg)
            page = doc[0]
            zoom = width / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
            doc.close()
            fg = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
            # KiCad plots on a white page: make white transparent before compositing on dark
            px = fg.load()
            for y in range(fg.height):
                for x in range(fg.width):
                    r, g, b, a = px[x, y]
                    if r > 245 and g > 245 and b > 245:
                        px[x, y] = (0, 0, 0, 0)
            img = Image.new("RGBA", fg.size, BG + (255,))
            img.alpha_composite(fg)
            pad = 24
            framed = Image.new("RGB", (img.width + 2 * pad, img.height + 2 * pad), BG)
            framed.paste(img.convert("RGB"), (pad, pad))
            framed.save(IMG / f"{name}.png", optimize=True)
            print(name, framed.size)


def detail(width=4400, box=(0.5, 0.0, 0.98, 0.54)):
    """Close-up of the module fan-out to the GPIO header (box: fractions of the board image)."""
    from PIL import Image
    global LAYERS
    saved, LAYERS = LAYERS, {"layer_detail": "B.Cu,F.Cu,F.Silkscreen,Edge.Cuts"}
    try:
        layers(width)
    finally:
        LAYERS = saved
    path = IMG / "layer_detail.png"
    im = Image.open(path)
    w, h = im.size
    im = im.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3])))
    im.thumbnail((900, 1100))
    im.save(path, optimize=True)
    print("layer_detail", im.size)


# ---------------------------------------------------------------- 3D board
RENDERS = {  # image -> kicad-cli pcb render arguments (orthographic)
    "board_iso": ["--side", "top", "--rotate", "-55,0,25", "--zoom", "0.85"],
    "board_iso2": ["--side", "top", "--rotate", "-60,0,-25", "--zoom", "0.85"],
    "board_top": ["--side", "top", "--zoom", "0.95"],
    "board_bottom": ["--side", "bottom", "--zoom", "0.95"],
    "board_front": ["--side", "front", "--rotate", "15,0,0", "--zoom", "0.9"],
}


def render(w=1600, h=1200):
    from PIL import Image
    for name, args in RENDERS.items():
        path = IMG / f"{name}.png"
        kcli("pcb", "render", "--quality", "high", "--background", "transparent",
             "-w", w, "-h", h, *args, "-o", path, PCB)
        im = Image.open(path).convert("RGBA")
        # drop the raytracer's semi-transparent floor shadow, keep the board's soft edge
        a = im.getchannel("A").point(lambda v: 0 if v < 180 else min(255, (v - 180) * 4))
        im.putalpha(a)
        im.crop(a.getbbox()).save(path, optimize=True)      # trim the empty margin
        print(name, Image.open(path).size)


# ---------------------------------------------------------------- case
def main():
    IMG.mkdir(parents=True, exist_ok=True)
    jobs = sys.argv[1:] or ["sch", "layers", "render", "case"]
    if "sch" in jobs:
        schematic()
    if "layers" in jobs:
        layers()
        detail()
    if "render" in jobs:
        render()
    if "case" in jobs:
        from case_views import case_views  # docs/case_views.py
        case_views(IMG)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
