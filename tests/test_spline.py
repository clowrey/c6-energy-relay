"""hw/spline.py: smooth curves through waypoints as lines and tangent-continuous arcs (KiCad has no spline tracks)."""
import math

import pytest

from hw.spline import spline_path


def _tangents(item):
    """Unit tangents at the start and end of a ("line", a, b) or ("arc", a, mid, b)."""
    if item[0] == "line":
        _, a, b = item
        d = math.dist(a, b)
        u = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        return u, u
    _, a, m, b = item
    ax, ay, bx, by, cx, cy = *a, *m, *b
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    turn = 1 if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0 else -1

    def tan(p):
        return (-turn * (p[1] - uy) / r, turn * (p[0] - ux) / r)
    return tan(a), tan(b)


def _angle(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))))


CASES = [
    [(0, 0), (10, 0), (10, 10)],
    [(0, 0), (3, 4), (8, 4), (12, 9), (20, 9)],
    [(0, 0), (5, 1), (10, 0), (15, 1), (20, 0)],
    [(0, 0), (0, 5), (5, 5), (5, 0), (9, 0)],
]


@pytest.mark.parametrize("pts", CASES)
def test_smooth_and_through_every_waypoint(pts):
    items = spline_path(pts)
    assert math.dist(items[0][1], pts[0]) < 1e-6 and math.dist(items[-1][-1], pts[-1]) < 1e-6
    joints = [i[1] for i in items] + [items[-1][-1]]
    for p in pts:
        assert min(math.dist(p, j) for j in joints) < 1e-6, p
    for a, b in zip(items, items[1:]):
        assert math.dist(a[-1], b[1]) < 1e-6
        assert _angle(_tangents(a)[1], _tangents(b)[0]) < 0.6


def test_two_points_make_one_line():
    assert spline_path([(0, 0), (7, 3)]) == [("line", (0, 0), (7, 3))]


def test_collinear_points_stay_straight():
    assert all(i[0] == "line" for i in spline_path([(0, 0), (4, 0), (9, 0)]))


def test_end_directions():
    """start / end directions make the curve leave and arrive as asked (out of a pad, into a via)."""
    items = spline_path([(0, 0), (10, 6)], start=(1, 0), end=(1, 0))
    assert _angle(_tangents(items[0])[0], (1, 0)) < 0.6
    assert _angle(_tangents(items[-1])[1], (1, 0)) < 0.6
