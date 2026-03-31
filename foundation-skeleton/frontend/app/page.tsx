'use client';

import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { fetchHealth, login, type LoginResponse } from '../lib/api';
import {
  approveApprovalRequest,
  createMCPAuthConfig,
  createMCPServer,
  healthCheckMCPServer,
  listApprovalRequests,
  listAllowedTools,
  listMCPAuthConfigs,
  listMCPServers,
  listPlans,
  listRuns,
  rejectApprovalRequest,
  submitAgentRequest,
  syncMCPServer,
} from '../lib/workflow-api';
import type {
  AgentRequestResponse,
  ApprovalRequest,
  MCPAuthConfig,
  MCPServer,
  PlanResponse,
  TenantToolRegistration,
  WorkflowRun,
} from '../lib/workflow-types';
import { MCP_HEALTH_LABELS, PLAN_STATUS_COLORS, WORKFLOW_TYPE_LABELS } from '../lib/workflow-types';

type HealthState = {
  status: 'loading' | 'ready' | 'error';
  message: string;
};

const defaultCredentials = {
  email: 'owner@example.com',
  password: 'changeme123',
};

const defaultMcpAuthForm = {
  name: '',
  authType: 'none' as const,
  headerName: '',
  secretRef: '',
};

const defaultMcpServerForm = {
  name: '',
  baseUrl: '',
  authConfigId: '',
  scopeFilter: 'knowledge',
  timeoutSeconds: '15',
  maxRetries: '2',
};

