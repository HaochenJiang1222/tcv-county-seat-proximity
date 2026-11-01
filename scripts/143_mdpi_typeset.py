# -*- coding: utf-8 -*-
"""
143：Manuscript v1.2 → MDPI 投稿排版稿（基于 land_template.docx）

流程
  1 预处理：标题页转 build_mdpi 期望格式（**Authors:** / ¹ ² / * Correspondence:）
            表标题 h3 → **Table N.**（tcap）；Notes → *Notes:*（表注样式）
            删除版本标注行与 Tables / Figures 分组标题
            back matter 二级标题 → 加粗声明标题
  2 调 build_mdpi.build() 生成 docx（MDPI 段落样式、三线表、图注）
  3 排版后自检：段落数、表格数、图片数、参考文献条目数

用法：python dofile/143_mdpi_typeset.py
"""
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_mdpi
from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.argv[1] if len(sys.argv) > 1 else 'v1.2'
# 第三参数为输出文件名的附加后缀。成品 docx 被 WPS/Word 预览占用时无法覆盖写入，
# 用后缀另存新文件，避免改动版本号（版本号与实证内容绑定，不得随交付顺序变化）。
SUF = sys.argv[2] if len(sys.argv) > 2 else ''
SRC = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s.md' % VER)
MID = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s%s_mdpi.md' % (VER, SUF))
DST = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s%s_MDPI.docx' % (VER, SUF))

t = open(SRC, encoding='utf-8').read()

# ---- 1 标题页 ----
t = re.sub(r'^\*\*Manuscript %s[^\n]*\*\*\n' % re.escape(VER), '', t, flags=re.M)
t = t.replace('Yue Yu ^1^, Haochen Jiang ^2,^\\*^',
              '**Authors:** Yue Yu¹, Haochen Jiang²,*')
t = t.replace('^1^ College of Humanities and Education',
              '¹ College of Humanities and Education')
t = t.replace('^2^ College of Rural Revitalization',
              '² College of Rural Revitalization')
t = re.sub(r'^\^\*\^\s*Correspondence:', '* Correspondence:', t, flags=re.M)

# ---- 2 表标题与表注 ----
t = re.sub(r'^### Table (\d+)\.\s*(.+)$', r'**Table \1.** \2', t, flags=re.M)
t = re.sub(r'^Notes:\s*', '*Notes:* ', t, flags=re.M)

# ---- 3 删除分组标题 ----
t = re.sub(r'^## (Tables|Figures)\n', '', t, flags=re.M)

# ---- 3b 行内代码反引号：md 里的 `center` 在 Word 中会原样显示反引号 ----
_n_tick = t.count('`')
t = t.replace('`', '')
print('反引号清洗：%d 处' % _n_tick)

# ---- 4 back matter 标题 ----
BM = ['Author Contributions', 'Funding', 'Data Availability Statement',
      'Acknowledgments', 'Conflicts of Interest',
      'Declaration of Generative AI and AI-Assisted Technologies in the Writing Process']
for name in BM:
    t = t.replace('## %s\n' % name, '**%s:**\n' % name)

open(MID, 'w', encoding='utf-8').write(t)
print('预处理写出', os.path.basename(MID))

# ---- 5 排版 ----
out = build_mdpi.build(MID, DST)
print('排版输出', os.path.basename(str(out)))

# ---- 6 排版后自检 ----
d = Document(str(DST))
n_par = len(d.paragraphs)
n_tab = len(d.tables)
n_img = len(d.inline_shapes)
txt = '\n'.join(p.text for p in d.paragraphs)
SEC = ('Introduction', 'Institutional Background and Analytical Expectations',
       'Materials and Methods', 'Results', 'Discussion', 'Conclusions', 'References')
n_ref = sum(1 for p in d.paragraphs
            if re.match(r'^\d+\.\s', p.text) and not p.text.endswith(SEC))
print()
print('段落 %d；表格 %d；内联图片 %d；参考文献条目 %d' % (n_par, n_tab, n_img, n_ref))
for k in ['Figure 1', 'Figure 2', 'Table 1', 'Table 4', 'Cai Jian [2017] No. 318',
          '\u22120.370', 'Author Contributions', 'Data Availability Statement']:
    print('  %-28s %s' % (k, '有' if k in txt else '缺失'))
print('  %-28s %s' % ('残留版本标注', '有（需清除）' if 'Manuscript %s —' % VER in txt else '无'))

# ---- 4 视觉风险修复：图与图注同页 ----
BLIP = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
n_fix = 0
for p in d.paragraphs:
    if p._p.findall('.//' + BLIP):
        if not p.paragraph_format.keep_with_next:
            p.paragraph_format.keep_with_next = True
            n_fix += 1
if n_fix:
    d.save(str(DST))
print('  图段 keep_with_next 修复：%d 处' % n_fix)
print()
print('输出：%s' % DST)
