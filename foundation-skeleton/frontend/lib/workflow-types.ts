/**
 * Workflow types matching backend schemas
 */

// Enums
export type RunStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'awaiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type StepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'awaiting_approval';

export type EventType =
  | 'run_created'
  | 'run_started'
  | 'run_paused'
  | 'run_resumed'
  | 'run_completed'
  | 'run_failed'
  | 'run_cancelled'
  | 'run_retry_requested'
  | 'step_started'
  | 'step_completed'
  | 'step_failed'
  | 'step_retry_scheduled'
  | 'approval_requested'
  | 'approval_granted'
  | 'approval_denied'
  | 'state_updated';

export type ActionRiskClass = 'A' | 'B' | 'C' | 'D';

export type ApprovalRequestStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';

// Step Definition
export type StepDefinition = {
  id: string;
  name: string;
  step_type: string;
  order: number;
  config: Record<string, unknown>;
  requires_approval: boolean;
  action_risk_class: ActionRiskClass;
  required_approver_role: string | null;
  timeout_seconds: number | null;
  max_retries: number;
};

// Workflow Definition
export type WorkflowDefinition = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  steps: StepDefinition[];
};

// Run Step
export type RunStep = {
  id: string;
  step_index: number;
  status: StepStatus;
  started_at: string | null;
  completed_at: string | null;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  attempt_number: number;
  approved_by_user_id: string | null;
  approved_at: string | null;
};

export type ApprovalRequest = {
  id: string;
  run_id: string;
  run_step_id: string;
  step_definition_id: string;
  step_index: number;
  step_name: string;
  status: ApprovalRequestStatus;
  action_risk_class: ActionRiskClass;
  required_role: string | null;
  requested_by_user_id: string | null;
  requested_at: string;
  decision_by_user_id: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  request_context: Record<string, unknown>;
};

// Workflow Run
export type WorkflowRun = {
  id: string;
  workflow_definition_id: string;
  tenant_id: string;
  idempotency_key: string;
  status: RunStatus;
  current_step_index: number;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  state: Record<string, unknown>;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  triggered_by_user_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  steps: RunStep[];
  approval_requests: ApprovalRequest[];
};

// Workflow Event (for timeline)
export type WorkflowEvent = {
  id: string;
  run_id: string;
  event_type: EventType;
  sequence_number: number;
  previous_status: string | null;
  new_status: string | null;
  step_index: number | null;
  payload: Record<string, unknown>;
  actor_user_id: string | null;
  created_at: string;
};

// Timeline Response
export type TimelineResponse = {
  run_id: string;
  events: WorkflowEvent[];
};

export type ApprovalRequestList = {
  items: ApprovalRequest[];
  total: number;
};

export type ToolDefinition = {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  source_type: 'internal' | 'mcp';
  is_read_only: boolean;
  default_timeout_seconds: number;
  default_max_retries: number;
  metadata_json: Record<string, unknown>;
};

export type TenantToolRegistration = {
  id: string;
  tenant_id: string;
  enabled: boolean;
  override_timeout_seconds: number | null;
  override_max_retries: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  tool_definition: ToolDefinition;
};

export type TenantToolRegistrationList = {
  items: TenantToolRegistration[];
  total: number;
};

// Status display helpers
export const STATUS_COLORS: Record<RunStatus, string> = {
  pending: 'bg-gray-400',
  running: 'bg-blue-500',
  paused: 'bg-yellow-500',
  awaiting_approval: 'bg-orange-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-gray-600',
};

export const STEP_STATUS_COLORS: Record<StepStatus, string> = {
  pending: 'bg-gray-400',
  running: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  skipped: 'bg-gray-300',
  awaiting_approval: 'bg-orange-500',
};

export const EVENT_ICONS: Record<EventType, string> = {
  run_created: '🆕',
  run_started: '▶️',
  run_paused: '⏸️',
  run_resumed: '▶️',
  run_completed: '✅',
  run_failed: '❌',
  run_cancelled: '🚫',
  run_retry_requested: '🔄',
  step_started: '⏵',
  step_completed: '✓',
  step_failed: '✗',
  step_retry_scheduled: '↻',
  approval_requested: '⏳',
  approval_granted: '👍',
  approval_denied: '👎',
  state_updated: '📝',
};

