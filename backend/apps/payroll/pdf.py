"""PDF documents (ReportLab): payslips, payroll summaries, tabular reports and salary statements."""
import io
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.models import CompanySettings

NAVY = colors.HexColor("#13315C")
GOLD = colors.HexColor("#E0A100")
LIGHT = colors.HexColor("#EEF2F7")
GREY = colors.HexColor("#5B6573")

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_styles["Heading1"], textColor=NAVY, fontSize=15, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=_styles["Heading3"], textColor=NAVY, fontSize=10.5, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("body", parent=_styles["BodyText"], fontSize=8.5, leading=11)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7, textColor=GREY, leading=9)
RIGHT = ParagraphStyle("right", parent=BODY, alignment=TA_RIGHT)


def fmt(value, currency=""):
    if value is None or value == "":
        return "-"
    v = Decimal(str(value))
    s = f"{abs(v):,.2f}"
    s = f"({s})" if v < 0 else s
    return f"{currency} {s}".strip()


def _header(company, title, subtitle=""):
    logo = None
    if company.logo:
        try:
            logo = Image(company.logo.path, width=22 * mm, height=22 * mm, kind="proportional")
        except Exception:
            logo = None
    if logo is None:
        logo = Table([[Paragraph("<font color='white'><b>B</b></font>",
                                 ParagraphStyle("lg", fontSize=20, alignment=1, leading=24))]],
                     colWidths=[16 * mm], rowHeights=[16 * mm])
        logo.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    info = [
        Paragraph(f"<b>{company.name}</b>", ParagraphStyle("cn", parent=BODY, fontSize=12, textColor=NAVY, leading=15)),
        Paragraph((company.address or "").replace("\n", "<br/>"), SMALL),
        Paragraph(" | ".join(x for x in [company.phone, company.email, f"TIN: {company.tin}" if company.tin else ""] if x), SMALL),
    ]
    right = [Paragraph(f"<b>{title}</b>", ParagraphStyle("t", parent=H1, alignment=TA_RIGHT)),
             Paragraph(subtitle, ParagraphStyle("st", parent=SMALL, alignment=TA_RIGHT))]
    t = Table([[logo, info, right]], colWidths=[22 * mm, None, 70 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, GOLD),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _footer_cb(text):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(GREY)
        w, _ = doc.pagesize
        canvas.drawString(doc.leftMargin, 10 * mm, text[:180])
        canvas.drawRightString(w - doc.rightMargin, 10 * mm,
                               f"Generated {timezone.localtime():%d/%m/%Y %H:%M} | Page {doc.page}")
        canvas.restoreState()
    return draw


def _doc(buf, pagesize=A4):
    return SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=14 * mm, rightMargin=14 * mm,
                             topMargin=12 * mm, bottomMargin=18 * mm)


def _amount_table(rows, total_label=None, total_value=None, currency="TZS"):
    data = [[Paragraph(str(n), BODY), Paragraph(fmt(v), RIGHT)] for n, v in rows] or [[Paragraph("None", SMALL), ""]]
    if total_label:
        data.append([Paragraph(f"<b>{total_label}</b>", BODY), Paragraph(f"<b>{fmt(total_value)}</b>", RIGHT)])
    t = Table(data, colWidths=[None, 32 * mm])
    style = [("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if total_label:
        style += [("BACKGROUND", (0, -1), (-1, -1), LIGHT), ("LINEABOVE", (0, -1), (-1, -1), 0.8, NAVY)]
    t.setStyle(TableStyle(style))
    return t


def _section(title, table):
    return [Paragraph(title, H2), table]


def payslip_pdf(item, payslip_number):
    """Render a single employee payslip for a PayrollItem."""
    company = CompanySettings.load()
    period = item.run.period
    buf = io.BytesIO()
    doc = _doc(buf)
    cur = company.currency
    lines = list(item.lines.all())
    earnings = [l for l in lines if l.category == "EARNING"]
    allowances = [(l.name, l.amount) for l in earnings if l.sub_category == "ALLOWANCE"]
    basic = [(l.name, l.amount) for l in earnings if l.source_type in ("SALARY", "LEAVE")]
    other_earn = [(l.name, l.amount) for l in earnings if l.source_type not in ("SALARY", "LEAVE")
                  and l.sub_category != "ALLOWANCE"]
    deductions = [l for l in lines if l.category == "DEDUCTION"]
    tax = [(l.name, l.amount) for l in deductions if l.sub_category == "TAX"]
    statutory = [(l.name, l.amount) for l in deductions if l.is_statutory and l.sub_category != "TAX"]
    other_ded = [(l.name, l.amount) for l in deductions if not l.is_statutory]
    employer = [(l.name, l.amount) for l in lines if l.category == "EMPLOYER"]

    story = [_header(company, "PAYSLIP", f"{period.name} &nbsp;|&nbsp; No. {payslip_number}"), Spacer(1, 5)]
    emp_rows = [
        ["Employee name", item.employee_name, "Employee ID", item.employee_number],
        ["Department", item.department_name, "Job title", item.job_title or "-"],
        ["Pay period", f"{period.start_date:%d/%m/%Y} - {period.end_date:%d/%m/%Y}", "Pay date",
         f"{period.pay_date:%d/%m/%Y}" if period.pay_date else "-"],
        ["TIN", item.tin or "-", "Social security no.", item.social_security_number or "-"],
        ["Days employed", f"{item.days_employed} of {item.days_in_period}", "Monthly basic", fmt(item.monthly_basic_salary, cur)],
    ]
    t = Table([[Paragraph(f"<b>{a}</b>", SMALL), Paragraph(str(b), BODY), Paragraph(f"<b>{c}</b>", SMALL),
                Paragraph(str(d), BODY)] for a, b, c, d in emp_rows], colWidths=[28 * mm, None, 30 * mm, None])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                           ("BACKGROUND", (2, 0), (2, -1), LIGHT), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    story.append(t)

    left = []
    left += _section("Basic salary", _amount_table(basic))
    left += _section("Allowances", _amount_table(allowances))
    left += _section("Other earnings", _amount_table(other_earn, "Gross salary", item.gross_earnings))
    right = []
    right += _section("Tax (PAYE)", _amount_table(tax))
    right += _section("Statutory deductions", _amount_table(statutory))
    right += _section("Other deductions", _amount_table(other_ded, "Total deductions", item.total_deductions))
    cols = Table([[left, right]], colWidths=["50%", "50%"])
    cols.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (0, -1), 6), ("LEFTPADDING", (1, 0), (1, -1), 6)]))
    story += [Spacer(1, 4), cols, Spacer(1, 8)]

    net = Table([[Paragraph("<font color='white'><b>NET SALARY</b></font>", BODY),
                  Paragraph(f"<font color='white' size='12'><b>{fmt(item.net_salary, cur)}</b></font>", RIGHT)]],
                colWidths=[None, 60 * mm], rowHeights=[11 * mm])
    net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LINEBELOW", (0, 0), (-1, -1), 2, GOLD)]))
    story.append(net)

    pay = getattr(item, "payment", None)
    pay_rows = [
        ("Payment method", item.get_payment_method_display()),
        ("Bank", item.bank_name or "-"),
        ("Account", _mask(item.bank_account_number or item.mobile_money_number)),
        ("Payment status", pay.get_status_display() if pay else "Pending"),
        ("Reference", (pay.reference if pay and pay.reference else "-")),
    ]
    pt = Table([[Paragraph(f"<b>{a}</b>", SMALL), Paragraph(str(b), BODY)] for a, b in pay_rows], colWidths=[30 * mm, None])
    employer_block = _amount_table(employer, "Employer contributions", item.total_employer_contributions)
    bottom = Table([[[Paragraph("Payment information", H2), pt],
                     [Paragraph("Employer contributions (not deducted from pay)", H2), employer_block]]],
                   colWidths=["50%", "50%"])
    bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [Spacer(1, 6), bottom, Spacer(1, 10), Paragraph(company.payslip_footer, SMALL)]
    doc.build(story, onFirstPage=_footer_cb(company.name), onLaterPages=_footer_cb(company.name))
    return buf.getvalue()


