# -*- coding: utf-8 -*-
"""主检验与扩展检验的正式估计（条件 Logit 精确条件似然 + 县级 block bootstrap）

主检验（过程 B）：已进入 2017 年安排的村落中，2017 当年支持 = 1，拟 2018 支持 = 0
扩展检验（过程 A）：三省第四批村落中，进入 2017 年任一安排 = 1，未进入 = 0
变量尺度：海拔与 1km 起伏以百米为单位；到县城距离取 log(1+km)
主推断：县级 block bootstrap（有放回重抽县，重估完整条件 Logit），SEED=20261030
"""
import csv, sys, os, math, collections, time
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
SEED = 20261030
NB_MAIN, NB_SENS = 5000, 2000

rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
BAD = {('建德市', '建南村章家自然村')}          # 到所属县界 42.7 km，落在富阳区腹地
EDGE = {('东阳市', '李宅村'), ('歙县', '萌坑村')}  # 边界附近（2.1 / 0.4 km）
for r in rows:
    r['_bad'] = (r['county'], r['village']) in BAD
    r['_edge'] = (r['county'], r['village']) in EDGE

VAR = {'elev': lambda r: float(r['elev_srtm30']) / 100.0,
       'dist': lambda r: math.log1p(float(r['dist_county_km'])),
       'relief': lambda r: float(r['elev_range_1km_srtm30']) / 100.0}
VAR_A = {'elev': lambda r: float(r['elev_aster30']) / 100.0,
         'dist': VAR['dist'],
         'relief': lambda r: float(r['elev_range_1km_aster30']) / 100.0}
LABEL = {'elev': '海拔（百米）', 'dist': 'log(1+到县城公里)', 'relief': '1km 起伏（百米）'}


def build(sub, cols, getter):
    y = np.array([1.0 if r['status'] == 'A_2017' else 0.0 for r in sub])
    X = np.array([[getter[c](r) for c in cols] for r in sub], float)
    keys = sorted({r['_grp'] for r in sub})
    idx = {k: i for i, k in enumerate(keys)}
    g = np.array([idx[r['_grp']] for r in sub])
    return y, X, g


def clogit(sub, cols, getter=VAR):
    y, X, g = build(sub, cols, getter)
    res = ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300)
    return res


def boot(sub, cols, getter=VAR, nb=NB_MAIN, seed=SEED):
    rng = np.random.default_rng(seed)
    cty = sorted({r['_grp'] for r in sub})
    buck = collections.defaultdict(list)
    for r in sub:
        buck[r['_grp']].append(r)
    out = []
    for b in range(nb):
        pick = rng.integers(0, len(cty), len(cty))
        s = []
        for j in range(len(cty)):
            for r in buck[cty[pick[j]]]:
                rr = dict(r)
                rr['_grp'] = '%s#%d' % (r['_grp'], j)
                s.append(rr)
        try:
            res = clogit(s, cols, getter)
            if np.all(np.isfinite(res.params)) and np.max(np.abs(res.params)) < 50:
                out.append(res.params)
        except Exception:
            continue
    return np.array(out)


def show(title, sub, cols, getter=VAR, nb=NB_MAIN, save=None):
    res = clogit(sub, cols, getter)
    B = boot(sub, cols, getter, nb=nb)
    print()
    print('===== %s =====' % title)
    print('样本 %d 村 / %d 县；事件 %d / %d' % (
        len(sub), len({r['_grp'] for r in sub}), int(sum(1 for r in sub if r['status'] == 'A_2017')), len(sub)))
    print('%-18s %8s %8s %8s %18s %8s' % ('变量', 'beta', 'se_cond', 'OR', 'bootstrap 95%CI', 'boot_p'))
    recs = []
    for i, c in enumerate(cols):
        b = res.params[i]
        lo, hi = np.percentile(B[:, i], [2.5, 97.5])
        d = B[:, i] - B[:, i].mean()
        p = 2 * min((d <= -abs(b)).mean(), (d >= abs(b)).mean())
        p = min(1.0, max(p, 1.0 / max(len(B), 2)))
        print('%-18s %8.3f %8.3f %8.3f %18s %8.3f' % (
            LABEL.get(c, c), b, res.bse[i], math.exp(b), '[%.3f, %.3f]' % (lo, hi), p))
        recs.append({'model': title, 'var': c, 'beta': round(b, 4), 'se_cond': round(res.bse[i], 4),
                     'OR': round(math.exp(b), 4), 'ci_lo': round(lo, 4), 'ci_hi': round(hi, 4),
                     'boot_p': round(p, 4), 'n': len(sub), 'n_county': len({r['_grp'] for r in sub}),
                     'nboot': len(B)})
    if save is not None:
        save.extend(recs)
    return res, B


# ---------- 样本构造 ----------
for r in rows:
    r['_grp'] = r['province'] + '|' + r['county']
    r['_key'] = (r['county'], r['village'])

abc = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    abc[r['_grp']][{'A_2017': 0, 'B_2018promised': 1, 'C_not_in_1044': 2}[r['status']]] += 1
MIXED = {k for k, v in abc.items() if v[0] and v[1]}
VAR_A_COUNTY = {k for k, v in abc.items() if (v[0] + v[1]) and v[2]}

main = [r for r in rows if r['status'] in ('A_2017', 'B_2018promised')
        and r['_grp'] in MIXED and not r['_bad']]
print('主检验样本：%d 村 / %d 县（A %d / B %d）' % (
    len(main), len({r['_grp'] for r in main}),
    sum(1 for r in main if r['status'] == 'A_2017'),
    sum(1 for r in main if r['status'] == 'B_2018promised')))

