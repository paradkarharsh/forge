/**
 * Strongly typed definitions for the Forge Agentic Development Engine (FP8).
 * Strictly mirrors the verified schemas and enums from services/api.
 */

export type AgentStatus =
  | 'created'
  | 'planning'
  | 'running'
  | 'waiting_for_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'timed_out'
  | 'expired';

export const AGENT_STATUSES: Record<string, AgentStatus> = {
  CREATED: 'created',
  PLANNING: 'planning',
  RUNNING: 'running',
  WAITING_FOR_APPROVAL: 'waiting_for_approval',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  TIMED_OUT: 'timed_out',
  EXPIRED: 'expired',
} as const;

export function isTerminalStatus(status: AgentStatus): boolean {
  return (
    status === 'completed' ||
    status === 'failed' ||
    status === 'cancelled' ||
    status === 'timed_out' ||
    status === 'expired'
  );
}

export function isCancellableStatus(status: AgentStatus): boolean {
  return (
    status === 'created' ||
    status === 'planning' ||
    status === 'running' ||
    status === 'waiting_for_approval'
  );
}

export interface AgentLimits {
  readonly max_wall_time_seconds: number;
  readonly max_llm_calls: number;
  readonly max_tool_calls: number;
  readonly max_output_bytes: number;
  readonly max_observation_bytes: number;
}

export interface ExecutionMetrics {
  readonly total_llm_calls: number;
  readonly total_llm_retries: number;
  readonly total_tool_calls: number;
  readonly total_input_tokens: number;
  readonly total_output_tokens: number;
  readonly wall_time_seconds: number;
  readonly estimated_cost_usd: number;
}

export interface AgentSession {
  readonly id: string;
  readonly workspace_id: string;
  readonly user_id: string;
  readonly objective: string;
  readonly status: AgentStatus;
  readonly repository_id: string | null;
  readonly conversation_id: string | null;
  readonly model: string | null;
  readonly limits: AgentLimits;
  readonly metrics: ExecutionMetrics;
  readonly usage_summary: ExecutionMetrics;
  readonly failure_reason: string | null;
  readonly current_step: number | null;
  readonly metadata: Record<string, unknown>;
  readonly created_at: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
  readonly cancelled_at: string | null;
  readonly last_heartbeat_at: string | null;
}

export type StepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'skipped';

export interface AgentStep {
  readonly id: string;
  readonly session_id: string;
  readonly sequence: number;
  readonly objective: string;
  readonly status: StepStatus;
  readonly created_at: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
  readonly metadata: Record<string, unknown>;
}

export type ToolRiskLevel = 'low' | 'high' | 'critical';

export type ToolCallStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'rejected';

export interface AgentToolCall {
  readonly id: string;
  readonly session_id: string;
  readonly step_id: string | null;
  readonly tool_name: string;
  readonly arguments: Record<string, unknown>;
  readonly risk_level: ToolRiskLevel;
  readonly status: ToolCallStatus;
  readonly approval_id: string | null;
  readonly output: string | null;
  readonly error_message: string | null;
  readonly duration_ms: number | null;
  readonly created_at: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
  readonly metadata: Record<string, unknown>;
}

export type ApprovalStatus = 'pending' | 'granted' | 'denied' | 'expired';

export interface AgentApproval {
  readonly id: string;
  readonly session_id: string;
  readonly tool_call_id: string;
  readonly tool_name: string;
  readonly arguments_hash: string;
  readonly status: ApprovalStatus;
  readonly requested_by: string | null;
  readonly decided_by: string | null;
  readonly reason: string | null;
  readonly requested_at: string;
  readonly decided_at: string | null;
  readonly expires_at: string | null;
  readonly metadata: Record<string, unknown>;
}

export interface AgentEvent {
  readonly id: string;
  readonly event_type: string;
  readonly session_id: string;
  readonly timestamp: string;
  readonly data: Record<string, unknown>;
}

export interface ApiEnvelope<T> {
  readonly data: T;
  readonly error: null;
  readonly meta?: {
    readonly total?: number;
    readonly limit?: number;
    readonly offset?: number;
    readonly [key: string]: unknown;
  };
}

export interface ApiErrorDetail {
  readonly code: string;
  readonly message: string;
  readonly details?: unknown;
  readonly request_id?: string;
}

export interface ApiErrorEnvelope {
  readonly data: null;
  readonly error: ApiErrorDetail;
}

export type ApiResponse<T> = ApiEnvelope<T> | ApiErrorEnvelope;

export interface PaginatedMeta {
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

export interface PaginatedResponse<T> {
  readonly data: T[];
  readonly error: null;
  readonly meta: PaginatedMeta;
}

export interface CreateAgentSessionPayload {
  readonly objective: string;
  readonly repository_id?: string | null;
  readonly conversation_id?: string | null;
  readonly model?: string | null;
  readonly limits?: Partial<AgentLimits> | null;
  readonly metadata?: Record<string, unknown> | null;
}

export interface ListAgentsParams {
  readonly repository_id?: string | null;
  readonly status?: AgentStatus | null;
  readonly limit?: number;
  readonly offset?: number;
}

export interface ListToolCallsParams {
  readonly limit?: number;
  readonly offset?: number;
}

export interface GrantApprovalPayload {
  readonly reason?: string | null;
}

export interface DenyApprovalPayload {
  readonly reason?: string | null;
}

export type FileChangeOperation = 'ADDED' | 'MODIFIED' | 'DELETED';

export interface ChangedFile {
  readonly path: string;
  readonly operation: FileChangeOperation;
  readonly additions: number;
  readonly deletions: number;
  readonly diff?: string;
  readonly toolName?: string;
  readonly timestamp: string;
}
