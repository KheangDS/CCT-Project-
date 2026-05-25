from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.db import get_recent_calculations, save_calculation
from src.report import result_to_html, result_to_markdown, result_to_pdf_bytes
from src.tax_logic import (
    batch_salary_payroll,
    compute_accommodation_tax,
    compute_land_tax,
    compute_patent_tax,
    compute_prepayment_income_tax,
    compute_public_lighting_tax,
    compute_salary_tax,
    compute_specific_tax,
    compute_stamp_duty,
    compute_vat,
    compute_vehicle_import_tax,
    compute_vehicle_road_tax,
    compute_withholding_tax,
    fmt_money,
    load_config,
)


BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "public" / "image.png"

st.set_page_config(
    page_title="Cambodian Tax Calculator",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

def money_input(label: str, value: float = 0.0, min_value: float = 0.0) -> float:
    return st.number_input(label, min_value=min_value, value=float(value), step=10000.0, format="%.2f")


def rate_input(label: str, value: float, help_text: str | None = None) -> float:
    pct = st.number_input(label, min_value=0.0, max_value=100.0, value=value * 100, step=0.5, help=help_text)
    return pct / 100


def shared_currency() -> tuple[str, float]:
    left, right = st.columns([1, 1])
    with left:
        currency = st.radio("Currency", ["KHR", "USD"], horizontal=True)
    with right:
        exchange_rate = st.number_input("Exchange rate (KHR per USD)", min_value=1.0, value=4000.0, step=50.0)
    return currency, exchange_rate


def show_result(module: str, title: str, input_data: dict[str, Any], result: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Result")

    key_values = [
        (key, value)
        for key, value in result.items()
        if isinstance(value, (int, float, str, bool)) or value is None
    ]
    if key_values:
        st.dataframe(
            pd.DataFrame(key_values, columns=["Field", "Value"]),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Raw calculation details"):
        st.json(result)

    calc_id = save_calculation(module, title, input_data, result)
    st.success(f"Saved calculation {calc_id}")

    col1, col2, col3, col4 = st.columns(4)
    json_bytes = json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    col1.download_button("JSON", json_bytes, f"{module.lower().replace(' ', '_')}.json", "application/json")
    col2.download_button(
        "Markdown",
        result_to_markdown(module, title, input_data, result),
        f"{module.lower().replace(' ', '_')}.md",
        "text/markdown",
    )
    col3.download_button(
        "HTML",
        result_to_html(module, title, input_data, result),
        f"{module.lower().replace(' ', '_')}.html",
        "text/html",
    )
    col4.download_button(
        "PDF",
        result_to_pdf_bytes(module, title, input_data, result),
        f"{module.lower().replace(' ', '_')}.pdf",
        "application/pdf",
    )


def salary_tax_page() -> None:
    st.header("Salary Tax")
    with st.form("salary_tax_form"):
        currency, exchange_rate = shared_currency()
        left, right = st.columns(2)
        with left:
            gross_salary = money_input("Monthly gross salary", 2_000_000)
            residency = st.selectbox("Residency", ["Resident", "Non-resident"])
            spouse_count = st.number_input("Dependent spouse", min_value=0, max_value=1, value=0, step=1)
        with right:
            child_count = st.number_input("Dependent children", min_value=0, value=0, step=1)
            fringe_benefit_value = money_input("Monthly fringe benefit value", 0)
        submitted = st.form_submit_button("Calculate")

    if submitted:
        input_data = {
            "gross_salary": gross_salary,
            "residency": residency,
            "spouse_count": spouse_count,
            "child_count": child_count,
            "fringe_benefit_value": fringe_benefit_value,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_salary_tax(**input_data)
        st.metric("Salary tax", fmt_money(result["salary_tax_native"], currency))
        st.metric("Net salary", fmt_money(result["net_salary_native"], currency))
        show_result("Salary Tax", "Salary Tax Calculation", input_data, result)


def payroll_page() -> None:
    st.header("Business Payroll")
    sample = pd.DataFrame(
        [
            {
                "employee_name": "Employee 1",
                "gross_salary": 2_000_000,
                "residency": "Resident",
                "spouse_count": 0,
                "child_count": 0,
                "fringe_benefit_value": 0,
            }
        ]
    )
    currency, exchange_rate = shared_currency()
    rows = st.data_editor(sample, num_rows="dynamic", use_container_width=True)
    if st.button("Calculate payroll", type="primary"):
        input_data = {"rows": rows.to_dict("records"), "currency": currency, "exchange_rate": exchange_rate}
        result = batch_salary_payroll(input_data["rows"], currency=currency, exchange_rate=exchange_rate)
        st.metric("Total salary tax", fmt_money(result["total_salary_tax_khr"], "KHR"))
        st.metric("Total fringe benefit tax", fmt_money(result["total_fbt_khr"], "KHR"))
        st.dataframe(pd.DataFrame(result["employees"]), use_container_width=True, hide_index=True)
        show_result("Business Payroll", "Payroll Calculation", input_data, result)


def withholding_page() -> None:
    st.header("Withholding Tax")
    rates = load_config()["withholding_tax"]["resident_rates"]
    with st.form("withholding_form"):
        currency, exchange_rate = shared_currency()
        amount = money_input("Payment amount", 1_000_000)
        residency = st.selectbox("Payee residency", ["Resident", "Non-resident"])
        payment_type = st.selectbox("Payment type", list(rates.keys()))
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "amount": amount,
            "residency": residency,
            "payment_type": payment_type,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_withholding_tax(**input_data)
        st.metric("Withholding tax", fmt_money(result["tax_native"], currency))
        show_result("Withholding Tax", "Withholding Tax Calculation", input_data, result)


def land_tax_page() -> None:
    st.header("Land Tax")
    with st.form("land_form"):
        currency, exchange_rate = shared_currency()
        area_m2 = st.number_input("Land area (m2)", min_value=0.0, value=60_000.0, step=100.0)
        value_per_m2 = money_input("Value per m2", 100_000)
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "area_m2": area_m2,
            "value_per_m2": value_per_m2,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_land_tax(**input_data)
        st.metric("Land tax", fmt_money(result["tax_native"], currency))
        show_result("Land Tax", "Land Tax Calculation", input_data, result)


def stamp_duty_page() -> None:
    st.header("Stamp Duty")
    scenarios = [
        "Standard transfer",
        "Full exemption",
        "Concession/state/diplomatic",
        "Inheritance close family",
        "First gift close family",
        "Second+ gift close family",
        "Inlaws/siblings inheritance",
        "Inlaws/siblings gift",
    ]
    with st.form("stamp_form"):
        currency, exchange_rate = shared_currency()
        property_value = money_input("Property value", 100_000_000)
        scenario = st.selectbox("Scenario", scenarios)
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "property_value": property_value,
            "scenario": scenario,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_stamp_duty(**input_data)
        st.metric("Stamp duty", fmt_money(result["tax_native"], currency))
        show_result("Stamp Duty", "Stamp Duty Calculation", input_data, result)


def vat_page() -> None:
    st.header("VAT")
    with st.form("vat_form"):
        currency, exchange_rate = shared_currency()
        left, right = st.columns(2)
        with left:
            output_taxable_sales = money_input("Output taxable sales", 10_000_000)
            output_rate = rate_input("Output VAT rate", load_config()["vat"]["default_rate"])
            eligible_input_vat = money_input("Eligible input VAT", 0)
            imported_goods_vat = money_input("Imported goods VAT", 0)
        with right:
            mixed_input_vat = money_input("Mixed input VAT", 0)
            taxable_supplies = money_input("Taxable supplies", 0)
            total_supplies = money_input("Total supplies", 0)
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "output_taxable_sales": output_taxable_sales,
            "output_rate": output_rate,
            "eligible_input_vat": eligible_input_vat,
            "mixed_input_vat": mixed_input_vat,
            "taxable_supplies": taxable_supplies,
            "total_supplies": total_supplies,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "imported_goods_vat": imported_goods_vat,
        }
        result = compute_vat(**input_data)
        st.metric("VAT payable", fmt_money(result["vat_payable_native"], currency))
        st.metric("Carry forward", fmt_money(result["carry_forward_native"], currency))
        show_result("VAT", "VAT Calculation", input_data, result)


def simple_taxes_page(module: str) -> None:
    st.header(module)
    with st.form(f"{module}_form"):
        currency, exchange_rate = shared_currency()
        if module == "Patent Tax":
            size_or_revenue = st.selectbox("Taxpayer size", ["Small", "Medium", "Large", "Large (>10b revenue)"])
            annual_revenue = money_input("Annual revenue", 0)
            submitted = st.form_submit_button("Calculate")
            input_data = {
                "size_or_revenue": size_or_revenue,
                "annual_revenue": annual_revenue,
                "currency": currency,
                "exchange_rate": exchange_rate,
            }
            compute = compute_patent_tax
        elif module == "Prepayment Income Tax":
            previous_month_turnover = money_input("Previous month turnover", 10_000_000)
            submitted = st.form_submit_button("Calculate")
            input_data = {
                "previous_month_turnover": previous_month_turnover,
                "currency": currency,
                "exchange_rate": exchange_rate,
            }
            compute = compute_prepayment_income_tax
        else:
            accommodation_revenue = money_input("Accommodation revenue", 10_000_000)
            exempt = st.checkbox("Exempt")
            submitted = st.form_submit_button("Calculate")
            input_data = {
                "accommodation_revenue": accommodation_revenue,
                "exempt": exempt,
                "currency": currency,
                "exchange_rate": exchange_rate,
            }
            compute = compute_accommodation_tax
    if submitted:
        result = compute(**input_data)
        tax_key = next((key for key in result if key.endswith("_native")), None)
        if tax_key:
            st.metric(module, fmt_money(result[tax_key], currency))
        show_result(module, f"{module} Calculation", input_data, result)


def patent_tax_page() -> None:
    simple_taxes_page("Patent Tax")

def prepayment_income_tax_page() -> None:
    simple_taxes_page("Prepayment Income Tax")

def accommodation_tax_page() -> None:
    simple_taxes_page("Accommodation Tax")

def specific_tax_page() -> None:
    st.header("Specific Tax")
    rates = load_config()["specific_tax"]["rates"]
    with st.form("specific_tax_form"):
        currency, exchange_rate = shared_currency()
        category = st.selectbox("Category", list(rates.keys()))
        supply_type = st.selectbox("Supply type", ["Domestic goods", "Imported goods", "Service"])
        supply_value = money_input("Supply value", 10_000_000)
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "category": category,
            "supply_value": supply_value,
            "supply_type": supply_type,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_specific_tax(**input_data)
        st.metric("Specific tax", fmt_money(result["tax_native"], currency))
        show_result("Specific Tax", "Specific Tax Calculation", input_data, result)


def public_lighting_page() -> None:
    st.header("Public Lighting Tax")
    with st.form("public_lighting_form"):
        currency, exchange_rate = shared_currency()
        product_category = st.text_input("Product category", "Alcohol / tobacco")
        base_value = money_input("Tax base value", 10_000_000)
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "base_value": base_value,
            "product_category": product_category,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_public_lighting_tax(**input_data)
        st.metric("Public lighting tax", fmt_money(result["tax_native"], currency))
        show_result("Public Lighting Tax", "Public Lighting Tax Calculation", input_data, result)


def vehicle_road_page() -> None:
    st.header("Vehicle Road Tax")
    with st.form("vehicle_road_form"):
        currency, exchange_rate = shared_currency()
        engine_capacity_cc = st.number_input("Engine capacity (cc)", min_value=0, value=2000, step=100)
        vehicle_age = st.selectbox("Vehicle age", ["New", "Old"])
        use_custom = st.checkbox("Use custom tax amount")
        custom_tax = money_input("Custom tax amount", 0) if use_custom else None
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "engine_capacity_cc": engine_capacity_cc,
            "vehicle_age": vehicle_age,
            "custom_tax": custom_tax,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_vehicle_road_tax(**input_data)
        st.metric("Annual road tax", fmt_money(result["tax_native"], currency))
        show_result("Vehicle Road Tax", "Vehicle Road Tax Calculation", input_data, result)


def vehicle_import_page() -> None:
    st.header("Vehicle Import Tax")
    with st.form("vehicle_import_form"):
        currency, exchange_rate = shared_currency()
        cif_value = money_input("CIF value", 10_000_000)
        import_duty_rate = rate_input("Import duty rate", 0.35)
        special_tax_rate = rate_input("Special tax rate", 0.30)
        vat_rate = rate_input("VAT rate", 0.10)
        submitted = st.form_submit_button("Calculate")
    if submitted:
        input_data = {
            "cif_value": cif_value,
            "import_duty_rate": import_duty_rate,
            "special_tax_rate": special_tax_rate,
            "vat_rate": vat_rate,
            "currency": currency,
            "exchange_rate": exchange_rate,
        }
        result = compute_vehicle_import_tax(**input_data)
        st.metric("Total import tax", fmt_money(result["total_tax_native"], currency))
        show_result("Vehicle Import Tax", "Vehicle Import Tax Calculation", input_data, result)


def history_page() -> None:
    st.header("History")
    rows = get_recent_calculations(50)
    if rows.empty:
        st.info("No saved calculations yet.")
        return
    st.dataframe(rows[["id", "module", "title", "created_at"]], use_container_width=True, hide_index=True)
    selected = st.selectbox("Open saved calculation", rows["id"].tolist())
    record = rows.loc[rows["id"] == selected].iloc[0]
    with st.expander("Inputs", expanded=True):
        st.json(json.loads(record["input_json"]))
    with st.expander("Result", expanded=True):
        st.json(json.loads(record["result_json"]))


def main() -> None:
    
    st.markdown("""
        <style>
            :root {
                --tax-green: #0f5132;
                --tax-muted: #5d6b63;
                --tax-border: #d9e2dc;
            }

            /* Modernizing the look */
            div.block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
                max-width: 1200px;
            }
            .app-header {
                display: flex;
                align-items: center;
                gap: 1rem;
                padding: 1.3rem 1rem;
                border: 1px solid var(--tax-border);
                border-radius: 8px;
                background: #ffffff;
                box-shadow: 0 8px 24px rgba(15, 81, 50, 0.08);
                margin-bottom: 0.9rem;
            }
            .app-header img {
                width: 90px;
                height: 90px;
                object-fit: contain;
                flex: 0 0 auto;
            }
            .app-title {
                color: var(--tax-green);
                font-size: 1.55rem;
                font-weight: 800;
                line-height: 1.25;
                letter-spacing: 0;
            }
            .app-subtitle {
                color: var(--tax-muted);
                font-size: 0.95rem;
                margin-top: 0.2rem;
                letter-spacing: 0;
            }
            .stButton>button {
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.2s ease;
            }
            .stButton>button:hover {
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                transform: translateY(-1px);
            }
            div[data-testid="stMetricValue"] {
                font-size: 2rem;
                font-weight: 700;
                color: #1f5f3e;
            }
            /* Styling expanders similarly to cards */
            div[data-testid="stExpander"] {
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            }
            @media (max-width: 720px) {
                .app-header {
                    align-items: flex-start;
                    gap: 0.75rem;
                }
                .app-header img {
                    width: 54px;
                    height: 54px;
                }
                .app-title {
                    font-size: 1.18rem;
                }
                .app-subtitle {
                    font-size: 0.86rem;
                }
            }
        </style>
    """, unsafe_allow_html=True)
    
    pages = {
        "Personal & Payroll": [
            st.Page(salary_tax_page, title="Salary Tax"),
            st.Page(payroll_page, title="Business Payroll"),
        ],
        "Business Taxes": [
            st.Page(withholding_page, title="Withholding Tax"),
            st.Page(vat_page, title="VAT"),
            st.Page(patent_tax_page, title="Patent Tax"),
            st.Page(prepayment_income_tax_page, title="Prepayment Income Tax"),
            st.Page(specific_tax_page, title="Specific Tax"),
        ],
        "Property & Others": [
            st.Page(land_tax_page, title="Land Tax"),
            st.Page(stamp_duty_page, title="Stamp Duty"),
            st.Page(accommodation_tax_page, title="Accommodation Tax"),
            st.Page(public_lighting_page, title="Public Lighting Tax"),
            st.Page(vehicle_road_page, title="Vehicle Road Tax"),
            st.Page(vehicle_import_page, title="Vehicle Import Tax"),
        ],
        "System": [
            st.Page(history_page, title="History"),
        ]
    }

    with LOGO_PATH.open("rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    
    st.markdown(
        f"""
        <div class="app-header">
            <img src="data:image/png;base64,{img_b64}" alt="General Department of Taxation logo" />
            <div>
                <div class="app-title">Cambodia Tax Calculator</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
