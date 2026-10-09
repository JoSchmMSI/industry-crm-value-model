"""Industry CRM Value Model: calculation engine.

All figures are hypothetical showcase inputs. Rules built in:
- revenue levers count at margin; price and leakage at 100%
- cost savings count as EBIT; capacity is shown separately
- cash release (DSO) is kept out of EBIT; only interest is shown, below EBIT
- each euro is attributed to one lever; AI is uplift on the same KPIs
- several AI use cases on one KPI combine with diminishing returns
- results are net of program cost and run cost, ramped over three years
"""
from dataclasses import dataclass, field

LEVERS = {
    "attach": "Contract attach rate",
    "churn": "Contract churn",
    "win": "Quote win rate",
    "price": "Price realization",
    "leak": "Revenue leakage",
    "ftf": "First-time fix rate",
    "dso": "Days sales outstanding (cash)",
}

# KPI unit, default baseline, default target, direction (+1 higher is better, -1 lower is better)
LEVER_DEFAULTS = {
    "attach": ("%", 40.0, 45.0, +1),
    "churn": ("% a year", 12.0, 9.0, -1),
    "win": ("%", 32.0, 33.0, +1),
    "price": ("% avg. discount", 10.0, 9.0, -1),
    "leak": ("% unbilled", 3.0, 1.5, -1),
    "ftf": ("% of visits", 75.0, 82.0, +1),
    "dso": ("days", 75.0, 62.0, -1),
}

# Illustrative assumptions only: KPI effects in points (days for DSO) and annual run cost in EUR
AI_USE_CASES = {
    "Technician knowledge assistant": {"type": "Generative", "effects": {"ftf": 2.5}, "run_cost": 100_000,
        "note": "Answers from manuals and service history on the technician's device"},
    "Contract propensity model": {"type": "Predictive", "effects": {"attach": 0.8}, "run_cost": 100_000,
        "note": "Ranks uncontracted installed units by likelihood to buy a contract"},
    "Quote drafting assistant": {"type": "Generative", "effects": {"win": 0.3}, "run_cost": 80_000,
        "note": "Drafts quotes from product data and past quotes; seller approves"},
    "Failure alerts from machine data": {"type": "Predictive", "effects": {"ftf": 1.0, "churn": -0.5}, "run_cost": 50_000,
        "note": "Alerts before failure; parts prepared before the visit; protects uptime contracts"},
    "Churn risk model": {"type": "Predictive", "effects": {"churn": -0.8}, "run_cost": 60_000,
        "note": "Flags contracts at risk before renewal from case, usage and payment history"},
    "Price guidance in quoting": {"type": "Predictive", "effects": {"price": -0.3}, "run_cost": 70_000,
        "note": "Suggests a price corridor per deal from won and lost quotes; approval above the limit"},
    "Billing anomaly check": {"type": "Predictive", "effects": {"leak": -0.5, "dso": -2.0}, "run_cost": 50_000,
        "note": "Checks work orders against contracts and invoices before sending; fewer disputes"},
    "Case triage and summaries": {"type": "Generative", "effects": {}, "run_cost": 40_000, "capacity_minutes": 10,
        "note": "Routes and summarizes cases; frees agent time (capacity, not EBIT)"},
}

AI_OVERLAP_FACTOR = 0.75   # second and further AI effects on the same KPI count at 75%
RAMP = (0.25, 0.70, 1.00)  # CRM benefit realization in years 1 to 3
AI_RAMP = (0.0, 0.50, 1.00)  # AI starts after integration and clean data


@dataclass
class Company:
    equipment_revenue: float = 80e6
    equipment_margin: float = 0.30
    service_margin: float = 0.40
    installed_units: int = 5000
    contract_value: float = 10_000
    other_service_revenue: float = 20e6
    pipeline: float = 250e6
    visits: int = 20_000
    revisit_cost: float = 350
    service_cases: int = 15_000
    hourly_cost: float = 60
    baseline_ebit: float = 12e6
    financing_rate: float = 0.06

    def contract_revenue(self, attach_pct):
        return self.installed_units * attach_pct / 100 * self.contract_value

    def total_revenue(self, attach_pct):
        return self.equipment_revenue + self.contract_revenue(attach_pct) + self.other_service_revenue


