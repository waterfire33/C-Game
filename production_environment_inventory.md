# Production Environment Inventory

## 1. Core application settings
- APP_ENV:
  - required in production: yes
  - allowed default in production: no
  - placeholder allowed in production: no
  - source of truth: deployment environment
  - owner: deployment/operator
  - notes: should be set explicitly to production

- APP_SECRET_KEY:
  - required in production: yes
  - allowed default in production: no
  - placeholder allowed in production: no
  - source of truth: secure secret store / production environment
  - owner: deployment/operator
  - notes: must never use `change-me`

- ACCESS_TOKEN_EXPIRE_MINUTES:
  - required in production: yes
  - allowed default in production: yes
  - placeholder allowed in production: no
  - source of truth: deployment environment or documented default
  - owner: application owner
  - notes: current code default is 60

- APP_CORS_ORIGINS:
  - required in production: yes
  - allowed default in production: no
  - placeholder allowed in production: no
  - source of truth: deployment environment
  - owner: deployment/operator
  - notes: localhost default is not suitable for production

## 2. Database and cache
- DATABASE_URL:
  - required in production: yes
  - allowed default in production: no
  - placeholder allowed in production: no
  - source of truth: secure deployment environment
  - owner: deployment/operator
  - notes: required by config, no code default

- REDIS_URL:
  - required in production: yes
  - allowed default in production: no
  - placeholder allowed in production: no
  - source of truth: secure deployment environment
  - owner: deployment/operator
  - notes: required by config, no code default

## 3. Telemetry
- ENABLE_TELEMETRY:
  - required in production: yes
  - allowed default in production: yes
  - placeholder allowed in production: no
  - source of truth: deployment environment
  - owner: deployment/operator
  - notes: current code default is false

- OTEL_SERVICE_NAME:
  - required in production: yes
  - allowed default in production: yes
  - placeholder allowed in production: no
  - source of truth: deployment environment or documented default
  - owner: application owner
  - notes: current code default is foundation-backend

- OTEL_EXPORTER_OTLP_ENDPOINT:
  - required in production: if telemetry is enabled
  - allowed default in production: yes, only when telemetry is disabled
  - placeholder allowed in production: no
  - source of truth: deployment environment
  - owner: deployment/operator
  - notes: no code default beyond none

- OTEL_CONSOLE_EXPORTER_ENABLED:
  - required in production: no
  - allowed default in production: yes
  - placeholder allowed in production: no
  - source of truth: deployment environment
  - owner: deployment/operator
  - notes: current code default is false

## 4. Placeholder blocking policy
Block these in production:
- empty values
- whitespace-only values
- change-me
- secret
- test
- demo
- password
- 123456
- invalid env: references

## 5. Status
- draft