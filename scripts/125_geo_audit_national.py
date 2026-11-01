# -*- coding: utf-8 -*-
"""
125：全国坐标质量硬检验——第四批村点位是否落在其所属县界多边形内
县界来自 DataV.GeoAtlas 公开边界服务（123 已缓存）
输出 data/master/geo_audit_national.csv
"""
import csv, sys, os, re, json, math, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
CACHE = os.path.join(ROOT, 'data', 'geo', 'datav_cache')

cc = list(csv.DictReader(open(os.path.join(D, 'geo', 'county_center_national.csv'),
                              encoding='utf-8-sig')))
m = list(csv.DictReader(open(os.path.join(D, 'master', 'master_final_1598.csv'),
                            encoding='utf-8-sig')))


def core(s):
    s = re.sub(r'\s', '', s or '')
    s = re.sub(r'(自治县|自治旗|特区|林区)$', '', s)
    s = re.sub(r'[市县区旗]$', '', s)
    return s


MAP = {('云南省', '怒江州贡山县'): '贡山独龙族怒族自治县',
       ('四川省', '宜宾县'): '叙州区', ('山东省', '莱城区'): '莱芜区',
       ('山东省', '蒙山旅游区'): '平邑县', ('山西省', '大同县'): '云州区',
       ('山西省', '长治县'): '上党区', ('湖南省', '汩罗市'): '汨罗市',
       ('贵州省', '安顺经济技术开发区'): '西秀区'}
idx = {}
for r in cc:
    idx.setdefault((r['province'], core(r['county'])), r)


def city_file(adcode):
    a = str(adcode)
    for cand in [a[:4] + '00', a[:2] + '0000']:
        p = os.path.join(CACHE, cand + '.json')
        if os.path.exists(p):
            return p
    return None


def load_poly(adcode):
    p = city_file(adcode)
    if not p:
        return None
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception:
        return None
    for f in d.get('features', []):
        if str(f['properties'].get('adcode')) == str(adcode):
            return f['geometry']
    return None


def rings(geom):
    if not geom:
        return []
    t, cs = geom.get('type'), geom.get('coordinates', [])
    if t == 'Polygon':
        return cs
    if t == 'MultiPolygon':
        return [r for poly in cs for r in poly]
    return []


def in_ring(pt, ring):
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def dist_to_ring(pt, ring):
    x, y = pt
    best = 1e9
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        dx, dy = x2 - x1, y2 - y1
        t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy) if (dx or dy) else 0
        t = max(0, min(1, t))
        px, py = x1 + t * dx, y1 + t * dy
        d = math.hypot(x - px, y - py)
        best = min(best, d)
    return best * 111.32 * math.cos(math.radians(y))


rows = []
no_poly = []
for r in m:
    if not r['latitude']:
        rows.append({'village_id': r['village_id'], 'result': 'no_coord', 'dist_km': ''})
        continue
    key = (r['province'], core(r['county']))
    rec0 = idx.get(key)
    if rec0 is None and (r['province'], r['county']) in MAP:
        rec0 = idx.get((r['province'], core(MAP[(r['province'], r['county'])])))
    if rec0 is None:
        rows.append({'village_id': r['village_id'], 'result': 'no_county', 'dist_km': ''})
        no_poly.append((r['province'], r['county']))
        continue
    geom = load_poly(rec0['adcode'])
    if geom is None:
        rows.append({'village_id': r['village_id'], 'result': 'no_polygon', 'dist_km': ''})
        no_poly.append((r['province'], r['county']))
        continue
    pt = (float(r['longitude']), float(r['latitude']))
    rs = rings(geom)
    inside = any(in_ring(pt, rg) for rg in rs)
    if inside:
        rows.append({'village_id': r['village_id'], 'result': 'inside', 'dist_km': 0})
    else:
        d = min((dist_to_ring(pt, rg) for rg in rs), default=999)
        rows.append({'village_id': r['village_id'], 'result': 'outside', 'dist_km': round(d, 2)})

with open(os.path.join(D, 'master', 'geo_audit_national.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['village_id', 'result', 'dist_km'])
    w.writeheader()
    w.writerows(rows)

print(collections.Counter(r['result'] for r in rows))
out = [r for r in rows if r['result'] == 'outside']
print('界外 %d 条，其中距县界 >5 km 的 %d 条' % (len(out), sum(1 for r in out if float(r['dist_km']) > 5)))
by = {r['village_id']: r for r in rows}
mm = {r['village_id']: r for r in m}
for r in sorted(out, key=lambda x: -float(x['dist_km']))[:20]:
    v = mm[r['village_id']]
    print('   %-8s %-10s %-24s 距界 %s km' % (v['province'], v['county'], v['village'], r['dist_km']))
if no_poly:
    print('无县界可用 %d 条，涉及县 %d 个' % (len(no_poly), len(set(no_poly))))