def _mask(account):
    if not account:
        return "-"
    return ("*" * max(len(account) - 4, 0)) + account[-4:]


def table_report_pdf(title, subtitle, headers, rows, totals=None, landscape_mode=False, notes=None, col_widths=None):
    """Generic tabular report. `rows` are lists of display values; numeric cells are right-aligned."""
    company = CompanySettings.load()
    buf = io.BytesIO()
    doc = _doc(buf, landscape(A4) if landscape_mode else A4)
    story = [_header(company, title, subtitle), Spacer(1, 6)]

    def cell(v):
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            return Paragraph(fmt(v) if not isinstance(v, int) else f"{v:,}", RIGHT)
        return Paragraph(str(v if v is not None else "-"), BODY)

    data = [[Paragraph(f"<font color='white'><b>{h}</b></font>", BODY) for h in headers]]
    data += [[cell(v) for v in r] for r in rows]
    if totals:
        data.append([Paragraph(f"<b>{fmt(v) if isinstance(v, Decimal) else (v if v is not None else '')}</b>",
                               RIGHT if isinstance(v, Decimal) else BODY) for v in totals])
    t = Table(data, repeatRows=1, colWidths=col_widths)
    style = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
             ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if totals:
        style += [("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FFF4D6")), ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY)]
    t.setStyle(TableStyle(style))
    story.append(t)
    for n in notes or []:
        story += [Spacer(1, 4), Paragraph(n, SMALL)]
    story += [Spacer(1, 6), Paragraph(company.statutory_disclaimer, SMALL)]
    doc.build(story, onFirstPage=_footer_cb(f"{company.name} - {title}"), onLaterPages=_footer_cb(f"{company.name} - {title}"))
    return buf.getvalue()


def summary_pdf(title, subtitle, kv_rows, table=None):
    """Key/value summary followed by an optional table (headers, rows, totals)."""
    company = CompanySettings.load()
    buf = io.BytesIO()
    doc = _doc(buf)
    story = [_header(company, title, subtitle), Spacer(1, 6)]
    kv = Table([[Paragraph(f"<b>{k}</b>", BODY), Paragraph(fmt(v) if isinstance(v, Decimal) else str(v), RIGHT)]
                for k, v in kv_rows], colWidths=[None, 50 * mm])
    kv.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                            ("BACKGROUND", (0, 0), (0, -1), LIGHT)]))
    story.append(kv)
    if table:
        headers, rows, totals = table
        data = [[Paragraph(f"<font color='white'><b>{h}</b></font>", BODY) for h in headers]]
        data += [[Paragraph(fmt(v), RIGHT) if isinstance(v, Decimal) else Paragraph(str(v), BODY) for v in r] for r in rows]
        if totals:
            data.append([Paragraph(f"<b>{fmt(v)}</b>", RIGHT) if isinstance(v, Decimal) else Paragraph(f"<b>{v}</b>", BODY)
                         for v in totals])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT])]))
        story += [Spacer(1, 8), t]
    story += [Spacer(1, 6), Paragraph(company.statutory_disclaimer, SMALL)]
    doc.build(story, onFirstPage=_footer_cb(f"{company.name} - {title}"), onLaterPages=_footer_cb(f"{company.name} - {title}"))
    return buf.getvalue()
