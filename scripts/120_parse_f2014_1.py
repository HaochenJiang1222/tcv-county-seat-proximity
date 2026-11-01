# -*- coding: utf-8 -*-
"""解析 2014 年第一批列入中央财政支持范围的中国传统村落名单（官方 .doc，327 村）

来源 安徽省住建厅转载的建村文件附件（与住建部公告同一名单）
用途 全国口径"既有财政支持经验"变量的历史名单基础；并交叉核对本地三省名单完整性
"""
import olefile, re, sys, csv, collections

sys.stdout.reconfigure(encoding='utf-8')
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
SRC = 'data/tcv_funding/official_pre/f2014_1.doc'
OUT = 'data/tcv_funding/official_pre/support_2014_1.csv'

PROV = ('北京市|天津市|河北省|山西省|内蒙古自治区|辽宁省|吉林省|黑龙江省|上海市|江苏省|浙江省|安徽省|'
        '福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|广西壮族自治区|海南省|重庆市|四川省|贵州省|云南省|'
        '西藏自治区|陕西省|甘肃省|青海省|宁夏回族自治区|新疆维吾尔自治区')
HEAD = re.compile(r'^[一二三四五六七八九十百]+[、.]\s*(' + PROV + r')\s*[（(]\s*(\d+)\s*个\s*[）)]')
VILL = re.compile(r'村|寨|屯|堡|组|社区|庄|湾|沟|巷|厝|围|楼|屋|民居|古村')

o = olefile.OleFileIO(SRC)
txt = o.openstream('WordDocument').read().decode('utf-16-le', errors='ignore')
paras = [p.strip() for p in re.split(r'[\r\n]+', txt) if p.strip()]
paras = [p for p in paras if len(p) >= 2 and not re.match(r'^[\x00-\x1f\s]*$', p)]
heads = [(i, m.group(1), int(m.group(2))) for i, p in enumerate(paras) for m in [HEAD.match(p)] if m]
print('省份标题 %d；声明合计 %d' % (len(heads), sum(h[2] for h in heads)))

rows, mismatch = [], []
for j, (i, pv, exp_n) in enumerate(heads):
    end = heads[j + 1][0] if j + 1 < len(heads) else len(paras)
    seg = paras[i + 1:end]
    cand = []
    for x in seg:
        if len(x) < 4 or len(x) > 40:
            continue
        if HEAD.match(x):
            continue
        if not VILL.search(x):
            continue
        cand.append(x)
    if len(cand) != exp_n:
        mismatch.append((pv, exp_n, len(cand), seg[:6]))
    for x in cand:
        rows.append({'year': 2014, 'batch': '2014-1', 'prov': pv, 'village': x})

print('解析村数 %d（官方 327）' % len(rows))
for pv, e, g, seg in mismatch:
    print('   ⚠ %s 声明 %d 解析 %d；该段前几行 %s' % (pv, e, g, seg))

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['year', 'batch', 'prov', 'village'])
    w.writeheader()
    w.writerows(rows)
print('写出 %s' % OUT)

# 与本地三省名单交叉核对
T3 = {'浙江省', '安徽省', '江苏省'}
print()
print('== 与本地三省 2014-1 名单交叉核对 ==')
loc = [r for r in csv.DictReader(open('data/tcv_funding/funding_master.csv', encoding='utf-8-sig'))
       if r['batch'] == '2014-1' and r['year'] == '2014']
locn = {(r['prov'] if r['prov'].endswith('省') else r['prov'] + '省'): 0 for r in loc}
loc_set = set()
for r in loc:
    p = r['prov'] if r['prov'].endswith('省') else r['prov'] + '省'
    loc_set.add((p, r['village'].strip()))
off = {(r['prov'], r['village']) for r in rows if r['prov'] in T3}
print('官方 2014-1 三省：%d；本地记录：%d' % (len(off), len(loc_set)))
def norm(s):
    return re.sub(r'[\s·、（）()]', '', s)
offn = {(p, norm(v)) for p, v in off}
locn2 = {(p, norm(v)) for p, v in loc_set}
only_off = sorted(offn - locn2)
only_loc = sorted(locn2 - offn)
print('官方有、本地无：%d' % len(only_off))
for x in only_off[:10]:
    print('   ', x[0], x[1])
print('本地有、官方无：%d' % len(only_loc))
for x in only_loc[:10]:
    print('   ', x[0], x[1])
