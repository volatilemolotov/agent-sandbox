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

import hashlib
import os
import unittest
from unittest import mock

# gateway.py reads API_SERVER_KEY unconditionally at import time
# (os.environ["API_SERVER_KEY"], no default) and calls
# config.load_incluster_config()/CustomObjectsApi() at module level too, so
# both have to be in place before the module is ever imported.
os.environ.setdefault("API_SERVER_KEY", "test-api-server-key")

with mock.patch("kubernetes.config.load_incluster_config"), \
     mock.patch("kubernetes.client.CustomObjectsApi") as _mock_crd_cls:
    _mock_crd_at_import = _mock_crd_cls.return_value
    import gateway


def _reset_gateway_state():
    """gateway.py's in-flight/last-activity dicts are module-level and
    mutated by routes; each test gets a clean slate plus a fresh CRD mock
    so assertions on call counts aren't polluted by other tests."""
    gateway.last_activity.clear()
    gateway.in_flight.clear()
    gateway.crd = mock.MagicMock()
    return gateway.crd


def _claim(user, token=None, extra_annotations=None):
    annotations = dict(extra_annotations or {})
    if token is not None:
        annotations[gateway.TOKEN_ANNOTATION] = hashlib.sha256(token.encode()).hexdigest()
    return {
        "metadata": {"name": gateway.claim_name(user), "annotations": annotations},
        "status": {"sandbox": {"name": f"{gateway.claim_name(user)}-sandbox"}},
    }


def _sandbox(mode="Running", ready=None, suspended=None, fqdn="sb.hermes-demo.svc"):
    conditions = []
    if ready is not None:
        conditions.append({"type": "Ready", "status": "True" if ready else "False"})
    if suspended is not None:
        conditions.append({"type": "Suspended", "status": "True" if suspended else "False"})
    return {
        "metadata": {"name": "hermes-alice-sandbox"},
        "spec": {"operatingMode": mode},
        "status": {"conditions": conditions, "serviceFQDN": fqdn},
    }


class PureFunctionTest(unittest.TestCase):
    def test_claim_name(self):
        self.assertEqual(gateway.claim_name("alice"), "hermes-alice")

    def test_condition_true(self):
        obj = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        self.assertTrue(gateway.condition(obj, "Ready"))

    def test_condition_false(self):
        obj = {"status": {"conditions": [{"type": "Ready", "status": "False"}]}}
        self.assertFalse(gateway.condition(obj, "Ready"))

    def test_condition_missing_type(self):
        obj = {"status": {"conditions": [{"type": "Other", "status": "True"}]}}
        self.assertFalse(gateway.condition(obj, "Ready"))

    def test_condition_no_status_block(self):
        self.assertFalse(gateway.condition({}, "Ready"))

    def test_derive_state_provisioning_when_no_sandbox(self):
        self.assertEqual(gateway.derive_state(None), "Provisioning")

    def test_derive_state_ready(self):
        self.assertEqual(gateway.derive_state(_sandbox(mode="Running", ready=True)), "Ready")

    def test_derive_state_waking(self):
        self.assertEqual(gateway.derive_state(_sandbox(mode="Running", ready=False)), "Waking")

    def test_derive_state_suspended(self):
        sb = _sandbox(mode="Suspended", suspended=True)
        self.assertEqual(gateway.derive_state(sb), "Suspended")

    def test_derive_state_suspending(self):
        sb = _sandbox(mode="Suspended", suspended=False)
        self.assertEqual(gateway.derive_state(sb), "Suspending")


class AuthorizedTest(unittest.TestCase):
    def setUp(self):
        _reset_gateway_state()
        self.app = gateway.app.test_client()

    def test_correct_token_is_authorized(self):
        claim = _claim("alice", token="secret-token")
        with gateway.app.test_request_context(headers={"Authorization": "Bearer secret-token"}):
            self.assertTrue(gateway.authorized(claim))

    def test_wrong_token_is_not_authorized(self):
        claim = _claim("alice", token="secret-token")
        with gateway.app.test_request_context(headers={"Authorization": "Bearer wrong-token"}):
            self.assertFalse(gateway.authorized(claim))

    def test_missing_token_is_not_authorized(self):
        claim = _claim("alice", token="secret-token")
        with gateway.app.test_request_context():
            self.assertFalse(gateway.authorized(claim))

    def test_no_stored_annotation_is_not_authorized(self):
        claim = _claim("alice")  # no token annotation at all
        with gateway.app.test_request_context(headers={"Authorization": "Bearer anything"}):
            self.assertFalse(gateway.authorized(claim))


