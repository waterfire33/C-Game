# CI Requirements

## 1. Purpose
This document defines the minimum continuous integration requirements for the project.

## 2. Scope
CI must cover:
- backend test execution
- dependency installation validation
- migration sanity checks
- linting and type-checking once added
- failure visibility on push and pull request

## 3. Minimum required backend test command
The canonical backend test command is:

```bash
ENABLE_TELEMETRY=false DATABASE_URL=sqlite+aiosqlite:///:memory: REDIS_URL=redis://localhost:6379/0 PYTHONPATH=./foundation-skeleton/backend ./.venv/bin/python -m pytest -c pytest.ini foundation-skeleton/backend/tests -v
```

## 4. Required CI checks
- install dependencies in a clean environment
- run the canonical backend pytest command
- fail the build on any test failure
- fail the build on missing required config for the test environment
- validate that migrations can be loaded and checked safely
- add lint and type-check jobs when those tools are introduced

## 5. Trigger requirements
CI must run on:
- every push to main
- every pull request targeting main

## 6. Branch protection expectations
- merging to main should require passing CI checks
- failed checks should block merge
- production deployment should only happen from a known green commit or tag

## 7. Output requirements
CI must clearly show:
- which step failed
- raw test failure output
- environment/setup failure output
- migration validation failure output if applicable

## 8. Future CI additions
- lint job
- type-check job
- migration dry-run or validation job
- container/build validation job
- deployment readiness checks

## 9. Required implementation follow-up
- create a GitHub Actions workflow
- encode the canonical backend test command in CI
- define migration validation behavior
- add linting and type-checking once tools are selected
- document the required green checks before deployment

## 10. Status
- draft
