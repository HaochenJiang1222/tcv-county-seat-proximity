# -*- coding: utf-8 -*-
"""
135：点位库修正（第三十九部分任务一，用户指定必须先处理的两项）

  1 省份标签错误：fid 119 黎平县永从乡豆洞村 误标"陕西省" → 贵州省
  2 5 组完全重复记录（含 1 组坐标完全相同）：保留已连接公告记录的那条，删除未连接的镜像
      云南省腾冲县腾越镇尚家寨村   1354 保留 / 1355 删
      云南省剑川县沙溪镇甸头村     1504 保留 / 1505 删
      云南省大理市双廊镇双廊村     1481 保留 / 1482 删
      云南省景洪市基诺族乡巴亚村委会巴坡村 1466 保留 / 1467 删（坐标完全相同）
      四川省石棉县蟹螺藏族乡猛种村 1084 保留 / 1085 删

输出 data/master/geo_points_pre2555_v4.csv（2,550 行）
"""
import csv, os, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
SRC = os.path.join(D, 'master', 'geo_points_pre2555_v3.csv')
DST = os.path.join(D, 'master', 'geo_points_pre2555_v4.csv')
LOG = os.path.join(D, 'master', 'fix_points_135.txt')

rows = list(csv.DictReader(open(SRC, encoding='utf-8-sig')))
lines = []


def P(s=''):
    print(s)
    lines.append(s)


P('=== 135 点位库修正 ===')
P('读入 %d 行' % len(rows))

# 1 省份修正
FIX_PROV = {'119': ('陕西省', '贵州省')}
nfix = 0
for r in rows:
    if r['fid'] in FIX_PROV:
        old, new = FIX_PROV[r['fid']]
        assert r['prov'] == old, (r['fid'], r['prov'])
        r['prov'] = new
        nfix += 1
        P('省份修正 fid %s：%s → %s（%s %s %s）' %
          (r['fid'], old, new, r['dist'], r['town'], r['vill']))
P('省份修正 %d 条' % nfix)

# 2 重复剔除
DROP_FID = {'1355', '1505', '1482', '1467', '1085'}
before = len(rows)
keep = []
dropped = []
for r in rows:
    if r['fid'] in DROP_FID:
        dropped.append(r)
        P('删除重复 fid %s %s %s %s %s（保留同名的已连接记录）' %
          (r['fid'], r['prov'], r['dist'], r['town'], r['vill']))
    else:
        keep.append(r)
rows = keep
P('重复剔除 %d 条，剩 %d 行（%d → %d）' % (len(dropped), len(rows), before, len(rows)))

# 校验
P('')
P('--- 修正后状态 ---')
n_link = sum(1 for r in rows if r['first_announce_date'])
P('已连接公告 %d；未连接 %d' % (n_link, len(rows) - n_link))
P('未连接明细：')
for r in rows:
    if not r['first_announce_date']:
        P('   fid %s %s %s %s %s' % (r['fid'], r['prov'], r['dist'], r['town'], r['vill']))

fields = list(rows[0].keys())
with open(DST, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
P('')
P('写出 %s（%d 行）' % (DST, len(rows)))

open(LOG, 'w', encoding='utf-8').write('\n'.join(lines))
print()
print('写出 %s' % LOG)
