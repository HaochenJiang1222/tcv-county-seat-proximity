# -*- coding: utf-8 -*-
"""把地形变量从 18 县 163 村扩展到三省第四批全部 279 村（补查缺失村的高程）"""
import csv, json, os, sys, time, math, collections, urllib.request, urllib.parse

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
MASTER = 'data/master/master_final_1598.csv'
OUT = 'data/master/geo_vars_sample.csv'
OFF = 0.0045
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url, timeout=60, retry=3):
    for i in range(retry):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == retry - 1:
                raise
            time.sleep(2 + 2 * i)


master = list(csv.DictReader(open(MASTER, encoding='utf-8-sig')))
T = {'江苏省', '浙江省', '安徽省'}
target = [r for r in master if r['province'] in T]
have = {r['village_id'] for r in csv.DictReader(open(OUT, encoding='utf-8-sig'))}
need = [r for r in target if r['village_id'] not in have and r['latitude']]
print('三省第四批 %d 村；已有变量 %d；待补 %d' % (len(target), len(have), len(need)))
no_coord = [r for r in target if not r['latitude']]
print('无坐标村：%d %s' % (len(no_coord), [r['official_name_2016'] for r in no_coord]))

pts = []
for r in need:
    la, lo = float(r['latitude']), float(r['longitude'])
    for dy in (-OFF, 0, OFF):
        for dx in (-OFF, 0, OFF):
            pts.append((r['village_id'], round(dy, 5), round(dx, 5), round(la + dy, 6), round(lo + dx, 6)))
print('待查询高程点：%d' % len(pts))


def query_elev(ds, pts, batch=100):
    rec = {}
    for i in range(0, len(pts), batch):
        chunk = pts[i:i + batch]
        loc = '|'.join('%.6f,%.6f' % (p[3], p[4]) for p in chunk)
        url = 'https://api.opentopodata.org/v1/%s?locations=%s' % (ds, urllib.parse.quote(loc, safe='|,.'))
        j = json.loads(get(url).decode('utf-8'))
        if j.get('status') != 'OK':
            raise RuntimeError('%s: %s' % (ds, j.get('error')))
        for p, res in zip(chunk, j['results']):
            rec[(p[0], p[1], p[2])] = res['elevation']
        time.sleep(1.1)
    print('  %s 完成 %d 点' % (ds, len(pts)))
    return rec


elev = {}
if pts:
    for ds in ('srtm30m', 'aster30m'):
        try:
            elev[ds] = query_elev(ds, pts)
        except Exception as e:
            print('  %s 失败 %s' % (ds, str(e)[:120]))


def summarize(rec, vid):
    vals = [rec.get((vid, dy, dx)) for dy in (-OFF, 0, OFF) for dx in (-OFF, 0, OFF)]
    if any(v is None for v in vals):
        return None
    mean = sum(vals) / 9
    std = (sum((v - mean) ** 2 for v in vals) / 9) ** 0.5
    return {'elev': rec[(vid, 0.0, 0.0)], 'elev_mean_1km': round(mean, 2),
            'elev_range_1km': round(max(vals) - min(vals), 2), 'elev_sd_1km': round(std, 2)}


old = list(csv.DictReader(open(OUT, encoding='utf-8-sig')))
cols = list(old[0].keys())
byid = {r['village_id']: r for r in master}
for r in need:
    s = summarize(elev.get('srtm30m', {}), r['village_id'])
    a = summarize(elev.get('aster30m', {}), r['village_id'])
    old.append({
        'village_id': r['village_id'], 'province': r['province'], 'county': r['county'],
        'township': r['township'], 'village': r['village'], 'official_name_2016': r['official_name_2016'],
        'status': r['status'], 'latitude': r['latitude'], 'longitude': r['longitude'],
        'dist_county_km': '', 'county_center_source': '',
        'elev_srtm30': s['elev'] if s else '', 'elev_mean_1km_srtm30': s['elev_mean_1km'] if s else '',
        'elev_range_1km_srtm30': s['elev_range_1km'] if s else '', 'elev_sd_1km_srtm30': s['elev_sd_1km'] if s else '',
        'elev_aster30': a['elev'] if a else '', 'elev_range_1km_aster30': a['elev_range_1km'] if a else '',
        'elev_sd_1km_aster30': a['elev_sd_1km'] if a else '',
    })
with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(old)
print('写出 %s：%d 行' % (OUT, len(old)))
print('高程有效：%d/%d' % (sum(1 for r in old if r['elev_srtm30'] != ''), len(old)))
