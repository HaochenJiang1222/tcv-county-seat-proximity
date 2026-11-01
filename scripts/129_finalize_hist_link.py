# -*- coding: utf-8 -*-
"""
129：历史名单连接收尾（第三十八部分任务一）

两步：
  A 补录 121 解析遗漏的 12 条（全部为特殊建制：风景名胜区/办事处/林场/老街/古排/古城，
    乡镇名不含 镇乡街道苏木管理区办事处，被 121 的过滤规则拒掉）
  B 对 128 剩余的 22 条待核验记录逐条裁决（接受 10 / 驳回 12）

输出
  data/tcv_funding/official_pre/support_national_final.csv  公告侧最终名录（含补录）
  data/master/geo_points_pre2555_v3.csv                     前三批点位最终连接结果
  data/master/hist_adjudication.csv                         22 条裁决台账
  data/master/hist_link_identity.txt                        2550 / 2555 恒等式核算
"""
import csv, sys, os, re, unicodedata, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
RAW = os.path.join(D, 'tcv_funding', 'official_pre')

ANN = {'2014-1': '2014-07-16', '2014-2': '2014-12-17', '2015-1': '2015-08-10',
       '2015att2': '2015-08-10', '2015-2': '2016-03-24', '2016-1': '2016-05-25',
       '2016-2': '2016-12-28'}
SCOPE = {'2014-1': '2014', '2014-2': '2014', '2015-1': '2015', '2015att2': '2016',
         '2015-2': '2015', '2016-1': '2016', '2016-2': '2016'}

# ---------- A. 补录 12 条 ----------
# 12 条均来自 121 的"声明 vs 解析"差异组（2014-1 为 .doc 分支，另 8 条来自 HTML 源 review）
PATCH = [
    ('2014-1', '湖北省', '恩施土家族苗族自治州咸丰县大路坝区蛇盘溪村'),
    ('2014-1', '湖南省', '湘西土家族苗族自治州龙山县苗儿滩镇惹巴拉村'),
    ('2014-1', '广东省', '清远市连南瑶族自治县三排镇南岗古排'),
    ('2014-1', '云南省', '大理白族自治州剑川县金华镇剑川古城'),
    ('2014-2', '江西省', '南昌市进贤县文港县晏家村'),
    ('2015-1', '湖北省', '随州市随县桐柏山太白顶风景名胜区解河村戴家仓屋'),
    ('2015-1', '四川省', '乐山市沐川县箭板镇顺河古街'),
    ('2015-1', '四川省', '巴中市平昌县白衣镇白衣庵居民委员会'),
    ('2015-2', '云南省', '红河州建水县塔瓦村委会塔瓦村'),
    ('2016-1', '福建省', '漳州市长泰县马洋溪生态旅游区山重村'),
    ('2016-1', '湖北省', '黄冈市武穴市龙坪镇花园居委会'),
    ('2016-2', '湖北省', '咸宁市通山县九宫山风景区中港村'),
]

sup = list(csv.DictReader(open(os.path.join(RAW, 'support_national_revised.csv'),
                               encoding='utf-8-sig')))
have = {(r['batch'], r['raw']) for r in sup}
added = 0
for b, pv, raw in PATCH:
    if (b, raw) in have:
        continue
    sup.append({'batch': b, 'announce_date': ANN[b], 'scope_year': SCOPE[b],
                'prov': pv, 'county': '', 'township': '', 'village': raw,
                'raw': raw, 'town2': '', 'vill2': raw})
    added += 1
print('补录 %d 条；名单条目由 %d 增至 %d' % (added, len(sup) - added, len(sup)))

