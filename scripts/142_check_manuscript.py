# -*- coding: utf-8 -*-
"""
142：Manuscript 内容检查（v1.2 起，排版前必跑）

不是查字体与页边距，而是查七项内容标准：
  1 文献编号 [1]-[14] 按正文首次引用顺序连续出现
  2 政策文件 [11][12][13] 使用已核实的政府网站直达链接
  3 Figure 1-2 与 Table 1-4 在正文均有引用
  4 数值保真：主系数与冻结结果一致（并从结果文件交叉验证）
  5 单位核查：县等权 -1.92 单位为 km；进入率差 -0.039 不得与 km 连写
  6 摘要 <= 200 词且保留县等权限制
  7 声明齐全：Author Contributions / Funding / Data Availability / Conflicts / AI 声明

用法：python dofile/142_check_manuscript.py [md路径]
输出：data/master/manuscript_check.txt（控制台同步打印）
"""
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_arg = sys.argv[1] if len(sys.argv) > 1 else None
if _arg is None:
    MD = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_v1.2.md')
elif os.sep in _arg or _arg.endswith('.md'):
    MD = _arg
else:
    MD = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s.md' % _arg)
t = open(MD, encoding='utf-8').read()

body = t.split('## References')[0]
refs = t.split('## References')[1] if '## References' in t else ''

# 正文使用 Unicode 减号 U+2212，检查时统一归一化为 ASCII 连字符
t_norm = t.replace('\u2212', '-')
body_norm = body.replace('\u2212', '-')

out = []
fails = []


