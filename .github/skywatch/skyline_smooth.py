#!/usr/bin/env python3
"""Smooth the traced downtown skyline and merge day + night into ONE aligned drawing.

Inputs (kept in this folder so the build is repeatable):
  skyline_src_day.html   - the detailed day trace (14 flat colours + ink layer)
  skyline_src_night.html - the night trace (its lit windows and crowns are reused)

What it does:
  1. Every traced shape is cleaned like a vector drawing: pixel stair-steps removed
     (Douglas-Peucker), near-vertical/near-horizontal edges snapped straight,
     crumbs dropped. All colours and shapes are kept, so the detail stays.
  2. Salesforce Tower gets a clean tapered shaft and its rounded crown back.
  3. Day and night share the same shapes: the night is the day drawing recoloured
     by CSS, and the night skyline's lit windows (drawn by Fable from another agent's rendering) are moved onto it (aligned on
     Salesforce Tower and the Transamerica Pyramid) and clipped to the buildings.
  4. data-sky (top edge every 10 viewBox units) is recomputed for the jets.

Run:  python3 .github/skywatch/skyline_smooth.py > /tmp/skyline.html   (pip install shapely numpy)
"""
import math, os, re, sys
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.abspath(__file__))

def paths(svg):
    out = []
    for m in re.finditer(r'<path ([^>]*?)d="([^"]*)"([^>]*)>', svg):
        out.append((dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1) + m.group(3))), m.group(2)))
    return out

def rings(d):
    res = []
    for sub in re.findall(r'M[^M]*', d):
        toks = re.findall(r'[MmHhVvZzLl]|-?[\d.]+', sub); pts = []; x = y = 0; i = 0; cmd = 'M'
        while i < len(toks):
            t = toks[i]
            if t.isalpha(): cmd = t; i += 1
            if cmd in 'Zz' or i >= len(toks): break
            if cmd in 'ML': x, y = float(toks[i]), float(toks[i + 1]); i += 2
            elif cmd == 'h': x += float(toks[i]); i += 1
            elif cmd == 'v': y += float(toks[i]); i += 1
            elif cmd == 'H': x = float(toks[i]); i += 1
            elif cmd == 'V': y = float(toks[i]); i += 1
            pts.append((x, y))
        if len(pts) >= 3: res.append(pts)
    return res

def rdp(P, eps):
    n = len(P)
    if n < 3: return P
    keep = np.zeros(n, bool); keep[0] = keep[-1] = True; st = [(0, n - 1)]
    while st:
        a, b = st.pop()
        if b <= a + 1: continue
        A, B = P[a], P[b]; v = B - A; L = math.hypot(*v); seg = P[a + 1:b]
        d = np.abs(v[0] * (seg[:, 1] - A[1]) - v[1] * (seg[:, 0] - A[0])) / L if L > 0 else np.hypot(*(seg - A).T)
        i = int(d.argmax())
        if d[i] > eps: k = a + 1 + i; keep[k] = True; st += [(a, k), (k, b)]
    return P[keep]

def ring_rdp(P, eps):
    j = int(np.hypot(*(P - P[0]).T).argmax())
    a = rdp(P[:j + 1], eps); b = rdp(np.vstack([P[j:], P[:1]]), eps)
    return np.vstack([a, b[1:-1]])

def snap(P, tol=.5, mx=2.6):
    P = P.copy(); n = len(P)
    for _ in range(3):
        for i in range(n):
            j = (i + 1) % n; dx, dy = abs(P[j, 0] - P[i, 0]), abs(P[j, 1] - P[i, 1])
            if dx < mx and dx <= tol * dy: P[i, 0] = P[j, 0] = (P[i, 0] + P[j, 0]) / 2
            elif dy < mx and dy <= tol * dx: P[i, 1] = P[j, 1] = (P[i, 1] + P[j, 1]) / 2
    return P

def clean(d, eps, minarea):
    polys = []
    for r in rings(d):
        P = np.array(r, float)
        if Polygon(P).area < minarea: continue
        P = ring_rdp(P, eps)
        if len(P) < 3: continue
        P = np.round(snap(P), 1)
        if len(P) > 3: P = ring_rdp(P, .06)
        P = np.array([q for i, q in enumerate(P) if i == 0 or (q != P[i - 1]).any()])
        if len(np.unique(P, axis=0)) < 3: continue
        g = make_valid(Polygon(P))
        g = unary_union([x for x in getattr(g, 'geoms', [g]) if x.geom_type in ('Polygon', 'MultiPolygon')]) if g.geom_type == 'GeometryCollection' else g
        if g.area >= minarea: polys.append(g)
    return polys