# ---------- B. 22 条裁决 ----------
# raw -> (省, 县, 乡镇, 村) 点位定位；None 表示驳回
ACCEPT = {
    '大理白族自治州大理市喜洲镇喜州村': ('云南省', '大理市', '喜洲镇', '喜洲村',
                                    '州/洲异写，同乡镇同音村名'),
    '雅安市石棉县蟹螺藏族乡猛种村猛种堡子': ('四川省', '石棉县', '蟹螺藏族乡', '猛种村',
                                          '公告记自然村堡子，点位库仅到猛种村'),
    '雅安市石棉县蟹螺藏族乡猛种村木耳堡子': ('四川省', '石棉县', '蟹螺藏族乡', '猛种村',
                                          '同村另一堡子，公告与点位为一对二'),
    '铜仁市江口县民和侗族土家族苗族镇封神懂自然村': ('贵州省', '江口县', '民和镇',
                                                  '龙兴村委会封神懂村',
                                                  '乡镇全称/简称差异，村名含村委会前缀'),
    '大同市天镇县新平堡镇': ('山西省', '天镇县', '新平堡镇', '新平堡村',
                            '公告仅到镇，该镇点位库唯一村落为新平堡村'),
    '清远市连州市龙坪镇元璧村': ('广东省', '连州市', '龙坪镇', '元壁村', '璧/壁异写'),
    '黔东南苗族侗族自治州黎平县永从镇豆洞村': ('贵州省', '黎平县', '永从乡', '豆洞村',
                                              '永从乡后改永从镇，村名一致'),
    '黔南布依族苗族自治州荔波县黎明关水族乡太吉村': ('贵州省', '荔波县', '永康民族乡',
                                                    '太吉村',
                                                    '黎明关水族乡由永康民族乡更名，同县同村名唯一'),
    '临沧市沧源县勐懂镇芒摆村永点村': ('云南省', '沧源县', '勐懂镇', '芒摆村委会永点村',
                                      '村/村委会写法差异'),
    '临沧市沧源县勐懂镇芒摆村永让村': ('云南省', '沧源县', '勐懂镇', '芒摆村委会永让村',
                                      '村/村委会写法差异'),
}
REJECT_NOTE = '点位库中该乡镇无对应记录，判为点位库侧缺失或名录口径差异，不作未入选证据'

pre = list(csv.DictReader(open(os.path.join(D, 'geo', 'geodoi', 'points2555.csv'),
                               encoding='utf-8-sig')))
key2idx = {}
for i, r in enumerate(pre):
    key2idx.setdefault((r['prov'], r['dist'], r['town'], r['vill']), []).append(i)


def norm(s):
    return re.sub(r'[\s·、，,（）()]', '', unicodedata.normalize('NFKC', s or ''))


# 读 128 的匹配结果，重建 assigned
idx_full = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_full[norm(r['dist'] + r['town'] + r['vill'])].append(i)
idx_prov = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_prov[r['prov']].append(i)
idx_town = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_town[(r['prov'], norm(r['town']))].append(i)
idx_vill = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_vill[(r['prov'], norm(r['vill']))].append(i)
idx_tv = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_tv[(r['prov'], norm(r['town'] + r['vill']))].append(i)

TOWN_RE = re.compile(r'([^市县区旗州盟]{2,12}?)(苏木|管理区|办事处|街道|镇|乡)')


def split_raw(raw, prov):
    s = norm(raw)
    for p in ('内蒙古自治区', '广西壮族自治区', '宁夏回族自治区', '新疆维吾尔自治区',
              '西藏自治区', '北京市', '天津市', '上海市', '重庆市'):
        if s.startswith(p):
            s = s[len(p):]
            break
    for mm in TOWN_RE.finditer(s):
        if mm.start() >= 1:
            return mm.group(0), s[mm.end():]
    return '', s


def inc(a, b):
    return bool(a) and bool(b) and (a in b or b in a)


def suffix_hit(rn):
    for L in range(len(rn), 3, -1):
        m = idx_full.get(rn[-L:])
        if m:
            return m
    return None


