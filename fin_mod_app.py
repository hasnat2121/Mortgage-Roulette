import math
from dataclasses import dataclass
from typing import Callable, Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Mortgage Roulette", layout="wide", initial_sidebar_state="collapsed")

# ---------- UI polish ----------
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
        max-width: 1280px;
    }
    h1, h2, h3 {
        letter-spacing: -0.02em;
    }
    .subtle {
        color: #6b7280;
        font-size: 0.95rem;
        line-height: 1.45;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    .section-card {
        padding: 0.9rem 1rem;
        border: 1px solid rgba(49,51,63,0.12);
        border-radius: 12px;
        background: rgba(250,250,252,0.72);
        margin-bottom: 0.9rem;
    }
    div[data-testid="stTabs"] button {
        white-space: nowrap;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.75rem;
            padding-bottom: 1rem;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        h1 { font-size: 1.65rem; }
        h2 { font-size: 1.2rem; }
        h3 { font-size: 1.05rem; }
        .subtle { font-size: 0.88rem; }
        [data-testid="stMetricValue"] { font-size: 1.15rem; }
        .section-card {
            padding: 0.75rem 0.8rem;
            border-radius: 10px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_chart_with_actions(fig: go.Figure, chart_key: str, title: str):
    chart_json = fig.to_json()
    chart_html = pio.to_html(fig, full_html=True, include_plotlyjs="cdn")

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "displaylogo": False,
            "responsive": True,
            "toImageButtonOptions": {"format": "png", "filename": chart_key, "scale": 2},
        },
        key=f"plot_{chart_key}",
    )

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            label="Download HTML",
            data=chart_html,
            file_name=f"{chart_key}.html",
            mime="text/html",
            key=f"download_{chart_key}",
            use_container_width=True,
        )
    with c2:
        button_html = f"""
        <button onclick="navigator.clipboard.writeText(document.getElementById('clip-{chart_key}').value)"
                style="width:100%;padding:0.5rem 0.75rem;border:1px solid rgba(49,51,63,0.2);border-radius:8px;background:#fff;cursor:pointer;">
            Copy chart JSON
        </button>
        <textarea id="clip-{chart_key}" style="position:absolute;left:-9999px;top:-9999px;">{chart_json}</textarea>
        """
        components.html(button_html, height=44)

    st.caption(f"Use the modebar on the chart to download a PNG. Use Download HTML or Copy chart JSON below for sharing.")


# =========================
# STAMP DUTY FUNCTIONS
# =========================

def england_stamp_duty_standard(property_price: float) -> float:
    bands = [
        (125000, 0.00),
        (250000, 0.02),
        (925000, 0.05),
        (1500000, 0.10),
        (float("inf"), 0.12),
    ]
    remaining = property_price
    previous_limit = 0
    tax = 0.0
    for limit, rate in bands:
        taxable_band = min(remaining, limit - previous_limit)
        if taxable_band > 0:
            tax += taxable_band * rate
            remaining -= taxable_band
        previous_limit = limit
        if remaining <= 0:
            break
    return tax


def england_stamp_duty_ftb(property_price: float) -> float:
    if property_price > 500000:
        return england_stamp_duty_standard(property_price)
    if property_price <= 300000:
        return 0.0
    return (property_price - 300000) * 0.05


# =========================
# DATA MODEL
# =========================

@dataclass
class Scenario:
    name: str
    property_price: float
    deposit: float
    annual_rate: float
    term_years: int
    fees: Dict[str, float]
    annual_costs: Dict[str, float]
    stamp_duty_func: Callable[[float], float]


# =========================
# CORE FINANCE FUNCTIONS
# =========================

