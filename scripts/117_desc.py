# -*- coding: utf-8 -*-
"""主检验样本的描述性统计与县内均值差（供报告使用）"""
import csv, sys, math, collections
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
SEED = 20261030
rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
BAD = {('建德市', '建南村章家自然村')}
for r in rows:
    r['_grp'] = r['province'] + '|' + r['county']
abc = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    abc[r['_grp']][{'A_2017': 0, 'B_2018promised': 1, 'C_not_in_1044': 2}[r['status']]] += 1
MIXED = {k for k, v in abc.items() if v[0] and v[1]}
main = [r for r in rows if r['status'] in ('A_2017', 'B_2018promised')
        and r['_grp'] in MIXED and (r['county'], r['village']) not in BAD]
print('主检验样本 %d 村 / %d 县（A %d / B %d）' % (
    len(main), len(MIXED), sum(1 for r in main if r['status'] == 'A_2017'),
    sum(1 for r in main if r['status'] == 'B_2018promised')))
print()
print('| 变量 | 2017 当年支持（A）中位 | 拟 2018 支持（B）中位 | 差（A−B） |')
for nm, f in [('海拔（m）', lambda r: float(r['elev_srtm30'])),
              ('到县城（km）', lambda r: float(r['dist_county_km'])),
              ('1 km 起伏（m）', lambda r: float(r['elev_range_1km_srtm30']))]:
    a = sorted(f(r) for r in main if r['status'] == 'A_2017')
    b = sorted(f(r) for r in main if r['status'] == 'B_2018promised')
    print('| %s | %.1f | %.1f | %+.1f |' % (nm, a[len(a) // 2], b[len(b) // 2],
                                            a[len(a) // 2] - b[len(b) // 2]))
print()
rng = np.random.default_rng(SEED)
print('| 变量 | 县内均值差 A−B（县等权，n=18） | bootstrap 95%CI | boot p | 县符号（负/正） |')
for nm, f, unit in [('海拔', 'elev_srtm30', 'm'), ('到县城距离', 'dist_county_km', 'km'),
                    ('1 km 起伏', 'elev_range_1km_srtm30', 'm')]:
    ds = []
    for k in sorted(MIXED):
        g = [r for r in main if r['_grp'] == k]
        a = [float(r[f]) for r in g if r['status'] == 'A_2017']
        b = [float(r[f]) for r in g if r['status'] == 'B_2018promised']
        if a and b:
            ds.append(np.mean(a) - np.mean(b))
    ds = np.array(ds)
    bs = np.array([ds[rng.integers(0, len(ds), len(ds))].mean() for _ in range(5000)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    bb = bs - bs.mean()
    p = 2 * min((bb <= -abs(ds.mean())).mean(), (bb >= abs(ds.mean())).mean())
    print('| %s | %+.2f %s | [%.2f, %.2f] | %.3f | %d / %d |' % (
        nm, ds.mean(), unit, lo, hi, min(1, max(p, 1 / 5000)), int((ds < 0).sum()), int((ds > 0).sum())))
print()
print('== 按县：A 组与 B 组到县城距离均值（km）==')
print('| 县 | A 村数 | A 均值 | B 村数 | B 均值 | 差 |')
for k in sorted(MIXED, key=lambda x: -abc[x][0] - abc[x][1]):
    g = [r for r in main if r['_grp'] == k]
    a = [float(r['dist_county_km']) for r in g if r['status'] == 'A_2017']
    b = [float(r['dist_county_km']) for r in g if r['status'] == 'B_2018promised']
    if a and b:
        print('| %s | %d | %.1f | %d | %.1f | %+.1f |' % (
            k.replace('|', '·'), len(a), np.mean(a), len(b), np.mean(b), np.mean(a) - np.mean(b)))
