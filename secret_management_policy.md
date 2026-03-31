# Secret Management Policy

## 1. Scope
This policy defines how secrets are created, stored, loaded, rotated, revoked, and audited for the project.

## 2. What counts as a secret
- application secret keys
- jwt signing keys
- database credentials
- redis credentials
- api tokens
- mcp auth secrets
- third-party service credentials

## 3. Rules
- secrets must never be committed to git
- secrets must never be hardcoded in source files
- production secrets must only come from secure environment sources
- test secrets and development secrets must be separate from production secrets
- placeholder values must not be allowed in production
- secrets must be rotated when compromised, exposed, or deprecated

## 4. Environment separation
- local development uses local-only non-production secrets
- test environment uses test-only secrets
- staging uses staging-only secrets
- production uses production-only secrets
- no secret may be shared across all environments unless explicitly justified and documented

## 5. Storage and loading
- secrets are loaded through environment configuration
- secrets must be injected at runtime, not stored in the repository
- startup should fail in production if required secrets are missing or unsafe

## 6. Unsafe values
The following must be treated as unsafe in production:
- empty values
- whitespace-only values
- `changeme`
- `secret`
- `test`
- `demo`
- `password`
- `123456`
- placeholder `env:` references with no real target

## 7. Rotation and revocation
- define rotation owner
- define rotation schedule for long-lived secrets
- rotate immediately after exposure or suspected compromise
- revoke unused credentials promptly
- document the rotation procedure and validation steps

## 8. Auditing
- audit auth and secret-related config values regularly
- verify no secrets are committed to git
- verify production config does not use placeholders
- verify secrets differ by environment

## 9. Required implementation follow-up
- audit `foundation-skeleton/backend/app/core/config.py`
- audit `foundation-skeleton/backend/app/core/security.py`
- document password-hash migration away from legacy fallback
- add explicit production startup checks for unsafe secret values

## 10. Status
- draft
