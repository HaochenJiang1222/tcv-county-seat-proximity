# -*- coding: utf-8 -*-
"""抓取中国传统村落数字博物馆「村落名录」全量村级名单（公开接口，无需密钥）

接口  https://www.dmctv.cn/compat-api/directories-province?pici=p
      https://www.dmctv.cn/compat-api/directories-city?ProvinceCode=XX&pici=p
      https://www.dmctv.cn/compat-api/directories-list?ProvinceCode=XX&CityCode=yy&pici=p
      pici 1..6 对应第一批至第六批

输出  data/tcv_funding/roster_national.csv  pici,prov_code,province,city_code,city,village,desc
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tcv_funding" / "roster_national.csv"
BASE = "https://www.dmctv.cn/compat-api/"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
       "Referer": "https://www.dmctv.cn/directories.aspx"}
PICI = [1, 2, 3, 4, 5, 6]


def get(url, retry=3):
    for k in range(retry):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if k == retry - 1:
                print("  FAIL", url, e)
                return ""
            time.sleep(1.2 * (k + 1))
    return ""


def provinces(p=1):
    s = get(BASE + "directories-province?pici=%d" % p)
    return re.findall(r"<option value=(\d+)\s*[^>]*>([^<]+)</option>", s)


def cities(pc, p):
    s = get(BASE + "directories-city?ProvinceCode=%s&pici=%d" % (pc, p))
    return re.findall(r"<option value='(\d+)'\s*[^>]*>([^<]+)</option>", s)


def villages(pc, cc, p):
    s = get(BASE + "directories-list?ProvinceCode=%s&CityCode=%s&pici=%d" % (pc, cc, p))
    out = []
    for m in re.finditer(r"<li><span>([^<]+)<span class='show-more'>", s):
        out.append(m.group(1).strip())
    return out


def main():
    done = set()
    rows = 0
    f = open(OUT, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(f)
    if OUT.stat().st_size == 0:
        w.writerow(["pici", "prov_code", "province", "city_code", "city", "village", "desc"])
    else:
        for r in csv.reader(open(OUT, encoding="utf-8-sig")):
            if len(r) >= 5 and r[0].isdigit():
                done.add((r[0], r[1], r[3]))
        rows = len(done)
    print("已完成 %d 个 省×市×批次 单元" % len(done))

    provs = provinces(1)
    print("省份 %d 个" % len(provs))
    for pc, pname in provs:
        citymap = {}
        for p in PICI:
            for cc, cname in cities(pc, p):
                citymap.setdefault(cc, cname)
            time.sleep(0.1)
        tot = 0
        for cc, cname in sorted(citymap.items()):
            for p in PICI:
                key = (str(p), pc, cc)
                if key in done:
                    continue
                vs = villages(pc, cc, p)
                for v in vs:
                    w.writerow([p, pc, pname, cc, cname, v, ""])
                tot += len(vs)
                rows += 1
                time.sleep(0.12)
        f.flush()
        print("%s 完成，累计村 %d，单元 %d" % (pname, tot, rows), flush=True)
    f.close()
    print("写出", OUT)


if __name__ == "__main__":
    main()
