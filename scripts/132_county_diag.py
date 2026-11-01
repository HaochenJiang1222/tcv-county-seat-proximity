# -*- coding: utf-8 -*-
"""
132：县级影响诊断与县等权检验（第三十八部分第五节要求）

用户关注点：全国条件Logit 的显著结果（过程A dist）与各县简单平均差异不完全一致
（县等权 p=0.051，94 县中仅 51 县同向）。因此需要确认系数是否由少数高权重县驱动。

  D1 县级逐一剔除（leave-one-county-out）：过程A / 过程B 的 dist 系数范围
  D2 影响最大的县：剔除后 |β| 下降最多的 8 个县（含该县村数与状态构成）
  D3 县等权：每县内计算已安排组与未安排组的 dist 均值差，对县做 bootstrap
  D4 同向县比例与符号分布

输出 data/master/county_diag.txt
"""
import csv, sys, os, math, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
SEED = 20261030
B = 5000

m = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'master_final_1598.csv'), encoding='utf-8-sig'))}
exp = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'exposure_v2.csv'), encoding='utf-8-sig'))}
el = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'elev_national.csv'), encoding='utf-8-sig'))}
dc = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'dist_county_national.csv'), encoding='utf-8-sig'))}

recs = []
for v, r in m.items():
    e, x, d = exp.get(v), el.get(v), dc.get(v)
    if not (e and x and d and r['latitude'] and d['dist_km'] and x['elev_srtm']):
        continue
    if e['d_nearest_early'] in ('', None) or e['d_nearest_late'] in ('', None):
        continue
    recs.append({'vid': v, 'grp': r['province'] + '|' + r['county'], 'prov': r['province'],
                 'cty': r['county'], 'st': r['status'],
                 'dist': math.log1p(float(d['dist_km'])),
                 'dist_km': float(d['dist_km']),
                 'elev': float(x['elev_srtm']) / 100.0,
                 'rng': float(x['elev_range_srtm']) / 100.0,
                 'd_early': math.log1p(float(e['d_nearest_early'])),
                 'd_late': math.log1p(float(e['d_nearest_late'])),
                 'yA': 1.0 if r['status'] in ('A_2017', 'B_2018promised') else 0.0,
                 'yB': 1.0 if r['status'] == 'A_2017' else (0.0 if r['status'] == 'B_2018promised' else -1.0)})

COLS = ['dist', 'elev', 'rng', 'd_early', 'd_late']


def vary(sub, ykey):
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in ok]


def fit(sub, ykey, cols=COLS):
    y = np.array([r[ykey] for r in sub])
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub])
    g = np.array([gi[r['grp']] for r in sub])
    return ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300)


A = vary([r for r in recs if r['st'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')], 'yA')
B_ = vary([r for r in recs if r['st'] in ('A_2017', 'B_2018promised')], 'yB')
out = []
out.append('=== 县级影响诊断 ===')
out.append('过程A 样本 %d 村 / %d 县；过程B %d 村 / %d 县'
           % (len(A), len({r['grp'] for r in A}), len(B_), len({r['grp'] for r in B_})))

# ---------- D1/D2 县级逐一剔除 ----------
for tag, sub, ykey in [('A', A, 'yA'), ('B', B_, 'yB')]:
    base = fit(sub, ykey).params[0]
    ctys = sorted({r['grp'] for r in sub})
    vals = []
    for c in ctys:
        s2 = vary([r for r in sub if r['grp'] != c], ykey)
        try:
            vals.append((c, fit(s2, ykey).params[0], len(s2)))
        except Exception:
            pass
    v = np.array([x[1] for x in vals])
    out.append('')
    out.append('[过程%s] 全样本 dist β = %.3f' % (tag, base))
    out.append('  逐一剔县（%d 县）：β ∈ [%.3f, %.3f]，符号恒定 %s'
               % (len(vals), v.min(), v.max(),
                  '是' if (v > 0).all() or (v < 0).all() else '否'))
    out.append('  同号县 %d / %d（%.1f%%）'
               % (int(((v > 0) == (base > 0)).sum()), len(v),
                  100 * ((v > 0) == (base > 0)).mean()))
    # 影响最大的县：剔除后 |β| 最小（即该县对结果贡献最大）
    order = sorted(vals, key=lambda x: abs(x[1]))
    out.append('  剔除后 |β| 最小的 8 个县（这些县对估计贡献最大）：')
    for c, b, n in order[:8]:
        g = [r for r in sub if r['grp'] == c]
        na = sum(1 for r in g if r['st'] == 'A_2017')
        nb = sum(1 for r in g if r['st'] == 'B_2018promised')
        nc = sum(1 for r in g if r['st'] == 'C_not_in_1044')
        out.append('     %-16s β=%7.3f  本县村数 %d（A%d B%d C%d）'
                   % (c, b, len(g), na, nb, nc))

# ---------- D3/D4 县等权 ----------
out.append('')
out.append('=== 县等权检验（每县一个均值差，对县 bootstrap %d 次）===' % B)
rng = np.random.default_rng(SEED)
for tag, sub, ykey in [('A', A, 'yA'), ('B', B_, 'yB')]:
    by = collections.defaultdict(lambda: [[], []])
    for r in sub:
        if ykey == 'yA':
            (by[r['grp']][0] if r['yA'] == 1 else by[r['grp']][1]).append(r['dist_km'])
        else:
            if r['yB'] < 0:
                continue
            (by[r['grp']][0] if r['yB'] == 1 else by[r['grp']][1]).append(r['dist_km'])
    diffs = []
    for k, (a, b) in by.items():
        if a and b:
            diffs.append((k, float(np.mean(a)) - float(np.mean(b)), len(a), len(b)))
    arr = np.array([d[1] for d in diffs])
    boot = np.array([np.mean(rng.choice(arr, len(arr), replace=True)) for _ in range(B)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())
    neg = int((arr < 0).sum())
    out.append('')
    out.append('[过程%s] 有效县 %d；县内均值差（组1 − 组0）平均 %.2f km'
               % (tag, len(arr), arr.mean()))
    out.append('  bootstrap 95%%CI [%.2f, %.2f]，p = %.3f' % (lo, hi, p))
    out.append('  负向县 %d / %d（%.1f%%）' % (neg, len(arr), 100 * neg / len(arr)))
    out.append('  中位 %.2f km；四分位 [%.2f, %.2f]'
               % (np.median(arr), np.percentile(arr, 25), np.percentile(arr, 75)))

txt = '\n'.join(out)
print(txt)
open(os.path.join(D, 'master', 'county_diag.txt'), 'w', encoding='utf-8').write(txt)
