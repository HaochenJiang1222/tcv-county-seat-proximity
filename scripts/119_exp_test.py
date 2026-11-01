# -*- coding: utf-8 -*-
"""既有财政支持经验与资源进入速度（第三十六部分 H1）

识别设计
  计数型暴露与遗产密度相关 0.98，无法分离两种解释，故改用距离型暴露
    d_sup    到最近的"2014—2016 已获中央财政支持"历史认定村的距离
    d_notsup 到最近的"已认定但 2014—2016 未获支持"历史认定村的距离
  两者相关 0.172，可同时入模；两者系数之差即为"经验"相对"集聚"的增量

层次
  基准   2017 年是否进入支持安排（三省 279 村中有组内变异的县）
  机制   加入 d_sup，再同时加入 d_notsup
  竞争   控制海拔、1 km 起伏、到县城距离
推断 县级 block bootstrap，5000 次（次要口径 2000 次），SEED=20261030
"""
import csv, sys, math, collections
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

sys.stdout.reconfigure(encoding='utf-8')
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
SEED = 20261030
NB_MAIN, NB_SENS = 5000, 2000

geo = {r['village_id']: r for r in csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig'))}
exp = list(csv.DictReader(open('data/master/exposure_vars.csv', encoding='utf-8-sig')))
for r in exp:
    g = geo[r['village_id']]
    r['elev'] = float(g['elev_srtm30'])
    r['dist'] = float(g['dist_county_km'])
    r['relief'] = float(g['elev_range_1km_srtm30'])
    r['_grp'] = r['province'] + '|' + r['county']
    r['_bad'] = (r['county'], r['village']) in {('建德市', '建南村章家自然村')}
    r['ds'] = math.log1p(float(r['d_nearest_sup']))
    r['dn'] = math.log1p(float(r['d_nearest_notsup']))
    r['ns'] = float(r['n_pre_sup_10'])
    r['nn'] = float(r['n_pre_notsup_10'])

LABEL = {'ds': 'log(1+到最近已获支持村 km)', 'dn': 'log(1+到最近未获支持历史村 km)',
         'ns': '10km 内已获支持历史村数', 'nn': '10km 内未获支持历史村数',
         'elev': '海拔（百米）', 'dist': 'log(1+到县城 km)', 'relief': '1km 起伏（百米）'}
GET = {'ds': lambda r: r['ds'], 'dn': lambda r: r['dn'], 'ns': lambda r: r['ns'],
       'nn': lambda r: r['nn'], 'elev': lambda r: r['elev'] / 100.0,
       'dist': lambda r: math.log1p(r['dist']), 'relief': lambda r: r['relief'] / 100.0}


def clogit(sub, cols):
    y = np.array([1.0 if r['status'] == 'A_2017' else 0.0 for r in sub])
    X = np.array([[GET[c](r) for c in cols] for r in sub], float)
    keys = sorted({r['_grp'] for r in sub})
    idx = {k: i for i, k in enumerate(keys)}
    g = np.array([idx[r['_grp']] for r in sub])
    res = ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300)
    return res


def boot(sub, cols, nb, seed=SEED):
    rng = np.random.default_rng(seed)
    cty = sorted({r['_grp'] for r in sub})
    buck = collections.defaultdict(list)
    for r in sub:
        buck[r['_grp']].append(r)
    out = []
    for _ in range(nb):
        pick = rng.integers(0, len(cty), len(cty))
        s = []
        for j in range(len(cty)):
            for r in buck[cty[pick[j]]]:
                rr = dict(r)
                rr['_grp'] = r['_grp'] + '#%d' % j
                s.append(rr)
        try:
            res = clogit(s, cols)
            if np.all(np.isfinite(res.params)) and np.max(np.abs(res.params)) < 50:
                out.append(res.params)
        except Exception:
            continue
    return np.array(out)


