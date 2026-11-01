# -*- coding: utf-8 -*-
"""构建认定前地形与可达性变量（全部来自公开可复核来源）

来源 1  行政中心坐标：DataV.GeoAtlas（阿里云公开行政区划边界服务）
        https://geo.datav.aliyun.com/areas_v3/bound/{adcode}_full.json
来源 2  高程：OpenTopoData 公共实例（SRTM 30m / ASTER 30m，原始数据源公开）
        https://api.opentopodata.org/v1/{dataset}?locations=lat,lng|...
        SRTM 采集于 2000 年，早于 2016 年认定与 2017 年安排，满足"认定前已确定"。

输出 data/master/geo_vars_sample.csv
"""
import csv, json, os, sys, time, math, collections, urllib.request, urllib.parse

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
MASTER = 'data/master/master_final_1598.csv'
DATAV = 'data/geo/datav'
os.makedirs(DATAV, exist_ok=True)
OUT = 'data/master/geo_vars_sample.csv'

UA = {'User-Agent': 'Mozilla/5.0'}


def get(url, timeout=40, retry=3):
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == retry - 1:
                raise
            time.sleep(2 + 2 * i)


# ---------- 1. 行政中心坐标 ----------
PROV_ADCODE = {'浙江省': 330000, '安徽省': 340000, '江苏省': 320000}
centers = {}          # (prov, name) -> (lon, lat)
adcode_map = {}
for prov, ad in PROV_ADCODE.items():
    fp = os.path.join(DATAV, '%d_full.json' % ad)
    if not os.path.exists(fp):
        b = get('https://geo.datav.aliyun.com/areas_v3/bound/%d_full.json' % ad, timeout=60)
        open(fp, 'wb').write(b)
    d = json.load(open(fp, encoding='utf-8'))
    n_lv = collections.Counter()
    for f in d['features']:
        p = f['properties']
        n_lv[p['level']] += 1
        if p['level'] in ('district', 'county') and p.get('center'):
            centers[(prov, p['name'])] = (float(p['center'][0]), float(p['center'][1]))
            adcode_map[(prov, p['name'])] = p['adcode']
    print('%s: features %d, levels %s, 县级条目 %d' % (prov, len(d['features']), dict(n_lv),
                                                    sum(1 for k in centers if k[0] == prov)))

# ---------- 2. 目标样本：18 个混合状态县的全部第四批村 ----------
rows = list(csv.DictReader(open(MASTER, encoding='utf-8-sig')))
T = {'江苏省', '浙江省', '安徽省'}
byc = collections.defaultdict(list)
for r in rows:
    if r['province'] in T:
        byc[(r['province'], r['county'])].append(r)
mix_keys = [k for k, g in byc.items()
            if any(x['status'] == 'A_2017' for x in g) and any(x['status'] == 'B_2018promised' for x in g)]
sample = [r for k in mix_keys for r in byc[k]]
print('目标样本：18 县 %d 村' % len(sample))

# 县名匹配（DataV 用全称，如"松阳县""建德市""丽水市莲都区"）
def find_center(prov, county):
    if (prov, county) in centers:
        return centers[(prov, county)], 'exact'
    for (pv, nm), xy in centers.items():
        if pv == prov and nm.endswith(county):
            return xy, 'suffix:' + nm
    for (pv, nm), xy in centers.items():
        if pv == prov and county.rstrip('县市区') and county.rstrip('县市区') in nm:
            return xy, 'fuzzy:' + nm
    return None, 'miss'


miss_cty = []
for r in sample:
    xy, how = find_center(r['province'], r['county'])
    r['_ctr'] = xy
    r['_ctr_how'] = how
    if xy is None:
        miss_cty.append((r['province'], r['county']))
print('县中心未匹配：%s' % sorted(set(miss_cty)))


def hav(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, [a[1], a[0], b[1], b[0]])
    d = 2 * R * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                    math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
    return d


for r in sample:
    if r['_ctr']:
        r['dist_county_km'] = round(hav((float(r['longitude']), float(r['latitude'])), r['_ctr']), 3)
    else:
        r['dist_county_km'] = ''

# ---------- 3. 高程：3x3 邻域 ----------
OFF = 0.0045   # ≈ 500 m
pts = []       # (village_id, dy, dx, lat, lng)
for r in sample:
    la, lo = float(r['latitude']), float(r['longitude'])
    for dy in (-OFF, 0, OFF):
        for dx in (-OFF, 0, OFF):
            pts.append((r['village_id'], round(dy, 5), round(dx, 5), round(la + dy, 6), round(lo + dx, 6)))
print('高程查询点：%d（每村 9 点）' % len(pts))


