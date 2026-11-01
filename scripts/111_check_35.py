# -*- coding: utf-8 -*-
"""第三十五部分核对
1) 18 县 102 条候选记录的结构（浙江 15 县 / 安徽 3 县）
2) 用户列出的 18 对村举例在母表中是否一 A 一 B
3) 坐标质量：重复坐标检测（geodoi 页面提示"部分坐标以上一级行政单位位置替代"）
"""
import csv, sys, collections, math

sys.stdout.reconfigure(encoding='utf-8')
rows = list(csv.DictReader(open('data/master/master_final_1598.csv', encoding='utf-8-sig')))
T = {'江苏省', '浙江省', '安徽省'}

# ---------- 1. 18 县结构 ----------
byc = collections.defaultdict(list)
for r in rows:
    if r['province'] in T:
        byc[(r['province'], r['county'])].append(r)

mix = []
for k, g in byc.items():
    a = [x for x in g if x['status'] == 'A_2017']
    b = [x for x in g if x['status'] == 'B_2018promised']
    c = [x for x in g if x['status'] == 'C_not_in_1044']
    if a and b:
        mix.append((k[0], k[1], len(g), len(a), len(b), len(c), g))
mix.sort(key=lambda x: (x[0] != '浙江省', -(x[3] + x[4])))

print('== 一、18 个混合状态县（按 A+B 降序）==')
print('| 省份 | 县区 | 认定村 | A当年 | B拟次年 | C未列入 | 候选记录A+B |')
tot = collections.Counter()
for pv, ct, n, na, nb, nc, g in mix:
    print('| %s | %s | %d | %d | %d | %d | %d |' % (pv[:2], ct, n, na, nb, nc, na + nb))
    tot[pv] += na + nb
    tot[pv + '_A'] += na
    tot[pv + '_B'] += nb
print('县数 %d；合计候选记录 %d（A %d / B %d）' % (
    len(mix), sum(tot[x] for x in tot if not x.endswith('_A') and not x.endswith('_B')),
    sum(tot[x] for x in tot if x.endswith('_A')), sum(tot[x] for x in tot if x.endswith('_B'))))
print('浙江 %d 县 %d 条（A%d/B%d）；安徽 %d 县 %d 条（A%d/B%d）' % (
    sum(1 for x in mix if x[0] == '浙江省'), tot['浙江省'], tot['浙江省_A'], tot['浙江省_B'],
    sum(1 for x in mix if x[0] == '安徽省'), tot['安徽省'], tot['安徽省_A'], tot['安徽省_B']))

# ---------- 2. 18 对村举例 ----------
PAIRS = [
    ('松阳县', '何山头', '玉岩'),
    ('建德市', '于合', '麻车岗'),
    ('武义县', '橄榄源', '梁家山'),
    ('仙居县', '管山', '十都英'),
    ('莲都区', '官桥', '堰头'),
    ('缙云县', '宫前', '吾丰'),
    ('东阳市', '李宅', '白坦'),
    ('龙泉市', '炉地垟', '车盂'),
    ('遂昌县', '长濂', '福罗淤'),
    ('天台县', '灵坑', '山头郑'),
    ('诸暨市', '十四都', '次坞'),
    ('泰顺县', '仙居村', '徐岙'),
    ('衢江区', '破石', '洋坑'),
    ('奉化区', '马头', '西坞'),
    ('嵊州市', '崇仁六', '泉岗'),
    ('歙县', '苏村', '庐山'),
    ('休宁县', '枧潭', '樟源里'),
    ('泾县', '宝峰', '九峰'),
]
print()
print('== 二、18 对村举例逐条核对（在母表全量匹配结果中检索）==')
print('| 县区 | 举例A(应2017) | 命中状态 | 举例B(应拟2018) | 命中状态 |')
ok = 0
for ct, na, nb in PAIRS:
    cand = [r for r in rows if r['county'] == ct]
    ha = [r for r in cand if na in r['official_name_2016']]
    hb = [r for r in cand if nb in r['official_name_2016']]
    sa = ','.join(sorted({x['status'] for x in ha})) or '未命中'
    sb = ','.join(sorted({x['status'] for x in hb})) or '未命中'
    good = (sa == 'A_2017' and sb == 'B_2018promised')
    ok += good
    print('| %s | %s | %s%s | %s | %s%s |' % (
        ct, na, sa, '' if good else ' ⚠',
        nb, sb, '' if good else ' ⚠'))
    if not good:
        for x in ha + hb:
            print('     -> %s %s' % (x['official_name_2016'], x['status']))
        if not ha:
            print('     A 侧候选名: ' + '; '.join(x['official_name_2016'] for x in cand if len(na) > 1 and na[0] in x['official_name_2016'])[:200])
        if not hb:
            print('     B 侧候选名: ' + '; '.join(x['official_name_2016'] for x in cand if len(nb) > 1 and nb[0] in x['official_name_2016'])[:200])