# ---------- 描述性 ----------
print()
print('== 描述性（主检验样本）==')
for st in ('A_2017', 'B_2018promised'):
    g = [r for r in main if r['status'] == st]
    for nm, f in [('海拔', lambda r: float(r['elev_srtm30'])),
                  ('到县城km', lambda r: float(r['dist_county_km'])),
                  ('1km起伏', lambda r: float(r['elev_range_1km_srtm30']))]:
        v = sorted(f(r) for r in g)
        print('  %s %-8s n=%d 中位 %.1f  四分位 [%.1f, %.1f]' % (
            st, nm, len(g), v[len(v) // 2], v[len(v) // 4], v[3 * len(v) // 4]))
    print()

# 县内均值差（县等权）+ bootstrap
def county_diff(field, sub=main):
    ds, ws = [], []
    for k in sorted({r['_grp'] for r in sub}):
        g = [r for r in sub if r['_grp'] == k]
        a = [float(r[field]) for r in g if r['status'] == 'A_2017']
        b = [float(r[field]) for r in g if r['status'] == 'B_2018promised']
        if a and b:
            ds.append(np.mean(a) - np.mean(b))
            ws.append(k)
    return np.array(ds), ws

rng = np.random.default_rng(SEED)
print('== 县内均值差（A − B，县等权，n=%d 县）==' % len(MIXED))
for field, unit in [('elev_srtm30', 'm'), ('dist_county_km', 'km'), ('elev_range_1km_srtm30', 'm')]:
    ds, ws = county_diff(field)
    bs = []
    for _ in range(NB_MAIN):
        idx = rng.integers(0, len(ds), len(ds))
        bs.append(ds[idx].mean())
    lo, hi = np.percentile(bs, [2.5, 97.5])
    d0 = ds.mean()
    bb = np.array(bs) - np.array(bs).mean()
    p = 2 * min((bb <= -abs(d0)).mean(), (bb >= abs(d0)).mean())
    print('  %-24s 均值差 %+.2f %s  bootstrap 95%%CI [%.2f, %.2f]  p %.3f  县符号 %d负/%d正' % (
        field, d0, unit, lo, hi, min(1.0, max(p, 1.0 / NB_MAIN)),
        int((ds < 0).sum()), int((ds > 0).sum())))

# ---------- 主检验 ----------
results = []
show('主检验 · 过程 B：2017 当年 vs 拟 2018（三变量）', main, ['elev', 'dist', 'relief'], save=results)
show('主检验 · 过程 B：单变量 到县城距离', main, ['dist'], nb=NB_MAIN, save=results)
show('主检验 · 过程 B：单变量 海拔', main, ['elev'], nb=NB_MAIN, save=results)
show('主检验 · 过程 B：单变量 1km 起伏', main, ['relief'], nb=NB_MAIN, save=results)

# ---------- 敏感性 ----------
print()
print('########## 敏感性 ##########')
s1 = [r for r in rows if r['status'] in ('A_2017', 'B_2018promised') and r['_grp'] in MIXED]
show('敏感性 1：不剔除坐标异常（102 条）', s1, ['elev', 'dist', 'relief'], nb=NB_SENS, save=results)
s2 = [r for r in main if not r['_edge']]
show('敏感性 2：同时剔除 4 条县界外点（100 条）', s2, ['elev', 'dist', 'relief'], nb=NB_SENS, save=results)
s3 = [r for r in main if r['province'] == '浙江省']
show('敏感性 3：仅浙江 15 县', s3, ['elev', 'dist', 'relief'], nb=NB_SENS, save=results)
show('敏感性 4：高程与起伏改用 ASTER 30m', main, ['elev', 'dist', 'relief'], getter=VAR_A, nb=NB_SENS, save=results)
show('敏感性 5：海拔 + 距离（不含起伏）', main, ['elev', 'dist'], nb=NB_SENS, save=results)

# 逐县删除
print()
print('== 敏感性 6：逐县删除（jackknife）==')
ctys = sorted({r['_grp'] for r in main})
jk = collections.defaultdict(list)
for c in ctys:
    sub = [r for r in main if r['_grp'] != c]
    try:
        res = clogit(sub, ['elev', 'dist', 'relief'])
        for i, v in enumerate(['elev', 'dist', 'relief']):
            jk[v].append(res.params[i])
    except Exception:
        pass
for v in ['elev', 'dist', 'relief']:
    a = np.array(jk[v])
    print('  %-8s beta 范围 [%.3f, %.3f]；符号恒定：%s；删除后最大 |beta| 变化 %.3f' % (
        v, a.min(), a.max(), '是' if (a > 0).all() or (a < 0).all() else '否',
        np.abs(a - clogit(main, ['elev', 'dist', 'relief']).params[['elev', 'dist', 'relief'].index(v)]).max()))

# ---------- 扩展检验：过程 A ----------
print()
print('########## 扩展检验 ##########')
subA = [r for r in rows if r['_grp'] in VAR_A_COUNTY and not r['_bad']]
for r in subA:
    r['statusA'] = 'A_2017' if r['status'] in ('A_2017', 'B_2018promised') else 'B_2018promised'
subA2 = []
for r in subA:
    rr = dict(r)
    rr['status'] = r['statusA']
    subA2.append(rr)
print('样本：有组内变异的县 %d，村 %d（进入安排 %d）' % (
    len(VAR_A_COUNTY), len(subA2), sum(1 for r in subA2 if r['status'] == 'A_2017')))
show('扩展检验 · 过程 A：是否进入 2017 年安排', subA2, ['elev', 'dist', 'relief'], nb=NB_SENS, save=results)

with open('data/master/main_results.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print()
print('结果已写入 data/master/main_results.csv（种子 %d）' % SEED)
