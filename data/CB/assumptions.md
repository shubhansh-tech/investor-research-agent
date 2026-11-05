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
likely understates depreciation on original cost. Because depreciation is not disclosed,
the agent adds the same estimate back, so the two cancel.

## Standing decisions on owner earnings

Decided 2026-11-04/05; the reasoning is in docs/POLICY_DECISIONS.md. The agent applies these
on every run and flags only items not listed here, or a listed item that trips its alarm.
Older 10-Ks for the 5-year history go in CB/history/.

Treatments: remove = take the item out of owner earnings (non-cash); normalize = replace this
year's figure with the N-year average; as_reported = include the cash-flow line as reported;
exclude = leave the line out of owner earnings.
Alarms (measured against the larger of |net income| and 1% of shareholders' equity):
size = flag if this year's amount exceeds 15%; deviation = flag if this year differs from its
N-year average by more than 5%.

```yaml
decisions:
  - name: Realized investment gains/losses
    concepts: [us-gaap:RealizedInvestmentGainsLosses]
    treatment: normalize
    years: 5
    alarm: deviation
  - name: Market-risk-benefit value changes
    concepts: [us-gaap:MarketRiskBenefitChangeInFairValueGainLoss]
    treatment: remove
    alarm: size
  - name: Equity-method income (partially-owned entities)
    concepts: [us-gaap:IncomeLossFromEquityMethodInvestments]
    treatment: normalize
    years: 5
    alarm: deviation
  - name: Investment-fund flows (consolidated investment products)
    concepts: [cb:SalesPurchaseOfInvestmentsByConsolidatedInvestmentsProducts,
               cb:SalesPurchaseOfInvestmentsByConsolidatedInvestmentProducts]
    treatment: exclude
    alarm: none
  - name: Other operating line
    concepts: [us-gaap:IncreaseDecreaseInOtherOperatingCapitalNet]
    treatment: as_reported
    years: 5
    alarm: deviation
  - name: Insurance float (unpaid losses)
    concepts: [us-gaap:IncreaseDecreaseInLiabilityForClaimsAndClaimsAdjustmentExpenseReserve]
    treatment: exclude
    alarm: none
  - name: Insurance float (unearned premiums)
    concepts: [us-gaap:IncreaseDecreaseInUnearnedPremiums]
    treatment: exclude
    alarm: none
  - name: Insurance float (future policy benefits)
    concepts: [us-gaap:IncreaseDecreaseInFuturePolicyBenefitReserves]
    treatment: exclude
    alarm: none
  - name: Insurance float (reinsurance balances payable)
    concepts: [us-gaap:IncreaseDecreaseInReinsurancePayables]
    treatment: exclude
    alarm: none
  - name: Insurance float (insurance and reinsurance balances receivable)
    concepts: [us-gaap:IncreaseDecreaseInPremiumsReceivable]
    treatment: exclude
    alarm: none
  - name: Insurance float (reinsurance recoverable)
    concepts: [us-gaap:IncreaseDecreaseInReinsuranceRecoverable]
    treatment: exclude
    alarm: none
  - name: Insurance float (deferred policy acquisition costs)
    concepts: [us-gaap:IncreaseDecreaseInDeferredPolicyAcquisitionCosts]
    treatment: exclude
    alarm: none
```
