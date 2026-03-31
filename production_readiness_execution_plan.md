# Production Readiness Execution Plan

## Phase 1 — high-risk blockers
1. Auth and secrets hardening
2. Database migration safety
3. CI and automated checks
4. Deployment readiness
5. Backup and rollback plan

## Phase 2 — operational quality
6. Logging and observability
7. Linting and type checking

## Immediate next actions
- Audit auth and secret configuration in `foundation-skeleton/backend/app/core/config.py`
- Audit password hashing and fallback behavior in `foundation-skeleton/backend/app/core/security.py`
- Review all Alembic migrations in `foundation-skeleton/backend/alembic/versions/`
- Define the canonical CI command for backend tests
- Write the production migration runbook
- Write the deployment runbook
- Write the rollback runbook

## Deliverables
- secret_management_policy.md
- migration_runbook.md
- deployment_runbook.md
- rollback_runbook.md
- ci_requirements.md

## Definition of done
- Production secrets policy documented
- Migration process tested and documented
- CI runs automatically on push and pull request
- Deployment sequence documented
- Rollback procedure documented
- Observability minimum standard defined
- Linting and type checking added to workflow