class CreateUserTest(unittest.TestCase):
    def setUp(self):
        self.crd = _reset_gateway_state()
        self.app = gateway.app.test_client()

    def test_rejects_invalid_username(self):
        resp = self.app.post("/users", json={"user": "Not_Valid!"})
        self.assertEqual(resp.status_code, 400)

    def test_rejects_missing_username(self):
        resp = self.app.post("/users", json={})
        self.assertEqual(resp.status_code, 400)

    def test_conflict_when_user_already_exists(self):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="x")
        resp = self.app.post("/users", json={"user": "alice"})
        self.assertEqual(resp.status_code, 409)
        self.crd.create_namespaced_custom_object.assert_not_called()

    @mock.patch("gateway.wait_ready")
    def test_success_creates_claim_and_returns_token_once(self, mock_wait_ready):
        self.crd.get_namespaced_custom_object.return_value = None
        mock_wait_ready.return_value = _sandbox(mode="Running", ready=True)

        resp = self.app.post("/users", json={"user": "alice"})

        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["user"], "alice")
        self.assertEqual(body["state"], "Ready")
        self.assertTrue(body["token"])

        self.crd.create_namespaced_custom_object.assert_called_once()
        args, kwargs = self.crd.create_namespaced_custom_object.call_args
        created_body = args[-1] if not kwargs else kwargs.get("body", args[-1])
        stored_hash = created_body["metadata"]["annotations"][gateway.TOKEN_ANNOTATION]
        self.assertEqual(stored_hash, hashlib.sha256(body["token"].encode()).hexdigest())
        self.assertNotEqual(body["token"], stored_hash, "the raw token itself must never be stored")

    def test_concurrent_signup_race_returns_409(self):
        import kubernetes.client
        self.crd.get_namespaced_custom_object.return_value = None
        api_exc = kubernetes.client.ApiException(status=409)
        self.crd.create_namespaced_custom_object.side_effect = api_exc

        resp = self.app.post("/users", json={"user": "alice"})
        self.assertEqual(resp.status_code, 409)


class GetUserTest(unittest.TestCase):
    def setUp(self):
        self.crd = _reset_gateway_state()
        self.app = gateway.app.test_client()

    def test_unknown_user_404(self):
        self.crd.get_namespaced_custom_object.return_value = None
        resp = self.app.get("/users/nobody")
        self.assertEqual(resp.status_code, 404)

    def test_wrong_token_401(self):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        resp = self.app.get("/users/alice", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(resp.status_code, 401)

    @mock.patch("gateway.sandbox_of")
    def test_authorized_returns_state(self, mock_sandbox_of):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True)

        resp = self.app.get("/users/alice", headers={"Authorization": "Bearer secret"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["state"], "Ready")


class DeleteUserTest(unittest.TestCase):
    def setUp(self):
        self.crd = _reset_gateway_state()
        self.app = gateway.app.test_client()

    def test_unknown_user_404(self):
        self.crd.get_namespaced_custom_object.return_value = None
        resp = self.app.delete("/users/nobody")
        self.assertEqual(resp.status_code, 404)

    def test_wrong_token_401_and_does_not_delete(self):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        resp = self.app.delete("/users/alice", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(resp.status_code, 401)
        self.crd.delete_namespaced_custom_object.assert_not_called()

    def test_authorized_deletes_claim(self):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        gateway.last_activity["alice"] = 12345.0

        resp = self.app.delete("/users/alice", headers={"Authorization": "Bearer secret"})

        self.assertEqual(resp.status_code, 200)
        self.crd.delete_namespaced_custom_object.assert_called_once_with(
            gateway.GROUP, gateway.VERSION, gateway.NAMESPACE,
            "sandboxclaims", "hermes-alice")
        self.assertNotIn("alice", gateway.last_activity)

    def test_already_deleted_is_idempotent_success(self):
        import kubernetes.client
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        self.crd.delete_namespaced_custom_object.side_effect = \
            kubernetes.client.ApiException(status=404)

        resp = self.app.delete("/users/alice", headers={"Authorization": "Bearer secret"})
        self.assertEqual(resp.status_code, 200)


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.crd = _reset_gateway_state()
        self.app = gateway.app.test_client()

    def test_unknown_user_404(self):
        self.crd.get_namespaced_custom_object.return_value = None
        resp = self.app.get("/u/nobody/v1/models")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(gateway.in_flight.get("nobody", 0), 0, "an early-rejected request must not leak an in-flight reservation")

    def test_wrong_token_401(self):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        resp = self.app.get("/u/alice/v1/models", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(gateway.in_flight.get("alice", 0), 0)

    @mock.patch("gateway.sandbox_of")
    def test_sandbox_not_provisioned_returns_503(self, mock_sandbox_of):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        mock_sandbox_of.return_value = None

        resp = self.app.get("/u/alice/v1/models", headers={"Authorization": "Bearer secret"})

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(gateway.in_flight.get("alice", 0), 0)

    @mock.patch("gateway.wait_ready")
    @mock.patch("gateway.set_operating_mode")
    @mock.patch("gateway.sandbox_of")
    def test_suspended_sandbox_wakes_on_connect(self, mock_sandbox_of, mock_set_mode, mock_wait_ready):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        mock_sandbox_of.return_value = _sandbox(mode="Suspended", suspended=True)
        mock_wait_ready.return_value = None  # never comes back Ready within WAKE_TIMEOUT

        resp = self.app.get("/u/alice/v1/models", headers={"Authorization": "Bearer secret"})

        mock_set_mode.assert_called_once_with("hermes-alice-sandbox", "Running")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.headers.get("Retry-After"), "10")

    @mock.patch("gateway.requests.request")
    @mock.patch("gateway.sandbox_of")
    def test_v1_path_routes_to_api_port_with_platform_key(self, mock_sandbox_of, mock_request):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True, fqdn="sb.hermes-demo.svc")
        upstream_resp = mock.MagicMock(status_code=200, headers={}, iter_content=lambda chunk_size: iter([b"ok"]))
        mock_request.return_value = upstream_resp

        resp = self.app.get("/u/alice/v1/models", headers={"Authorization": "Bearer secret"})
        resp.get_data()  # drain relay()'s generator -- its `finally` (end_flight) only runs once fully consumed

        self.assertEqual(resp.status_code, 200)
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(mock_request.call_args.args[1], "http://sb.hermes-demo.svc:8642/v1/models")
        self.assertEqual(call_kwargs["headers"]["Authorization"], f"Bearer {gateway.API_SERVER_KEY}")
        self.assertEqual(gateway.in_flight.get("alice", 0), 0, "in-flight reservation must be released once the stream completes")

    @mock.patch("gateway.requests.request")
    @mock.patch("gateway.sandbox_of")
    def test_non_v1_path_routes_to_dashboard_port_without_platform_key(self, mock_sandbox_of, mock_request):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True, fqdn="sb.hermes-demo.svc")
        upstream_resp = mock.MagicMock(status_code=200, headers={}, iter_content=lambda chunk_size: iter([b"<html>"]))
        mock_request.return_value = upstream_resp

        resp = self.app.get("/u/alice/dashboard", headers={"Authorization": "Bearer secret"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_request.call_args.args[1], "http://sb.hermes-demo.svc:9119/dashboard")
        self.assertNotIn("Authorization", mock_request.call_args.kwargs["headers"])

    @mock.patch("gateway.requests.request")
    @mock.patch("gateway.sandbox_of")
    def test_token_query_param_is_never_forwarded_upstream(self, mock_sandbox_of, mock_request):
        self.crd.get_namespaced_custom_object.return_value = _claim("alice", token="secret")
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True)
        upstream_resp = mock.MagicMock(status_code=200, headers={}, iter_content=lambda chunk_size: iter([b"ok"]))
        mock_request.return_value = upstream_resp

        self.app.get("/u/alice/v1/models?token=secret&other=1",
                      headers={"Authorization": "Bearer secret"})

        forwarded_params = dict(mock_request.call_args.kwargs["params"])
        self.assertNotIn("token", forwarded_params)
        self.assertEqual(forwarded_params.get("other"), "1")