def chk(ok, name, detail=''):
    out.append('%-4s %-28s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        fails.append(name)


# ---- 1 文献编号顺序 ----
NREF = 18   # v1.4 起：15-18 为三条行政建制调整批复与红安县官方页面
order = []
seen = set()
for m in re.finditer(r'\[([0-9][0-9,\u2013\-]*)\]', body):
    for p in re.split(r'[,\u2013\-]', m.group(1)):
        p = p.strip()
        if p.isdigit() and p not in seen and int(p) <= NREF:
            seen.add(p)
            order.append(int(p))
chk(order == list(range(1, NREF + 1)), '文献编号顺序',
    '首次出现次序 %s' % order)
nref = len(re.findall(r'^\d+\. ', refs, re.M))
chk(nref == NREF, '参考文献条目数', '%d 条' % nref)

# ---- 2 政策文件链接 ----
links = {
    11: 'zjt.ln.gov.cn/zjt/tftz/21ADD09A01BA42A88E12EADEF7CF9F95/index.shtml',
    12: 'jsj.yueyang.gov.cn/54027/54028/54036/content_1393357.html',
    13: 'jjs.mof.gov.cn/zxzyzf/gkjs_8456/201801/t20180104_2792684.htm',
}
for k, u in links.items():
    seg = refs.split('\n%d. ' % k)[1].split('\n%d. ' % (k + 1))[0] if '\n%d. ' % k in refs else ''
    chk(u in seg, '文献[%d]直达链接' % k, u[:46] + '...')
chk('mohurd.gov.cn' not in refs, '已清除 mohurd 首页占位')
chk('to be verified' not in refs and 'to be inserted' not in refs,
    '已清除待核占位标注')
chk('Cai Jian [2017] No. 318' in refs, '财政文号 318 入文献')
chk('Cai Jian [2017] No. 318' in body, '财政文号 318 入正文')

# ---- 3 图表引用 ----
for k in ['Figure 1', 'Figure 2', 'Table 1', 'Table 2', 'Table 3', 'Table 4']:
    # 只统计正文引用（不含图表的题注行）
    cites = [ln for ln in body.split('\n')
             if k in ln and not ln.strip().startswith(('**%s.' % k, '### %s.' % k, '![%s' % k))]
    chk(len(cites) >= 1, '%s 正文引用' % k, '%d 处' % len(cites))

# ---- 4 数值保真（并与结果文件交叉验证）----
FROZEN = {
    '主系数 A': ('-0.370', '[−0.838, −0.067]', '0.025'),
    '剔坐标 A': ('-0.452', '[−0.971, −0.122]', '0.010'),
    '县界检验 A': ('-0.435', '[−0.947, −0.083]', '0.025'),
    'LPM 全样本': ('-0.034', '[−0.073, 0.002]', '0.060'),
    'LPM 有效组': ('-0.088', '[−0.180, −0.008]', '0.036'),
    '过程B 全国': ('0.312', '[−0.173, 0.856]', '0.175'),
}
FROZEN = {k: tuple(v.replace('\u2212', '-') for v in vals)
          for k, vals in FROZEN.items()}
for k, (b, ci, p) in FROZEN.items():
    ok = (b in t_norm) and (ci in t_norm) and (p in t_norm)
    chk(ok, '数值 %s' % k, '%s %s p=%s' % (b, ci, p))

# 从结果文件交叉验证主系数
rv = os.path.join(ROOT, 'data', 'master', 'national_results_v3.txt')
if os.path.exists(rv):
    rt = open(rv, encoding='utf-8').read()
    m = re.search(r'A 基准\(距离\+地形\).*?dist 到县城\(log1p km\)\s+(-?\d+\.\d+)', rt, re.S)
    if m:
        chk(m.group(1) == '-0.370', '主系数与结果文件一致', '结果文件 %s' % m.group(1))
ch = os.path.join(ROOT, 'data', 'master', 'checks_139.txt')
if os.path.exists(ch):
    ct = open(ch, encoding='utf-8').read()
    for tag, val in [('全样本', '-0.034'), ('有效组', '-0.088')]:
        seg = ct.split('--- %s' % tag)[1][:400] if '--- %s' % tag in ct else ''
        chk(val in seg, 'LPM %s 与139一致' % tag, val)

# ---- 5 单位核查 ----
ok192 = bool(re.search(r'-1\.92\s*km', t_norm)) and not re.search(r'-1\.92\s*percentage', t_norm)
chk(ok192, '县等权 -1.92 单位为 km')
ok039 = bool(re.search(r'-0\.039', t_norm)) and not re.search(r'-0\.039\s*km', t_norm)
chk(ok039, '进入率差 -0.039 不与 km 连写')
ok683 = '0.683' in t and '31.7%' in t and 'odds' in body.lower()
chk(ok683, '优势比换算表述', 'OR 0.683 / 31.7% / odds')

# ---- 6 摘要 ----
m = re.search(r'## Abstract\n\n(.*?)\n\n\*\*Keywords', t, re.S)
ab = m.group(1) if m else ''
w = len(ab.split())
chk(w <= 200, '摘要 <= 200 词', '%d 词' % w)
chk('equal-county' in ab or 'equal-county-weighted' in ab, '摘要保留县等权限制')

# ---- 7 声明 ----
for k in ['Author Contributions', 'Funding', 'Data Availability Statement',
          'Conflicts of Interest', 'Declaration of Generative AI']:
    chk(k in t, '声明：%s' % k)
chk('2024SJYB0562' in t, '资助号 2024SJYB0562')

# ---- 另：政策时间线使用文件日期 ----
chk('9 December 2016' in body and '9 May 2017' in body, '正文使用文件日期')

txt = '=== Manuscript 内容检查：%s ===\n\n' % os.path.basename(MD) + '\n'.join(out)
txt += '\n\n通过 %d / %d' % (len(out) - len(fails), len(out))
txt += '\n结论：%s' % ('全部通过，可进入排版' if not fails
                       else '未通过项：' + '；'.join(fails))
print(txt)
p = os.path.join(ROOT, 'data', 'master', 'manuscript_check.txt')
open(p, 'w', encoding='utf-8').write(txt)
print('\n写出', p)
