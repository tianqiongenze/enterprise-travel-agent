"""Tests for dual-window internal-secret rotation on the runtime side (Gap1).

Covers src.travel_agent.api.app._verify_signature, which must accept
signatures made with the current secret and, while
TRAVEL_INTERNAL_SHARED_SECRET_PREVIOUS is set, fall back to it for the
rotation window.
"""

from __future__ import annotations

import unittest

from src.travel_agent.security import make_internal_signature


class SecretRotationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        import src.travel_agent.api.app as app_module

        self.app_module = app_module
        self._prev_secret = app_module.shared_secret
        self._prev_previous = app_module.shared_secret_previous
        app_module.shared_secret = "rotation-current-secret"
        app_module.shared_secret_previous = ""

    def tearDown(self) -> None:
        self.app_module.shared_secret = self._prev_secret
        self.app_module.shared_secret_previous = self._prev_previous

    def test_current_secret_signature_accepted(self) -> None:
        sig = make_internal_signature("key-1", "rotation-current-secret", "techgroup-enterprise-travel-gateway")
        self.assertTrue(
            self.app_module._verify_signature("key-1", "techgroup-enterprise-travel-gateway", sig)
        )

    def test_unknown_secret_signature_rejected(self) -> None:
        sig = make_internal_signature("key-1", "not-a-real-secret", "techgroup-enterprise-travel-gateway")
        self.assertFalse(
            self.app_module._verify_signature("key-1", "techgroup-enterprise-travel-gateway", sig)
        )

    def test_previous_secret_accepted_during_rotation_window(self) -> None:
        self.app_module.shared_secret_previous = "rotation-old-secret"
        sig = make_internal_signature("key-2", "rotation-old-secret", "techgroup-enterprise-travel-gateway")
        self.assertTrue(
            self.app_module._verify_signature("key-2", "techgroup-enterprise-travel-gateway", sig)
        )

    def test_previous_secret_ignored_when_window_closed(self) -> None:
        # shared_secret_previous is empty: an old-secret signature must fail.
        sig = make_internal_signature("key-3", "rotation-old-secret", "techgroup-enterprise-travel-gateway")
        self.assertFalse(
            self.app_module._verify_signature("key-3", "techgroup-enterprise-travel-gateway", sig)
        )

    def test_clearing_previous_secret_closes_window(self) -> None:
        self.app_module.shared_secret_previous = "rotation-old-secret"
        sig = make_internal_signature("key-4", "rotation-old-secret", "techgroup-enterprise-travel-gateway")
        self.assertTrue(self.app_module._verify_signature("key-4", "techgroup-enterprise-travel-gateway", sig))
        self.app_module.shared_secret_previous = ""
        self.assertFalse(self.app_module._verify_signature("key-4", "techgroup-enterprise-travel-gateway", sig))


if __name__ == "__main__":
    unittest.main()
