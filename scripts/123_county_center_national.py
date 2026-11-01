# -*- coding: utf-8 -*-
"""
123：全国县级行政中心坐标（DataV.GeoAtlas 公开边界服务）
省 full -> 市 full -> 县 center，三级下沉后与第四批村所属县名匹配。
输出 data/geo/county_center_national.csv
"""
import json, sys, os, csv, re, time, collections
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'geo', 'county_center_national.csv')
CACHE = os.path.join(ROOT, 'data', 'geo', 'datav_cache')
os.makedirs(CACHE, exist_ok=True)

BASE = 'https://geo.datav.aliyun.com/areas_v3/bound/%s_full.json'


def get(code):
    p = os.path.join(CACHE, '%s.json' % code)
    if os.path.exists(p) and os.path.getsize(p) > 200:
        return json.load(open(p, encoding='utf-8'))
    for _ in range(3):
        try:
            req = urllib.request.Request(BASE % code, headers={'User-Agent': 'Mozilla/5.0'})
            t = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
            open(p, 'w', encoding='utf-8').write(t)
            return json.loads(t)
        except Exception as e:
            time.sleep(1.5)
    return None


rows = []
d = get('100000')
if d is None:
    print('省级清单获取失败')
    sys.exit(1)
provs = [(f['properties']['adcode'], f['properties']['name']) for f in d['features']]
print('省级 %d 个' % len(provs))

city_codes = []      # 需再下沉一层取县级
direct = []          # 本身已是县级（直辖市辖区、省直辖汇总下的县）
for pc, pn in provs:
    dd = get(pc)
    if not dd:
        print('  省失败', pn)
        continue
    for f in dd['features']:
        pr = f['properties']
        code = str(pr['adcode'])
        if code.endswith('00') and not code.endswith('9000'):
            city_codes.append((code, pr['name'], pn))
        else:
            # 直辖市辖区（110101）或省直辖县级行政区划汇总（469000）
            if pr.get('center'):
                direct.append({'province': pn, 'city': pn, 'county': pr['name'],
                               'adcode': code, 'lon': pr['center'][0], 'lat': pr['center'][1]})
            if code.endswith('9000'):
                city_codes.append((code, pr['name'], pn))
# 省直辖县级行政区划在部分省份不出现于省级清单，显式补齐
for extra in ['469000', '419000', '429000', '469001']:
    city_codes.append((extra, '省直辖', ''))
print('地级 %d 个，直接县级 %d 个' % (len(city_codes), len(direct)))

n_city = 0
for cc, cn, pn in city_codes:
    dd = get(cc)
    if not dd:
        continue
    n_city += 1
    for f in dd['features']:
        pr = f['properties']
        if not pr.get('center'):
            continue
        pv = pn or pr['name']
        rows.append({'province': pv, 'city': cn, 'county': pr['name'],
                     'adcode': pr['adcode'],
                     'lon': pr['center'][0], 'lat': pr['center'][1]})
rows += direct
# 省直辖条目省份名回填
prov_by_code = {str(pc): pn for pc, pn in provs}
for r in rows:
    if not r['province']:
        r['province'] = prov_by_code.get(str(r['adcode'])[:2] + '0000', '')
print('取回市级 %d 个，县级条目 %d' % (n_city, len(rows)))

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['province', 'city', 'county', 'adcode', 'lon', 'lat'])
    w.writeheader()
    w.writerows(rows)
print('写出 %s' % OUT)

# 与第四批村的县名核对
m = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'master', 'master_final_1598.csv'),
                             encoding='utf-8-sig')))


def core(s):
    s = re.sub(r'[\s]', '', s or '')
    s = re.sub(r'(自治县|自治旗|特区|林区|新区)$', '', s)
    s = re.sub(r'[市县区旗]$', '', s)
    return s


idx = collections.defaultdict(list)
for r in rows:
    idx[(r['province'], core(r['county']))].append(r)
need = sorted({(r['province'], r['county']) for r in m})
miss = []
for pv, ct in need:
    if (pv, core(ct)) not in idx and not [(k) for k in idx if k[0] == pv and
                                          (core(ct) in k[1] or k[1] in core(ct))]:
        miss.append((pv, ct))
print('第四批村涉及县 %d 个，县中心未匹配 %d 个' % (len(need), len(miss)))
for x in miss[:20]:
    print('   ', x)
