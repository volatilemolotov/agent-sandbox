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
import unittest
from unittest import mock

# agent.py raises RuntimeError at import time if these aren't set.
os.environ.setdefault("OPENAI_BASE_URL", "http://test-invalid/v1/")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "test-model")

from fastapi.testclient import TestClient

import agent


def _completion(text):
    """Builds a minimal fake object matching the
    resp.choices[0].message.content shape agent.py reads."""
    message = mock.Mock(content=text)
    choice = mock.Mock(message=message)
    return mock.Mock(choices=[choice])


class AgentTest(unittest.TestCase):
    def setUp(self):
        agent._history.clear()
        self.client = TestClient(agent.app)

    def test_healthz(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    @mock.patch("agent._client")
    def test_chat_system_prompt_names_the_owner(self, mock_client):
        mock_client.chat.completions.create.return_value = _completion("hi")

        resp = self.client.post("/chat", json={"prompt": "hello"}, headers={"X-Owner": "alice"})

        self.assertEqual(resp.status_code, 200)
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertIn("alice", messages[0]["content"])
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1], {"role": "user", "content": "hello"})

    @mock.patch("agent._client")
    def test_chat_defaults_owner_to_anonymous(self, mock_client):
        mock_client.chat.completions.create.return_value = _completion("hi")

        resp = self.client.post("/chat", json={"prompt": "hello"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["owner"], "anonymous")

    @mock.patch("agent._client")
    def test_chat_returns_the_model_reply_and_turn_count(self, mock_client):
        mock_client.chat.completions.create.return_value = _completion("nice to meet you")

        resp = self.client.post("/chat", json={"prompt": "hi"}, headers={"X-Owner": "bob"})

        body = resp.json()
        self.assertEqual(body["owner"], "bob")
        self.assertEqual(body["reply"], "nice to meet you")
        self.assertEqual(body["history_turns"], 1)

    @mock.patch("agent._client")
    def test_chat_includes_prior_turns_in_the_next_call(self, mock_client):
        mock_client.chat.completions.create.return_value = _completion("turn one reply")
        self.client.post("/chat", json={"prompt": "turn one"}, headers={"X-Owner": "carol"})

        mock_client.chat.completions.create.return_value = _completion("turn two reply")
        resp = self.client.post("/chat", json={"prompt": "turn two"}, headers={"X-Owner": "carol"})

        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        # system + (user, assistant) from turn one + user from turn two
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[1], {"role": "user", "content": "turn one"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "turn one reply"})
        self.assertEqual(messages[3], {"role": "user", "content": "turn two"})
        self.assertEqual(resp.json()["history_turns"], 2)

    @mock.patch("agent._client")
    def test_chat_history_is_isolated_per_owner(self, mock_client):
        mock_client.chat.completions.create.return_value = _completion("alice's reply")
        self.client.post("/chat", json={"prompt": "hi"}, headers={"X-Owner": "alice"})

        mock_client.chat.completions.create.return_value = _completion("bob's reply")
        self.client.post("/chat", json={"prompt": "hi"}, headers={"X-Owner": "bob"})

        # bob's call must not have seen alice's turn in its message list.
        bob_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(len(bob_messages), 2)  # system + this user turn only

    @mock.patch("agent._client")
    def test_reset_clears_only_that_owners_history(self, mock_client):
        mock_client.chat.completions.create.return_value = _completion("reply")
        self.client.post("/chat", json={"prompt": "hi"}, headers={"X-Owner": "alice"})
        self.client.post("/chat", json={"prompt": "hi"}, headers={"X-Owner": "bob"})

        resp = self.client.post("/reset", headers={"X-Owner": "alice"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"owner": "alice", "reset": True})
        self.assertNotIn("alice", agent._history)
        self.assertIn("bob", agent._history)

    def test_history_deque_is_bounded(self):
        owner = "chatty"
        with mock.patch("agent._client") as mock_client:
            for i in range(agent._HISTORY_TURNS + 10):
                mock_client.chat.completions.create.return_value = _completion(f"reply {i}")
                self.client.post("/chat", json={"prompt": f"turn {i}"}, headers={"X-Owner": owner})

        # deque(maxlen=_HISTORY_TURNS * 2) holds user+assistant pairs.
        self.assertEqual(len(agent._history[owner]), agent._HISTORY_TURNS * 2)


if __name__ == "__main__":
    unittest.main()
