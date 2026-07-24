# Task 5 Report: Authentication Schemas and Errors

## Files

- `agent/schema/auth.py` — request and response schemas with shared password-policy validation.
- `agent/api/auth_errors.py` — stable authentication HTTP error constructors.
- `agent/tests/test_auth_api.py` — schema normalization, validation, response, and error-contract tests.

## RED

`python -m pytest tests/test_auth_api.py -v` failed during collection as expected because `api.auth_errors` did not exist.

## GREEN

After the Task 5 modules were added, `python -m pytest tests/test_auth_api.py -v` passed: 12 passed.

## Full backend suite

`python -m pytest -v` passed: 421 passed, 3 skipped, 2 warnings in 12.99s.

## Concerns

The full suite emits two pre-existing `RuntimeWarning` messages for unawaited `AsyncMock` calls in generation/version tests outside Task 5. No Task 5 test or file emitted a warning.

## SHA

`d51d4775601dbd9cce465b0788798830183bf4eb` (`feat: define authentication API contracts`)

## Review fixes

- Added live FastAPI tests for every authentication error response, including the response body, status code, and `WWW-Authenticate: Bearer` headers on 401 responses.
- Preserved `HTTPException` headers when the global handler constructs JSON responses.
- Added a typed `PasswordPolicyViolation` path so registration password-policy failures return the documented `400 PASSWORD_POLICY_VIOLATION` contract while ordinary request validation remains `422 VALIDATION_ERROR`.
- Declared password limits in OpenAPI and enforced login limits of 128 characters and 256 UTF-8 bytes without applying registration password-complexity rules.

### Review RED/GREEN

- RED: the new focused suite initially had 7 failures: missing OpenAPI/login limits, lost 401 headers, and a weak registration password returned generic 422.
- GREEN: `python -m pytest tests/test_auth_api.py -v` passed: 25 passed.

### Review full backend suite

`python -m pytest -v` passed: 434 passed, 3 skipped, 3 warnings in 11.65s.

### Review concerns

The focused TestClient suite emits a Starlette deprecation warning from the installed dependency. The full suite also retains the two pre-existing unawaited-`AsyncMock` warnings in unrelated generation/version tests.

### Review SHA

`9d85f671c8eb74f9822105a9cb622249d6ac53c0` (`fix: preserve authentication error contracts`)
