import math
from dataclasses import dataclass
from typing import Callable, Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Mortgage Roulette", layout="wide", initial_sidebar_state="collapsed")

# Hidden anchor for top of page
st.markdown('<div id="home"></div>', unsafe_allow_html=True)

# Mobile viewport
components.html(
    """
    <script>
    const meta = document.createElement('meta');
    meta.name = 'viewport';
    meta.content = 'width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover, user-scalable=no';
    document.head.appendChild(meta);
    </script>
    """,
    height=0,
)

# App-wide CSS
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.4rem;
        max-width: 1280px;
    }
    html, body, [data-testid="stAppViewContainer"], .main {
        overflow-x: hidden;
        width: 100%;
    }
    h1, h2, h3 { letter-spacing: -0.02em; }
    .subtle {
        color: #6b7280;
        font-size: 0.95rem;
        line-height: 1.45;
    }
    .section-card {
        padding: 0.5rem 0 0 0;
        border-top: 1px solid rgba(49,51,63,0.12);
        border-radius: 0;
        background: transparent;
        margin: 0.75rem 0;
    }
    .scenario-summary {
        padding: 0.85rem 0.95rem;
        border: 1px solid rgba(49,51,63,0.12);
        border-radius: 12px;
        background: rgba(255,255,255,0.9);
        color: #111827;
        height: 100%;
    }
    .scenario-summary h4 {
        margin: 0 0 0.55rem 0;
        font-size: 1rem;
        color: #111827;
    }
    .scenario-kv {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 0.25rem 0.75rem;
        font-size: 0.92rem;
    }
    .scenario-kv div:nth-child(odd) { color: #4b5563; }
    .scenario-kv div:nth-child(even) { font-weight: 600; color: #111827; }
    @media (prefers-color-scheme: dark) {
        .scenario-summary {
            background: rgba(17,24,39,0.92);
            border-color: rgba(255,255,255,0.14);
            color: #f3f4f6;
        }
        .scenario-summary h4 { color: #f9fafb; }
        .scenario-kv div:nth-child(odd) { color: #d1d5db; }
        .scenario-kv div:nth-child(even) { color: #f9fafb; }
    }
    [data-testid="stMetricValue"] { font-size: 1.45rem; }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.8rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.7rem !important;
            padding-right: 0.7rem !important;
            max-width: 100% !important;
        }
        h1 { font-size: 1.6rem !important; line-height: 1.15 !important; }
        h2 { font-size: 1.2rem !important; line-height: 1.2 !important; }
        h3 { font-size: 1.05rem !important; line-height: 1.2 !important; }
        button, input, select, textarea, [data-baseweb="select"] {
            font-size: 16px !important;
        }
        .section-card, .scenario-summary {
            padding: 0.75rem 0.8rem !important;
            border-radius: 10px !important;
        }
        .subtle {
            font-size: 0.9rem !important;
        }
        [data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;
        }
    }

    div[data-testid="stPopover"] > div > button {
        transform: scale(0.7);
        transform-origin: top right;
        min-height: 0 !important;
        padding: 0.1rem 0.25rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# HELPERS
# =========================

def render_chart_with_actions(fig: go.Figure, chart_key: str, title: str):
    fig.update_layout(
        autosize=True,
        margin=dict(l=10, r=10, t=40, b=40),
        legend=dict(orientation="h", y=-0.2, x=0, xanchor="left"),
    )
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


def render_required_cash_summary_cards(required_cash_df: pd.DataFrame) -> None:
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


def render_strategy_summary_cards(strategy_tables: dict, property_price: float, fees: dict, stamp_func: Callable[[float], float]) -> None:
    total_fees = sum(fees.values())
    stamp_duty = stamp_func(property_price)
    cols = st.columns(3)
    for col, key in zip(cols, ["25Y", "35Y", "40Y"]):
        df = strategy_tables[key]
        loan_amount = float(df["opening_balance"].iloc[0]) if len(df) else 0.0
        monthly_payment_val = float(df["payment"].iloc[0]) if len(df) else 0.0
        total_principal = float(df["principal"].sum()) if len(df) else 0.0
        total_interest = float(df["interest"].sum()) if len(df) else 0.0
        deposit_amount = max(property_price - loan_amount, 0.0)
        cash_required = deposit_amount + total_fees + stamp_duty
        ftv_pct = (loan_amount / property_price * 100) if property_price > 0 else 0.0
        with col:
            st.markdown(
                f"""
                <div class="scenario-summary">
                    <h4>{key}</h4>
                    <div class="scenario-kv">
                        <div>Monthly Mortgage Payment</div><div>{fmt_gbp(monthly_payment_val)}/mo</div>
                        <div>FTV %</div><div>{ftv_pct:.1f}%</div>
                        <div>Total Principal</div><div>{fmt_gbp(total_principal)}</div>
                        <div>Total Interest</div><div>{fmt_gbp(total_interest)}</div>
                        <div>Fees</div><div>{fmt_gbp(total_fees)}</div>
                        <div>Stamp Duty</div><div>{fmt_gbp(stamp_duty)}</div>
                        <div>Cash Required</div><div>{fmt_gbp(cash_required)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

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




def build_lump_payment_summary(input_df: pd.DataFrame, custom_df: pd.DataFrame, max_year: int) -> pd.DataFrame:
    """
    Returns a display table for lump sums with added columns:
    Fee (£) and Updated Monthly Mortgage (£) based on the recalculated
    payment at the start of the chosen year.
    """
    if input_df is None or len(input_df) == 0:
        return pd.DataFrame(columns=["Year", "Amount", "Fee", "Updated Monthly Mortgage (£)"])

    out = pd.DataFrame(input_df).copy()
    cols = {c.lower(): c for c in out.columns}
    year_col = cols.get("year")
    amount_col = cols.get("amount")
    fee_col = cols.get("fee")
    if year_col is None:
        return pd.DataFrame(columns=["Year", "Amount", "Fee", "Updated Monthly Mortgage (£)"])

    rename_map = {year_col: "Year"}
    if amount_col is not None:
        rename_map[amount_col] = "Amount"
    if fee_col is not None:
        rename_map[fee_col] = "Fee"

    out = out[list(rename_map)].rename(columns=rename_map)
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["Amount"] = pd.to_numeric(out.get("Amount", 0.0), errors="coerce").fillna(0.0)
    out["Fee"] = pd.to_numeric(out.get("Fee", 0.0), errors="coerce").fillna(0.0)
    out = out.dropna(subset=["Year"])
    out["Year"] = out["Year"].astype(int)
    out = out[(out["Year"] >= 1) & (out["Year"] <= max_year) & ((out["Amount"] > 0) | (out["Fee"] > 0))].copy()

    def _payment_for_year_start(year_val: int) -> float:
        month_num = (int(year_val) - 1) * 12 + 1
        sub = custom_df[custom_df["month_number"] == month_num]
        if len(sub):
            return float(sub["payment"].iloc[0])
        return float("nan")

    out["Updated Monthly Mortgage (£)"] = out["Year"].apply(_payment_for_year_start)
    return out.reset_index(drop=True)


def build_amortisation_chart(df_monthly: pd.DataFrame, scenario_title: str, selected_view: str = "Overview") -> go.Figure:
    df_yearly = yearly_from_monthly(df_monthly).copy()

    if selected_view == "Overview":
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_yearly["year"], y=df_yearly["principal"], name="Principal",
            hovertemplate="Year %{x}<br>Principal: £%{y:,.2f}<extra></extra>"
        ))
        fig.add_trace(go.Bar(
            x=df_yearly["year"], y=df_yearly["interest"], name="Interest",
            hovertemplate="Year %{x}<br>Interest: £%{y:,.2f}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=df_yearly["year"], y=df_yearly["balance"], name="Balance",
            mode="lines+markers", yaxis="y2",
            hovertemplate="Year %{x}<br>Balance: £%{y:,.2f}<extra></extra>"
        ))
        title = f"{scenario_title} · Principal, Interest and Balance"
        xaxis_title = "Year"
    else:
        year_num = int(selected_view.replace("Year ", ""))
        sub = df_monthly[df_monthly["year"] == year_num].copy()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=sub["month_in_year"], y=sub["principal"], name="Principal",
            hovertemplate=f"Year {year_num} Month %{{x}}<br>Principal: £%{{y:,.2f}}<extra></extra>"
        ))
        fig.add_trace(go.Bar(
            x=sub["month_in_year"], y=sub["interest"], name="Interest",
            hovertemplate=f"Year {year_num} Month %{{x}}<br>Interest: £%{{y:,.2f}}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=sub["month_in_year"], y=sub["balance"], name="Balance",
            mode="lines+markers", yaxis="y2",
            hovertemplate=f"Year {year_num} Month %{{x}}<br>Balance: £%{{y:,.2f}}<extra></extra>"
        ))
        title = f"{scenario_title} · Monthly Drilldown for Year {year_num}"
        xaxis_title = f"Month in Year {year_num}"

    fig.update_layout(
        title=title,
        template="plotly_white",
        barmode="group",
        xaxis=dict(title=xaxis_title),
        yaxis=dict(title="Principal / Interest difference (£)"),
        yaxis2=dict(title="Balance difference (£)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=-0.24, x=0, font=dict(size=10)),
        height=460,
        margin=dict(t=80, l=10, r=10, b=105),
    )
    return fig


def build_amortisation_difference_chart(
    df_25y: pd.DataFrame,
    df_35y: pd.DataFrame,
    title_prefix: str,
    selected_view: str = "Overview",
) -> go.Figure:
    df25y = df_25y.copy()
    df35y = df_35y.copy()

    df25y_yearly = yearly_from_monthly(df25y).copy().rename(columns={
        "principal": "principal_25",
        "interest": "interest_25",
        "balance": "balance_25",
    })
    df35y_yearly = yearly_from_monthly(df35y).copy().rename(columns={
        "principal": "principal_35",
        "interest": "interest_35",
        "balance": "balance_35",
    })
    df_yearly = df25y_yearly.merge(
        df35y_yearly[["year", "principal_35", "interest_35", "balance_35"]],
        on="year",
        how="inner",
    )
    df_yearly["principal_diff"] = df_yearly["principal_25"] - df_yearly["principal_35"]
    df_yearly["interest_diff"] = df_yearly["interest_35"] - df_yearly["interest_25"]
    df_yearly["balance_diff"] = df_yearly["balance_35"] - df_yearly["balance_25"]

    if selected_view == "Overview":
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_yearly["year"], y=df_yearly["principal_diff"],
            name="25Y - 35Y Principal",
            hovertemplate="Year %{x}<br>25Y - 35Y Principal: £%{y:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=df_yearly["year"], y=df_yearly["interest_diff"],
            name="35Y - 25Y Interest",
            hovertemplate="Year %{x}<br>35Y - 25Y Interest: £%{y:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df_yearly["year"], y=df_yearly["balance_diff"],
            name="Balance difference (35Y - 25Y)",
            mode="lines+markers",
            yaxis="y2",
            hovertemplate="Year %{x}<br>Balance gap: £%{y:,.2f}<extra></extra>",
        ))
        title = f"{title_prefix} · Yearly amortisation difference"
        xaxis_title = "Year"
    else:
        year_num = int(selected_view.replace("Year ", ""))
        df25y_monthly = df25y[df25y["year"] == year_num].copy().rename(columns={
            "principal": "principal_25",
            "interest": "interest_25",
            "balance": "balance_25",
        })
        df35y_monthly = df35y[df35y["year"] == year_num].copy().rename(columns={
            "principal": "principal_35",
            "interest": "interest_35",
            "balance": "balance_35",
        })
        monthly = df25y_monthly.merge(
            df35y_monthly[["month_in_year", "principal_35", "interest_35", "balance_35"]],
            on="month_in_year",
            how="inner",
        )
        monthly["principal_diff"] = monthly["principal_25"] - monthly["principal_35"]
        monthly["interest_diff"] = monthly["interest_35"] - monthly["interest_25"]
        monthly["balance_diff"] = monthly["balance_35"] - monthly["balance_25"]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=monthly["month_in_year"], y=monthly["principal_diff"],
            name="25Y - 35Y Principal",
            hovertemplate=f"Year {year_num} Month %{{x}}<br>25Y - 35Y Principal: £%{{y:,.2f}}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=monthly["month_in_year"], y=monthly["interest_diff"],
            name="35Y - 25Y Interest",
            hovertemplate=f"Year {year_num} Month %{{x}}<br>35Y - 25Y Interest: £%{{y:,.2f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=monthly["month_in_year"], y=monthly["balance_diff"],
            name="Balance difference (35Y - 25Y)",
            mode="lines+markers",
            yaxis="y2",
            hovertemplate=f"Year {year_num} Month %{{x}}<br>Balance gap: £%{{y:,.2f}}<extra></extra>",
        ))
        title = f"{title_prefix} · Monthly difference for Year {year_num}"
        xaxis_title = f"Month in Year {year_num}"

    fig.update_layout(
        title=title,
        template="plotly_white",
        barmode="group",
        xaxis=dict(title=xaxis_title),
        yaxis=dict(title="Principal / Interest difference (£)"),
        yaxis2=dict(title="Balance difference (£)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=-0.24, x=0, font=dict(size=10)),
        height=460,
        margin=dict(t=80, l=10, r=10, b=105),
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



def build_strategy_simple_chart(
    compare_df: pd.DataFrame,
    title_prefix: str,
    view_mode: str = "Totals",
    interest_label: str = "Extra Interest",
    principal_label: str = "Extra Principal",
) -> go.Figure:
    fig = go.Figure()

    show_monthly = (view_mode == "Monthly Avg")
    if show_monthly:
        y_interest = compare_df["avg_extra_interest_per_month"]
        y_principal = compare_df["avg_extra_principal_per_month"]
        yaxis_title = "£ per Month"
        chart_title = f"{title_prefix} · Monthly Averages by 5-Year Period"
        interest_hover = f"{interest_label} / month"
        principal_hover = f"{principal_label} / month"
        interest_name = f"{interest_label} / Month"
        principal_name = f"{principal_label} / Month"
    else:
        y_interest = compare_df["total_extra_interest"]
        y_principal = compare_df["total_extra_principal"]
        yaxis_title = "£ Total over 5-Year Period"
        chart_title = f"{title_prefix} · Totals by 5-Year Period"
        interest_hover = interest_label
        principal_hover = principal_label
        interest_name = interest_label
        principal_name = principal_label

    fig.add_trace(go.Bar(
        x=compare_df["period"],
        y=y_interest,
        name=interest_name,
        text=[f"£{v:,.0f}" for v in y_interest],
        textposition="outside",
        hovertemplate="%{x}<br>" + interest_hover + ": £%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=compare_df["period"],
        y=y_principal,
        name=principal_name,
        text=[f"£{v:,.0f}" for v in y_principal],
        textposition="outside",
        hovertemplate="%{x}<br>" + principal_hover + ": £%{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=chart_title,
        template="plotly_white",
        barmode="group",
        xaxis_title="5-Year Interval",
        yaxis_title=yaxis_title,
        height=460,
        legend=dict(orientation="h", y=-0.28, x=0, font=dict(size=10)),
        margin=dict(t=100, l=10, r=10, b=120),
    )
    return fig



def build_strategy_chart(compare_df: pd.DataFrame, title_prefix: str, view_mode: str = "Totals") -> go.Figure:
    fig = go.Figure()
    comparisons = compare_df["comparison"].unique().tolist()
    show_monthly = (view_mode == "Monthly Avg")

    for comp in comparisons:
        sub = compare_df[compare_df["comparison"] == comp]
        if show_monthly:
            y_interest = sub["avg_extra_interest_per_month"]
            y_principal = sub["avg_extra_principal_per_month"]
            name_interest = f"{comp} · Avg Interest / Month"
            name_principal = f"{comp} · Avg Principal / Month"
            hover_interest = f"{comp} avg interest / month"
            hover_principal = f"{comp} avg principal / month"
            yaxis_title = "£ per Month"
            chart_title = f"{title_prefix} · Monthly Averages by 5-Year Period"
        else:
            y_interest = sub["total_extra_interest"]
            y_principal = sub["total_extra_principal"]
            name_interest = f"{comp} · Extra Interest"
            name_principal = f"{comp} · Extra Principal"
            hover_interest = f"{comp} extra interest"
            hover_principal = f"{comp} extra principal"
            yaxis_title = "£ Total over 5-Year Period"
            chart_title = f"{title_prefix} · Totals by 5-Year Period"

        fig.add_trace(go.Bar(
            x=sub["period"],
            y=y_interest,
            name=name_interest,
            text=[f"£{v:,.0f}" for v in y_interest],
            textposition="outside",
            hovertemplate="%{x}<br>" + hover_interest + ": £%{y:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=sub["period"],
            y=y_principal,
            name=name_principal,
            text=[f"£{v:,.0f}" for v in y_principal],
            textposition="outside",
            hovertemplate="%{x}<br>" + hover_principal + ": £%{y:,.2f}<extra></extra>",
        ))

    fig.update_layout(
        title=chart_title,
        template="plotly_white",
        barmode="group",
        xaxis_title="5-Year Interval",
        yaxis_title=yaxis_title,
        height=500,
        legend=dict(orientation="h", y=-0.3, x=0, font=dict(size=10)),
        margin=dict(t=100, l=10, r=10, b=120),
    )
    return fig



def monthly_payment_months(principal: float, annual_rate: float, months: int) -> float:
    if months <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / months if months else 0.0
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)


def _clean_lump_sum_inputs(df: pd.DataFrame, max_year: int) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["Year", "Amount", "Fee"])
    out = pd.DataFrame(df).copy()
    cols = {c.lower(): c for c in out.columns}
    year_col = cols.get("year")
    amount_col = cols.get("amount")
    fee_col = cols.get("fee")
    if year_col is None:
        return pd.DataFrame(columns=["Year", "Amount", "Fee"])
    rename_map = {year_col: "Year"}
    if amount_col is not None:
        rename_map[amount_col] = "Amount"
    if fee_col is not None:
        rename_map[fee_col] = "Fee"

    out = out[list(rename_map)].rename(columns=rename_map)
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["Amount"] = pd.to_numeric(out.get("Amount", 0.0), errors="coerce").fillna(0.0)
    out["Fee"] = pd.to_numeric(out.get("Fee", 0.0), errors="coerce").fillna(0.0)
    out = out.dropna(subset=["Year"])
    out["Year"] = out["Year"].astype(int)
    out = out[(out["Year"] >= 1) & (out["Year"] <= max_year) & ((out["Amount"] > 0) | (out["Fee"] > 0))]
    return out.sort_values(["Year", "Amount", "Fee"]).reset_index(drop=True)


def _clean_rate_block_inputs(df: pd.DataFrame, max_year: int) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["Start Year", "New Rate (%)", "End Year"])
    out = pd.DataFrame(df).copy()
    cols = {c.lower(): c for c in out.columns}
    start_col = cols.get("start year")
    rate_col = cols.get("new rate (%)")
    if start_col is None or rate_col is None:
        return pd.DataFrame(columns=["Start Year", "New Rate (%)", "End Year"])
    out = out[[start_col, rate_col]].rename(columns={start_col: "Start Year", rate_col: "New Rate (%)"})
    out["Start Year"] = pd.to_numeric(out["Start Year"], errors="coerce")
    out["New Rate (%)"] = pd.to_numeric(out["New Rate (%)"], errors="coerce")
    out = out.dropna(subset=["Start Year", "New Rate (%)"])
    out["Start Year"] = out["Start Year"].astype(int)
    out = out[(out["Start Year"] >= 1) & (out["Start Year"] <= max_year) & (out["New Rate (%)"] >= 0)]
    out["End Year"] = (out["Start Year"] + 4).clip(upper=max_year)
    return out.sort_values(["Start Year", "New Rate (%)"]).reset_index(drop=True)


def _rate_for_year(base_rate: float, year: int, rate_blocks: pd.DataFrame) -> float:
    if rate_blocks is None or len(rate_blocks) == 0:
        return base_rate
    rate = base_rate
    for _, row in rate_blocks.iterrows():
        if int(row["Start Year"]) <= year <= int(row["End Year"]):
            rate = float(row["New Rate (%)"])
    return rate


def amort_table_personalised(scenario: Scenario, lump_sum_df: pd.DataFrame | None = None, rate_blocks_df: pd.DataFrame | None = None) -> pd.DataFrame:
    base_principal = scenario.property_price - scenario.deposit
    max_year = scenario.term_years
    lump_sum_df = _clean_lump_sum_inputs(lump_sum_df, max_year)
    rate_blocks_df = _clean_rate_block_inputs(rate_blocks_df, max_year)

    lump_month_map = {}
    if len(lump_sum_df):
        # apply lump sum at the start of the selected year
        grouped = lump_sum_df.groupby("Year", as_index=False)["Amount"].sum()
        for _, row in grouped.iterrows():
            month_num = (int(row["Year"]) - 1) * 12 + 1
            lump_month_map[month_num] = float(row["Amount"])

    rows = []
    balance = base_principal
    total_months = scenario.term_years * 12
    current_rate = None
    current_payment = None

    for month_num in range(1, total_months + 1):
        if balance <= 1e-8:
            break

        year = ((month_num - 1) // 12) + 1
        month_in_year = ((month_num - 1) % 12) + 1

        # apply lump sum before the regular payment for the selected year starts
        lump_sum_applied = lump_month_map.get(month_num, 0.0)
        if lump_sum_applied:
            balance = max(balance - lump_sum_applied, 0.0)

        applied_rate = _rate_for_year(scenario.annual_rate, year, rate_blocks_df)
        remaining_months = total_months - month_num + 1

        if (current_rate != applied_rate) or (lump_sum_applied > 0) or (current_payment is None):
            current_payment = monthly_payment_months(balance, applied_rate, remaining_months)
            current_rate = applied_rate

        opening_balance = balance
        monthly_rate = applied_rate / 100 / 12
        interest = opening_balance * monthly_rate
        principal_paid = current_payment - interest

        if principal_paid > balance:
            principal_paid = balance
            pay_actual = interest + principal_paid
        else:
            pay_actual = current_payment

        balance = opening_balance - principal_paid

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
            "applied_rate": applied_rate,
            "lump_sum_applied": lump_sum_applied,
        })

    return pd.DataFrame(rows)


# =========================
# UI
# =========================

with st.sidebar:
    st.header("Inputs")
    property_price = st.number_input("Property price (£)", min_value=0, value=0, step=5000, placeholder="Enter property price")
    annual_rate = st.number_input("Annual rate (%)", min_value=0.0, value=6.15, step=0.05)
    target_payment = st.number_input(
        "Target monthly mortgage payment (£)",
        min_value=0,
        value=1500,
        step=25,
        key="target_payment",
    )
    st.markdown(
        "<div style='margin:4px 0 4px 0; border-top:1px solid rgba(0,0,0,0.12);'></div>",
        unsafe_allow_html=True,
    )
    strategy_deposit = st.number_input(
        "Deposit Strategy (£)",
        min_value=0,
        max_value=int(property_price),
        value=min(int(property_price), int(BASE_COMPARISON_DEPOSIT)),
        step=5000,
        key="strategy_deposit",
    )
    st.markdown(
        "<div style='margin:4px 0 4px 0; border-top:1px solid rgba(0,0,0,0.12);'></div>",
        unsafe_allow_html=True,
    )
    st.subheader("Fees")
    solicitor_fee = st.number_input("Solicitor fees (£)", min_value=0, value=2000, step=50)
    surveyor_fee = st.number_input("Surveyor (£)", min_value=0, value=1200, step=50)
    land_registry_fee = st.number_input("Land Registry fee (£)", min_value=0, value=150, step=25)
    valuation_fee = st.number_input("Valuation fee (£)", min_value=0, value=300, step=25)
    admin_fee = st.number_input("Admin/arrangement fee (£)", min_value=0, value=300, step=25)
    legal_contribution_fee = st.number_input("Legal contribution fee (£)", min_value=0, value=350, step=25)
    insurance_upfront = st.number_input("Buildings insurance upfront (£)", min_value=0, value=200, step=25)
    insurance_annual = st.number_input("Buildings insurance annual (£)", min_value=0, value=200, step=25)

    st.markdown(
        "<div style='margin:4px 0 4px 0; border-top:1px solid rgba(0,0,0,0.12);'></div>",
        unsafe_allow_html=True,
    )
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

# Live scenarios follow the current sidebar-driven cash results.
live_scenarios = build_scenario_objects_from_required_cash(
    required_cash_df,
    fees,
    annual_costs,
    stamp_func,
)

# Amortisation and personalised strategy follow the live sidebar-driven scenarios.
amort_tables = {k: amort_table(v) for k, v in live_scenarios.items()}

home_tab, cash_tab, amort_tab, personalised_tab, strategy_tab, custom_tab = st.tabs(["Home", "Cash Required", "Amortisation", "Personalised Strategy", "Debt Delay Strategy", "Custom Delay Strategy"])

with home_tab:
    st.title("Welcome to Mortgage Roulette")
    st.subheader("How to Use")
    st.markdown(
        '<div class="subtle">Each section of Mortgage Roulette serves a specific function, guiding you through different aspects of your mortgage planning — from upfront costs to long-term repayment strategy.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-card">'
        '<h4 style="margin-bottom:0.35rem;">1. Cash Required</h4>'
        '<div class="subtle">Variables to set: Target Monthly Payment and Property Price.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">See exactly how much upfront cash each scenario requires.</div>'
        '<ul style="margin:0.75rem 0 0 1rem; padding-left:1rem;">'
        '<li>Deposit requirements</li>'
        '<li>Upfront fees and stamp duty</li>'
        '<li>Total cash needed to complete purchase</li>'
        '</ul>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-card">'
        '<h4 style="margin-bottom:0.35rem;">2. Amortisation</h4>'
        '<div class="subtle">Variables to set: Target Monthly Payment and Property Price.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">Compare repayment schedules side by side.</div>'
        '<ul style="margin:0.75rem 0 0 1rem; padding-left:1rem;">'
        '<li>Balance reduction over time</li>'
        '<li>Interest versus principal split</li>'
        '<li>Term-specific cost patterns</li>'
        '</ul>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-card">'
        '<h4 style="margin-bottom:0.35rem;">3. Personalised Strategy</h4>'
        '<div class="subtle">Variables to set: Target Monthly Payment and Property Price.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">Build a custom repayment plan with flexible inputs.</div>'
        '<ul style="margin:0.75rem 0 0 1rem; padding-left:1rem;">'
        '<li>Add lump sum payments</li>'
        '<li>Adjust interest-rate blocks</li>'
        '<li>See future amortisation impact</li>'
        '</ul>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-card" style="margin-top:1rem;">'
        '<h4 style="margin-bottom:0.35rem;">4. Debt Delay Strategy</h4>'
        '<div class="subtle">Variables to set: Deposit and Property Price.</div>'
        '<p class="subtle" style="margin-top:0.75rem;">This section reverses the typical approach. Instead of setting a target monthly payment, you begin by defining your available deposit to understand how this impacts monthly repayments across different mortgage terms.</p>'
        '<p class="subtle">By holding the deposit constant, you can compare how each amortisation plan affects:</p>'
        '<ul style="margin:0.75rem 0 0 1rem; padding-left:1rem;">'
        '<li>Monthly payment levels</li>'
        '<li>Total interest paid over time</li>'
        '<li>Speed of debt reduction</li>'
        '</ul>'
        '<p class="subtle" style="margin-top:0.75rem;">Longer-term mortgages will naturally produce lower monthly payments. This section highlights the true cost of that flexibility.</p>'
        '<h5 style="margin:1rem 0 0.35rem 0;">Understanding the Cost of Delay</h5>'
        '<div class="subtle">For each scenario, the dashboard calculates the additional interest paid compared to a standard 25-year plan.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">This is presented as a monthly average cost broken down across 5-year periods.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">This “extra interest” is the cost of delaying debt repayment — the price you pay to keep more cash available upfront or reduce monthly pressure.</div>'
        '<h5 style="margin:1rem 0 0.35rem 0;">Strategic Insight</h5>'
        '<div class="subtle">Use this data to assess whether lower monthly payments are worth the additional long-term cost, and when it may be beneficial to reduce debt earlier.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">For example, you may choose a longer-term plan for affordability today, then later make a lump sum payment to offset delayed principal and reduce future interest.</div>'
        '<h5 style="margin:1rem 0 0.35rem 0;">Towards a Personalised Delay Strategy</h5>'
        '<div class="subtle">This section is designed to evolve into a fully interactive tool driven by your deposit size rather than your monthly payment.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">Future features will help you simulate lump sums, adjust repayment timing, and optimise affordability versus long-term cost.</div>'
        '<div class="subtle" style="margin-top:0.75rem;">This helps answer the key question: “What is the real cost of giving myself more breathing room today?”</div>'
        '</div>',
        unsafe_allow_html=True,
    )

with cash_tab:
    st.title("Cash Required")
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
    render_required_cash_summary_cards(required_cash_df)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Required cash to hit target payment")
    st.markdown('<div class="subtle">For the selected property price and mortgage target, this shows the upfront cash mix needed across the 25-year, 35-year and 40-year structures.</div>', unsafe_allow_html=True)
    render_chart_with_actions(build_required_cash_chart(required_cash_df), "cash_required", "Cash Required")
    with st.expander("Show cash summary table"):
        st.dataframe(required_cash_df, use_container_width=True, height=300)
    st.markdown('</div>', unsafe_allow_html=True)


with amort_tab:
    st.title("Amortisation")
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
    render_required_cash_summary_cards(required_cash_df)

    for key in ["25Y", "35Y", "40Y"]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader(base_scenarios[key]["label"].replace("Scenario", "amortisation"))
        st.markdown(
            f'<div class="subtle">Use the view menu below to switch between yearly overview and monthly drilldown. On a phone, landscape mode works best. These charts follow the current sidebar inputs, including your target monthly mortgage payment. Download PNG from the chart icons, or use the HTML / JSON actions below.</div>',
            unsafe_allow_html=True
        )

        years_available = sorted(amort_tables[key]["year"].unique().tolist())
        view_options = ["Overview"] + [f"Year {yr}" for yr in years_available]
        select_col, _ = st.columns([1.4, 3.6])
        with select_col:
            selected_view = st.selectbox(
                "View",
                view_options,
                index=0,
                key=f"amort_view_{key}",
                label_visibility="collapsed",
            )

        render_chart_with_actions(
            build_amortisation_chart(amort_tables[key], base_scenarios[key]["label"], selected_view),
            f"amort_{key.lower()}_{selected_view.lower().replace(' ', '_')}",
            f"{key} Amortisation",
        )
        st.markdown('</div>', unsafe_allow_html=True)


with strategy_tab:
    st.title("Debt Delay Strategy")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Property price", fmt_gbp(property_price))
    with m2:
        st.metric("Annual rate", f"{annual_rate:.2f}%")
    with m3:
        st.metric("Deposit", fmt_gbp(strategy_deposit))
    with m4:
        st.metric("Stamp duty mode", "FTB" if stamp_mode == "First-time buyer" else "Standard")

    st.markdown("<div style='height:0.35rem'></div>", unsafe_allow_html=True)
    strategy_deposit = min(float(strategy_deposit), float(property_price))
    strategy_scenarios = {
        key: Scenario(
            key,
            float(property_price),
            float(strategy_deposit),
            float(cfg["annual_rate"]),
            int(cfg["term_years"]),
            fees,
            annual_costs,
            stamp_func,
        )
        for key, cfg in base_scenarios.items()
    }
    strategy_tables = {k: amort_table(v) for k, v in strategy_scenarios.items()}
    render_strategy_summary_cards(strategy_tables, property_price, fees, stamp_func)
    compare_35_vs_25 = build_5yr_comparison_against_base(strategy_tables["25Y"], strategy_tables["35Y"], "35Y vs 25Y")
    compare_40_vs_25 = build_5yr_comparison_against_base(strategy_tables["25Y"], strategy_tables["40Y"], "40Y vs 25Y")
    compare_against_25 = pd.concat([compare_35_vs_25, compare_40_vs_25], ignore_index=True)
    compare_40_vs_35 = build_5yr_comparison_against_base(strategy_tables["35Y"], strategy_tables["40Y"], "40Y vs 35Y")

    st.subheader("5-year interval comparison · amortisation gap · 25-year vs 35-year")
    st.markdown(
        f'<div class="subtle">Using a deposit of {fmt_gbp(strategy_deposit)} for the 5-year strategy charts. This compares 35Y minus 25Y for principal and interest each year. A positive interest bar means 35Y paid more interest than 25Y; a negative principal bar means 35Y paid less principal than 25Y. The line shows the balance gap between 35Y and 25Y.</div>',
        unsafe_allow_html=True,
    )
    years_available = sorted(strategy_tables["25Y"]["year"].unique().tolist())
    view_diff_25_35 = st.selectbox(
        "View mode",
        ["Overview"] + [f"Year {yr}" for yr in years_available],
        index=0,
        key="strategy_view_diff_25_35"
    )
    render_chart_with_actions(
        build_amortisation_difference_chart(
            strategy_tables["25Y"],
            strategy_tables["35Y"],
            "25-Year vs 35-Year principal and interest gap",
            view_diff_25_35,
        ),
        "strategy_5yr_diff_25_35",
        "5-Year Strategy · 25-Year vs 35-Year principal/interest gap",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison · quick view · 25-year vs 35-year")
    st.markdown('<div class="subtle">A simpler view for users who want the headline 5-year interval difference only. This shows 35Y vs 25Y over five-year spans.</div>', unsafe_allow_html=True)
    view_simple_25_35_intervals = st.selectbox(
        "View mode",
        ["Totals", "Monthly Avg"],
        index=0,
        key="strategy_view_simple_25_35_intervals"
    )
    render_chart_with_actions(
        build_strategy_simple_chart(
            compare_35_vs_25,
            "25-Year vs 35-Year",
            view_simple_25_35_intervals,
            interest_label="Extra Interest (35Y - 25Y)",
            principal_label="Extra Principal (25Y - 35Y)",
        ),
        "strategy_5yr_simple_25_35_intervals",
        "5-Year Strategy · 25-Year vs 35-Year · 5-Year Intervals",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison · quick view · 25-year vs 40-year")
    st.markdown('<div class="subtle">A simpler view for users who want the headline comparison only. This shows 40Y vs 25Y.</div>', unsafe_allow_html=True)
    view_simple_25_40 = st.selectbox(
        "View mode",
        ["Totals", "Monthly Avg"],
        index=0,
        key="strategy_view_simple_25_40"
    )
    render_chart_with_actions(
        build_strategy_simple_chart(
            compare_40_vs_25,
            "25-Year vs 40-Year",
            view_simple_25_40,
            interest_label="Extra Interest (40Y - 25Y)",
            principal_label="Extra Principal (25Y - 40Y)",
        ),
        "strategy_5yr_simple_25_40",
        "5-Year Strategy · 25-Year vs 40-Year",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison · anchored to 25-year")
    st.markdown('<div class="subtle">This compares 35Y vs 25Y and 40Y vs 25Y on a like-for-like basis using a current required deposit. Extra interest means the longer plan paid more interest; extra principal means the shorter plan paid down more principal over the same 5-year block.</div>', unsafe_allow_html=True)
    view_anchor_25 = st.selectbox(
        "View mode",
        ["Totals", "Monthly Avg"],
        index=0,
        key="strategy_view_anchor_25"
    )
    render_chart_with_actions(
        build_strategy_chart(compare_against_25, "Anchored to 25-Year", view_anchor_25),
        "strategy_5yr_anchor_25",
        "5-Year Strategy vs 25-Year",
    )
    with st.expander("Show anchored-to-25 comparison table"):
        st.dataframe(compare_against_25.round(2), use_container_width=True, height=300)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("5-year interval comparison · anchored to 35-year")
    st.markdown('<div class="subtle">This compares 40Y vs 35Y on a like-for-like basis using a current required deposit. Extra interest means the 40Y plan paid more interest; extra principal means the 35Y plan paid down more principal over the same 5-year block.</div>', unsafe_allow_html=True)
    view_anchor_35 = st.selectbox(
        "View mode",
        ["Totals", "Monthly Avg"],
        index=0,
        key="strategy_view_anchor_35"
    )
    render_chart_with_actions(
        build_strategy_chart(compare_40_vs_35, "Anchored to 35-Year", view_anchor_35),
        "strategy_5yr_anchor_35",
        "5-Year Strategy vs 35-Year",
    )
    with st.expander("Show anchored-to-35 comparison table"):
        st.dataframe(compare_40_vs_35.round(2), use_container_width=True, height=260)
    st.markdown('</div>', unsafe_allow_html=True)



with personalised_tab:
    st.title("Personalised Strategy")
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
    render_required_cash_summary_cards(required_cash_df)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Personalised Strategy")
    st.markdown(
        '<div class="subtle">This tab starts from fresh copies of the amortisation schedules above whenever the sidebar inputs change. Add one-off lump sums and 5-year rate blocks to recalculate the future schedule exactly in real time for the currently selected sidebar assumptions.</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # tie editor state to sidebar inputs so customised schedules reset cleanly when the base assumptions change
    reset_signature = f"{property_price}_{annual_rate}_{target_payment}_{stamp_mode}_{solicitor_fee}_{surveyor_fee}_{land_registry_fee}_{valuation_fee}_{admin_fee}_{legal_contribution_fee}_{insurance_upfront}_{insurance_annual}"

    for key in ["25Y", "35Y", "40Y"]:
        cfg = live_scenarios[key]
        baseline_df = amort_tables[key].copy()

        reset_counter_key = f"personal_reset_counter_{key}_{reset_signature}"
        if reset_counter_key not in st.session_state:
            st.session_state[reset_counter_key] = 0
        reset_counter = st.session_state[reset_counter_key]

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        header_left, header_mid, header_right = st.columns([4.5, 1.4, 1.6])
        with header_left:
            st.subheader(f"{base_scenarios[key]['label']} · custom strategy")
            st.markdown(
                '<div class="subtle">Add optional lump sums by year and optional 5-year interest-rate blocks. Lump sums are applied at the start of the chosen year. Each rate row applies from the chosen start year for 5 years.</div>',
                unsafe_allow_html=True
            )
        with header_mid:
            st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)
            if st.button("Reset section", key=f"reset_btn_{key}_{reset_signature}", use_container_width=True):
                st.session_state[reset_counter_key] += 1
                st.rerun()
        with header_right:
            st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)
            # placeholder, actual button rendered later once custom values exist

        years_available = sorted(baseline_df["year"].unique().tolist())
        view_options = ["Overview"] + [f"Year {yr}" for yr in years_available]

        controls_col, _ = st.columns([1.4, 3.6])
        with controls_col:
            selected_view = st.selectbox(
                "View",
                view_options,
                index=0,
                key=f"personal_view_{key}_{reset_signature}_{reset_counter}",
                label_visibility="collapsed",
            )

        editor_col1, editor_col2 = st.columns(2)
        with editor_col1:
            st.caption("One-off lump sums")
            default_lump_df = pd.DataFrame(columns=["Year", "Amount", "Fee"])
            lump_df_raw = st.data_editor(
                default_lump_df,
                key=f"personal_lumps_{key}_{reset_signature}_{reset_counter}",
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "Year": st.column_config.NumberColumn("Year", min_value=1, max_value=cfg.term_years, step=1, format="%d"),
                    "Amount": st.column_config.NumberColumn("Amount (£)", min_value=0.0, step=1000.0, format="£%.0f"),
                    "Fee": st.column_config.NumberColumn("Fee (£)", min_value=0.0, step=50.0, format="£%.0f"),
                },
            )

        with editor_col2:
            st.caption("5-year rate blocks")
            default_rate_df = pd.DataFrame(columns=["Start Year", "New Rate (%)"])
            rate_df = st.data_editor(
                default_rate_df,
                key=f"personal_rates_{key}_{reset_signature}_{reset_counter}",
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "Start Year": st.column_config.NumberColumn("Start Year", min_value=1, max_value=cfg.term_years, step=1, format="%d"),
                    "New Rate (%)": st.column_config.NumberColumn("New Rate (%)", min_value=0.0, step=0.1, format="%.2f"),
                },
            )

        clean_lumps = _clean_lump_sum_inputs(lump_df_raw, cfg.term_years)
        clean_rates = _clean_rate_block_inputs(rate_df, cfg.term_years)
        custom_df = amort_table_personalised(cfg, clean_lumps, clean_rates)

        lump_payment_table = build_lump_payment_summary(lump_df_raw, custom_df, cfg.term_years)

        # show enriched lump sum summary below with updated payment
        if len(lump_payment_table):
            st.dataframe(
                lump_payment_table,
                use_container_width=True,
                height=min(260, 44 + len(lump_payment_table) * 35),
                hide_index=True,
            )

        render_chart_with_actions(
            build_amortisation_chart(custom_df, f"{base_scenarios[key]['label']} · personalised", selected_view),
            f"personalised_{key.lower()}_{selected_view.lower().replace(' ', '_')}",
            f"{key} Personalised Strategy",
        )

        # Summary comparison cards: baseline vs customised
        baseline_interest = float(baseline_df["interest"].sum()) if len(baseline_df) else 0.0
        custom_interest = float(custom_df["interest"].sum()) if len(custom_df) else 0.0
        interest_delta = custom_interest - baseline_interest

        baseline_months = int(len(baseline_df))
        custom_months = int(len(custom_df))
        month_delta = baseline_months - custom_months

        baseline_last_balance = float(baseline_df["balance"].iloc[-1]) if len(baseline_df) else 0.0
        custom_last_balance = float(custom_df["balance"].iloc[-1]) if len(custom_df) else 0.0
        ending_balance_delta = custom_last_balance - baseline_last_balance

        total_fee = clean_lumps["Fee"].sum() if len(clean_lumps) else 0
        summary_html = f"""<html><body><h2>{base_scenarios[key]["label"]} · custom strategy</h2><p>Selected view: {selected_view}</p><ul><li>Baseline total interest: {fmt_gbp(baseline_interest)}</li><li>Custom total interest: {fmt_gbp(custom_interest)}</li><li>Baseline months: {baseline_months}</li><li>Custom months: {custom_months}</li><li>Starting deposit: {fmt_gbp(cfg.deposit)}</li><li>Total lump sum fees: {fmt_gbp(total_fee)}</li></ul></body></html>"""
        st.download_button(
            "Export section HTML",
            data=summary_html,
            file_name=f"{key.lower()}_custom_strategy.html",
            mime="text/html",
            key=f"html_summary_{key}_{reset_signature}_{reset_counter}",
            use_container_width=False,
        )

        top_metrics = st.columns(3)
        with top_metrics[0]:
            st.metric("Total interest impact", fmt_gbp(abs(interest_delta)), delta=(f"{fmt_gbp(interest_delta)} vs baseline"))
        with top_metrics[1]:
            payoff_delta_text = f"{month_delta:+d} months"
            st.metric("Payoff timing impact", payoff_delta_text, delta="negative = slower, positive = faster")
        with top_metrics[2]:
            st.metric("Ending balance impact", fmt_gbp(abs(ending_balance_delta)), delta=(f"{fmt_gbp(ending_balance_delta)} vs baseline"))

        info_cols = st.columns(4)
        with info_cols[0]:
            st.metric("Starting deposit", fmt_gbp(cfg.deposit))
        with info_cols[1]:
            st.metric("Lump sums added", fmt_gbp(clean_lumps["Amount"].sum() if len(clean_lumps) else 0))
        with info_cols[2]:
            st.metric("Lump sum fees", fmt_gbp(clean_lumps["Fee"].sum() if len(clean_lumps) else 0))
        with info_cols[3]:
            st.metric("Custom rate blocks", int(len(clean_rates)))

        compare_left, compare_right = st.columns(2)
        with compare_left:
            compare_df = pd.DataFrame({
                "Metric": ["Baseline total interest", "Custom total interest", "Baseline months", "Custom months"],
                "Value": [fmt_gbp(baseline_interest), fmt_gbp(custom_interest), baseline_months, custom_months],
            })
            with st.expander("Show baseline vs custom summary"):
                st.dataframe(compare_df, use_container_width=True, height=180, hide_index=True)
        with compare_right:
            with st.expander("Show cleaned strategy inputs"):
                c1, c2 = st.columns(2)
                with c1:
                    if len(clean_lumps):
                        st.dataframe(clean_lumps, use_container_width=True, height=180, hide_index=True)
                    else:
                        st.caption("No lump sums added.")
                with c2:
                    if len(clean_rates):
                        st.dataframe(clean_rates, use_container_width=True, height=180, hide_index=True)
                    else:
                        st.caption("No rate blocks added.")

        st.markdown('</div>', unsafe_allow_html=True)

with custom_tab:
    st.title("Custom Delay Strategy")
    st.markdown('<div class="subtle">Coming Soon</div>', unsafe_allow_html=True)
