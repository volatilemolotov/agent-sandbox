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

import os
import tempfile
import unittest

# WORKSPACE is created on the real filesystem at import time
# (os.environ.get("SANDBOX_WORKSPACE", "/workspace")), so point it at a
# scratch dir before importing rather than writing into /workspace.
_workspace_dir = tempfile.mkdtemp(prefix="firecracker-sandbox-test-")
os.environ["SANDBOX_WORKSPACE"] = _workspace_dir

from fastapi.testclient import TestClient

import main


class HealthAndRootTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_health_returns_204(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 204)

    def test_root_probe(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["runtime"], "firecracker-sandbox")

    def test_metrics_always_has_a_timestamp(self):
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("timestamp", resp.json())


class SafePathTest(unittest.TestCase):
    def test_relative_path_within_workspace_is_allowed(self):
        resolved = main._safe_path("subdir/file.txt")
        self.assertTrue(str(resolved).startswith(str(main.WORKSPACE.resolve())))

    def test_relative_traversal_outside_workspace_is_rejected(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            main._safe_path("../../etc/passwd")
        self.assertEqual(cm.exception.status_code, 403)

    def test_absolute_path_outside_workspace_is_rejected(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            main._safe_path("/etc/passwd")
        self.assertEqual(cm.exception.status_code, 403)

    def test_absolute_path_inside_workspace_is_allowed(self):
        inside = str(main.WORKSPACE.resolve() / "ok.txt")
        resolved = main._safe_path(inside)
        self.assertEqual(str(resolved), inside)


class InitAndEnvsTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main._user_env.clear()

    def test_init_merges_envs(self):
        resp = self.client.post("/init", json={"envs": {"MY_VAR": "hello"}})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(main._user_env["MY_VAR"], "hello")
        self.assertEqual(os.environ["MY_VAR"], "hello")

    def test_init_without_timestamp_has_no_skew(self):
        resp = self.client.post("/init", json={})
        self.assertIsNone(resp.json()["skew_seconds"])

    def test_init_with_timestamp_computes_skew(self):
        import time
        resp = self.client.post("/init", json={"timestamp": time.time() - 5})
        self.assertGreaterEqual(resp.json()["skew_seconds"], 4)

    def test_envs_reflects_user_env(self):
        self.client.post("/init", json={"envs": {"VISIBLE_VAR": "yes"}})
        resp = self.client.get("/envs")
        self.assertEqual(resp.json()["VISIBLE_VAR"], "yes")


class ExecTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_args_mode_runs_without_shell(self):
        resp = self.client.post("/exec", json={"cmd": "echo", "args": ["hello"]})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["stdout"], "hello\n")
        self.assertEqual(body["exit_code"], 0)

    def test_shell_mode_when_args_omitted(self):
        resp = self.client.post("/exec", json={"cmd": "echo $((1 + 1))"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["stdout"].strip(), "2")

    def test_nonexistent_binary_returns_127(self):
        resp = self.client.post("/exec", json={"cmd": "this-binary-does-not-exist-xyz", "args": []})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["exit_code"], 127)

    def test_timeout_returns_negative_one_and_notes_timeout(self):
        resp = self.client.post("/exec", json={"cmd": "sleep", "args": ["5"], "timeout": 0.2})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["exit_code"], -1)
        self.assertIn("timeout", body["stderr"])

    def test_env_vars_are_passed_through(self):
        resp = self.client.post("/exec", json={
            "cmd": "sh", "args": ["-c", "echo $MY_EXEC_VAR"],
            "env": {"MY_EXEC_VAR": "exec-value"},
        })
        self.assertEqual(resp.json()["stdout"].strip(), "exec-value")

    def test_nonexistent_cwd_returns_400(self):
        resp = self.client.post("/exec", json={"cmd": "echo", "args": ["hi"], "cwd": "does-not-exist"})
        self.assertEqual(resp.status_code, 400)

    def test_cwd_path_traversal_returns_403(self):
        resp = self.client.post("/exec", json={"cmd": "echo", "args": ["hi"], "cwd": "../../etc"})
        self.assertEqual(resp.status_code, 403)


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_upload_then_download_round_trip(self):
        upload = self.client.post(
            "/files",
            data={"path": "greeting.txt"},
            files={"file": ("greeting.txt", b"hello world", "text/plain")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(upload.json()["path"], "greeting.txt")
        self.assertEqual(upload.json()["size"], len(b"hello world"))

        download = self.client.get("/files", params={"path": "greeting.txt"})
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"hello world")

    def test_download_missing_file_404(self):
        resp = self.client.get("/files", params={"path": "does-not-exist.txt"})
        self.assertEqual(resp.status_code, 404)

    def test_download_path_traversal_403(self):
        resp = self.client.get("/files", params={"path": "../../etc/passwd"})
        self.assertEqual(resp.status_code, 403)

    def test_upload_creates_parent_directories(self):
        upload = self.client.post(
            "/files",
            data={"path": "nested/dir/file.txt"},
            files={"file": ("file.txt", b"data", "text/plain")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(upload.json()["path"], os.path.join("nested", "dir", "file.txt"))


if __name__ == "__main__":
    unittest.main()