export const EVENT_LABELS: Record<EventType, string> = {
  run_created: 'Run Created',
  run_started: 'Run Started',
  run_paused: 'Run Paused',
  run_resumed: 'Run Resumed',
  run_completed: 'Run Completed',
  run_failed: 'Run Failed',
  run_cancelled: 'Run Cancelled',
  run_retry_requested: 'Retry Requested',
  step_started: 'Step Started',
  step_completed: 'Step Completed',
  step_failed: 'Step Failed',
  step_retry_scheduled: 'Step Retry Scheduled',
  approval_requested: 'Approval Requested',
  approval_granted: 'Approval Granted',
  approval_denied: 'Approval Denied',
  state_updated: 'State Updated',
};

// =====================
// Agent Router / Planner types (Section 3)
// =====================

export type WorkflowType =
  | 'information_request'
  | 'draft_action'
  | 'executable_tool';

export type PlannerStrategy = 'deterministic' | 'llm';

export type PlanStatus = 'pending' | 'routed' | 'failed';

export type PlannerFailureCategory =
  | 'none'
  | 'unparseable_output'
  | 'no_matching_workflow'
  | 'llm_timeout'
  | 'llm_refusal'
  | 'invalid_plan_schema'
  | 'internal_error';

export type PlannedStep = {
  name: string;
  step_type: string;
  config: Record<string, unknown>;
  reasoning: string | null;
};

export type PlanResponse = {
  id: string;
  tenant_id: string;
  agent_request_id: string;
  workflow_type: WorkflowType;
  strategy: PlannerStrategy;
  status: PlanStatus;
  confidence: number | null;
  reasoning: string | null;
  planned_steps: PlannedStep[];
  selected_workflow_definition_id: string | null;
  run_id: string | null;
  failure_category: PlannerFailureCategory;
  error_message: string | null;
  latency_ms: number | null;
  created_at: string;
};

export type AgentRequestResponse = {
  id: string;
  tenant_id: string;
  submitted_by_user_id: string | null;
  body: string;
  context: Record<string, unknown>;
  idempotency_key: string;
  created_at: string;
  plan: PlanResponse | null;
};

export type PlanList = {
  items: PlanResponse[];
  total: number;
};

export const WORKFLOW_TYPE_LABELS: Record<WorkflowType, string> = {
  information_request: 'Information Request',
  draft_action: 'Draft Action',
  executable_tool: 'Executable Tool',
};

export const PLAN_STATUS_COLORS: Record<PlanStatus, string> = {
  pending: 'bg-gray-400',
  routed: 'bg-green-500',
  failed: 'bg-red-500',
};

// =====================
// MCP Integration types (Section 6)
// =====================

export type MCPAuthType = 'none' | 'bearer_token' | 'static_header';

export type MCPServerHealthStatus = 'unknown' | 'healthy' | 'degraded' | 'unreachable';

export type MCPAuthConfig = {
  id: string;
  tenant_id: string;
  name: string;
  auth_type: MCPAuthType;
  header_name: string | null;
  secret_ref: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type MCPAuthConfigList = {
  items: MCPAuthConfig[];
  total: number;
};

export type MCPServer = {
  id: string;
  tenant_id: string;
  name: string;
  base_url: string;
  enabled: boolean;
  auth_config_id: string | null;
  health_path: string;
  tools_path: string;
  invoke_path_template: string;
  scope_filter: string[];
  timeout_seconds: number;
  max_retries: number;
  descriptor_metadata_json: Record<string, unknown>;
  health_status: MCPServerHealthStatus;
  health_metadata_json: Record<string, unknown>;
  last_health_checked_at: string | null;
  last_synced_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type MCPServerList = {
  items: MCPServer[];
  total: number;
};

export type MCPHealthCheckResponse = {
  server: MCPServer;
};

export type MCPSyncResponse = {
  server: MCPServer;
  discovered_tool_names: string[];
  synced_count: number;
  disabled_count: number;
};

export const MCP_HEALTH_LABELS: Record<MCPServerHealthStatus, string> = {
  unknown: 'Unknown',
  healthy: 'Healthy',
  degraded: 'Degraded',
  unreachable: 'Unreachable',
};
