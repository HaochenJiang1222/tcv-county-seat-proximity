# -*- coding: utf-8 -*-
"""
146：逐页内容清单（分页模拟的文本版视觉校对）
输出每一页的段落条目（首 62 字符），用于人工核对顺序、表图位置与脚注归属。
输出：data/master/page_inventory_<ver>.txt
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.shared import Emu
from docx.text.paragraph import Paragraph
from docx.table import Table

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.argv[1] if len(sys.argv) > 1 else 'v1.3'
SUF = sys.argv[2] if len(sys.argv) > 2 else ''
SRC = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s%s_MDPI.docx' % (VER, SUF))
OUT = os.path.join(ROOT, 'data', 'master', 'page_inventory_%s.txt' % VER)

d = Document(SRC)
s = d.sections[0]
AVH = Emu(s.page_height - s.top_margin - s.bottom_margin).cm
AVW = Emu(s.page_width - s.left_margin - s.right_margin).cm
PT2CM = 0.0352778
BLIP = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'

items = []
for child in d.element.body.iterchildren():
    tag = child.tag.split('}')[-1]
    if tag == 'p':
        items.append(('p', Paragraph(child, d)))
    elif tag == 'tbl':
        items.append(('t', Table(child, d)))


def psize(p):
    for r in p.runs:
        if r.font.size is not None:
            return r.font.size.pt
    try:
        if p.style.font.size is not None:
            return p.style.font.size.pt
    except Exception:
        pass
    return 10.0


def ph(p):
    if p._p.findall('.//' + BLIP):
        h = 0.0
        for sh in d.inline_shapes:
            if sh._inline in p._p.iter():
                h = max(h, sh.height.cm)
        return (h or 8.0) + 0.3
    txt = p.text
    if not txt.strip():
        pf = p.paragraph_format
        return ((pf.space_after.pt if pf.space_after else 0)
                + (pf.space_before.pt if pf.space_before else 0)) * PT2CM
    sz = psize(p)
    pf = p.paragraph_format
    ls = pf.line_spacing if pf.line_spacing else 1.15
    if hasattr(ls, 'pt'):
        ls = 1.15
    cpl = max(20, int(AVW / (sz * 0.5 * PT2CM)))
    nl = max(1, -(-len(txt) // cpl))
    return (nl * sz * float(ls) * 1.2 + (pf.space_after.pt if pf.space_after else 0)
           + (pf.space_before.pt if pf.space_before else 0)) * PT2CM


def th(tb):
    tot = 0.0
    widths = [(c.width.cm if c.width else AVW / max(1, len(tb.columns)))
              for c in tb.columns]
    for row in tb.rows:
        mx = 1
        for i, cell in enumerate(row.cells):
            w = widths[i] if i < len(widths) else 3.0
            cpl = max(6, int((w - 0.3) / (9 * 0.5 * PT2CM)))
            mx = max(mx, -(-max(1, len(cell.text)) // cpl))
        tot += mx * 9.0 * 1.15 * 1.2 * PT2CM + 0.12
    return tot


pages = [[]]
used = 0.0


def gh(i):
    """前瞻式：本段 + 其后由 keep_with_next 粘连的段落总高度"""
    k, o = items[i]
    tot = ph(o) if k == 'p' else th(o)
    j = i
    while (j < len(items) and items[j][0] == 'p'
           and items[j][1].paragraph_format.keep_with_next
           and j + 1 < len(items)):
        nk, no = items[j + 1]
        tot += ph(no) if nk == 'p' else th(no)
        j += 1
    return tot


for idx, (kind, obj) in enumerate(items):
    h = ph(obj) if kind == 'p' else th(obj)
    if used + gh(idx) > AVH and used > 0:
        pages.append([])
        used = 0.0
    pages[-1].append((kind, obj, idx))
    used += h

lines = []
lines.append('逐页内容清单 — manuscript_TCV_EN_%s%s_MDPI.docx' % (VER, SUF))
lines.append('版心 %.1f × %.1f cm；模拟共 %d 页' % (AVW, AVH, len(pages)))
lines.append('=' * 78)
for pi, pg in enumerate(pages, 1):
    lines.append('')
    lines.append('── 第 %d 页 ──' % pi)
    for kind, obj, idx in pg:
        if kind == 't':
            lines.append('  [表 %d行×%d列] %s' % (len(obj.rows), len(obj.columns),
                                                obj.rows[0].cells[0].text[:34]))
            if obj.rows[0].cells[1:]:
                lines.append('            列：%s' % ' | '.join(
                    c.text[:14] for c in obj.rows[0].cells[1:]))
        else:
            if obj._p.findall('.//' + BLIP):
                lines.append('  [图]')
                continue
            txt = obj.text.strip()
            if not txt:
                continue
            lines.append('  %s' % txt[:62])

open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
print('写出', OUT)
print('\n'.join(lines[:60]))
