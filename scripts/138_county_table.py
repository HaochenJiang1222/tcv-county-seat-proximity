# -*- coding: utf-8 -*-
"""
138：全国过程A的县内描述统计表（第三十九部分任务三）

目的：让读者直接看到条件 Logit 的负向关联来自多少县，而不只是一个平均系数。

做法
  每个县内部按"到县城距离"的中位数把该县第四批村分为 近 / 远 两组（县内相对，
  剔除跨县水平差异），比较两组的 2017 年支持安排进入率。
  仅在组内同时存在"进入"与"未进入"的县（条件 Logit 实际使用的县）中作跨县汇总。

输出
  data/master/county_table_v3.txt   （表1 全国汇总 / 表2 县级差值分布 / 表3 分省）
  data/master/county_table_v3.csv   （逐县明细）
"""
import csv, os, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
SEED = 20261030

rows = [r for r in csv.DictReader(open(os.path.join(D, 'master', 'exposure_v3.csv'),
                                       encoding='utf-8-sig'))
        if r['dist_km'] not in ('', None) and r['status'] in
        ('A_2017', 'B_2018promised', 'C_not_in_1044')]
for r in rows:
    r['dist_km'] = float(r['dist_km'])
    r['yA'] = int(r['yA'])
print('过程A 样本 %d 村' % len(rows))

lines = []


def P(s=''):
    print(s)
    lines.append(s)


gp = collections.defaultdict(list)
for r in rows:
    gp[r['grp']].append(r)

per = []
for k, v in sorted(gp.items()):
    if len(v) < 2:
        continue
    med = float(np.median([r['dist_km'] for r in v]))
    near = [r for r in v if r['dist_km'] <= med]
    far = [r for r in v if r['dist_km'] > med]
    if not near or not far:
        continue
    rn = sum(r['yA'] for r in near) / len(near)
    rf = sum(r['yA'] for r in far) / len(far)
    per.append({'grp': k, 'prov': v[0]['prov'], 'county': v[0]['county'],
                'n': len(v), 'n_near': len(near), 'n_far': len(far),
                'med_km': round(med, 2),
                'near_km': round(float(np.mean([r['dist_km'] for r in near])), 2),
                'far_km': round(float(np.mean([r['dist_km'] for r in far])), 2),
                'rate_near': round(rn, 4), 'rate_far': round(rf, 4),
                'dif': round(rf - rn, 4),
                'informative': 1 if len({r['yA'] for r in v}) > 1 else 0})

P('=== 138 县内描述统计：近/远组进入率（过程A）===')
P('分组：县内按到县城距离中位数分为 近 / 远 两组')
P('')

# 表1 全国汇总
P('表1 全国汇总')
P('%-24s %8s %8s %8s %8s' % ('样本', '县数', '村数', '近组进入率', '远组进入率'))
for tag, sel in [('全部有近远分组的县', per),
                 ('条件Logit 实际使用的县（组内 y 有变异）', [r for r in per if r['informative'] == 1])]:
    if not sel:
        continue
    nn = sum(r['n_near'] for r in sel)
    nf = sum(r['n_far'] for r in sel)
    rn = sum(r['rate_near'] * r['n_near'] for r in sel) / nn
    rf = sum(r['rate_far'] * r['n_far'] for r in sel) / nf
    P('%-24s %8d %8d %8.3f %8.3f' % (tag, len(sel), nn + nf, rn, rf))
P('')
P('   注：全国汇总按村加权；条件Logit 的县内比较只使用第二行的县')

# 表2 县级差值分布
inf = [r for r in per if r['informative'] == 1]
d = np.array([r['dif'] for r in inf])
P('')
P('表2 县级差值分布（远组进入率 − 近组进入率）')
P('   县数 %d' % len(inf))
P('   均值 %.3f；中位数 %.3f' % (d.mean(), np.median(d)))
qs = np.percentile(d, [10, 25, 50, 75, 90])
P('   分位 10%%/25%%/50%%/75%%/90%%：%.3f / %.3f / %.3f / %.3f / %.3f' % tuple(qs))
neg = int((d < 0).sum())
zero = int((d == 0).sum())
pos = int((d > 0).sum())
P('   负向（远组更低）%d 县 %.1f%%；持平 %d 县；正向 %d 县 %.1f%%'
  % (neg, 100.0 * neg / len(d), zero, pos, 100.0 * pos / len(d)))
