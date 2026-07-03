from datetime import date
from io import BytesIO
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Expense, FuelEntry, MaintenanceEntry, TireEvent, Vehicle

ORANGE = colors.HexColor("#ff6a00")
CHARCOAL = colors.HexColor("#1a1a1a")
GRAY = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f1f5f9")

SPEC_LABELS = [
    ("engine_model", "Engine"),
    ("engine_displacement_l", "Displacement (L)"),
    ("engine_cylinders", "Cylinders"),
    ("engine_hp", "Horsepower"),
    ("fuel_type", "Fuel"),
    ("drive_type", "Drive Type"),
    ("transmission_type", "Transmission"),
    ("body_class", "Body"),
    ("trim", "Trim"),
    ("gvwr", "GVWR"),
]


def _fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def _fmt_date(d) -> str:
    if isinstance(d, date):
        return d.strftime("%b %d, %Y")
    return str(d)


def _section_table(data: List[List], col_widths: List[float]) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CHARCOAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def build_vehicle_report(
    vehicle: Vehicle,
    fuel_entries: List[FuelEntry],
    maint_entries: List[MaintenanceEntry],
    expenses: List[Expense],
    tire_events: Optional[List[TireEvent]] = None,
) -> bytes:
    """Render a full vehicle history report as PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title=f"Vehicle Report — {vehicle.year} {vehicle.make} {vehicle.model}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TTitle", parent=styles["Title"], textColor=CHARCOAL, fontSize=20, spaceAfter=2)
    sub_style = ParagraphStyle("TSub", parent=styles["Normal"], textColor=GRAY, fontSize=9, spaceAfter=10)
    h2 = ParagraphStyle("TH2", parent=styles["Heading2"], textColor=ORANGE, fontSize=13, spaceBefore=14, spaceAfter=6)
    cell = ParagraphStyle("TCell", parent=styles["Normal"], fontSize=8, leading=10)

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    name = vehicle.nickname or f"{vehicle.year} {vehicle.make} {vehicle.model}"
    story.append(Paragraph(name, title_style))
    sub_parts = [f"{vehicle.year} {vehicle.make} {vehicle.model}"]
    if vehicle.vin:
        sub_parts.append(f"VIN {vehicle.vin}")
    if vehicle.license_plate:
        sub_parts.append(f"Plate {vehicle.license_plate}")
    sub_parts.append(f"Odometer {vehicle.current_mileage:,.0f} mi")
    sub_parts.append(f"Generated {_fmt_date(date.today())}")
    story.append(Paragraph(" &nbsp;•&nbsp; ".join(sub_parts), sub_style))

    # ── Specs ───────────────────────────────────────────────────────────────
    specs = dict(vehicle.nhtsa_data or {})
    specs.update(vehicle.specs_overrides or {})
    spec_rows = [(label, str(specs[key])) for key, label in SPEC_LABELS if specs.get(key)]
    if spec_rows:
        story.append(Paragraph("Vehicle Specifications", h2))
        half = (len(spec_rows) + 1) // 2
        left, right = spec_rows[:half], spec_rows[half:]
        rows = []
        for i in range(half):
            row = [left[i][0], left[i][1]]
            row += [right[i][0], right[i][1]] if i < len(right) else ["", ""]
            rows.append(row)
        spec_table = Table(rows, colWidths=[1.3 * inch, 2.25 * inch, 1.3 * inch, 2.25 * inch])
        spec_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
            ("TEXTCOLOR", (2, 0), (2, -1), GRAY),
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(spec_table)

    # ── Cost summary ─────────────────────────────────────────────────────────
    fuel_cost = sum(e.cost for e in fuel_entries)
    maint_cost = sum(e.cost for e in maint_entries)
    other_cost = sum(e.amount for e in expenses if e.category != "fuel")
    total_cost = fuel_cost + maint_cost + other_cost
    mileages = [e.mileage for e in list(fuel_entries) + list(maint_entries) if e.mileage and e.mileage > 0]
    miles_tracked = max(mileages) - min(mileages) if len(mileages) >= 2 else 0
    mpg_values = [e.mpg for e in fuel_entries if e.mpg is not None]
    avg_mpg = sum(mpg_values) / len(mpg_values) if mpg_values else None

    story.append(Paragraph("Ownership Cost Summary", h2))
    summary_rows = [
        ["Fuel", "Maintenance", "Other Expenses", "Total", "Miles Tracked", "Cost / Mile", "Avg MPG"],
        [
            _fmt_money(fuel_cost),
            _fmt_money(maint_cost),
            _fmt_money(other_cost),
            _fmt_money(total_cost),
            f"{miles_tracked:,.0f}" if miles_tracked else "—",
            _fmt_money(total_cost / miles_tracked) if miles_tracked else "—",
            f"{avg_mpg:.1f}" if avg_mpg else "—",
        ],
    ]
    story.append(_section_table(summary_rows, [1.02 * inch] * 7))

    # ── Maintenance history ──────────────────────────────────────────────────
    story.append(Paragraph("Maintenance History", h2))
    if maint_entries:
        rows = [["Date", "Mileage", "Service", "Provider", "Cost", "Notes"]]
        for e in sorted(maint_entries, key=lambda x: x.date, reverse=True):
            rows.append([
                _fmt_date(e.date),
                f"{e.mileage:,.0f}" if e.mileage else "—",
                Paragraph(e.type or "", cell),
                Paragraph(e.service_provider or "", cell),
                _fmt_money(e.cost or 0),
                Paragraph(e.notes or "", cell),
            ])
        story.append(_section_table(rows, [0.85 * inch, 0.7 * inch, 1.5 * inch, 1.2 * inch, 0.7 * inch, 2.2 * inch]))
    else:
        story.append(Paragraph("No maintenance records.", sub_style))

    # ── Expenses ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Expenses", h2))
    if expenses:
        rows = [["Date", "Category", "Description", "Amount"]]
        for e in sorted(expenses, key=lambda x: x.date, reverse=True):
            rows.append([
                _fmt_date(e.date),
                (e.category or "").capitalize(),
                Paragraph(e.description or "", cell),
                _fmt_money(e.amount or 0),
            ])
        story.append(_section_table(rows, [0.95 * inch, 1.1 * inch, 4.1 * inch, 1.0 * inch]))
    else:
        story.append(Paragraph("No expense records.", sub_style))

    # ── Tire history ─────────────────────────────────────────────────────────
    installs = [e for e in (tire_events or []) if e.event_type == "install"]
    if installs:
        story.append(Paragraph("Tire History", h2))
        rows = [["Date", "Mileage", "Brand", "Size"]]
        for e in sorted(installs, key=lambda x: x.date, reverse=True):
            rows.append([_fmt_date(e.date), f"{e.mileage:,.0f}" if e.mileage else "—", e.brand or "—", e.size or "—"])
        story.append(_section_table(rows, [1.2 * inch, 1.0 * inch, 2.5 * inch, 2.45 * inch]))

    # ── Fuel log ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Fuel Log", h2))
    if fuel_entries:
        rows = [["Date", "Mileage", "Gallons", "Cost", "MPG", "Location"]]
        for e in sorted(fuel_entries, key=lambda x: x.date, reverse=True):
            rows.append([
                _fmt_date(e.date),
                f"{e.mileage:,.0f}",
                f"{e.gallons:.2f}",
                _fmt_money(e.cost or 0),
                f"{e.mpg:.1f}" if e.mpg else "—",
                Paragraph(e.location or "", cell),
            ])
        story.append(_section_table(rows, [0.85 * inch, 0.75 * inch, 0.7 * inch, 0.75 * inch, 0.6 * inch, 3.5 * inch]))
    else:
        story.append(Paragraph("No fuel records.", sub_style))

    story.append(Spacer(1, 18))
    story.append(Paragraph("Generated by Tracktion — self-hosted vehicle maintenance tracking", sub_style))

    doc.build(story)
    return buf.getvalue()
