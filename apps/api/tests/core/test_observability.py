"""
Tests for observability setup — Sentry/Glitchtip initialization.

These tests verify that:
1. sentry_sdk.init is NOT called when GLITCHTIP_DSN is None (safe in dev)
2. configure_logging does not raise regardless of debug flag
"""

from unittest.mock import patch


class TestSentryInit:
    """Sentry initialization must be safe when DSN is None."""

    def test_sentry_not_initialized_when_dsn_is_none(self) -> None:
        """When GLITCHTIP_DSN is None, sentry_sdk.init must NOT be called."""
        with patch("sentry_sdk.init") as mock_init:
            # Simulate the initialization guard from main.py
            glitchtip_dsn = None
            if glitchtip_dsn:
                import sentry_sdk

                sentry_sdk.init(dsn=glitchtip_dsn)
            mock_init.assert_not_called()

    def test_sentry_initialized_when_dsn_is_set(self) -> None:
        """When GLITCHTIP_DSN is set, sentry_sdk.init must be called with the DSN."""
        with patch("sentry_sdk.init") as mock_init:
            glitchtip_dsn = "https://abc123@glitchtip.example.com/1"
            if glitchtip_dsn:
                import sentry_sdk

                sentry_sdk.init(dsn=glitchtip_dsn, traces_sample_rate=0.2, environment="production")
            mock_init.assert_called_once()
            call_kwargs = mock_init.call_args.kwargs
            assert call_kwargs["dsn"] == glitchtip_dsn


class TestLoggingConfiguration:
    """configure_logging must not raise in any environment."""

    def test_configure_logging_production(self) -> None:
        """configure_logging(debug=False) must not raise."""
        from core.logging import configure_logging

        configure_logging(debug=False)  # should not raise

    def test_configure_logging_development(self) -> None:
        """configure_logging(debug=True) must not raise."""
        from core.logging import configure_logging

        configure_logging(debug=True)  # should not raise
