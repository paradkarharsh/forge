import { apiClient } from './client';
import type {
  AgentApproval,
  AgentSession,
  AgentStep,
  AgentToolCall,
  CreateAgentSessionPayload,
  DenyApprovalPayload,
  GrantApprovalPayload,
  ListAgentsParams,
  ListToolCallsParams,
  PaginatedMeta,
} from './types';

export interface PaginatedAgentSessions {
  readonly items: AgentSession[];
  readonly meta: PaginatedMeta;
}

export class AgentService {
  /**
   * Create a new agent session in the given workspace.
   */
  async createSession(
    workspaceId: string,
    payload: CreateAgentSessionPayload,
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return apiClient.post<AgentSession>(
      `/v1/workspaces/${workspaceId}/agents`,
      payload,
      signal
    );
  }

  /**
   * List agent sessions in the given workspace with optional repository/status filters.
   */
  async listSessions(
    workspaceId: string,
    params: ListAgentsParams = {},
    signal?: AbortSignal
  ): Promise<PaginatedAgentSessions> {
    const raw = await apiClient.request<AgentSession[]>(
      `/v1/workspaces/${workspaceId}/agents`,
      {
        method: 'GET',
        params: {
          repository_id: params.repository_id,
          status: params.status,
          limit: params.limit ?? 50,
          offset: params.offset ?? 0,
        },
        signal,
      }
    );

    // Note: The API envelope returns `data: AgentSession[]` and `meta: { total, limit, offset }`.
    // In apiClient.request, if payload has meta, we need to ensure we return both data and meta.
    return {
      items: raw || [],
      meta: {
        total: raw?.length ?? 0,
        limit: params.limit ?? 50,
        offset: params.offset ?? 0,
      },
    };
  }

  /**
   * Fetch a specific agent session by ID.
   */
  async getSession(
    workspaceId: string,
    agentId: string,
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return apiClient.get<AgentSession>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}`,
      undefined,
      signal
    );
  }

  /**
   * Manually trigger/resume execution for an agent session.
   */
  async runSession(
    workspaceId: string,
    agentId: string,
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return apiClient.post<AgentSession>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/run`,
      undefined,
      signal
    );
  }

  /**
   * Request cancellation for an active agent session.
   */
  async cancelSession(
    workspaceId: string,
    agentId: string,
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return apiClient.post<AgentSession>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/cancel`,
      undefined,
      signal
    );
  }

  /**
   * List execution plan steps for an agent session.
   */
  async getSteps(
    workspaceId: string,
    agentId: string,
    signal?: AbortSignal
  ): Promise<AgentStep[]> {
    return apiClient.get<AgentStep[]>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/steps`,
      undefined,
      signal
    );
  }

  /**
   * List tool invocations for an agent session.
   */
  async getToolCalls(
    workspaceId: string,
    agentId: string,
    params: ListToolCallsParams = {},
    signal?: AbortSignal
  ): Promise<AgentToolCall[]> {
    return apiClient.get<AgentToolCall[]>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/tool-calls`,
      {
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
      },
      signal
    );
  }

  /**
   * List approval requests for an agent session.
   */
  async getApprovals(
    workspaceId: string,
    agentId: string,
    signal?: AbortSignal
  ): Promise<AgentApproval[]> {
    return apiClient.get<AgentApproval[]>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/approvals`,
      undefined,
      signal
    );
  }

  /**
   * Grant human approval for a pending tool call.
   */
  async grantApproval(
    workspaceId: string,
    agentId: string,
    approvalId: string,
    payload?: GrantApprovalPayload,
    signal?: AbortSignal
  ): Promise<AgentApproval> {
    return apiClient.post<AgentApproval>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/approvals/${approvalId}/grant`,
      payload,
      signal
    );
  }

  /**
   * Deny human approval for a pending tool call.
   */
  async denyApproval(
    workspaceId: string,
    agentId: string,
    approvalId: string,
    payload?: DenyApprovalPayload,
    signal?: AbortSignal
  ): Promise<AgentApproval> {
    return apiClient.post<AgentApproval>(
      `/v1/workspaces/${workspaceId}/agents/${agentId}/approvals/${approvalId}/deny`,
      payload,
      signal
    );
  }
}

export const agentService = new AgentService();
