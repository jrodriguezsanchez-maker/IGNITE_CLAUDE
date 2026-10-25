"""
Xray Cloud REST API client.
Obtiene test plans, test executions y test runs con sus estados.
"""
import requests
from typing import Any


XRAY_STATUS_MAP = {
    "PASS": "pass",
    "FAIL": "fail",
    "EXECUTING": "executing",
    "TODO": "todo",
    "BLOCKED": "blocked",
    "ABORTED": "aborted",
}


class XrayClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_test_plan(self, plan_key: str) -> dict:
        return self._get(f"/testplan/{plan_key}")

    def get_test_plan_executions(self, plan_key: str) -> list[dict]:
        result = self._get(f"/testplan/{plan_key}/testexecutions")
        return result if isinstance(result, list) else result.get("results", [])

    def get_execution_runs(self, execution_key: str) -> list[dict]:
        """Devuelve todos los test runs de una test execution."""
        all_runs = []
        limit = 100
        start = 0
        while True:
            data = self._get(f"/testexecution/{execution_key}/testruns",
                             params={"limit": limit, "start": start})
            runs = data if isinstance(data, list) else data.get("results", [])
            all_runs.extend(runs)
            if len(runs) < limit:
                break
            start += limit
        return all_runs

    def get_all_runs_for_plan(self, plan_key: str) -> list[dict]:
        """Agrega todos los test runs de todas las executions del plan."""
        executions = self.get_test_plan_executions(plan_key)
        all_runs = []
        for ex in executions:
            ex_key = ex.get("key") or ex.get("issueKey")
            if ex_key:
                runs = self.get_execution_runs(ex_key)
                for run in runs:
                    run["_execution_key"] = ex_key
                all_runs.extend(runs)
        return all_runs

    def normalize_status(self, status: str) -> str:
        return XRAY_STATUS_MAP.get(status.upper() if status else "", "unknown")