@dataclass
class Inputs:
    company: Company = field(default_factory=Company)
    levers: dict = field(default_factory=dict)        # key -> (baseline, target)
    ai: list = field(default_factory=list)            # names of AI use cases
    adoption: float = 0.80
    conservative: bool = False
    one_time_cost: float = 3.5e6
    crm_run_cost: float = 0.7e6


def ai_effects(ai_names, scale=1.0):
    """Combined AI effect per KPI, with diminishing returns when use cases overlap."""
    per_kpi = {}
    for name in ai_names:
        for k, v in AI_USE_CASES[name]["effects"].items():
            per_kpi.setdefault(k, []).append(v)
    out = {}
    for k, vals in per_kpi.items():
        vals = sorted(vals, key=abs, reverse=True)
        out[k] = scale * (vals[0] + AI_OVERLAP_FACTOR * sum(vals[1:]))
    return out


def lever_value(key, base, target, c: Company, attach_base):
    """Annual run-rate effect of moving a KPI from base to target.
    Returns dict: revenue, ebit, cash, formula."""
    d = target - base
    if key == "attach":
        units = c.installed_units * d / 100
        rev = units * c.contract_value
        return dict(revenue=rev, ebit=rev * c.service_margin, cash=0,
                    formula=f"{c.installed_units:,} units × {d:+.1f} pts = {units:,.0f} contracts × €{c.contract_value:,.0f} = €{rev/1e6:.2f}M revenue × {c.service_margin:.0%} margin")
    if key == "churn":
        base_rev = c.contract_revenue(attach_base)
        rev = base_rev * (-d) / 100
        return dict(revenue=rev, ebit=rev * c.service_margin, cash=0,
                    formula=f"€{base_rev/1e6:.1f}M contract base × {-d:+.1f} pts churn = €{rev/1e6:.2f}M revenue kept × {c.service_margin:.0%} margin")
    if key == "win":
        rev = c.pipeline * d / 100
        return dict(revenue=rev, ebit=rev * c.equipment_margin, cash=0,
                    formula=f"€{c.pipeline/1e6:.0f}M pipeline × {d:+.1f} pts = €{rev/1e6:.2f}M revenue × {c.equipment_margin:.0%} margin")
    if key == "price":
        rev = c.equipment_revenue * (-d) / 100
        return dict(revenue=rev, ebit=rev, cash=0,
                    formula=f"€{c.equipment_revenue/1e6:.0f}M equipment × {-d:+.1f} pts less discount = €{rev/1e6:.2f}M, no extra cost, 100% to EBIT")
    if key == "leak":
        rev = c.other_service_revenue * (-d) / 100
        return dict(revenue=rev, ebit=rev, cash=0,
                    formula=f"€{c.other_service_revenue/1e6:.0f}M billable service × {-d:+.1f} pts leakage = €{rev/1e6:.2f}M billed, cost already incurred")
    if key == "ftf":
        revisits = c.visits * d / 100
        sav = revisits * c.revisit_cost
        return dict(revenue=0, ebit=sav, cash=0,
                    formula=f"{c.visits:,} visits × {d:+.1f} pts = {revisits:,.0f} revisits avoided × €{c.revisit_cost:,.0f} = €{sav/1e6:.2f}M cost of sales (only if cost is released)")
    if key == "dso":
        rev_total = c.total_revenue(attach_base)
        cash = rev_total / 365 * (-d)
        return dict(revenue=0, ebit=0, cash=cash,
                    formula=f"€{rev_total/1e6:.0f}M revenue ÷ 365 × {-d:+.0f} days = €{cash/1e6:.2f}M cash released once; not EBIT")
    raise KeyError(key)


def clamp(key, v):
    if key == "dso":
        return max(v, 1.0)
    return min(max(v, 0.0), 100.0)


