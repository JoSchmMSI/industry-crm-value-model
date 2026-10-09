"""Industry CRM Value Model: showcase app.

Run locally:  streamlit run app.py
All figures are hypothetical. This is an illustrative showcase, not a financial forecast.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from value_model import (AI_OVERLAP_FACTOR, AI_RAMP, AI_USE_CASES, LEVER_DEFAULTS, LEVERS, RAMP,
                         Company, Inputs, compute)

st.set_page_config(page_title="Industry CRM Value Model", page_icon="📈", layout="wide")

TEAL, CORAL, PURPLE, GRAY = "#1D9E75", "#D85A30", "#534AB7", "#888780"


def m(x, sign=False):
    """Format euros as millions."""
    s = f"{x / 1e6:+,.2f}" if sign else f"{x / 1e6:,.2f}"
    return f"€{s}M".replace("€+", "+€").replace("€-", "−€")


# ---------------------------------------------------------------- header
st.title("Industry CRM Value Model")
st.caption("Value driver model linking CRM KPIs to EBIT, cash flow and payback in industries. "
           "All results are indicative and non-binding.")

# ---------------------------------------------------------------- sidebar: example company
with st.sidebar:
    st.header("Example company")
    st.caption("Hypothetical equipment manufacturer (OEM). Edit any value.")
    eq_rev = st.number_input("Equipment revenue (€M)", 1.0, 10_000.0, 80.0, 1.0)
    eq_margin = st.number_input("Equipment gross margin (%)", 1.0, 90.0, 30.0, 1.0)
    svc_margin = st.number_input("Service gross margin (%)", 1.0, 90.0, 40.0, 1.0,
                                 help="Reference: McKinsey reports an average EBIT margin of about 25% for "
                                      "aftermarket services versus about 10% for new equipment, across 30 industries.")
    units = st.number_input("Installed units", 100, 1_000_000, 5_000, 100)
    cvalue = st.number_input("Service contract value per unit (€ a year)", 100, 1_000_000, 10_000, 500)
    other_svc = st.number_input("Other billable service (€M)", 0.0, 10_000.0, 20.0, 1.0,
                                help="Repairs, parts and time-and-material work outside contracts.")
    pipeline = st.number_input("Quoted equipment pipeline (€M a year)", 1.0, 100_000.0, 250.0, 10.0)
    visits = st.number_input("Field service visits a year", 100, 10_000_000, 20_000, 1_000)
    revisit = st.number_input("Cost per revisit (€)", 10, 100_000, 350, 10)
    cases = st.number_input("Service cases a year", 0, 10_000_000, 15_000, 1_000)
    hourly = st.number_input("Loaded hourly cost (€)", 10, 1_000, 60, 5)
    ebit0 = st.number_input("Baseline EBIT (€M)", -1_000.0, 10_000.0, 12.0, 0.5,
                            help="EBIT: earnings before interest and taxes.")
    fin = st.number_input("Financing cost (%)", 0.0, 30.0, 6.0, 0.5,
                          help="Used only for the interest effect of released cash, below EBIT.")

company = Company(equipment_revenue=eq_rev * 1e6, equipment_margin=eq_margin / 100, service_margin=svc_margin / 100,
                  installed_units=int(units), contract_value=float(cvalue), other_service_revenue=other_svc * 1e6,
                  pipeline=pipeline * 1e6, visits=int(visits), revisit_cost=float(revisit), service_cases=int(cases),
                  hourly_cost=float(hourly), baseline_ebit=ebit0 * 1e6, financing_rate=fin / 100)

# ---------------------------------------------------------------- step 1: CRM levers
st.subheader("1. CRM levers")
chosen = st.multiselect("Select the KPIs (key performance indicators) the program targets",
                        options=list(LEVERS), default=list(LEVERS), format_func=lambda k: LEVERS[k])
levers, warnings = {}, []
for k in chosen:
    unit, b0, t0, direction = LEVER_DEFAULTS[k]
    col = st.columns([3, 2, 2])
    col[0].markdown(f"{LEVERS[k]}  \n<span style='color:{GRAY};font-size:0.85em'>{unit}</span>",
                    unsafe_allow_html=True)
    hi = 365.0 if k == "dso" else 100.0
    step = 1.0 if k == "dso" else 0.5
    base = col[1].number_input("Baseline", 0.0, hi, b0, step, key=f"b_{k}")
    target = col[2].number_input("Target", 0.0, hi, t0, step, key=f"t_{k}")
    levers[k] = (base, target)
    change = (target - base) * direction
    if change < 0:
        warnings.append(f"{LEVERS[k]}: the target is worse than the baseline.")
    elif change > (20 if k == "dso" else 10):
        warnings.append(f"{LEVERS[k]}: a change of {abs(target - base):.1f} {'days' if k == 'dso' else 'points'} "
                        f"is ambitious; check it against a pilot or peer benchmark.")
for w in warnings:
    st.warning(w, icon="⚠️")

# ---------------------------------------------------------------- step 2: AI use cases
st.subheader("2. AI use cases (optional)")
ai = st.multiselect("Add one or several; each is modeled as extra uplift on the same KPIs, with its own run cost",
                    options=list(AI_USE_CASES))
if ai:
    rows = []
    for n in ai:
        u = AI_USE_CASES[n]
        eff = ", ".join(f"{LEVERS[k]} {v:+.1f} {'days' if k == 'dso' else 'pts'}" for k, v in u["effects"].items())
        if u.get("capacity_minutes"):
            eff = f"{u['capacity_minutes']} min saved per case (capacity, not EBIT)"
        rows.append({"Use case": n, "Type": u["type"], "Effect": eff, "Run cost a year": m(u["run_cost"]),
                     "What it does": u["note"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption(f"Illustrative assumptions. When several use cases move the same KPI, the second and further "
               f"effects count at {AI_OVERLAP_FACTOR:.0%}. AI benefits start in year 2, after integration and data cleansing.")

# ---------------------------------------------------------------- step 3 and 4: realization and cost
c3, c4 = st.columns(2)
with c3:
    st.subheader("3. Realization")
    adoption = st.slider("Adoption (share of potential actually realized)", 0, 100, 80, 5, format="%d%%",
                         help="Potential × adoption × ramp-up. Adoption is usually the biggest factor in practice.")
    scenario = st.radio("Scenario", ["Base", "Conservative"], horizontal=True,
                        help="Conservative halves every KPI improvement and AI uplift.")
with c4:
    st.subheader("4. Program cost")
    one_time = st.number_input("One-time cost (€M): design, build, migration, change", 0.0, 1_000.0, 3.5, 0.1)
    run_cost = st.number_input("CRM run cost (€M a year): licenses, support", 0.0, 1_000.0, 0.7, 0.1)

r = compute(Inputs(company=company, levers=levers, ai=ai, adoption=adoption / 100,
                   conservative=(scenario == "Conservative"), one_time_cost=one_time * 1e6,
                   crm_run_cost=run_cost * 1e6))

# ---------------------------------------------------------------- results
st.divider()
st.subheader("Result")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Net EBIT run-rate", m(r["net_runrate"], sign=True),
          help="Full run-rate (year 3) after adoption, minus CRM and AI run costs. One-time cost is in payback.",
          border=True)
k2.metric("EBIT margin", f"{r['margin_after']:.1%}",
          delta=f"{(r['margin_after'] - r['margin_before']) * 100:+.1f} pts vs {r['margin_before']:.1%}", border=True)
k3.metric("Cash released (one-time)", m(r["cash"]),
          delta=f"{m(r['interest'], sign=True)} interest a year", delta_color="off", border=True,
          help="Lower DSO (days sales outstanding) brings cash in sooner. Balance sheet, not EBIT.")
pb = r["payback"]
pbc = r["payback_cash"]
k4.metric("Payback", f"{pb:.1f} years" if pb is not None else "Not within 10 years",
          delta=(f"{pbc:.1f} years incl. cash release" if pbc is not None else None), delta_color="off",
          border=True)
if r["capacity_hours"] > 0:
    st.info(f"Capacity freed: about {r['capacity_hours']:,.0f} agent hours a year (≈ {m(r['capacity_value'])}). "
            f"Shown separately: it only becomes EBIT if cost is actually released.", icon="ℹ️")

# waterfall
labels, values, measures, colors = ["Baseline EBIT"], [company.baseline_ebit], ["absolute"], []
for row in r["rows"]:
    v = row["crm"]["ebit"] * r["adoption"]
    if abs(v) > 1:
        short = row["name"].replace(" rate", "").replace("Contract ", "").replace(" (cash)", "")
        labels.append(short.capitalize())
        values.append(v)
        measures.append("relative")
if abs(r["ai_ebit"]) > 1:
    labels.append("AI uplift")
    values.append(r["ai_ebit"])
    measures.append("relative")
labels.append("CRM run cost")
values.append(-r["crm_run"])
measures.append("relative")
if r["ai_run"]:
    labels.append("AI run cost")
    values.append(-r["ai_run"])
    measures.append("relative")
labels.append("New EBIT run-rate")
values.append(company.baseline_ebit + r["net_runrate"])
measures.append("total")
fig = go.Figure(go.Waterfall(
    x=labels, y=[v / 1e6 for v in values], measure=measures,
    text=[f"{v / 1e6:+.2f}" if mm == "relative" else f"{v / 1e6:.2f}" for v, mm in zip(values, measures)],
    textposition="outside",
    increasing={"marker": {"color": TEAL}}, decreasing={"marker": {"color": CORAL}},
    totals={"marker": {"color": PURPLE}}, connector={"line": {"color": GRAY, "width": 0.5}}))
lo = min(company.baseline_ebit, company.baseline_ebit + r["net_runrate"]) / 1e6
hi_ = (company.baseline_ebit + max(0.0, r["crm_ebit"] + r["ai_ebit"])) / 1e6
pad = max(0.5, (hi_ - lo) * 0.25)
fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
                  yaxis=dict(title="EBIT, € million", range=[max(0.0, lo - pad), hi_ + pad]),
                  title=dict(text="EBIT bridge at full run-rate (axis does not start at zero)", font=dict(size=14)))
st.plotly_chart(fig)

# three-year view
st.markdown("**Three-year view (€ million)**")
yr = pd.DataFrame({
    "": ["CRM levers (ramped)", "AI uplift (ramped)", "CRM run cost", "AI run cost", "One-time program cost",
         "Net EBIT effect", "Cumulative", "Cash release (DSO)", "Interest saved (below EBIT)"],
    **{f"Year {y['year']}": [y["crm"], y["ai"], y["crm_run"], y["ai_run"], y["one_time"], y["net"],
                             y["cumulative"], y["cash"], y["interest"]] for y in r["years"]}})
for col in yr.columns[1:]:
    yr[col] = yr[col].map(lambda v: f"{v / 1e6:+,.2f}" if abs(v) > 1 else "–")
st.dataframe(yr, hide_index=True)

# ---------------------------------------------------------------- show the math
with st.expander("Show the math"):
    st.markdown(f"**Scenario:** {scenario}" + (" (all improvements halved)" if r["scale"] < 1 else "")
                + f"  ·  **Adoption:** {adoption}% applied to every lever")
    for row in r["rows"]:
        st.markdown(f"**{row['name']}:** {row['formula_crm']}")
        if abs(row["ai"]["ebit"]) > 1 or abs(row["ai"]["cash"]) > 1:
            st.markdown(f"&nbsp;&nbsp;+ AI moves the target from {row['target']:.2f} to {row['target_ai']:.2f}: "
                        f"{m(row['ai']['ebit'] + row['ai']['cash'], sign=True)} before adoption")
    st.markdown("---")
    st.markdown(
        f"- Revenue levers count at margin; price realization and leakage count at 100% because no extra cost is attached.\n"
        f"- First-time fix counts as savings only if the cost is really released (overtime, subcontractors).\n"
        f"- Cash from lower DSO is kept out of EBIT; its P&L effect is interest at {fin:.1f}%, below EBIT.\n"
        f"- AI is extra uplift on the same KPIs, never a separate benefit, so no euro is counted twice.\n"
        f"- Ramp-up: CRM levers {', '.join(f'{x:.0%}' for x in RAMP)}; AI {', '.join(f'{x:.0%}' for x in AI_RAMP)} in years 1 to 3.\n"
        f"- Payback: years until cumulative net EBIT turns positive (after year 3 at run-rate). Tax and timing within a year are ignored.")

st.divider()
st.caption("Industry CRM Value Model · Joscha Schmidt · Abbreviations: AI artificial intelligence, CFO chief financial "
           "officer, CRM customer relationship management, DSO days sales outstanding, EBIT earnings before interest "
           "and taxes, KPI key performance indicator, OEM original equipment manufacturer, P&L profit and loss.")
