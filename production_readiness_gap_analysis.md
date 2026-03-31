# Production Readiness Gap Analysis

## 1. Auth and secrets hardening
- Current state
  - Authentication flow exists in the backend.
  - Password hashing has been modernized toward `pwdlib` / Argon2.
  - Legacy Passlib / bcrypt fallback still exists for backward compatibility with older hashes.
  - `secret_ref` validation has been moved into the schema layer instead of route-body handling.
  - Secret and environment configuration are being loaded through backend config instead of hardcoded values.

- Risks
  - Legacy password-hash fallback increases long-term attack surface and maintenance burden.
  - It is still unclear whether all existing password hashes have been migrated to Argon2.
  - Secret rotation and secret lifecycle are not yet documented.
  - There is no confirmed audit yet for weak default values, accidental dev secrets, or environment drift between local, test, and production.
  - There is no confirmed policy yet for separating test-only secrets from production secrets.

- Required fixes
  - Remove Passlib / bcrypt fallback after confirming all stored hashes are migrated.
  - Document the password migration strategy and rollback path.
  - Audit all auth- and secret-related config values for weak defaults or unsafe placeholders.
  - Define a production secret-management policy for generation, storage, rotation, and revocation.
  - Confirm that production secrets are only loaded from secure environment sources and are never committed.
  - Add explicit checks to prevent startup with unsafe or placeholder secret values in production.

- Priority
  - high

## 2. Database migration safety
- Current state
  - The backend now includes multiple Alembic migration files beyond the initial migration.
  - New workflow-, planner-, tool-, approval-, and MCP-related models have been introduced.
  - The project is using migration-based schema evolution rather than relying only on ad hoc table creation.
  - The backend test suite passes against the current code and migration state in the local workflow.

- Risks
  - There is no confirmed review yet for migration ordering, downgrade correctness, or production safety under real data.
  - Multi-step schema changes can fail if production data does not match local assumptions.
  - Destructive changes, nullable-to-non-nullable transitions, and enum/state changes may cause deployment failures or partial rollouts.
  - There is no confirmed documented process yet for backup-before-migrate, rollback-after-failure, or migration dry runs.
  - Long-running migrations could cause downtime or lock contention in production databases.

- Required fixes
  - Audit every migration file for upgrade and downgrade correctness.
  - Test migrations from a clean database and from realistic existing database states.
  - Identify any destructive or locking-prone migrations and split them into safer staged migrations if needed.
  - Document the exact production migration runbook, including pre-checks, backup step, execution order, validation, and rollback steps.
  - Add a migration validation step to CI so schema drift is caught before deployment.
  - Confirm that application startup behavior is safe if the code version and database schema are temporarily out of sync during deployment.

- Priority
  - high

## 3. Logging and observability
- Current state
  - Telemetry logic has been moved into FastAPI lifespan instead of import-time startup behavior.
  - Test behavior has been adjusted so telemetry exporters are skipped in test runs.
  - The codebase now has clearer startup control than before the cleanup.
  - There is at least a basic observability direction, but production-level operational visibility is not yet confirmed.

- Risks
  - It is still unclear whether request logging, error logging, structured logs, correlation IDs, and audit-critical events are consistently captured.
  - Failures in worker execution, approvals, planner flows, MCP execution, and tool calls may be hard to diagnose without structured observability.
  - There is no confirmed alerting strategy yet for production incidents.
  - There is no confirmed metrics baseline yet for latency, failures, queue depth, auth failures, or migration/deployment health.
  - Without production observability standards, incidents may become debugging exercises instead of controlled responses.

- Required fixes
  - Define a structured logging format and use it consistently across API, worker, planner, MCP, and tool execution paths.
  - Add correlation/request IDs so multi-step workflow execution can be traced end to end.
  - Identify the minimum required production metrics: request rate, error rate, latency, background job failures, approval backlog, and tool/MCP execution failures.
  - Document which events must be logged for security and auditability.
  - Add health checks and startup diagnostics that are useful in deployment, not just in local tests.
  - Define alert thresholds and incident triage signals for the first production environment.

- Priority
  - medium-high

