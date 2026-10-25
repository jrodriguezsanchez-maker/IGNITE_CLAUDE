"""
SIT Reporter - Generador automatico de KPIs para System Integration Testing.
Conecta con JIRA Cloud + Xray Cloud y envia reportes via Outlook/Microsoft Graph.

Uso:
  python main.py                    # Genera y envia ambos reportes
  python main.py --only-executive   # Solo reporte ejecutivo
  python main.py --only-tracking    # Solo reporte de seguimiento
  python main.py --no-email         # Genera HTML pero no envia email
  python main.py --preview          # Abre el reporte en el navegador (sin email)
"""
import argparse
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.auth.graph_auth import get_graph_token
from src.auth.jira_oauth import get_jira_token
from src.auth.xray_auth import get_xray_token
from src.clients.jira_client import JiraClient
from src.clients.xray_client import XrayClient
from src.kpis.calculator import calculate
from src.reports.generator import generate_html, save_html
from src.reports.sender import send_report_email


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_email_subject(report_type: str, project_key: str) -> str:
    date_str = datetime.now().strftime("%d/%m/%Y")
    label = "Ejecutivo" if report_type == "executive" else "Seguimiento"
    return f"[SIT] Dashboard {label} - {project_key} - {date_str}"


def main():
    parser = argparse.ArgumentParser(description="SIT Reporter")
    parser.add_argument("--only-executive", action="store_true")
    parser.add_argument("--only-tracking", action="store_true")
    parser.add_argument("--no-email", action="store_true", help="Genera HTML sin enviar email")
    parser.add_argument("--preview", action="store_true", help="Abre el reporte en el navegador")
    parser.add_argument("--config", default="config.yaml", help="Ruta al archivo de configuracion")
    args = parser.parse_args()

    load_dotenv()
    config = load_config(args.config)

    # Determine which reports to generate
    run_executive = not args.only_tracking
    run_tracking = not args.only_executive

    print("\n" + "="*60)
    print("  SIT Reporter - Iniciando...")
    print("="*60)

    # === AUTENTICACION ===
    print("\n[1/4] Autenticando con JIRA Cloud...")
    jira_token = get_jira_token(
        client_id=os.environ["JIRA_CLIENT_ID"],
        client_secret=os.environ["JIRA_CLIENT_SECRET"],
        redirect_uri=os.environ["JIRA_REDIRECT_URI"],
    )

    print("[1/4] Autenticando con Xray Cloud...")
    xray_token = get_xray_token(
        client_id=os.environ["XRAY_CLIENT_ID"],
        client_secret=os.environ["XRAY_CLIENT_SECRET"],
        base_url=config["xray"]["base_url"],
    )

    graph_token = None
    if not args.no_email and not args.preview:
        print("[1/4] Autenticando con Microsoft Graph (Outlook)...")
        graph_token = get_graph_token(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["AZURE_CLIENT_ID"],
        )

    # === RECOPILACION DE DATOS ===
    print("\n[2/4] Recopilando datos de JIRA y Xray...")
    jira = JiraClient(base_url=os.environ["JIRA_BASE_URL"], access_token=jira_token)
    xray = XrayClient(base_url=config["xray"]["base_url"], token=xray_token)

    project_key = config["jira"]["project_key"]
    plan_key = config["jira"]["test_plan_key"]
    incident_types = config["jira"].get("incident_issue_types", ["Bug"])
    integration_label = config["jira"].get("integration_label", "integration")

    print(f"  -> Obteniendo test runs del plan {plan_key}...")
    runs = xray.get_all_runs_for_plan(plan_key)
    print(f"     {len(runs)} test runs encontrados.")

    print(f"  -> Obteniendo incidencias P1 de {project_key}...")
    incidents_p1 = jira.get_incidents_p1(project_key, incident_types)
    print(f"     {len(incidents_p1)} incidencias P1 activas.")

    print(f"  -> Obteniendo todas las incidencias activas...")
    all_incidents = jira.get_all_incidents(project_key, incident_types)
    print(f"     {len(all_incidents)} incidencias activas en total.")

    print(f"  -> Obteniendo tests de integracion (label={integration_label})...")
    integration_tests = jira.get_integration_tests(project_key, integration_label)
    print(f"     {len(integration_tests)} tests de integracion.")

    # === CALCULO DE KPIs ===
    print("\n[3/4] Calculando KPIs...")
    report = calculate(
        runs=runs,
        incidents_p1=incidents_p1,
        all_incidents=all_incidents,
        integration_tests=integration_tests,
        config=config,
        xray_client=xray,
    )

    print(f"  -> Total: {report.total_tests} tests | "
          f"Pass: {report.passed} ({report.pct_pass}%) | "
          f"Fail: {report.failed} ({report.pct_fail}%) | "
          f"Pendientes: {report.pending}")
    print(f"  -> Avance real: {report.pct_actual}% vs esperado: {report.pct_expected}%")

    # === GENERACION Y ENVIO ===
    print("\n[4/4] Generando reportes y enviando...")
    output_dir = config["reports"].get("output_dir", "./output")
    date_tag = datetime.now().strftime("%Y%m%d_%H%M")
    paths = {}

    if run_executive:
        print("  -> Generando reporte ejecutivo...")
        html_exec = generate_html(report, "executive")
        fname = f"sit_executive_{date_tag}.html"
        path = save_html(html_exec, output_dir, fname)
        paths["executive"] = path
        print(f"     Guardado en: {path}")

        if not args.no_email and not args.preview and graph_token:
            to_list = [e.strip() for e in os.environ.get("EMAIL_TO_EXECUTIVE", "").split(",") if e.strip()]
            if to_list:
                send_report_email(
                    graph_token=graph_token,
                    from_address=os.environ["EMAIL_FROM"],
                    to_addresses=to_list,
                    subject=build_email_subject("executive", project_key),
                    html_body=html_exec,
                    attachments=[{"name": fname, "content": html_exec}],
                )

    if run_tracking:
        print("  -> Generando reporte de seguimiento...")
        html_track = generate_html(report, "tracking")
        fname = f"sit_tracking_{date_tag}.html"
        path = save_html(html_track, output_dir, fname)
        paths["tracking"] = path
        print(f"     Guardado en: {path}")

        if not args.no_email and not args.preview and graph_token:
            to_list = [e.strip() for e in os.environ.get("EMAIL_TO_TRACKING", "").split(",") if e.strip()]
            if to_list:
                send_report_email(
                    graph_token=graph_token,
                    from_address=os.environ["EMAIL_FROM"],
                    to_addresses=to_list,
                    subject=build_email_subject("tracking", project_key),
                    html_body=html_track,
                    attachments=[{"name": fname, "content": html_track}],
                )

    if args.preview:
        for label, path in paths.items():
            print(f"\n  Abriendo {label} en el navegador...")
            webbrowser.open(Path(path).absolute().as_uri())

    print("\n" + "="*60)
    print("  SIT Reporter - Completado exitosamente.")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        raise
