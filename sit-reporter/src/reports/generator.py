"""
Genera los reportes HTML usando Jinja2 con gráficos matplotlib embebidos en base64.
"""
import base64
import io
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from jinja2 import Environment, FileSystemLoader

from src.kpis.calculator import SITReport


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

COLORS = {
    "pass": "#22c55e",
    "fail": "#ef4444",
    "blocked": "#f97316",
    "executing": "#3b82f6",
    "todo": "#94a3b8",
    "aborted": "#7c3aed",
}


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _chart_progress_gauge(report: SITReport) -> str:
    fig, ax = plt.subplots(figsize=(5, 2.5), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")

    bar_h = 0.4
    ax.barh(1, 100, height=bar_h, color="#1e293b", zorder=2)
    ax.barh(1, report.pct_expected, height=bar_h, color="#334155", zorder=3, label=f"Esperado {report.pct_expected}%")
    ax.barh(1, report.pct_actual, height=bar_h * 0.6,
            color="#22c55e" if report.is_on_track else "#ef4444", zorder=4,
            label=f"Real {report.pct_actual}%")

    ax.set_xlim(0, 100)
    ax.set_ylim(0.5, 1.5)
    ax.set_yticks([])
    ax.set_xlabel("% Avance", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)

    legend = ax.legend(loc="upper left", facecolor="#1e293b", edgecolor="none",
                       labelcolor="white", fontsize=8)
    return _fig_to_base64(fig)


def _chart_donut(report: SITReport) -> str:
    labels = ["Pasados", "Fallados", "Bloqueados", "En curso", "Pendientes"]
    sizes = [report.passed, report.failed, report.blocked, report.executing, report.todo]
    colors = [COLORS["pass"], COLORS["fail"], COLORS["blocked"], COLORS["executing"], COLORS["todo"]]
    sizes = [max(s, 0) for s in sizes]
    total = sum(sizes)
    if total == 0:
        sizes = [1]
        colors = [COLORS["todo"]]
        labels = ["Sin datos"]

    fig, ax = plt.subplots(figsize=(4.5, 3.5), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")
    wedges, _ = ax.pie(sizes, colors=colors, startangle=90,
                       wedgeprops=dict(width=0.5, edgecolor="#0f172a"))
    ax.text(0, 0, f"{report.pct_complete}%\nEjecutado",
            ha="center", va="center", color="white", fontsize=11, fontweight="bold")

    patches = [mpatches.Patch(color=c, label=l) for c, l in zip(colors, labels) if l != "Sin datos"]
    ax.legend(handles=patches, loc="lower center", ncol=3, facecolor="#1e293b",
              edgecolor="none", labelcolor="white", fontsize=7, bbox_to_anchor=(0.5, -0.15))
    return _fig_to_base64(fig)


def _chart_streams(report: SITReport) -> str:
    if not report.streams:
        return ""
    names = [s.name for s in report.streams]
    passes = [s.passed for s in report.streams]
    fails = [s.failed for s in report.streams]
    blocked = [s.blocked for s in report.streams]
    todo = [s.pending for s in report.streams]

    fig, ax = plt.subplots(figsize=(7, max(3, len(names) * 0.6)), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")
    y = range(len(names))
    bar_h = 0.55

    left = [0] * len(names)
    for vals, color, label in [
        (passes, COLORS["pass"], "Pass"),
        (fails, COLORS["fail"], "Fail"),
        (blocked, COLORS["blocked"], "Bloqueado"),
        (todo, COLORS["todo"], "Pendiente"),
    ]:
        ax.barh(list(y), vals, height=bar_h, left=left, color=color, label=label)
        left = [l + v for l, v in zip(left, vals)]

    ax.set_yticks(list(y))
    ax.set_yticklabels(names, color="white", fontsize=9)
    ax.set_xlabel("Casos de prueba", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(loc="lower right", facecolor="#1e293b", edgecolor="none",
              labelcolor="white", fontsize=7)
    return _fig_to_base64(fig)


def _chart_executor_progress(report: SITReport) -> str:
    if not report.executors:
        return ""
    names = [e.name.split()[0] for e in report.executors[:10]]
    pcts = [e.pct_complete for e in report.executors[:10]]
    colors = ["#22c55e" if p >= 80 else "#f97316" if p >= 50 else "#ef4444" for p in pcts]

    fig, ax = plt.subplots(figsize=(6, max(3, len(names) * 0.5)), facecolor="#0f172a")
    ax.set_facecolor("#0f172a")
    bars = ax.barh(names, pcts, color=colors, height=0.5)
    ax.set_xlim(0, 100)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{pct}%", va="center", color="white", fontsize=8)
    ax.set_xlabel("% Completado", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_to_base64(fig)


def generate_html(report: SITReport, report_type: str = "executive") -> str:
    """Genera el HTML del reporte. report_type: 'executive' o 'tracking'."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template_file = f"{report_type}.html"
    template = env.get_template(template_file)

    charts = {
        "progress_gauge": _chart_progress_gauge(report),
        "donut": _chart_donut(report),
        "streams": _chart_streams(report),
    }
    if report_type == "tracking":
        charts["executor_progress"] = _chart_executor_progress(report)

    return template.render(report=report, charts=charts, colors=COLORS)


def save_html(html: str, output_dir: str, filename: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