class IdleSweeperTest(unittest.TestCase):
    """Exercises one pass of idle_sweeper()'s body. time.sleep(15) is the
    first statement in the loop (before the try block), so it has to
    succeed once to let the body run at all, then raise on the second call
    -- at the top of the next iteration -- to break out afterward."""

    class _StopLoop(Exception):
        pass

    def setUp(self):
        self.crd = _reset_gateway_state()

    def _run_one_pass(self):
        with mock.patch("gateway.time.sleep", side_effect=[None, self._StopLoop]):
            with self.assertRaises(self._StopLoop):
                gateway.idle_sweeper()

    @mock.patch("gateway.set_operating_mode")
    @mock.patch("gateway.sandbox_of")
    def test_suspends_ready_user_idle_past_timeout(self, mock_sandbox_of, mock_set_mode):
        self.crd.list_namespaced_custom_object.return_value = {"items": [_claim("alice", token="x")]}
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True)
        gateway.last_activity["alice"] = 0.0  # far in the past => idle

        self._run_one_pass()

        mock_set_mode.assert_called_once_with("hermes-alice-sandbox", "Suspended")

    @mock.patch("gateway.set_operating_mode")
    @mock.patch("gateway.sandbox_of")
    def test_does_not_suspend_recently_active_user(self, mock_sandbox_of, mock_set_mode):
        self.crd.list_namespaced_custom_object.return_value = {"items": [_claim("alice", token="x")]}
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True)
        gateway.last_activity["alice"] = __import__("time").time()  # just now

        self._run_one_pass()

        mock_set_mode.assert_not_called()

    @mock.patch("gateway.set_operating_mode")
    @mock.patch("gateway.sandbox_of")
    def test_does_not_suspend_user_with_request_in_flight(self, mock_sandbox_of, mock_set_mode):
        self.crd.list_namespaced_custom_object.return_value = {"items": [_claim("alice", token="x")]}
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=True)
        gateway.last_activity["alice"] = 0.0
        gateway.in_flight["alice"] = 1  # a proxy request is being served right now

        self._run_one_pass()

        mock_set_mode.assert_not_called()

    @mock.patch("gateway.set_operating_mode")
    @mock.patch("gateway.sandbox_of")
    def test_does_not_suspend_non_ready_sandbox(self, mock_sandbox_of, mock_set_mode):
        self.crd.list_namespaced_custom_object.return_value = {"items": [_claim("alice", token="x")]}
        mock_sandbox_of.return_value = _sandbox(mode="Running", ready=False)
        gateway.last_activity["alice"] = 0.0

        self._run_one_pass()

        mock_set_mode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
