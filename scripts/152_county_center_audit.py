# -*- coding: utf-8 -*-
"""
152：县级「中心」坐标的定义核验（审稿 R2 第二项高风险）

问题：正文把 dist 解释为「到县级行政中心的距离」，但程序读的是
DataV.GeoAtlas areas_v3 的 properties.center 字段。center 可能是
①政府驻地/行政中心点 ②地图服务给定的标注点 ③多边形几何质心。
三者是不同空间概念，必须核验而不是默认等价。

本脚本做四件事：
T1 字段自洽：DataV 自带 centroid 字段 vs 用边界几何自行计算的质心，验证算法
T2 中心 vs 质心：center 与（自算）几何质心的直线距离分布
T3 内部性：center 是否落在本县边界多边形内（质心不一定落在多边形内）
T4 使用范围：只统计实际进入估计的县（601 个县 / 1,596 村）

输出 data/geo/county_center_audit.csv、data/master/county_center_audit.txt
"""
import json, os, csv, math, glob, sys, collections
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CACHE = os.path.join('data', 'geo', 'datav_cache')

# ---------- 几何工具 ----------
def ring_area(r):
    # 平面近似（度），仅用于面积加权；相对权重在县内比较中足够
    s = 0.0
    n = len(r)
    for i in range(n - 1):
        x1, y1 = r[i][0], r[i][1]
        x2, y2 = r[i + 1][0], r[i + 1][1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def ring_centroid(r):
    a = ring_area(r)
    if abs(a) < 1e-14:
        return 0.0, 0.0, 0.0
    cx = cy = 0.0
    n = len(r)
    for i in range(n - 1):
        x1, y1 = r[i][0], r[i][1]
        x2, y2 = r[i + 1][0], r[i + 1][1]
        f = x1 * y2 - x2 * y1
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    # 标准多边形质心：C = 1/(6A) * Σ (p_i + p_{i+1}) * cross_i，A 为带符号面积
    return cx / (6 * a), cy / (6 * a), a


def poly_centroid(geom):
    """返回 (cx, cy, area)：按带符号面积加权，外环减内环"""
    t = geom['type']
    coords = geom['coordinates']
    if t == 'Polygon':
        polys = [coords]
    elif t == 'MultiPolygon':
        polys = coords
    else:
        return None
    tx = ty = 0.0
    tot = 0.0
    for poly in polys:
        for k, ring in enumerate(poly):
            cx, cy, a = ring_centroid(ring)
            sgn = 1.0 if k == 0 else -1.0
            if a == 0:
                continue
            aa = abs(a) * sgn
            tx += cx * aa
            ty += cy * aa
            tot += aa
    if abs(tot) < 1e-14:
        return None
    return tx / tot, ty / tot, abs(tot)


def inside(geom, x, y):
    t = geom['type']
    coords = geom['coordinates']
    polys = [coords] if t == 'Polygon' else coords if t == 'MultiPolygon' else []
    cnt = 0
    for poly in polys:
        ring = poly[0]
        n = len(ring)
        c = False
        j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-18) + xi):
                c = not c
            j = i
        if c:
            cnt += 1
    # 内环处理（简化：仅外环判定，内环极少影响县城点位）
    return cnt > 0


def hav(lon1, lat1, lon2, lat2, R=6371.0088):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------- 1 扫描缓存，取全部县级 feature 的 center / centroid / geometry ----------
feat = {}
for p in glob.glob(os.path.join(CACHE, '*.json')):
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception:
        continue
    for f in d.get('features', []):
        pr = f.get('properties', {})
        ad = str(pr.get('adcode', ''))
        if not ad or pr.get('level') not in ('district', 'city', 'province'):
            continue
        if ad.endswith('0000') or (ad.endswith('00') and len(ad) == 6 and not ad.endswith('9000')):
            # 省级、地级本身跳过（除非是直辖县级汇总 9000 也跳过）
            continue
        if ad.endswith('9000'):
            continue
        if ad in feat:
            continue
        feat[ad] = {'name': pr.get('name'), 'center': pr.get('center'),
                    'centroid': pr.get('centroid'), 'geom': f.get('geometry'),
                    'level': pr.get('level'), 'parent': pr.get('parent')}
print('缓存中县级 feature：%d' % len(feat))

# ---------- 2 自算几何质心 ----------
rows = []
for ad, v in feat.items():
    c = v['center']
    ce = v['centroid']
    g = v['geom']
    pc = poly_centroid(g) if g else None
    if not c:
        continue
    row = {'adcode': ad, 'name': v['name'], 'level': v['level'],
           'lon_center': c[0], 'lat_center': c[1],
           'lon_centroid_field': ce[0] if ce else '', 'lat_centroid_field': ce[1] if ce else '',
           'lon_centroid_calc': round(pc[0], 6) if pc else '', 'lat_centroid_calc': round(pc[1], 6) if pc else ''}
    if ce:
        row['d_center_centroidfield'] = round(hav(c[0], c[1], ce[0], ce[1]), 3)
    else:
        row['d_center_centroidfield'] = ''
    if pc:
        row['d_center_calc'] = round(hav(c[0], c[1], pc[0], pc[1]), 3)
        row['d_field_calc'] = round(hav(ce[0], ce[1], pc[0], pc[1]), 3) if ce else ''
    else:
        row['d_center_calc'] = ''
        row['d_field_calc'] = ''
    try:
        row['center_in_poly'] = int(inside(g, c[0], c[1])) if g else ''
    except Exception:
        row['center_in_poly'] = ''
    try:
        row['centroid_in_poly'] = int(inside(g, ce[0], ce[1])) if (g and ce) else ''
    except Exception:
        row['centroid_in_poly'] = ''
    rows.append(row)
