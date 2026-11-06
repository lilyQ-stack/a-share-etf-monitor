#!/usr/bin/env python3
"""Conservative SSE post-clearing ETF share collector. No synthetic data."""
import argparse
import csv
import json
import os
import re
import urllib.request
from datetime import datetime
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

FUNDS = {"510300":"沪深300", "510310":"沪深300", "510330":"沪深300",
         "510050":"上证50", "510180":"上证180", "510500":"中证500",
         "512100":"中证1000", "588080":"科创50"}
SOURCE = "https://www.sse.com.cn/assortment/fund/list/etfinfo/basic/index.shtml?FUNDID={code}"
DATA = Path("data/sse_shares.csv")
DIAGNOSTIC = Path("output/sse_diagnostic.json")
FIELDS = ["date","code","index","shares_10k","shares","source","captured_at_cst"]

def download(code):
    url = SOURCE.format(code=code)
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ETF research collector)",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.sse.com.cn/"})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read(5_000_000)
    return raw.decode("utf-8", errors="replace"), url

def parse_share_rows(html, code):
    """Only accept fully labelled, fund-specific rows in the 基金规模 section.
    Do not parse PCF creation units, trading volume, or fund AUM."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    # Fail closed when server responds with a JavaScript-only application shell.
    start = text.find("基金规模")
    if start < 0:
        return [], "missing_fund_scale_section"
    stop = text.find("公告申购赎回清单", start + 4)
    section = text[start: stop if stop > start else None]
    # Keep only explicitly dated rows with the exact fund code and '万份' scale.
    if "总份额（万份）" not in section and "总份额(万份)" not in section:
        return [], "missing_total_shares_header"
    pattern = re.compile(r"(20\d{2}-\d{2}-\d{2})\s+" + re.escape(code) +
                         r"\s+(.{1,55}?)\s+([\d,]+(?:\.\d+)?)"
                         r"(?=\s+(?:20\d{2}-\d{2}-\d{2}|注：|注:|$))")
    result = []
    for match in pattern.finditer(section):
        date, label, share_text = match.groups()
        try:
            datetime.strptime(date, "%Y-%m-%d")
            amount = float(share_text.replace(",", ""))
            if not (0 < amount < 1e10):
                continue
            # The official field is 万份 (10,000 shares), not 份 or 亿元.
            result.append({"date":date,"code":code,"index":FUNDS[code],
                           "shares_10k":format(amount, ".4f").rstrip("0").rstrip("."),
                           "shares":str(round(amount * 10000)),
                           "source":SOURCE.format(code=code)})
        except (ValueError, OverflowError):
            continue
    return result, ("ok" if result else "no_valid_dated_rows")

def persist(rows):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    old = []
    if DATA.exists():
        with DATA.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDS:
                raise ValueError("CSV schema mismatch; refusing overwrite")
            old = list(reader)
    merged = {(r["date"],r["code"]):r for r in old}
    for r in rows:
        key = (r["date"],r["code"])
        if key in merged and merged[key]["shares"] != r["shares"]:
            raise ValueError(f"Official share revision requires manual review: {key}")
        merged.setdefault(key, r)
    records = sorted(merged.values(), key=lambda r:(r["date"],r["code"]))
    if len(records) == len(old):
        return 0
    import tempfile
    with tempfile.NamedTemporaryFile("w",dir=DATA.parent,delete=False,encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
        temp=f.name
    os.replace(temp,DATA)
    return len(records)-len(old)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--probe",action="store_true",help="Only diagnose; do not write history")
    args=parser.parse_args()
    now=datetime.now(ZoneInfo("Asia/Shanghai"))
    diag={"captured_at_cst":now.isoformat(),"mode":"probe" if args.probe else "collect",
          "instruments":{},"new_rows":0,
          "note":"Share data only. No NAV, net subscription or national-team attribution."}
    candidates=[]
    for code in FUNDS:
        try:
            html,url=download(code)
            rows,status=parse_share_rows(html,code)
            # Do not allow future-dated rows or implausibly old future-year dates.
            rows=[r for r in rows if r["date"] <= now.date().isoformat()]
            candidates.extend(rows)
            diag["instruments"][code]={"status":status,"rows":len(rows),
                                      "latest":max((r["date"] for r in rows),default=None),
                                      "response_bytes":len(html),"source":url}
        except Exception as exc:
            diag["instruments"][code]={"status":"error","error":f"{type(exc).__name__}: {exc}"}
    if not args.probe and candidates:
        stamp=now.isoformat()
        for row in candidates: row["captured_at_cst"]=stamp
        diag["new_rows"]=persist(candidates)
    diag["status"]="observed" if candidates else "no_verified_rows"
    DIAGNOSTIC.parent.mkdir(parents=True,exist_ok=True)
    DIAGNOSTIC.write_text(json.dumps(diag,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(diag,ensure_ascii=False,indent=2))
    if not candidates: raise SystemExit("No verified SSE share rows; refusing to fabricate")

if __name__=="__main__": main()
