# -*- coding: utf-8 -*-
"""
127：县等权检验——县内两组变量均值差，以县为单位 bootstrap（避免大县主导）
"""
import csv, sys, os, math, collections
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'master')
SEED = 20261030

m = {r['village_id']: r for r in csv.DictReader(open(os.path.join(D, 'master_final_1598.csv'),
                                                     encoding='utf-8-sig'))}
exp = {r['village_id']: r for r in csv.DictReader(open(os.path.join(D, 'exposure_national.csv'),
                                                       encoding='utf-8-sig'))}
el = {r['village_id']: r for r in csv.DictReader(open(os.path.join(D, 'elev_national.csv'),
                                                      encoding='utf-8-sig'))}
dc = {r['village_id']: float(r['dist_km']) for r in
      csv.DictReader(open(os.path.join(D, 'dist_county_national.csv'), encoding='utf-8-sig'))
      if r['dist_km']}
audit = {r['village_id']: r for r in csv.DictReader(open(os.path.join(D, 'geo_audit_national.csv'),
                                                         encoding='utf-8-sig'))}
recs = []
for v, r in m.items():
    e, x = exp.get(v), el.get(v)
    if not e or not x or v not in dc:
        continue
    if e['d_nearest_sup'] == '' or e['d_nearest_notsup'] == '' or x['elev_srtm'] == '':
        continue
    a = audit.get(v, {})
    recs.append({'vid': v, 'prov': r['province'], 'cty': r['county'], 'st': r['status'],
                 'grp': r['province'] + '|' + r['county'],
                 'dist_km': dc[v], 'dist': math.log1p(dc[v]),
                 'd_sup': math.log1p(float(e['d_nearest_sup'])),
                 'd_not': math.log1p(float(e['d_nearest_notsup'])),
                 'elev': float(x['elev_srtm']) / 100,
                 'rng': float(x['elev_range_srtm']) / 100,
                 'out5': (a.get('result') == 'outside' and a.get('dist_km') != ''
                          and float(a['dist_km']) > 5)})


def pv(b):
    return 2 * min((b <= 0).mean(), (b >= 0).mean())


def run(recs, scope, kind):
    if kind == 'A':
        sub = [r for r in recs if r['st'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]
        y = np.array([1.0 if r['st'] in ('A_2017', 'B_2018promised') else 0.0 for r in sub])
    else:
        sub = [r for r in recs if r['st'] in ('A_2017', 'B_2018promised')]
        y = np.array([1.0 if r['st'] == 'A_2017' else 0.0 for r in sub])
    by = collections.defaultdict(lambda: {'1': [], '0': []})
    for r, yy in zip(sub, y):
        by[r['grp']]['1' if yy == 1 else '0'].append(r)
    keys = sorted({r['grp'] for r in sub})
    rng = np.random.default_rng(SEED + 7)
    print()
    print('--- %s 过程%s：%d 县 %d 村 ---' % (scope, kind, len(keys), len(sub)))
    print('%-8s %10s %22s %8s %8s' % ('变量', '县内均值差', '95% CI', 'p', '负向县数'))
    for var, unit in [('dist_km', 'km'), ('d_sup', 'log'), ('d_not', 'log'),
                      ('elev', '百米'), ('rng', '百米')]:
        diffs = []
        for k in keys:
            a = [x[var] for x in by[k]['1']]
            b = [x[var] for x in by[k]['0']]
            if a and b:
                diffs.append(np.mean(a) - np.mean(b))
        if len(diffs) < 5:
            continue
        obs = float(np.mean(diffs))
        idxs = rng.integers(0, len(diffs), (5000, len(diffs)))
        bs = np.array([np.mean(diffs[i] for i in row) for row in idxs]) if False else \
            np.array([np.mean([diffs[i] for i in row]) for row in idxs[:2000]])
        lo, hi = np.percentile(bs, [2.5, 97.5])
        neg = sum(1 for x in diffs if x < 0)
        print('%-8s %10.3f %22s %8.3f %6d/%d' % (
            var, obs, '[%.3f, %.3f]' % (lo, hi), pv(bs), neg, len(diffs)))


clean = [r for r in recs if not r['out5']]
three = [r for r in clean if r['prov'] in ('江苏省', '浙江省', '安徽省')]
for rs, scope in [(clean, '全国（剔坐标可疑）'), (three, '三省')]:
    for kind in ['A', 'B']:
        run(rs, scope, kind)