def compute(inp: Inputs):
    c = inp.company
    scale = 0.5 if inp.conservative else 1.0
    ai_kpi = ai_effects(inp.ai, scale)
    attach_base = inp.levers.get("attach", (LEVER_DEFAULTS["attach"][1],))[0]

    keys = list(inp.levers.keys())
    for k in ai_kpi:  # AI on a KPI not selected as lever: start from its default baseline
        if k not in keys:
            keys.append(k)

    rows = []
    for k in keys:
        base, target = inp.levers.get(k, (LEVER_DEFAULTS[k][1], LEVER_DEFAULTS[k][1]))
        target_s = base + (target - base) * scale
        target_ai = clamp(k, target_s + ai_kpi.get(k, 0.0))
        crm = lever_value(k, base, target_s, c, attach_base)
        both = lever_value(k, base, target_ai, c, attach_base)
        ai_part = {x: both[x] - crm[x] for x in ("revenue", "ebit", "cash")}
        rows.append(dict(key=k, name=LEVERS[k], base=base, target=target_s, target_ai=target_ai,
                         crm=crm, ai=ai_part, formula_crm=crm["formula"], formula_total=both["formula"]))

    a = inp.adoption
    crm_ebit = sum(r["crm"]["ebit"] for r in rows) * a
    ai_ebit = sum(r["ai"]["ebit"] for r in rows) * a
    crm_rev = sum(r["crm"]["revenue"] for r in rows) * a
    ai_rev = sum(r["ai"]["revenue"] for r in rows) * a
    cash = sum(r["crm"]["cash"] + r["ai"]["cash"] for r in rows) * a
    ai_run = sum(AI_USE_CASES[n]["run_cost"] for n in inp.ai)

    capacity_hours = sum(c.service_cases * AI_USE_CASES[n].get("capacity_minutes", 0) / 60 for n in inp.ai) * a * scale
    capacity_value = capacity_hours * c.hourly_cost

    net_runrate = crm_ebit + ai_ebit - inp.crm_run_cost - ai_run
    rev_base = c.total_revenue(attach_base)
    margin_before = c.baseline_ebit / rev_base
    margin_after = (c.baseline_ebit + net_runrate) / (rev_base + crm_rev + ai_rev)

    years = []
    cum = 0.0
    for i in range(3):
        y_crm = crm_ebit * RAMP[i]
        y_ai = ai_ebit * AI_RAMP[i]
        y_ai_run = ai_run if AI_RAMP[i] > 0 else 0.0
        y_one = inp.one_time_cost if i == 0 else 0.0
        net = y_crm + y_ai - inp.crm_run_cost - y_ai_run - y_one
        cum += net
        y_cash = cash if i == 1 else 0.0
        years.append(dict(year=i + 1, crm=y_crm, ai=y_ai, crm_run=-inp.crm_run_cost, ai_run=-y_ai_run,
                          one_time=-y_one, net=net, cumulative=cum, cash=y_cash,
                          interest=cash * c.financing_rate if i >= 1 else 0.0))

    def payback(include_cash):
        cum, prev = 0.0, 0.0
        for i in range(10):
            if i < 3:
                y = years[i]
                net = y["net"] + (y["cash"] if include_cash else 0.0)
            else:
                net = net_runrate
            prev, cum = cum, cum + net
            if cum >= 0 and net > 0:
                return i + (-prev / net if prev < 0 else 0.0)
        return None

    return dict(rows=rows, crm_ebit=crm_ebit, ai_ebit=ai_ebit, crm_rev=crm_rev, ai_rev=ai_rev, cash=cash,
                interest=cash * c.financing_rate, ai_run=ai_run, crm_run=inp.crm_run_cost,
                net_runrate=net_runrate, margin_before=margin_before, margin_after=margin_after,
                rev_base=rev_base, years=years, payback=payback(False), payback_cash=payback(True),
                capacity_hours=capacity_hours, capacity_value=capacity_value, adoption=a, scale=scale)
