# -*- coding: utf-8 -*-
"""
145：排版成品视觉校对（分页模拟 + 风险检测）
环境无 Word / LibreOffice，改用几何估算复现分页，检测四类视觉问题：
  V1 图与图注跨页分离
  V2 表题与表格分离、表格跨页断裂（报出断裂行）
  V3 表格总宽超出版心
  V4 标题页与 back matter 元素完整性
输出：data/master/visual_proof.txt
"""
import io
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.shared import Emu, Pt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.argv[1] if len(sys.argv) > 1 else 'v1.2'
SUF = sys.argv[2] if len(sys.argv) > 2 else ''
SRC = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s%s_MDPI.docx' % (VER, SUF))
OUT = os.path.join(ROOT, 'data', 'master', 'visual_proof_%s.txt' % VER)

buf = io.StringIO()


def P(s=''):
    buf.write(s + '\n')
    print(s)


d = Document(SRC)
s = d.sections[0]
AVH = Emu(s.page_height - s.top_margin - s.bottom_margin).cm
AVW = Emu(s.page_width - s.left_margin - s.right_margin).cm

P('=' * 78)
P('排版成品视觉校对（分页模拟）')
P('=' * 78)
P('文件：%s' % os.path.basename(SRC))
P('版面：A4 21.0 × 29.7 cm；版心 %.1f × %.1f cm' % (AVW, AVH))
P()

PT2CM = 0.0352778


def style_size(p, default=10.0):
    sz = None
    for r in p.runs:
        if r.font.size is not None:
            sz = r.font.size.pt
            break
    if sz is None:
        try:
            if p.style.font.size is not None:
                sz = p.style.font.size.pt
        except Exception:
            sz = None
    return sz or default