print('18 对中状态完全符合预期：%d / 18' % ok)

# ---------- 3. 坐标质量：重复坐标检测 ----------
print()
print('== 三、坐标质量：重复坐标检测（geodoi 提示部分坐标为上一级行政单位位置）==')
def key(r):
    try:
        return (round(float(r['latitude']), 6), round(float(r['longitude']), 6))
    except Exception:
        return None
allc = collections.Counter(key(r) for r in rows if key(r))
dup_groups = {k: v for k, v in allc.items() if v > 1}
n_dup_rows = sum(dup_groups.values())
print('全国 1598 村：有效坐标 %d；重复坐标组 %d；涉及村 %d（占 %.1f%%）' % (
    sum(allc.values()), len(dup_groups), n_dup_rows, 100.0 * n_dup_rows / 1598))
# 重复组内是否同县同乡镇（=点位替代嫌疑高）
grp = collections.defaultdict(list)
for r in rows:
    k = key(r)
    if k and allc[k] > 1:
        grp[k].append(r)
same_town = sum(1 for k, g in grp.items() if len({x['township'] for x in g}) == 1)
print('重复坐标组中，全部村属于同一乡镇的组：%d / %d' % (same_town, len(dup_groups)))
print('最大重复组（前 8）:')
for k, g in sorted(grp.items(), key=lambda x: -len(x[1]))[:8]:
    print('   %d 村 @ %s | %s | %s' % (len(g), k, g[0]['province'] + g[0]['county'] + g[0]['township'],
                                       '; '.join(x['village'] for x in g)[:80]))

# 三省 18 县内部
print()
print('-- 18 县内部坐标重复 --')
cand18 = [r for k in mix for r in k[6]]
c18 = collections.Counter(key(r) for r in cand18 if key(r))
d18 = {k: v for k, v in c18.items() if v > 1}
print('18 县认定村 %d；有效坐标 %d；重复坐标组 %d；涉及村 %d' % (
    len(cand18), sum(c18.values()), len(d18), sum(d18.values())))
g18 = collections.defaultdict(list)
for r in cand18:
    k = key(r)
    if k and c18[k] > 1:
        g18[k].append(r)
for k, g in sorted(g18.items(), key=lambda x: -len(x[1])):
    print('   %d 村 @ %s | %s%s | %s' % (len(g), k, g[0]['county'], g[0]['township'],
                                          '; '.join(x['village'] for x in g)[:70]))

# 102 条候选中重复坐标
cand102 = [r for r in cand18 if r['status'] in ('A_2017', 'B_2018promised')]
c102 = collections.Counter(key(r) for r in cand102 if key(r))
print('102 条候选记录中：有效坐标 %d；重复坐标组 %d；涉及村 %d' % (
    sum(c102.values()), sum(1 for v in c102.values() if v > 1), sum(v for v in c102.values() if v > 1)))

# ---------- 4. 18 县 102 条的点位有效性 & 后续变量可行性 ----------
print()
print('== 四、硬门槛状态 ==')
miss = [r for r in cand102 if not r['latitude'] or r['geolocation_quality'] != 'matched']
print('102 条中无坐标/未匹配点位：%d' % len(miss))
for r in miss:
    print('   ', r['province'], r['official_name_2016'], r['status'])
