# -*- coding: utf-8 -*-
"""构建"既有财政支持经验"暴露变量（第三十六部分核心变量）

思路
  1) 前三批认定村落点位：geodoi 已发表空间数据集（2555 村），取三省 313 村
  2) 与本地 2014—2016 年中央财政支持名单匹配，得到每个历史村的支持状态
  3) 对第四批 279 村计算周边（5 / 10 / 20 km）历史认定村数、已获支持村数、比例与最近距离

关键区分
  n_pre_design  周边前三批认定村落数，代表遗产集聚
  n_pre_sup     周边 2014—2016 已列入中央财政支持的历史村落数，代表既有项目经验
"""
import csv, sys, math, collections, re

sys.stdout.reconfigure(encoding='utf-8')
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

T3 = {'浙江省', '安徽省', '江苏省'}

# ---------- 1. 前三批点位 ----------
pts = list(csv.DictReader(open('data/geo/geodoi/points2555.csv', encoding='utf-8-sig')))
pre = [r for r in pts if r['prov'] in T3]
print('空间库三省前三批村：%d（全国 %d）' % (len(pre), len(pts)))
for r in pre:
    r['lon'] = float(r['lon']); r['lat'] = float(r['lat'])
    r['dist'] = (r['dist'] or '').strip()
    r['town'] = (r['town'] or '').strip()
    r['vill'] = (r['vill'] or '').strip()

# ---------- 2. 支持名单 ----------
mr = list(csv.DictReader(open('data/tcv_funding/match_result.csv', encoding='utf-8-sig')))
mrn = list(csv.DictReader(open('data/tcv_raw.csv', encoding='utf-8-sig')))
byname = {}
for r in mrn:
    byname.setdefault((r['prov'], r['village'].strip()), r['batch'])
pre_rows = [r for r in mr if r['batch'] in ('1', '2', '3')]
print('本地三省前三批村：%d' % len(pre_rows))


def norm(s):
    return re.sub(r'[·\s、（(）)]', '', s or '')


# 用子串匹配：点位 (dist, town, vill) 是否都出现在名录完整地址中
matched, unmatched, amb = 0, [], 0
rule = collections.Counter()
for r in pre:
    d, t, v = norm(r['dist']), norm(r['town']), norm(r['vill'])
    pool = [p for p in pre_rows if p['prov'] == r['prov']]
    c3 = [p for p in pool if d and d in norm(p['village']) and t and t in norm(p['village'])
          and v[:3] and v[:3] in norm(p['village'])]
    c2 = [p for p in pool if d and d in norm(p['village']) and v[:3] and v[:3] in norm(p['village'])]
    c1 = [p for p in pool if v[:3] and v[:3] in norm(p['village'])]
    if len(c3) == 1:
        hit, rl = c3[0], 'village+town+county'
    elif len(c3) > 1:
        hit, rl = c3[0], 'ambiguous'
        amb += 1
    elif len(c2) == 1:
        hit, rl = c2[0], 'village+county'
    elif len(c2) > 1:
        hit, rl = c2[0], 'ambiguous'
        amb += 1
    elif len(c1) == 1:
        hit, rl = c1[0], 'village_only'
    elif len(c1) > 1:
        hit, rl = c1[0], 'ambiguous'
        amb += 1
    else:
        r['support_year'], r['support_batch'], r['match_rule'] = '', '', 'miss'
        unmatched.append(r)
        continue
    r['support_year'], r['support_batch'] = hit['support_year'], hit['support_batch']
    r['match_rule'] = rl
    rule[rl] += 1
    matched += 1
print('点位与支持名单匹配：%d / %d；规则 %s；未匹配 %d' % (
    matched, len(pre), dict(rule), len(unmatched)))
if unmatched:
    print('未匹配示例（前 10）：')
    for r in unmatched[:10]:
        print('   %s %s%s%s' % (r['prov'], r['dist'], r['town'], r['vill']))

sup_years = collections.Counter(r['support_year'] for r in pre)
print('三省前三批村支持年份分布：%s' % dict(sup_years))
n_sup = sum(1 for r in pre if r['support_year'] in ('2014.0', '2015.0', '2016.0'))
print('2014—2016 已获支持 %d / %d = %.1f%%' % (n_sup, len(pre), 100.0 * n_sup / len(pre)))

# ---------- 4. 暴露变量 ----------
v4 = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
print()
print('第四批目标村：%d' % len(v4))


def hav(lat1, lon1, lat2, lon2):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
    return 2 * R * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                       math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


