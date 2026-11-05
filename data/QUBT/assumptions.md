# QUBT assumptions (written by Shubhansh; read-only for the agent)

## Standing decisions on owner earnings

Decided 2026-11-04; the reasoning is in docs/POLICY_DECISIONS.md. The agent applies these on
every run and flags only items not listed here, or a listed item that trips its alarm.

```yaml
decisions:
  - name: Warrant revaluation (QPhoton warrants, derivative liability)
    concepts: [us-gaap:FairValueAdjustmentOfWarrants]
    treatment: remove
    alarm: none
```
