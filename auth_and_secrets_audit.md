## Required findings

### 1. Config inventory
- name: app_secret_key
- alias: APP_SECRET_KEY
- default value: change-me
- source: environment variable APP_SECRET_KEY, with code fallback in config.py
- risk level: high

- name: access_token_expire_minutes
- alias: ACCESS_TOKEN_EXPIRE_MINUTES
- default value: 60
- source: environment variable ACCESS_TOKEN_EXPIRE_MINUTES, with code fallback in config.py
- risk level: medium

- name: database_url
- alias: DATABASE_URL
- default value: none in code
- source: required environment variable DATABASE_URL
- risk level: high

- name: enable_telemetry
- alias: ENABLE_TELEMETRY
- default value: false
- source: environment variable ENABLE_TELEMETRY, with code fallback in config.py
- risk level: low

- name: redis_url
- alias: REDIS_URL
- default value: none in code
- source: required environment variable REDIS_URL
- risk level: medium

- name: otel_service_name
- alias: OTEL_SERVICE_NAME
- default value: foundation-backend
- source: environment variable OTEL_SERVICE_NAME, with code fallback in config.py
- risk level: low

- name: otel_exporter_otlp_endpoint
- alias: OTEL_EXPORTER_OTLP_ENDPOINT
- default value: none in code
- source: optional environment variable OTEL_EXPORTER_OTLP_ENDPOINT, with code fallback of none in config.py
- risk level: low

- name: otel_console_exporter_enabled
- alias: OTEL_CONSOLE_EXPORTER_ENABLED
- default value: false
- source: environment variable OTEL_CONSOLE_EXPORTER_ENABLED, with code fallback in config.py
- risk level: low

- name: app_cors_origins
- alias: APP_CORS_ORIGINS
- default value: http://localhost:3000
- source: environment variable APP_CORS_ORIGINS, with code fallback in config.py
- risk level: low

### 2. Secret loading path
- secrets and config values are loaded through pydantic settings
- environment variable aliases are used for external loading
- some values are required and have no code fallback, such as DATABASE_URL and REDIS_URL
- some values have explicit code fallbacks, including APP_SECRET_KEY
- the current fallback for APP_SECRET_KEY is `change-me`, which is unsafe for production

### 3. Unsafe values based on config.py alone
- APP_SECRET_KEY currently allows an unsafe default value: `change-me`
- there is no visible production-only startup enforcement in config.py blocking unsafe placeholder values
- required environment variables DATABASE_URL and REDIS_URL do not have placeholder defaults in config.py
- additional unsafe-value blocking for empty, whitespace-only, `secret`, `test`, `demo`, `password`, `123456`, and invalid `env:` references is not visible in this file

### 4. Password hashing
- current hash algorithm: pwdlib recommended password hash
- legacy passlib/bcrypt fallback still exists: yes
- exact removal condition: remove the passlib bcrypt fallback only after all stored legacy bcrypt hashes have been migrated or naturally replaced with pwdlib-generated hashes and verification is no longer needed for old hashes

### 5. Startup enforcement
- production startup does not appear to fail on unsafe APP_SECRET_KEY values from security.py alone
- token creation uses settings.app_secret_key directly
- there is no visible enforcement here blocking `change-me` or other unsafe secret placeholders before token signing begins
- explicit production startup validation for secret safety still needs to be added

### 6. Identified Issues

- file: foundation-skeleton/backend/app/core/config.py
- issue: APP_SECRET_KEY has an unsafe default fallback of `change-me`
- risk: production tokens could be signed with a predictable secret if environment configuration is missing or incorrect
- required fix: remove the unsafe default or block startup in production when APP_SECRET_KEY is missing or set to a placeholder
- priority: high

- file: foundation-skeleton/backend/app/core/security.py
- issue: legacy passlib bcrypt fallback is still enabled in password verification
- risk: legacy compatibility code increases maintenance burden and extends attack surface until old hashes are fully migrated
- required fix: document the migration path and remove the fallback once all legacy bcrypt hashes are gone
- priority: medium

- file: foundation-skeleton/backend/app/core/security.py
- issue: create_access_token signs tokens with settings.app_secret_key without visible runtime enforcement of secret strength or safety
- risk: insecure token signing could occur if the configured secret is weak, placeholder-based, or accidentally left at an unsafe default
- required fix: add production-only startup validation that rejects weak or placeholder secret values before the app can serve requests
- priority: high
