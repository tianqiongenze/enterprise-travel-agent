"""Tests for TRAVEL_A2A_INTERNAL_ONLY gating on /a2a/* (Gap1)."""

from __future__ import annotations

import unittest

from src.travel_agent.security import make_internal_signature


class A2aInternalModeTestCase(unittest.TestCase):
    def _set_flag(self, value: str) -> None:
        import src.travel_agent.api.app as app_module

        app_module.a2a_internal_only = value.strip().lower() == "true"

    def setUp(self) -> None:
        import src.travel_agent.api.app as app_module

        self.app_module = app_module
        self._prev_flag = app_module.a2a_internal_only
        self._prev_secret = app_module.shared_secret
        app_module.shared_secret = "test-internal-secret"
        self._prev_previous = app_module.shared_secret_previous
        app_module.shared_secret = "test-internal-secret"

    def tearDown(self) -> None:
        self.app_module.a2a_internal_only = self._prev_flag
        self.app_module.shared_secret = self._prev_secret
        self.app_module.shared_secret_previous = self._prev_previous

    def _headers(self, scope: str, secret: str = "test-internal-secret", client: str = "techgroup-enterprise-travel-gateway"):
        return {
            "X-Internal-Client-Id": client,
            "X-Internal-Signature": make_internal_signature(scope, secret, client),
            "X-A2A-Scope": scope,
        }

    def test_flag_off_allows_open_access(self) -> None:
        self._set_flag("false")
        result = self.app_module.a2a_send({"sender": "a", "receiver": "b", "topic": "t", "payload": {}})
        self.assertIn("message", result)

    def test_flag_on_without_signature_rejected(self) -> None:
        self._set_flag("true")
        with self.assertRaises(PermissionError):
            self.app_module.verify_a2a_internal_access(
                {"X-Internal-Client-Id": "", "X-Internal-Signature": "", "X-A2A-Scope": "inbox.b"}
            )

    def test_flag_on_bad_signature_rejected(self) -> None:
        self._set_flag("true")
        headers = self._headers("inbox.b", secret="wrong-secret")
        with self.assertRaises(PermissionError):
            self.app_module.verify_a2a_internal_access(headers)

    def test_flag_on_untrusted_client_rejected(self) -> None:
        self._set_flag("true")
        headers = self._headers("inbox.b", client="rogue-gateway")
        with self.assertRaises(PermissionError):
            self.app_module.verify_a2a_internal_access(headers)

    def test_flag_on_valid_signature_passes(self) -> None:
        self._set_flag("true")
        self.app_module.verify_a2a_internal_access(self._headers("inbox.trip-planner-agent"))

    def test_flag_on_previous_secret_window_passes(self) -> None:
        self._set_flag("true")
        import src.travel_agent.api.app as app_module

        previous = app_module.shared_secret_previous
        app_module.shared_secret_previous = "old-internal-secret"
        try:
            headers = self._headers("inbox.b", secret="old-internal-secret")
            app_module.verify_a2a_internal_access(headers)
        finally:
            app_module.shared_secret_previous = previous


if __name__ == "__main__":
    unittest.main()
