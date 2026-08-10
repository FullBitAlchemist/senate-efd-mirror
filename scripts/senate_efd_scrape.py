#!/usr/bin/env python3
"""Standalone Senate eFD scraper — runs on a NON-blocked host (GitHub Actions).

efdsearch.senate.gov edge-blocks datacenter IPs (e.g. our DigitalOcean droplet),
so the 24/7 agent cannot scrape it directly. This script runs on GitHub's
runners (clean IPs), writes recent electronic Periodic Transaction Reports to a
JSON file, and the repo publishes that file via raw.githubusercontent.com — which
the droplet CAN read (config.SENATE_EFD_MIRROR).

Output: a JSON list of {ticker, senator, type, transaction_date, disclosure_date,
amount} — the exact shape agent._fetch_senate_mirror() consumes. No project deps.

Usage: python senate_efd_scrape.py [output_path] [lookback_days]
"""
import json, re, sys, time, datetime as dt
import requests

BASE = "https://efdsearch.senate.gov"
UA = "Mozilla/5.0 (compatible; CongressAgentMirror/1.0; +https://github.com)"
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/senate_efd.json"
LOOKBACK = int(sys.argv[2]) if len(sys.argv) > 2 else 45
MAX_REPORTS = 60


def norm_date(s):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime((s or "").strip()[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def parse_ptr(html):
    out = []
    for tbl in re.findall(r"<table.*?</table>", html, re.S):
        if "Transaction Date" not in tbl or "Ticker" not in tbl:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S):
            cols = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                    for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cols) < 8:
                continue
            txn_date, ticker_cell = cols[1], cols[3].upper()
            asset_name, asset_type, ttype, amount = cols[4], cols[5], cols[6], cols[7]
            if "stock" not in (asset_type or "").lower():
                continue
            ticker = ticker_cell if re.fullmatch(r"[A-Z]{1,5}", ticker_cell) else ""
            if not ticker:
                m = re.match(r"([A-Z]{1,5})\s*-\s", asset_name)
                ticker = m.group(1) if m else ""
            if ticker:
                out.append((norm_date(txn_date) or txn_date, ticker, ttype, amount))
    return out


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"})
    land = s.get(f"{BASE}/search/", timeout=30)
    land.raise_for_status()
    token = s.cookies.get("csrftoken", "")
    s.post(f"{BASE}/search/home/", timeout=30, headers={"Referer": f"{BASE}/search/"},
           data={"prohibition_agreement": "1", "csrfmiddlewaretoken": token})
    token = s.cookies.get("csrftoken", token)
    frm = (dt.date.today() - dt.timedelta(days=LOOKBACK)).strftime("%m/%d/%Y")
    resp = s.post(f"{BASE}/search/report/data/", timeout=40,
                  headers={"Referer": f"{BASE}/search/", "X-CSRFToken": token},
                  data={"draw": "1", "start": "0", "length": "200", "search[value]": "",
                        "report_types": "[11]", "filer_types": "[]",
                        "submitted_start_date": f"{frm} 00:00:00", "submitted_end_date": "",
                        "candidate_state": "", "senator_state": "", "office_id": "",
                        "first_name": "", "last_name": "", "csrfmiddlewaretoken": token})
    rows = resp.json().get("data", [])
    records, reports = [], 0
    for r in rows[:MAX_REPORTS]:
        first, last = (r[0] or "").strip(), (r[1] or "").strip()
        link, fdate = r[3] or "", norm_date(r[4] or "")
        m = re.search(r'href=[\'"](/search/view/[^\'"]+)', link)
        if not m or not fdate:
            continue
        try:
            rp = s.get(BASE + m.group(1), timeout=30, headers={"Referer": f"{BASE}/search/"})
            reports += 1
            if rp.status_code == 200:
                for txn_date, ticker, ttype, amount in parse_ptr(rp.text):
                    records.append({"ticker": ticker,
                                    "senator": f"{first} {last}".strip() or "Senator",
                                    "type": ttype, "transaction_date": txn_date,
                                    "disclosure_date": fdate, "amount": amount})
        except Exception as e:
            print(f"report fetch failed: {e}", file=sys.stderr)
        time.sleep(0.25)

    import os
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    payload = {"generated_at": dt.datetime.utcnow().isoformat() + "Z",
               "lookback_days": LOOKBACK, "count": len(records), "records": records}
    # agent._fetch_senate_mirror accepts either a bare list or {"records": [...]}.
    with open(OUT, "w") as f:
        json.dump(records, f, indent=0)
    with open(OUT.replace(".json", "_meta.json"), "w") as f:
        json.dump({k: payload[k] for k in ("generated_at", "lookback_days", "count")}, f)
    print(f"wrote {len(records)} records from {reports} reports -> {OUT}")


if __name__ == "__main__":
    main()
