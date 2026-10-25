"""
Calcula todos los KPIs del SIT a partir de los datos de JIRA y Xray.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from dateutil import parser as dateutil_parser
from typing import Any


@dataclass
class StreamKPI:
    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    executing: int = 0
    todo: int = 0
    aborted: int = 0

    @property
    def executed(self) -> int:
        return self.passed + self.failed + self.blocked + self.aborted

    @property
    def pending(self) -> int:
        return self.todo + self.executing

    @property
    def pct_complete(self) -> float:
        return round(self.executed / self.total * 100, 1) if self.total else 0.0

    @property
    def pct_pass(self) -> float:
        return round(self.passed / self.executed * 100, 1) if self.executed else 0.0

    @property
    def pct_fail(self) -> float:
        return round(self.failed / self.executed * 100, 1) if self.executed else 0.0


@dataclass
class ExecutorKPI:
    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    pending: int = 0

    @property
    def pct_complete(self) -> float:
        executed = self.passed + self.failed + self.blocked
        return round(executed / self.total * 100, 1) if self.total else 0.0


@dataclass
class IncidentKPI:
    key: str
    summary: str
    priority: str
    status: str
    assignee: str
    days_open: int
    linked_tests: int = 0


@dataclass
class SITReport:
    generated_at: str = ""
    project_key: str = ""
    plan_key: str = ""

    # Totals
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    executing: int = 0
    todo: int = 0
    aborted: int = 0

    # Planning
    plan_start: str = ""
    plan_end: str = ""
    pct_expected: float = 0.0
    pct_actual: float = 0.0
    days_remaining: int = 0

    # By stream
    streams: list[StreamKPI] = field(default_factory=list)

    # By executor
    executors: list[ExecutorKPI] = field(default_factory=list)

    # Incidents
    p1_incidents: list[IncidentKPI] = field(default_factory=list)
    all_incidents: list[IncidentKPI] = field(default_factory=list)
    top_blocking: list[IncidentKPI] = field(default_factory=list)

    # Integration tests
    integration_tests: list[dict] = field(default_factory=list)

    @property
    def executed(self) -> int:
        return self.passed + self.failed + self.blocked + self.aborted

    @property
    def pending(self) -> int:
        return self.todo + self.executing

    @property
    def pct_pass(self) -> float:
        return round(self.passed / self.executed * 100, 1) if self.executed else 0.0

    @property
    def pct_fail(self) -> float:
        return round(self.failed / self.executed * 100, 1) if self.executed else 0.0

    @property
    def pct_blocked(self) -> float:
        return round(self.blocked / self.executed * 100, 1) if self.executed else 0.0

    @property
    def pct_complete(self) -> float:
        return round(self.executed / self.total_tests * 100, 1) if self.total_tests else 0.0

    @property
    def pct_pending(self) -> float:
        return round(self.pending / self.total_tests * 100, 1) if self.total_tests else 0.0

    @property
    def is_on_track(self) -> bool:
        return self.pct_actual >= self.pct_expected - 5  # 5% tolerance


def _days_open(created_str: str) -> int:
    try:
        created = dateutil_parser.parse(created_str)
        return (datetime.now(created.tzinfo) - created).days
    except Exception:
        return 0


def _get_assignee(issue: dict) -> str:
    assignee = issue.get("fields", {}).get("assignee")
    if assignee:
        return assignee.get("displayName", "Sin asignar")
    return "Sin asignar"


def _get_linked_test_count(issue: dict) -> int:
    links = issue.get("fields", {}).get("issuelinks", [])
    count = 0
    for link in links:
        inward = link.get("inwardIssue", {})
        outward = link.get("outwardIssue", {})
        if inward.get("fields", {}).get("issuetype", {}).get("name") == "Test":
            count += 1
        if outward.get("fields", {}).get("issuetype", {}).get("name") == "Test":
            count += 1
    return count


def _expected_progress(start_date: str, end_date: str) -> tuple[float, int]:
    """Calcula el % de avance esperado según la fecha de hoy."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    today = date.today()

    total_days = (end - start).days
    elapsed_days = max(0, (today - start).days)
    remaining = max(0, (end - today).days)

    if total_days <= 0:
        return 100.0, 0
    pct = min(100.0, round(elapsed_days / total_days * 100, 1))
    return pct, remaining


