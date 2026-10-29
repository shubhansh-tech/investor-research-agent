"""Build the fictional EXMP ticker: three tiny inline-XBRL filings plus fetch logs,
EDGAR snapshot and synthetic news. EXMP is invented (it matches the illustrative row
in PRD Q17) and lets the app and tests run before real CB/QUBT filings are added.

Expected TTM values (10-K FY2025 + 10-Q H1 2026 - 10-Q H1 2025):
  net income 1,200 + 640 - 600 = 1,240 ($M)
  average equity (6,500 + 7,000) / 2 = 6,750  -> ROE 18.37%
  owner earnings 1,240 + D&A 200 + SBC 60 - depreciation 180 - WC 40 = 1,280
  market cap 62.50 x 500M = 31,250 -> Owner Earnings Yield 4.10%

Run:  python tools/make_exmp_fixture.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "data" / "EXMP"

CIK = "0000999999"
P = {  # period id -> (start, end)
    "FY25": ("2025-01-01", "2025-12-31"), "FY24": ("2024-01-01", "2024-12-31"),
    "H126": ("2026-01-01", "2026-06-30"), "H125": ("2025-01-01", "2025-06-30"),
    "H124": ("2024-01-01", "2024-06-30"),
}
# income / cash flow values in $M by period
FLOW = {
    "NI":   {"FY25": 1200, "FY24": 1100, "H126": 640, "H125": 600, "H124": 560},
    "DA":   {"FY25": 190, "FY24": 180, "H126": 105, "H125": 95, "H124": 90},
    "SBC":  {"FY25": 55, "FY24": 50, "H126": 32, "H125": 27, "H124": 25},
    "AR":   {"FY25": 30, "FY24": 20, "H126": 25, "H125": 15, "H124": 10},   # increase in receivables (uses cash)
    "CAPEX": {"FY25": 210, "FY24": 200, "H126": 110, "H125": 100, "H124": 95},
    "DEP":  {"FY25": 170, "FY24": 160, "H126": 95, "H125": 85, "H124": 80},
    "REV":  {"FY25": 9000, "FY24": 8500, "H126": 4700, "H125": 4400, "H124": 4100},
}
# balance sheet instants in $M: (assets, liabilities, equity)
BS = {
    "2026-06-30": (20000, 13000, 7000), "2025-12-31": (19000, 12200, 6800),
    "2025-06-30": (18600, 12100, 6500), "2024-12-31": (18000, 11700, 6300),
}


def ctx_xml(cid: str, start=None, end=None, instant=None) -> str:
    period = (f"<xbrli:instant>{instant}</xbrli:instant>" if instant else
              f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>")
    return (f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}'
            f"</xbrli:identifier></xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>")


def num(concept, cid, v, paren=False):
    tag = f'<ix:nonFraction name="{concept}" contextRef="{cid}" unitRef="usd" scale="6" decimals="-6">{abs(v):,}</ix:nonFraction>'
    return f"$ ({tag})" if paren else f"$ {tag}"


def build(form, period_end, flow_periods, bs_dates, shares, shares_date, fy, fp, symbol="EXMP", name="Example Holdings Inc."):
    ctxs = [ctx_xml("cover", *P[flow_periods[0]]), ctx_xml("sh", instant=shares_date)]
    for p in flow_periods:
        ctxs.append(ctx_xml(p, *P[p]))
    for d in bs_dates:
        ctxs.append(ctx_xml("i" + d, instant=d))
    hdr = "".join(f"<th>{p}</th>" for p in flow_periods)

    def row(label, concept, key, paren=False):
        cells = "".join(f"<td>{num(concept, p, FLOW[key][p], paren)}</td>" for p in flow_periods)
        return f"<tr><td>{label}</td>{cells}</tr>"

    def bsrow(label, concept, idx):
        cells = "".join(f"<td>{num(concept, 'i' + d, BS[d][idx])}</td>" for d in bs_dates)
        return f"<tr><td>{label}</td>{cells}</tr>"

    tl = "".join(f"<td>{num('us-gaap:LiabilitiesAndStockholdersEquity', 'i' + d, BS[d][1] + BS[d][2])}</td>" for d in bs_dates)
    return f"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
<div style="display:none"><ix:header><ix:hidden>
<ix:nonNumeric name="dei:DocumentType" contextRef="cover">{form}</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="cover">{period_end}</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="cover">{fy}</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="cover">{fp}</ix:nonNumeric>
<ix:nonNumeric name="dei:EntityCentralIndexKey" contextRef="cover">{CIK}</ix:nonNumeric>
</ix:hidden><ix:resources>{''.join(ctxs)}</ix:resources></ix:header></div>
<p>FICTIONAL TEST FILING - EXMP does not exist. {form} for the period ended {period_end}.</p>
<p>Registrant: <ix:nonNumeric name="dei:EntityRegistrantName" contextRef="cover">{name}</ix:nonNumeric>
 Trading symbol: <ix:nonNumeric name="dei:TradingSymbol" contextRef="cover">{symbol}</ix:nonNumeric></p>
<p>Shares of common stock outstanding as of {shares_date}:
 <ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="sh" unitRef="shares" decimals="INF">{shares:,}</ix:nonFraction></p>
<h3>CONSOLIDATED BALANCE SHEETS</h3>
<table><tr><th></th>{''.join(f'<th>{d}</th>' for d in bs_dates)}</tr>
{bsrow('Total assets', 'us-gaap:Assets', 0)}
{bsrow('Total liabilities', 'us-gaap:Liabilities', 1)}
{bsrow("Total shareholders' equity", 'us-gaap:StockholdersEquity', 2)}
<tr><td>Total liabilities and shareholders' equity</td>{tl}</tr></table>
<h3>CONSOLIDATED STATEMENTS OF OPERATIONS</h3>
<table><tr><th></th>{hdr}</tr>
{row('Total revenues', 'us-gaap:Revenues', 'REV')}
{row('Net income', 'us-gaap:NetIncomeLoss', 'NI')}</table>
<h3>CONSOLIDATED STATEMENTS OF CASH FLOWS</h3>
<table><tr><th></th>{hdr}</tr>
{row('Net income', 'us-gaap:NetIncomeLoss', 'NI')}
{row('Depreciation and amortization', 'us-gaap:DepreciationDepletionAndAmortization', 'DA')}
{row('Share-based compensation', 'us-gaap:ShareBasedCompensation', 'SBC')}
{row('Increase in accounts receivable', 'us-gaap:IncreaseDecreaseInAccountsReceivable', 'AR', paren=True)}
{row('Purchases of property and equipment', 'us-gaap:PaymentsToAcquirePropertyPlantAndEquipment', 'CAPEX', paren=True)}</table>
<h3>NOTES TO CONSOLIDATED FINANCIAL STATEMENTS</h3>
<p>Note 5 - Property and equipment</p>
<table><tr><th></th>{hdr}</tr>{row('Depreciation expense', 'us-gaap:Depreciation', 'DEP')}</table>
</body></html>"""