def monthly_payment(principal: float, annual_rate: float, term_years: int) -> float:
    r = annual_rate / 100 / 12
    n = term_years * 12
    if r == 0:
        return principal / n
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def amort_table(scenario: Scenario) -> pd.DataFrame:
    principal = scenario.property_price - scenario.deposit
    r = scenario.annual_rate / 100 / 12
    n = scenario.term_years * 12
    pay = monthly_payment(principal, scenario.annual_rate, scenario.term_years)

    rows = []
    balance = principal

    for month_num in range(1, n + 1):
        opening_balance = balance
        interest = opening_balance * r
        principal_paid = pay - interest

        if principal_paid > balance:
            principal_paid = balance
            pay_actual = interest + principal_paid
        else:
            pay_actual = pay

        balance = opening_balance - principal_paid
        year = ((month_num - 1) // 12) + 1
        month_in_year = ((month_num - 1) % 12) + 1

        rows.append({
            "scenario": scenario.name,
            "month_number": month_num,
            "year": year,
            "month_in_year": month_in_year,
            "month_label": f"Y{year}-M{month_in_year:02d}",
            "opening_balance": opening_balance,
            "principal": principal_paid,
            "interest": interest,
            "payment": pay_actual,
            "balance": balance,
        })

        if balance <= 1e-8:
            break

    return pd.DataFrame(rows)


def yearly_from_monthly(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("year", as_index=False)
        .agg({
            "interest": "sum",
            "principal": "sum",
            "payment": "sum",
            "balance": "last"
        })
    )


def build_scenario_objects(scenarios_dict: dict, fees: dict, annual_costs: dict, stamp_duty_func):
    scenario_objects = {}
    for key, cfg in scenarios_dict.items():
        scenario_objects[key] = Scenario(
            key,
            cfg["property_price"],
            cfg["deposit"],
            cfg["annual_rate"],
            cfg["term_years"],
            fees,
            annual_costs,
            stamp_duty_func,
        )
    return scenario_objects


def max_loan_from_target_mortgage_payment(target_mortgage_payment: float, annual_rate: float, term_years: int) -> float:
    r = annual_rate / 100 / 12
    n = term_years * 12
    if r == 0:
        return target_mortgage_payment * n
    return target_mortgage_payment * ((1 + r) ** n - 1) / (r * (1 + r) ** n)


def required_cash_for_target_mortgage_payment(
    scenario_name: str,
    property_price: float,
    annual_rate: float,
    term_years: int,
    target_mortgage_payment: float,
    fees: dict,
    annual_costs: dict,
    stamp_duty_func,
) -> dict:
    max_loan = max_loan_from_target_mortgage_payment(target_mortgage_payment, annual_rate, term_years)
    deposit_required = max(property_price - max_loan, 0.0)
    fees_total = sum(fees.values())
    stamp_duty = stamp_duty_func(property_price)
    monthly_annual_costs = sum(annual_costs.values()) / 12
    total_cash_needed = deposit_required + fees_total + stamp_duty

    result = {
        "scenario": scenario_name,
        "property_price": round(property_price, 2),
        "annual_rate": round(annual_rate, 4),
        "term_years": term_years,
        "target_mortgage_payment": round(target_mortgage_payment, 2),
        "max_loan_supported": round(max_loan, 2),
        "deposit_required": round(deposit_required, 2),
        "fees_total": round(fees_total, 2),
        "stamp_duty": round(stamp_duty, 2),
        "total_cash_needed": round(total_cash_needed, 2),
        "monthly_annual_costs_separate": round(monthly_annual_costs, 2),
    }
    for k, v in fees.items():
        result[f"fee__{k}"] = round(v, 2)
    return result


def build_required_cash_df(target_payment: float, scenarios: dict, fees: dict, annual_costs: dict, stamp_func) -> pd.DataFrame:
    rows = []
    for scenario_name, cfg in scenarios.items():
        rows.append(
            required_cash_for_target_mortgage_payment(
                scenario_name=scenario_name,
                property_price=cfg["property_price"],
                annual_rate=cfg["annual_rate"],
                term_years=cfg["term_years"],
                target_mortgage_payment=target_payment,
                fees=fees,
                annual_costs=annual_costs,
                stamp_duty_func=stamp_func,
            )
        )
    return pd.DataFrame(rows)


def build_required_cash_chart(df_required_cash: pd.DataFrame) -> go.Figure:
    stack_parts = {
        "deposit_required": "Deposit Required",
        "stamp_duty": "Stamp Duty",
        "fee__Solicitor Fees": "Solicitor Fees",
        "fee__Surveyor": "Surveyor",
        "fee__Land Registry Fee": "Land Registry Fee",
        "fee__Valuation Fee": "Valuation Fee",
        "fee__Admin/Arrangement Fee": "Admin/Arrangement Fee",
        "fee__Legal Contribution Fee": "Legal Contribution Fee",
        "fee__Buildings Insurance (Upfront)": "Buildings Insurance (Upfront)",
    }

    fig = go.Figure()
    for col, label in stack_parts.items():
        fig.add_trace(
            go.Bar(
                x=df_required_cash["scenario"],
                y=df_required_cash[col],
                name=label,
                hovertemplate="Scenario: %{x}<br>" + label + ": £%{y:,.0f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Cash Required for £{df_required_cash['target_mortgage_payment'].iloc[0]:,.0f}/mo Mortgage",
        barmode="stack",
        template="plotly_white",
        xaxis_title="Scenario",
        yaxis_title="Cash Required (£)",
        height=440,
        legend=dict(orientation="h", y=-0.26, x=0, font=dict(size=10)),
        margin=dict(t=60, l=10, r=10, b=110),
    )

    for _, row in df_required_cash.iterrows():
        fig.add_annotation(
            x=row["scenario"],
            y=row["total_cash_needed"],
            text=f"£{row['total_cash_needed']:,.0f}",
            showarrow=False,
            yshift=12,
        )

    return fig


def build_amortisation_drilldown_chart(df_monthly: pd.DataFrame, scenario_title: str) -> go.Figure:
    df_yearly = yearly_from_monthly(df_monthly).copy()
    years = sorted(df_monthly["year"].unique())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_yearly["year"], y=df_yearly["principal"], name="Principal (Yearly)", visible=True,
        hovertemplate="Year %{x}<br>Principal: £%{y:,.2f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=df_yearly["year"], y=df_yearly["interest"], name="Interest (Yearly)", visible=True,
        hovertemplate="Year %{x}<br>Interest: £%{y:,.2f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=df_yearly["year"], y=df_yearly["balance"], name="Balance (Yearly)", mode="lines+markers",
        visible=True, yaxis="y2",
        hovertemplate="Year %{x}<br>Balance: £%{y:,.2f}<extra></extra>"
    ))

    for yr in years:
        sub = df_monthly[df_monthly["year"] == yr].copy()
        fig.add_trace(go.Bar(
            x=sub["month_in_year"], y=sub["principal"], name=f"Principal Y{yr}", visible=False,
            hovertemplate=f"Year {yr} Month %{{x}}<br>Principal: £%{{y:,.2f}}<extra></extra>"
        ))
        fig.add_trace(go.Bar(
            x=sub["month_in_year"], y=sub["interest"], name=f"Interest Y{yr}", visible=False,
            hovertemplate=f"Year {yr} Month %{{x}}<br>Interest: £%{{y:,.2f}}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=sub["month_in_year"], y=sub["balance"], name=f"Balance Y{yr}", mode="lines+markers",
            visible=False, yaxis="y2",
            hovertemplate=f"Year {yr} Month %{{x}}<br>Balance: £%{{y:,.2f}}<extra></extra>"
        ))

    total_traces = 3 + len(years) * 3
    buttons = []
    yearly_visible = [True, True, True] + [False] * (total_traces - 3)
    buttons.append(dict(
        label="Yearly Overview",
        method="update",
        args=[
            {"visible": yearly_visible},
            {"title": f"{scenario_title} · Principal, Interest and Balance", "xaxis.title": "Year", "barmode": "group"}
        ]
    ))

    for i, yr in enumerate(years):
        visible = [False] * total_traces
        start = 3 + i * 3
        visible[start:start+3] = [True, True, True]
        buttons.append(dict(
            label=f"Monthly: Year {yr}",
            method="update",
            args=[
                {"visible": visible},
                {"title": f"{scenario_title} · Monthly Drilldown for Year {yr}", "xaxis.title": f"Month in Year {yr}", "barmode": "group"}
            ]
        ))

    fig.update_layout(
        title=f"{scenario_title} · Principal, Interest and Balance",
        template="plotly_white",
        barmode="group",
        updatemenus=[dict(buttons=buttons, direction="down", x=0, xanchor="left", y=1.12, yanchor="top")],
        xaxis=dict(title="Year", tickangle=0),
        yaxis=dict(title="Principal / Interest (£)"),
        yaxis2=dict(title="Balance (£)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=-0.24, x=0, font=dict(size=10)),
        height=440,
        margin=dict(t=95, l=10, r=10, b=105),
    )
    return fig


def build_5yr_comparison(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    y1 = yearly_from_monthly(df1).copy()
    y2 = yearly_from_monthly(df2).copy()
    years = pd.DataFrame({"year": range(1, 26)})
    y1 = years.merge(y1, on="year", how="left").fillna(0)
    y2 = years.merge(y2, on="year", how="left").fillna(0)

    rows = []
    for start_year in [1, 6, 11, 16, 21]:
        end_year = start_year + 4
        sub1 = y1[(y1["year"] >= start_year) & (y1["year"] <= end_year)]
        sub2 = y2[(y2["year"] >= start_year) & (y2["year"] <= end_year)]
        extra_interest_35_vs_25 = sub2["interest"].sum() - sub1["interest"].sum()
        extra_principal_25_vs_35 = sub1["principal"].sum() - sub2["principal"].sum()
        rows.append({
            "period": f"Years {start_year}-{end_year}",
            "total_extra_interest_35_vs_25": extra_interest_35_vs_25,
            "total_extra_principal_25_vs_35": extra_principal_25_vs_35,
            "avg_extra_interest_per_month": extra_interest_35_vs_25 / 60,
            "avg_extra_principal_per_month": extra_principal_25_vs_35 / 60,
        })
    return pd.DataFrame(rows)


def build_5yr_chart(compare_5yr: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=compare_5yr["period"],
        y=compare_5yr["total_extra_interest_35_vs_25"],
        name="Total Extra Interest (35Y vs 25Y)",
        visible=True,
        hovertemplate="%{x}<br>Total extra interest: £%{y:,.2f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=compare_5yr["period"],
        y=compare_5yr["total_extra_principal_25_vs_35"],
        name="Total Extra Principal (25Y vs 35Y)",
        visible=True,
        hovertemplate="%{x}<br>Total extra principal: £%{y:,.2f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=compare_5yr["period"],
        y=compare_5yr["avg_extra_interest_per_month"],
        name="Avg Extra Interest / Month",
        visible=False,
        hovertemplate="%{x}<br>Avg extra interest / month: £%{y:,.2f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=compare_5yr["period"],
        y=compare_5yr["avg_extra_principal_per_month"],
        name="Avg Extra Principal / Month",
        visible=False,
        hovertemplate="%{x}<br>Avg extra principal / month: £%{y:,.2f}<extra></extra>"
    ))

    buttons = [
        dict(
            label="Totals by 5-Year Period",
            method="update",
            args=[
                {"visible": [True, True, False, False]},
                {"title": "5-Year Totals · Extra Interest and Extra Principal", "yaxis.title": "£ Total over 5-Year Period", "barmode": "group"}
            ]
        ),
        dict(
            label="Monthly Averages by 5-Year Period",
            method="update",
            args=[
                {"visible": [False, False, True, True]},
                {"title": "5-Year Monthly Averages · Extra Interest and Extra Principal", "yaxis.title": "£ per Month", "barmode": "group"}
            ]
        )
    ]

    fig.update_layout(
        title="5-Year Totals · Extra Interest and Extra Principal",
        template="plotly_white",
        barmode="group",
        updatemenus=[dict(buttons=buttons, direction="down", x=0, xanchor="left", y=1.12, yanchor="top")],
        xaxis_title="5-Year Interval",
        yaxis_title="£ Total over 5-Year Period",
        height=430,
        legend=dict(orientation="h", y=-0.24, x=0, font=dict(size=10)),
        margin=dict(t=95, l=10, r=10, b=105),
    )
    return fig


# =========================
# STREAMLIT UI
# =========================

st.title("Welcome to Mortgage Roulette")
st.markdown('<div class="subtle">A mortgage comparison workspace for testing payment targets, upfront cash requirements, and amortisation trade-offs.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Inputs")
    property_price = st.number_input("Property price (£)", min_value=0, value=0, step=5000, placeholder="Enter property price")
    deposit = st.number_input("Deposit (£)", min_value=0, value=150000, step=5000)
    annual_rate = st.number_input("Annual rate (%)", min_value=0.0, value=6.15, step=0.05)
    target_payment = st.number_input("Target monthly mortgage payment (£)", min_value=0, value=1500, step=25)

    st.divider()
    st.subheader("Fees")
    solicitor_fee = st.number_input("Solicitor fees (£)", min_value=0, value=2000, step=50)
    surveyor_fee = st.number_input("Surveyor (£)", min_value=0, value=1200, step=50)
    land_registry_fee = st.number_input("Land Registry fee (£)", min_value=0, value=150, step=25)
    valuation_fee = st.number_input("Valuation fee (£)", min_value=0, value=300, step=25)
    admin_fee = st.number_input("Admin/arrangement fee (£)", min_value=0, value=300, step=25)
    legal_contribution_fee = st.number_input("Legal contribution fee (£)", min_value=0, value=350, step=25)
    insurance_upfront = st.number_input("Buildings insurance upfront (£)", min_value=0, value=200, step=25)
    insurance_annual = st.number_input("Buildings insurance annual (£)", min_value=0, value=200, step=25)

    st.divider()
    stamp_mode = st.selectbox("Stamp duty mode", ["First-time buyer", "Standard"])

if property_price == 0:
    st.info("Enter a property price in the sidebar to begin.")
    st.stop()

fees = {
    "Solicitor Fees": float(solicitor_fee),
    "Surveyor": float(surveyor_fee),
    "Land Registry Fee": float(land_registry_fee),
    "Valuation Fee": float(valuation_fee),
    "Admin/Arrangement Fee": float(admin_fee),
    "Legal Contribution Fee": float(legal_contribution_fee),
    "Buildings Insurance (Upfront)": float(insurance_upfront),
}
annual_costs = {"Buildings Insurance (Annual)": float(insurance_annual)}
stamp_func = england_stamp_duty_ftb if stamp_mode == "First-time buyer" else england_stamp_duty_standard

scenarios = {
    "25Y": {"label": "25-Year Scenario", "property_price": float(property_price), "deposit": float(deposit), "annual_rate": float(annual_rate), "term_years": 25},
    "35Y": {"label": "35-Year Scenario", "property_price": float(property_price), "deposit": float(deposit), "annual_rate": float(annual_rate), "term_years": 35},
}

# Build data
required_cash_df = build_required_cash_df(target_payment, scenarios, fees, annual_costs, stamp_func)
scenario_objects = build_scenario_objects(scenarios, fees, annual_costs, stamp_func)
df1 = amort_table(scenario_objects["25Y"])
df2 = amort_table(scenario_objects["35Y"])
compare_5yr = build_5yr_comparison(df1, df2)

# Header metrics
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Property price", f"£{property_price:,.0f}")
with c2:
    st.metric("Deposit", f"£{deposit:,.0f}")
with c3:
    st.metric("Annual rate", f"{annual_rate:.2f}%")
with c4:
    st.metric("Target mortgage", f"£{target_payment:,.0f}/mo")

cash_tab, amort_tab, strategy_tab = st.tabs(["Cash Required", "Amortisation", "5-Year Strategy"])

with cash_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Required cash to hit target payment")
    st.markdown('<div class="subtle">For the selected property price and mortgage target, this shows the upfront cash mix needed across the 25-year and 35-year structures.</div>', unsafe_allow_html=True)
    render_chart_with_actions(build_required_cash_chart(required_cash_df), 'cash_required', 'Cash Required')
    with st.expander('Show cash summary table'):
        st.dataframe(required_cash_df, use_container_width=True, height=260)
    st.markdown('</div>', unsafe_allow_html=True)

with amort_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("25-year amortisation")
    st.markdown('<div class="subtle">Use the chart menu to switch between yearly overview and monthly drilldown. PNG download, HTML download, and chart JSON copy are available below.</div>', unsafe_allow_html=True)
    render_chart_with_actions(
        build_amortisation_drilldown_chart(df1, scenarios["25Y"]["label"]),
        'amort_25',
        '25-Year Amortisation'
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("35-year amortisation")
    st.markdown('<div class="subtle">Use the chart menu to switch between yearly overview and monthly drilldown. PNG download, HTML download, and chart JSON copy are available below.</div>', unsafe_allow_html=True)
    render_chart_with_actions(
        build_amortisation_drilldown_chart(df2, scenarios["35Y"]["label"]),
        'amort_35',
        '35-Year Amortisation'
    )
    st.markdown('</div>', unsafe_allow_html=True)

with strategy_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison")
    st.markdown('<div class="subtle">Toggle between total impact by 5-year block and the monthly average cost of delaying debt.</div>', unsafe_allow_html=True)
    render_chart_with_actions(build_5yr_chart(compare_5yr), 'strategy_5yr', '5-Year Strategy')
    with st.expander('Show 5-year comparison table'):
        st.dataframe(compare_5yr.round(2), use_container_width=True, height=240)
    st.markdown('</div>', unsafe_allow_html=True)