def calculate(
    runs: list[dict],
    incidents_p1: list[dict],
    all_incidents: list[dict],
    integration_tests: list[dict],
    config: dict,
    xray_client: Any,
) -> SITReport:
    report = SITReport()
    report.generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    report.project_key = config["jira"]["project_key"]
    report.plan_key = config["jira"]["test_plan_key"]
    report.plan_start = config["planning"]["start_date"]
    report.plan_end = config["planning"]["end_date"]

    report.pct_expected, report.days_remaining = _expected_progress(
        report.plan_start, report.plan_end
    )

    # Aggregate overall counts
    for run in runs:
        status = xray_client.normalize_status(run.get("status", "TODO"))
        report.total_tests += 1
        if status == "pass":
            report.passed += 1
        elif status == "fail":
            report.failed += 1
        elif status == "blocked":
            report.blocked += 1
        elif status == "executing":
            report.executing += 1
        elif status == "aborted":
            report.aborted += 1
        else:
            report.todo += 1

    report.pct_actual = report.pct_complete

    # By stream: group runs by component label
    stream_configs = config["jira"].get("streams", [])
    for stream_cfg in stream_configs:
        skpi = StreamKPI(name=stream_cfg["name"])
        stream_label = stream_cfg["name"].lower().replace(" ", "_")
        for run in runs:
            labels = [l.lower() for l in (run.get("labels") or [])]
            components = [c.lower() for c in (run.get("components") or [])]
            if stream_label in labels or stream_cfg["name"].lower() in components:
                status = xray_client.normalize_status(run.get("status", "TODO"))
                skpi.total += 1
                if status == "pass":
                    skpi.passed += 1
                elif status == "fail":
                    skpi.failed += 1
                elif status == "blocked":
                    skpi.blocked += 1
                elif status == "executing":
                    skpi.executing += 1
                elif status == "aborted":
                    skpi.aborted += 1
                else:
                    skpi.todo += 1
        if skpi.total == 0:
            skpi.total = report.total_tests // max(len(stream_configs), 1)
        report.streams.append(skpi)

    # By executor
    executors_map: dict[str, ExecutorKPI] = {}
    for run in runs:
        assignee = run.get("assignee") or "Sin asignar"
        if isinstance(assignee, dict):
            assignee = assignee.get("displayName", "Sin asignar")
        if assignee not in executors_map:
            executors_map[assignee] = ExecutorKPI(name=assignee)
        ekpi = executors_map[assignee]
        status = xray_client.normalize_status(run.get("status", "TODO"))
        ekpi.total += 1
        if status == "pass":
            ekpi.passed += 1
        elif status == "fail":
            ekpi.failed += 1
        elif status == "blocked":
            ekpi.blocked += 1
        else:
            ekpi.pending += 1
    report.executors = sorted(executors_map.values(), key=lambda e: e.pct_complete, reverse=True)

    # P1 incidents
    for issue in incidents_p1:
        f = issue.get("fields", {})
        report.p1_incidents.append(IncidentKPI(
            key=issue["key"],
            summary=f.get("summary", ""),
            priority=f.get("priority", {}).get("name", ""),
            status=f.get("status", {}).get("name", ""),
            assignee=_get_assignee(issue),
            days_open=_days_open(f.get("created", "")),
            linked_tests=_get_linked_test_count(issue),
        ))

    # All incidents + top blocking
    for issue in all_incidents:
        f = issue.get("fields", {})
        linked = _get_linked_test_count(issue)
        inc = IncidentKPI(
            key=issue["key"],
            summary=f.get("summary", ""),
            priority=f.get("priority", {}).get("name", ""),
            status=f.get("status", {}).get("name", ""),
            assignee=_get_assignee(issue),
            days_open=_days_open(f.get("created", "")),
            linked_tests=linked,
        )
        report.all_incidents.append(inc)

    top_n = config["reports"].get("top_blocking", 5)
    report.top_blocking = sorted(
        report.all_incidents, key=lambda i: i.linked_tests, reverse=True
    )[:top_n]

    # Integration tests status
    report.integration_tests = []
    for issue in integration_tests:
        f = issue.get("fields", {})
        report.integration_tests.append({
            "key": issue["key"],
            "summary": f.get("summary", ""),
            "status": f.get("status", {}).get("name", ""),
            "assignee": _get_assignee(issue),
        })

    return report
