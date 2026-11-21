"""3D views of the case with the board in it, rendered offscreen with VTK (called by make_images.py).

Case coordinates (case/case.py): x, y as the board (lower-left corner at 0, y up), z = 0 at the
PCB's bottom face, +z toward the front. The board comes from kicad-cli as GLB with --drill-origin,
so it lands in the same frame (scaled from metres to mm).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "case"))
import case as casemod  # noqa: E402  case/case.py

KCLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
PCB = ROOT / "hw" / "c6-energy-relay.kicad_pcb"

COVER = (0.86, 0.87, 0.89)
BASE = (0.30, 0.33, 0.38)
RAIL = (0.75, 0.76, 0.78)


def shape_actor(shape, colour, tol=0.05):
    verts, tris = shape.tessellate(tol, 0.2)
    pts = np.array([(v.X, v.Y, v.Z) for v in verts], dtype=float)
    cells = np.hstack([np.full((len(tris), 1), 3), np.array(tris)]).astype(np.int64).ravel()
    poly = vtk.vtkPolyData()
    p = vtk.vtkPoints()
    p.SetData(numpy_to_vtk(pts, deep=True))
    poly.SetPoints(p)
    ca = vtk.vtkCellArray()
    ca.SetCells(len(tris), numpy_to_vtkIdTypeArray(cells, deep=True))
    poly.SetPolys(ca)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.SetFeatureAngle(35)
    normals.SplittingOn()
    normals.ConsistencyOn()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    pr = actor.GetProperty()
    pr.SetColor(*colour)
    pr.SetAmbient(0.15)
    pr.SetDiffuse(0.8)
    pr.SetSpecular(0.15)
    pr.SetSpecularPower(20)
    return actor


def board_actors(glb):
    """Import the board GLB into a scratch renderer and hand back its actors (scaled to mm)."""
    ren = vtk.vtkRenderer()
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    imp = vtk.vtkGLTFImporter()
    imp.SetFileName(str(glb))
    imp.SetRenderWindow(win)
    imp.Update()
    actors = []
    coll = ren.GetActors()
    coll.InitTraversal()
    for _ in range(coll.GetNumberOfItems()):
        a = coll.GetNextActor()
        actors.append(a)
    for a in actors:
        ren.RemoveActor(a)
    return actors


def place(actors, dz=0.0, scale=1.0):
    for a in actors:
        t = vtk.vtkTransform()
        t.PostMultiply()
        if a.GetUserTransform() is not None:
            t.Concatenate(a.GetUserTransform())
        if scale != 1.0:          # the board GLB: metres, y up -> mm, z up
            t.RotateX(90)
            t.Scale(scale, scale, scale)
        t.Translate(0, 0, dz)
        a.SetUserTransform(t)


def ts35_rail(y_centre, z_face, x0, x1):
    """TS35 x 7.5 top-hat rail along x: flanges against the base's back face at z_face."""
    from build123d import Box, Pos
    def box(ax0, ax1, ay0, ay1, az0, az1):
        return Pos((ax0 + ax1) / 2, (ay0 + ay1) / 2, (az0 + az1) / 2) * Box(ax1 - ax0, ay1 - ay0, az1 - az0)
    t = 1.0
    rail = box(x0, x1, y_centre + 12.5, y_centre + 17.5, z_face - t, z_face)          # upper flange
    rail += box(x0, x1, y_centre - 17.5, y_centre - 12.5, z_face - t, z_face)         # lower flange
    rail += box(x0, x1, y_centre + 12.5, y_centre + 13.5, z_face - 7.5, z_face)       # sides
    rail += box(x0, x1, y_centre - 13.5, y_centre - 12.5, z_face - 7.5, z_face)
    rail += box(x0, x1, y_centre - 13.5, y_centre + 13.5, z_face - 7.5, z_face - 6.5)  # back
    for xs in np.arange(x0 + 10, x1 - 5, 25):                                       # mounting slots
        rail -= box(xs - 3, xs + 3, y_centre - 2.6, y_centre + 2.6, z_face - 8, z_face - 6)
    return rail


