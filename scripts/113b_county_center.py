# -*- coding: utf-8 -*-
"""补取县级行政中心坐标（DataV.GeoAtlas 下沉到地级市层），计算村到县城直线距离，
并合并回 data/master/geo_vars_sample.csv"""
import csv, json, os, sys, time, math, collections, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
DATAV = 'data/geo/datav'
os.makedirs(DATAV, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url, timeout=60, retry=3):
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == retry - 1:
                raise
            time.sleep(2 + 2 * i)


def load_adcode(ad):
    fp = os.path.join(DATAV, '%d_full.json' % ad)
    if not os.path.exists(fp):
        open(fp, 'wb').write(get('https://geo.datav.aliyun.com/areas_v3/bound/%d_full.json' % ad))
    return json.load(open(fp, encoding='utf-8'))


# 省级 -> 地级市
PROV = {'浙江省': 330000, '安徽省': 340000, '江苏省': 320000}
centers, how = {}, {}
for prov, ad in PROV.items():
    d = load_adcode(ad)
    cities = [(f['properties']['adcode'], f['properties']['name'])
              for f in d['features'] if f['properties']['level'] == 'city']
    print('%s 地级市 %d' % (prov, len(cities)))
    for cad, cname in cities:
        try:
            dd = load_adcode(cad)
        except Exception as e:
            print('  %s %s 抓取失败 %s' % (prov, cname, str(e)[:60]))
            continue
        for f in dd['features']:
            p = f['properties']
            if p['level'] in ('district', 'county') and p.get('center'):
                key = (prov, p['name'])
                centers[key] = (float(p['center'][0]), float(p['center'][1]))
                how[key] = cname
        time.sleep(0.15)
print('县级中心条目：%d' % len(centers))

rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
need = sorted({(r['province'], r['county']) for r in rows})
print('样本涉及县：%d' % len(need))
miss = []
for k in need:
    if k not in centers:
        # 去后缀再试
        core = k[1].rstrip('县市区')
        cand = [kk for kk in centers if kk[0] == k[0] and core and core in kk[1]]
        if len(cand) == 1:
            centers[k] = centers[cand[0]]
            how[k] = 'fuzzy:' + cand[0][1]
        else:
            miss.append(k)
print('未匹配：%s' % miss)


def hav(lat1, lon1, lat2, lon2):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
    return 2 * R * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                       math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


for r in rows:
    k = (r['province'], r['county'])
    if k in centers:
        c = centers[k]
        r['dist_county_km'] = round(hav(float(r['latitude']), float(r['longitude']), c[1], c[0]), 3)
        r['county_center_source'] = how.get(k, 'exact')
    else:
        r['dist_county_km'] = ''
        r['county_center_source'] = 'miss'

cols = list(rows[0].keys())
with open('data/master/geo_vars_sample.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print('已回写 dist_county_km：有效 %d/%d' % (sum(1 for r in rows if r['dist_county_km'] != ''), len(rows)))

print()
print('== 分状态描述（18 县 163 村）==')
for st in ('A_2017', 'B_2018promised', 'C_not_in_1044'):
    g = [r for r in rows if r['status'] == st and r['dist_county_km'] != '']
    if not g:
        continue
    def med(v):
        v = sorted(v); return v[len(v) // 2]
    print('%s n=%d  海拔中位 %.0f m  1km起伏中位 %.0f m  到县城中位 %.1f km（最远 %.1f）' % (
        st, len(g), med([float(x['elev_srtm30']) for x in g]),
        med([float(x['elev_range_1km_srtm30']) for x in g]),
        med([float(x['dist_county_km']) for x in g]), max(float(x['dist_county_km']) for x in g)))
print()
print('== 县中心坐标明细 ==')
for k in need:
    if k in centers:
        print('  %s %s -> %.4f, %.4f (%s)' % (k[0][:2], k[1], centers[k][0], centers[k][1], how.get(k, '')))