## 4. CI and automated checks
- Current state
  - The backend has a known-good canonical pytest command from repo root.
  - The backend suite currently passes with 73 tests.
  - The project now has clearer workflow documentation, a Makefile, and a cleaner dependency story.
  - Manual local validation is much better than before the cleanup.

- Risks
  - There is no confirmed CI pipeline yet enforcing the passing test suite automatically on pushes and pull requests.
  - Migration validity, dependency integrity, and environment consistency can regress silently without CI enforcement.
  - Local success alone does not protect the branch from future broken commits.
  - The repo previously suffered from mixed-scope Git noise, showing that process enforcement is still weak.
  - Without automated checks, production readiness will depend too much on manual memory and discipline.

- Required fixes
  - Add a CI workflow that runs the canonical backend test command on every push and pull request.
  - Add separate CI jobs for dependency installation, migration sanity, and test execution.
  - Add a fast failure step for missing config or invalid startup behavior.
  - Ensure CI uses a reproducible environment matching the documented local workflow.
  - Add branch protection expectations so failing checks block merges.
  - Document the minimum required green checks before deployment.

- Priority
  - high

## 5. Linting and type checking
- Current state
  - The codebase has been stabilized functionally through tests.
  - Dependency and workflow cleanup improved maintainability.
  - There is currently no confirmed enforced linting or type-checking gate in the project baseline.

- Risks
  - Style drift, dead code, import issues, and type regressions can accumulate even while tests still pass.
  - Tests do not catch every maintainability or correctness issue.
  - Refactors across backend models, schemas, services, and worker flows will become riskier without static analysis.
  - New contributors or future LLM-assisted changes can easily introduce subtle quality regressions.

- Required fixes
  - Add a formatter/linter standard for the backend and document it.
  - Add type checking for the backend and define the minimum acceptable strictness level.
  - Add lint and type-check commands to the Makefile and CI.
  - Fix high-value typing gaps first in config, auth, DB session, services, and worker code.
  - Make linting and typing part of the normal pre-commit or pre-push workflow.

- Priority
  - medium-high

## 6. Deployment readiness
- Current state
  - The project now has a cleaner backend structure, migrations, tests, and documented commands.
  - Startup behavior is safer than before because telemetry was moved into lifespan.
  - There is already Docker- and environment-related project structure in the repo.
  - The codebase is much closer to a deployable baseline than it was before cleanup.

- Risks
  - There is no confirmed end-to-end production deployment runbook yet.
  - It is still unclear whether environment variables, secrets, migrations, app startup order, worker startup, and health checks are deployment-safe in real infrastructure.
  - There is no confirmed staging-validation process yet before production deployment.
  - If app, worker, DB, Redis, and migrations are not coordinated correctly, deployments may partially succeed and leave the system in a broken state.
  - Operational ownership during deployment failure is not yet defined.

- Required fixes
  - Document the exact deployment sequence for backend, migrations, worker components, and supporting services.
  - Define required environment variables and production-safe defaults.
  - Validate container/build behavior in a staging-like environment.
  - Add startup/readiness checks for app and worker services.
  - Define deployment acceptance checks: migration success, app health, worker health, and key endpoint verification.
  - Create a rollback procedure tied to specific deploy failure modes.

- Priority
  - high

## 7. Backup and rollback plan
- Current state
  - A clean Git baseline now exists and has been tagged.
  - The project has a known rollback point at the code level.
  - The codebase now has a much clearer checkpoint than before the Git cleanup.

- Risks
  - Code rollback alone is not enough if database schema or production data changes have already been applied.
  - There is no fully documented backup-and-restore runbook yet for database and operational state.
  - A failed deploy could require coordinated rollback across code, migrations, background processes, and secrets/config.
  - Without a defined rollback owner and procedure, recovery time will be slow and improvised.

- Required fixes
  - Define pre-deployment backup requirements for the production database.
  - Document exactly when rollback should use Git revert, redeploy of prior image, migration rollback, or database restore.
  - Classify migrations into reversible and non-reversible categories.
  - Define a deployment checkpoint procedure: backup, deploy, validate, decide go/no-go, then either continue or rollback.
  - Record the current clean Git tag as the first formal rollback anchor.
  - Write a short emergency recovery runbook with step order and decision rules.

- Priority
  - high