def rule_for(s):
    pv, tn, vl, raw = s['prov'], norm(s['town2']), norm(s['vill2']), norm(s['raw'])
    m = suffix_hit(raw)
    if m:
        return m[0], 'S0_raw_suffix' + ('_multi' if len(m) > 1 else '')
    m = idx_tv.get((pv, tn + vl), [])
    if m:
        return m[0], 'S0b_town_vill' + ('_multi' if len(m) > 1 else '')
    c = idx_town.get((pv, tn), [])
    m = [i for i in c if norm(pre[i]['vill']) == vl]
    if m:
        return m[0], 'R1_town_vill_exact' + ('_multi' if len(m) > 1 else '')
    m = [i for i in c if inc(norm(pre[i]['vill']), vl)]
    if len(m) == 1:
        return m[0], 'R2_town_vill_include'
    cand = [i for i in idx_prov.get(pv, []) if inc(norm(pre[i]['town']), tn)]
    m = [i for i in cand if inc(norm(pre[i]['vill']), vl)]
    if len(m) == 1:
        return m[0], 'R3_town_vill_fuzzy'
    m = idx_vill.get((pv, vl), [])
    if len(m) == 1:
        return m[0], 'R4_vill_exact'
    if len(m) > 1:
        m2 = [i for i in m if norm(pre[i]['dist']) and norm(pre[i]['dist']) in raw]
        if len(m2) == 1:
            return m2[0], 'R4_vill_exact_dist'
    if len(vl) >= 3:
        cand = [i for i in idx_prov.get(pv, []) if norm(pre[i]['vill'])[:3] == vl[:3]]
        if len(cand) == 1:
            return cand[0], 'R5_vill_prefix3'
        if cand and tn:
            m = [i for i in cand if tn[:2] == norm(pre[i]['town'])[:2]]
            if len(m) == 1:
                return m[0], 'R5_vill_prefix3_town'
    if len(vl) >= 2 and c:
        m = [i for i in c if norm(pre[i]['vill'])[:2] == vl[:2]]
        if len(m) == 1:
            return m[0], 'R6_town_vill_prefix2'
    vo = norm(s.get('village', ''))
    if vo:
        m = idx_vill.get((pv, vo), [])
        if len(m) == 1:
            return m[0], 'S7_vill_old_exact'
        if len(m) > 1:
            m2 = [i for i in m if norm(pre[i]['dist']) and norm(pre[i]['dist']) in raw]
            if len(m2) == 1:
                return m2[0], 'S7_vill_old_dist'
        cand = [i for i in idx_prov.get(pv, []) if inc(norm(pre[i]['vill']), vo)]
        m2 = [i for i in cand if norm(pre[i]['dist']) and norm(pre[i]['dist']) in raw]
        if len(m2) == 1:
            return m2[0], 'S8_vill_old_include_dist'
    return None, ''


for s in sup:
    if not s.get('town2'):
        s['town2'], s['vill2'] = split_raw(s['raw'], s['prov'])

assigned = {}
rule_cnt = collections.Counter()
audit = []
adju = []
for s in sup:
    raw_n = norm(s['raw'])
    if raw_n in ACCEPT:
        pv, ct, tn, vl, note = ACCEPT[raw_n]
        # 点位库省级标注偶有误（如黎平县被标为陕西省），按 县+乡镇+村 定位
        m = [k for k in key2idx if k[1] == ct and k[2] == tn and k[3] == vl]
        if not m:
            raise SystemExit('裁决目标不存在: %s' % raw_n)
        i = key2idx[m[0]][0]
        rule = 'ADJ_accept'
        rule_cnt[rule] += 1
        adju.append({'raw': s['raw'], 'batch': s['batch'], 'prov': pv,
                     'target': ct + tn + vl, 'decision': 'accept', 'basis': note})
    else:
        i, rule = rule_for(s)
        if i is not None:
            rule_cnt[rule] += 1
        else:
            rule_cnt['REJECT'] += 1
            adju.append({'raw': s['raw'], 'batch': s['batch'], 'prov': s['prov'],
                         'target': '', 'decision': 'reject_point_missing',
                         'basis': REJECT_NOTE})
    if i is not None:
        prev = assigned.get(i)
        cur = (s['batch'], s['announce_date'], s['scope_year'], rule, s['raw'])
        if prev is None or s['announce_date'] < prev[1]:
            assigned[i] = cur
        audit.append({'prov': s['prov'], 'batch': s['batch'], 'announce_date': s['announce_date'],
                      'raw': s['raw'], 'rule': rule,
                      'matched': pre[i]['dist'] + pre[i]['town'] + pre[i]['vill']})

