# Deployment Runbook

## 1. Purpose
This runbook defines the standard deployment process for the application and supporting services.

## 2. Scope
This applies to deployment of:
- backend application
- frontend application
- database migrations
- worker processes
- supporting services required by the app

## 3. Pre-deployment checks
- confirm the target commit is correct
- confirm the branch or tag being deployed
- confirm required environment variables are present
- confirm secrets are loaded from approved runtime sources
- confirm the database backup plan is ready
- confirm migration review is complete
- confirm the rollback plan is ready
- confirm the deployment window and operator

## 4. Required inputs
- target environment
- target commit or tag
- deployment operator
- migration decision
- backup confirmation
- rollback target

## 5. Deployment order
- verify target environment
- verify configuration and secrets
- take or confirm backup if required
- run database migrations
- deploy backend
- deploy worker processes
- deploy frontend if applicable
- verify health and critical flows

## 6. Configuration checks
- backend config loads correctly
- production secrets are not placeholders
- database connection settings are correct
- redis connection settings are correct
- external API credentials are present where required
- telemetry/logging configuration is valid for the environment

## 7. Post-deployment validation
- verify application startup
- verify health endpoints
- verify authentication flow
- verify critical API paths
- verify worker execution
- verify logs show no immediate failure spike
- verify frontend can reach backend where applicable

## 8. Deployment failure handling
- stop rollout if migrations fail
- stop rollout if backend health checks fail
- stop rollout if critical auth or data paths fail
- use the rollback runbook rather than ad hoc recovery steps
- document the incident and failure point

## 9. Minimum release evidence
- deployed commit or tag recorded
- migration result recorded
- health check result recorded
- operator and deployment time recorded
- rollback decision documented if needed

## 10. Required implementation follow-up
- define the canonical production deployment command set
- define backend and worker startup commands
- define health check endpoints and acceptance criteria
- document environment-specific deployment differences
- confirm staging-to-production promotion flow

## 11. Status
- draft
