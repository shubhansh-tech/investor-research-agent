# Stand-in for SEC EDGAR listing QUBT's real filing names and dates (accession numbers made up)
F = [("10-Q","2026-08-11","2026-06-30","qubt-20260630.htm",""), ("8-K","2026-08-11","2026-08-11","q8k1.htm","2.02,9.01"),
     ("10-Q","2026-05-12","2026-03-31","qubt-20260331.htm",""), ("10-K","2026-03-16","2025-12-31","qubt-20251231.htm",""),
     ("8-K","2026-03-16","2026-03-16","q8k2.htm","2.02"), ("10-Q","2025-11-14","2025-09-30","qubt-20250930.htm",""),
     ("10-Q","2025-08-14","2025-06-30","qubt-20250630.htm",""), ("10-K","2025-03-31","2024-12-31","qubt-20241231.htm",""),
     ("8-K","2026-10-01","2026-10-01","q8k3.htm","5.02")]
F.sort(key=lambda r: r[1], reverse=True)
def fetch(url):
    if url.endswith("company_tickers.json"):
        return {"0": {"cik_str": 1758009, "ticker": "QUBT", "title": "Quantum Computing Inc."}}
    return {"name": "Quantum Computing Inc.", "filings": {"recent": {
        "form": [r[0] for r in F], "filingDate": [r[1] for r in F], "reportDate": [r[2] for r in F],
        "accessionNumber": [f"0001213900-{r[1][2:4]}-{i:06d}" for i, r in enumerate(F)], "primaryDocument": [r[3] for r in F],
        "items": [r[4] for r in F], "primaryDocDescription": [r[0] for r in F]}}}
