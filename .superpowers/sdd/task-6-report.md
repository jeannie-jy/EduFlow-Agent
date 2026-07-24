# Task 6 Report: Registration and Login Service

## RED

- `python -m pytest tests/test_auth_service.py -v` initially failed because
  `services.auth_service` did not exist.

## GREEN

- Added `agent/services/auth_service.py` with registration, login, opaque
  refresh-session creation, result/error types, normalized-email lookup,
  generic invalid credentials, password-hash replacement, and named unique
  constraint race handling in a nested transaction.
- Added `agent/tests/test_auth_service.py` covering registration/session token
  issuance, duplicate normalized email, named unique races, unknown email,
  wrong password, inactive users, last login, and password rehashing.
- Focused suite: `python -m pytest tests/test_auth_service.py -v` — 7 passed.

## Full Backend Suite

- `python -m pytest -v` — 441 passed, 3 skipped, 3 warnings.
- The warnings are pre-existing: one Starlette TestClient deprecation and two
  unrelated unawaited AsyncMock warnings in generation/version tests.

## Concerns

- SQLite drops timezone metadata when reloading a timezone-aware `DateTime`;
  the focused test therefore verifies that `last_login_at` is persisted rather
  than asserting the SQLite-reloaded timezone object.

## Commit

- `40ec71e893765f598f965463142948900b80b1cd` — `feat: implement registration and login service`
