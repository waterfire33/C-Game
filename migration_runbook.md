# Migration Runbook

## 1. Purpose
This runbook defines how database migrations must be reviewed, tested, executed, validated, and rolled back.

## 2. Scope
This applies to all schema migrations in:
- `foundation-skeleton/backend/alembic/versions/`

## 3. Pre-migration checks
- confirm the target commit is clean and tagged if needed
- confirm the deployment window
- confirm database backup capability
- confirm the exact migration files included in the release
- review upgrade and downgrade paths
- identify destructive or locking-prone changes
- confirm application and database version compatibility during rollout

## 4. Required backup step
- take a database backup before running production migrations
- verify the backup completed successfully
- verify restore procedure is known before continuing

## 5. Local validation
- run migrations against a clean local database
- run migrations against a realistic existing database state if available
- confirm upgrade completes successfully
- confirm downgrade works where supported
- confirm the application starts correctly after migration
- confirm tests still pass after migration

## 6. Migration execution order
- deploy migration-capable code or migration artifact
- run the migration command
- wait for migration completion
- verify schema state
- start or continue application rollout
- verify application health after schema update

## 7. Production execution checklist
- identify migration operator
- confirm environment variables are correct
- confirm database target is correct
- confirm backup is complete
- run migration
- capture migration logs
- verify success before proceeding

## 8. Post-migration validation
- verify application startup
- verify health endpoints
- verify critical read/write paths
- verify worker processes if they depend on schema changes
- verify no immediate error spike in logs

## 9. Rollback guidance
- if migration is reversible, use the defined downgrade path
- if migration is not safely reversible, restore from backup and redeploy prior code
- do not improvise rollback steps during incident response
- document whether each migration is reversible or non-reversible

## 10. Risks to watch
- destructive column or table changes
- nullable to non-nullable transitions
- enum or state-machine changes
- long-running locks
- code/schema mismatch during rolling deploys
- partial rollout with incompatible workers or services

## 11. Required implementation follow-up
- audit every file in `foundation-skeleton/backend/alembic/versions/`
- classify each migration as reversible or non-reversible
- document the canonical migration command for deployment
- add migration validation to CI

## 12. Status
- draft
