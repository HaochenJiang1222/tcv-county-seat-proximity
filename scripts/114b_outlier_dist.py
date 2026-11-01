# -*- coding: utf-8 -*-
"""对落在县界外的点位，量化其到所属县边界的最短距离（判断是边界简化误差还是坐标错误）"""
import csv, json, os, sys, math

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
DATAV = 'data/geo/datav'
rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))

polys = {}
PROV = {'浙江省': 330000, '安徽省': 340000}
for prov, ad in PROV.items():
    d = json.load(open(os.path.join(DATAV, '%d_full.json' % ad), encoding='utf-8'))
    for f in d['features']:
        if f['properties']['level'] != 'city':
            continue
        fp = os.path.join(DATAV, '%d_full.json' % f['properties']['adcode'])
        if not os.path.exists(fp):
            continue
        for g in json.load(open(fp, encoding='utf-8'))['features']:
            q = g['properties']
            if q['level'] not in ('district', 'county'):
                continue
            geom = g.get('geometry') or {}
            rings = []
            if geom.get('type') == 'Polygon':
                rings = geom['coordinates']
            elif geom.get('type') == 'MultiPolygon':
                for poly in geom['coordinates']:
                    rings.extend(poly)
            if rings:
                polys[(prov, q['name'])] = rings


def hav(lat1, lon1, lat2, lon2):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
    return 2 * R * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                       math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


def seg_km(lat, lon, a, b):
    """点到线段最短距离（等距圆柱近似，尺度小）"""
    kx = 111.32 * math.cos(math.radians(lat))
    ky = 110.57
    px, py = lon * kx, lat * ky
    ax, ay = a[0] * kx, a[1] * ky
    bx, by = b[0] * kx, b[1] * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_to_rings(lat, lon, rings):
    best = 1e9
    for r in rings:
        for i in range(len(r)):
            d = seg_km(lat, lon, r[i], r[(i + 1) % len(r)])
            best = min(best, d)
    return best


def in_poly(lat, lon, rings):
    for ring in rings:
        n = len(ring); j = n - 1; ins = False
        for i in range(n):
            xi, yi = ring[i]; xj, yj = ring[j]
            if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-18) + xi):
                ins = not ins
            j = i
        if ins:
            return True
    return False


TARGETS = []
for r in rows:
    k = (r['province'], r['county'])
    if k in polys and not in_poly(float(r['latitude']), float(r['longitude']), polys[k]):
        TARGETS.append(r)
print('界外村 %d 个' % len(TARGETS))
for r in TARGETS:
    ct = r['county']
    lat, lon = float(r['latitude']), float(r['longitude'])
    own = polys.get((r['province'], ct))
    d_own = dist_to_rings(lat, lon, own) if own else float('nan')
    # 实际落入的县
    hits = []
    for k, rings in polys.items():
        # 简化：用最近边界距离 + 是否在内部（复用 ray casting）
        inside = False
        for ring in rings:
            n = len(ring); j = n - 1; ins = False
            for i in range(n):
                xi, yi = ring[i]; xj, yj = ring[j]
                if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-18) + xi):
                    ins = not ins
                j = i
            if ins:
                inside = True; break
        if inside:
            hits.append(k)
    print('%s %s %s  [%s]' % (r['province'][:2], ct, r['village'], r['status']))
    print('   点位 %.5f, %.5f  海拔 %s m' % (lon, lat, r['elev_srtm30']))
    print('   到所属县界最短 %.2f km；到县城中心 %s km' % (d_own, r['dist_county_km']))
    for k in hits:
        d2 = dist_to_rings(lat, lon, polys[k])
        print('   实际落入 %s%s，到该县界 %.2f km' % (k[0][:2], k[1], d2))
    print()
