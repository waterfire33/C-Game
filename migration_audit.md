# Migration Audit

## Files in scope
- foundation-skeleton/backend/alembic/versions/0001_initial.py
- foundation-skeleton/backend/alembic/versions/0002_workflow_models.py
- foundation-skeleton/backend/alembic/versions/0003_tool_abstraction_layer.py
- foundation-skeleton/backend/alembic/versions/0004_approval_engine.py
- foundation-skeleton/backend/alembic/versions/0005_agent_router.py
- foundation-skeleton/backend/alembic/versions/0006_mcp_integration.py

## Audit goals
- identify migration order and dependency chain
- identify destructive changes
- identify locking-risk changes
- identify downgrade support
- identify reversible vs non-reversible migrations
- identify rollout safety concerns

## Required findings

### 1. Migration inventory
- revision
- file
- purpose
- depends on

### 2. Upgrade safety
- destructive operations
- nullable to non-nullable transitions
- table or column drops
- enum or state changes
- data backfill requirements
- long-running lock risks

### 3. Downgrade safety
- downgrade exists: yes or no
- downgrade appears safe: yes or no
- downgrade concerns

### 4. Deployment compatibility
- code/schema mismatch risk
- rolling deploy risk
- worker compatibility risk
- backup requirement level

### 5. Classification
- reversible or non-reversible
- production risk: low, medium, high

## Output format
For each migration, use:
- file
- purpose
- destructive changes
- downgrade status
- compatibility risk
- classification
- priority

## Status
- draft

## Migration findings

### 0001_initial

- file: foundation-skeleton/backend/alembic/versions/0001_initial.py
- issue: revision id was incorrectly set to `0000_initial` while later migration expected `0001_initial`
- risk: Alembic migration chain was broken and migration resolution could fail
- required fix: set `revision = "0001_initial"` to match the dependency chain
- priority: high

### 1. Migration inventory
- revision: 0001_initial
- file: foundation-skeleton/backend/alembic/versions/0001_initial.py
- purpose: create initial core schema for tenants, users, and memberships
- depends on: none

### 2. Upgrade safety
- destructive operations: no
- nullable to non-nullable transitions: no
- table or column drops: no
- enum or state changes: no
- data backfill requirements: no
- long-running lock risks: low

### 3. Downgrade safety
- downgrade exists: yes
- downgrade appears safe: yes
- downgrade concerns: drops all initial tables and related indexes, so downgrade is destructive to stored data if used after production data exists

### 4. Deployment compatibility
- code/schema mismatch risk: low
- rolling deploy risk: low
- worker compatibility risk: low
- backup requirement level: medium

### 5. Classification
- reversible or non-reversible: reversible
- production risk: medium

- file: foundation-skeleton/backend/alembic/versions/0001_initial.py
- purpose: create initial tenants, users, and memberships schema with primary keys, uniqueness, and membership foreign keys
- destructive changes: none in upgrade; downgrade drops all created tables and indexes
- downgrade status: exists and structurally reverses the migration
- compatibility risk: low
- classification: reversible
- priority: medium

### 0002_workflow_models

### 1. Migration inventory
- revision: 0002_workflow_models
- file: foundation-skeleton/backend/alembic/versions/0002_workflow_models.py
- purpose: add workflow definition, workflow step, workflow run, workflow run step, and workflow event models plus supporting enums and indexes
- depends on: 0001_initial

### 2. Upgrade safety
- destructive operations: no
- nullable to non-nullable transitions: no
- table or column drops: no
- enum or state changes: yes, new enums are introduced
- data backfill requirements: no
- long-running lock risks: medium

### 3. Downgrade safety
- downgrade exists: yes
- downgrade appears safe: partially
- downgrade concerns: downgrade uses raw `DROP TABLE IF EXISTS ... CASCADE` and `DROP TYPE IF EXISTS ...`, which is destructive and may remove dependent objects broadly; it is structurally reversible but aggressive

### 4. Deployment compatibility
- code/schema mismatch risk: medium
- rolling deploy risk: medium
- worker compatibility risk: medium
- backup requirement level: high

### 5. Classification
- reversible or non-reversible: reversible with destructive downgrade behavior
- production risk: high

- file: foundation-skeleton/backend/alembic/versions/0002_workflow_models.py
- purpose: introduce workflow backbone tables, statuses, event log, run steps, and workflow definition structures
- destructive changes: none in upgrade; downgrade aggressively drops workflow tables and enum types with cascade
- downgrade status: exists, but uses destructive raw drop statements and should be treated cautiously
- compatibility risk: medium due to new enums, new workflow state tables, and possible code/schema mismatch during rollout
- classification: reversible with destructive downgrade behavior
- priority: high

### 0003_tool_abstraction_layer

### 1. Migration inventory
- revision: 0003_tool_abstraction_layer
- file: foundation-skeleton/backend/alembic/versions/0003_tool_abstraction_layer.py
- purpose: add tool definition, tenant tool registration, and tool call tracking models plus supporting enums and indexes
- depends on: 0002_workflow_models

### 2. Upgrade safety
- destructive operations: no
- nullable to non-nullable transitions: no
- table or column drops: no
- enum or state changes: yes, new enums are introduced
- data backfill requirements: no
- long-running lock risks: medium

### 3. Downgrade safety
- downgrade exists: yes
- downgrade appears safe: yes
- downgrade concerns: downgrade drops tool-related tables and custom enum types, which is structurally reversible but destructive to stored tool-call history if used after production data exists

