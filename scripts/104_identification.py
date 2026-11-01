# -*- coding: utf-8 -*-
"""
第四批村落支持时序的识别可行性统计。
用法： python dofile/104_identification.py
输出： data/tcv_funding/official/identification.txt
"""
import csv, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
OFF = Path('data/tcv_funding/official')
rows = list(csv.DictReader((OFF / 'batch4_matched.csv').open(encoding='utf-8-sig')))
N = len(rows)


def county_key(r):
    return (r['prov'], r['county'] or r['city'] or r['prov'])


out = []
P = out.append
P('第四批（2016年认定）1598村 · 支持时序识别可行性')
P('=' * 60)
P('')
P('一、事件结构')
arm = collections.Counter(r['first_batch'] or 'D' for r in rows)
for k in ['2017', '2018-1', '2018-2', 'D']:
    P('  %-8s %5d  %5.1f%%' % (k, arm[k], 100 * arm[k] / N))
P('  事件合计 %d（%.1f%%），右删失 %d（%.1f%%）' % (N - arm['D'], 100 * (N - arm['D']) / N, arm['D'], 100 * arm['D'] / N))
dup = [r for r in rows if int(r['n_batch']) > 1]
P('  同一村被多个批次重复列入：%d 村' % len(dup))
if dup:
    for r in dup[:10]:
        P('    %s  %s' % (r['full'], r['batches']))
P('')

P('二、县内可比单元（同一县第四批村≥2 且 既有事件又有删失）')
byc = collections.defaultdict(list)
for r in rows:
    byc[county_key(r)].append(r)
c_multi = {k: v for k, v in byc.items() if len(v) >= 2}
c_mixed = {k: v for k, v in c_multi.items() if 0 < sum(1 for r in v if r['first_batch']) < len(v)}
P('  有第四批村的县（区）数          %4d' % len(byc))
P('  其中含≥2个第四批村的县          %4d  覆盖 %d 村' % (len(c_multi), sum(len(v) for v in c_multi.values())))
P('  其中兼有事件与删失的县          %4d  覆盖 %d 村' % (len(c_mixed), sum(len(v) for v in c_mixed.values())))
P('')

P('三、县内时序差异（同一县事件发生在两个及以上不同年份档）')
c_time = {}
for k, v in c_multi.items():
    yrs = {r['first_batch'] for r in v if r['first_batch']}
    if len(yrs) >= 2:
        c_time[k] = (v, yrs)
P('  县内出现≥2个支持年份档的县      %4d  覆盖 %d 村' % (len(c_time), sum(len(v) for v, _ in c_time.values())))
P('  其中"2017 与 2018-1"并存（同批审查、差一年）  %4d 县'
  % sum(1 for _, ys in c_time.values() if {'2017', '2018-1'} <= ys))
P('')

P('四、分省覆盖与时序（用于区域条件检验）')
byp = collections.defaultdict(collections.Counter)
for r in rows:
    byp[r['prov']][r['first_batch'] or 'D'] += 1
P('  %-10s %6s %6s %6s %6s %6s %7s' % ('省份', '村数', '2017', '2018-1', '2018-2', '未列入', '覆盖率'))
for p, c in sorted(byp.items(), key=lambda x: -sum(x[1].values())):
    tot = sum(c.values())
    P('  %-10s %6d %6d %6d %6d %6d %6.1f%%' % (p, tot, c['2017'], c['2018-1'], c['2018-2'], c['D'],
                                               100 * (tot - c['D']) / tot))
P('')

P('五、判定门槛对照')
P('  事件村 ≥1500     实际 %d           %s' % (N - arm['D'], '通过' if N - arm['D'] >= 1500 else '未达（1175/1500）'))
P('  县内可比单元 ≥100 实际 %d           %s' % (len(c_mixed), '通过' if len(c_mixed) >= 100 else '未达'))
txt = '\n'.join(out)
print(txt)
(OFF / 'identification.txt').write_text(txt, encoding='utf-8')
