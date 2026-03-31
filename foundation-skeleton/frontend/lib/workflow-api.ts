/**
 * Workflow API client functions
 */
import type {
  AgentRequestResponse,
  ApprovalRequest,
  ApprovalRequestList,
  MCPAuthConfig,
  MCPAuthConfigList,
  MCPHealthCheckResponse,
  MCPServer,
  MCPServerList,
  MCPSyncResponse,
  PlanList,
  PlanResponse,
  TenantToolRegistrationList,
  TimelineResponse,
  WorkflowDefinition,
  WorkflowRun,
} from './workflow-types';

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

type FetchOptions = {
  token: string;
};

async function authFetch<T>(
  endpoint: string,
  options: FetchOptions & RequestInit
): Promise<T> {
  const { token, ...fetchOptions } = options;
  
  const response = await fetch(`${apiBaseUrl}${endpoint}`, {
    ...fetchOptions,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...fetchOptions.headers,
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errorBody.detail ?? 'Request failed');
  }

  return response.json() as Promise<T>;
}

// =====================
// Workflow Definitions
// =====================

export type ListWorkflowDefinitionsResponse = {
  items: WorkflowDefinition[];
  total: number;
};

export async function listWorkflowDefinitions(
  options: FetchOptions & { skip?: number; limit?: number }
): Promise<ListWorkflowDefinitionsResponse> {
  const params = new URLSearchParams();
  if (options.skip !== undefined) params.set('skip', String(options.skip));
  if (options.limit !== undefined) params.set('limit', String(options.limit));

  return authFetch<ListWorkflowDefinitionsResponse>(
    `/workflows/definitions?${params}`,
    { token: options.token }
  );
}

export async function getWorkflowDefinition(
  id: string,
  options: FetchOptions
): Promise<WorkflowDefinition> {
  return authFetch<WorkflowDefinition>(`/workflows/definitions/${id}`, {
    token: options.token,
  });
}

export type CreateWorkflowDefinitionRequest = {
  name: string;
  description?: string;
  steps: Array<{
    name: string;
    step_type: string;
    config?: Record<string, unknown>;
    requires_approval?: boolean;
    timeout_seconds?: number;
    max_retries?: number;
  }>;
};

export async function createWorkflowDefinition(
  data: CreateWorkflowDefinitionRequest,
  options: FetchOptions
): Promise<WorkflowDefinition> {
  return authFetch<WorkflowDefinition>('/workflows/definitions', {
    token: options.token,
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// =====================
// Workflow Runs
// =====================

export type ListRunsResponse = {
  items: WorkflowRun[];
  total: number;
};

export async function listRuns(
  options: FetchOptions & {
    workflow_definition_id?: string;
    status?: string;
    skip?: number;
    limit?: number;
  }
): Promise<ListRunsResponse> {
  const params = new URLSearchParams();
  if (options.workflow_definition_id) {
    params.set('workflow_definition_id', options.workflow_definition_id);
  }
  if (options.status) params.set('status', options.status);
  if (options.skip !== undefined) params.set('skip', String(options.skip));
  if (options.limit !== undefined) params.set('limit', String(options.limit));

  return authFetch<ListRunsResponse>(`/workflows/runs?${params}`, {
    token: options.token,
  });
}

export async function getRun(id: string, options: FetchOptions): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/runs/${id}`, { token: options.token });
}

export type CreateRunRequest = {
  workflow_definition_id: string;
  idempotency_key: string;
  input_data?: Record<string, unknown>;
};

export async function createRun(
  data: CreateRunRequest,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>('/workflows/runs', {
    token: options.token,
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getRunTimeline(
  runId: string,
  options: FetchOptions
): Promise<TimelineResponse> {
  return authFetch<TimelineResponse>(`/workflows/runs/${runId}/timeline`, {
    token: options.token,
  });
}

// =====================
// Run Actions
// =====================

export async function approveStep(
  runId: string,
  stepIndex: number,
  reason: string | undefined,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/runs/${runId}/approve`, {
    token: options.token,
    method: 'POST',
    body: JSON.stringify({ step_index: stepIndex, reason }),
  });
}

export async function denyStep(
  runId: string,
  stepIndex: number,
  reason: string | undefined,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/runs/${runId}/deny`, {
    token: options.token,
    method: 'POST',
    body: JSON.stringify({ step_index: stepIndex, reason }),
  });
}

export async function cancelRun(
  runId: string,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/runs/${runId}/cancel`, {
    token: options.token,
    method: 'POST',
  });
}

