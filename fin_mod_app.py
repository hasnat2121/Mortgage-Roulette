import math
from dataclasses import dataclass
from typing import Callable, Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Mortgage Roulette", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.4rem;
        max-width: 1280px;
    }
    h1, h2, h3 { letter-spacing: -0.02em; }
    .subtle {
        color: #6b7280;
        font-size: 0.95rem;
        line-height: 1.45;
    }
    .section-card {
        padding: 0.9rem 1rem;
        border: 1px solid rgba(49,51,63,0.12);
        border-radius: 12px;
        background: rgba(250,250,252,0.72);
        margin-bottom: 0.9rem;
    }
    .scenario-summary {
        padding: 0.85rem 0.95rem;
        border: 1px solid rgba(49,51,63,0.12);
        border-radius: 12px;
        background: #fff;
        height: 100%;
    }
    .scenario-summary h4 {
        margin: 0 0 0.55rem 0;
        font-size: 1rem;
    }
    .scenario-kv {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 0.25rem 0.75rem;
        font-size: 0.92rem;
    }
    .scenario-kv div:nth-child(odd) { color: #6b7280; }
    .scenario-kv div:nth-child(even) { font-weight: 600; }
    [data-testid="stMetricValue"] { font-size: 1.45rem; }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.7rem;
            padding-bottom: 1rem;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        h1 { font-size: 1.6rem; }
        h2 { font-size: 1.15rem; }
        .subtle { font-size: 0.87rem; }
        .section-card, .scenario-summary {
            padding: 0.75rem 0.8rem;
            border-radius: 10px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# HELPERS
# =========================

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
            "toImageButtonOptions": {
                "format": "png",
                "filename": chart_key,
                "scale": 2,
            },
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

    st.caption("Use the chart modebar for PNG download. HTML and JSON options are below.")


def fmt_gbp(x: float) -> str:
    return f"£{x:,.0f}"

# Fixed deposit assumption used for like-for-like amortisation and strategy comparisons
BASE_COMPARISON_DEPOSIT = 150000.0


# =========================
# STAMP DUTY
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
# CORE FINANCE
# =========================

def monthly_payment(principal: float, annual_rate: float, term_years: int) -> float:
    r = annual_rate / 100 / 12
    n = term_years * 12
    if r == 0:
        return principal / n
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


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
    total_cash_needed = deposit_required + fees_total + stamp_duty
    monthly_annual_costs = sum(annual_costs.values()) / 12
    ftv_pct = (max_loan / property_price * 100) if property_price > 0 else 0.0

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
        "ftv_pct": round(ftv_pct, 2),
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
    df = pd.DataFrame(rows)
    order = ["25Y", "35Y", "40Y"]
    df["scenario"] = pd.Categorical(df["scenario"], categories=order, ordered=True)
    return df.sort_values("scenario").reset_index(drop=True)


def build_scenario_objects_from_required_cash(required_cash_df: pd.DataFrame, fees: dict, annual_costs: dict, stamp_duty_func) -> dict:
    scenario_objects = {}
    for _, row in required_cash_df.iterrows():
        scenario_objects[row["scenario"]] = Scenario(
            row["scenario"],
            float(row["property_price"]),
            float(row["deposit_required"]),
            float(row["annual_rate"]),
            int(row["term_years"]),
            fees,
            annual_costs,
            stamp_duty_func,
        )
    return scenario_objects


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
            "balance": "last",
        })
    )


# =========================
# CHARTS
# =========================