def fmt(v):
    s = f"{v:.1f}"; s = s[:-2] if s.endswith('.0') else s
    return '0' if s == '-0' else s

def to_d(geoms):
    out = []
    for g in geoms:
        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
            if p.is_empty or p.geom_type != 'Polygon' or p.area < .05: continue
            p = orient(p, 1)
            for ring in [p.exterior] + list(p.interiors):
                c = list(ring.coords)[:-1]
                out.append('M' + ' '.join(f'{fmt(x)} {fmt(y)}' for x, y in c) + 'Z')
    return ''.join(out)

day = open(os.path.join(HERE, 'skyline_src_day.html')).read()
night = open(os.path.join(HERE, 'skyline_src_night.html')).read()

layers = []
for a, d in paths(day):
    ink = 'fill-opacity' in a or 'opacity' in a
    layers.append({'fill': a['fill'], 'ink': ink, 'op': a.get('opacity'),
                   'g': clean(d, .5 if ink else .9, .25 if ink else .5)})

# ---- Salesforce Tower: clean shaft + rounded crown (measured from the trace) ----
cx, top, shoulder = 196.6, 112.4, 121.5
pts = [(188.9, 156), (189.9, shoulder)]
for i in range(1, 24):
    t = math.pi - i * math.pi / 24
    hw = 6.5
    pts.append((cx + hw * math.cos(t), shoulder - (shoulder - top) * math.sin(t) ** .8))
pts += [(203.3, shoulder), (204.3, 156)]
sf = Polygon(pts)
region = box(184, 100, 209, 152)
for L in layers:
    L['g'] = [g.difference(region).union(g.intersection(region).intersection(sf)) for g in L['g']]
base = next(L for L in layers if L['fill'] == '#5c7491')
base['g'].insert(0, sf.intersection(region))
# a soft glass highlight down the sunlit edge and a pale crown band
facet = Polygon([(190, 152), (190.9, shoulder), (192.4, shoulder - 3.2), (192.4, 152)])
crown = Polygon([(cx + 6.1 * math.cos(math.pi - i * math.pi / 24), shoulder - .3 - (shoulder - top - .5) * math.sin(math.pi - i * math.pi / 24) ** .8) for i in range(25)] +
                [(202.8, shoulder - 1), (190.4, shoulder - 1)])

mass = unary_union([g for L in layers if not L['ink'] for g in L['g']])

# ---- night windows: night lights moved onto the day drawing ----
# anchors (traced tops): Salesforce 181.0 -> 196.5, Transamerica 430.5 -> 433.0
ax = (433.0 - 196.5) / (430.5 - 181.0); bx = 196.5 - ax * 181.0
inner = mass.buffer(-.25)
lights = []
for a, d in paths(night):
    if a.get('class') != 'lt': continue
    gs = []
    for r in rings(d):
        g = make_valid(Polygon([(ax * x + bx, y) for x, y in r]))
        g = g.intersection(inner)
        if g.area > .08: gs.append(g)
    lights.append((a['fill'], gs))

# ---- data-sky for the jets ----
sky = []
for k in range(61):
    s = mass.intersection(box(k * 10 - 5, 0, k * 10 + 5, 230))
    sky.append(230 if s.is_empty else int(math.floor(s.bounds[1])) - 2)

# ---- output: one SVG, classes per colour so CSS recolours it for night ----
svg = ['<svg viewBox="0 0 600 230" preserveAspectRatio="xMidYMax meet" shape-rendering="geometricPrecision" '
       f'data-sky="{",".join(map(str, sky))}" aria-hidden="true">']
cls = {}
for L in layers:
    if L['ink']:
        svg.append(f'<path class="sk-ink" d="{to_d(L["g"])}"/>'); continue
    c = cls.setdefault(L['fill'], f'k{len(cls)}')
    svg.append(f'<path class="{c}" d="{to_d(L["g"])}"/>')
svg.append(f'<path class="sk-facet" d="{to_d([facet])}"/><path class="sk-crown" d="{to_d([crown])}"/>')
svg.append('<g class="sk-lights">' + ''.join(f'<path fill="{f}" d="{to_d(g)}"/>' for f, g in lights if g) + '</g>')
svg.append(f'<circle class="beacon" cx="{cx}" cy="{top - 1.3}" r="1.5"/></svg>')
print('<div class="skyline" aria-hidden="true">' + ''.join(svg) + '</div>')
# palette for the CSS (day colour -> class), printed to stderr
print(' '.join(f'{c}:{f}' for f, c in cls.items()), file=sys.stderr)
