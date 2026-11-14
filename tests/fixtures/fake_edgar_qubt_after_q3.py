import json, os
ROWS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qubt_edgar_rows_after_q3.json")))
ROWS.sort(key=lambda r: r[1], reverse=True)
def fetch(url):
    if url.endswith("company_tickers.json"):
        return {"0": {"cik_str": 1758009, "ticker": "QUBT", "title": "Quantum Computing Inc."}}
    return {"name": "Quantum Computing Inc.", "filings": {"recent": {
        "form": [r[0] for r in ROWS], "filingDate": [r[1] for r in ROWS], "reportDate": [r[2] for r in ROWS],
        "accessionNumber": [r[3] for r in ROWS], "primaryDocument": [r[4] for r in ROWS], "items": [r[5] for r in ROWS],
        "primaryDocDescription": [r[0] for r in ROWS]}}}
