# -*- coding: utf-8 -*-
"""
123b：全国第四批 1598 村高程（OpenTopoData 公共实例，SRTM 30m + ASTER 30m）
SRTM 采集于 2000 年，早于 2016 年认定，满足"认定前已确定"。
每村取 3x3 邻域（±0.0045° ≈ 500 m），输出海拔、1 km 内均值、起伏、标准差。
"""
import csv, sys, os, json, time, math
import urllib.request, urllib.parse

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'master')
OUT = os.path.join(D, 'elev_national.csv')
API = 'https://api.opentopodata.org/v1/%s?locations=%s'

rows = list(csv.DictReader(open(os.path.join(D, 'master_final_1598.csv'), encoding='utf-8-sig')))
pts = [(i, float(r['latitude']), float(r['longitude'])) for i, r in enumerate(rows)
       if r['latitude'] and r['longitude']]
print('有坐标村 %d' % len(pts))

# 邻域 3x3
NEI = [(-0.0045, -0.0045), (-0.0045, 0), (-0.0045, 0.0045),
       (0, -0.0045), (0, 0), (0, 0.0045),
       (0.0045, -0.0045), (0.0045, 0), (0.0045, 0.0045)]
locs, owner = [], []
for i, la, lo in pts:
    for dl, dn in NEI:
        locs.append((round(la + dl, 6), round(lo + dn, 6)))
        owner.append(i)
print('待查询点 %d' % len(locs))


def fetch(ds, batch):
    q = '|'.join('%.6f,%.6f' % (a, b) for a, b in batch)
    url = API % (ds, urllib.parse.quote(q, safe=',|.'))
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            j = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))
            if j.get('status') == 'OK':
                return [r['elevation'] for r in j['results']]
        except Exception as e:
            time.sleep(2)
    return None


res = {ds: [None] * len(locs) for ds in ('srtm30m', 'aster30m')}
B = 100
n_batch = math.ceil(len(locs) / B)
t0 = time.time()
for ds in res:
    for b in range(n_batch):
        batch = locs[b * B:(b + 1) * B]
        v = fetch(ds, batch)
        if v is None:
            print('   %s 批次 %d 失败' % (ds, b))
            v = [None] * len(batch)
        for k, x in enumerate(v):
            res[ds][b * B + k] = x
        time.sleep(1.05)
    print('%s 完成 %.0f s' % (ds, time.time() - t0))

out = []
for i, r in enumerate(rows):
    rec = {'village_id': r['village_id'], 'province': r['province'], 'county': r['county'],
           'village': r['village'], 'latitude': r['latitude'], 'longitude': r['longitude'],
           'status': r['status']}
    for ds, tag in [('srtm30m', 'srtm'), ('aster30m', 'aster')]:
        idx = [k for k, o in enumerate(owner) if o == i]
        vals = [res[ds][k] for k in idx if res[ds][k] is not None]
        if not vals:
            rec['elev_' + tag] = ''
            rec['elev_range_' + tag] = ''
            rec['elev_sd_' + tag] = ''
            continue
        rec['elev_' + tag] = round(vals[4] if len(vals) == 9 else sum(vals) / len(vals), 1)
        rec['elev_range_' + tag] = round(max(vals) - min(vals), 1)
        rec['elev_sd_' + tag] = round((sum((x - sum(vals) / len(vals)) ** 2 for x in vals) /
                                       len(vals)) ** .5, 1)
    out.append(rec)

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
ok = sum(1 for x in out if x['elev_srtm'] != '')
print('高程有效 %d / %d，写出 %s' % (ok, len(out), OUT))
d = [abs(float(x['elev_srtm']) - float(x['elev_aster'])) for x in out
     if x['elev_srtm'] != '' and x['elev_aster'] != '']
if d:
    d.sort()
    print('SRTM 与 ASTER 差：中位 %.1f m，最大 %.1f m' % (d[len(d) // 2], d[-1]))