def query_elev(ds, pts, batch=100):
    rec = {}
    for i in range(0, len(pts), batch):
        chunk = pts[i:i + batch]
        loc = '|'.join('%.6f,%.6f' % (p[3], p[4]) for p in chunk)
        url = 'https://api.opentopodata.org/v1/%s?locations=%s' % (ds, urllib.parse.quote(loc, safe='|,.'))
        b = get(url, timeout=60)
        j = json.loads(b.decode('utf-8'))
        if j.get('status') != 'OK':
            raise RuntimeError('%s: %s' % (ds, j.get('error')))
        for p, res in zip(chunk, j['results']):
            rec[(p[0], p[1], p[2])] = res['elevation']
        print('  %s %d/%d' % (ds, min(i + batch, len(pts)), len(pts)))
        time.sleep(1.1)
    return rec


elev = {}
for ds in ('srtm30m', 'aster30m'):
    try:
        elev[ds] = query_elev(ds, pts)
    except Exception as e:
        print('  %s 失败: %s' % (ds, str(e)[:120]))

# ---------- 4. 汇总到村 ----------
def summarize(rec, vid):
    vals = [rec[(vid, dy, dx)] for dy in (-OFF, 0, OFF) for dx in (-OFF, 0, OFF)
            if (vid, dy, dx) in rec and rec[(vid, dy, dx)] is not None]
    if len(vals) < 9:
        return None
    ctr = rec.get((vid, 0.0, 0.0))
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    return {'elev': ctr, 'elev_mean_1km': round(mean, 2),
            'elev_range_1km': round(max(vals) - min(vals), 2), 'elev_sd_1km': round(std, 2)}


cols = ['village_id', 'province', 'county', 'township', 'village', 'official_name_2016',
        'status', 'latitude', 'longitude', 'dist_county_km', 'county_center_source',
        'elev_srtm30', 'elev_mean_1km_srtm30', 'elev_range_1km_srtm30', 'elev_sd_1km_srtm30',
        'elev_aster30', 'elev_range_1km_aster30', 'elev_sd_1km_aster30']
out_rows = []
for r in sample:
    vid = r['village_id']
    s = summarize(elev.get('srtm30m', {}), vid)
    a = summarize(elev.get('aster30m', {}), vid)
    out_rows.append({
        'village_id': vid, 'province': r['province'], 'county': r['county'],
        'township': r['township'], 'village': r['village'],
        'official_name_2016': r['official_name_2016'], 'status': r['status'],
        'latitude': r['latitude'], 'longitude': r['longitude'],
        'dist_county_km': r['dist_county_km'], 'county_center_source': r['_ctr_how'],
        'elev_srtm30': s['elev'] if s else '', 'elev_mean_1km_srtm30': s['elev_mean_1km'] if s else '',
        'elev_range_1km_srtm30': s['elev_range_1km'] if s else '', 'elev_sd_1km_srtm30': s['elev_sd_1km'] if s else '',
        'elev_aster30': a['elev'] if a else '', 'elev_range_1km_aster30': a['elev_range_1km'] if a else '',
        'elev_sd_1km_aster30': a['elev_sd_1km'] if a else '',
    })
with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out_rows)
print('写出 %s（%d 行）' % (OUT, len(out_rows)))

# ---------- 5. 诊断 ----------
print()
print('== 数据质量诊断 ==')
ok_s = sum(1 for r in out_rows if r['elev_srtm30'] != '')
ok_a = sum(1 for r in out_rows if r['elev_aster30'] != '')
ok_d = sum(1 for r in out_rows if r['dist_county_km'] != '')
print('高程有效（srtm30m 9/9 点）：%d/%d；aster30m：%d/%d；县中心距离：%d/%d' % (
    ok_s, len(out_rows), ok_a, len(out_rows), ok_d, len(out_rows)))
srtm = {r['village_id']: r['elev_srtm30'] for r in out_rows if r['elev_srtm30'] != ''}
aste = {r['village_id']: r['elev_aster30'] for r in out_rows if r['elev_aster30'] != ''}
common = [k for k in srtm if k in aste]
if common:
    dif = [abs(float(srtm[k]) - float(aste[k])) for k in common]
    dif.sort()
    print('两数据集高程差：n=%d 中位 %.0f m，90 分位 %.0f m，最大 %.0f m' % (
        len(common), dif[len(dif) // 2], dif[int(len(dif) * 0.9)], dif[-1]))
    cc = sum(1 for k in common if abs(float(srtm[k]) - float(aste[k])) <= 50) / len(common)
    print('两数据集差 ≤50 m 的村占比 %.1f%%' % (100 * cc))
for st in ('A_2017', 'B_2018promised', 'C_not_in_1044'):
    g = [r for r in out_rows if r['status'] == st and r['elev_srtm30'] != '' and r['dist_county_km'] != '']
    if not g:
        continue
    e = sorted(float(x['elev_srtm30']) for x in g)
    d = sorted(float(x['dist_county_km']) for x in g)
    rg = sorted(float(x['elev_range_1km_srtm30']) for x in g)
    print('%s n=%d  海拔中位 %.0f m  1km起伏中位 %.0f m  到县城中位 %.1f km' % (
        st, len(g), e[len(e) // 2], rg[len(rg) // 2], d[len(d) // 2]))