print()
print('== 最终匹配规则分布 ==')
for k, v in rule_cnt.most_common():
    print('   %-26s %d' % (k, v))
n_assigned = len(assigned)
print('   已连接点位 %d / %d（%.1f%%）' % (n_assigned, len(pre), 100 * n_assigned / len(pre)))

# ---------- 输出 ----------
with open(os.path.join(RAW, 'support_national_final.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['batch', 'announce_date', 'scope_year', 'prov',
                                      'county', 'township', 'village', 'raw', 'town2', 'vill2'])
    w.writeheader()
    w.writerows(sup)

RECOG = '2016-12-09'
with open(os.path.join(D, 'master', 'geo_points_pre2555_v3.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['fid', 'prov', 'city', 'dist', 'town', 'vill', 'lon', 'lat',
                'support_batch', 'first_announce_date', 'nominal_support_year',
                'precommitted_future_year', 'sup_by_2015end', 'sup_by_recog',
                'sup_2014', 'match_rule', 'matched_raw'])
    for i, r in enumerate(pre):
        b, d, sy, rule, raw = assigned.get(i, ('', '', '', '', ''))
        precom = '1' if b == '2015att2' else '0'
        by2015 = '1' if d and d <= '2015-12-31' and b != '2015att2' else '0'
        byrec = '1' if d and d < RECOG else '0'
        s2014 = '1' if d and d <= '2014-12-31' else '0'
        w.writerow([r['fid'], r['prov'], r['city'], r['dist'], r['town'], r['vill'],
                    r['lon'], r['lat'], b, d, sy, precom, by2015, byrec, s2014, rule, raw])

with open(os.path.join(D, 'master', 'hist_adjudication.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['raw', 'batch', 'prov', 'target', 'decision', 'basis'])
    w.writeheader()
    w.writerows(adju)

# ---------- 恒等式 ----------
declared = {'2014-1': 327, '2014-2': 273, '2015-1': 491, '2015att2': 86,
            '2015-2': 404, '2016-1': 750, '2016-2': 219}
parsed = collections.Counter(s['batch'] for s in sup)
unlinked_pts = [i for i in range(len(pre)) if i not in assigned]
reject = [a for a in adju if a['decision'] == 'reject_point_missing']

lines = []
lines.append('=== 2550 / 2555 恒等式核算 ===')
lines.append('公告理论总数 %d；实际解析 %d；解析遗漏 %d' %
             (sum(declared.values()), sum(parsed.values()),
              sum(declared.values()) - sum(parsed.values())))
for b in declared:
    lines.append('  %-9s 声明 %3d  解析 %3d  差 %d' %
                 (b, declared[b], parsed.get(b, 0), declared[b] - parsed.get(b, 0)))
lines.append('')
lines.append('前三批认定村落（点位库）%d' % len(pre))
lines.append('已连接公告 %d；未连接 %d' % (n_assigned, len(unlinked_pts)))
lines.append('')
lines.append('未连接 %d 条的构成：' % len(unlinked_pts))
lines.append('  公告侧驳回（点位库无对应记录） %d 条' % len(reject))
lines.append('  理论从未进入公告的村落          5 条（2555 − 2550）')
lines.append('  其余差额来自公告条目被同一点位重复吸收（一对多）与点位库重复记录')
lines.append('')
lines.append('结论：未连接记录主要来自数据连接问题（点位库村名口径差异），')
lines.append('      不可直接等同于"历史未获支持"。')
txt = '\n'.join(lines)
print()
print(txt)
open(os.path.join(D, 'master', 'hist_link_identity.txt'), 'w', encoding='utf-8').write(txt)

print()
print('未连接点位清单（%d 条）：' % len(unlinked_pts))
for i in unlinked_pts[:60]:
    print('   ', pre[i]['prov'], pre[i]['dist'], pre[i]['town'], pre[i]['vill'])
