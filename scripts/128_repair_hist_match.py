# -*- coding: utf-8 -*-
"""
128：历史支持名单 2,550 对 2,555 全量连接（第三十八部分任务一）

问题：122 用解析出的 county 字段匹配，而 121 的 split_addr 把"平山县杨家桥"
     "丰""内"之类的碎片当县名，导致 137 条名单条目匹配失败。

修正：放弃 county 字段，直接从 raw 完整地址提取乡镇与村名：
      raw = "石家庄市平山县杨家桥乡大坪村"
      ->  township = "杨家桥乡"   village = "大坪村"
     乡镇名禁止包含 市/县/区/旗/州，避免"丰镇市""临翔区"被误判为乡镇。

输出
  data/tcv_funding/official_pre/support_national_revised.csv  名单 + 重解析字段
  data/master/geo_points_pre2555_v2.csv                       前三批点位 + 支持状态
  data/master/hist_match_audit.csv                            逐条匹配台账
  data/master/hist_unmatched_queue.csv                        仍待核验队列
"""
import csv, sys, os, re, unicodedata, collections

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')


def norm(s):
    return re.sub(r'[\s·、，,（）()]', '', unicodedata.normalize('NFKC', s or ''))


TOWN_RE = re.compile(r'([^市县区旗州盟]{2,12}?)(苏木|管理区|办事处|街道|镇|乡)')


def split_raw(raw, prov):
    """从完整地址提取 (乡镇, 村名)；失败返回 ('', raw)"""
    s = norm(raw)
    for p in ('内蒙古自治区', '广西壮族自治区', '宁夏回族自治区', '新疆维吾尔自治区',
              '西藏自治区', '北京市', '天津市', '上海市', '重庆市'):
        if s.startswith(p):
            s = s[len(p):]
            break
    m = None
    for mm in TOWN_RE.finditer(s):
        if mm.start() >= 1:
            m = mm
            break
    if not m:
        return '', s
    town = m.group(0)
    vill = s[m.end():]
    return town, vill


# ---------- 读入 ----------
sup = list(csv.DictReader(open(os.path.join(D, 'tcv_funding', 'official_pre',
                                            'support_national_all.csv'), encoding='utf-8-sig')))
pre = list(csv.DictReader(open(os.path.join(D, 'geo', 'geodoi', 'points2555.csv'),
                               encoding='utf-8-sig')))
print('名单条目 %d，前三批点位 %d' % (len(sup), len(pre)))

for s in sup:
    s['town2'], s['vill2'] = split_raw(s['raw'], s['prov'])

# 索引
idx_prov = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_prov[r['prov']].append(i)
idx_town = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_town[(r['prov'], norm(r['town']))].append(i)
idx_vill = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_vill[(r['prov'], norm(r['vill']))].append(i)


def inc(a, b):
    return bool(a) and bool(b) and (a in b or b in a)


# full = 县+乡镇+村 的完整串；名单 raw 通常以其结尾
idx_full = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_full[norm(r['dist'] + r['town'] + r['vill'])].append(i)
# 也建 dist+town 与 town+vill
idx_tv = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_tv[(r['prov'], norm(r['town'] + r['vill']))].append(i)


def suffix_hit(rn):
    """raw 的所有后缀中，能命中 pre 完整串的最长者"""
    for L in range(len(rn), 3, -1):
        m = idx_full.get(rn[-L:])
        if m:
            return m
    return None


def rule_for(s):
    """返回 (点位下标, 规则) 或 (None, '')"""
    pv, tn, vl, raw = s['prov'], norm(s['town2']), norm(s['vill2']), norm(s['raw'])
    # S0 raw 后缀命中 县+乡镇+村 完整串
    m = suffix_hit(raw)
    if m:
        return (m[0], 'S0_raw_suffix' + ('_multi' if len(m) > 1 else ''))
    # S0b 省 + 乡镇+村
    m = idx_tv.get((pv, tn + vl), [])
    if len(m) >= 1:
        return (m[0], 'S0b_town_vill' + ('_multi' if len(m) > 1 else ''))
    # R1 省 + 乡镇精确 + 村名精确
    c = idx_town.get((pv, tn), [])
    m = [i for i in c if norm(pre[i]['vill']) == vl]
    if len(m) >= 1:
        return (m[0], 'R1_town_vill_exact' + ('_multi' if len(m) > 1 else ''))
    # R2 省 + 乡镇精确 + 村名互含
    m = [i for i in c if inc(norm(pre[i]['vill']), vl)]
    if len(m) == 1:
        return (m[0], 'R2_town_vill_include')
    # R3 省 + 乡镇互含 + 村名互含
    cand = [i for i in idx_prov.get(pv, []) if inc(norm(pre[i]['town']), tn)]
    m = [i for i in cand if inc(norm(pre[i]['vill']), vl)]
    if len(m) == 1:
        return (m[0], 'R3_town_vill_fuzzy')
    # R4 省 + 村名精确
    m = idx_vill.get((pv, vl), [])
    if len(m) == 1:
        return (m[0], 'R4_vill_exact')
    if len(m) > 1:
        # 用 raw 是否含 dist 来定
        m2 = [i for i in m if norm(pre[i]['dist']) and norm(pre[i]['dist']) in raw]
        if len(m2) == 1:
            return (m2[0], 'R4_vill_exact_dist')
    # R5 省 + 村名前 3 字 + 乡镇前 2 字
    if len(vl) >= 3:
        cand = [i for i in idx_prov.get(pv, []) if norm(pre[i]['vill'])[:3] == vl[:3]]
        if len(cand) == 1:
            return (cand[0], 'R5_vill_prefix3')
        if len(cand) > 1 and tn:
            m = [i for i in cand if tn[:2] == norm(pre[i]['town'])[:2]]
            if len(m) == 1:
                return (m[0], 'R5_vill_prefix3_town')
    # R6 省 + 乡镇精确 + 村名前 2 字
    if len(vl) >= 2 and c:
        m = [i for i in c if norm(pre[i]['vill'])[:2] == vl[:2]]
        if len(m) == 1:
            return (m[0], 'R6_town_vill_prefix2')
    # S7 原 village 字段 + raw 含 dist（原 county 字段不可靠，改用 dist 定位）
    vo = norm(s.get('village', ''))
    if vo:
        m = idx_vill.get((pv, vo), [])
        if len(m) == 1:
            return (m[0], 'S7_vill_old_exact')
        if len(m) > 1:
            m2 = [i for i in m if norm(pre[i]['dist']) and norm(pre[i]['dist']) in raw]
            if len(m2) == 1:
                return (m2[0], 'S7_vill_old_dist')
        # S8 原 village 与点位村名互含 + raw 含 dist
        cand = [i for i in idx_prov.get(pv, []) if inc(norm(pre[i]['vill']), vo)]
        m2 = [i for i in cand if norm(pre[i]['dist']) and norm(pre[i]['dist']) in raw]
        if len(m2) == 1:
            return (m2[0], 'S8_vill_old_include_dist')
        if len(m2) == 0 and len(cand) == 1:
            return (cand[0], 'S8_vill_old_include')
    return (None, '')


