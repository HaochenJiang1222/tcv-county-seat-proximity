# -*- coding: utf-8 -*-
"""诊断主检验发散：变量相关性、县内变异、条件 Logit 收敛（用 statsmodels 精确条件似然）"""
import csv, sys, os, math, collections
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
for r in rows:
    r['elev'] = float(r['elev_srtm30'])
    r['dist'] = float(r['dist_county_km'])
    r['relief'] = float(r['elev_range_1km_srtm30'])

BAD = {('建德市', '建南村章家自然村')}
mix = [r for r in rows if r['status'] in ('A_2017', 'B_2018promised') and (r['county'], r['village']) not in BAD]
abc = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    abc[r['province'] + '|' + r['county']][{'A_2017': 0, 'B_2018promised': 1, 'C_not_in_1044': 2}[r['status']]] += 1
mixed = {k for k, v in abc.items() if v[0] and v[1]}
main = [r for r in mix if (r['province'] + '|' + r['county']) in mixed]
print('主检验样本 %d 村 / %d 县' % (len(main), len(mixed)))

# 1. 相关性与县内变异
V = ['elev', 'dist', 'relief']
M = np.array([[r[v] for v in V] for r in main], float)
print()
print('== 原始相关矩阵 ==')
print(np.round(np.corrcoef(M.T), 3))
# 县内去均值
keys = [r['province'] + '|' + r['county'] for r in main]
dm = M.copy()
for k in set(keys):
    idx = [i for i, kk in enumerate(keys) if kk == k]
    dm[idx] = M[idx] - M[idx].mean(axis=0)
print('== 县内去均值后相关矩阵 ==')
print(np.round(np.corrcoef(dm.T), 3))
print('== 县内标准差（乡村层面可用变异）==')
print(dict(zip(V, np.round(dm.std(axis=0), 2))))
print('全县样本标准差：%s' % dict(zip(V, np.round(M.std(axis=0), 2))))

# 2. 条件 Logit（statsmodels 精确条件似然）
try:
    from statsmodels.discrete.conditional_models import ConditionalLogit
    import statsmodels.api as sm
    y = np.array([1.0 if r['status'] == 'A_2017' else 0.0 for r in main])
    grp = np.array([sorted(mixed).index(k) for k in keys])
    print()
    print('== 条件 Logit（statsmodels 精确条件似然）==')
    for cols in (['elev'], ['dist'], ['relief'], ['elev', 'dist'], ['elev', 'dist', 'relief']):
        X = np.array([[r[c] / (100.0 if c != 'dist' else 1.0) for c in cols] for r in main], float)
        if cols == ['dist']:
            X = np.array([[math.log1p(r['dist'])] for r in main], float)
        elif 'dist' in cols:
            j = cols.index('dist')
            X[:, j] = np.log1p([r['dist'] for r in main])
        try:
            mod = ConditionalLogit(y, X, groups=grp)
            res = mod.fit(disp=0, maxiter=200)
            b = res.params
            se = res.bse
            print('%-28s ' % '+'.join(cols) + '  '.join(
                '%s=%+.3f (se %.3f, p %.3f)' % (c, b[i], se[i], res.pvalues[i]) for i, c in enumerate(cols)))
        except Exception as e:
            print('%-28s 拟合失败 %s' % ('+'.join(cols), str(e)[:100]))
except ImportError as e:
    print('ConditionalLogit 不可用：%s' % e)