sup_pts = [r for r in pre if r['support_year'] in ('2014.0', '2015.0', '2016.0')]
notsup_pts = [r for r in pre if r['support_year'] not in ('2014.0', '2015.0', '2016.0')]
print('历史认定村中：已获支持 %d，未获支持 %d' % (len(sup_pts), len(notsup_pts)))
RADII = [5, 10, 20]
out = []
for v in v4:
    la, lo = float(v['latitude']), float(v['longitude'])
    rec = {'village_id': v['village_id'], 'province': v['province'], 'county': v['county'],
           'village': v['village'], 'status': v['status'], 'latitude': la, 'longitude': lo}
    d_all = sorted(hav(la, lo, p['lat'], p['lon']) for p in pre)
    d_sup = sorted(hav(la, lo, p['lat'], p['lon']) for p in sup_pts)
    d_nosup = sorted(hav(la, lo, p['lat'], p['lon']) for p in notsup_pts)
    for R in RADII:
        rec['n_pre_design_%d' % R] = sum(1 for d in d_all if d <= R)
        rec['n_pre_sup_%d' % R] = sum(1 for d in d_sup if d <= R)
        rec['n_pre_notsup_%d' % R] = sum(1 for d in d_nosup if d <= R)
        rec['share_sup_%d' % R] = round(rec['n_pre_sup_%d' % R] / rec['n_pre_design_%d' % R], 3) \
            if rec['n_pre_design_%d' % R] else ''
    rec['d_nearest_pre'] = round(d_all[0], 3) if d_all else ''
    rec['d_nearest_sup'] = round(d_sup[0], 3) if d_sup else ''
    rec['d_nearest_notsup'] = round(d_nosup[0], 3) if d_nosup else ''
    out.append(rec)

cols = list(out[0].keys())
with open('data/master/exposure_vars.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out)
print('写出 data/master/exposure_vars.csv（%d 行）' % len(out))

# ---------- 5. 诊断 ----------
print()
print('== 暴露变量分布（279 村）==')
for R in RADII:
    a = [r['n_pre_design_%d' % R] for r in out]
    b = [r['n_pre_sup_%d' % R] for r in out]
    s = [r['share_sup_%d' % R] for r in out if r['share_sup_%d' % R] != '']
    print('%2d km：历史认定村 中位 %.0f（0 值 %d 村）；已获支持村 中位 %.0f（0 值 %d 村）；支持比例 中位 %.2f（n=%d）' % (
        R, sorted(a)[len(a) // 2], sum(1 for x in a if x == 0),
        sorted(b)[len(b) // 2], sum(1 for x in b if x == 0),
        sorted(s)[len(s) // 2], len(s)))
print('到最近历史认定村 中位 %.2f km；到最近已获支持村 中位 %.2f km' % (
    sorted(r['d_nearest_pre'] for r in out)[len(out) // 2],
    sorted(r['d_nearest_sup'] for r in out)[len(out) // 2]))


def corr(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((a - my) ** 2 for a in y) ** 0.5
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy + 1e-18)


print()
print('== 遗产集聚与支持经验的相关（共线诊断）==')
for R in RADII:
    x = [r['n_pre_design_%d' % R] for r in out]
    y = [r['n_pre_sup_%d' % R] for r in out]
    z = [r['n_pre_notsup_%d' % R] for r in out]
    print('%2d km：corr(n_design, n_sup) = %.3f；corr(n_sup, n_notsup) = %.3f；corr(n_design, n_notsup) = %.3f' % (
        R, corr(x, y), corr(y, z), corr(x, z)))
    print('      10 km 内有未获支持历史村的第四批村：%d；有已获支持历史村的：%d' % (
        sum(1 for r in out if r['n_pre_notsup_%d' % R]), sum(1 for r in out if r['n_pre_sup_%d' % R])))
print()
print('== 距离型暴露（可分离性检验）==')
ds = [r['d_nearest_sup'] for r in out]
dn = [r['d_nearest_notsup'] for r in out]
print('到最近已获支持村：中位 %.2f km；到最近未获支持历史村：中位 %.2f km；两者相关 %.3f' % (
    sorted(ds)[len(ds) // 2], sorted(dn)[len(dn) // 2], corr(ds, dn)))
print('最近的历史村未获支持的第四批村数：%d' % sum(1 for r in out if r['d_nearest_notsup'] < r['d_nearest_sup']))

print()
print('== 分状态描述（10 km 口径）==')
for st in ('A_2017', 'B_2018promised', 'C_not_in_1044'):
    g = [r for r in out if r['status'] == st]
    a = sorted(r['n_pre_design_10'] for r in g)
    b = sorted(r['n_pre_sup_10'] for r in g)
    d = sorted(r['d_nearest_sup'] for r in g)
    print('%s n=%d  历史认定村中位 %.0f  已获支持村中位 %.0f  到最近已支持村中位 %.2f km' % (
        st, len(g), a[len(a) // 2], b[len(b) // 2], d[len(d) // 2]))