FILINGS = [
    # file, form, period_end, flow periods, bs dates, shares, shares date, fy, fp, filing date, accession
    ("exmp-20251231.htm", "10-K", "2025-12-31", ["FY25", "FY24"], ["2025-12-31", "2024-12-31"], 495_000_000, "2026-02-10", "2025", "FY", "2026-02-20", "0000999999-26-000011"),
    ("exmp-20260630.htm", "10-Q", "2026-06-30", ["H126", "H125"], ["2026-06-30", "2025-12-31"], 500_000_000, "2026-07-25", "2026", "Q2", "2026-07-30", "0000999999-26-000052"),
    ("exmp-20250630.htm", "10-Q", "2025-06-30", ["H125", "H124"], ["2025-06-30", "2024-12-31"], 490_000_000, "2025-07-25", "2025", "Q2", "2025-07-31", "0000999999-25-000049"),
]

LOG_COLS = ["Form Type", "Form Description", "Filing Date", "Reporting Date", "Filings URL", "Accession Number"]


def url(acc: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{CIK.lstrip('0')}/{acc.replace('-', '')}/{acc}-index.htm"


def main() -> None:
    (T / "filings").mkdir(parents=True, exist_ok=True)
    rows = []
    for fn, form, pe, fps, bsd, sh, shd, fy, fp, fdate, acc in FILINGS:
        (T / "filings" / fn).write_text(build(form, pe, fps, bsd, sh, shd, fy, fp))
        desc = "Annual report" if form == "10-K" else "Quarterly report"
        rows.append([form, desc, fdate, pe, url(acc), acc])
    k8 = [["8-K", "Current report, items 2.02 and 9.01", "2026-07-29", "2026-07-29", url("0000999999-26-000050"), "0000999999-26-000050"]]
    q1 = ["10-Q", "Quarterly report", "2026-04-30", "2026-03-31", url("0000999999-26-000031"), "0000999999-26-000031"]

    # Q1 2026 10-Q exists on EDGAR but was not downloaded; it pre-dates the latest
    # fetch-log filing date, so the new-filing rule correctly ignores it.
    pd.DataFrame(rows, columns=LOG_COLS).to_excel(T / "10-K-10-Q_fetch_log.xlsx", index=False)
    pd.DataFrame(k8, columns=LOG_COLS).to_excel(T / "8-K_fetch_log.xlsx", index=False)
    snap = T / "edgar_snapshot_TEST_only"
    snap.mkdir(exist_ok=True)
    pd.DataFrame(rows + [q1], columns=LOG_COLS).to_excel(snap / "10-K-10-Q_EDGAR_filing_list.xlsx", index=False)
    pd.DataFrame(k8, columns=LOG_COLS).to_excel(snap / "8-K_EDGAR_filing_list.xlsx", index=False)
    (T / "synthetic-news_TEST_only").mkdir(exist_ok=True)
    print("EXMP fixture written to", T, file=sys.stderr)


if __name__ == "__main__":
    main()
