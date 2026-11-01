# -*- coding: utf-8 -*-
"""
124：全国主分析（第四批 1598 村）

过程A：是否进入 2017 年 5 月公布的 1044 村支持安排
过程B：已进入安排者中，2017 当年支持 还是 2017 年宣布拟于 2018 支持

模型：县分层条件 Logit（statsmodels 精确条件似然，等价于县固定效应）
推断：县级 block bootstrap（重抽整县），SEED 20261030
主变量
  log(1 + 到县城距离 km)                      空间可达性（认定前已确定）
  log(1 + 到最近"认定前已获支持"历史村距离)     历史财政支持经验
  log(1 + 到最近"已认定但未见于支持名单"村距离)  历史遗产集聚对照
  海拔（百米）、1 km 起伏（百米）              地形障碍
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
elev = {r['village_id']: r for r in csv.DictReader(open(os.path.join(D, 'elev_national.csv'),
                                                        encoding='utf-8-sig'))}
cc_path = os.path.join(ROOT, 'data', 'geo', 'county_center_national.csv')
dist_file = os.path.join(D, 'dist_county_national.csv')

# ---------- 到县城距离 ----------
if not os.path.exists(dist_file):
    sys.exit('缺 %s，先跑 123' % dist_file)
distc = {}
for r in csv.DictReader(open(dist_file, encoding='utf-8-sig')):
    if r['dist_km']:
        distc[r['village_id']] = float(r['dist_km'])


def hav(a1, o1, a2, o2):
    R = 6371.0088
    p1, p2 = math.radians(a1), math.radians(a2)
    dp = p2 - p1
    dl = math.radians(o2 - o1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1, math.sqrt(x)))


def build():
    recs = []
    for vid, r in m.items():
        e = exp.get(vid)
        el = elev.get(vid)
        if not e or not el or vid not in distc:
            continue
        rec = {'vid': vid, 'prov': r['province'], 'cty': r['county'], 'status': r['status'],
               'grp': r['province'] + '|' + r['county'],
               'dist': math.log1p(distc[vid]),
               'd_sup': math.log1p(float(e['d_nearest_sup'])) if e['d_nearest_sup'] != '' else None,
               'd_not': math.log1p(float(e['d_nearest_notsup'])) if e['d_nearest_notsup'] != '' else None,
               'n_sup': float(e['n_sup_10']), 'n_not': float(e['n_notsup_10']),
               'n_pre': float(e['n_pre_10']),
               'elev': float(el['elev_srtm']) / 100 if el['elev_srtm'] != '' else None,
               'rng': float(el['elev_range_srtm']) / 100 if el['elev_range_srtm'] != '' else None}
        if None in (rec['d_sup'], rec['d_not'], rec['elev'], rec['rng']):
            continue
        recs.append(rec)
    return recs


recs = build()
print('可用样本 %d 村 / %d 县' % (len(recs), len({r['grp'] for r in recs})))

SPEC = {
    '可达性': ['dist'],
    '可达性+地形': ['dist', 'elev', 'rng'],
    '经验(距离型)': ['dist', 'd_sup', 'd_not', 'elev', 'rng'],
    '经验(计数型)': ['dist', 'n_sup', 'n_not', 'elev', 'rng'],
    '经验(实施经验口径)': ['dist', 'd_exp', 'd_not', 'elev', 'rng'],
}
# 实施经验口径的最近距离
for r in recs:
    e = exp[r['vid']]
    r['d_exp'] = math.log1p(float(e['d_nearest_exp'])) if e['d_nearest_exp'] != '' else r['d_sup']


def sample_for(kind):
    """返回可用于估计的样本：组内因变量必须有变异"""
    if kind == 'A':
        sub = [r for r in recs if r['status'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]
        y = np.array([1.0 if r['status'] in ('A_2017', 'B_2018promised') else 0.0 for r in sub])
    else:
        sub = [r for r in recs if r['status'] in ('A_2017', 'B_2018promised')]
        y = np.array([1.0 if r['status'] == 'A_2017' else 0.0 for r in sub])
    keep = []
    for r, yy in zip(sub, y):
        keep.append(r)
    # 组内变异筛选
    gp = collections.defaultdict(list)
    for i, r in enumerate(keep):
        gp[r['grp']].append(y[i])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    idx = [i for i, r in enumerate(keep) if r['grp'] in ok]
    sub = [keep[i] for i in idx]
    y = np.array([y[i] for i in idx])
    return sub, y


def fit(sub, y, cols):
    X = np.array([[r[c] for c in cols] for r in sub])
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    g = np.array([gi[r['grp']] for r in sub])
    res = ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300)
    return res.params, keys


def boot(sub, y, cols, Bn):
    keys = sorted({r['grp'] for r in sub})
    buck = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buck[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    out = []
    for b in range(Bn):
        pick = rng.integers(0, len(keys), len(keys))
        idx = []
        for j in range(len(keys)):
            idx += buck[keys[pick[j]]]
        s2 = [sub[i] for i in idx]
        y2 = y[idx]
        if len(set(y2)) < 2:
            continue
        try:
            p, _ = fit(s2, y2, cols)
        except Exception:
            continue
        if np.all(np.isfinite(p)) and np.max(np.abs(p)) < 20:
            out.append(p)
    return np.array(out) if out else None


def report(kind, cols_list, Bn=B):
    sub, y = sample_for(kind)
    print()
    print('===== 过程%s：%d 县 %d 村 =====' % (kind, len({r['grp'] for r in sub}), len(sub)))
    rows = []
    for name, cols in cols_list.items():
        cols = [c for c in cols if c not in ('d_exp',) or any('d_exp' in r for r in sub)]
        b0, _ = fit(sub, y, cols)
        bs = boot(sub, y, cols, Bn)
        rec = {'spec': name}
        for j, c in enumerate(cols):
            lo, hi = np.percentile(bs[:, j], [2.5, 97.5])
            p = 2 * min((bs[:, j] <= 0).mean(), (bs[:, j] >= 0).mean()) if bs is not None else np.nan
            rec[c] = (b0[j], math.exp(b0[j]), lo, hi, p)
        if 'd_sup' in cols and 'd_not' in cols:
            j1, j2 = cols.index('d_sup'), cols.index('d_not')
            d = bs[:, j1] - bs[:, j2]
            lo, hi = np.percentile(d, [2.5, 97.5])
            p = 2 * min((d <= 0).mean(), (d >= 0).mean())
            rec['d_sup-d_not'] = (b0[j1] - b0[j2], math.exp(b0[j1] - b0[j2]), lo, hi, p)
        if 'n_sup' in cols and 'n_not' in cols:
            j1, j2 = cols.index('n_sup'), cols.index('n_not')
            d = bs[:, j1] - bs[:, j2]
            lo, hi = np.percentile(d, [2.5, 97.5])
            p = 2 * min((d <= 0).mean(), (d >= 0).mean())
            rec['n_sup-n_not'] = (b0[j1] - b0[j2], math.exp(b0[j1] - b0[j2]), lo, hi, p)
        rows.append(rec)
    hdr = ['spec'] + [c for c in cols_list[list(cols_list)[-1]]] + \
        (['d_sup-d_not'] if 'd_sup' in cols_list[list(cols_list)[-1]] else [])
    print('%-18s %10s %8s %10s %10s %8s' % ('设定', '变量', 'beta', 'OR', 'CI低', 'CI高'))
    for rec in rows:
        for c, v in rec.items():
            if c == 'spec':
                continue
            print('%-18s %10s %8.3f %8.3f %10.3f %10.3f %8.3f' % (
                rec['spec'], c, v[0], v[1], v[2], v[3], v[4]))
    return rows


t0 = time.time()
resA = report('A', SPEC)
resB = report('B', SPEC)
print()
print('总耗时 %.0f s' % (time.time() - t0))

# 写结果
with open(os.path.join(D, 'national_results.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['process', 'spec', 'variable', 'beta', 'OR', 'ci_lo', 'ci_hi', 'p_boot'])
    for kind, rs in [('A', resA), ('B', resB)]:
        for rec in rs:
            for c, v in rec.items():
                if c == 'spec':
                    continue
                w.writerow([kind, rec['spec'], c] + [round(x, 4) for x in v])
print('写出 national_results.csv')
