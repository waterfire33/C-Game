# Rollback Runbook

## 1. Purpose
This runbook defines how to recover safely from a failed deployment, failed migration, or post-deployment production incident.

## 2. Scope
This applies to rollback of:
- backend application code
- frontend application code
- database migrations
- worker processes
- environment/config changes linked to a deployment

## 3. Rollback triggers
- migration failure
- backend health check failure
- authentication failure after deployment
- critical API path failure
- worker failure affecting core flows
- severe error spike after release
- confirmed configuration or secret issue in the deployed version

## 4. Required rollback inputs
- current deployed commit or tag
- last known good commit or tag
- migration status
- database backup status
- environment affected
- rollback operator
- incident timestamp

## 5. Rollback decision rules
- if code failed but schema is still compatible, redeploy the last known good code
- if a reversible migration caused the failure, use the documented downgrade path
- if a non-reversible migration caused the failure, restore from backup and redeploy the prior compatible code
- do not improvise rollback steps during an active incident
- document which path is chosen and why

## 6. Rollback sequence
- stop or pause rollout
- identify the exact failure point
- confirm rollback target
- confirm database rollback strategy
- restore prior code or image
- rollback migration or restore database if required
- restart backend and workers as needed
- verify health endpoints
- verify critical read/write paths
- verify logs and error rate stabilization

## 7. Database-specific rollback guidance
- reversible migration: use the downgrade plan
- non-reversible migration: restore from backup
- do not run undocumented manual schema edits in production
- record whether data loss risk exists before acting

## 8. Post-rollback validation
- backend starts successfully
- frontend loads successfully if affected
- auth works
- critical API operations work
- worker processes are healthy
- logs show recovery
- error rate returns to acceptable level

## 9. Incident recording
- what failed
- when it failed
- who executed rollback
- what rollback path was used
- whether database restore was required
- final recovery status
- follow-up actions required

## 10. Required implementation follow-up
- define the last known good deployment reference format
- classify migrations as reversible or non-reversible
- document the exact rollback commands for code deploys
- document the exact rollback commands for migrations where safe
- document backup restore ownership and procedure

## 11. Status
- draft
