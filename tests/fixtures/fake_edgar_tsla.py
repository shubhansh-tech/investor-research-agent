# Stand-in for SEC EDGAR (made-up accession numbers; layout of the real JSON service)
F = []
def add(form, filed, period, doc, items=""):
    n = len(F) + 1
    F.append((form, filed, period, f"0000950170-{filed[2:4]}-{n:06d}", doc, items))
for y in range(2021, 2026):
    add("10-K", f"{y+1}-01-29", f"{y}-12-31", f"tsla-{y}1231.htm")
for y, qs in ((2025, ("03-31", "06-30", "09-30")), (2026, ("03-31", "06-30", "09-30"))):
    for q in qs:
        filed = {"03-31": "04-23", "06-30": "07-24", "09-30": "10-23"}[q]
        add("10-Q", f"{y}-{filed}", f"{y}-{q}", f"tsla-{y}{q.replace('-', '')}.htm")
        add("8-K", f"{y}-{filed}", f"{y}-{filed}", f"tsla-8k{y}{filed}.htm", "2.02,9.01")
add("10-K/A", "2026-04-30", "2025-12-31", "tsla-10ka.htm")
add("8-K", "2026-11-03", "2026-11-03", "tsla-8k-1103.htm", "5.07")
F.sort(key=lambda r: r[1], reverse=True)
def fetch(url):
    if url.endswith("company_tickers.json"):
        return {"0": {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."}, "1": {"cik_str": 1, "ticker": "CB", "title": "Chubb"}, "2": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA Corp"}}
    return {"name": "Tesla, Inc.", "filings": {"recent": {
        "form": [r[0] for r in F], "filingDate": [r[1] for r in F], "reportDate": [r[2] for r in F],
        "accessionNumber": [r[3] for r in F], "primaryDocument": [r[4] for r in F], "items": [r[5] for r in F],
        "primaryDocDescription": [r[0] for r in F]}}}