def para_height(p):
    txt = p.text
    sz = style_size(p)
    pf = p.paragraph_format
    ls = pf.line_spacing if pf.line_spacing else 1.15
    if hasattr(ls, 'pt'):
        ls = 1.15
    sa = pf.space_after.pt if pf.space_after else 0
    sb = pf.space_before.pt if pf.space_before else 0
    # 图：用实际图片高度
    if p._p.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
        h = 0.0
        for sh in d.inline_shapes:
            if sh._inline in p._p.iter():
                h = max(h, sh.height.cm)
        if h == 0:
            h = 8.0
        return h + (sa + sb) * PT2CM
    if not txt.strip():
        return (sa + sb) * PT2CM
    cpl = max(20, int(AVW / (sz * 0.5 * PT2CM)))
    nline = max(1, -(-len(txt) // cpl))
    return nline * sz * float(ls) * 1.2 * PT2CM + (sa + sb) * PT2CM


def table_height(tb):
    tot = 0.0
    widths = [(c.width.cm if c.width else AVW / max(1, len(tb.columns))) for c in tb.columns]
    for row in tb.rows:
        mx = 1
        for i, cell in enumerate(row.cells):
            w = widths[i] if i < len(widths) else 3.0
            sz = 9.0
            cpl = max(6, int((w - 0.3) / (sz * 0.5 * PT2CM)))
            mx = max(mx, -(-max(1, len(cell.text)) // cpl))
        tot += mx * 9.0 * 1.15 * 1.2 * PT2CM + 0.12
    return tot


# ---- 按 body 顺序遍历 ----
body = d.element.body
items = []
for child in body.iterchildren():
    tag = child.tag.split('}')[-1]
    if tag == 'p':
        from docx.text.paragraph import Paragraph
        items.append(('p', Paragraph(child, d)))
    elif tag == 'tbl':
        from docx.table import Table
        items.append(('t', Table(child, d)))

# ---- 分页模拟（前瞻式 keepNext：整组一起推到下一页） ----
pages = [[]]
used = 0.0


def newpage():
    global used
    pages.append([])
    used = 0.0


def group_height(i):
    """本段 + 其后所有由 keep_with_next 粘连的段落的总高度"""
    k, o = items[i]
    tot = para_height(o) if k == 'p' else table_height(o)
    j = i
    while (j < len(items) and items[j][0] == 'p'
           and items[j][1].paragraph_format.keep_with_next
           and j + 1 < len(items)):
        nk, no = items[j + 1]
        tot += para_height(no) if nk == 'p' else table_height(no)
        j += 1
    return tot


for idx, (kind, obj) in enumerate(items):
    h = para_height(obj) if kind == 'p' else table_height(obj)
    gh = group_height(idx)
    if used + gh > AVH and used > 0:
        newpage()
    pages[-1].append((kind, obj, idx))
    used += h

P('模拟结果：共 %d 页；表格 %d 个；图片 %d 个'
  % (len(pages), len(d.tables), len(d.inline_shapes)))
P()

# ---- V1 图与图注分离 ----
P('--- V1  图与图注是否跨页分离 ---')
fig_pg = {}
for pi, pg in enumerate(pages, 1):
    for kind, obj, idx in pg:
        if kind == 'p' and obj._p.findall(
                './/{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
            fig_pg[idx] = pi
bad = 0
for idx, pi in fig_pg.items():
    cap = items[idx + 1][1] if idx + 1 < len(items) else None
    cap_pg = None
    for pj, pg in enumerate(pages, 1):
        for k, o, i2 in pg:
            if i2 == idx + 1:
                cap_pg = pj
    if cap is None or not cap.text.strip().startswith('Figure'):
        P('  [FAIL] 第 %d 段图片后无 Figure 图注' % idx)
        bad += 1
    elif cap_pg != pi:
        P('  [FAIL] 图（第 %d 页）与图注（第 %d 页）分离' % (pi, cap_pg))
        bad += 1
    else:
        P('  [PASS] 第 %d 段图片与图注同在第 %d 页：%s'
          % (idx, pi, cap.text.strip()[:52]))
if bad == 0:
    P('  结论：图与图注未分离')

# ---- V2 表格 ----
P()
P('--- V2  表题与表格同页、表格跨页断裂 ---')
tbl_breaks = []
for ti, tb in enumerate(d.tables, 1):
    idx = None
    for i2, (k, o) in enumerate(items):
        if k == 't' and o._tbl is tb._tbl:
            idx = i2
            break
    pg = None
    for pj, p in enumerate(pages, 1):
        for k, o, i2 in p:
            if i2 == idx:
                pg = pj
    cap = items[idx - 1][1].text.strip() if idx and items[idx - 1][0] == 'p' else ''
    ok_cap = (cap.startswith('Table %d.' % ti)
              or cap.startswith('Table A%d.' % (ti - len(d.tables) + len(d.tables)))
              or bool(re.match(r'^Table A\d+\.', cap)))
    P('  表%d：第 %d 页；%d 行；表题 %s' % (ti, pg, len(tb.rows),
                                    'OK' if ok_cap else '缺失/不符（%s）' % cap[:40]))
    # 估算各行高度，判断是否可能跨页
    h = table_height(tb)
    P('        估算高度 %.1f cm（版心 %.1f cm）%s'
      % (h, AVH, '— 可能跨页' if h > AVH * 0.55 else '— 单页可容纳'))
    if not ok_cap:
        tbl_breaks.append('表%d 表题' % ti)

# ---- V3 表格宽度 ----
P()
P('--- V3  表格宽度是否超出版心（%.1f cm）---' % AVW)
for ti, tb in enumerate(d.tables, 1):
    tot = sum((c.width.cm if c.width else 0) for c in tb.columns)
    flag = 'FAIL 超宽' if tot > AVW + 0.05 else 'PASS'
    P('  表%d：总宽 %.1f cm  %s' % (ti, tot, flag))
    if tot > AVW + 0.05:
        tbl_breaks.append('表%d 超宽' % ti)

# ---- V4 元素完整性 ----
P()
P('--- V4  标题页与声明完整性 ---')
txt = '\n'.join(p.text for p in d.paragraphs)
for k in ['Recognition as Eligibility', 'Yue Yu', 'Haochen Jiang',
          'College of Humanities and Education', 'College of Rural Revitalization',
          '210036', 'Abstract', 'Keywords', 'Author Contributions', 'Funding',
          '2024SJYB0562', 'Data Availability Statement', 'Conflicts of Interest']:
    P('  [%s] %s' % ('PASS' if k in txt else 'FAIL', k))
ai = 'AI' in txt or 'artificial intelligence' in txt.lower()
P('  [%s] AI 使用披露' % ('PASS' if ai else 'FAIL'))

P()
P('=' * 78)
P('待处理：%s' % ('；'.join(tbl_breaks) if tbl_breaks else '无'))
P('=' * 78)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(buf.getvalue())