def render(actors, path, direction, up=(0, 1, 0), size=(1600, 1200), zoom=1.0, angle=18):
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    ren.SetBackgroundAlpha(0.0)
    for a in actors:
        ren.AddActor(a)
    kit = vtk.vtkLightKit()
    kit.SetKeyLightIntensity(0.9)
    kit.AddLightsToRenderer(ren)
    ren.UseFXAAOn()
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetAlphaBitPlanes(1)
    win.SetMultiSamples(0)
    win.SetSize(*size)
    win.AddRenderer(ren)
    cam = ren.GetActiveCamera()
    cam.SetViewAngle(angle)
    cam.SetFocalPoint(0, 0, 0)
    cam.SetPosition(*direction)
    cam.SetViewUp(*up)
    ren.ResetCamera()
    cam.Zoom(zoom)
    ren.ResetCameraClippingRange()
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.SetInputBufferTypeToRGBA()
    grab.ReadFrontBufferOff()
    grab.Update()
    w = vtk.vtkPNGWriter()
    w.SetFileName(str(path))
    w.SetInputConnection(grab.GetOutputPort())
    w.Write()
    # trim the empty margin
    from PIL import Image
    im = Image.open(path)
    im.crop(im.getchannel("A").getbbox()).save(path, optimize=True)
    print(Path(path).name, Image.open(path).size)


def case_views(img: Path):
    features = json.loads((ROOT / "hw" / "out" / "board_features.json").read_text())
    base, cover = casemod.build_case(features)
    w, h = features["outline_mm"]
    with tempfile.TemporaryDirectory() as tmp:
        glb = Path(tmp) / "board.glb"
        subprocess.run([str(KCLI), "pcb", "export", "glb", "--drill-origin", "--subst-models",
                        "--include-tracks", "--include-pads", "--include-zones", "--include-silkscreen",
                        "--include-soldermask", "-o", str(glb), str(PCB)], check=True, capture_output=True)

        def board(dz=0.0):
            acts = board_actors(glb)
            place(acts, dz=dz, scale=1000.0)
            return acts

        b = [a.GetBounds() for a in board()]
        print("board bounds", [round(f(v[i] for v in b), 1) for i, f in
                               ((0, min), (1, max), (2, min), (3, max), (4, min), (5, max))])

        def centred(actors, dz=0.0):
            for a in actors:
                t = vtk.vtkTransform()
                t.PostMultiply()
                if a.GetUserTransform() is not None:
                    t.Concatenate(a.GetUserTransform())
                t.Translate(-w / 2, -h / 2, dz)
                a.SetUserTransform(t)
            return actors

        # 1. closed case from the front, below left: front face, LED window, plug openings
        acts = [shape_actor(cover, COVER), shape_actor(base, BASE)] + board()
        render(centred(acts), img / "case_front.png", direction=(-0.55, -0.75, 1.0), zoom=1.0)

        # 2. exploded along z: base, board, cover
        acts = [shape_actor(base, BASE)] + board()
        a_cover = shape_actor(cover, COVER)
        place([a_cover], dz=40.0)
        a_base = acts[0]
        place([a_base], dz=-30.0)
        render(centred(acts + [a_cover]), img / "case_exploded.png", direction=(-1.0, -0.55, 0.45),
               up=(0, 0, 1), zoom=1.0)

        # 3. the board in the cover, seen from the back (base off)
        acts = [shape_actor(cover, COVER)] + board()
        render(centred(acts), img / "case_inside.png", direction=(0.35, -0.45, -1.0), zoom=1.0)

        # 4. on a TS35 rail, seen from the back: the hook and the sprung latch
        rail = ts35_rail(h / 2, casemod.Z_BACK_OUT, -30, w + 30)
        acts = [shape_actor(cover, COVER), shape_actor(base, BASE), shape_actor(rail, RAIL)]
        render(centred(acts), img / "case_din.png", direction=(0.6, -0.55, -1.0), zoom=1.0)


if __name__ == "__main__":
    out = ROOT / "docs" / "img"
    out.mkdir(parents=True, exist_ok=True)
    case_views(out)
