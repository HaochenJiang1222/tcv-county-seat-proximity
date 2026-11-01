# -*- coding: utf-8 -*-
"""
134：分组计数对账与缺口配对（第三十九部分任务一）

用户指出：early 1,085 / late 1,384 / precom 86 与按公告日期推算的
1,091 / 1,373 / 86 / 5（上海）存在系统性差异（early 少 6、late 多 11）。
本脚本只做诊断与配对，不改数据。

步骤
  1 公告侧按批次对账：final 各批计数 vs 理论值（327/273/491/404/86/750/219）
  2 点位侧按首次公告对账，给出逐批缺口
  3 双向配对：公告侧未被任何点位占用的记录（孤儿） × 点位侧无公告日期的村（20 条）
     配对规则：同省 + 村名标准化后互相包含（或去掉"村/寨/屯/堡"后缀后相等）
  4 输出配对表供人工裁决
"""
import csv, os, sys, re, collections
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
FIN = os.path.join(D, 'tcv_funding', 'official_pre', 'support_national_final.csv')
PTS = os.path.join(D, 'master', 'geo_points_pre2555_v3.csv')
OUT = os.path.join(D, 'master', 'reconcile_134.txt')
OUTCSV = os.path.join(D, 'master', 'reconcile_pairs_134.csv')

THEORY = {'2014-1': 327, '2014-2': 273, '2015-1': 491, '2015-2': 404,
          '2015att2': 86, '2016-1': 750, '2016-2': 219}

fin = list(csv.DictReader(open(FIN, encoding='utf-8-sig')))
pts = list(csv.DictReader(open(PTS, encoding='utf-8-sig')))
lines = []


def P(s=''):
    print(s)
    lines.append(s)


P('=== 134 分组计数对账 ===')
P('')
P('--- 1 公告侧批次对账 ---')
cnt = collections.Counter(r['batch'] for r in fin)
tot_t = 0
for b in ['2014-1', '2014-2', '2015-1', '2015-2', '2015att2', '2016-1', '2016-2']:
    t = THEORY[b]
    tot_t += t
    P('   %-9s 公告侧 %4d  理论 %4d  差 %+d' % (b, cnt[b], t, cnt[b] - t))
P('   合计      公告侧 %4d  理论 %4d  差 %+d' % (len(fin), tot_t, len(fin) - tot_t))
P('   注：差值来自公告原文解析遗漏；理论值由各批次名额独立给出')

P('')
P('--- 2 点位侧首次公告对账 ---')
used_raw = set(r['matched_raw'] for r in pts if r.get('matched_raw'))
P('   点位侧已占用公告记录 %d / %d' % (len(used_raw), len(fin)))
date_cnt = collections.Counter(r['first_announce_date'] for r in pts if r['first_announce_date'])
P('   点位侧按首次公告日：')
for d in sorted(date_cnt):
    P('      %s  %d' % (d, date_cnt[d]))
P('   无公告日（未连接）%d 条' % sum(1 for r in pts if not r['first_announce_date']))

# 公告侧孤儿
orphan = [r for r in fin if r['raw'] not in used_raw]
P('')
P('--- 3 公告侧孤儿记录 %d 条（未被任何点位占用）---' % len(orphan))
oc = collections.Counter(r['batch'] for r in orphan)
for b in sorted(oc):
    P('      %-9s %d' % (b, oc[b]))
P('')
for r in orphan:
    P('   [%s] %s | %s | %s | %s' % (r['batch'], r['prov'], r['county'], r['village'], r['raw']))

# 点位侧未匹配
noann = [r for r in pts if not r['first_announce_date']]
P('')
P('--- 4 点位侧无公告记录 %d 条 ---' % len(noann))
for r in noann:
    P('   fid %s | %s %s %s %s %s' % (r['fid'], r['prov'], r['city'], r['dist'],
                                      r['town'], r['vill']))

# 标准化
SUF = re.compile(r'(村|寨|屯|堡|沟|湾|坪|坡|行政村|村委会|社区|居民委员会)$')


def norm(s):
    s = (s or '').strip()
    s = re.sub(r'[（）()\s·・]', '', s)
    s = re.sub(r'^.*?委会', '', s)
    for _ in range(3):
        s2 = SUF.sub('', s)
        if s2 == s or len(s2) < 2:
            break
        s = s2
    return s


def provkey(p):
    return re.sub(r'(省|市|自治区|壮族|回族|维吾尔|特别行政区)', '', (p or ''))


pairs = []
for o in orphan:
    on = norm(o['village'])
    op = provkey(o['prov'])
    best = []
    for pt in noann:
        vn = norm(pt['vill'])
        if provkey(pt['prov']) != op:
            continue
        if not on or not vn:
            continue
        if on == vn:
            sc = 3
        elif on in vn or vn in on:
            sc = 2
        elif on[:2] == vn[:2] and min(len(on), len(vn)) >= 2:
            sc = 1
        else:
            continue
        best.append((sc, pt, vn))
    best.sort(key=lambda x: -x[0])
    pairs.append((o, best))

P('')
P('--- 5 孤儿 × 未匹配点位 候选配对（同省 + 村名包含）---')
rows = []
for o, best in pairs:
    if best:
        for sc, pt, vn in best[:3]:
            P('   %-9s %-14s <=> fid %-5s %s %s %s  score %d' %
              (o['batch'], o['village'], pt['fid'], pt['dist'], pt['town'], pt['vill'], sc))
            rows.append({'batch': o['batch'], 'announce_date': o['announce_date'],
                         'ann_prov': o['prov'], 'ann_county': o['county'],
                         'ann_village': o['village'], 'ann_raw': o['raw'],
                         'fid': pt['fid'], 'pt_prov': pt['prov'], 'pt_dist': pt['dist'],
                         'pt_town': pt['town'], 'pt_vill': pt['vill'], 'score': sc})
    else:
        P('   %-9s %-14s <=> （无同省候选）' % (o['batch'], o['village']))
        rows.append({'batch': o['batch'], 'announce_date': o['announce_date'],
                     'ann_prov': o['prov'], 'ann_county': o['county'],
                     'ann_village': o['village'], 'ann_raw': o['raw'],
                     'fid': '', 'pt_prov': '', 'pt_dist': '', 'pt_town': '',
                     'pt_vill': '', 'score': 0})

with open(OUTCSV, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

P('')
P('--- 6 差额核算 ---')
n_early = sum(1 for r in pts if r['first_announce_date'] and r['first_announce_date'] <= '2015-12-31'
              and r['precommitted_future_year'] != '1')
n_late = sum(1 for r in pts if r['precommitted_future_year'] != '1' and
             (not r['first_announce_date'] or r['first_announce_date'] > '2015-12-31'))
n_pre = sum(1 for r in pts if r['precommitted_future_year'] == '1')
P('   实际 early %d / late %d / precom %d' % (n_early, n_late, n_pre))
P('   理论 early %d / late %d / precom %d / 未入公告 %d' %
  (1091, 1373, 86, 5))
P('   early 差 %+d；late 差 %+d' % (n_early - 1091, n_late - 1373))
P('   late 多出的 %d 条 = 上海 5 村（从未入公告）+ %d 条公告侧有记录但点位未连接' %
  (n_late - 1373, n_late - 1373 - 5))
P('   其中可经由孤儿配对找回 %d 条' % sum(1 for r in rows if r['score'] > 0 and r['fid']))

open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
print()
print('写出 %s' % OUT)
print('写出 %s' % OUTCSV)
