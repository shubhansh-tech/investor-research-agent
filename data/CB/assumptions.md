# CB assumptions (written by Shubhansh; read-only for the agent)

maintenance_capex_ttm: $637M

Why: Chubb does not disclose depreciation expense in its 10-K or 10-Qs, so the rule
"maintenance capex = depreciation" needs an estimate. Source: 10-K FY2025, Note 1 p)
"Property and equipment" (property and equipment $3.5B at 2025-12-31).
- Capitalized software $2.2B / 5 years = $440M (all software assumed 5 years; the
  15-year systems of record are ignored by choice)
- Company-owned facilities $364M / 40 years = $9M
- Remaining property and equipment ~$0.94B ($3.5B - $2.2B - $0.364B), type not
  disclosed, / 5 years = $188M
- Total = $637M per year
Limitation: the note gives net book values (after accumulated depreciation), so this
likely understates depreciation on original cost.
