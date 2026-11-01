# -*- coding: utf-8 -*-
"""
134b：孤儿公告记录的真实归属探测（第三十九部分任务一）

134 发现：14 条公告侧孤儿与 20 条点位侧未匹配几乎不对应，但多组落在同一乡镇。
假设：公告名单用自然村/村民小组名（"四联村委会段家登村"、"丰禾村北汤天村"），
认定名单用行政村名，同一乡镇内出现"邻村式"错配。

本脚本对每条孤儿，在全部 2,555 个点位中检索：
  A 同省 + 同县（dist 名包含）+ 村名互相包含 / 首两字相同
  B 同省 + 同乡镇（town）的任意村名相似
并报告该点位当前是否已连接公告记录、其批次与日期。
若孤儿匹配到"已连接"的点位，说明存在重复占用或跨批同名，需人工裁决；
若匹配到"未连接"的点位，即为应补配对。
"""
import csv, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
FIN = os.path.join(D, 'tcv_funding', 'official_pre', 'support_national_final.csv')
PTS = os.path.join(D, 'master', 'geo_points_pre2555_v3.csv')
OUT = os.path.join(D, 'master', 'orphan_probe_134b.txt')

fin = list(csv.DictReader(open(FIN, encoding='utf-8-sig')))
pts = list(csv.DictReader(open(PTS, encoding='utf-8-sig')))
lines = []


def P(s=''):
    print(s)
    lines.append(s)


used_raw = set(r['matched_raw'] for r in pts if r.get('matched_raw'))
orphan = [r for r in fin if r['raw'] not in used_raw]

SUF = re.compile(r'(村|寨|屯|堡|沟|湾|坪|坡|行政村|村委会|社区|居民委员会|老寨|新寨)$')


def norm(s):
    s = (s or '').strip()
    s = re.sub(r'[（）()\s·・\-—]', '', s)
    s = re.sub(r'^.*?委会', '', s)
    for _ in range(3):
        s2 = SUF.sub('', s)
        if s2 == s or len(s2) < 2:
            break
        s = s2
    return s


def provkey(p):
    return re.sub(r'(省|市|自治区|壮族|回族|维吾尔|特别行政区|州)', '', (p or ''))


P('=== 134b 孤儿归属探测 ===')
P('孤儿 %d 条' % len(orphan))
P('')
for o in orphan:
    on = norm(o['village'])
    op = provkey(o['prov'])
    oc = (o['county'] or '').replace('区', '').replace('县', '').replace('市', '')
    ot = (o['township'] or '')
    cands = []
    for pt in pts:
        if provkey(pt['prov']) != op:
            continue
        vn = norm(pt['vill'])
        if not vn:
            continue
        score = 0
        if on == vn:
            score = 5
        elif on and vn and (on in vn or vn in on):
            score = 4
        elif len(on) >= 2 and len(vn) >= 2 and on[:2] == vn[:2]:
            score = 3
        else:
            continue
        # 同县加分
        pc = (pt['dist'] or '').replace('区', '').replace('县', '').replace('市', '')
        if oc and pc and (oc in pc or pc in oc):
            score += 1
        if ot and pt['town'] and (ot[:2] == pt['town'][:2]):
            score += 1
        cands.append((score, pt))
    cands.sort(key=lambda x: -x[0])
    P('--- 孤儿 [%s %s] %s | %s | %s' % (o['batch'], o['announce_date'], o['prov'],
                                         o['county'], o['village']))
    if not cands:
        P('      （全表无同省候选）')
    for sc, pt in cands[:4]:
        state = ('已连接 %s %s' % (pt['support_batch'], pt['first_announce_date'])) if \
            pt['first_announce_date'] else '未连接'
        P('      score %d | fid %s %s %s %s | %s' %
          (sc, pt['fid'], pt['dist'], pt['town'], pt['vill'], state))
    P('')

open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
print('写出 %s' % OUT)
