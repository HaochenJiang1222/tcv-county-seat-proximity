# -*- coding: utf-8 -*-
"""
第四批（2016年认定，1598村）母表 × 2017/2018 全国中央财政支持名单 全量匹配。
用法： python dofile/103_match_national.py
输出： data/tcv_funding/official/support_national.csv  全国支持名单（带批次）
       data/tcv_funding/official/batch4_matched.csv    1598村逐村匹配结果
       data/tcv_funding/official/match_report.txt      匹配报告
"""
import re, sys, csv, html
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

FD = Path('data/tcv_funding')
OFF = FD / 'official'
PROVS = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
         '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
         '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
         '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区']
PROV_HEAD = re.compile(r'^(?:[一二三四五六七八九十]+[、.])?\s*(' + '|'.join(PROVS) + r')\s*[（(]\s*\d+\s*个\s*[）)]\s*\$')
VILL_LINE = re.compile(r'[\u4e00-\u9fa5]{2,}(?:镇|乡|街道|苏木|办事处|管理委员会|管委会|社区)[\u4e00-\u9fa5]{2,}')


def load(f: Path):
    raw = f.read_bytes()
    for enc in ('utf-8', 'gb18030'):
        try:
            s = raw.decode(enc)
            break
        except Exception:
            pass
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '\n', s)
    s = html.unescape(s).replace('\xa0', '\n')
    return [l.strip() for l in s.split('\n') if l.strip()]


def norm(v: str) -> str:
    v = str(v).replace(' ', '').replace('\u3000', '')
    v = re.sub(r'^(?:' + '|'.join(PROVS) + r')', '', v)
    v = re.sub(r'[（）()\[\]【】]', '', v)
    v = re.sub(r'(村委|村委会)$', '', v)
    return v


def harvest(lines, start, end):
    """从 lines[start:end] 抽取村名行"""
    out, prov = [], None
    for l in lines[start:end]:
        if re.search(r'(MERGEFORMAT|^PAGE\$|^\d+\$|视频|小程序|在看|分享|留言|收藏|听过)', l):
            continue
        m = PROV_HEAD.match(l)
        if m:
            prov = m.group(1)
            continue
        if not (6 <= len(l) <= 45):
            continue
        if not VILL_LINE.search(l):
            continue
        if re.search(r'(名单|通知|公布|附件|来源|编辑|记者|字号|点击|返回|上一篇|下一篇|拟列入|支持范围的中国传统村落)', l):
            continue
        out.append((prov, l))
    return out


def main():
    # ---------- 1. 2017 年名单（600）+ 2018 年拟列入（444） ----------
    L = load(FD / 'f2017.html')
    i17 = next(i for i, l in enumerate(L) if l.strip() == '2017年列入中央财政支持范围的中国传统村落名单')
    i18 = next(i for i, l in enumerate(L) if '2018年拟列入中央财政支持范围的中国传统村落名单' == l.strip())
    g17 = harvest(L, i17 + 1, i18)
    g18 = harvest(L, i18 + 1, len(L))
    print('2017年列入      解析 %d（官方 600）' % len(g17))
    print('2018年拟列入    解析 %d（官方 444）' % len(g18))

    # ---------- 2. 2018 年第二批（156） ----------
    L2 = load(FD / 'f2018b.html')
    ia = next((i for i, l in enumerate(L2) if '附件' in l and '2018年第二批' in l), None)
    g18b = harvest(L2, (ia + 1) if ia else 0, len(L2))
    print('2018年第二批    解析 %d（官方 156）' % len(g18b))

    sup = []
    for prov, v in g17:
        sup.append(dict(batch='2017', prov=prov, raw=v, key=norm(v)))
    for prov, v in g18:
        sup.append(dict(batch='2018-1', prov=prov, raw=v, key=norm(v)))
    for prov, v in g18b:
        sup.append(dict(batch='2018-2', prov=prov, raw=v, key=norm(v)))
    with (OFF / 'support_national.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['batch', 'prov', 'raw', 'key'])
        w.writeheader()
        w.writerows(sup)
    print('支持名单写出', len(sup), '条')

    # ---------- 3. 与第四批母表匹配 ----------
    ros = list(csv.DictReader((OFF / 'roster_official.csv').open(encoding='utf-8-sig')))
    print('母表', len(ros), '村')
    idx = {}
    for s in sup:
        idx.setdefault(s['key'], []).append(s['batch'])
    rows, hit = [], 0
    for r in ros:
        k = norm(r['full'])
        bs = idx.get(k, [])
        rows.append(dict(prov=r['prov'], city=r['city'], county=r['county'],
                         township=r['township'], village=r['village'], full=r['full'],
                         first_batch=(sorted(bs)[0] if bs else ''),
                         n_batch=len(bs), batches='|'.join(sorted(bs))))
        hit += 1 if bs else 0
    with (OFF / 'batch4_matched.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('匹配命中 %d / %d = %.1f%%' % (hit, len(ros), 100 * hit / len(ros)))

    # ---------- 4. 分组与报告 ----------
    import collections
    arm = collections.Counter(r['first_batch'] if r['first_batch'] else 'D-未列入' for r in rows)
    lines = ['第四批（1598村）支持时序分组', '']
    for k in ['2017', '2018-1', '2018-2', 'D-未列入']:
        lines.append('  %-10s %4d  %5.1f%%' % (k, arm.get(k, 0), 100 * arm.get(k, 0) / len(rows)))
    lines.append('')
    lines.append('分省（2017 / 2018-1 / 2018-2 / 未列入 / 合计）')
    byprov = collections.defaultdict(collections.Counter)
    for r in rows:
        byprov[r['prov']][r['first_batch'] or 'D'] += 1
    for p in PROVS:
        if p in byprov:
            c = byprov[p]
            lines.append('  %-10s %4d %4d %4d %4d  %4d' % (p, c['2017'], c['2018-1'], c['2018-2'], c['D'], sum(c.values())))
    txt = '\n'.join(lines)
    print()
    print(txt)
    (OFF / 'match_report.txt').write_text(txt, encoding='utf-8')


if __name__ == '__main__':
    main()