### 4. Deployment compatibility
- code/schema mismatch risk: medium
- rolling deploy risk: medium
- worker compatibility risk: medium
- backup requirement level: high

### 5. Classification
- reversible or non-reversible: reversible
- production risk: high

- file: foundation-skeleton/backend/alembic/versions/0003_tool_abstraction_layer.py
- purpose: introduce tool registry, per-tenant tool registration, and tool call logging/tracking infrastructure
- destructive changes: none in upgrade; downgrade drops all tool-related tables, indexes, and enum types
- downgrade status: exists and structurally reverses the migration
- compatibility risk: medium due to new enums, new foreign keys into workflow tables, and possible code/schema mismatch during rollout
- classification: reversible
- priority: high

### 0004_approval_engine

#### 1. Migration inventory
- revision: 0004_approval_engine
- file: foundation-skeleton/backend/alembic/versions/0004_approval_engine.py
- purpose: add approval engine tables, approval statuses, action risk classification, and approval-related indexes
- depends on: 0003_tool_abstraction_layer

#### 2. Upgrade safety
- destructive operations: no
- nullable to non-nullable transitions: yes, a new non-nullable `action_risk_class` column is added with a server default
- table or column drops: no
- enum or state changes: yes, new enums are introduced
- data backfill requirements: yes, existing `workflow_step_definitions` rows are updated to populate `action_risk_class` and `required_approver_role`
- long-running lock risks: medium

#### 3. Downgrade safety
- downgrade exists: yes
- downgrade appears safe: mostly
- downgrade concerns: downgrade removes approval data, drops the added columns from `workflow_step_definitions`, and drops enum types; it is structurally reversible but destructive to approval history

#### 4. Deployment compatibility
- code/schema mismatch risk: medium
- rolling deploy risk: medium
- worker compatibility risk: medium
- backup requirement level: high

#### 5. Classification
- reversible or non-reversible: reversible
- production risk: high

- file: foundation-skeleton/backend/alembic/versions/0004_approval_engine.py
- purpose: introduce approval request tracking and risk classification for workflow steps
- destructive changes: none in upgrade; downgrade removes approval data, drops added columns, and drops enum types
- downgrade status: exists and structurally reverses the migration
- compatibility risk: medium due to new enums, added non-nullable column with backfill update, and possible code/schema mismatch during rollout
- classification: reversible
- priority: high

### 0005_agent_router

#### 1. Migration inventory
- revision: 0005_agent_router
- file: foundation-skeleton/backend/alembic/versions/0005_agent_router.py
- purpose: add agent request intake and planner/route tracking records plus supporting enums and indexes
- depends on: 0004_approval_engine

#### 2. Upgrade safety
- destructive operations: no
- nullable to non-nullable transitions: no
- table or column drops: no
- enum or state changes: yes, new enums are introduced
- data backfill requirements: no
- long-running lock risks: medium

#### 3. Downgrade safety
- downgrade exists: yes
- downgrade appears safe: yes
- downgrade concerns: downgrade drops planner and request history plus enum types, which is structurally reversible but destructive to stored routing/planning data if used after production use

#### 4. Deployment compatibility
- code/schema mismatch risk: medium
- rolling deploy risk: medium
- worker compatibility risk: medium
- backup requirement level: high

#### 5. Classification
- reversible or non-reversible: reversible
- production risk: high

- file: foundation-skeleton/backend/alembic/versions/0005_agent_router.py
- purpose: introduce canonical agent request storage, structured planning records, and planner failure/routing metadata
- destructive changes: none in upgrade; downgrade drops planner/request tables, indexes, and enum types
- downgrade status: exists and structurally reverses the migration
- compatibility risk: medium due to new enums, new request/planning persistence, and possible code/schema mismatch during rollout
- classification: reversible
- priority: high

### 0006_mcp_integration

#### 1. Migration inventory
- revision: 0006_mcp_integration
- file: foundation-skeleton/backend/alembic/versions/0006_mcp_integration.py
- purpose: add MCP auth config and MCP server descriptor models, extend tool source type, and add MCP health/auth enums and indexes
- depends on: 0005_agent_router

#### 2. Upgrade safety
- destructive operations: yes, the existing `tool_source_type` enum is altered in place to add a new value
- nullable to non-nullable transitions: no
- table or column drops: no
- enum or state changes: yes, existing enum is altered and new enums are introduced
- data backfill requirements: no
- long-running lock risks: medium

#### 3. Downgrade safety
- downgrade exists: yes
- downgrade appears safe: partially
- downgrade concerns: downgrade drops MCP tables and custom enum types, but it does not remove the added `mcp` value from `tool_source_type`; that makes the migration only partially reversible

#### 4. Deployment compatibility
- code/schema mismatch risk: medium
- rolling deploy risk: medium
- worker compatibility risk: medium
- backup requirement level: high

#### 5. Classification
- reversible or non-reversible: partially reversible
- production risk: high

- file: foundation-skeleton/backend/alembic/versions/0006_mcp_integration.py
- purpose: introduce MCP auth configuration and MCP server descriptor storage plus MCP-specific health/auth enums
- destructive changes: upgrade alters an existing enum in place by adding `mcp`; downgrade drops MCP tables and enums but does not remove the added enum value from `tool_source_type`
- downgrade status: exists, but is only partially reversible
- compatibility risk: medium due to in-place enum alteration, new MCP tables, and possible code/schema mismatch during rollout
- classification: partially reversible
- priority: high