def build_required_cash_chart(df_required_cash: pd.DataFrame) -> go.Figure:
    stack_parts = {
        "deposit_required": "Deposit",
        "stamp_duty": "Stamp Duty",
        "fee__Solicitor Fees": "Solicitor Fees",
        "fee__Surveyor": "Surveyor",
        "fee__Land Registry Fee": "Land Registry Fee",
        "fee__Valuation Fee": "Valuation Fee",
        "fee__Admin/Arrangement Fee": "Admin / Arrangement Fee",
        "fee__Legal Contribution Fee": "Legal Contribution Fee",
        "fee__Buildings Insurance (Upfront)": "Buildings Insurance (Upfront)",
    }

    fig = go.Figure()
    for col, label in stack_parts.items():
        fig.add_trace(go.Bar(
            x=df_required_cash["scenario"],
            y=df_required_cash[col],
            name=label,
            hovertemplate="Scenario: %{x}<br>" + label + ": £%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title=f"Cash Required for £{df_required_cash['target_mortgage_payment'].iloc[0]:,.0f}/mo Mortgage",
        barmode="stack",
        template="plotly_white",
        xaxis_title="Scenario",
        yaxis_title="Cash Required (£)",
        height=500,
        legend=dict(orientation="h", y=-0.28, x=0, font=dict(size=10)),
        margin=dict(t=60, l=10, r=10, b=120),
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
        xaxis=dict(title="Year"),
        yaxis=dict(title="Principal / Interest (£)"),
        yaxis2=dict(title="Balance (£)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=-0.24, x=0, font=dict(size=10)),
        height=460,
        margin=dict(t=95, l=10, r=10, b=105),
    )
    return fig


def build_5yr_comparison_against_base(df_base: pd.DataFrame, df_compare: pd.DataFrame, compare_label: str) -> pd.DataFrame:
    y_base = yearly_from_monthly(df_base).copy()
    y_cmp = yearly_from_monthly(df_compare).copy()
    years = pd.DataFrame({"year": range(1, 26)})
    y_base = years.merge(y_base, on="year", how="left").fillna(0)
    y_cmp = years.merge(y_cmp, on="year", how="left").fillna(0)

    rows = []
    for start_year in [1, 6, 11, 16, 21]:
        end_year = start_year + 4
        sub_base = y_base[(y_base["year"] >= start_year) & (y_base["year"] <= end_year)]
        sub_cmp = y_cmp[(y_cmp["year"] >= start_year) & (y_cmp["year"] <= end_year)]
        extra_interest = sub_cmp["interest"].sum() - sub_base["interest"].sum()
        extra_principal = sub_base["principal"].sum() - sub_cmp["principal"].sum()
        rows.append({
            "comparison": compare_label,
            "period": f"Years {start_year}-{end_year}",
            "total_extra_interest": extra_interest,
            "total_extra_principal": extra_principal,
            "avg_extra_interest_per_month": extra_interest / 60,
            "avg_extra_principal_per_month": extra_principal / 60,
        })
    return pd.DataFrame(rows)


def build_strategy_chart(compare_df: pd.DataFrame, title_prefix: str) -> go.Figure:
    fig = go.Figure()
    comparisons = compare_df["comparison"].unique().tolist()

    # totals view
    for comp in comparisons:
        sub = compare_df[compare_df["comparison"] == comp]
        fig.add_trace(go.Bar(
            x=sub["period"],
            y=sub["total_extra_interest"],
            name=f"{comp} · Extra Interest",
            visible=True,
            text=[f"£{v:,.0f}" for v in sub["total_extra_interest"]],
            textposition="outside",
            hovertemplate="%{x}<br>" + comp + " extra interest: £%{y:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=sub["period"],
            y=sub["total_extra_principal"],
            name=f"{comp} · Extra Principal",
            visible=True,
            text=[f"£{v:,.0f}" for v in sub["total_extra_principal"]],
            textposition="outside",
            hovertemplate="%{x}<br>" + comp + " extra principal: £%{y:,.2f}<extra></extra>",
        ))

    # monthly averages view
    for comp in comparisons:
        sub = compare_df[compare_df["comparison"] == comp]
        fig.add_trace(go.Bar(
            x=sub["period"],
            y=sub["avg_extra_interest_per_month"],
            name=f"{comp} · Avg Interest / Month",
            visible=False,
            text=[f"£{v:,.0f}" for v in sub["avg_extra_interest_per_month"]],
            textposition="outside",
            hovertemplate="%{x}<br>" + comp + " avg interest / month: £%{y:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=sub["period"],
            y=sub["avg_extra_principal_per_month"],
            name=f"{comp} · Avg Principal / Month",
            visible=False,
            text=[f"£{v:,.0f}" for v in sub["avg_extra_principal_per_month"]],
            textposition="outside",
            hovertemplate="%{x}<br>" + comp + " avg principal / month: £%{y:,.2f}<extra></extra>",
        ))

    n = len(comparisons) * 2
    buttons = [
        dict(
            label="Totals by 5-Year Period",
            method="update",
            args=[
                {"visible": [True] * n + [False] * n},
                {"title": f"{title_prefix} · Totals by 5-Year Period", "yaxis.title": "£ Total over 5-Year Period", "barmode": "group"}
            ]
        ),
        dict(
            label="Monthly Averages by 5-Year Period",
            method="update",
            args=[
                {"visible": [False] * n + [True] * n},
                {"title": f"{title_prefix} · Monthly Averages by 5-Year Period", "yaxis.title": "£ per Month", "barmode": "group"}
            ]
        ),
    ]

    fig.update_layout(
        title=f"{title_prefix} · Totals by 5-Year Period",
        template="plotly_white",
        barmode="group",
        updatemenus=[dict(buttons=buttons, direction="down", x=0, xanchor="left", y=1.14, yanchor="top")],
        xaxis_title="5-Year Interval",
        yaxis_title="£ Total over 5-Year Period",
        height=500,
        legend=dict(orientation="h", y=-0.3, x=0, font=dict(size=10)),
        margin=dict(t=95, l=10, r=10, b=120),
    )
    return fig


# =========================
# UI
# =========================

st.title("Welcome to Mortgage Roulette")
st.markdown(
    '<div class="subtle">A mortgage comparison workspace for testing payment targets, upfront cash requirements, and amortisation trade-offs.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Inputs")
    property_price = st.number_input("Property price (£)", min_value=0, value=0, step=5000, placeholder="Enter property price")
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

base_scenarios = {
    "25Y": {"label": "25-Year Scenario", "property_price": float(property_price), "annual_rate": float(annual_rate), "term_years": 25},
    "35Y": {"label": "35-Year Scenario", "property_price": float(property_price), "annual_rate": float(annual_rate), "term_years": 35},
    "40Y": {"label": "40-Year Scenario", "property_price": float(property_price), "annual_rate": float(annual_rate), "term_years": 40},
}

required_cash_df = build_required_cash_df(target_payment, base_scenarios, fees, annual_costs, stamp_func)

# Fixed-deposit scenarios for like-for-like amortisation and strategy comparisons
comparison_scenarios = {
    key: Scenario(
        key,
        float(cfg["property_price"]),
        float(BASE_COMPARISON_DEPOSIT),
        float(cfg["annual_rate"]),
        int(cfg["term_years"]),
        fees,
        annual_costs,
        stamp_func,
    )
    for key, cfg in base_scenarios.items()
}

# build amortisation data on the same deposit basis across terms
amort_tables = {k: amort_table(v) for k, v in comparison_scenarios.items()}
compare_35_vs_25 = build_5yr_comparison_against_base(amort_tables["25Y"], amort_tables["35Y"], "35Y vs 25Y")
compare_40_vs_25 = build_5yr_comparison_against_base(amort_tables["25Y"], amort_tables["40Y"], "40Y vs 25Y")
compare_against_25 = pd.concat([compare_35_vs_25, compare_40_vs_25], ignore_index=True)

compare_40_vs_35 = build_5yr_comparison_against_base(amort_tables["35Y"], amort_tables["40Y"], "40Y vs 35Y")

# top metrics row
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Property price", fmt_gbp(property_price))
with m2:
    st.metric("Annual rate", f"{annual_rate:.2f}%")
with m3:
    st.metric("Target mortgage", f"£{target_payment:,.0f}/mo")
with m4:
    st.metric("Stamp duty mode", "FTB" if stamp_mode == "First-time buyer" else "Standard")

st.markdown("<div style='height:0.35rem'></div>", unsafe_allow_html=True)
summary_cols = st.columns(3)
for col, (_, row) in zip(summary_cols, required_cash_df.iterrows()):
    with col:
        st.markdown(
            f"""
            <div class="scenario-summary">
                <h4>{row['scenario']}</h4>
                <div class="scenario-kv">
                    <div>Cash Required</div><div>{fmt_gbp(row['total_cash_needed'])}</div>
                    <div>Deposit</div><div>{fmt_gbp(row['deposit_required'])}</div>
                    <div>Fees</div><div>{fmt_gbp(row['fees_total'])}</div>
                    <div>Stamp Duty</div><div>{fmt_gbp(row['stamp_duty'])}</div>
                    <div>FTV %</div><div>{row['ftv_pct']:.1f}%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

cash_tab, amort_tab, strategy_tab = st.tabs(["Cash Required", "Amortisation", "5-Year Strategy"])

with cash_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Required cash to hit target payment")
    st.markdown('<div class="subtle">For the selected property price and mortgage target, this shows the upfront cash mix needed across the 25-year, 35-year and 40-year structures.</div>', unsafe_allow_html=True)
    render_chart_with_actions(build_required_cash_chart(required_cash_df), "cash_required", "Cash Required")
    with st.expander("Show cash summary table"):
        st.dataframe(required_cash_df, use_container_width=True, height=300)
    st.markdown('</div>', unsafe_allow_html=True)

with amort_tab:
    for key in ["25Y", "35Y", "40Y"]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader(base_scenarios[key]["label"].replace("Scenario", "amortisation"))
        st.markdown(f'<div class="subtle">Use the chart menu to switch between yearly overview and monthly drilldown. Charts use a fixed like-for-like comparison deposit of {fmt_gbp(BASE_COMPARISON_DEPOSIT)}. PNG download, HTML download, and chart JSON copy are available below.</div>', unsafe_allow_html=True)
        render_chart_with_actions(
            build_amortisation_drilldown_chart(amort_tables[key], base_scenarios[key]["label"]),
            f"amort_{key.lower()}",
            f"{key} Amortisation",
        )
        st.markdown('</div>', unsafe_allow_html=True)

with strategy_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison · anchored to 25-year")
    st.markdown(f'<div class="subtle">This compares 35Y vs 25Y and 40Y vs 25Y using a fixed comparison deposit of {fmt_gbp(BASE_COMPARISON_DEPOSIT)}. Extra interest means the longer plan paid more interest; extra principal means the shorter plan paid down more principal over the same 5-year block. Use the menu to switch between totals and monthly averages.</div>', unsafe_allow_html=True)
    render_chart_with_actions(
        build_strategy_chart(compare_against_25, "Anchored to 25-Year"),
        "strategy_5yr_anchor_25",
        "5-Year Strategy vs 25-Year",
    )
    with st.expander("Show anchored-to-25 comparison table"):
        st.dataframe(compare_against_25.round(2), use_container_width=True, height=300)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison · anchored to 35-year")
    st.markdown(f'<div class="subtle">This compares 40Y vs 35Y using a fixed comparison deposit of {fmt_gbp(BASE_COMPARISON_DEPOSIT)}. Extra interest means the 40Y plan paid more interest; extra principal means the 35Y plan paid down more principal over the same 5-year block. Use the menu to switch between totals and monthly averages.</div>', unsafe_allow_html=True)
    render_chart_with_actions(
        build_strategy_chart(compare_40_vs_35, "Anchored to 35-Year"),
        "strategy_5yr_anchor_35",
        "5-Year Strategy vs 35-Year",
    )
    with st.expander("Show anchored-to-35 comparison table"):
        st.dataframe(compare_40_vs_35.round(2), use_container_width=True, height=260)
    st.markdown('</div>', unsafe_allow_html=True)
