#!/usr/bin/env python3
"""Collect SSE post-clearing ETF shares via the exchange's dated ETF-scale JSON.
Fail closed: never fill missing funds, invent dates or infer net flows.
"""
import csv
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

FUNDS = {"510300":"沪深300", "510310":"沪深300", "510330":"沪深300",
         "510050":"上证50", "510180":"上证180", "510500":"中证500",
         "512100":"中证1000", "588080":"科创50"}
URL = "https://query.sse.com.cn/commonQuery.do"
REFERER = "https://www.sse.com.cn/market/funddata/volumn/etfvolumn/"
SQL_ID = "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L"
DATA = Path("data/sse_shares.csv")
DIAG = Path("output/sse_diagnostic.json")
FIELDS = ["date","code","index","shares_10k","shares","source","captured_at_cst"]
TZ = ZoneInfo("Asia/Shanghai")

def fetch_date(session, date):
    params = {
        "isPagination":"true", "pageHelp.pageSize":"1000",
        "pageHelp.pageNo":"1", "pageHelp.beginPage":"1",
        "pageHelp.cacheSize":"1", "pageHelp.endPage":"1",
        "sqlId":SQL_ID, "STAT_DATE":date
    }
    response=session.get(URL,params=params,timeout=25)
    response.raise_for_status()
    obj=response.json()
    if not isinstance(obj,dict): raise ValueError("Unexpected JSON root")
    rows=obj.get("result")
    if not isinstance(rows,list): rows=(obj.get("pageHelp") or {}).get("data")
    if not isinstance(rows,list): raise ValueError("Missing result/pageHelp.data")
    count=int((obj.get("pageHelp") or {}).get("pageCount") or 1)
    if count>1: raise ValueError(f"Pagination count {count}>1; refusing incomplete set")
    selected={}
    for row in rows:
        if not isinstance(row,dict): continue
        code=str(row.get("SEC_CODE") or "").strip()
        if code not in FUNDS: continue
        rowdate=str(row.get("STAT_DATE") or "").strip()
        if rowdate!=date: raise ValueError(f"Date mismatch for {code}: {rowdate!r}")
        if code in selected: raise ValueError(f"Duplicate {code} on {date}")
        try:
            vol=Decimal(str(row["TOT_VOL"]).replace(",","").strip())
            shares=vol*10000
            if not vol.is_finite() or vol<=0 or shares!=shares.to_integral_value():
                raise ValueError("Invalid fractional/zero share count")
        except (KeyError,InvalidOperation,TypeError) as exc:
            raise ValueError(f"Invalid TOT_VOL for {code}") from exc
        selected[code]={"date":date,"code":code,"index":FUNDS[code],
            "shares_10k":format(vol,"f"),
            "shares":str(int(shares)),
            "source":REFERER}
    if set(selected)!=set(FUNDS):
        missing=sorted(set(FUNDS)-set(selected))
        raise ValueError(f"Incomplete ETF set ({len(selected)}/8), missing={missing}, raw_rows={len(rows)}")
    return [selected[k] for k in sorted(selected)],len(rows)

def persist(incoming):
    DATA.parent.mkdir(parents=True,exist_ok=True)
    existing=[]
    if DATA.exists():
        with DATA.open(newline="",encoding="utf-8") as f:
            reader=csv.DictReader(f)
            if reader.fieldnames!=FIELDS: raise ValueError("Unexpected historical CSV schema")
            existing=list(reader)
    indexed={(r["date"],r["code"]):r for r in existing}
    if len(indexed)!=len(existing): raise ValueError("Duplicate stored dates/codes")
    for row in incoming:
        key=(row["date"],row["code"])
        if key in indexed and indexed[key]["shares"]!=row["shares"]:
            raise ValueError(f"Official revision for {key}; review manually")
        indexed.setdefault(key,row)
    added=len(indexed)-len(existing)
    if added:
        tmp=DATA.with_suffix(".tmp")
        with tmp.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(sorted(indexed.values(),key=lambda r:(r["date"],r["code"])))
        os.replace(tmp,DATA)
    return added

def main():
    now=datetime.now(TZ)
    diag={"captured_at_cst":now.isoformat(),"source":URL,
          "source_page":REFERER,"status":"not_verified",
          "dates":{},"new_rows":0}
    DIAG.parent.mkdir(parents=True,exist_ok=True)
    try:
        session=requests.Session()
        session.headers.update({"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
          "Referer":REFERER,"Accept":"application/json, text/javascript, */*; q=0.01"})
        accepted=[]
        # Query a short window so a delayed daily run can recover recent trading days.
        # Weekends/holidays have no rows and are not treated as errors for other dates.
        for age in range(0,9):
            date=(now.date()-timedelta(days=age)).isoformat()
            if (now.date()-timedelta(days=age)).weekday()>=5: continue
            try:
                rows,total=fetch_date(session,date)
                for row in rows: row["captured_at_cst"]=now.isoformat()
                accepted.extend(rows)
                diag["dates"][date]={"status":"verified","funds":len(rows),"source_rows":total}
            except Exception as exc:
                diag["dates"][date]={"status":"rejected","error":f"{type(exc).__name__}: {exc}"}
        if accepted:
            diag["new_rows"]=persist(accepted)
            diag["status"]="verified_partial_dates" if any(x["status"]=="rejected" for x in diag["dates"].values()) else "verified"
        else: diag["status"]="no_verified_dates"
    except Exception as exc:
        diag["fatal_error"]=f"{type(exc).__name__}: {exc}"
    finally:
        DIAG.write_text(json.dumps(diag,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(diag,ensure_ascii=False,indent=2))
    if diag["status"] not in ("verified","verified_partial_dates"):
        raise SystemExit("No verified complete date; see diagnostic")
if __name__=="__main__":main()