assigned = {}      # 点位下标 -> (batch, announce_date, scope_year, rule)
audit = []
queue = []
rule_cnt = collections.Counter()
for s in sup:
    i, rule = rule_for(s)
    if i is not None:
        rule_cnt[rule] += 1
        prev = assigned.get(i)
        cur = (s['batch'], s['announce_date'], s['scope_year'], rule, s['raw'])
        if prev is None or s['announce_date'] < prev[1]:
            assigned[i] = cur
        audit.append({'prov': s['prov'], 'batch': s['batch'], 'announce_date': s['announce_date'],
                      'raw': s['raw'], 'town2': s['town2'], 'vill2': s['vill2'],
                      'matched_pre': pre[i]['dist'] + pre[i]['town'] + pre[i]['vill'],
                      'rule': rule})
    else:
        rule_cnt['MISS'] += 1
        queue.append({'prov': s['prov'], 'batch': s['batch'], 'announce_date': s['announce_date'],
                      'raw': s['raw'], 'town2': s['town2'], 'vill2': s['vill2'],
                      'county_old': s['county'], 'village_old': s['village']})

print()
print('== 修复后匹配 ==')
for k, v in rule_cnt.most_common():
    print('   %-28s %d' % (k, v))
n_assigned = len(assigned)
print('   已赋支持状态点位 %d / %d（%.1f%%）' % (n_assigned, len(pre), 100 * n_assigned / len(pre)))
print('   仍待核验名单条目 %d' % len(queue))
print('   名单条目被点位吸收（去重后）%d' % sum(1 for _ in audit))

# ---------- 恒等式核算 ----------
print()
print('== 2550 / 2555 恒等式核算 ==')
declared = {'2014-1': 327, '2014-2': 273, '2015-1': 491, '2015att2': 86,
            '2015-2': 404, '2016-1': 750, '2016-2': 219}
parsed = collections.Counter(s['batch'] for s in sup)
tot_d = sum(declared.values())
tot_p = sum(parsed.values())
print('   公告理论总数 %d；已解析 %d；解析遗漏 %d' % (tot_d, tot_p, tot_d - tot_p))
for b in declared:
    print('      %-9s 声明 %3d  解析 %3d  差 %d' % (b, declared[b], parsed.get(b, 0),
                                                    declared[b] - parsed.get(b, 0)))
n_unmatched_points = len(pre) - n_assigned
print('   前三批认定村落 %d；已连接 %d；未连接 %d' % (len(pre), n_assigned, n_unmatched_points))
print('   未连接 = 未匹配名单条目(去重前) %d 中真正无归属者 + 解析遗漏 %d + 理论未入选 5'
      % (len(queue), tot_d - tot_p))

# ---------- 输出 ----------
with open(os.path.join(D, 'tcv_funding', 'official_pre', 'support_national_revised.csv'),
          'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(sup[0].keys()) + ['town2', 'vill2'])
    w.writeheader()
    w.writerows(sup)

with open(os.path.join(D, 'master', 'geo_points_pre2555_v2.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['fid', 'prov', 'city', 'dist', 'town', 'vill', 'lon', 'lat',
                'support_batch', 'first_announce_date', 'nominal_support_year',
                'precommitted_future_year', 'match_rule', 'matched_raw'])
    for i, r in enumerate(pre):
        b, d, sy, rule, raw = assigned.get(i, ('', '', '', '', ''))
        precom = '1' if b == '2015att2' else ''
        w.writerow([r['fid'], r['prov'], r['city'], r['dist'], r['town'], r['vill'],
                    r['lon'], r['lat'], b, d, sy, precom, rule, raw])

with open(os.path.join(D, 'master', 'hist_match_audit.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(audit[0].keys()))
    w.writeheader()
    w.writerows(audit)

if queue:
    with open(os.path.join(D, 'master', 'hist_unmatched_queue.csv'), 'w', newline='',
              encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(queue[0].keys()))
        w.writeheader()
        w.writerows(queue)

print()
print('待核验队列样例（前 25）:')
for q in queue[:25]:
    print('   ', q['prov'], q['batch'], '| raw=', q['raw'][:38], '| town2=', q['town2'],
          '| vill2=', q['vill2'][:20])
