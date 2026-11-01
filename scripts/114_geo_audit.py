# -*- coding: utf-8 -*-
"""坐标质量硬检验（公开数据自洽性，不依赖任何商业地图服务）

检验 1  点位是否落在所属县级行政边界内（DataV.GeoAtlas 公开边界 + ray casting）
检验 2  同乡镇村点最小间距（识别"以上一级行政单位位置替代"的批量替代）
检验 3  高程异常（SRTM/ASTER 缺失值、海拔 0 或负值、两数据集分歧）
检验 4  点位到县中心距离的极端值
"""
import csv, json, os, sys, math, collections

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
DATAV = 'data/geo/datav'

# ---------- 读县界 ----------
polys = {}    # (prov, county) -> list of rings (list of (lon,lat))
PROV = {'浙江省': 330000, '安徽省': 340000, '江苏省': 320000}
for prov, ad in PROV.items():
    d = json.load(open(os.path.join(DATAV, '%d_full.json' % ad), encoding='utf-8'))
    for f in d['features']:
        p = f['properties']
        if p['level'] != 'city':
            continue
        cad = p['adcode']
        fp = os.path.join(DATAV, '%d_full.json' % cad)
        if not os.path.exists(fp):
            continue
        dd = json.load(open(fp, encoding='utf-8'))
        for g in dd['features']:
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
print('可检验县界：%d 个' % len(polys))


def in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-18) + xi):
            inside = not inside
        j = i
    return inside


def in_poly(lon, lat, rings):
    for r in rings:
        if in_ring(lon, lat, r):
            return True
    return False


# ---------- 检验 1：点是否落在所属县界内 ----------
print()
print('== 检验 1：村点是否落在所属县级边界内 ==')
bad = []
tested = 0
for r in rows:
    k = (r['province'], r['county'])
    lon, lat = float(r['longitude']), float(r['latitude'])
    if k not in polys:
        continue
    tested += 1
    if not in_poly(lon, lat, polys[k]):
        # 找实际落在哪个县
        hit = [kk for kk in polys if in_poly(lon, lat, polys[kk])]
        bad.append((r, hit))
print('可检验 %d 村；落在县界外 %d 村' % (tested, len(bad)))
for r, hit in bad:
    print('   ⚠ %s %s %s (%.5f,%.5f) 实际落在 %s' % (
        r['county'], r['township'], r['village'], float(r['longitude']), float(r['latitude']),
        ','.join('%s%s' % (h[0][:2], h[1]) for h in hit) or '未命中任何县'))

# ---------- 检验 2：同乡镇村点最小间距 ----------
print()
print('== 检验 2：同乡镇村点最小间距（上级单位位置替代嫌疑）==')


def hav(lat1, lon1, lat2, lon2):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
    return 2 * R * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                       math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


by_town = collections.defaultdict(list)
for r in rows:
    by_town[(r['province'], r['county'], r['township'])].append(r)
suspect = []
for k, g in by_town.items():
    if len(g) < 2:
        continue
    md = min(hav(float(a['latitude']), float(a['longitude']),
                 float(b['latitude']), float(b['longitude']))
             for i, a in enumerate(g) for b in g[i + 1:])
    if md < 0.15:      # 小于 150 米
        suspect.append((k, len(g), md))
print('含 2 村以上的乡镇：%d；最小间距 <150 m 的乡镇：%d' % (
    sum(1 for g in by_town.values() if len(g) >= 2), len(suspect)))
for k, n, md in sorted(suspect, key=lambda x: x[2]):
    print('   ⚠ %s %s %s：%d 村，最近两村相距 %.0f m' % (k[0][:2], k[1], k[2], n, md * 1000))

# ---------- 检验 3：高程异常 ----------
print()
print('== 检验 3：高程异常 ==')
anom = []
for r in rows:
    e = r['elev_srtm30']
    a = r['elev_aster30']
    if e == '' or a == '':
        anom.append((r, '缺失'))
        continue
    fe, fa = float(e), float(a)
    if fe <= 0 or fe > 3000:
        anom.append((r, '海拔异常 %.0f' % fe))
    elif abs(fe - fa) > 50:
        anom.append((r, '两数据集差 %.0f m' % abs(fe - fa)))
print('异常条目：%d' % len(anom))
for r, why in anom[:15]:
    print('   %s %s %s：%s（srtm %s / aster %s）' % (r['county'], r['township'], r['village'], why,
                                                 r['elev_srtm30'], r['elev_aster30']))
neg = [r for r in rows if r['elev_srtm30'] != '' and float(r['elev_srtm30']) <= 0]
print('海拔 ≤0 的村：%d' % len(neg))

# ---------- 检验 4：距离极端值 ----------
print()
print('== 检验 4：到县城距离极端值（前 8）==')
ds = sorted(rows, key=lambda r: -float(r['dist_county_km']))[:8]
for r in ds:
    print('   %-6s %-8s %-10s %.1f km  海拔 %.0f m  %s' % (
        r['province'][:2], r['county'], r['village'], float(r['dist_county_km']),
        float(r['elev_srtm30']), r['status']))

# ---------- 汇总 ----------
print()
print('== 结论 ==')
print('样本 %d 村；县界检验通过 %d/%d；上级单位替代嫌疑乡镇 %d；高程异常 %d' % (
    len(rows), tested - len(bad), tested, len(suspect), len(anom)))
