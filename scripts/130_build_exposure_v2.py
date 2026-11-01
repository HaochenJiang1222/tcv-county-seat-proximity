# -*- coding: utf-8 -*-
"""
130：重建历史暴露变量（第三十八部分任务二）

从"支持 vs 未支持"改为"早支持 vs 晚支持"，因为前三批 2,555 村几乎全部进入过
支持安排（2,535 已连接），"永久未获支持"对照组基本不存在。

两套变量（用户第三十八部分第四节）
  第一套 历史支持安排早晚（截点 2015-12-31）
    early : 2015 年底前已公布当年支持安排（2014-1 / 2014-2 / 2015-1，公告日均 <=2015-08-10）
    late  : 截至 2015 年底尚未公开列入任何支持安排（其后仍可能入选）
    注：2015att2（86 村，已通过审查列入 2016 年支持）单独标 precommitted，
        既不算 early（尚无当年安排），也不算 late（已有未来承诺）
  第二套 历史资源支持成熟度（截点 2014-12-31）
    mature: 2014 年已获支持（2014-1 / 2014-2），潜在项目实施时间最长

两类都配 计数型(n_) 与 距离型(d_nearest_)，并输出 n_pre（附近前三批总数）作集聚控制。

输出
  data/master/exposure_v2.csv
"""
import csv, sys, os, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')

pre = list(csv.DictReader(open(os.path.join(D, 'master', 'geo_points_pre2555_v3.csv'),
                               encoding='utf-8-sig')))
m = list(csv.DictReader(open(os.path.join(D, 'master', 'master_final_1598.csv'),
                             encoding='utf-8-sig')))
m4 = [r for r in m if r['latitude'] and r['longitude']]
print('前三批点位 %d；第四批有坐标 %d' % (len(pre), len(m4)))

plat = np.array([float(r['lat']) for r in pre])
plon = np.array([float(r['lon']) for r in pre])
mlat = np.array([float(r['latitude']) for r in m4])
mlon = np.array([float(r['longitude']) for r in m4])


def hav(la1, lo1, la2, lo2):
    R = 6371.0088
    p1, p2 = np.radians(la1), np.radians(la2)
    dp = p2 - p1
    dl = np.radians(lo2 - lo1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


Dall = hav(mlat[:, None], mlon[:, None], plat[None, :], plon[None, :])

groups = {}
groups['early'] = [i for i, r in enumerate(pre)
                   if r['first_announce_date'] and r['first_announce_date'] <= '2015-12-31'
                   and r['precommitted_future_year'] != '1']
groups['late'] = [i for i, r in enumerate(pre)
                  if r['precommitted_future_year'] != '1' and
                  (not r['first_announce_date'] or r['first_announce_date'] > '2015-12-31')]
groups['precom'] = [i for i, r in enumerate(pre) if r['precommitted_future_year'] == '1']
groups['mature'] = [i for i, r in enumerate(pre) if r['sup_2014'] == '1']
groups['never'] = [i for i, r in enumerate(pre) if not r['first_announce_date']
                   and r['precommitted_future_year'] != '1']
print()
print('== 历史村分组（前三批 2555）==')
for k, v in groups.items():
    print('   %-8s %d' % (k, len(v)))
print('   校验 early + late + precom + never = %d' %
      (len(groups['early']) + len(groups['late']) + len(groups['precom']) + len(groups['never'])))

RADII = [5, 10, 20]
Dg = {k: Dall[:, v].min(axis=1) for k, v in groups.items() if v}
Dg['pre'] = Dall.min(axis=1)

rows = []
for j, r in enumerate(m4):
    rec = {'village_id': r['village_id'], 'province': r['province'], 'county': r['county'],
           'township': r['township'], 'village': r['village'],
           'latitude': r['latitude'], 'longitude': r['longitude'], 'status': r['status']}
    for R in RADII:
        rec['n_pre_%d' % R] = int((Dall[j] <= R).sum())
        for k, v in groups.items():
            if not v:
                continue
            dd = hav(mlat[j], mlon[j], plat[v], plon[v])
            rec['n_%s_%d' % (k, R)] = int((dd <= R).sum())
    for k in ['pre', 'early', 'late', 'mature', 'precom', 'never']:
        if k in Dg:
            rec['d_nearest_%s' % k] = round(float(Dg[k][j]), 3)
    rows.append(rec)

outp = os.path.join(D, 'master', 'exposure_v2.csv')
with open(outp, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print()
print('写出 %s（%d 行）' % (outp, len(rows)))


def corr(a, b):
    a = np.array([float(x) for x in a], dtype=float)
    b = np.array([float(x) for x in b], dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


print()
print('== 独立变异诊断（距离型，log1p 后相关）==')
import math
lg = lambda k: [math.log1p(float(x[k])) for x in rows if x.get(k) not in ('', None)]
for a, b in [('d_nearest_early', 'd_nearest_late'),
             ('d_nearest_early', 'd_nearest_pre'),
             ('d_nearest_late', 'd_nearest_pre'),
             ('d_nearest_mature', 'd_nearest_late')]:
    print('   corr(%s, %s) = %.3f' % (a, b, corr([float(x[a]) for x in rows],
                                                  [float(x[b]) for x in rows])))
print()
print('== 独立变异诊断（计数型 10km）==')
for a, b in [('n_early_10', 'n_late_10'), ('n_early_10', 'n_pre_10'), ('n_late_10', 'n_pre_10')]:
    print('   corr(%s, %s) = %.3f' % (a, b, corr([x[a] for x in rows], [x[b] for x in rows])))
print()
print('== 暴露覆盖（10km 内至少 1 个）==')
for k in ['early', 'late', 'mature', 'never']:
    n = sum(1 for x in rows if x.get('n_%s_10' % k, 0) > 0)
    print('   %-8s %d / %d（%.1f%%）' % (k, n, len(rows), 100 * n / len(rows)))
