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
