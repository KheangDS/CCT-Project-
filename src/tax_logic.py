
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "tax_rates.json"


def load_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Tax rate config file not found: {CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tax rate config file is invalid JSON: {CONFIG_PATH}") from exc


def fmt_money(value: float, currency: str = "KHR") -> str:
    symbol = "៛" if currency.upper() == "KHR" else "$"
    return f"{value:,.2f} {symbol}" if currency.upper() != "KHR" else f"{value:,.0f} {symbol}"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except Exception:
        return default


def currency_to_khr(amount: float, currency: str, exchange_rate: float) -> float:
    return amount if currency.upper() == "KHR" else amount * exchange_rate


def khr_to_currency(amount_khr: float, currency: str, exchange_rate: float) -> float:
    return amount_khr if currency.upper() == "KHR" else amount_khr / exchange_rate


def salary_tax_bracket(taxable_salary_khr: float) -> dict[str, Any]:
    cfg = load_config()["salary_tax"]["resident_brackets_khr"]
    chosen = cfg[0]
    for bracket in cfg:
        upper = bracket["max"]
        lower = bracket["min"]
        if taxable_salary_khr >= lower and (upper is None or taxable_salary_khr <= upper):
            chosen = bracket
            break
    return chosen


def compute_salary_tax(
    gross_salary: float,
    residency: str,
    spouse_count: int = 0,
    child_count: int = 0,
    fringe_benefit_value: float = 0.0,
    currency: str = "KHR",
    exchange_rate: float = 4000.0,
) -> dict[str, Any]:
    cfg = load_config()["salary_tax"]
    gross_khr = currency_to_khr(gross_salary, currency, exchange_rate)
    fringe_khr = currency_to_khr(fringe_benefit_value, currency, exchange_rate)
    spouse_deduction = to_float(cfg["dependent_deduction_khr"]["spouse"]) * min(max(int(spouse_count), 0), 1)
    child_deduction = to_float(cfg["dependent_deduction_khr"]["child"]) * max(int(child_count), 0)
    dependent_total = spouse_deduction + child_deduction

    residency_norm = residency.strip().lower()
    if residency_norm.startswith("non"):
        salary_tax_khr = gross_khr * cfg["non_resident_rate"]
        bracket = {"min": None, "max": None, "rate": cfg["non_resident_rate"], "quick_deduction": 0}
        taxable_salary_khr = gross_khr
    else:
        taxable_salary_khr = max(gross_khr - dependent_total, 0)
        bracket = salary_tax_bracket(taxable_salary_khr)
        salary_tax_khr = max((taxable_salary_khr * bracket["rate"]) - bracket["quick_deduction"], 0.0)

    fringe_benefit_tax_khr = max(fringe_khr * cfg["fringe_benefit_rate"], 0.0)
    net_salary_khr = max(gross_khr - salary_tax_khr, 0.0)
    salary_tax_native = khr_to_currency(salary_tax_khr, currency, exchange_rate)
    fringe_benefit_tax_native = khr_to_currency(fringe_benefit_tax_khr, currency, exchange_rate)
    net_salary_native = khr_to_currency(net_salary_khr, currency, exchange_rate)

    explanation = [
        "Resident taxpayers use the progressive bracket plus quick deduction (លម្អៀងលើស)."
        if not residency_norm.startswith("non")
        else "Non-resident salary tax is flat 20%.",
        "Fringe benefit tax is calculated separately at 20% and is typically an employer liability."
    ]

    return {
        "gross_salary_khr": gross_khr,
        "fringe_benefit_value_khr": fringe_khr,
        "spouse_deduction_khr": spouse_deduction,
        "child_deduction_khr": child_deduction,
        "dependent_total_khr": dependent_total,
        "taxable_salary_khr": taxable_salary_khr,
        "salary_tax_khr": salary_tax_khr,
        "salary_tax_native": salary_tax_native,
        "fringe_benefit_tax_khr": fringe_benefit_tax_khr,
        "fringe_benefit_tax_native": fringe_benefit_tax_native,
        "net_salary_khr": net_salary_khr,
        "net_salary_native": net_salary_native,
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
        "residency": residency,
        "bracket": bracket,
        "explanation": explanation,
    }


def compute_withholding_tax(amount: float, residency: str, payment_type: str, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    cfg = load_config()["withholding_tax"]
    amount_khr = currency_to_khr(amount, currency, exchange_rate)
    if residency.strip().lower().startswith("non"):
        rate = cfg["non_resident_rate"]
        category = "Non-resident"
    else:
        rate = cfg["resident_rates"].get(payment_type, cfg["resident_rates"].get("Service", 0.15))
        category = payment_type
    tax_khr = max(amount_khr * rate, 0.0)
    return {
        "amount_khr": amount_khr,
        "rate": rate,
        "category": category,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_land_tax(area_m2: float, value_per_m2: float, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    cfg = load_config()["land_tax"]
    value_khr = currency_to_khr(value_per_m2, currency, exchange_rate)
    taxable_area = max(to_float(area_m2) - cfg["exemption_area_m2"], 0.0)
    base_khr = taxable_area * value_khr
    tax_khr = base_khr * cfg["rate"]
    return {
        "total_area_m2": area_m2,
        "taxable_area_m2": taxable_area,
        "value_per_m2_khr": value_khr,
        "tax_base_khr": base_khr,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
    }


def compute_stamp_duty(property_value: float, scenario: str, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    cfg = load_config()["stamp_duty"]
    value_khr = currency_to_khr(property_value, currency, exchange_rate)
    rate = cfg["rate"]
    deduction = 0.0
    tax_khr = 0.0

    s = scenario.strip().lower()
    if s in {"full exemption", "concession/state/diplomatic", "inheritance close family", "first gift close family"}:
        deduction = value_khr
        tax_khr = 0.0
        label = "Fully exempt"
    elif s == "second+ gift close family":
        deduction = cfg["family_deductions_khr"]["second_plus_gift"]
        tax_khr = max((value_khr - deduction) * rate, 0.0)
        label = "Gift (2nd+ within close family)"
    elif s == "inlaws/siblings inheritance":
        deduction = cfg["family_deductions_khr"]["inlaws_siblings_inheritance"]
        tax_khr = max((value_khr - deduction) * rate, 0.0)
        label = "Inheritance (in-laws / siblings)"
    elif s == "inlaws/siblings gift":
        deduction = cfg["family_deductions_khr"]["inlaws_siblings_gift"]
        tax_khr = max((value_khr - deduction) * rate, 0.0)
        label = "Gift (in-laws / siblings)"
    else:
        label = "Standard transfer"
        tax_khr = max(value_khr * rate, 0.0)

    return {
        "property_value_khr": value_khr,
        "deduction_khr": deduction,
        "rate": rate,
        "scenario": label,
        "tax_base_khr": max(value_khr - deduction, 0.0),
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_vat(
    output_taxable_sales: float = 0.0,
    output_rate: float = 0.10,
    eligible_input_vat: float = 0.0,
    mixed_input_vat: float = 0.0,
    taxable_supplies: float = 0.0,
    total_supplies: float = 0.0,
    currency: str = "KHR",
    exchange_rate: float = 4000.0,
    imported_goods_vat: float = 0.0,
) -> dict[str, Any]:
    output_sales_khr = currency_to_khr(output_taxable_sales, currency, exchange_rate)
    eligible_input_khr = currency_to_khr(eligible_input_vat, currency, exchange_rate)
    mixed_input_khr = currency_to_khr(mixed_input_vat, currency, exchange_rate)
    taxable_supplies_khr = currency_to_khr(taxable_supplies, currency, exchange_rate)
    total_supplies_khr = currency_to_khr(total_supplies, currency, exchange_rate)
    import_vat_khr = currency_to_khr(imported_goods_vat, currency, exchange_rate)

    output_vat_khr = max(output_sales_khr * output_rate, 0.0)

    allowed_mixed_khr = 0.0
    ratio = None
    if mixed_input_khr > 0 and total_supplies_khr > 0:
        ratio = taxable_supplies_khr / total_supplies_khr
        if ratio < 0.05:
            allowed_mixed_khr = 0.0
        elif ratio > 0.95:
            allowed_mixed_khr = mixed_input_khr
        else:
            allowed_mixed_khr = mixed_input_khr * ratio

    total_input_credit_khr = eligible_input_khr + allowed_mixed_khr + import_vat_khr
    vat_payable_khr = output_vat_khr - total_input_credit_khr
    carry_forward_khr = -vat_payable_khr if vat_payable_khr < 0 else 0.0

    return {
        "output_taxable_sales_khr": output_sales_khr,
        "output_rate": output_rate,
        "output_vat_khr": output_vat_khr,
        "eligible_input_vat_khr": eligible_input_khr,
        "mixed_input_vat_khr": mixed_input_khr,
        "allowed_mixed_credit_khr": allowed_mixed_khr,
        "imported_goods_vat_khr": import_vat_khr,
        "taxable_supplies_khr": taxable_supplies_khr,
        "total_supplies_khr": total_supplies_khr,
        "mixed_ratio": ratio,
        "input_credit_total_khr": total_input_credit_khr,
        "vat_payable_khr": vat_payable_khr,
        "carry_forward_khr": carry_forward_khr,
        "vat_payable_native": khr_to_currency(vat_payable_khr, currency, exchange_rate),
        "carry_forward_native": khr_to_currency(carry_forward_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_patent_tax(size_or_revenue: str, annual_revenue: float | None = None, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    cfg = load_config()["patent_tax"]
    label = size_or_revenue.strip().lower()
    revenue_khr = currency_to_khr(annual_revenue or 0.0, currency, exchange_rate)
    if annual_revenue is not None and revenue_khr >= cfg["over_10b_threshold_khr"]:
        amount_khr = cfg["large_over_10b"]
        size = "Large (>10b revenue)"
    elif label.startswith("small"):
        amount_khr = cfg["small"]
        size = "Small"
    elif label.startswith("medium"):
        amount_khr = cfg["medium"]
        size = "Medium"
    elif label.startswith("large") and "10b" not in label:
        amount_khr = cfg["large"]
        size = "Large"
    else:
        amount_khr = cfg["large_over_10b"]
        size = "Large (>10b revenue)"
    return {
        "size": size,
        "annual_revenue_khr": revenue_khr,
        "patent_tax_khr": amount_khr,
        "patent_tax_native": khr_to_currency(amount_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_prepayment_income_tax(previous_month_turnover: float, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    rate = load_config()["prepayment_income_tax"]["rate"]
    turnover_khr = currency_to_khr(previous_month_turnover, currency, exchange_rate)
    tax_khr = turnover_khr * rate
    return {
        "turnover_khr": turnover_khr,
        "rate": rate,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_accommodation_tax(accommodation_revenue: float, exempt: bool = False, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    rate = load_config()["accommodation_tax"]["rate"]
    revenue_khr = currency_to_khr(accommodation_revenue, currency, exchange_rate)
    tax_khr = 0.0 if exempt else revenue_khr * rate
    return {
        "revenue_khr": revenue_khr,
        "rate": rate,
        "exempt": exempt,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_specific_tax(
    category: str,
    supply_value: float,
    supply_type: str = "Domestic goods",
    currency: str = "KHR",
    exchange_rate: float = 4000.0,
) -> dict[str, Any]:
    cfg = load_config()["specific_tax"]
    rates = cfg["rates"]
    rate = rates.get(category, 0.0)
    value_khr = currency_to_khr(supply_value, currency, exchange_rate)
    stype = supply_type.strip().lower()
    if "import" in stype:
        tax_base_khr = value_khr
        basis = "Imported goods"
    elif "service" in stype:
        tax_base_khr = value_khr
        basis = "Services"
    else:
        tax_base_khr = value_khr * cfg["domestic_goods_base_multiplier"]
        basis = "Domestic goods (90% base)"
    tax_khr = tax_base_khr * rate
    return {
        "category": category,
        "basis": basis,
        "supply_value_khr": value_khr,
        "tax_base_khr": tax_base_khr,
        "rate": rate,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_public_lighting_tax(base_value: float, product_category: str, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    rate = load_config()["public_lighting_tax"]["rate"]
    base_khr = currency_to_khr(base_value, currency, exchange_rate)
    tax_khr = base_khr * rate
    return {
        "product_category": product_category,
        "base_khr": base_khr,
        "rate": rate,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_vehicle_road_tax(engine_capacity_cc: int, vehicle_age: str, category_override: str = "", custom_tax: float | None = None, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    cfg = load_config()["vehicle_tax"]["annual_road_tax"]
    age = vehicle_age.strip().lower()
    if custom_tax is not None:
        tax_khr = currency_to_khr(custom_tax, currency, exchange_rate)
        label = "Custom"
    else:
        if engine_capacity_cc < 1500:
            tax_khr = cfg["under_1500_new"] if age == "new" else cfg["under_1500_old"]
            label = "< 1500cc"
        elif 2000 <= engine_capacity_cc <= 2900:
            tax_khr = cfg["2000_2900_new"] if age == "new" else cfg["2000_2900_old"]
            label = "2000–2900cc"
        elif engine_capacity_cc > 4000:
            tax_khr = cfg["over_4000_new"] if age == "new" else cfg["over_4000_old"]
            label = "> 4000cc"
        else:
            tax_khr = currency_to_khr(custom_tax or 0.0, currency, exchange_rate)
            label = "Custom / unsupported band"
    return {
        "label": label,
        "engine_capacity_cc": engine_capacity_cc,
        "vehicle_age": age,
        "tax_khr": tax_khr,
        "tax_native": khr_to_currency(tax_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def compute_vehicle_import_tax(cif_value: float, import_duty_rate: float, special_tax_rate: float, vat_rate: float = 0.10, currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    cif_khr = currency_to_khr(cif_value, currency, exchange_rate)
    import_duty_khr = cif_khr * import_duty_rate
    special_base_khr = cif_khr + import_duty_khr
    special_tax_khr = special_base_khr * special_tax_rate
    vat_base_khr = cif_khr + import_duty_khr + special_tax_khr
    vat_khr = vat_base_khr * vat_rate
    total_khr = import_duty_khr + special_tax_khr + vat_khr
    return {
        "cif_khr": cif_khr,
        "import_duty_rate": import_duty_rate,
        "import_duty_khr": import_duty_khr,
        "special_tax_rate": special_tax_rate,
        "special_tax_khr": special_tax_khr,
        "vat_rate": vat_rate,
        "vat_khr": vat_khr,
        "total_tax_khr": total_khr,
        "total_tax_native": khr_to_currency(total_khr, currency, exchange_rate),
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def batch_salary_payroll(rows: list[dict[str, Any]], currency: str = "KHR", exchange_rate: float = 4000.0) -> dict[str, Any]:
    employees: list[dict[str, Any]] = []
    total_salary_tax = 0.0
    total_fbt = 0.0
    total_gross = 0.0
    total_net = 0.0
    for row in rows:
        result = compute_salary_tax(
            gross_salary=to_float(row.get("gross_salary", 0)),
            residency=str(row.get("residency", "Resident")),
            spouse_count=int(row.get("spouse_count", 0) or 0),
            child_count=int(row.get("child_count", 0) or 0),
            fringe_benefit_value=to_float(row.get("fringe_benefit_value", 0)),
            currency=currency,
            exchange_rate=exchange_rate,
        )
        name = str(row.get("employee_name", "")).strip() or "Unnamed"
        employee = {
            "employee_name": name,
            "residency": row.get("residency", "Resident"),
            "gross_salary_khr": result["gross_salary_khr"],
            "salary_tax_khr": result["salary_tax_khr"],
            "fbt_khr": result["fringe_benefit_tax_khr"],
            "net_salary_khr": result["net_salary_khr"],
            "fringe_benefit_value_khr": result["fringe_benefit_value_khr"],
            "spouse_deduction_khr": result["spouse_deduction_khr"],
            "child_deduction_khr": result["child_deduction_khr"],
            "taxable_salary_khr": result["taxable_salary_khr"],
            "bracket_rate": result["bracket"].get("rate"),
            "quick_deduction": result["bracket"].get("quick_deduction"),
        }
        employees.append(employee)
        total_salary_tax += result["salary_tax_khr"]
        total_fbt += result["fringe_benefit_tax_khr"]
        total_gross += result["gross_salary_khr"]
        total_net += result["net_salary_khr"]
    return {
        "employees": employees,
        "employee_count": len(employees),
        "total_gross_salary_khr": total_gross,
        "total_salary_tax_khr": total_salary_tax,
        "total_fbt_khr": total_fbt,
        "total_net_salary_khr": total_net,
        "currency": currency.upper(),
        "exchange_rate": exchange_rate,
    }


def row_to_result_table(result: dict[str, Any], rows: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for label, value in rows:
        out.append({"Description": label, "Value": value})
    return out
