"""Standing decisions: Shubhansh's per-ticker policy for recurring owner-earnings items.

Read from the ```yaml block in <TICKER>/assumptions.md. The agent never writes them.

How each treatment maps onto the cash-flow statement
----------------------------------------------------
Owner earnings = net income + the cash-flow adjustment lines we choose to include.
A cash-flow adjustment line *reverses* an item's effect on net income, so:
  remove       include the line          -> the item's effect on profit is taken out
  normalize    include the line, then subtract its N-year annual average
               -> this year's effect is replaced by the average effect
  as_reported  include the line as reported (real cash, e.g. "Other")
  exclude      leave the line out         (cash that is not owners' earnings, e.g. float)
  keep         leave the line out         (the item stays in profit as reported)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config as C

TREATMENTS = {"remove", "normalize", "as_reported", "exclude", "keep"}
ALARMS = {"size", "deviation", "none"}
INCLUDES_LINE = {"remove", "normalize", "as_reported"}

SIZE_ALARM = 0.15        # remove items: flag if this year exceeds 15% of the alarm base
DEVIATION_ALARM = 0.05   # normalize / as_reported: flag if this year is >5% of base away from average
MIN_HISTORY_YEARS = 3    # a normalized average needs at least this many years


@dataclass
class Decision:
    name: str
    concepts: list[str]
    treatment: str
    alarm: str = "none"
    years: int = 5

    @property
    def includes_line(self) -> bool:
        return self.treatment in INCLUDES_LINE


@dataclass
class Decisions:
    items: list[Decision] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def by_concept(self) -> dict[str, Decision]:
        return {c: d for d in self.items for c in d.concepts}

    def for_model(self) -> list[dict]:
        return [{"name": d.name, "concepts": d.concepts, "treatment": d.treatment} for d in self.items]


_YAML_BLOCK = re.compile(r"```ya?ml\s*\n(.*?)```", re.S)


def load(tdir: Path) -> Decisions:
    p = tdir / C.ASSUMPTIONS_FILE
    out = Decisions()
    if not p.exists():
        return out
    m = _YAML_BLOCK.search(p.read_text(encoding="utf-8"))
    if not m:
        return out
    try:
        data = yaml.safe_load(m[1]) or {}
    except yaml.YAMLError as e:
        out.problems.append(f"{tdir.name}/{C.ASSUMPTIONS_FILE}: decisions block is not valid YAML ({e})")
        return out
    for i, raw in enumerate(data.get("decisions") or [], start=1):
        name = str(raw.get("name") or f"decision {i}")
        concepts = raw.get("concepts") or ([raw["concept"]] if raw.get("concept") else [])
        treatment = str(raw.get("treatment", "")).strip()
        alarm = str(raw.get("alarm", "none")).strip()
        if not concepts or treatment not in TREATMENTS or alarm not in ALARMS:
            out.problems.append(f"{tdir.name}/{C.ASSUMPTIONS_FILE}: decision '{name}' needs concepts, a treatment "
                                f"({'/'.join(sorted(TREATMENTS))}) and an alarm ({'/'.join(sorted(ALARMS))})")
            continue
        out.items.append(Decision(name, [str(c) for c in concepts], treatment, alarm, int(raw.get("years", 5))))
    return out
