# -*- coding: utf-8 -*-
"""
126：全国结果的敏感性
  S1 全样本          S2 剔除坐标质量可疑（界外且距县界>5 km）  S3 仅苏浙皖
  另加县等权检验：县内 A组与对照组的变量均值差，县为单位 bootstrap
"""
import csv, sys, os, math, time, collections
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'master')
SEED = 20261030
B = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

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
                 'dist': math.log1p(dc[v]),
                 'd_sup': math.log1p(float(e['d_nearest_sup'])),
                 'd_not': math.log1p(float(e['d_nearest_notsup'])),
                 'elev': float(x['elev_srtm']) / 100,
                 'rng': float(x['elev_range_srtm']) / 100,
                 'out5': (a.get('result') == 'outside' and a.get('dist_km') != ''
                          and float(a['dist_km']) > 5)})
print('全样本 %d 村；坐标可疑 %d 条' % (len(recs), sum(1 for r in recs if r['out5'])))

SAMPLE = {'S1 全样本': recs,
          'S2 剔坐标可疑': [r for r in recs if not r['out5']],
          'S3 仅苏浙皖': [r for r in recs if r['prov'] in ('江苏省', '浙江省', '安徽省')]}


def prep(recs, kind):
    if kind == 'A':
        sub = [r for r in recs if r['st'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]
        y = np.array([1.0 if r['st'] in ('A_2017', 'B_2018promised') else 0.0 for r in sub])
    else:
        sub = [r for r in recs if r['st'] in ('A_2017', 'B_2018promised')]
        y = np.array([1.0 if r['st'] == 'A_2017' else 0.0 for r in sub])
    gp = collections.defaultdict(list)
    for i, r in enumerate(sub):
        gp[r['grp']].append(y[i])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    idx = [i for i, r in enumerate(sub) if r['grp'] in ok]
    return [sub[i] for i in idx], y[idx]


def fit(sub, y, cols):
    X = np.array([[r[c] for c in cols] for r in sub])
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    g = np.array([gi[r['grp']] for r in sub])
    return ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300).params


def boot(sub, y, cols, Bn):
    keys = sorted({r['grp'] for r in sub})
    buck = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buck[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    out = []
    for _ in range(Bn):
        pick = rng.integers(0, len(keys), len(keys))
        idx = [i for j in range(len(keys)) for i in buck[keys[pick[j]]]]
        s2, y2 = [sub[i] for i in idx], y[idx]
        if len(set(y2)) < 2:
            continue
        try:
            p = fit(s2, y2, cols)
        except Exception:
            continue
        if np.all(np.isfinite(p)) and np.max(np.abs(p)) < 20:
            out.append(p)
    return np.array(out) if out else None


def pv(b):
    return 2 * min((b <= 0).mean(), (b >= 0).mean())


MAIN = ['dist', 'd_sup', 'd_not', 'elev', 'rng']
print()
print('%-12s %-4s %-6s %8s %8s %10s %10s %8s' % (
    '样本', '过程', '变量', 'beta', 'OR', 'CI低', 'CI高', 'p'))
res_rows = []
for sname, rs in SAMPLE.items():
    for kind in ['A', 'B']:
        sub, y = prep(rs, kind)
        if len(sub) < 30:
            print('%-12s %-4s 样本不足' % (sname, kind))
            continue
        b0 = fit(sub, y, MAIN)
        bs = boot(sub, y, MAIN, B)
        for j, c in enumerate(MAIN):
            lo, hi = np.percentile(bs[:, j], [2.5, 97.5])
            print('%-12s %-4s %-6s %8.3f %8.3f %10.3f %10.3f %8.3f' % (
                sname, kind, c, b0[j], math.exp(b0[j]), lo, hi, pv(bs[:, j])))
            res_rows.append([sname, kind, c, b0[j], math.exp(b0[j]), lo, hi, pv(bs[:, j])])
        d = bs[:, 1] - bs[:, 2]
        lo, hi = np.percentile(d, [2.5, 97.5])
        print('%-12s %-4s %-6s %8.3f %8s %10.3f %10.3f %8.3f' % (
            sname, kind, 'd_sup-d_not', b0[1] - b0[2], '', lo, hi, pv(d)))
        res_rows.append([sname, kind, 'd_sup-d_not', b0[1] - b0[2], '', lo, hi, pv(d)])
        print('   （%d 县 %d 村）' % (len({r['grp'] for r in sub}), len(sub)))

# ---------- 县等权：县内均值差 ----------
print()
print('== 县等权：县内两组均值差（县级 bootstrap %d 次）==' % B)
for kind, lab in [('A', 'A：进入安排 vs 未进入'), ('B', 'B：当年 vs 次年')]:
    sub, y = prep(recs, kind)
    by = collections.defaultdict(lambda: {'1': [], '0': []})
    for r, yy in zip(sub, y):
        by[r['grp']]['1' if yy == 1 else '0'].append(r)
    keys = sorted({r['grp'] for r in sub})
    rng = np.random.default_rng(SEED + 1)
    for var in ['dist', 'd_sup', 'd_not', 'elev', 'rng']:
        diffs = []
        for k in keys:
            a = [x[var] for x in by[k]['1']]
            b = [x[var] for x in by[k]['0']]
            if a and b:
                diffs.append(np.mean(a) - np.mean(b))
        obs = float(np.mean(diffs))
        bs = []
        for _ in range(2000):
            pick = rng.integers(0, len(diffs), len(diffs))
            bs.append(np.mean([diffs[i] for i in pick]))
        bs = np.array(bs)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print('  %s %-6s 县内差 %8.3f  CI [%7.3f, %7.3f]  p %.3f  （%d 县，%d 县为负）' % (
            lab[:1], var, obs, lo, hi, pv(bs), len(diffs), sum(1 for x in diffs if x < 0)))

with open(os.path.join(D, 'national_sensitivity.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['sample', 'process', 'variable', 'beta', 'OR', 'ci_lo', 'ci_hi', 'p_boot'])
    w.writerows([[a, b, c] + [round(x, 4) for x in v] for a, b, c, *v in res_rows])
print()
print('写出 national_sensitivity.csv')
