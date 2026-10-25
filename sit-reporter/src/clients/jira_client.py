"""
JIRA Cloud REST API client (API v3).
Gestiona todas las llamadas a JIRA: issues, proyectos, incidencias.
"""
import requests
from typing import Any


class JiraClient:
    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> Any:
        resp = self.session.get(f"{self.base_url}/rest/api/3{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_project(self, project_key: str) -> dict:
        return self._get(f"/project/{project_key}")

    def search_issues(self, jql: str, fields: list[str] = None, max_results: int = 1000) -> list[dict]:
        all_issues = []
        start_at = 0
        fields_str = ",".join(fields) if fields else "*all"
        while True:
            data = self._get("/search", params={
                "jql": jql,
                "startAt": start_at,
                "maxResults": min(100, max_results - len(all_issues)),
                "fields": fields_str,
            })
            all_issues.extend(data.get("issues", []))
            if len(all_issues) >= data["total"] or len(all_issues) >= max_results:
                break
            start_at += len(data["issues"])
        return all_issues

    def get_issue(self, issue_key: str) -> dict:
        return self._get(f"/issue/{issue_key}")

    def get_incidents_p1(self, project_key: str, issue_types: list[str]) -> list[dict]:
        types = ", ".join(f'"{t}"' for t in issue_types)
        jql = (
            f'project = {project_key} '
            f'AND issuetype in ({types}) '
            f'AND priority in (Highest, Critical, "P1") '
            f'AND status not in (Done, Closed, Resolved) '
            f'ORDER BY created ASC'
        )
        return self.search_issues(jql, fields=["summary", "status", "priority", "assignee",
                                                "created", "updated", "issuelinks"])

    def get_all_incidents(self, project_key: str, issue_types: list[str]) -> list[dict]:
        types = ", ".join(f'"{t}"' for t in issue_types)
        jql = (
            f'project = {project_key} '
            f'AND issuetype in ({types}) '
            f'AND status not in (Done, Closed, Resolved) '
            f'ORDER BY priority ASC, created ASC'
        )
        return self.search_issues(jql, fields=["summary", "status", "priority", "assignee",
                                                "created", "updated", "issuelinks"])

    def get_integration_tests(self, project_key: str, label: str) -> list[dict]:
        jql = f'project = {project_key} AND issuetype = Test AND labels = "{label}"'
        return self.search_issues(jql, fields=["summary", "status", "assignee", "labels"])
