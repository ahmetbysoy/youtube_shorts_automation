"""Regression checks for the Phase 3 Actions module entrypoints; no network IO."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module", ["scripts.topic_history", "scripts.topic_persistence_probe"])
def test_phase3_module_help_without_pythonpath_or_credentials(module):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "GH_TOKEN", "GITHUB_TOKEN", "GITHUB_REPOSITORY"}
    }
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


@pytest.mark.parametrize(
    ("workflow", "module"),
    [
        ("daily_shorts.yml", "scripts.topic_history"),
        ("topic_history_persistence_probe.yml", "scripts.topic_persistence_probe"),
    ],
)
def test_workflows_invoke_phase3_modules(workflow, module):
    text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    assert f"python -m {module} " in text
    assert f"python {module.replace('.', '/')}.py " not in text


def test_probe_installs_its_pinned_requests_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    request_pin = next(line for line in requirements if line.startswith("requests=="))
    workflow = (ROOT / ".github/workflows/topic_history_persistence_probe.yml").read_text(encoding="utf-8")
    assert f"python -m pip install {request_pin}" in workflow


def test_ci_unit_test_command_removes_remote_history_environment():
    workflow = (ROOT / ".github/workflows/ubuntu_26_test.yml").read_text(encoding="utf-8")
    line = next(line.strip() for line in workflow.splitlines() if "python -m pytest -q tests" in line and not "tests/" in line)
    command = shlex.split(line.removeprefix("run: "))
    # Execute the workflow's actual environment prefix, but replace pytest with
    # a no-network assertion. GitHub's injected defaults must not select a store.
    prefix = command[:command.index("python")]
    env = dict(os.environ, GITHUB_REPOSITORY="owner/repo", GH_TOKEN="fixture", GITHUB_TOKEN="fixture")
    result = subprocess.run(
        prefix + [sys.executable, "-c", "from scripts.topic_history import make_store_from_environment; assert make_store_from_environment() is None"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
