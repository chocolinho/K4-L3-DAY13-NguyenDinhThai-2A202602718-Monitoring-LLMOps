from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


COLORS = {
    "blue": "#60a5fa",
    "cyan": "#22d3ee",
    "violet": "#a78bfa",
    "green": "#34d399",
    "amber": "#fbbf24",
    "red": "#fb7185",
    "muted": "#94a3b8",
}
CHART_WIDTH = 580
CHART_HEIGHT = 166


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[index]


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_records(path: Path, minutes: int) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row.get("ts")]
    if not rows:
        return []
    newest = max(parse_time(row["ts"]) for row in rows)
    cutoff = newest - timedelta(minutes=minutes)
    return [row for row in rows if parse_time(row["ts"]) >= cutoff]


def load_challenge(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def bucket_rows(rows: list[dict], minutes: int) -> tuple[list[str], list[list[dict]]]:
    if not rows:
        return [], []
    parsed = [(parse_time(row["ts"]), row) for row in rows]
    end = max(timestamp for timestamp, _ in parsed).replace(second=0, microsecond=0)
    start = end - timedelta(minutes=max(minutes - 1, 0))
    count = max(minutes, 1)
    labels = [(start + timedelta(minutes=i)).strftime("%H:%M") for i in range(count)]
    buckets: list[list[dict]] = [[] for _ in labels]
    for timestamp, row in parsed:
        index = int((timestamp - start).total_seconds() // 60)
        if 0 <= index < count:
            buckets[index].append(row)
    return labels, buckets


def svg_line_chart(
    labels: list[str],
    series: list[tuple[str, str, list[float | None]]],
    *,
    threshold: float | None = None,
    threshold_label: str = "",
    extra_thresholds: list[tuple[float, str, str]] | None = None,
    empty_label: str = "No samples in this window",
) -> str:
    width, height = CHART_WIDTH, CHART_HEIGHT
    left, right, top, bottom = 40, width - 8, 12, height - 32
    plot_w, plot_h = right - left, bottom - top
    values = [v for _, _, items in series for v in items if v is not None]
    thresholds = list(extra_thresholds or [])
    if threshold is not None:
        thresholds.insert(0, (threshold, threshold_label or str(threshold), COLORS["red"]))
    values.extend(value for value, _, _ in thresholds)
    if not values:
        return f'<div class="chart-empty">{html.escape(empty_label)}</div>'
    high = max(values) * 1.12 if max(values) > 0 else 1
    high = max(high, 1)

    def point(index: int, value: float) -> tuple[float, float]:
        x = left + (plot_w * index / max(len(labels) - 1, 1))
        y = bottom - (value / high * plot_h)
        return x, y

    bits = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for step in range(4):
        y = top + plot_h * step / 3
        value = high * (3 - step) / 3
        bits.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="gridline"/>')
        digits = 2 if high <= 1 else (3 if high < 0.1 else 0)
        bits.append(f'<text x="{left - 7}" y="{y + 4:.1f}" text-anchor="end" class="axis">{value:.{digits}f}</text>')
    for value, label, color in thresholds:
        y = bottom - (value / high * plot_h)
        bits.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="threshold" style="stroke:{color}"/>')
        bits.append(f'<text x="{right - 3}" y="{max(top + 10, y - 4):.1f}" text-anchor="end" class="threshold-label" style="fill:{color}">{html.escape(label)}</text>')
    for name, color, items in series:
        chunks: list[str] = []
        current: list[str] = []
        for index, value in enumerate(items):
            if value is None:
                if current:
                    chunks.append(" ".join(current))
                    current = []
                continue
            x, y = point(index, value)
            current.append(f"{x:.1f},{y:.1f}")
        if current:
            chunks.append(" ".join(current))
        for points in chunks:
            bits.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
        for index, value in enumerate(items):
            if value is not None:
                x, y = point(index, value)
                bits.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.7" fill="{color}"/>')
    if labels:
        bits.append(f'<text x="{left}" y="{height - 8}" class="axis">{html.escape(labels[0])}</text>')
        bits.append(f'<text x="{right}" y="{height - 8}" text-anchor="end" class="axis">{html.escape(labels[-1])}</text>')
    bits.append("</svg>")
    legend = "".join(
        f'<span class="legend-item"><i style="background:{color}"></i>{html.escape(name)}</span>'
        for name, color, _ in series
    )
    for _, label, color in thresholds:
        legend += f'<span class="legend-item"><i class="legend-dash" style="border-color:{color}"></i>{html.escape(label)}</span>'
    return f'<div class="chart-wrap">{"".join(bits)}<div class="legend">{legend}</div></div>'


def svg_bar_chart(labels: list[str], values: list[float], color: str, unit: str = "", threshold: float | None = None, threshold_label: str = "") -> str:
    if not any(values):
        return '<div class="chart-empty">No samples in this window</div>'
    width, height = CHART_WIDTH, CHART_HEIGHT
    left, right, top, bottom = 40, width - 8, 12, height - 32
    max_value = max(max(values) * 1.18, threshold * 1.08 if threshold is not None else 0, 1e-9)
    plot_h, plot_w = bottom - top, right - left
    bar_w = max(3, plot_w / max(len(values), 1) * 0.62)
    bits = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for step in range(4):
        y = top + plot_h * step / 3
        value = max_value * (3 - step) / 3
        bits.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="gridline"/>')
        digits = 3 if max_value < 0.1 else (2 if max_value < 10 else 0)
        bits.append(f'<text x="{left - 7}" y="{y + 4:.1f}" text-anchor="end" class="axis">{value:.{digits}f}{html.escape(unit)}</text>')
    for index, value in enumerate(values):
        x = left + plot_w * (index + 0.5) / max(len(values), 1) - bar_w / 2
        bar_h = value / max_value * plot_h
        y = bottom - bar_h
        bits.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="3" fill="{color}" opacity=".9"/>')
    if threshold is not None:
        y = bottom - threshold / max_value * plot_h
        bits.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="threshold"/>')
        bits.append(f'<text x="{right - 3}" y="{max(top + 10, y - 4):.1f}" text-anchor="end" class="threshold-label">{html.escape(threshold_label)}</text>')
    if labels:
        bits.append(f'<text x="{left}" y="{height - 8}" class="axis">{html.escape(labels[0])}</text>')
        bits.append(f'<text x="{right}" y="{height - 8}" text-anchor="end" class="axis">{html.escape(labels[-1])}</text>')
    bits.append("</svg>")
    legend = f'<div class="legend"><span class="legend-item"><i style="background:{color}"></i>Per-minute samples</span><span class="legend-item"><i class="legend-dash"></i>{html.escape(threshold_label)}</span></div>' if threshold is not None else ""
    return f'<div class="chart-wrap">{"".join(bits)}{legend}</div>'


def panel(title: str, badge: str, chart: str, summary: str, foot: str) -> str:
    return (
        f'<section class="panel"><div class="panel-head"><h2>{html.escape(title)}</h2>'
        f'<span class="unit">{html.escape(badge)}</span></div>'
        f'{chart}<div class="panel-summary">{summary}</div><p class="panel-foot">{html.escape(foot)}</p></section>'
    )


def render(rows: list[dict], minutes: int, challenge: dict) -> str:
    labels, buckets = bucket_rows(rows, minutes)
    responses = [row for row in rows if row.get("event") == "response_sent"]
    requests = [row for row in rows if row.get("event") == "request_received"]
    failures = [row for row in rows if row.get("event") == "request_failed"]
    latencies = [float(row["latency_ms"]) for row in responses if row.get("latency_ms") is not None]
    ttft_values = [float(row["ttft_ms"]) for row in responses if row.get("ttft_ms") is not None]
    quality_values = [float(row["quality_score"]) for row in responses if row.get("quality_score") is not None]
    retrieval_rows = [row for row in responses if row.get("tool_success") is not None]
    retrieval_pct = 100 * sum(row.get("tool_success") is True for row in retrieval_rows) / len(retrieval_rows) if retrieval_rows else 0
    error_pct = 100 * len(failures) / len(requests) if requests else 0
    challenge_threshold = float(challenge.get("latency_threshold_ms", 2000))
    slo_threshold = 3000.0
    feature = str(challenge.get("affected_feature", "monitoring"))
    challenge_id = str(challenge.get("challenge_id", "Day 13 practice"))
    incident_name = str(challenge.get("incident", "rag_slow"))
    challenge_sessions = {
        query.get("session_id")
        for query in challenge.get("queries", [])
        if isinstance(query, dict) and query.get("session_id")
    }
    affected = [
        row for row in responses
        if row.get("feature") == feature
        and (not challenge_sessions or row.get("session_id") in challenge_sessions)
    ]
    # A challenge may be replayed more than once in the selected hour. Keep the
    # most recent request batch together so the banner matches one run/report.
    affected.sort(key=lambda row: parse_time(row["ts"]))
    challenge_batches: list[list[dict]] = []
    for row in affected:
        if (
            not challenge_batches
            or parse_time(row["ts"]) - parse_time(challenge_batches[-1][-1]["ts"])
            > timedelta(seconds=20)
        ):
            challenge_batches.append([row])
        else:
            challenge_batches[-1].append(row)
    affected = challenge_batches[-1] if challenge_batches else []
    affected_sorted = sorted(affected, key=lambda row: float(row.get("latency_ms", 0)), reverse=True)
    peak = affected_sorted[0] if affected_sorted else None
    peak_latency = float(peak.get("latency_ms", 0)) if peak else 0.0
    p95 = percentile(latencies, 95)
    incident_active = bool(affected and (peak_latency > challenge_threshold or p95 > challenge_threshold))
    incident_class = "incident-banner active" if incident_active else "incident-banner clear"
    incident_status = "CHALLENGE SIGNAL DETECTED" if incident_active else "NO CHALLENGE SIGNAL IN WINDOW"

    latency_series = [
        ("P50", COLORS["blue"], [percentile([float(r["latency_ms"]) for r in group if r.get("latency_ms") is not None], 50) if any(r.get("latency_ms") is not None for r in group) else None for group in buckets]),
        ("P95", COLORS["red"], [percentile([float(r["latency_ms"]) for r in group if r.get("latency_ms") is not None], 95) if any(r.get("latency_ms") is not None for r in group) else None for group in buckets]),
        ("TTFT P95", COLORS["cyan"], [percentile([float(r["ttft_ms"]) for r in group if r.get("ttft_ms") is not None], 95) if any(r.get("ttft_ms") is not None for r in group) else None for group in buckets]),
    ]
    latency_summary = "".join([
        f'<span>P50 <b>{percentile(latencies, 50):.0f} ms</b></span>',
        f'<span class="{ "bad" if p95 > slo_threshold else "good" }">P95 <b>{p95:.0f} ms</b></span>',
        f'<span>P99 <b>{percentile(latencies, 99):.0f} ms</b></span>',
        f'<span>TTFT P95 <b>{percentile(ttft_values, 95):.0f} ms</b></span>',
    ])
    latency_panel = panel(
        "Latency & first token", "MILLISECONDS",
        svg_line_chart(labels, latency_series, extra_thresholds=[
            (challenge_threshold, f"Challenge {challenge_threshold:.0f} ms", COLORS["red"]),
            (slo_threshold, f"P95 SLO {slo_threshold:.0f} ms", COLORS["amber"]),
        ]),
        latency_summary, f"SLO line: P95 <= {slo_threshold:.0f} ms · challenge line: {challenge_threshold:.0f} ms",
    )

    traffic_values = [sum(row.get("event") == "request_received" for row in group) for group in buckets]
    traffic_panel = panel(
        "Request traffic", "REQUESTS / MIN",
        svg_bar_chart(labels, traffic_values, COLORS["blue"], threshold=1, threshold_label="Traffic floor 1 req/min"),
        f'<span>Requests <b>{len(requests)}</b></span><span>Peak / min <b>{max(traffic_values, default=0)}</b></span>',
        "Incoming request count · expected minimum 1 request/min",
    )

    error_series = [
        ("Error rate", COLORS["red"], [100 * sum(r.get("event") == "request_failed" for r in group) / max(sum(r.get("event") == "request_received" for r in group), 1) if any(r.get("event") == "request_received" for r in group) else None for group in buckets]),
        ("Retrieval success", COLORS["green"], [100 * sum(r.get("tool_success") is True for r in group) / max(sum(r.get("tool_success") is not None for r in group), 1) if any(r.get("tool_success") is not None for r in group) else None for group in buckets]),
    ]
    errors_panel = panel(
        "Errors & retrieval", "PERCENT",
        svg_line_chart(labels, error_series, extra_thresholds=[
            (2, "Error max 2%", COLORS["red"]),
            (90, "Retrieval SLO 90%", COLORS["green"]),
        ]),
        f'<span>Error rate <b class="{ "bad" if error_pct > 2 else "good" }">{error_pct:.1f}%</b></span><span>Retrieval success <b>{retrieval_pct:.1f}%</b></span>',
        "Guardrails: error rate <= 2% · retrieval success >= 90%",
    )

    cost_values = [sum(float(r.get("cost_usd", 0)) for r in group if r.get("event") == "response_sent") for group in buckets]
    total_cost = sum(float(row.get("cost_usd", 0)) for row in responses)
    cost_panel = panel(
        "Generation cost", "MILLI-USD / MIN",
        svg_bar_chart(labels, [value * 1000 for value in cost_values], COLORS["violet"], unit="m$"),
        f'<span>Selected window <b>${total_cost:.4f}</b></span><span>Daily cap <b>$2.50</b></span><span>Avg / request <b>${statistics.mean([float(r.get("cost_usd", 0)) for r in responses]) if responses else 0:.4f}</b></span>',
        "Per-minute estimate · daily guardrail is $2.50 (shown separately from this time scale)",
    )

    token_in = [sum(int(r.get("tokens_in", 0)) for r in group if r.get("event") == "response_sent") for group in buckets]
    token_out = [sum(int(r.get("tokens_out", 0)) for r in group if r.get("event") == "response_sent") for group in buckets]
    tokens_panel = panel(
        "Token consumption", "TOKENS / MIN",
        svg_line_chart(labels, [
            ("Input", COLORS["cyan"], [float(v) if v else None for v in token_in]),
            ("Output", COLORS["amber"], [float(v) if v else None for v in token_out]),
            ("Total", COLORS["violet"], [float(i + o) if i + o else None for i, o in zip(token_in, token_out)]),
        ]),
        f'<span>Input <b>{sum(token_in):,}</b></span><span>Output <b>{sum(token_out):,}</b></span><span>Total <b>{sum(token_in) + sum(token_out):,} / 50k</b></span>',
        "Per-minute usage trend · total is compared with the 50,000-token window guardrail",
    )

    quality_trend = [statistics.mean([float(r["quality_score"]) for r in group if r.get("quality_score") is not None]) if any(r.get("quality_score") is not None for r in group) else None for group in buckets]
    quality_avg = statistics.mean(quality_values) if quality_values else 0.0
    quality_panel = panel(
        "Answer quality proxy", "SCORE · 0–1",
        svg_line_chart(labels, [("Quality avg", COLORS["green"], quality_trend)], threshold=0.75, threshold_label="Quality SLO 0.75"),
        f'<span>Window average <b class="{ "bad" if quality_values and quality_avg < .75 else "good" }">{quality_avg:.2f}</b></span><span>Scored responses <b>{len(quality_values)}</b></span>',
        "SLO: average quality proxy >= 0.75 · not a human evaluation score",
    )

    challenge_line = (
        f'<span class="banner-tag">{html.escape(challenge_id)}</span>'
        f'<span>{html.escape(incident_name)} · feature {html.escape(feature)}</span>'
        f'<span>{len(affected)} matched challenge-session responses · P95 {percentile([float(row.get("latency_ms", 0)) for row in affected], 95):.0f} ms vs threshold {challenge_threshold:.0f} ms</span>'
        f'<span>Correlation ID <b>{html.escape(str(peak.get("correlation_id", "—") if peak else "—"))}</b></span>'
    )
    banner = f'<section class="{incident_class}"><div class="banner-title"><span class="pulse"></span>{incident_status}</div><div class="banner-details">{challenge_line}</div><div class="banner-hint">Investigation path: metric spike → correlation_id in logs → matching trace → slow child observation</div></section>'
    freshest = max((parse_time(row["ts"]) for row in rows), default=None)
    refreshed = freshest.strftime("%Y-%m-%d %H:%M UTC") if freshest else "no data"
    kpis = (
        f'<div class="top-kpis"><div><small>REQUESTS</small><strong>{len(requests)}</strong><em>in selected window</em></div>'
        f'<div class="kpi-red"><small>P95 LATENCY</small><strong>{p95:.0f}<i>ms</i></strong><em>target <= {slo_threshold:.0f} ms</em></div>'
        f'<div><small>RETRIEVAL SUCCESS</small><strong>{retrieval_pct:.0f}<i>%</i></strong><em>target >= 90%</em></div>'
        f'<div><small>EST. COST</small><strong>${total_cost:.4f}</strong><em>{sum(token_in) + sum(token_out):,} total tokens</em></div></div>'
    )
    panels = latency_panel + traffic_panel + errors_panel + cost_panel + tokens_panel + quality_panel
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>K4-L3B · LLMOps Runtime Dashboard</title><style>
:root{{--bg:#07111f;--surface:#101d2d;--surface2:#142438;--border:#21364d;--text:#e6eef8;--muted:#91a4ba;--blue:#60a5fa;--green:#34d399;--red:#fb7185;--amber:#fbbf24}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 50% -25%,#173353 0,transparent 54%),var(--bg);color:var(--text);font:14px/1.45 Inter,"Segoe UI",Arial,sans-serif}}
.shell{{max-width:1640px;margin:auto;padding:24px 28px 30px}}.topbar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:17px}}
.brand{{display:flex;align-items:center;gap:12px}}.logo{{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#2563eb,#22d3ee);display:grid;place-items:center;font-weight:800;color:white;font-size:17px;box-shadow:0 7px 24px #0284c755}}
h1{{font-size:20px;letter-spacing:-.35px;margin:0}}.subtitle{{font-size:12px;color:var(--muted);margin-top:2px}}.toolbar{{display:flex;align-items:center;gap:10px}}
.chip{{border:1px solid var(--border);background:#0d1928;border-radius:8px;padding:8px 11px;color:#c8d5e4;font-size:12px}}.snapshot{{color:#8bdcf0}}.snapshot:before{{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:#22d3ee;margin-right:7px;box-shadow:0 0 9px #22d3ee}}
.incident-banner{{border:1px solid #7f3343;background:linear-gradient(100deg,#3a1723,#261724 55%,#181c2b);border-radius:12px;padding:14px 17px;margin-bottom:14px;box-shadow:inset 3px 0 #fb7185}}
.incident-banner.clear{{border-color:#1f5949;background:linear-gradient(100deg,#102a2a,#142633);box-shadow:inset 3px 0 #34d399}}.banner-title{{font-size:12px;font-weight:800;letter-spacing:.8px;color:#ff9aaa;display:flex;align-items:center;gap:8px}}
.clear .banner-title{{color:#7ee5bc}}.pulse{{width:8px;height:8px;border-radius:50%;background:#fb7185;box-shadow:0 0 0 4px #fb718533}}.clear .pulse{{background:#34d399;box-shadow:0 0 0 4px #34d39933}}
.banner-details{{display:flex;flex-wrap:wrap;gap:10px 23px;margin-top:9px;font-size:12px;color:#e5cbd2}}.clear .banner-details{{color:#c0ded7}}.banner-details b{{color:#fff;font-family:Consolas,monospace}}.banner-tag{{font-weight:700;color:#fff}}
.banner-hint{{font-size:11px;color:#bd8d9b;margin-top:8px}}.clear .banner-hint{{color:#8eb8aa}}
.top-kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:14px}}.top-kpis>div{{border:1px solid var(--border);background:linear-gradient(145deg,#12243a,#0f1a29);border-radius:11px;padding:12px 15px;display:flex;flex-direction:column;min-height:82px}}
.top-kpis small{{font-size:10px;letter-spacing:1px;color:#8da4bd;font-weight:700}}.top-kpis strong{{font-size:23px;letter-spacing:-.5px;margin-top:2px}}.top-kpis strong i{{font-size:12px;font-style:normal;color:#98adc2;margin-left:4px}}.top-kpis em{{font-size:10px;color:#8498af;font-style:normal}}
.top-kpis .kpi-red strong{{color:#ff8b9a}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
.panel{{min-width:0;border:1px solid var(--border);border-radius:12px;background:linear-gradient(155deg,#122238,#0d1928 75%);padding:13px 14px 11px;box-shadow:0 10px 25px #02081744}}
.panel-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}}h2{{font-size:13px;margin:0;font-weight:700;letter-spacing:.1px}}.unit{{font-size:9px;font-weight:700;letter-spacing:.8px;color:#8198b2;background:#1a2b40;border-radius:5px;padding:4px 6px}}
.chart-wrap{{position:relative}}.chart{{width:100%;height:132px;display:block;overflow:visible}}.gridline{{stroke:#23364b;stroke-width:1}}.axis{{fill:#8195ab;font-size:9px}}.threshold{{stroke:#fb7185;stroke-width:1.4;stroke-dasharray:5 4;opacity:.92}}.threshold-label{{fill:#ff9aa7;font-size:9px;font-weight:700}}
.legend{{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 3px 39px;min-height:15px}}.legend-item{{font-size:9px;color:#9badc1;display:inline-flex;align-items:center;gap:5px}}.legend-item i{{width:8px;height:8px;border-radius:50%;display:inline-block}}.legend-dash{{width:13px!important;height:0!important;border-top:2px dashed #fb7185;border-radius:0!important;background:transparent!important}}
.panel-summary{{display:flex;flex-wrap:wrap;gap:7px 15px;padding:7px 0 5px;border-top:1px solid #1d3045;font-size:10px;color:#91a4ba}}.panel-summary b{{font-size:12px;color:#e6eef8;margin-left:3px}}.panel-summary .good{{color:#7ee5bc}}.panel-summary .bad,.bad{{color:#ff8999!important}}.panel-foot{{margin:0;color:#71859d;font-size:9px}}
.chart-empty{{height:132px;display:grid;place-items:center;color:#70849a;font-size:11px}}
footer{{display:flex;justify-content:space-between;color:#687f98;font-size:10px;margin-top:11px;padding:0 2px}}
@media(max-width:1100px){{.shell{{padding:17px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:650px){{.topbar{{align-items:flex-start;gap:12px;flex-direction:column}}.top-kpis{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}.banner-details{{gap:7px 12px}}}}
</style></head><body><main class="shell">
<header class="topbar"><div class="brand"><div class="logo">M</div><div><h1>K4-L3B · Monitoring &amp; LLMOps</h1><div class="subtitle">Production observability · structured logs + Langfuse traces</div></div></div>
<div class="toolbar"><span class="chip">◷ &nbsp;Last {minutes} minutes</span><span class="chip snapshot">SNAPSHOT · local logs</span></div></header>
{banner}{kpis}<div class="grid">{panels}</div>
<footer><span>Source: data/logs.jsonl · window ends {html.escape(refreshed)}</span><span>Targets: latency P95 ≤ 3000 ms · retrieval ≥ 90% · quality ≥ 0.75</span></footer>
</main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a six-panel LLMOps dashboard from structured JSONL logs")
    parser.add_argument("--input", type=Path, default=Path("data/logs.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/dashboard.html"))
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--challenge", type=Path, default=Path("config/challenge.json"))
    args = parser.parse_args()
    rows = load_records(args.input, args.minutes)
    challenge = load_challenge(args.challenge)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(rows, args.minutes, challenge), encoding="utf-8")
    print(f"Dashboard written to {args.output} from {len(rows)} records")
    print(f"Challenge: {challenge.get('challenge_id', 'not configured')} · incident: {challenge.get('incident', 'unknown')}")


if __name__ == "__main__":
    main()