print('可核验县级条目：%d' % len(rows))

# ---------- 3 实际使用范围 ----------
master = list(csv.DictReader(open(os.path.join('data', 'master', 'master_final_1598.csv'),
                                  encoding='utf-8-sig')))
dist = list(csv.DictReader(open(os.path.join('data', 'master', 'dist_county_national.csv'),
                                encoding='utf-8-sig')))
vid2dist = {r['village_id']: r for r in dist}
used = collections.defaultdict(int)
vill_by_county = collections.defaultdict(list)
for m in master:
    if m['village_id'] in vid2dist:
        used[(m['province'], m['county'])] += 1
        vill_by_county[(m['province'], m['county'])].append(m['village_id'])

cc = list(csv.DictReader(open(os.path.join('data', 'geo', 'county_center_national.csv'),
                              encoding='utf-8-sig')))
idx = {(r['province'], r['county']): r['adcode'] for r in cc}
used_ad = {}
for (pv, ct), n in used.items():
    ad = idx.get((pv, ct))
    if ad:
        used_ad[str(ad)] = (pv, ct, n)
print('估计用县 %d 个（覆盖 %d 村），可定位到 adcode %d 个'
      % (len(used), sum(used.values()), len(used_ad)))

# ---------- 4 统计 ----------
lines = []
lines.append('=== 152 县级中心点定义核验（%s） ===' % __import__('datetime').date.today())
lines.append('')
lines.append('--- T1 自算几何质心 vs DataV centroid 字段（算法自洽性）---')
a = [r['d_field_calc'] for r in rows if r['d_field_calc'] not in ('', None)]
a = sorted(float(x) for x in a)


def q(x, p):
    return x[int(p * (len(x) - 1))]


lines.append('可比对 %d 县；距离中位 %.3f km，p90 %.3f km，p99 %.3f km，最大 %.3f km'
             % (len(a), q(a, .5), q(a, .9), q(a, .99), a[-1]))
lines.append('结论：自算质心与 DataV centroid 字段在 %s 以内一致，几何算法可用'
             % ('1 km' if q(a, .99) < 1 else '%.1f km' % q(a, .99)))
lines.append('')
lines.append('--- T2 center 与自算几何质心的距离（核心检验）---')
ua = [row for row in rows if row['adcode'] in used_ad and row['d_center_calc'] not in ('', None)]
b = sorted(float(r['d_center_calc']) for r in ua)
lines.append('估计用县 %d 个；center 到几何质心距离：中位 %.2f km，p25 %.2f，p75 %.2f，p90 %.2f，最大 %.2f'
             % (len(b), q(b, .5), q(b, .25), q(b, .75), q(b, .9), b[-1]))
lines.append('完全重合（<0.1 km）的县：%d / %d（%.1f%%）'
             % (sum(1 for x in b if x < 0.1), len(b), 100 * sum(1 for x in b if x < 0.1) / len(b)))
lines.append('相差 >1 km 的县：%d（%.1f%%）；>5 km：%d（%.1f%%）'
             % (sum(1 for x in b if x > 1), 100 * sum(1 for x in b if x > 1) / len(b),
                sum(1 for x in b if x > 5), 100 * sum(1 for x in b if x > 5) / len(b)))
lines.append('')
lines.append('--- T3 点位是否落在本县边界内 ---')
ci = [r for r in ua if r['center_in_poly'] != '']
pf = [r for r in ua if r['centroid_in_poly'] != '']
lines.append('center 落在县界内：%d / %d（%.1f%%）'
             % (sum(int(r['center_in_poly']) for r in ci), len(ci),
                100 * sum(int(r['center_in_poly']) for r in ci) / max(len(ci), 1)))
lines.append('centroid 字段落在县界内：%d / %d（%.1f%%）'
             % (sum(int(r['centroid_in_poly']) for r in pf), len(pf),
                100 * sum(int(r['centroid_in_poly']) for r in pf) / max(len(pf), 1)))
lines.append('')
lines.append('--- T4 判定 ---')
med = q(b, .5)
same = sum(1 for x in b if x < 0.1) / len(b)
if same > 0.8:
    verdict = 'center 与几何质心高度重合，不能作为政府驻地的证据；应改称「县级区域中心点」'
elif med > 1.0:
    verdict = 'center 与几何质心系统性分离（中位 %.2f km），center 不是几何质心' % med
else:
    verdict = 'center 与几何质心部分重合（重合率 %.1f%%），定义处于中间状态' % (100 * same)
lines.append('统计判定：%s' % verdict)
lines.append('注意：DataV.GeoAtlas 的 properties.center 为该服务维护的行政中心/标注点，')
lines.append('      properties.centroid 为同一服务给出的质心字段；两者来源同一份数据，')
lines.append('      本检验能区分「是否等于几何质心」，不能独立证明 center 即政府驻地坐标。')

out = os.path.join('data', 'geo', 'county_center_audit.csv')
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print('写出 %s' % out)

txt = os.path.join('data', 'master', 'county_center_audit.txt')
open(txt, 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