export default function HomePage() {
  const [credentials, setCredentials] = useState(defaultCredentials);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loginResult, setLoginResult] = useState<LoginResponse | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(false);
  const [activeDecisionId, setActiveDecisionId] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthState>({
    status: 'loading',
    message: 'Checking backend and Redis connectivity...',
  });

  // Section 3 — Agent request intake
  const [agentBody, setAgentBody] = useState('');
  const [agentResult, setAgentResult] = useState<AgentRequestResponse | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [isAgentSubmitting, setIsAgentSubmitting] = useState(false);
  const [recentPlans, setRecentPlans] = useState<PlanResponse[]>([]);
  const [mcpAuthConfigs, setMcpAuthConfigs] = useState<MCPAuthConfig[]>([]);
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);
  const [mcpTools, setMcpTools] = useState<TenantToolRegistration[]>([]);
  const [mcpError, setMcpError] = useState<string | null>(null);
  const [mcpSuccess, setMcpSuccess] = useState<string | null>(null);
  const [isMcpLoading, setIsMcpLoading] = useState(false);
  const [activeMcpServerId, setActiveMcpServerId] = useState<string | null>(null);
  const [mcpAuthForm, setMcpAuthForm] = useState(defaultMcpAuthForm);
  const [mcpServerForm, setMcpServerForm] = useState(defaultMcpServerForm);

  useEffect(() => {
    fetchHealth()
      .then((payload) => {
        setHealth({
          status: 'ready',
          message: `${payload.status} - Redis ${payload.redis}`,
        });
      })
      .catch(() => {
        setHealth({
          status: 'error',
          message: 'Backend readiness check failed.',
        });
      });
  }, []);

  useEffect(() => {
    if (!loginResult) {
      setApprovals([]);
      setRuns([]);
      setRecentPlans([]);
      setMcpAuthConfigs([]);
      setMcpServers([]);
      setMcpTools([]);
      return;
    }

    let cancelled = false;
    const token = loginResult?.access_token;
    if (!token) {
      return;
    }

    async function loadDashboard() {
      setIsDashboardLoading(true);
      try {
        const [approvalPayload, runsPayload, plansPayload, authPayload, serversPayload, toolsPayload] = await Promise.all([
          listApprovalRequests({ token, status: 'pending', limit: 20 }),
          listRuns({ token, limit: 20 }),
          listPlans({ token, limit: 10 }),
          listMCPAuthConfigs({ token }),
          listMCPServers({ token }),
          listAllowedTools({ token }),
        ]);

        if (cancelled) {
          return;
        }

        setApprovals(approvalPayload.items);
        setRuns(runsPayload.items);
        setRecentPlans(plansPayload.items);
        setMcpAuthConfigs(authPayload.items);
        setMcpServers(serversPayload.items);
        setMcpTools(toolsPayload.items.filter((item) => item.tool_definition.source_type === 'mcp'));
        setDashboardError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setDashboardError(error instanceof Error ? error.message : 'Failed to load workflow dashboard');
      } finally {
        if (!cancelled) {
          setIsDashboardLoading(false);
        }
      }
    }

    loadDashboard();
    const intervalId = window.setInterval(loadDashboard, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [loginResult]);

  async function refreshMcpState(token: string) {
    const [authPayload, serversPayload, toolsPayload] = await Promise.all([
      listMCPAuthConfigs({ token }),
      listMCPServers({ token }),
      listAllowedTools({ token }),
    ]);

    setMcpAuthConfigs(authPayload.items);
    setMcpServers(serversPayload.items);
    setMcpTools(toolsPayload.items.filter((item) => item.tool_definition.source_type === 'mcp'));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const payload = await login(credentials);
      setLoginResult(payload);
      setErrorMessage(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed';
      setLoginResult(null);
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleCredentialChange(field: 'email' | 'password') {
    return (event: ChangeEvent<HTMLInputElement>) => {
      setCredentials((current: typeof defaultCredentials) => ({ ...current, [field]: event.target.value }));
    };
  }

  async function handleApprovalDecision(
    approvalRequestId: string,
    decision: 'approve' | 'reject'
  ) {
    if (!loginResult) {
      return;
    }

    const reason = window.prompt(
      decision === 'approve'
        ? 'Optional approval note'
        : 'Why is this request being rejected?'
    ) ?? undefined;

    setActiveDecisionId(approvalRequestId);
    setDashboardError(null);
    try {
      if (decision === 'approve') {
        await approveApprovalRequest(approvalRequestId, reason, { token: loginResult.access_token });
      } else {
        await rejectApprovalRequest(approvalRequestId, reason, { token: loginResult.access_token });
      }

      const [approvalPayload, runsPayload] = await Promise.all([
        listApprovalRequests({ token: loginResult.access_token, status: 'pending', limit: 20 }),
        listRuns({ token: loginResult.access_token, limit: 20 }),
      ]);
      setApprovals(approvalPayload.items);
      setRuns(runsPayload.items);
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : 'Approval action failed');
    } finally {
      setActiveDecisionId(null);
    }
  }

  const activeMembership = loginResult?.user.memberships[0] ?? null;

  function updateMcpAuthForm(
    field: 'name' | 'authType' | 'headerName' | 'secretRef'
  ) {
    return (
      event: ChangeEvent<HTMLInputElement | HTMLSelectElement>
    ) => {
      setMcpAuthForm((current: typeof defaultMcpAuthForm) => ({ ...current, [field]: event.target.value }));
    };
  }

  function updateMcpServerForm(
    field: 'name' | 'baseUrl' | 'authConfigId' | 'scopeFilter' | 'timeoutSeconds' | 'maxRetries'
  ) {
    return (
      event: ChangeEvent<HTMLInputElement | HTMLSelectElement>
    ) => {
      setMcpServerForm((current: typeof defaultMcpServerForm) => ({ ...current, [field]: event.target.value }));
    };
  }

  async function handleAgentIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loginResult || !agentBody.trim()) {
      return;
    }
    setIsAgentSubmitting(true);
    setAgentError(null);
    setAgentResult(null);
    try {
      const key = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const result = await submitAgentRequest(
        { body: agentBody.trim(), context: {}, idempotency_key: key },
        { token: loginResult.access_token }
      );
      setAgentResult(result);
      // Refresh plan list
      const updated = await listPlans({ token: loginResult.access_token, limit: 10 });
      setRecentPlans(updated.items);
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : 'Agent request failed');
    } finally {
      setIsAgentSubmitting(false);
    }
  }

  async function handleCreateMcpAuthConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loginResult) {
      return;
    }

    setIsMcpLoading(true);
    setMcpError(null);
    setMcpSuccess(null);
    try {
      await createMCPAuthConfig(
        {
          name: mcpAuthForm.name.trim(),
          auth_type: mcpAuthForm.authType,
          header_name: mcpAuthForm.headerName.trim() || null,
          secret_ref: mcpAuthForm.secretRef.trim() || null,
          metadata_json: {},
        },
        { token: loginResult.access_token }
      );
      await refreshMcpState(loginResult.access_token);
      setMcpSuccess('MCP auth config created.');
      setMcpAuthForm(defaultMcpAuthForm);
    } catch (error) {
      setMcpError(error instanceof Error ? error.message : 'Failed to create MCP auth config');
    } finally {
      setIsMcpLoading(false);
    }
  }

  async function handleCreateMcpServer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loginResult) {
      return;
    }

    setIsMcpLoading(true);
    setMcpError(null);
    setMcpSuccess(null);
    try {
      await createMCPServer(
        {
          name: mcpServerForm.name.trim(),
          base_url: mcpServerForm.baseUrl.trim(),
          auth_config_id: mcpServerForm.authConfigId || null,
          scope_filter: mcpServerForm.scopeFilter
            .split(',')
            .map((value: string) => value.trim())
            .filter(Boolean),
          timeout_seconds: Number(mcpServerForm.timeoutSeconds),
          max_retries: Number(mcpServerForm.maxRetries),
        },
        { token: loginResult.access_token }
      );
      await refreshMcpState(loginResult.access_token);
      setMcpSuccess('MCP server attached.');
      setMcpServerForm(defaultMcpServerForm);
    } catch (error) {
      setMcpError(error instanceof Error ? error.message : 'Failed to attach MCP server');
    } finally {
      setIsMcpLoading(false);
    }
  }

  async function handleMcpServerAction(serverId: string, action: 'health' | 'sync') {
    if (!loginResult) {
      return;
    }

    setActiveMcpServerId(serverId);
    setMcpError(null);
    setMcpSuccess(null);
    try {
      if (action === 'health') {
        await healthCheckMCPServer(serverId, { token: loginResult.access_token });
        setMcpSuccess('Health check completed.');
      } else {
        const result = await syncMCPServer(serverId, { token: loginResult.access_token });
        setMcpSuccess(`Synced ${result.synced_count} tool(s), disabled ${result.disabled_count}.`);
      }
      await refreshMcpState(loginResult.access_token);
    } catch (error) {
      setMcpError(error instanceof Error ? error.message : 'MCP server action failed');
    } finally {
      setActiveMcpServerId(null);
    }
  }

  const mcpToolsByServer = mcpServers.map((server: MCPServer) => ({
    serverId: server.id,
    serverName: server.name,
    tools: mcpTools.filter(
      (registration: TenantToolRegistration) =>
        String(registration.tool_definition.metadata_json.mcp_server_id ?? '') === server.id
    ),
  }));

  return (
    <main>
      <section className="hero">
        <article className="panel intro">
          <p className="eyebrow">Section 1 - Foundation Skeleton</p>
          <h1>Tenant-aware product foundation.</h1>
          <p className="lead">
            Next.js handles the operator-facing login shell. FastAPI owns auth, tenant membership,
            migrations, health checks, Redis connectivity, and OpenTelemetry instrumentation.
          </p>
          <div className="metrics">
            <div className="metric">
              <strong>1 command</strong>
              <span>docker compose up --build</span>
            </div>
            <div className="metric">
              <strong>Seeded auth</strong>
              <span>Tenant, owner, and member created on boot</span>
            </div>
            <div className="metric">
              <strong>Observable</strong>
              <span>Health, logs, SQL, Redis, and request traces wired</span>
            </div>
          </div>
        </article>

        <article className="panel authCard">
          <h2>Log in</h2>
          <p>Use the seeded owner account to validate the full stack immediately after boot.</p>
          <div className={`status ${health.status === 'error' ? 'error' : 'success'}`}>
            {health.message}
          </div>
          <form onSubmit={handleSubmit}>
            <label>
              Email
              <input
                type="email"
                value={credentials.email}
                onChange={handleCredentialChange('email')}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={credentials.password}
                onChange={handleCredentialChange('password')}
                required
              />
            </label>
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
          <p className="helper">Default credentials: owner@example.com / changeme123</p>
          {errorMessage ? <div className="status error">{errorMessage}</div> : null}
          {loginResult ? (
            <div className="status success">
              Login succeeded for {loginResult.user.full_name}. Token and tenant memberships are
              shown below.
            </div>
          ) : null}
          {loginResult ? (
            <div className="codeBlock">{JSON.stringify(loginResult, null, 2)}</div>
          ) : null}
        </article>
      </section>

      {loginResult ? (
        <section className="dashboardShell">
          <article className="panel dashboardHeader">
            <div>
              <p className="eyebrow">Section 6 - MCP Integration</p>
              <h2>MCP server attachment and discovery.</h2>
            </div>
            <div className="dashboardMeta">
              <span>{mcpServers.length} servers</span>
              <span>{mcpTools.length} MCP tools</span>
              <span>{mcpAuthConfigs.length} auth configs</span>
            </div>
          </article>

          {mcpError ? <div className="status error">{mcpError}</div> : null}
          {mcpSuccess ? <div className="status success">{mcpSuccess}</div> : null}

          <div className="dashboardGrid mcpGrid">
            <article className="panel queuePanel">
              <div className="panelHeaderRow">
                <h3>Create auth config</h3>
                <span>Optional</span>
              </div>
              <form onSubmit={handleCreateMcpAuthConfig} className="stackForm">
                <label>
                  Config name
                  <input value={mcpAuthForm.name} onChange={updateMcpAuthForm('name')} required />
                </label>
                <label>
                  Auth type
                  <select value={mcpAuthForm.authType} onChange={updateMcpAuthForm('authType')}>
                    <option value="none">none</option>
                    <option value="bearer_token">bearer_token</option>
                    <option value="static_header">static_header</option>
                  </select>
                </label>
                <label>
                  Header name
                  <input
                    value={mcpAuthForm.headerName}
                    onChange={updateMcpAuthForm('headerName')}
                    placeholder="Authorization or X-API-Key"
                  />
                </label>
                <label>
                  Secret ref
                  <input
                    value={mcpAuthForm.secretRef}
                    onChange={updateMcpAuthForm('secretRef')}
                    placeholder="secret-demo-token"
                  />
                </label>
                <button type="submit" disabled={isMcpLoading || !mcpAuthForm.name.trim()}>
                  {isMcpLoading ? 'Saving...' : 'Create auth config'}
                </button>
              </form>
            </article>

            <article className="panel queuePanel">
              <div className="panelHeaderRow">
                <h3>Attach MCP server</h3>
                <span>Tenant scoped</span>
              </div>
              <form onSubmit={handleCreateMcpServer} className="stackForm">
                <label>
                  Server name
                  <input value={mcpServerForm.name} onChange={updateMcpServerForm('name')} required />
                </label>
                <label>
                  Base URL
                  <input
                    type="url"
                    value={mcpServerForm.baseUrl}
                    onChange={updateMcpServerForm('baseUrl')}
                    placeholder="https://mcp.example.test"
                    required
                  />
                </label>
                <label>
                  Auth config
                  <select value={mcpServerForm.authConfigId} onChange={updateMcpServerForm('authConfigId')}>
                    <option value="">none</option>
                    {mcpAuthConfigs.map((config) => (
                      <option key={config.id} value={config.id}>
                        {config.name} · {config.auth_type}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Scope filter
                  <input
                    value={mcpServerForm.scopeFilter}
                    onChange={updateMcpServerForm('scopeFilter')}
                    placeholder="knowledge,draft"
                  />
                </label>
                <div className="inlineFieldGrid">
                  <label>
                    Timeout (s)
                    <input value={mcpServerForm.timeoutSeconds} onChange={updateMcpServerForm('timeoutSeconds')} />
                  </label>
                  <label>
                    Retries
                    <input value={mcpServerForm.maxRetries} onChange={updateMcpServerForm('maxRetries')} />
                  </label>
                </div>
                <button type="submit" disabled={isMcpLoading || !mcpServerForm.name.trim() || !mcpServerForm.baseUrl.trim()}>
                  {isMcpLoading ? 'Attaching...' : 'Attach server'}
                </button>
              </form>
            </article>
          </div>

          <div className="dashboardGrid mcpGridWide">
            <article className="panel runsPanel">
              <div className="panelHeaderRow">
                <h3>Attached servers</h3>
                <span>{mcpServers.length} total</span>
              </div>
              {mcpServers.length === 0 ? (
                <div className="emptyState">No MCP servers attached yet.</div>
              ) : (
                <div className="queueList">
                  {mcpServers.map((server) => (
                    <div className="approvalCard" key={server.id}>
                      <div className="approvalTitleRow">
                        <strong>{server.name}</strong>
                        <span className={`statusPill status-${server.health_status}`}>
                          {MCP_HEALTH_LABELS[server.health_status]}
                        </span>
                      </div>
                      <p>{server.base_url}</p>
                      <p>
                        scopes {server.scope_filter.length > 0 ? server.scope_filter.join(', ') : 'all'} · timeout{' '}
                        {server.timeout_seconds}s · retries {server.max_retries}
                      </p>
                      <p className="approvalTimestamp">
                        last sync {server.last_synced_at ? new Date(server.last_synced_at).toLocaleString() : 'never'}
                      </p>
                      {server.last_error ? <p className="errorText">{server.last_error}</p> : null}
                      <div className="decisionRow">
                        <button
                          type="button"
                          disabled={activeMcpServerId === server.id}
                          onClick={() => handleMcpServerAction(server.id, 'health')}
                        >
                          {activeMcpServerId === server.id ? 'Working...' : 'Health check'}
                        </button>
                        <button
                          type="button"
                          className="secondaryButton"
                          disabled={activeMcpServerId === server.id}
                          onClick={() => handleMcpServerAction(server.id, 'sync')}
                        >
                          Sync tools
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="panel runsPanel">
              <div className="panelHeaderRow">
                <h3>Discovered MCP tools</h3>
                <span>{mcpTools.length} enabled</span>
              </div>
              {mcpToolsByServer.every((entry) => entry.tools.length === 0) ? (
                <div className="emptyState">No MCP tools synced yet. Attach a server and run sync.</div>
              ) : (
                <div className="queueList">
                  {mcpToolsByServer.map((entry) => (
                    entry.tools.length > 0 ? (
                      <div className="toolGroupCard" key={entry.serverId}>
                        <div className="toolGroupHeader">
                          <strong>{entry.serverName}</strong>
                          <span>{entry.tools.length} tool(s)</span>
                        </div>
                        <div className="toolChipGrid">
                          {entry.tools.map((registration) => (
                            <div className="toolChip" key={registration.id}>
                              <strong>{registration.tool_definition.display_name}</strong>
                              <span>{registration.tool_definition.name}</span>
                              <p>{registration.tool_definition.description ?? 'No description provided.'}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null
                  ))}
                </div>
              )}
            </article>
          </div>
        </section>
      ) : null}

      {loginResult ? (
        <section className="dashboardShell">
          <article className="panel dashboardHeader">
            <div>
              <p className="eyebrow">Section 3 - Agent Router</p>
              <h2>Request intake and planning.</h2>
            </div>
          </article>

          <div className="dashboardGrid">
            <article className="panel">
              <h3>Submit an agent request</h3>
              <p>Describe a task. The planner will classify and route it to a workflow.</p>
              <form onSubmit={handleAgentIntake} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <label>
                  Request body
                  <textarea
                    rows={3}
                    value={agentBody}
                    onChange={(e) => setAgentBody(e.target.value)}
                    placeholder="e.g. Find the top 10 customers by revenue this quarter"
                    required
                    style={{ width: '100%', padding: '0.5rem', fontFamily: 'inherit', borderRadius: '4px', border: '1px solid #ccc' }}
                  />
                </label>
                <button type="submit" disabled={isAgentSubmitting || !agentBody.trim()}>
                  {isAgentSubmitting ? 'Planning...' : 'Submit request'}
                </button>
              </form>
              {agentError ? <div className="status error">{agentError}</div> : null}
              {agentResult?.plan ? (
                <div className="status success" style={{ marginTop: '0.75rem' }}>
                  <strong>Plan created</strong> — type:{' '}
                  <em>{WORKFLOW_TYPE_LABELS[agentResult.plan.workflow_type]}</em>, strategy:{' '}
                  <em>{agentResult.plan.strategy}</em>, confidence:{' '}
                  <em>{agentResult.plan.confidence != null ? `${Math.round(agentResult.plan.confidence * 100)}%` : 'n/a'}</em>
                  {agentResult.plan.run_id ? (
                    <span> · run <code>{agentResult.plan.run_id.slice(0, 8)}…</code></span>
                  ) : null}
                </div>
              ) : null}
            </article>

            <article className="panel">
              <div className="panelHeaderRow">
                <h3>Recent plans</h3>
                <span>{recentPlans.length} loaded</span>
              </div>
              {recentPlans.length === 0 ? (
                <div className="emptyState">No plans yet. Submit a request above.</div>
              ) : (
                <div className="runTable">
                  {recentPlans.map((plan) => (
                    <div className="runRow" key={plan.id}>
                      <div>
                        <strong>{WORKFLOW_TYPE_LABELS[plan.workflow_type]}</strong>
                        <p>{plan.strategy} · {plan.latency_ms != null ? `${plan.latency_ms}ms` : ''}</p>
                      </div>
                      <div>
                        <span className={`statusPill ${PLAN_STATUS_COLORS[plan.status]}`}>{plan.status}</span>
                      </div>
                      <div>
                        <p>{plan.planned_steps.length} steps</p>
                        <p>{plan.confidence != null ? `${Math.round(plan.confidence * 100)}% conf.` : 'failed'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </section>
      ) : null}

      {loginResult ? (
        <section className="dashboardShell">
          <article className="panel dashboardHeader">
            <div>
              <p className="eyebrow">Section 5 - Approval Engine</p>
              <h2>Approval queue and run control.</h2>
            </div>
            <div className="dashboardMeta">
              <span>Tenant {activeMembership?.tenant_slug ?? 'unknown'}</span>
              <span>Role {activeMembership?.role ?? 'unknown'}</span>
              <span>{approvals.length} pending approvals</span>
            </div>
          </article>

          {dashboardError ? <div className="status error">{dashboardError}</div> : null}

          <div className="dashboardGrid">
            <article className="panel queuePanel">
              <div className="panelHeaderRow">
                <h3>Pending approvals</h3>
                <span>{isDashboardLoading ? 'Refreshing...' : `${approvals.length} open`}</span>
              </div>

              {approvals.length === 0 ? (
                <div className="emptyState">No approval requests are waiting right now.</div>
              ) : (
                <div className="queueList">
                  {approvals.map((approval) => (
                    <div className="approvalCard" key={approval.id}>
                      <div className="approvalTitleRow">
                        <strong>{approval.step_name}</strong>
                        <span className={`riskBadge risk${approval.action_risk_class}`}>
                          Risk {approval.action_risk_class}
                        </span>
                      </div>
                      <p>
                        Run {approval.run_id.slice(0, 8)}... · step {approval.step_index} · role{' '}
                        {approval.required_role ?? 'any'}
                      </p>
                      <p className="approvalTimestamp">
                        Requested {new Date(approval.requested_at).toLocaleString()}
                      </p>
                      <div className="decisionRow">
                        <button
                          type="button"
                          disabled={activeDecisionId === approval.id}
                          onClick={() => handleApprovalDecision(approval.id, 'approve')}
                        >
                          {activeDecisionId === approval.id ? 'Working...' : 'Approve'}
                        </button>
                        <button
                          type="button"
                          className="secondaryButton"
                          disabled={activeDecisionId === approval.id}
                          onClick={() => handleApprovalDecision(approval.id, 'reject')}
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="panel runsPanel">
              <div className="panelHeaderRow">
                <h3>Recent runs</h3>
                <span>{runs.length} loaded</span>
              </div>

              {runs.length === 0 ? (
                <div className="emptyState">No workflow runs have been created yet.</div>
              ) : (
                <div className="runTable">
                  {runs.map((run) => (
                    <div className="runRow" key={run.id}>
                      <div>
                        <strong>{run.id.slice(0, 8)}...</strong>
                        <p>{run.workflow_definition_id.slice(0, 8)}...</p>
                      </div>
                      <div>
                        <span className={`statusPill status-${run.status}`}>{run.status}</span>
                      </div>
                      <div>
                        <p>{run.steps.length} steps</p>
                        <p>{run.approval_requests.length} approvals</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </section>
      ) : null}
    </main>
  );
}
