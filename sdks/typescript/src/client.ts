/**
 * Hand-polished TypeScript client for the Kavach `/v1` API (ADR-0016).
 *
 * Method names mirror the reference Python client (`kavach/client.py`) 1:1,
 * camelCased: `issueMandate`, `getMandate`, `revokeMandate`, `requestDecision`,
 * etc. Generated OpenAPI types are shipped alongside in `types.ts` for callers
 * who want them; this wrapper returns plain JSON objects to match the Python
 * client's `dict[str, Any]` ergonomics.
 */

export interface KavachClientOptions {
  baseUrl: string;
  token: string;
  tenant?: string;
  operator?: string;
  /** Request timeout in milliseconds. Defaults to 10_000. */
  timeoutMs?: number;
}

export type Json = Record<string, unknown>;

/** Thrown for any non-2xx response, carrying the RFC 7807 problem body. */
export class KavachApiError extends Error {
  readonly status: number;
  readonly problem: Json | string;

  constructor(status: number, problem: Json | string) {
    const detail =
      typeof problem === "string"
        ? problem
        : (problem.detail as string) ?? (problem.title as string) ?? "request failed";
    super(`Kavach API error ${status}: ${detail}`);
    this.name = "KavachApiError";
    this.status = status;
    this.problem = problem;
  }
}

interface RequestInit_ {
  method: "GET" | "POST";
  path: string;
  body?: Json;
  query?: Record<string, string | number | undefined>;
  idempotencyKey?: string;
  mandateToken?: string;
}

export class KavachClient {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly tenant: string;
  private readonly operator?: string;
  private readonly timeoutMs: number;

  constructor(options: KavachClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.token = options.token;
    this.tenant = options.tenant ?? "default";
    this.operator = options.operator;
    this.timeoutMs = options.timeoutMs ?? 10_000;
  }

  private headers(idempotencyKey?: string, mandateToken?: string): Record<string, string> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
      "X-Kavach-Tenant": this.tenant,
    };
    if (this.operator) headers["X-Kavach-Operator"] = this.operator;
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    if (mandateToken) headers["X-Kavach-Mandate"] = mandateToken;
    return headers;
  }

  private async request(init: RequestInit_): Promise<Json> {
    const url = new URL(this.baseUrl + init.path);
    for (const [key, value] of Object.entries(init.query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const headers = this.headers(init.idempotencyKey, init.mandateToken);
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
    try {
      const resp = await fetch(url, {
        method: init.method,
        headers,
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
        signal: controller.signal,
      });
      const text = await resp.text();
      const parsed: Json | string = text ? safeJson(text) : {};
      if (!resp.ok) throw new KavachApiError(resp.status, parsed);
      return typeof parsed === "string" ? { value: parsed } : parsed;
    } finally {
      clearTimeout(timer);
    }
  }

  // -- system -------------------------------------------------------------

  async health(): Promise<Json> {
    return this.request({ method: "GET", path: "/v1/health" });
  }

  // -- ingress + decisions ------------------------------------------------

  async recordAction(
    agentId: string,
    args: {
      sessionId: string;
      actionType: string;
      parameters?: Json;
      context?: string;
      idempotencyKey?: string;
    },
  ): Promise<Json> {
    return this.request({
      method: "POST",
      path: `/v1/agents/${encodeURIComponent(agentId)}/actions`,
      body: {
        session_id: args.sessionId,
        action_type: args.actionType,
        parameters: args.parameters ?? {},
        context: args.context ?? null,
      },
      idempotencyKey: args.idempotencyKey,
    });
  }

  async requestDecision(
    agentId: string,
    args: {
      sessionId: string;
      actionType: string;
      parameters?: Json;
      useCase?: string;
      context?: string;
      idempotencyKey?: string;
      mandateToken?: string;
    },
  ): Promise<Json> {
    return this.request({
      method: "POST",
      path: `/v1/agents/${encodeURIComponent(agentId)}/decisions`,
      body: {
        session_id: args.sessionId,
        action_type: args.actionType,
        parameters: args.parameters ?? {},
        use_case: args.useCase ?? "customer_service",
        context: args.context ?? null,
      },
      idempotencyKey: args.idempotencyKey,
      mandateToken: args.mandateToken,
    });
  }

  async resolveStepUp(
    decisionId: string,
    args: { resolution: string; operatorId: string; rationale?: string },
  ): Promise<Json> {
    return this.request({
      method: "POST",
      path: `/v1/decisions/${encodeURIComponent(decisionId)}/step-up/resolve`,
      body: {
        resolution: args.resolution,
        operator_id: args.operatorId,
        rationale: args.rationale ?? "",
      },
    });
  }

  // -- reads --------------------------------------------------------------

  async getTrust(agentId: string, args?: { context?: string }): Promise<Json> {
    return this.request({
      method: "GET",
      path: `/v1/agents/${encodeURIComponent(agentId)}/trust`,
      query: { context: args?.context ?? "customer_service" },
    });
  }

  async getTimeline(agentId: string, args?: { limit?: number }): Promise<Json> {
    return this.request({
      method: "GET",
      path: `/v1/agents/${encodeURIComponent(agentId)}/timeline`,
      query: { limit: args?.limit ?? 50 },
    });
  }

  async requestAuditExport(args: {
    agentId: string;
    from: Date | string;
    to: Date | string;
  }): Promise<Json> {
    return this.request({
      method: "POST",
      path: "/v1/audit/exports",
      body: {
        agent_id: args.agentId,
        from: toIso(args.from),
        to: toIso(args.to),
      },
    });
  }

  // -- admin --------------------------------------------------------------

  async registerAgent(args: {
    agentId: string;
    displayName: string;
    useCase?: string;
    metadata?: Json;
  }): Promise<Json> {
    return this.request({
      method: "POST",
      path: "/v1/admin/agents",
      body: {
        agent_id: args.agentId,
        display_name: args.displayName,
        use_case: args.useCase ?? null,
        metadata: args.metadata ?? {},
      },
    });
  }

  async issueMandate(payload: Json): Promise<Json> {
    return this.request({ method: "POST", path: "/v1/mandates", body: payload });
  }

  async getMandate(mandateId: string): Promise<Json> {
    return this.request({
      method: "GET",
      path: `/v1/mandates/${encodeURIComponent(mandateId)}`,
    });
  }

  async revokeMandate(
    mandateId: string,
    args: { revokedBy: string; reason?: string },
  ): Promise<Json> {
    return this.request({
      method: "POST",
      path: `/v1/mandates/${encodeURIComponent(mandateId)}/revoke`,
      body: { revoked_by: args.revokedBy, reason: args.reason ?? "" },
    });
  }

  async uploadPolicy(payload: Json): Promise<Json> {
    return this.request({ method: "POST", path: "/v1/admin/policies", body: payload });
  }

  async createWebhookSubscription(args: {
    url: string;
    eventTypes: string[];
    secret?: string;
  }): Promise<Json> {
    return this.request({
      method: "POST",
      path: "/v1/webhooks/subscriptions",
      body: {
        url: args.url,
        event_types: args.eventTypes,
        secret: args.secret ?? null,
      },
    });
  }
}

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : value;
}

function safeJson(text: string): Json | string {
  try {
    return JSON.parse(text) as Json;
  } catch {
    return text;
  }
}
