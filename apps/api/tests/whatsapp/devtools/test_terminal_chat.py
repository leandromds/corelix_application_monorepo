"""Smoke tests for terminal_chat CLI."""

import sys
from uuid import uuid4

import pytest


class TestTerminalChat:
    def test_main_exits_for_invalid_uuid(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """UUID inválido deve causar sys.exit(1)."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "terminal_chat",
                "--professional-id",
                "not-a-uuid",
                "--client-phone",
                "+5511999999999",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            from whatsapp.devtools.terminal_chat import main

            main()
        assert exc_info.value.code == 1

    def test_build_args_parses_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_build_args deve parsear --professional-id e --client-phone."""
        prof_id = str(uuid4())
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "terminal_chat",
                "--professional-id",
                prof_id,
                "--client-phone",
                "+5511999999999",
            ],
        )
        from whatsapp.devtools.terminal_chat import _build_args

        args = _build_args()
        assert args.professional_id == prof_id
        assert args.client_phone == "+5511999999999"
