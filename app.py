"""Industry CRM Value Model: showcase app.

Run locally:  streamlit run app.py
All figures are hypothetical. This is an illustrative showcase, not a financial forecast.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from value_model import (AI_OVERLAP_FACTOR, AI_RAMP, AI_USE_CASES, ADOPTION_QUESTIONS,
                         FEASIBILITY_DEFAULTS, LEVER_DEFAULTS, LEVERS, RAMP,
                         Company, Inputs, adoption_stage, compute)

st.set_page_config(page_title="Industry CRM Value Model", page_icon="📈", layout="wide")

TEAL, CORAL, PURPLE, GRAY = "#1D9E75", "#D85A30", "#534AB7", "#888780"
AMBER = "#E8A838"

# Quadrant colours (priority matrix)
Q_COLORS = {
    "Start here":              TEAL,
    "Build the ground first":  AMBER,
    "Quick win":               PURPLE,
    "Park for now":            GRAY,
}


def m(x, sign=False):
    """Format euros as millions."""
    s = f"{x / 1e6:+,.2f}" if sign else f"{x / 1e6:,.2f}"
    return f"€{s}M".replace("€+", "+€").replace("€-", "−€")


def feasibility_score(data, ease, adoption, risk):
    """Composite feasibility: avg of data, ease, adoption, and inverted risk. Range 1–5."""
    return (data + ease + adoption + (6 - risk)) / 4


def priority_quadrant(value_norm, feasibility_norm):
    """Assign quadrant label from normalised 0–1 value and feasibility scores."""
    high_v = value_norm >= 0.5
    high_f = feasibility_norm >= 0.5
    if high_v and high_f:
        return "Start here"
    if high_v and not high_f:
        return "Build the ground first"
    if not high_v and high_f:
        return "Quick win"
    return "Park for now"


# ---------------------------------------------------------------- header
st.markdown(
    '<div style="font-size:2.5rem;font-weight:700;color:#0F2942;'
    'letter-spacing:-0.02em;margin-bottom:4px;">Industry CRM Value Model</div>'
    '<div style="font-size:0.85rem;color:#9CA3AF;margin-bottom:6px;">'
    '© 2026 Joscha Schmidt &nbsp;·&nbsp; Proprietary &amp; Confidential &nbsp;·&nbsp; All rights reserved'
    '</div>'
    '<div style="font-size:0.95rem;color:#64748B;margin-bottom:20px;">'
    'Value driver model linking CRM KPIs to EBIT, cash flow and payback in industries. '
    'All results are indicative and non-binding.'
    '</div>',
    unsafe_allow_html=True,
)

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

# ════════════════════════════════════════════════════════════════
# SECTION 1 — VALUE MODEL
# ════════════════════════════════════════════════════════════════
st.markdown(
    '<div style="font-size:1.4rem;font-weight:700;color:#0F2942;margin-top:8px;margin-bottom:2px;">'
    '① Value Model</div>'
    '<div style="font-size:0.88rem;color:#64748B;margin-bottom:16px;">'
    'Set your CRM levers and AI use cases. Results flow directly into the Priority Matrix below.'
    '</div>',
    unsafe_allow_html=True,
)

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
    rows_display = []
    for n in ai:
        u = AI_USE_CASES[n]
        eff = ", ".join(f"{LEVERS[k]} {v:+.1f} {'days' if k == 'dso' else 'pts'}" for k, v in u["effects"].items())
        if u.get("capacity_minutes"):
            eff = f"{u['capacity_minutes']} min saved per case (capacity, not EBIT)"
        rows_display.append({"Use case": n, "Type": u["type"], "Effect": eff, "Run cost a year": m(u["run_cost"]),
                             "What it does": u["note"]})
    st.dataframe(pd.DataFrame(rows_display), hide_index=True)
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


# ════════════════════════════════════════════════════════════════
# SECTION 2 — PRIORITY MATRIX
# ════════════════════════════════════════════════════════════════
st.divider()
st.markdown(
    '<div style="font-size:1.4rem;font-weight:700;color:#0F2942;margin-top:8px;margin-bottom:2px;">'
    '② Priority Matrix</div>'
    '<div style="font-size:0.88rem;color:#64748B;margin-bottom:4px;">'
    'Rate each use case on feasibility. Value (Y-axis) is calculated directly from your model above — '
    'no subjective scoring needed.'
    '</div>',
    unsafe_allow_html=True,
)

if not ai:
    st.info("Select one or more AI use cases in Section ① above to unlock the Priority Matrix.", icon="ℹ️")
else:
    st.caption("Adjust the feasibility sliders for each use case. Pre-filled defaults are illustrative — "
               "update them to reflect your actual data landscape and organisation.")

    # --- Feasibility scoring UI ---
    feasibility_scores = {}
    with st.expander("Rate feasibility per use case", expanded=True):
        for uc_name in ai:
            defaults = FEASIBILITY_DEFAULTS[uc_name]
            st.markdown(
                f"<div style='font-weight:600;color:#0F2942;margin-top:10px;margin-bottom:2px;'>{uc_name}</div>"
                f"<div style='font-size:0.82rem;color:#64748B;margin-bottom:6px;'>"
                f"{AI_USE_CASES[uc_name]['note']}</div>",
                unsafe_allow_html=True,
            )
            cols = st.columns(4)
            d = cols[0].slider("Data readiness", 1, 5, defaults["data"], key=f"fs_data_{uc_name}",
                               help="Is the required data available and clean?")
            e = cols[1].slider("Ease", 1, 5, defaults["ease"], key=f"fs_ease_{uc_name}",
                               help="How complex is the integration and IT lift?")
            adp = cols[2].slider("Adoption", 1, 5, defaults["adoption"], key=f"fs_adp_{uc_name}",
                                 help="Will the field or sales team actually use this?")
            rsk = cols[3].slider("Risk", 1, 5, defaults["risk"], key=f"fs_rsk_{uc_name}",
                                 help="Data quality, change management and compliance risk. 5 = high risk.")
            feasibility_scores[uc_name] = feasibility_score(d, e, adp, rsk)

    # --- Build matrix data ---
    ebit_per_case = r["ai_ebit_per_case"]
    max_ebit = max((abs(v) for v in ebit_per_case.values()), default=1.0)
    max_feas = 5.0
    min_feas = 1.0

    matrix_rows = []
    for uc_name in ai:
        ebit_val = ebit_per_case.get(uc_name, 0.0)
        feas_val = feasibility_scores[uc_name]
        # Normalise 0–1 for quadrant assignment
        ebit_norm = abs(ebit_val) / max_ebit if max_ebit > 0 else 0.5
        feas_norm = (feas_val - min_feas) / (max_feas - min_feas)
        quadrant = priority_quadrant(ebit_norm, feas_norm)
        matrix_rows.append({
            "name": uc_name,
            "ebit": ebit_val,
            "feasibility": feas_val,
            "ebit_norm": ebit_norm,
            "feas_norm": feas_norm,
            "quadrant": quadrant,
            "color": Q_COLORS[quadrant],
            "type": AI_USE_CASES[uc_name]["type"],
        })

    # --- Bubble chart ---
    fig2 = go.Figure()

    # Quadrant background shading
    mid_feas = (min_feas + max_feas) / 2  # 3.0
    mid_ebit = max_ebit / 2 / 1e6

    for quad, color, x0, x1, y0, y1 in [
        ("Start here",              "#E8F7F2", mid_feas, max_feas + 0.3, 0, max_ebit / 1e6 * 1.3),
        ("Build the ground first",  "#FEF9EC", min_feas - 0.3, mid_feas, 0, max_ebit / 1e6 * 1.3),
        ("Quick win",               "#F0EEF9", mid_feas, max_feas + 0.3, -max_ebit / 1e6 * 0.3, 0),
        ("Park for now",            "#F5F5F5", min_feas - 0.3, mid_feas, -max_ebit / 1e6 * 0.3, 0),
    ]:
        fig2.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                       fillcolor=color, line_width=0, layer="below")
        # Quadrant label (top-right corner of each zone)
        label_x = (x0 + x1) / 2
        label_y = y1 * 0.92 if y1 > 0 else y0 * 0.5
        fig2.add_annotation(x=label_x, y=label_y, text=quad,
                            showarrow=False, font=dict(size=11, color=Q_COLORS[quad]),
                            opacity=0.7, xanchor="center")

    # Divider lines
    fig2.add_shape(type="line", x0=mid_feas, x1=mid_feas,
                   y0=-max_ebit / 1e6 * 0.3, y1=max_ebit / 1e6 * 1.3,
                   line=dict(color=GRAY, width=1, dash="dot"))
    fig2.add_shape(type="line", x0=min_feas - 0.3, x1=max_feas + 0.3,
                   y0=mid_ebit, y1=mid_ebit,
                   line=dict(color=GRAY, width=1, dash="dot"))

    # Bubbles
    for row_m in matrix_rows:
        ebit_m = row_m["ebit"] / 1e6
        bubble_size = max(12, min(50, abs(ebit_m) * 18 + 12))
        fig2.add_trace(go.Scatter(
            x=[row_m["feasibility"]],
            y=[ebit_m],
            mode="markers+text",
            marker=dict(size=bubble_size, color=row_m["color"],
                        line=dict(color="#FFFFFF", width=2)),
            text=[row_m["name"].split(" ")[0]],  # first word as label to avoid clutter
            textposition="top center",
            textfont=dict(size=10),
            hovertemplate=(
                f"<b>{row_m['name']}</b><br>"
                f"EBIT contribution: {m(row_m['ebit'])}<br>"
                f"Feasibility score: {row_m['feasibility']:.2f} / 5<br>"
                f"Quadrant: {row_m['quadrant']}<br>"
                f"Type: {row_m['type']}"
                "<extra></extra>"
            ),
            name=row_m["name"],
            showlegend=False,
        ))

    fig2.update_layout(
        height=460,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(title="Feasibility  →  (data readiness · ease · adoption · inverted risk)",
                   range=[min_feas - 0.4, max_feas + 0.4],
                   tickvals=[1, 2, 3, 4, 5],
                   showgrid=False),
        yaxis=dict(title="EBIT contribution, € million  (from Value Model above)",
                   showgrid=False),
        plot_bgcolor="#FAFAFA",
        title=dict(text="AI use case priority matrix", font=dict(size=14)),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Ranked shortlist table ---
    sorted_matrix = sorted(matrix_rows, key=lambda x: (
        {"Start here": 0, "Build the ground first": 1, "Quick win": 2, "Park for now": 3}[x["quadrant"]],
        -x["ebit"]
    ))

    st.markdown("**Ranked shortlist**")
    shortlist_df = pd.DataFrame([{
        "Use case": row_m["name"],
        "Type": row_m["type"],
        "EBIT (€M)": f"{row_m['ebit'] / 1e6:.2f}",
        "Feasibility": f"{row_m['feasibility']:.1f} / 5",
        "Quadrant": row_m["quadrant"],
    } for row_m in sorted_matrix])
    st.dataframe(shortlist_df, hide_index=True, use_container_width=True)

    # Determine which cases are "Start here" for Section 3
    start_here_cases = [row_m["name"] for row_m in sorted_matrix if row_m["quadrant"] == "Start here"]
    quick_win_cases  = [row_m["name"] for row_m in sorted_matrix if row_m["quadrant"] == "Quick win"]
    shortlisted_cases = start_here_cases + quick_win_cases  # locked to shortlist for now

    if start_here_cases:
        st.success(
            "**Start here:** " + " · ".join(start_here_cases) +
            ("  |  **Quick wins:** " + " · ".join(quick_win_cases) if quick_win_cases else ""),
            icon="✅",
        )

    # Copy summary
    summary_lines = ["**AI Use Case Priority Summary**", ""]
    for row_m in sorted_matrix:
        summary_lines.append(
            f"• {row_m['name']} — {row_m['quadrant']} | "
            f"EBIT {m(row_m['ebit'])} | Feasibility {row_m['feasibility']:.1f}/5"
        )
    summary_text = "\n".join(summary_lines)
    st.download_button("⬇ Download summary", summary_text, file_name="priority_summary.txt",
                       mime="text/plain", use_container_width=False)


# ════════════════════════════════════════════════════════════════
# SECTION 3 — ADOPTION TRACKER
# ════════════════════════════════════════════════════════════════
st.divider()
st.markdown(
    '<div style="font-size:1.4rem;font-weight:700;color:#0F2942;margin-top:8px;margin-bottom:2px;">'
    '③ Adoption Tracker</div>'
    '<div style="font-size:0.88rem;color:#64748B;margin-bottom:4px;">'
    'Track whether work is actually changing — not licence counts or login rates.'
    '</div>',
    unsafe_allow_html=True,
)

if not ai:
    st.info("Select AI use cases in Section ① and score them in Section ② to unlock the Adoption Tracker.", icon="ℹ️")
elif not shortlisted_cases:
    st.info("No use cases are in the 'Start here' or 'Quick win' quadrants yet. "
            "Adjust feasibility scores or add more use cases in Section ② to build a shortlist.", icon="ℹ️")
else:
    st.caption(
        f"Tracking {len(shortlisted_cases)} shortlisted use case(s) from Section ②. "
        "Tick 'Piloted' for any use case you have started. Answer the four questions to place it on the adoption ladder."
    )

    # --- State: piloted checkbox and question answers ---
    piloted_state = {}
    answers_state = {}

    left_col, right_col = st.columns([1.1, 0.9])

    with left_col:
        st.markdown("**Four questions per use case**")
        st.caption("Licence and login counts tell you whether people tried a tool. "
                   "These four questions tell you whether the work changed.")

        for uc_name in shortlisted_cases:
            piloted_key = f"piloted_{uc_name}"
            piloted = st.checkbox(f"**{uc_name}**  — Piloted", key=piloted_key)
            piloted_state[uc_name] = piloted

            if piloted:
                # Question tabs
                q_tabs = st.tabs([f"Q{i+1}" for i in range(len(ADOPTION_QUESTIONS))])
                uc_answers = {}
                for i, q in enumerate(ADOPTION_QUESTIONS):
                    with q_tabs[i]:
                        st.markdown(f"**{q['question']}**")
                        ans = st.radio(
                            "Select",
                            options=list(range(len(q["answers"]))),
                            format_func=lambda idx, q=q: q["answers"][idx],
                            key=f"ans_{uc_name}_{q['key']}",
                            label_visibility="collapsed",
                        )
                        uc_answers[q["key"]] = ans
                        with st.expander("How to find out", expanded=False):
                            for bullet in q["how_to_find"]:
                                st.markdown(f"- {bullet}")
                answers_state[uc_name] = uc_answers
            else:
                answers_state[uc_name] = {}

            st.markdown("---")

    with right_col:
        # --- Adoption Ladder ---
        stage_labels = {4: "Redesigned", 3: "Embedded", 2: "Used", 1: "Tried"}
        stage_descriptions = {
            4: "Redesigned with the people who do the work, used every time and the value is proven.",
            3: "The standard way of working, with an owner and early measured results.",
            2: "Used regularly by part of the team, but the result is not yet measured or owned.",
            1: "People have access and have tried it. The work itself has not changed.",
        }
        stage_colors = {4: TEAL, 3: PURPLE, 2: AMBER, 1: GRAY}

        # Count use cases per stage
        stage_counts = {4: 0, 3: 0, 2: 0, 1: 0}
        uc_stages = {}
        for uc_name in shortlisted_cases:
            if piloted_state.get(uc_name, False):
                stage_num, stage_label = adoption_stage(answers_state.get(uc_name, {}))
            else:
                stage_num, stage_label = 0, "Not started"
            uc_stages[uc_name] = (stage_num, stage_label)
            if stage_num > 0:
                stage_counts[stage_num] += 1

        st.markdown("**Adoption ladder**")
        for stage_num in [4, 3, 2, 1]:
            count = stage_counts[stage_num]
            label = stage_labels[stage_num]
            desc = stage_descriptions[stage_num]
            color = stage_colors[stage_num]
            border_style = f"border-left: 4px solid {color}; padding: 10px 14px; margin-bottom: 8px; background: #FAFAFA; border-radius: 4px;"
            count_label = f"{count} use case{'s' if count != 1 else ''}"
            st.markdown(
                f'<div style="{border_style}">'
                f'<span style="font-size:0.75rem;font-weight:700;color:{color};text-transform:uppercase;'
                f'letter-spacing:0.05em;">{stage_num} &nbsp; {label}</span>'
                f'<span style="float:right;font-size:0.78rem;color:{GRAY};">{count_label}</span>'
                f'<div style="font-size:0.83rem;color:#64748B;margin-top:3px;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # --- Steering committee view ---
        st.markdown("**Steering committee view**")
        if not any(piloted_state.values()):
            st.caption("Tick 'Piloted' on a use case to start tracking it.")
        else:
            sc_rows = []
            for uc_name in shortlisted_cases:
                if not piloted_state.get(uc_name, False):
                    continue
                stage_num, stage_label = uc_stages[uc_name]
                ebit_val = r["ai_ebit_per_case"].get(uc_name, 0.0)

                # Next action logic
                if stage_num == 4:
                    next_action = "Document and scale"
                elif stage_num == 3:
                    next_action = "Redesign process with the team"
                elif stage_num == 2:
                    next_action = "Set baseline, assign owner"
                else:
                    next_action = "Move from occasional to consistent use"

                sc_rows.append({
                    "Use case": uc_name,
                    "Stage": f"{stage_num} · {stage_label}",
                    "EBIT at stake": m(ebit_val),
                    "Next action": next_action,
                })
            if sc_rows:
                st.dataframe(pd.DataFrame(sc_rows), hide_index=True, use_container_width=True)

                # Copy summary
                sc_lines = ["**Adoption Tracker — Steering Committee View**", ""]
                for row_sc in sc_rows:
                    sc_lines.append(
                        f"• {row_sc['Use case']} | {row_sc['Stage']} | "
                        f"{row_sc['EBIT at stake']} | Next: {row_sc['Next action']}"
                    )
                sc_text = "\n".join(sc_lines)
                st.download_button("⬇ Download summary", sc_text,
                                   file_name="adoption_summary.txt", mime="text/plain")

# ---------------------------------------------------------------- footer
st.divider()
st.caption("Industry CRM Value Model · Joscha Schmidt · Abbreviations: AI artificial intelligence, CFO chief financial "
           "officer, CRM customer relationship management, DSO days sales outstanding, EBIT earnings before interest "
           "and taxes, KPI key performance indicator, OEM original equipment manufacturer, P&L profit and loss.")
