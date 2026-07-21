#!/usr/bin/env python3
# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Files (or comments on) a GitHub issue when a periodic job component fails.

Uses only the standard library so periodic jobs don't need extra pip
dependencies just to report a failure.
"""

import json
import os
import urllib.parse
import urllib.request

API_ROOT = "https://api.github.com"
DEFAULT_TOKEN_PATH = "/etc/github-token/token"


def _request(method, url, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "agent-sandbox-nightly-unit-tests")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _job_url():
    """Best-effort link to the failing build, using Prow's injected env vars."""
    job_name = os.environ.get("JOB_NAME")
    build_id = os.environ.get("BUILD_ID")
    if not job_name or not build_id:
        return None
    return (
        "https://prow.k8s.io/view/gs/kubernetes-ci-logs/logs/"
        f"sigs.k8s.io_agent-sandbox/{job_name}/{build_id}/"
    )


def ensure_failure_issue(repo, component, log_excerpt, token_path=DEFAULT_TOKEN_PATH):
    """Opens a new issue for a failing component, or comments on the existing open one.

    component must stay stable across runs: it's embedded as a marker used to find
    a previously filed issue for the same component, so renaming a component here
    without updating any open issue's marker will cause a duplicate to be filed.
    """
    with open(token_path) as f:
        token = f.read().strip()

    marker = f"<!-- nightly-unit-test-failure: {component} -->"
    query = f"repo:{repo} is:issue is:open in:body {marker}"
    search_url = f"{API_ROOT}/search/issues?q={urllib.parse.quote(query)}"
    results = _request("GET", search_url, token)

    body_lines = [marker, f"### Nightly unit tests failing: `{component}`", ""]
    job_url = _job_url()
    if job_url:
        body_lines.append(f"[Latest failing run]({job_url})")
    body_lines += [
        "",
        "<details><summary>Log excerpt</summary>",
        "",
        "```",
        log_excerpt,
        "```",
        "</details>",
    ]
    body = "\n".join(body_lines)

    if results.get("total_count", 0) > 0:
        issue_number = results["items"][0]["number"]
        comment_url = f"{API_ROOT}/repos/{repo}/issues/{issue_number}/comments"
        _request("POST", comment_url, token, {"body": body})
    else:
        issues_url = f"{API_ROOT}/repos/{repo}/issues"
        _request(
            "POST",
            issues_url,
            token,
            {
                "title": f"Nightly unit tests failing: {component}",
                "body": body,
                "labels": ["kind/failing-test"],
            },
        )
