# -*- coding: utf-8 -*-
"""
133：早/晚支持暴露的系数差检验

131 报告的是 d_early 与 d_late 各自的系数。"历史支持经验"假设要求检验的是
两者之差（靠近早支持村相对靠近晚支持村的增量），因此这里直接对差做 bootstrap。

  模型：y ~ dist + elev + rng + a·(d_early + d_late)/2 + b·(d_late − d_early)
  b 即"早晚对比"系数；同理对计数型。

输出 data/master/contrast_test.txt
"""
import csv, sys, os, math, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
SEED = 20261030
B = 2000

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
    de = math.log1p(float(e['d_nearest_early']))
    dl = math.log1p(float(e['d_nearest_late']))
    ne, nl = float(e['n_early_10']), float(e['n_late_10'])
    recs.append({'grp': r['province'] + '|' + r['county'], 'st': r['status'],
                 'dist': math.log1p(float(d['dist_km'])),
                 'elev': float(x['elev_srtm']) / 100.0,
                 'rng': float(x['elev_range_srtm']) / 100.0,
                 'd_sum': (de + dl) / 2, 'd_dif': dl - de,
                 'n_sum': (ne + nl) / 2, 'n_dif': nl - ne,
                 'yA': 1.0 if r['status'] in ('A_2017', 'B_2018promised') else 0.0,
                 'yB': 1.0 if r['status'] == 'A_2017' else (0.0 if r['status'] == 'B_2018promised' else -1.0)})


def vary(sub, ykey):
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in ok]


def prep(sub, cols):
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub])
    g = np.array([gi[r['grp']] for r in sub])
    return X, g, keys


def run(tag, sub, ykey, cols, names):
    y = np.array([r[ykey] for r in sub])
    X, g, keys = prep(sub, cols)
    res = ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300)
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    ks = sorted(buckets)
    rng = np.random.default_rng(SEED)
    bs = []
    for b in range(B):
        pick = rng.integers(0, len(ks), len(ks))
        idx = np.array([i for j in range(len(ks)) for i in buckets[ks[pick[j]]]])
        yb = y[idx]
        if len(set(yb)) < 2:
            continue
        k2 = sorted({sub[i]['grp'] for i in idx})
        gi2 = {k: i for i, k in enumerate(k2)}
        gb = np.array([gi2[sub[i]['grp']] for i in idx])
        try:
            bs.append(ConditionalLogit(yb, X[idx], groups=gb).fit(disp=0, maxiter=300).params)
        except Exception:
            pass
    bs = np.array(bs)
    lines = ['--- %s：%d 县 %d 村 ---' % (tag, len(keys), len(sub))]
    lines.append('%-18s %8s %8s %18s %8s' % ('变量', 'beta', 'OR', 'boot 95%CI', 'boot p'))
    for k, nm in enumerate(names):
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        lines.append('%-18s %8.3f %8.3f [%7.3f,%7.3f] %8.3f'
                     % (nm, res.params[k], math.exp(res.params[k]), lo, hi, p))
    return '\n'.join(lines)


out = []
A = vary([r for r in recs if r['st'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')], 'yA')
Bs = vary([r for r in recs if r['st'] in ('A_2017', 'B_2018promised')], 'yB')
out.append('=== 早/晚支持暴露的对比系数（县级 block bootstrap B=%d，SEED=%d）===' % (B, SEED))
out.append('d_dif = log1p(d_late) − log1p(d_early)；n_dif = n_late_10 − n_early_10')
out.append('系数为正表示：靠近"晚支持"历史村（相对靠近"早支持"村）更不易进入/更晚获得支持')
out.append('')
out.append('[过程A] 是否进入 2017 年支持安排')
out.append(run('A 距离型', A, 'yA', ['dist', 'elev', 'rng', 'd_sum', 'd_dif'],
               ['dist', 'elev', 'rng', 'd_均值', 'd_差(晚−早)']))
out.append(run('A 计数型', A, 'yA', ['dist', 'elev', 'rng', 'n_sum', 'n_dif'],
               ['dist', 'elev', 'rng', 'n_均值', 'n_差(晚−早)']))
out.append('')
out.append('[过程B] 当年支持 vs 拟次年支持')
out.append(run('B 距离型', Bs, 'yB', ['dist', 'elev', 'rng', 'd_sum', 'd_dif'],
               ['dist', 'elev', 'rng', 'd_均值', 'd_差(晚−早)']))
out.append(run('B 计数型', Bs, 'yB', ['dist', 'elev', 'rng', 'n_sum', 'n_dif'],
               ['dist', 'elev', 'rng', 'n_均值', 'n_差(晚−早)']))

txt = '\n'.join(out)
print(txt)
open(os.path.join(D, 'master', 'contrast_test.txt'), 'w', encoding='utf-8').write(txt)
