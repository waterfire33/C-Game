# Placeholder Secret Enforcement Plan

## Objective
Prevent production startup when unsafe secret values are present.

## Target file
- foundation-skeleton/backend/app/core/config.py

## Unsafe values to block in production
- empty values
- whitespace-only values
- change-me
- secret
- test
- demo
- password
- 123456
- invalid env: references

## Required behavior
- allow current defaults in non-production if needed
- reject unsafe APP_SECRET_KEY in production
- fail startup early with a clear error
- keep logic centralized in config validation, not scattered across routes

## Implementation outline
- detect production mode from APP_ENV
- normalize secret value before checking
- raise a settings/config error if APP_SECRET_KEY is unsafe in production
- keep DATABASE_URL and REDIS_URL as required values
- do not silently auto-fix insecure values

## Acceptance criteria
- production startup fails for APP_SECRET_KEY=change-me
- production startup fails for empty or whitespace APP_SECRET_KEY
- non-production startup behavior remains compatible with current local workflow
- existing test suite still passes, or tests are updated intentionally

## Status
- draft
