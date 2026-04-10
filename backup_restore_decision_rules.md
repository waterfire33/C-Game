# Backup and Restore Decision Rules

## 1. Purpose
This document defines when deployment rollback should use code rollback, migration downgrade, or full database restore.

## 2. Use code rollback only when
- the deployment failed before any schema change was applied
- the schema is unchanged and still compatible with the last known good code
- the issue is isolated to application code or configuration

## 3. Use migration downgrade when
- the migration is explicitly classified as reversible
- downgrade steps are documented and tested
- data-loss risk is understood and accepted
- the downgrade is safer than restoring a full database backup

## 4. Use database restore when
- a migration is non-reversible or only partially reversible
- schema or data corruption is possible
- rollback requires returning both schema and data to a known good state
- the deploy introduced destructive or unsafe data-side effects

## 5. Do not use undocumented manual fixes when
- production data integrity is uncertain
- schema state is unclear
- multiple services may already depend on the changed schema

## 6. Required precondition before production migration
- a fresh backup must exist
- the backup must be verified as restorable
- the operator must know which rollback path will be used if the deploy fails

## 7. Current project-specific rules
- `0001_initial`: downgrade exists, but restoring production data may still require backup
- `0002_workflow_models`: downgrade is aggressive and should be treated cautiously
- `0003_tool_abstraction_layer`: downgrade is structurally reversible but destroys tool history
- `0004_approval_engine`: downgrade is structurally reversible but destroys approval history
- `0005_agent_router`: downgrade is structurally reversible but destroys planner/request history
- `0006_mcp_integration`: partially reversible; database restore may be safer than downgrade in production

## 8. Default decision rule
- if unsure, prefer backup + restore over improvised rollback

## 9. Status
- draft
