
# Cambodian Tax Calculator

Streamlit + SQLite tax calculator for:
- Salary Tax + Fringe Benefit Tax
- Business Payroll
- Withholding Tax
- Land Tax
- Stamp Duty
- VAT
- Patent Tax
- Prepayment Income Tax
- Accommodation Tax
- Specific Tax
- Public Lighting Tax
- Vehicle Tax

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- The provided vehicle road-tax table in the source text was partial, so the app includes the exact sample brackets plus a custom override.
- Stamp duty presets are implemented from the supplied notes and are easy to adjust in `config/tax_rates.json`.
- All calculations are saved to SQLite at `data/tax_calculations.sqlite3`.

## Project structure
- `app.py` – Streamlit UI
- `src/tax_logic.py` – tax engines
- `src/db.py` – SQLite storage
- `src/report.py` – PDF/HTML/JSON export
- `config/tax_rates.json` – editable tax rates