rng = np.random.default_rng(SEED)
bs = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(4000)])
lo, hi = np.percentile(bs, [2.5, 97.5])
p = 2 * min((bs <= 0).mean(), (bs >= 0).mean())
P('   县等权均值差 %.3f，95%%CI [%.3f, %.3f]，p %.3f' % (d.mean(), lo, hi, p))
P('   平均近/远组距离：%.1f km vs %.1f km（差 %.1f km）'
  % (np.mean([r['near_km'] for r in inf]), np.mean([r['far_km'] for r in inf]),
     np.mean([r['far_km'] for r in inf]) - np.mean([r['near_km'] for r in inf])))

# 表2b 按县内村数分层
P('')
P('表2b 按县内村数分层（县内村数越多，近/远组的进入率差越有信息量）')
P('%-10s %6s %8s %8s %8s %8s %8s %8s' %
  ('县内村数', '县数', '村数', '近组率', '远组率', '均值差', '负向县', 'CI'))
for lo_n, hi_n in [(2, 3), (4, 5), (6, 9), (10, 999)]:
    sel = [r for r in inf if lo_n <= r['n'] <= hi_n]
    if not sel:
        continue
    nn = sum(x['n_near'] for x in sel)
    nf = sum(x['n_far'] for x in sel)
    rn = sum(x['rate_near'] * x['n_near'] for x in sel) / nn
    rf = sum(x['rate_far'] * x['n_far'] for x in sel) / nf
    dv = np.array([x['dif'] for x in sel])
    bsb = np.array([dv[rng.integers(0, len(dv), len(dv))].mean() for _ in range(4000)])
    l2, h2 = np.percentile(bsb, [2.5, 97.5])
    tag = '%d–%d' % (lo_n, hi_n) if hi_n < 999 else '≥%d' % lo_n
    P('%-10s %6d %8d %8.3f %8.3f %8.3f %8d [%5.2f,%5.2f]'
      % (tag, len(sel), nn + nf, rn, rf, dv.mean(), int((dv < 0).sum()), l2, h2))
P('')
P('   县内村数分布：' + '；'.join(
    '%d 村 %d 县' % (k, v) for k, v in sorted(collections.Counter(r['n'] for r in inf).items())
    if k <= 12))

# 表3 分省
P('')
P('表3 分省（仅列县数 ≥3 的省）')
P('%-10s %6s %6s %8s %8s %8s %8s' %
  ('省', '县数', '村数', '近组率', '远组率', '均值差', '负向县'))
by = collections.defaultdict(list)
for r in inf:
    by[r['prov']].append(r)
tab = []
for k, v in by.items():
    if len(v) < 3:
        continue
    nn = sum(x['n_near'] for x in v)
    nf = sum(x['n_far'] for x in v)
    rn = sum(x['rate_near'] * x['n_near'] for x in v) / nn
    rf = sum(x['rate_far'] * x['n_far'] for x in v) / nf
    dv = np.mean([x['dif'] for x in v])
    ng = sum(1 for x in v if x['dif'] < 0)
    tab.append((k, len(v), nn + nf, rn, rf, dv, ng))
tab.sort(key=lambda x: x[5])
for k, nc, nv, rn, rf, dv, ng in tab:
    P('%-10s %6d %6d %8.3f %8.3f %8.3f %8d' % (k, nc, nv, rn, rf, dv, ng))

with open(os.path.join(D, 'master', 'county_table_v3.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(per[0].keys()))
    w.writeheader()
    w.writerows(per)

open(os.path.join(D, 'master', 'county_table_v3.txt'), 'w', encoding='utf-8').write('\n'.join(lines))
print()
print('写出 county_table_v3.txt / .csv')