def show(title, sub, cols, nb=NB_MAIN, diff=None, save=None):
    res = clogit(sub, cols)
    B = boot(sub, cols, nb)
    print()
    print('===== %s =====' % title)
    print('样本 %d 村 / %d 县；事件 %d' % (len(sub), len({r['_grp'] for r in sub}),
                                     int(sum(1 for r in sub if r['status'] == 'A_2017'))))
    print('%-28s %8s %8s %8s %18s %8s' % ('变量', 'beta', 'se_cond', 'OR', 'bootstrap 95% CI', 'boot_p'))
    recs = []
    for i, c in enumerate(cols):
        b = res.params[i]
        lo, hi = np.percentile(B[:, i], [2.5, 97.5])
        d = B[:, i] - B[:, i].mean()
        p = 2 * min((d <= -abs(b)).mean(), (d >= abs(b)).mean())
        p = min(1.0, max(p, 1.0 / max(len(B), 2)))
        print('%-28s %8.3f %8.3f %8.3f %18s %8.3f' % (
            LABEL.get(c, c), b, res.bse[i], math.exp(b), '[%.3f, %.3f]' % (lo, hi), p))
        recs.append({'model': title, 'var': c, 'beta': round(b, 4), 'se_cond': round(res.bse[i], 4),
                     'OR': round(math.exp(b), 4), 'ci_lo': round(lo, 4), 'ci_hi': round(hi, 4),
                     'boot_p': round(p, 4), 'n': len(sub), 'n_county': len({r['_grp'] for r in sub}),
                     'nboot': len(B)})
    if diff and diff[0] in cols and diff[1] in cols:
        i, j = cols.index(diff[0]), cols.index(diff[1])
        d = B[:, i] - B[:, j]
        est = res.params[i] - res.params[j]
        lo, hi = np.percentile(d, [2.5, 97.5])
        dd = d - d.mean()
        p = 2 * min((dd <= -abs(est)).mean(), (dd >= abs(est)).mean())
        p = min(1.0, max(p, 1.0 / max(len(B), 2)))
        print('%-28s %8.3f %8s %8s %18s %8.3f' % (
            '差（%s − %s）' % (diff[0], diff[1]), est, '', '', '[%.3f, %.3f]' % (lo, hi), p))
        recs.append({'model': title, 'var': 'diff_%s_%s' % (diff[0], diff[1]), 'beta': round(est, 4),
                     'se_cond': '', 'OR': '', 'ci_lo': round(lo, 4), 'ci_hi': round(hi, 4),
                     'boot_p': round(p, 4), 'n': len(sub), 'n_county': len({r['_grp'] for r in sub}),
                     'nboot': len(B)})
    if save is not None:
        save.extend(recs)
    return res, B


# ---------- 样本 ----------
abc = collections.defaultdict(lambda: [0, 0, 0])
for r in exp:
    abc[r['_grp']][{'A_2017': 0, 'B_2018promised': 1, 'C_not_in_1044': 2}[r['status']]] += 1
VAR_A_CTY = {k for k, v in abc.items() if (v[0] + v[1]) and v[2]}
MIXED = {k for k, v in abc.items() if v[0] and v[1]}

subA = []
for r in exp:
    if r['_grp'] in VAR_A_CTY and not r['_bad']:
        rr = dict(r)
        rr['status'] = 'A_2017' if r['status'] in ('A_2017', 'B_2018promised') else 'B_2018promised'
        subA.append(rr)
subB = [r for r in exp if r['status'] in ('A_2017', 'B_2018promised') and r['_grp'] in MIXED and not r['_bad']]
print('过程 A 样本：%d 县 / %d 村（进入安排 %d）' % (
    len(VAR_A_CTY), len(subA), sum(1 for r in subA if r['status'] == 'A_2017')))
print('过程 B 样本：%d 县 / %d 村（当年支持 %d）' % (
    len(MIXED), len(subB), sum(1 for r in subB if r['status'] == 'A_2017')))

results = []
print()
print('########## 过程 A：是否进入 2017 年支持安排 ##########')
show('A-M0 基准（无暴露，仅地形与可达性）', subA, ['elev', 'dist', 'relief'], nb=NB_SENS, save=results)
show('A-M1 机制（距离型暴露）', subA, ['ds'], nb=NB_SENS, save=results)
show('A-M2 核心（已支持 vs 未支持暴露）', subA, ['ds', 'dn'], nb=NB_SENS, diff=('ds', 'dn'), save=results)
show('A-M3 计数型暴露（已获支持村数）', subA, ['ns'], nb=NB_SENS, save=results)
show('A-M4 核心 + 遗产集聚对照（计数）', subA, ['ns', 'nn'], nb=NB_SENS, diff=('ns', 'nn'), save=results)
show('A-M5 核心 + 地形与可达性控制', subA,
     ['ds', 'dn', 'elev', 'dist', 'relief'], nb=NB_SENS, diff=('ds', 'dn'), save=results)

print()
print('########## 过程 B：已进入安排者中当年还是次年 ##########')
show('B-M0 基准（无暴露）', subB, ['elev', 'dist', 'relief'], nb=NB_SENS, save=results)
show('B-M1 机制（距离型暴露）', subB, ['ds'], nb=NB_SENS, save=results)
show('B-M2 核心（已支持 vs 未支持暴露）', subB, ['ds', 'dn'], nb=NB_SENS, diff=('ds', 'dn'), save=results)
show('B-M3 核心 + 地形与可达性控制', subB,
     ['ds', 'dn', 'elev', 'dist', 'relief'], nb=NB_SENS, diff=('ds', 'dn'), save=results)
show('B-M4 计数型（已获支持村数）', subB, ['ns', 'nn'], nb=NB_SENS, diff=('ns', 'nn'), save=results)

with open('data/master/exposure_results.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print()
print('结果写入 data/master/exposure_results.csv（种子 %d）' % SEED)
