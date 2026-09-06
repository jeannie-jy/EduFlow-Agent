"""Sensitive diagnostics must not cross logs or API response boundaries."""

from services.redaction import public_failure_message, redact_diagnostic


def test_redact_diagnostic_removes_credentials_and_local_paths():
    message = (
        "postgresql+asyncpg://agent:super-secret@db/eduflow "
        "Authorization: Bearer sk-example123456 "
        r"C:\Users\person\private\prompt.txt"
    )

    redacted = redact_diagnostic(message)

    assert "super-secret" not in redacted
    assert "sk-example123456" not in redacted
    assert "person" not in redacted
    assert "[REDACTED" in redacted


def test_public_failure_messages_do_not_interpolate_diagnostics():
    secret = "sk-sensitive-value"
    assert secret not in public_failure_message("module")
    assert secret not in public_failure_message("render")
