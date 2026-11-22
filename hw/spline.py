"""Smooth curves for tracks: a centripetal Catmull-Rom spline through the waypoints, written as lines and
arcs that join without a corner (biarcs), because KiCad tracks can only be straight or circular.

    spline_path([(x, y), ...], start=None, end=None) -> [("line", a, b) | ("arc", a, mid, b), ...]

start / end: optional direction vectors the curve leaves its first point and arrives at its last point with.
"""
from __future__ import annotations

import math

STRAIGHT = 1e-4      # sagitta below this fraction of the chord: draw it as a line
PIECES = 4           # biarcs per span between two waypoints


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _tangent(a, b, c):
    """Direction of the centripetal Catmull-Rom spline at b, between a and c."""
    t1, t2 = math.sqrt(math.dist(a, b)), math.sqrt(math.dist(b, c))
    return tuple((b[k] - a[k]) / t1 - (c[k] - a[k]) / (t1 + t2) + (c[k] - b[k]) / t2 for k in (0, 1))


def _hermite(p0, m0, p1, m1, u):
    """Point and direction on the cubic Hermite curve at u in 0..1."""
    a, b, c, d = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u, -2 * u**3 + 3 * u**2, u**3 - u**2
    e, f, g, h = 6 * u**2 - 6 * u, 3 * u**2 - 4 * u + 1, -6 * u**2 + 6 * u, 3 * u**2 - 2 * u
    return (tuple(a * p0[k] + b * m0[k] + c * p1[k] + d * m1[k] for k in (0, 1)),
            tuple(e * p0[k] + f * m0[k] + g * p1[k] + h * m1[k] for k in (0, 1)))


def _arc(a, ta, b):
    """Arc (or line) from a, leaving in direction ta, to b."""
    chord = math.dist(a, b)
    if chord < 1e-9:
        return None
    u = _unit((b[0] - a[0], b[1] - a[1]))
    cross, dot = ta[0] * u[1] - ta[1] * u[0], ta[0] * u[0] + ta[1] * u[1]
    half = math.atan2(cross, dot)                     # half the arc's turn
    sag = chord / 2 * math.tan(half / 2)              # positive: the arc bulges to the right of a -> b
    if abs(sag) < STRAIGHT * chord:
        return ("line", a, b)
    mid = ((a[0] + b[0]) / 2 + u[1] * sag, (a[1] + b[1]) / 2 - u[0] * sag)
    return ("arc", a, mid, b)


def _biarc(p0, t0, p1, t1):
    """Two arcs from p0 (direction t0) to p1 (direction t1), joined without a corner."""
    v = (p1[0] - p0[0], p1[1] - p0[1])
    s = (t0[0] + t1[0], t0[1] + t1[1])
    vv, vs, tt = v[0] ** 2 + v[1] ** 2, v[0] * s[0] + v[1] * s[1], 2 * (1 - (t0[0] * t1[0] + t0[1] * t1[1]))
    d = vv / (2 * vs) if tt < 1e-12 else (-vs + math.sqrt(vs * vs + tt * vv)) / tt
    j = ((p0[0] + p1[0] + d * (t0[0] - t1[0])) / 2, (p0[1] + p1[1] + d * (t0[1] - t1[1])) / 2)
    tj = (v[0] - d * s[0], v[1] - d * s[1])           # along the two control points, through the joint
    tj = _unit(tj) if math.hypot(*tj) > 1e-9 else t0
    return [x for x in (_arc(p0, t0, j), _arc(j, tj, p1)) if x]


def spline_path(pts, start=None, end=None):
    pts = [tuple(p) for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-9]
    n = len(pts)
    if n == 2 and not start and not end:
        return [("line", pts[0], pts[1])]
    # directions at the waypoints; at the ends the curve starts out along a mirrored neighbour's direction
    tans = [None] * n
    for i in range(1, n - 1):
        tans[i] = _unit(_tangent(pts[i - 1], pts[i], pts[i + 1]))

    def end_dir(p, q, tq):
        """Direction at p so that p -> q is a single arc arriving in direction tq."""
        u = _unit((q[0] - p[0], q[1] - p[1]))
        if tq is None:
            return u
        dot = tq[0] * u[0] + tq[1] * u[1]
        return (2 * dot * u[0] - tq[0], 2 * dot * u[1] - tq[1])

    tans[0] = _unit(start) if start else _unit(end_dir(pts[0], pts[1], tans[1] if n > 2 else (_unit(end) if end else None)))
    if end:
        tans[-1] = _unit(end)
    else:
        prev = tans[-2]
        u = _unit((pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]))
        dot = prev[0] * u[0] + prev[1] * u[1]
        tans[-1] = _unit((2 * dot * u[0] - prev[0], 2 * dot * u[1] - prev[1]))
    out = []
    for i in range(n - 1):
        p0, p1 = pts[i], pts[i + 1]
        length = math.dist(p0, p1)
        m0, m1 = tuple(length * c for c in tans[i]), tuple(length * c for c in tans[i + 1])
        prev_p, prev_t = p0, tans[i]
        for k in range(1, PIECES + 1):
            if k == PIECES:
                q, tq = p1, tans[i + 1]
            else:
                q, dq = _hermite(p0, m0, p1, m1, k / PIECES)
                tq = _unit(dq)
            out += _biarc(prev_p, prev_t, q, tq)
            prev_p, prev_t = q, tq
    return out
