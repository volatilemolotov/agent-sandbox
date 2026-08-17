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

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

SESSION_ID = "session-abc-123"

VALID_VERIFY = {
    "session": {"records_verified": True, "event_count_matches": True, "event_count": 12},
    "ledger": {
        "session_found": True,
        "session_digest_matches": True,
        "ledger_chain_verified": True,
    },
    "attestation": {
        "present": True,
        "signature_verified": True,
        "key_id_matches": True,
        "merkle_root_matches": True,
        "session_id_matches": True,
        "expected_public_key_matches": True,
    },
}

VALID_SESSION = {
    "session_id": SESSION_ID,
    "ended": True,
    "network_events": [{}, {}],
    "command_policy_events": [{}, {}, {}],
}


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def _run_script(tmp_path, verify_data, session_data, session_id=SESSION_ID):
    """Runs verify-audit.py fresh (it's straight-line top-level code, not
    reusable functions) against the given fixtures, by file path since
    verify-audit.py isn't a valid module name (hyphen)."""
    verify_path = os.path.join(tmp_path, "verification.json")
    session_path = os.path.join(tmp_path, "session.json")
    _write_json(verify_path, verify_data)
    _write_json(session_path, session_data)

    script_path = os.path.join(os.path.dirname(__file__), "verify-audit.py")
    with mock.patch.object(sys, "argv", ["verify-audit.py", verify_path, session_path, session_id]):
        spec = importlib.util.spec_from_file_location("nono_verify_audit", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


class VerifyAuditTest(unittest.TestCase):
    def setUp(self):
        self._tmp_dir_ctx = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp_dir_ctx.__enter__()
        self.addCleanup(self._tmp_dir_ctx.__exit__, None, None, None)

    def test_valid_session_passes_without_raising(self):
        _run_script(self.tmp_dir, VALID_VERIFY, VALID_SESSION)  # must not raise

    def test_wrong_session_id_fails(self):
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, VALID_VERIFY, VALID_SESSION, session_id="some-other-session")

    def test_unfinalized_session_fails(self):
        session = copy.deepcopy(VALID_SESSION)
        session["ended"] = False
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, VALID_VERIFY, session)

    def test_unverified_event_records_fails(self):
        verify = copy.deepcopy(VALID_VERIFY)
        verify["session"]["records_verified"] = False
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, verify, VALID_SESSION)

    def test_broken_ledger_chain_fails(self):
        verify = copy.deepcopy(VALID_VERIFY)
        verify["ledger"]["ledger_chain_verified"] = False
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, verify, VALID_SESSION)

    def test_missing_attestation_fails(self):
        verify = copy.deepcopy(VALID_VERIFY)
        verify["attestation"]["present"] = False
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, verify, VALID_SESSION)

    def test_signature_not_verified_fails(self):
        verify = copy.deepcopy(VALID_VERIFY)
        verify["attestation"]["signature_verified"] = False
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, verify, VALID_SESSION)

    def test_public_key_mismatch_fails(self):
        verify = copy.deepcopy(VALID_VERIFY)
        verify["attestation"]["expected_public_key_matches"] = False
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, verify, VALID_SESSION)

    def test_too_few_network_events_fails(self):
        session = copy.deepcopy(VALID_SESSION)
        session["network_events"] = [{}]  # only 1, need >= 2
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, VALID_VERIFY, session)

    def test_too_few_command_policy_events_fails(self):
        session = copy.deepcopy(VALID_SESSION)
        session["command_policy_events"] = [{}, {}]  # only 2, need >= 3
        with self.assertRaises(SystemExit):
            _run_script(self.tmp_dir, VALID_VERIFY, session)


if __name__ == "__main__":
    unittest.main()
