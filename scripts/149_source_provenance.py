# -*- coding: utf-8 -*-
"""149：历史名单与第五批名录的原始文件挂接（第十七轮，任务三）

做三件事，不做推断：
 1. 逐个原始解析文件取 SHA-256、字节数、修改时间，供外部核对
 2. 从文件本身提取可识别的来源信息（站点名、标题、发布日期），写进溯源表
 3. 用一份留存的住建部官网页面独立复核已解析的 2014 年第二批名单

输入  data/master/raw/*, data/tcv_funding/official_pre/*, p2014_2.html
输出  data/master/source_provenance.txt / source_provenance.csv
"""
import csv, sys, os, re, html, hashlib, collections, datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW708 = os.path.join(ROOT, 'data', 'master', 'raw')
PRE = os.path.join(ROOT, 'data', 'tcv_funding', 'official_pre')
OFF = os.path.join(ROOT, 'data', 'tcv_funding', 'official')
OUTD = os.path.join(ROOT, 'data', 'master')

FILES = [
    ('第四批认定名录 1598 村（原始 wikitext 备份）', os.path.join(RAW708, 'wikisource_2016.wiki'),
     'wikisource 转录：住房城乡建设部等《关于公布第四批列入中国传统村落名录的村落名单的通知》建村〔2016〕278号'),
    ('第四批认定名录 1598 村（本地官方 .doc 解析）', os.path.join(OFF, 'batch4.doc'),
     '官方 .doc 副本，与 wikisource 转录交叉核对'),
    ('2017 支持名单 600 村（原始网页）', os.path.join(RAW708, 's2017.html'),
     '基于 zsad.com.cn 转载的 2017 年支持名单'),
    ('2018 拟支持名单 444 村（原始网页）', os.path.join(RAW708, 'p2018.html'),
     '基于 asqxzs.com 转载的 2018 年拟支持名单'),
    ('历史名单 2014-1（原始 .doc）', os.path.join(PRE, 'f2014_1.doc'),
     '财政部/住建部 2014 年第一批名单的 .doc 附件副本'),
    ('历史名单 2014-2（已解析文件）', os.path.join(PRE, 'raw', 'f2014_2.html'),
     '传统村落网转载自住建部网站'),
    ('历史名单 2015-1 与 2015 附件2（已解析文件）', os.path.join(PRE, 'raw', 'f2015_1.html'),
     '建村部门 2015 年名单通知全文（通知 + 附件1 名单）'),
    ('历史名单 2015-2（已解析文件）', os.path.join(PRE, 'raw', 'f2015_2.html'),
     '中国传统村落数字博物馆站点'),
    ('历史名单 2016-1（已解析文件）', os.path.join(PRE, 'raw', 'f2016_1.html'),
     '地方门户网站全文转载，含完整名单'),
    ('历史名单 2016-2（已解析文件）', os.path.join(PRE, 'raw', 'f2016_2.html'),
     '全文转录名单'),
    ('复核用：2014-2 住建部官网页面（未用于解析）', os.path.join(PRE, 'p2014_2.html'),
     'mohurd.gov.cn 原文'),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def page_meta(p):
    """从 HTML 里提取可识别的来源线索"""
    s = open(p, encoding='utf-8', errors='ignore').read()
    t = re.search(r'<title>(.*?)</title>', s, re.S)
    out = {'title': html.unescape(t.group(1)).strip() if t else ''}
    canon = re.findall(r'rel="canonical"\s+href="([^"]+)"', s) or \
        re.findall(r'href="([^"]+)"\s+rel="canonical"', s)
    out['canonical'] = canon[0] if canon else ''
    for kw in ['来源', '发布时间', '日期']:
        m = re.search(kw + r'[：: ]{0,4}([^<\n]{2,40})', s)
        if m:
            out[kw] = html.unescape(m.group(1)).strip()[:40]
    return out


def main():
    lines, rows = [], []
    lines.append('=== 原始解析文件溯源清单（截至 %s）==='
                 % datetime.date.today().isoformat())
    lines.append('%-38s %10s %18s %s' % ('文件', '字节', 'SHA-256 前16位', '可识别来源'))
    for lab, p, note in FILES:
        if not os.path.exists(p):
            lines.append('%-38s %10s %18s  缺失' % (os.path.basename(p), '-', '-'))
            continue
        b = os.path.getsize(p)
        h16 = sha(p)[:16]
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d')
        src = ''
        if p.endswith('.html'):
            mm = page_meta(p)
            src = '；'.join([x for x in (mm['title'], mm.get('canonical', ''),
                                          mm.get('发布时间', ''), mm.get('来源', '')) if x])
        rows.append(dict(item=lab, file=os.path.relpath(p, ROOT).replace('\\', '/'),
                         bytes=b, sha256_first16=h16, mtime=mt, source=src or note, note=note))
        lines.append('%-38s %10d %18s %s' % (os.path.basename(p), b, h16, src or note))
        lines.append('    -> %s；本地保存日 %s' % (note, mt))

    lines.append('')
    lines.append('=== 完整校验和见 source_provenance.csv（40 位列 replication-paper）===')

    # ---------- 用留存的住建部页面复核 2014-2 ----------
    lines.append('')
    lines.append('=== 独立复核：2014 年第二批（官方页面 vs 已解析名单）===')
    fin = list(csv.DictReader(open(os.path.join(PRE, 'support_national_final.csv'),
                                   encoding='utf-8-sig')))
    got = {re.sub(r'[\s（）()]', '', r['raw']) for r in fin if r['batch'] == '2014-2'}
    s = open(os.path.join(PRE, 'p2014_2.html'), encoding='utf-8', errors='ignore').read()
    s = re.sub(r'<[^>]+>', '\n', s)
    s = html.unescape(s).replace('\xa0', '\n')
    cand = [l.strip() for l in s.split('\n') if l.strip()]
    VILL = re.compile(r'村|寨|屯|堡|组|社区')
    ext = set()
    for x in cand:
        if len(x) < 5 or len(x) > 45:
            continue
        if re.match(r'^(附件|注|说明|一、|二、|三、|四、|五、|六、|七、|八、|九、|十)', x):
            continue
        if not VILL.search(x):
            continue
        ext.add(re.sub(r'[\s（）()]', '', x))
    inter = got & ext
    lines.append('  官方页面抽取 %d 条；已解析名单 %d 条；完全一致 %d 条' % (len(ext), len(got), len(inter)))
    lines.append('  仅见于官方页面 %d 条；仅见于已解析名单 %d 条' % (len(ext) - len(inter), len(got) - len(inter)))
    for x in sorted(ext - got)[:8]:
        lines.append('      页面独有: ' + x)
    for x in sorted(got - ext)[:8]:
        lines.append('      名单独有: ' + x)
    rows.append(dict(item='2014-2 官方页面复核', file='data/tcv_funding/official_pre/p2014_2.html',
                     bytes=os.path.getsize(os.path.join(PRE, 'p2014_2.html')),
                     sha256_first16=sha(os.path.join(PRE, 'p2014_2.html'))[:16],
                     mtime=datetime.datetime.fromtimestamp(
                         os.path.getmtime(os.path.join(PRE, 'p2014_2.html'))).strftime('%Y-%m-%d'),
                     source='抽取 %d 条，与已解析名单一致 %d 条' % (len(ext), len(inter)),
                     note='复核用'))
    lines.append('')

    if rows:
        with open(os.path.join(OUTD, 'source_provenance.csv'), 'w', newline='',
                  encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    open(os.path.join(OUTD, 'source_provenance.txt'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
