"""Pure-Python Vector PDF Report Builder using ReportLab for Pusher load runs."""

from __future__ import annotations

import io
import re
from typing import Any

from reportlab.graphics.shapes import Drawing, Line, Polygon, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.core.crash_diagnosis import compute_crash_diagnosis


_GREEN_SOFT = colors.HexColor("#f0fdf4")
_AMBER_SOFT = colors.HexColor("#fffbeb")
_RED_SOFT = colors.HexColor("#fef2f2")
_SAGE_FILL = colors.Color(0.525, 0.937, 0.675, alpha=0.35)
_SAGE_STROKE = colors.HexColor("#16a34a")
_FOREST_LINE = colors.HexColor("#14532d")
_CORAL_LINE = colors.HexColor("#dc2626")
_CRIMSON_PIN = colors.HexColor("#991b1b")
_CHARCOAL = colors.HexColor("#111827")
_SLATE_MUTED = colors.HexColor("#4b5563")
_BORDER_INK = colors.HexColor("#111111")
_HEADER_SAGE_BG = colors.HexColor("#ecfdf5")


def safe_pdf_slug(value: str, fallback: str = "project") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-._").lower()
    return cleaned[:48] or fallback


def _status_colors(label: str) -> tuple[colors.Color, colors.Color, colors.Color]:
    upper = str(label or "SMOOTH").upper()
    if "CRASH" in upper or "FAIL" in upper:
        return colors.HexColor("#fee2e2"), colors.HexColor("#991b1b"), colors.HexColor("#dc2626")
    if "SLOW" in upper:
        return colors.HexColor("#fef3c7"), colors.HexColor("#92400e"), colors.HexColor("#d97706")
    return colors.HexColor("#dcfce7"), colors.HexColor("#14532d"), colors.HexColor("#16a34a")