export async function retryRun(
  runId: string,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/runs/${runId}/retry`, {
    token: options.token,
    method: 'POST',
  });
}

// =====================
// Approvals
// =====================

export async function listApprovalRequests(
  options: FetchOptions & {
    runId?: string;
    status?: string;
    skip?: number;
    limit?: number;
  }
): Promise<ApprovalRequestList> {
  const params = new URLSearchParams();
  if (options.runId) params.set('run_id', options.runId);
  if (options.status) params.set('status', options.status);
  if (options.skip !== undefined) params.set('skip', String(options.skip));
  if (options.limit !== undefined) params.set('limit', String(options.limit));

  return authFetch<ApprovalRequestList>(`/workflows/approvals?${params}`, {
    token: options.token,
  });
}

export async function getApprovalRequest(
  approvalRequestId: string,
  options: FetchOptions
): Promise<ApprovalRequest> {
  return authFetch<ApprovalRequest>(`/workflows/approvals/${approvalRequestId}`, {
    token: options.token,
  });
}

export async function approveApprovalRequest(
  approvalRequestId: string,
  reason: string | undefined,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/approvals/${approvalRequestId}/approve`, {
    token: options.token,
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function rejectApprovalRequest(
  approvalRequestId: string,
  reason: string | undefined,
  options: FetchOptions
): Promise<WorkflowRun> {
  return authFetch<WorkflowRun>(`/workflows/approvals/${approvalRequestId}/reject`, {
    token: options.token,
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

// =====================
// Agent Router / Planner (Section 3)
// =====================

export type AgentIntakePayload = {
  body: string;
  context?: Record<string, unknown>;
  idempotency_key: string;
};

export async function submitAgentRequest(
  payload: AgentIntakePayload,
  options: FetchOptions
): Promise<AgentRequestResponse> {
  return authFetch<AgentRequestResponse>('/agent/intake', {
    token: options.token,
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listPlans(
  options: FetchOptions & { offset?: number; limit?: number }
): Promise<PlanList> {
  const params = new URLSearchParams();
  if (options.offset !== undefined) params.set('offset', String(options.offset));
  if (options.limit !== undefined) params.set('limit', String(options.limit));
  return authFetch<PlanList>(`/agent/plans?${params}`, { token: options.token });
}

export async function getPlan(planId: string, options: FetchOptions): Promise<PlanResponse> {
  return authFetch<PlanResponse>(`/agent/plans/${planId}`, { token: options.token });
}

export async function getAgentRequest(
  requestId: string,
  options: FetchOptions
): Promise<AgentRequestResponse> {
  return authFetch<AgentRequestResponse>(`/agent/requests/${requestId}`, { token: options.token });
}

// =====================
// MCP Integration (Section 6)
// =====================

export type CreateMCPAuthConfigRequest = {
  name: string;
  auth_type: 'none' | 'bearer_token' | 'static_header';
  header_name?: string | null;
  secret_ref?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type CreateMCPServerRequest = {
  name: string;
  base_url: string;
  enabled?: boolean;
  auth_config_id?: string | null;
  health_path?: string;
  tools_path?: string;
  invoke_path_template?: string;
  scope_filter?: string[];
  timeout_seconds?: number;
  max_retries?: number;
  descriptor_metadata_json?: Record<string, unknown>;
};

export async function listMCPAuthConfigs(options: FetchOptions): Promise<MCPAuthConfigList> {
  return authFetch<MCPAuthConfigList>('/mcp/auth-configs', { token: options.token });
}

export async function createMCPAuthConfig(
  payload: CreateMCPAuthConfigRequest,
  options: FetchOptions
): Promise<MCPAuthConfig> {
  return authFetch<MCPAuthConfig>('/mcp/auth-configs', {
    token: options.token,
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listMCPServers(options: FetchOptions): Promise<MCPServerList> {
  return authFetch<MCPServerList>('/mcp/servers', { token: options.token });
}

export async function listAllowedTools(options: FetchOptions): Promise<TenantToolRegistrationList> {
  return authFetch<TenantToolRegistrationList>('/tools', { token: options.token });
}

export async function createMCPServer(
  payload: CreateMCPServerRequest,
  options: FetchOptions
): Promise<MCPServer> {
  return authFetch<MCPServer>('/mcp/servers', {
    token: options.token,
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function healthCheckMCPServer(
  serverId: string,
  options: FetchOptions
): Promise<MCPHealthCheckResponse> {
  return authFetch<MCPHealthCheckResponse>(`/mcp/servers/${serverId}/health-check`, {
    token: options.token,
    method: 'POST',
  });
}

export async function syncMCPServer(
  serverId: string,
  options: FetchOptions
): Promise<MCPSyncResponse> {
  return authFetch<MCPSyncResponse>(`/mcp/servers/${serverId}/sync`, {
    token: options.token,
    method: 'POST',
  });
}
