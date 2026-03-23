"""conftest_incidents.py — Pytest plugin that auto-reports test failures to /api/incidents.

Installed globally when present in tests/ directory. Fires POST /api/incidents
for each failed test with type=test_failure and P3 priority.

Usage:
  # Add to conftest.py:
  from tests.conftest_incidents import *  # noqa: F401, F403

  # Or enable via env var:
  GSD_INCIDENTS_ENABLED=1 pytest tests/

Set GSD_JIRA_API to override the API base URL (default: http://localhost:8000).
"""

import os
import traceback
import urllib.request
import json
import logging

logger = logging.getLogger("incidents")

_API_BASE = os.getenv("GSD_JIRA_API", "http://localhost:8000")
_ENABLED = os.getenv("GSD_INCIDENTS_ENABLED", "0") == "1"
_TIMEOUT = 4  # seconds — never slow down test suite


def _report_incident(title: str, summary: str, detail: str) -> None:
    """Fire-and-forget incident report. Never raises."""
    if not _ENABLED:
        return
    try:
        payload = json.dumps({
            "type": "test_failure",
            "title": title,
            "summary": summary,
            "detail": detail[:4000],
            "source": "pytest",
            "priority": "P3",
        }).encode()
        req = urllib.request.Request(
            f"{_API_BASE}/api/incidents",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=_TIMEOUT)
    except Exception as exc:
        logger.debug("Incidents API unavailable (non-fatal): %s", exc)


# pytest hook — called for each failed test report
def pytest_runtest_logreport(report):
    """Report test failures to the incidents API."""
    if not _ENABLED:
        return
    if report.when == "call" and report.failed:
        test_name = report.nodeid
        title = f"Test Failure: {test_name.split('::')[-1]}"
        summary = f"Pytest test '{test_name}' failed during CI/CD run."
        detail = ""
        if report.longrepr:
            if hasattr(report.longrepr, "reprtraceback"):
                detail = str(report.longrepr.reprtraceback)
            else:
                detail = str(report.longrepr)
        _report_incident(title=title, summary=summary, detail=detail)