def _normalize_points(run: dict[str, Any]) -> list[dict[str, float]]:
    raw = run.get("timeline_points") or run.get("timeseries") or []
    pts: list[dict[str, float]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        pts.append({
            "t": float(item.get("t", item.get("elapsed_sec", idx)) or idx),
            "vus": max(0.0, float(item.get("vus", item.get("active_vus", 0)) or 0.0)),
            "rps": max(0.0, float(item.get("rps", item.get("live_rps", 0)) or 0.0)),
            "p95_ms": max(0.0, float(item.get("p95_ms", 0.0) or 0.0)),
            "error_pct": max(0.0, min(100.0, float(item.get("error_pct", 0.0) or 0.0))),
        })
    pts.sort(key=lambda p: p["t"])
    return pts


def _build_vector_chart(
    points: list[dict[str, float]],
    crash_summary: dict[str, Any],
    width: float = 490.0,
    height: float = 175.0,
) -> Drawing:
    drawing = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 42.0, 42.0, 22.0, 26.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    # Soft stability zone bands (bottom-to-top in ReportLab coordinates: y=0 at bottom)
    smooth_h = plot_h * 0.40
    slow_h = plot_h * 0.30
    crash_h = plot_h * 0.30
    drawing.add(Rect(pad_l, pad_b, plot_w, smooth_h, fillColor=_GREEN_SOFT, strokeWidth=0))
    drawing.add(Rect(pad_l, pad_b + smooth_h, plot_w, slow_h, fillColor=_AMBER_SOFT, strokeWidth=0))
    drawing.add(Rect(pad_l, pad_b + smooth_h + slow_h, plot_w, crash_h, fillColor=_RED_SOFT, strokeWidth=0))

    # Zone labels
    drawing.add(String(pad_l + 5, pad_b + smooth_h + slow_h + crash_h - 11, "CRASHING / OVERLOADED", fontSize=6.5, fillColor=_CRIMSON_PIN, fontName="Helvetica-Bold"))
    drawing.add(String(pad_l + 5, pad_b + smooth_h + slow_h - 11, "SLOWING", fontSize=6.5, fillColor=colors.HexColor("#92400e"), fontName="Helvetica-Bold"))
    drawing.add(String(pad_l + 5, pad_b + 5, "SMOOTH", fontSize=6.5, fillColor=_FOREST_LINE, fontName="Helvetica-Bold"))

    # Legend above chart
    drawing.add(Rect(pad_l, height - 13, 8, 6, fillColor=_SAGE_FILL, strokeColor=_SAGE_STROKE, strokeWidth=0.6))
    drawing.add(String(pad_l + 11, height - 12, "Active Users (VUs)", fontSize=6.5, fillColor=_CHARCOAL))
    drawing.add(Line(pad_l + 96, height - 10, pad_l + 108, height - 10, strokeColor=_FOREST_LINE, strokeWidth=1.8))
    drawing.add(String(pad_l + 111, height - 12, "Response Time (Lower = Better)", fontSize=6.5, fillColor=_CHARCOAL))
    drawing.add(Line(pad_l + 240, height - 10, pad_l + 252, height - 10, strokeColor=_CORAL_LINE, strokeWidth=1.8))
    drawing.add(String(pad_l + 255, height - 12, "Errors / Failures (%)", fontSize=6.5, fillColor=_CHARCOAL))

    # Outer frame
    drawing.add(Rect(pad_l, pad_b, plot_w, plot_h, fillColor=None, strokeColor=_BORDER_INK, strokeWidth=0.9))

    if not points:
        drawing.add(String(pad_l + plot_w / 2, pad_b + plot_h / 2, "No timeline points recorded for this run.", fontSize=8, fillColor=_SLATE_MUTED, textAnchor="middle"))
        return drawing

    min_t = points[0]["t"]
    max_t = max(min_t + 1.0, points[-1]["t"])
    span_t = max(1.0, max_t - min_t)
    max_vus = max(10.0, *(p["vus"] for p in points))
    max_p95 = max(200.0, *(p["p95_ms"] for p in points))
    max_err = max(10.0, *(p["error_pct"] for p in points))

    def x_for(t_val: float) -> float:
        return pad_l + ((t_val - min_t) / span_t) * plot_w

    def y_vus(v_val: float) -> float:
        return pad_b + (v_val / max_vus) * plot_h * 0.85

    def y_p95(ms_val: float) -> float:
        return pad_b + (ms_val / max_p95) * plot_h

    def y_err(err_val: float) -> float:
        return pad_b + (err_val / max_err) * plot_h

    # Y-axis labels
    drawing.add(String(pad_l - 4, pad_b + plot_h - 4, f"{int(round(max_p95))}ms", fontSize=6.5, fillColor=_FOREST_LINE, textAnchor="end"))
    drawing.add(String(pad_l - 4, pad_b + plot_h * 0.5 - 2, f"{int(round(max_p95 / 2))}ms", fontSize=6.5, fillColor=_FOREST_LINE, textAnchor="end"))
    drawing.add(String(pad_l - 4, pad_b, "0ms", fontSize=6.5, fillColor=_FOREST_LINE, textAnchor="end"))

    drawing.add(String(width - pad_r + 4, pad_b + plot_h - 4, f"{int(round(max_err))}%", fontSize=6.5, fillColor=_CORAL_LINE, textAnchor="start"))
    drawing.add(String(width - pad_r + 4, pad_b + plot_h * 0.5 - 2, f"{int(round(max_err / 2))}%", fontSize=6.5, fillColor=_CORAL_LINE, textAnchor="start"))
    drawing.add(String(width - pad_r + 4, pad_b, "0% err", fontSize=6.5, fillColor=_CORAL_LINE, textAnchor="start"))

    # X-axis labels
    drawing.add(String(pad_l, pad_b - 11, f"{int(round(min_t))}s", fontSize=6.5, fillColor=_CHARCOAL, textAnchor="start"))
    drawing.add(String(pad_l + plot_w * 0.5, pad_b - 11, f"{int(round(min_t + span_t * 0.5))}s", fontSize=6.5, fillColor=_CHARCOAL, textAnchor="middle"))
    drawing.add(String(pad_l + plot_w, pad_b - 11, f"{int(round(max_t))}s", fontSize=6.5, fillColor=_CHARCOAL, textAnchor="end"))

    # Active Users Shaded Area Polygon
    vu_coords: list[float] = [x_for(points[0]["t"]), pad_b]
    vu_line_coords: list[float] = []
    p95_coords: list[float] = []
    err_coords: list[float] = []
    for pt in points:
        px = x_for(pt["t"])
        yv = y_vus(pt["vus"])
        vu_coords.extend([px, yv])
        vu_line_coords.extend([px, yv])
        p95_coords.extend([px, y_p95(pt["p95_ms"])])
        err_coords.extend([px, y_err(pt["error_pct"])])
    vu_coords.extend([x_for(points[-1]["t"]), pad_b])

    drawing.add(Polygon(vu_coords, fillColor=_SAGE_FILL, strokeWidth=0))
    if len(vu_line_coords) >= 4:
        drawing.add(PolyLine(vu_line_coords, strokeColor=_SAGE_STROKE, strokeWidth=0.9, strokeDashArray=[2, 2]))
    if len(p95_coords) >= 4:
        drawing.add(PolyLine(p95_coords, strokeColor=_FOREST_LINE, strokeWidth=1.8))
    if len(err_coords) >= 4:
        drawing.add(PolyLine(err_coords, strokeColor=_CORAL_LINE, strokeWidth=1.6))

    # Breaking Point Vertical Marker
    first_err_sec = crash_summary.get("first_error_sec")
    first_err_vus = crash_summary.get("first_error_vus")
    if first_err_sec is not None and min_t <= float(first_err_sec) <= max_t:
        bx = x_for(float(first_err_sec))
        drawing.add(Line(bx, pad_b, bx, pad_b + plot_h, strokeColor=_CRIMSON_PIN, strokeWidth=1.2, strokeDashArray=[3, 2]))
        badge_w = 115.0
        badge_x = min(pad_l + plot_w - badge_w - 2, max(pad_l + 2, bx - badge_w / 2))
        badge_y = pad_b + plot_h - 16
        drawing.add(Rect(badge_x, badge_y, badge_w, 12, fillColor=_CRIMSON_PIN, strokeWidth=0))
        drawing.add(String(badge_x + badge_w / 2, badge_y + 3.5, f"Started failing: {first_err_vus or '?'} users", fontSize=6.5, fontName="Helvetica-Bold", fillColor=colors.white, textAnchor="middle"))

    return drawing


def generate_run_pdf_bytes(run: dict[str, Any]) -> bytes:
    """Render a classy vector-charted PDF report for a saved Pusher test run."""
    buffer = io.BytesIO()
    run_id = str(run.get("run_id") or run.get("id") or "RUN-UNKNOWN")
    project_name = str(run.get("project_name") or "").strip() or "Unnamed Project"
    target_url = str(run.get("target_url") or run.get("target") or "N/A")
    mode = str(run.get("mode") or "Load Test")
    timestamp = str(run.get("timestamp") or run.get("started_at") or "")
    guard_id = str(run.get("guard_id") or "PG-ACTIVE")
    ram_limit = run.get("ram_limit_mb")

    breakdown = run.get("failure_breakdown") if isinstance(run.get("failure_breakdown"), list) else []
    crash_summary = run.get("crash_summary") if isinstance(run.get("crash_summary"), dict) else None
    points = _normalize_points(run)

    if crash_summary is None:
        _, crash_summary = compute_crash_diagnosis(
            [],
            timeseries=points,
            peak_vus=int(run.get("peak_vus") or 0),
            target_vus=int(run.get("target_vus") or 0),
            total_requests=int(run.get("total_requests") or 0),
            failed_requests=int(run.get("failed_requests") or 0),
            overall_p95_ms=float(run.get("p95_ms") or 0.0),
            p95_ceiling_ms=float(run.get("effective_p95_ceiling_ms") or run.get("p95_ceiling_ms") or 1500.0),
            circuit_status=str(run.get("status_label") or ""),
        )

    status_label = str(crash_summary.get("status_label") or "SMOOTH")
    bg_pill, fg_pill, border_pill = _status_colors(status_label)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PusherTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=_CHARCOAL, spaceAfter=2, leading=21)
    meta_style = ParagraphStyle("PusherMeta", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, textColor=_SLATE_MUTED, leading=11)
    section_hdr = ParagraphStyle("SectionHdr", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, textColor=_CHARCOAL, spaceBefore=8, spaceAfter=4)
    cell_style = ParagraphStyle("CellTxt", parent=styles["Normal"], fontName="Helvetica", fontSize=7.8, textColor=_CHARCOAL, leading=9.5)
    cell_bold = ParagraphStyle("CellBold", parent=cell_style, fontName="Helvetica-Bold")
    verdict_style = ParagraphStyle("VerdictBox", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.2, textColor=fg_pill, leading=12.5)

    def _draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(_SLATE_MUTED)
        ram_note = f"RAM Budget: {ram_limit} MB | " if ram_limit else ""
        canvas_obj.drawString(16 * mm, 11 * mm, f"PUSHER Performance Report  |  Guard: {guard_id}  |  {ram_note}4 KB Chunk-Discard Active")
        canvas_obj.drawRightString(A4[0] - 16 * mm, 11 * mm, f"Page {doc_obj.page}")
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title=f"Pusher Report - {project_name} ({run_id})",
    )

    story: list[Any] = []

    # 1. Project Header Banner
    header_data = [[
        [
            Paragraph(f"<font size='8' color='#14532d'><b>PUSHER LOAD REPORT</b></font>", meta_style),
            Paragraph(project_name, title_style),
            Paragraph(f"Target: <font name='Courier'>{target_url}</font>", meta_style),
            Paragraph(f"Run ID: <b>{run_id}</b>  ·  Mode: <b>{mode}</b>  ·  Time: {timestamp}  ·  Duration: {run.get('elapsed_sec', 0)}s / {run.get('duration_sec', 0)}s", meta_style),
        ],
        Paragraph(f"<b>{status_label}</b>", ParagraphStyle("Pill", fontName="Helvetica-Bold", fontSize=9.5, textColor=fg_pill, alignment=1)),
    ]]
    hdr_table = Table(header_data, colWidths=[136 * mm, 42 * mm])
    hdr_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.white),
        ("BACKGROUND", (1, 0), (1, 0), bg_pill),
        ("BOX", (0, 0), (-1, -1), 1.2, _BORDER_INK),
        ("LINEBEFORE", (1, 0), (1, 0), 1.0, border_pill),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 7))

    # Plain-English Verdict Strip
    verdict_tbl = Table([[Paragraph(crash_summary.get("plain_english_verdict") or "Completed test run.", verdict_style)]], colWidths=[178 * mm])
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_pill),
        ("BOX", (0, 0), (-1, -1), 1.0, border_pill),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(verdict_tbl)
    story.append(Spacer(1, 8))

    # 2. At-a-Glance 4-Box KPI Strip
    safe_vus = crash_summary.get("safe_max_vus") or 0
    peak_vus = run.get("peak_vus") or 0
    total_reqs = int(run.get("total_requests") or 0)
    failed_reqs = int(run.get("failed_requests") or 0)
    p95_val = run.get("p95_ms")
    err_pct = run.get("error_pct")
    kpi_rows = [
        [
            Paragraph("SAFE USER CAPACITY", meta_style),
            Paragraph("PEAK USERS TESTED", meta_style),
            Paragraph("RESPONSE SPEED (P95)", meta_style),
            Paragraph("FAILURE RATE", meta_style),
        ],
        [
            Paragraph(f"<b>{int(safe_vus):,} VUs</b>", ParagraphStyle("K1", fontSize=13, fontName="Helvetica-Bold", textColor=_FOREST_LINE)),
            Paragraph(f"<b>{int(peak_vus):,} VUs</b><br/><font size='7.5' color='#4b5563'>{total_reqs:,} total reqs · {run.get('avg_rps', 0)} avg RPS</font>", ParagraphStyle("K2", fontSize=13, fontName="Helvetica-Bold", textColor=_CHARCOAL, leading=14)),
            Paragraph(f"<b>{p95_val if p95_val is not None else 'N/A'} ms</b><br/><font size='7.5' color='#4b5563'>Peak {run.get('peak_rps', 0)} RPS</font>", ParagraphStyle("K3", fontSize=13, fontName="Helvetica-Bold", textColor=_CHARCOAL, leading=14)),
            Paragraph(f"<b>{err_pct if err_pct is not None else 0}%</b><br/><font size='7.5' color='#4b5563'>{failed_reqs:,} failed</font>", ParagraphStyle("K4", fontSize=13, fontName="Helvetica-Bold", textColor=_CORAL_LINE if (err_pct or 0) > 0 else _FOREST_LINE, leading=14)),
        ],
    ]
    kpi_table = Table(kpi_rows, colWidths=[44.5 * mm] * 4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_SAGE_BG),
        ("GRID", (0, 0), (-1, -1), 0.9, _BORDER_INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6))

    # 3. Unified Vector Performance Health Graph
    story.append(Paragraph(f"{project_name} — Performance Health Timeline", section_hdr))
    story.append(_build_vector_chart(points, crash_summary, width=495.0, height=175.0))
    story.append(Paragraph(crash_summary.get("plain_english_verdict") or "", meta_style))
    story.append(Spacer(1, 8))

    # 4. Where Did the Project Fail / Crash? Table
    story.append(Paragraph("Where Did the Project Fail / Crash?", section_hdr))
    if not breakdown:
        story.append(Paragraph("No per-endpoint failure breakdown was captured for this run.", meta_style))
    else:
        fb_rows: list[list[Any]] = [[
            Paragraph("Endpoint / Step", cell_bold),
            Paragraph("Reqs", cell_bold),
            Paragraph("Failed", cell_bold),
            Paragraph("Err %", cell_bold),
            Paragraph("First Broke", cell_bold),
            Paragraph("Error Codes", cell_bold),
            Paragraph("Health", cell_bold),
            Paragraph("Plain-English Cause", cell_bold),
        ]]
        for item in breakdown[:15]:
            codes_map = item.get("status_codes") or {}
            codes_text = ", ".join(f"{k}:{v}" for k, v in codes_map.items()) if codes_map else "None"
            first_broke = (
                f"{item['first_error_at_vus']} VUs @ {item.get('first_error_at_sec', 0)}s"
                if item.get("first_error_at_vus") is not None
                else "—"
            )
            fb_rows.append([
                Paragraph(f"<b>{item.get('part_name', '')}</b><br/><font size='6.5' color='#4b5563'>{item.get('method', 'GET')} {item.get('path', '/')}</font>", cell_style),
                Paragraph(f"{int(item.get('total_requests', 0)):,}", cell_style),
                Paragraph(f"{int(item.get('failed_requests', 0)):,}", cell_style),
                Paragraph(f"{float(item.get('error_rate_pct', 0.0)):.1f}%", cell_style),
                Paragraph(first_broke, cell_style),
                Paragraph(codes_text, cell_style),
                Paragraph(f"<b>{item.get('health_status', 'HEALTHY')}</b>", cell_style),
                Paragraph(str(item.get("plain_reason") or "—"), cell_style),
            ])
        fb_table = Table(
            fb_rows,
            colWidths=[36 * mm, 14 * mm, 14 * mm, 13 * mm, 24 * mm, 21 * mm, 18 * mm, 38 * mm],
            repeatRows=1,
        )
        fb_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_SAGE_BG),
            ("GRID", (0, 0), (-1, -1), 0.7, _BORDER_INK),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(fb_table)

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()
