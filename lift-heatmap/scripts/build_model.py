#!/usr/bin/env python3
"""Build assets/muscles-<body>.bin from the BodyParts3D muscle meshes. Python standard library only.

Usage:
  python3 scripts/build_model.py --body female --download
  python3 scripts/build_model.py --body male --src path/to/BodyParts3D/assets/BodyParts3D_data/stl

--download fetches the 214 STL files (about 560 MB) from a pinned commit of
https://github.com/Kevin-Mattheus-Moerman/BodyParts3D into --cache, and reuses them on the next run.
Parts and triangle budgets: references/model-parts.tsv. Body proportions: references/body-shapes.json.

Output format: uint32 header length, JSON header [{k, n, s, nv, nf, lo, ex, po, io}], then per part
uint16 positions quantized to the part's box (lo, ex) and uint16 triangle indices.
"""
import argparse
import bisect
import json
import os
import struct
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMIT = 'f0eeb6e843380cfe6b83797cf8c3e1af74de5e61'
URL = 'https://raw.githubusercontent.com/Kevin-Mattheus-Moerman/BodyParts3D/%s/assets/BodyParts3D_data/stl/%s.stl'


def read_parts():
    parts = []
    for line in open(os.path.join(ROOT, 'references', 'model-parts.tsv')):
        if line.startswith('#') or not line.strip():
            continue
        fid, key, side, faces, name = line.rstrip('\n').split('\t')
        parts.append({'id': fid, 'k': key, 's': side, 'faces': int(faces), 'n': name})
    return parts


def fetch(fid, cache):
    path = os.path.join(cache, fid + '.stl')
    if not os.path.exists(path):
        tmp = path + '.part'
        urllib.request.urlretrieve(URL % (COMMIT, fid), tmp)
        os.replace(tmp, path)
    return path


def read_stl(path):
    """Binary STL -> (welded vertices, triangles)."""
    d = open(path, 'rb').read()
    n = struct.unpack_from('<I', d, 80)[0]
    if len(d) != 84 + 50 * n:
        raise SystemExit('%s is not a binary STL' % path)
    index, verts, tris = {}, [], []
    for t in range(n):
        v = struct.unpack_from('<9f', d, 96 + 50 * t)
        tri = []
        for j in (0, 3, 6):
            p = v[j:j + 3]
            i = index.get(p)
            if i is None:
                i = index[p] = len(verts)
                verts.append(p)
            tri.append(i)
        tris.append(tri)
    return verts, tris


def cluster(verts, tris, h):
    """Vertex clustering on a grid of cell size h. Returns (cell of each vertex, kept triangles)."""
    cells, cell_of = {}, []
    for x, y, z in verts:
        c = (int(x // h), int(y // h), int(z // h))
        cell_of.append(cells.setdefault(c, len(cells)))
    seen, out = set(), []
    for a, b, c in tris:
        a, b, c = cell_of[a], cell_of[b], cell_of[c]
        if a == b or b == c or a == c:
            continue
        s = tuple(sorted((a, b, c)))
        if s not in seen:
            seen.add(s)
            out.append((a, b, c))
    return cell_of, out


def simplify(verts, tris, faces):
    """Pick the largest cell size that keeps at least `faces` triangles (bisection on a log scale)."""
    ext = max(max(v[a] for v in verts) - min(v[a] for v in verts) for a in range(3))
    lo, hi = ext / 2000, ext / 2
    best = cluster(verts, tris, lo)
    for _ in range(14):
        h = (lo * hi) ** 0.5
        res = cluster(verts, tris, h)
        if len(res[1]) >= faces:
            lo, best = h, res
        else:
            hi = h
    cell_of, out = best
    # cell position = mean of its vertices; keep only cells used by a triangle
    n = max(cell_of) + 1
    acc = [[0.0, 0.0, 0.0, 0] for _ in range(n)]
    for v, c in zip(verts, cell_of):
        a = acc[c]
        a[0] += v[0]; a[1] += v[1]; a[2] += v[2]; a[3] += 1
    used = sorted(set(i for t in out for i in t))
    remap = {c: i for i, c in enumerate(used)}
    pos = [(acc[c][0] / acc[c][3], acc[c][1] / acc[c][3], acc[c][2] / acc[c][3]) for c in used]
    return pos, [tuple(remap[i] for i in t) for t in out]


def width_at(table, y):
    hs = [p[0] for p in table]
    i = bisect.bisect_right(hs, y)
    if i == 0:
        return table[0][1]
    if i == len(table):
        return table[-1][1]
    (h0, w0), (h1, w1) = table[i - 1], table[i]
    return w0 + (w1 - w0) * (y - h0) / (h1 - h0)


def place(pos, shape, body):
    k, zo, table = shape['scale'], shape['z_offset'], shape['width'][body]
    out = []
    for x, y, z in pos:
        yy = z / 1000 * k
        out.append((x / 1000 * k * width_at(table, yy), yy, -y / 1000 * k + zo))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--body', choices=['female', 'male'], required=True)
    ap.add_argument('--src', help='folder with the BodyParts3D STL files (<id>.stl)')
    ap.add_argument('--download', action='store_true', help='download the STL files into --cache')
    ap.add_argument('--cache', default=os.path.join(os.path.expanduser('~'), '.cache', 'lift-heatmap', 'bodyparts3d'))
    ap.add_argument('--out')
    a = ap.parse_args()
    if not a.src and not a.download:
        raise SystemExit('give --src <folder> or --download')
    if a.download:
        os.makedirs(a.cache, exist_ok=True)
    out = a.out or os.path.join(ROOT, 'assets', 'muscles-%s.bin' % a.body)

    shape = json.load(open(os.path.join(ROOT, 'references', 'body-shapes.json')))
    parts = read_parts()
    meta, blob = [], bytearray()
    for i, p in enumerate(parts):
        path = fetch(p['id'], a.cache) if a.download else os.path.join(a.src, p['id'] + '.stl')
        verts, tris = read_stl(path)
        pos, tri = simplify(verts, tris, p['faces'])
        pos = place(pos, shape, a.body)
        lo = [round(min(v[j] for v in pos), 5) for j in range(3)]
        ex = [round(max(v[j] for v in pos) - lo[j], 5) or 1e-5 for j in range(3)]
        q = [max(0, min(65535, round((v[j] - lo[j]) / ex[j] * 65535))) for v in pos for j in range(3)]
        po = len(blob)
        blob += struct.pack('<%dH' % len(q), *q)
        io = len(blob)
        blob += struct.pack('<%dH' % (3 * len(tri)), *[j for t in tri for j in t])
        meta.append({'k': p['k'], 'n': p['n'], 's': p['s'], 'nv': len(pos), 'nf': len(tri), 'lo': lo, 'ex': ex, 'po': po, 'io': io})
        sys.stdout.write('\r%d/%d parts' % (i + 1, len(parts)))
        sys.stdout.flush()
    head = json.dumps(meta, separators=(',', ':')).encode()
    with open(out, 'wb') as f:
        f.write(struct.pack('<I', len(head)) + head + bytes(blob))
    print('\nwrote', out, sum(m['nf'] for m in meta), 'triangles')


if __name__ == '__main__':
    main()
