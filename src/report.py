
from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from typing import Any

def result_to_markdown(module: str, title: str, input_data: dict[str, Any], result_data: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        f"**Module:** {module}",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Inputs",
        "```json",
        json.dumps(input_data, ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "## Result",
        "```json",
        json.dumps(result_data, ensure_ascii=False, indent=2, default=str),
        "```",
    ]
    return "\n".join(lines)

def result_to_html(module: str, title: str, input_data: dict[str, Any], result_data: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ font-family: Arial, sans-serif; padding: 24px; color: #1f2937; }}
h1, h2 {{ color: #0f172a; }}
pre {{ background: #f8fafc; padding: 12px; border-radius: 10px; overflow-x: auto; }}
.badge {{ display:inline-block; padding:4px 10px; border-radius:999px; background:#e2e8f0; margin-bottom:8px; }}
</style>
</head>
<body>
<div class="badge">{module}</div>
<h1>{title}</h1>
<p><b>Generated:</b> {datetime.now().isoformat()}</p>
<h2>Inputs</h2>
<pre>{json.dumps(input_data, ensure_ascii=False, indent=2, default=str)}</pre>
<h2>Result</h2>
<pre>{json.dumps(result_data, ensure_ascii=False, indent=2, default=str)}</pre>
</body>
</html>"""

def result_to_pdf_bytes(module: str, title: str, input_data: dict[str, Any], result_data: dict[str, Any]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
    except Exception:
        return result_to_html(module, title, input_data, result_data).encode("utf-8")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Module: {module}", styles["Normal"]),
        Paragraph(f"Generated: {datetime.now().isoformat()}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
        Paragraph("Inputs", styles["Heading2"]),
        Preformatted(json.dumps(input_data, ensure_ascii=False, indent=2, default=str), styles["Code"]),
        Spacer(1, 0.2 * inch),
        Paragraph("Result", styles["Heading2"]),
        Preformatted(json.dumps(result_data, ensure_ascii=False, indent=2, default=str), styles["Code"]),
    ]
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
