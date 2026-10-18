import createClient, { type Client } from "openapi-fetch";
import type * as Api from "./client";

export type ClientOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  credentials?: RequestCredentials;
};
type PublicError = Pick<Api.ApiError, "message" | "request_id" | "code">;
export type CatalogBrowseOptions = NonNullable<
  Api.paths["/v1/manager/catalog"]["get"]["parameters"]["query"]
>;

export class OpenCommerceApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly error: PublicError | null,
  ) {
    super(error?.message ?? `Open Commerce API request failed: ${status}`);
    this.name = "OpenCommerceApiError";
  }
}

function publicError(payload: unknown): PublicError | null {
  if (!payload || typeof payload !== "object" || !("error" in payload))
    return null;
  const error = payload.error;
  if (!error || typeof error !== "object") return null;
  if (
    !("message" in error) ||
    typeof error.message !== "string" ||
    !("request_id" in error) ||
    typeof error.request_id !== "string" ||
    !("code" in error) ||
    typeof error.code !== "string"
  )
    return null;
  return {
    message: error.message,
    request_id: error.request_id,
    code: error.code,
  };
}

async function unwrap<T>(
  result: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await result;
  if (!response.ok)
    throw new OpenCommerceApiError(response.status, publicError(error));
  if (data === undefined) throw new Error("API returned no response body");
  return data;
}

function writeKey(key: string) {
  if (!key.trim()) throw new Error("An idempotency key is required");
  return { "Idempotency-Key": key };
}

/** Convenience methods over generated paths. Request and response types come from OpenAPI. */
export class OpenCommerceClient {
  readonly api: Client<Api.paths>;

  constructor(options: ClientOptions) {
    this.api = createClient<Api.paths>({
      baseUrl: options.baseUrl.replace(/\/$/, ""),
      fetch: options.fetcher,
      credentials: options.credentials ?? "omit",
      redirect: "error",
      cache: "no-store",
    });
  }

  live() {
    return unwrap(this.api.GET("/health/live"));
  }
  async ready() {
    const result = await this.api.GET("/health/ready");
    if (
      result.response.status === 503 &&
      result.error &&
      "status" in result.error
    )
      return result.error;
    return unwrap(Promise.resolve(result));
  }
  meta() {
    return unwrap(this.api.GET("/v1/meta"));
  }
  capabilities() {
    return unwrap(this.api.GET("/v1/capabilities"));
  }
  draftGoal(body: Api.GoalDraftRequest, key?: string) {
    if (body.planning_mode === "model_backed" && !key)
      throw new Error("Model interpretation requires a stable request key");
    return unwrap(
      this.api.POST("/v1/goals/draft", {
        body,
        headers: key ? writeKey(key) : undefined,
      }),
    );
  }
  reviewGoalConfiguration(body: Api.GoalCreateRequest) {
    return unwrap(this.api.POST("/v1/goals/review", { body }));
  }
  metricDefinitions(options: { cursor?: string; limit?: number } = {}) {
    return unwrap(
      this.api.GET("/v1/metrics/definitions", { params: { query: options } }),
    );
  }
  metricSummary(instanceId?: string) {
    return unwrap(
      this.api.GET("/v1/metrics/summary", {
        params: { query: { instance_id: instanceId } },
      }),
    );
  }
  metricSeries(
    options: {
      metric?: Api.MetricName;
      instanceId?: string;
      cursor?: string;
      limit?: number;
    } = {},
  ) {
    return unwrap(
      this.api.GET("/v1/metrics/series", {
        params: {
          query: {
            metric: options.metric,
            instance_id: options.instanceId,
            cursor: options.cursor,
            limit: options.limit,
          },
        },
      }),
    );
  }
  catalogProducts(
    options: { instanceId?: string; cursor?: string; limit?: number } = {},
  ) {
    return unwrap(
      this.api.GET("/v1/catalog/products", {
        params: {
          query: {
            instance_id: options.instanceId,
            cursor: options.cursor,
            limit: options.limit,
          },
        },
      }),
    );
  }
  catalogProduct(productId: string, instanceId?: string) {
    return unwrap(
      this.api.GET("/v1/catalog/products/{product_id}", {
        params: {
          path: { product_id: productId },
          query: { instance_id: instanceId },
        },
      }),
    );
  }
  catalogInventory(
    options: { instanceId?: string; cursor?: string; limit?: number } = {},
  ) {
    return unwrap(
      this.api.GET("/v1/catalog/inventory", {
        params: {
          query: {
            instance_id: options.instanceId,
            cursor: options.cursor,
            limit: options.limit,
          },
        },
      }),
    );
  }
  interventions(
    options: {
      status?: Api.ActionStatus;
      cursor?: string;
      limit?: number;
    } = {},
  ) {
    return unwrap(
      this.api.GET("/v1/interventions", { params: { query: options } }),
    );
  }
  audit(
    options: {
      action_id?: string;
      event_type?: string;
      cursor?: string;
      limit?: number;
    } = {},
  ) {
    return unwrap(this.api.GET("/v1/audit", { params: { query: options } }));
  }
  simulatorScenarios() {
    return unwrap(this.api.GET("/v1/simulator/scenarios"));
  }
  createSimulatorInstanceFromRequest(
    body: Api.CreateSimulatorInstanceAliasRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/simulator/instances", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  createSimulatorInstance(
    scenarioId: Api.ScenarioId,
    body: Api.CreateSimulatorInstanceRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/simulator/scenarios/{scenario_id}/instances", {
        body,
        params: { path: { scenario_id: scenarioId }, header: writeKey(key) },
      }),
    );
  }
  simulatorInstance(instanceId: string) {
    return unwrap(
      this.api.GET("/v1/simulator/instances/{instance_id}", {
        params: { path: { instance_id: instanceId } },
      }),
    );
  }
  simulatorState(instanceId: string) {
    return unwrap(
      this.api.GET("/v1/simulator/instances/{instance_id}/state", {
        params: { path: { instance_id: instanceId } },
      }),
    );
  }
  advanceSimulator(
    instanceId: string,
    body: Api.AdvanceSimulatorRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/simulator/instances/{instance_id}/advance", {
        body,
        params: { path: { instance_id: instanceId }, header: writeKey(key) },
      }),
    );
  }
  runSimulatorUntil(
    instanceId: string,
    body: Api.RunUntilSimulatorRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/simulator/instances/{instance_id}/run-until", {
        body,
        params: { path: { instance_id: instanceId }, header: writeKey(key) },
      }),
    );
  }
  resetSimulator(
    instanceId: string,
    body: Api.ResetSimulatorRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/simulator/instances/{instance_id}/reset", {
        body,
        params: { path: { instance_id: instanceId }, header: writeKey(key) },
      }),
    );
  }
  simulatorMetrics(instanceId: string) {
    return unwrap(
      this.api.GET("/v1/simulator/instances/{instance_id}/metrics", {
        params: { path: { instance_id: instanceId } },
      }),
    );
  }
  compareSimulatorBaseline(instanceId: string) {
    return unwrap(
      this.api.GET("/v1/simulator/instances/{instance_id}/compare-baseline", {
        params: { path: { instance_id: instanceId } },
      }),
    );
  }
  search(body: Api.SearchRequest) {
    return unwrap(this.api.POST("/v1/search", { body }));
  }
  parseSearch(body: Api.SearchRequest) {
    return unwrap(this.api.POST("/v1/search/parse", { body }));
  }
  evaluateSearch(body: Api.EvaluateSearchRequest) {
    return unwrap(this.api.POST("/v1/search/evaluate", { body }));
  }
  recommendations(body: Api.RecommendationRequest) {
    return unwrap(this.api.POST("/v1/recommendations", { body }));
  }
  ingestEventBatch(body: Api.EventBatchRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/events/batch", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  searchRules(goalContextId?: string) {
    return unwrap(
      this.api.GET("/v1/search/rules", {
        params: { query: { goal_context_id: goalContextId } },
      }),
    );
  }
  controllerGraph() {
    return unwrap(this.api.GET("/v1/controller/graph"));
  }
  createGoal(body: Api.GoalCreateRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/goals", { body, params: { header: writeKey(key) } }),
    );
  }
  goals(options: { cursor?: string; limit?: number } = {}) {
    return unwrap(this.api.GET("/v1/goals", { params: { query: options } }));
  }
  goal(goalId: string) {
    return unwrap(
      this.api.GET("/v1/goals/{goal_id}", {
        params: { path: { goal_id: goalId } },
      }),
    );
  }
  updateGoal(goalId: string, body: Api.GoalUpdateRequest, key: string) {
    return unwrap(
      this.api.PATCH("/v1/goals/{goal_id}", {
        body,
        params: { path: { goal_id: goalId }, header: writeKey(key) },
      }),
    );
  }
  activateGoal(goalId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/goals/{goal_id}/activate", {
        params: { path: { goal_id: goalId }, header: writeKey(key) },
      }),
    );
  }
  pauseGoal(goalId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/goals/{goal_id}/pause", {
        params: { path: { goal_id: goalId }, header: writeKey(key) },
      }),
    );
  }
  archiveGoal(goalId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/goals/{goal_id}/archive", {
        params: { path: { goal_id: goalId }, header: writeKey(key) },
      }),
    );
  }
  runGoal(goalId: string, body: Api.ControllerRunRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/goals/{goal_id}/run", {
        body,
        params: { path: { goal_id: goalId }, header: writeKey(key) },
      }),
    );
  }
  goalProgress(goalId: string) {
    return unwrap(
      this.api.GET("/v1/goals/{goal_id}/progress", {
        params: { path: { goal_id: goalId } },
      }),
    );
  }
  runs(goalId?: string) {
    return unwrap(
      this.api.GET("/v1/runs", { params: { query: { goal_id: goalId } } }),
    );
  }
  run(runId: string) {
    return unwrap(
      this.api.GET("/v1/runs/{run_id}", {
        params: { path: { run_id: runId } },
      }),
    );
  }
  runTrace(runId: string) {
    return unwrap(
      this.api.GET("/v1/runs/{run_id}/trace", {
        params: { path: { run_id: runId } },
      }),
    );
  }
  runEvents(runId: string, lastEventId?: string) {
    return unwrap(
      this.api.GET("/v1/runs/{run_id}/events", {
        params: {
          path: { run_id: runId },
          header: { "Last-Event-ID": lastEventId },
        },
        parseAs: "text",
      }),
    );
  }
  cancelRun(runId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/runs/{run_id}/cancel", {
        params: { path: { run_id: runId }, header: writeKey(key) },
      }),
    );
  }
  resumeRun(runId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/runs/{run_id}/resume", {
        params: { path: { run_id: runId }, header: writeKey(key) },
      }),
    );
  }
  actions(
    filters: {
      goalId?: string;
      runId?: string;
      status?: Api.ActionStatus;
      cursor?: string;
      limit?: number;
    } = {},
  ) {
    return unwrap(
      this.api.GET("/v1/actions", {
        params: {
          query: {
            goal_id: filters.goalId,
            run_id: filters.runId,
            status: filters.status,
            cursor: filters.cursor,
            limit: filters.limit,
          },
        },
      }),
    );
  }
  action(actionId: string) {
    return unwrap(
      this.api.GET("/v1/actions/{action_id}", {
        params: { path: { action_id: actionId } },
      }),
    );
  }
  approveAction(
    actionId: string,
    body: Api.ActionApprovalRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/actions/{action_id}/approve", {
        body,
        params: { path: { action_id: actionId }, header: writeKey(key) },
      }),
    );
  }
  rejectAction(actionId: string, body: Api.ActionApprovalRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/actions/{action_id}/reject", {
        body,
        params: { path: { action_id: actionId }, header: writeKey(key) },
      }),
    );
  }
  executeAction(actionId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/actions/{action_id}/execute", {
        params: { path: { action_id: actionId }, header: writeKey(key) },
      }),
    );
  }
  cancelAction(actionId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/actions/{action_id}/cancel", {
        params: { path: { action_id: actionId }, header: writeKey(key) },
      }),
    );
  }
  rollbackAction(actionId: string, key: string) {
    return unwrap(
      this.api.POST("/v1/actions/{action_id}/rollback", {
        params: { path: { action_id: actionId }, header: writeKey(key) },
      }),
    );
  }
  actionAudit(actionId: string) {
    return unwrap(
      this.api.GET("/v1/actions/{action_id}/audit", {
        params: { path: { action_id: actionId } },
      }),
    );
  }
  policy() {
    return unwrap(this.api.GET("/v1/policy"));
  }
  updatePolicy(body: Api.PolicyUpdateRequest, key: string) {
    return unwrap(
      this.api.PUT("/v1/policy", { body, params: { header: writeKey(key) } }),
    );
  }
  validatePolicy(body: Api.PolicyValidateRequest) {
    return unwrap(this.api.POST("/v1/policy/validate", { body }));
  }
  policyHistory() {
    return unwrap(this.api.GET("/v1/policy/history"));
  }
  killSwitch() {
    return unwrap(this.api.GET("/v1/kill-switch"));
  }
  enableKillSwitch(key: string) {
    return unwrap(
      this.api.POST("/v1/kill-switch/enable", {
        params: { header: writeKey(key) },
      }),
    );
  }
  disableKillSwitch(key: string) {
    return unwrap(
      this.api.POST("/v1/kill-switch/disable", {
        params: { header: writeKey(key) },
      }),
    );
  }
  managerThreads() {
    return unwrap(this.api.GET("/v1/manager/threads"));
  }
  managerWorkspace() {
    return unwrap(this.api.GET("/v1/manager/workspace"));
  }
  managerCatalog(options: CatalogBrowseOptions = {}) {
    return unwrap(this.api.GET("/v1/manager/catalog", { params: { query: options } }));
  }
  shopperCatalog(options: CatalogBrowseOptions = {}) {
    return unwrap(this.api.GET("/v1/shopper/catalog", { params: { query: options } }));
  }
  managerStatus() {
    return unwrap(this.api.GET("/v1/manager/status"));
  }
  rankingOverview() {
    return unwrap(this.api.GET("/v1/manager/ranking"));
  }
  trainRanking(body: Api.TrainRankingInput, key: string) {
    return unwrap(this.api.POST("/v1/manager/ranking/train", { body, params: { header: writeKey(key) } }));
  }
  approveRanking(body: Api.RankingApproval, key: string) {
    return unwrap(this.api.POST("/v1/manager/ranking/approve", { body, params: { header: writeKey(key) } }));
  }
  previewRanking(body: Api.RankingPreviewInput) {
    return unwrap(this.api.POST("/v1/manager/ranking/preview", { body }));
  }
  checkShopify() {
    return unwrap(this.api.POST("/v1/manager/connectors/shopify/check"));
  }
  importShopify(key: string) {
    return unwrap(this.api.POST("/v1/manager/connectors/shopify/import", { params: { header: writeKey(key) } }));
  }
  managerCommerceOverview() {
    return unwrap(this.api.GET("/v1/manager/commerce/overview"));
  }
  bootstrapManagerWorkspace(key: string) {
    return unwrap(
      this.api.POST("/v1/manager/workspace/bootstrap", {
        params: { header: writeKey(key) },
      }),
    );
  }
  resetManagerWorkspace(body: Api.ManagerWorkspaceResetRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/manager/workspace/reset", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  createManagerThread(body: Api.ManagerThreadCreateRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/manager/threads", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  managerThread(threadId: string) {
    return unwrap(
      this.api.GET("/v1/manager/threads/{thread_id}", {
        params: { path: { thread_id: threadId } },
      }),
    );
  }
  updateManagerThread(
    threadId: string,
    body: Api.ManagerThreadUpdateRequest,
    key: string,
  ) {
    return unwrap(
      this.api.PATCH("/v1/manager/threads/{thread_id}", {
        body,
        params: { path: { thread_id: threadId }, header: writeKey(key) },
      }),
    );
  }
  clearManagerChannel(threadId: string, key: string) {
    return unwrap(
      this.api.DELETE("/v1/manager/threads/{thread_id}/messages", {
        params: { path: { thread_id: threadId }, header: writeKey(key) },
      }),
    );
  }
  createManagerReplyThread(
    channelId: string,
    body: Api.ManagerReplyThreadCreateRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/manager/threads/{channel_id}/replies", {
        body,
        params: { path: { channel_id: channelId }, header: writeKey(key) },
      }),
    );
  }
  managerReplyThread(channelId: string, rootMessageId: string) {
    return unwrap(
      this.api.GET(
        "/v1/manager/threads/{channel_id}/messages/{root_message_id}/replies",
        {
          params: {
            path: {
              channel_id: channelId,
              root_message_id: rootMessageId,
            },
          },
        },
      ),
    );
  }
  sendManagerMessage(
    threadId: string,
    body: Api.ManagerMessageRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/manager/threads/{thread_id}/messages", {
        body,
        params: {
          path: { thread_id: threadId },
          header: writeKey(key),
        },
      }),
    );
  }
  createManagerRun(threadId: string, body: Api.ManagerMessageRequest, key: string) {
    return unwrap(this.api.POST("/v1/manager/threads/{thread_id}/runs", {
      body, params: { path: { thread_id: threadId }, header: writeKey(key) },
    }));
  }
  managerRun(runId: string) {
    return unwrap(this.api.GET("/v1/manager/runs/{run_id}", {
      params: { path: { run_id: runId } },
    }));
  }
  managerRunEvents(runId: string, after = 0) {
    return unwrap(this.api.GET("/v1/manager/runs/{run_id}/events", {
      params: { path: { run_id: runId }, query: { after } },
    }));
  }
  cancelManagerRun(runId: string, key: string) {
    return unwrap(this.api.POST("/v1/manager/runs/{run_id}/cancel", {
      params: { path: { run_id: runId }, header: writeKey(key) },
    }));
  }
  profileManagerDataset(
    threadId: string,
    body: Api.ManagerDatasetProfileRequest,
    key: string,
  ) {
    return unwrap(
      this.api.POST("/v1/manager/threads/{thread_id}/datasets/profile", {
        body,
        params: {
          path: { thread_id: threadId },
          header: writeKey(key),
        },
      }),
    );
  }
  managerMemories(layer?: "long_term" | "working" | "periodic") {
    return unwrap(
      this.api.GET("/v1/manager/memories", {
        params: { query: { layer } },
      }),
    );
  }
  deleteManagerMemory(memoryId: string, key: string) {
    return unwrap(
      this.api.DELETE("/v1/manager/memories/{memory_id}", {
        params: {
          path: { memory_id: memoryId },
          header: writeKey(key),
        },
      }),
    );
  }
  registerShopper(body: Api.ShopperRegisterRequest) {
    return unwrap(this.api.POST("/v1/shopper/auth/register", { body }));
  }
  loginShopper(body: Api.ShopperLoginRequest) {
    return unwrap(this.api.POST("/v1/shopper/auth/login", { body }));
  }
  async logoutShopper() {
    const result = await this.api.POST("/v1/shopper/auth/logout");
    if (!result.response.ok)
      throw new OpenCommerceApiError(
        result.response.status,
        publicError(result.error),
      );
  }
  shopperAccount() {
    return unwrap(this.api.GET("/v1/shopper/me"));
  }
  shopperConversations() {
    return unwrap(this.api.GET("/v1/shopper/conversations"));
  }
  shopperConversation(conversationId: string) {
    return unwrap(
      this.api.GET("/v1/shopper/conversations/{conversation_id}", {
        params: { path: { conversation_id: conversationId } },
      }),
    );
  }
  shopperMemories() {
    return unwrap(this.api.GET("/v1/shopper/memories"));
  }
  shopperActivity(query: Api.ActivityQuery = {}) {
    return unwrap(this.api.GET("/v1/shopper/activity", { params: { query } }));
  }
  configureShopperActivity(body: Api.ActivityRuleInput, key: string) {
    return unwrap(this.api.POST("/v1/shopper/activity/rules", {
      body, params: { header: writeKey(key) },
    }));
  }
  managerActivity(query: Api.ActivityQuery = {}) {
    return unwrap(this.api.GET("/v1/manager/activity", { params: { query } }));
  }
  configureManagerActivity(body: Api.ActivityRuleInput, key: string) {
    return unwrap(this.api.POST("/v1/manager/activity/rules", {
      body, params: { header: writeKey(key) },
    }));
  }
  shopperDiscovery() {
    return unwrap(this.api.GET("/v1/shopper/discovery"));
  }
  shopperCart() {
    return unwrap(this.api.GET("/v1/shopper/cart"));
  }
  shopperOrders(query: { limit?: number; offset?: number } = {}) {
    return unwrap(this.api.GET("/v1/shopper/orders", { params: { query } }));
  }
  addShopperCartItem(body: Api.CartItemAddRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/shopper/cart/items", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  updateShopperCartItem(
    lineId: string,
    body: Api.CartItemUpdateRequest,
    key: string,
  ) {
    return unwrap(
      this.api.PATCH("/v1/shopper/cart/items/{line_id}", {
        body,
        params: { path: { line_id: lineId }, header: writeKey(key) },
      }),
    );
  }
  deleteShopperCartItem(lineId: string, key: string) {
    return unwrap(
      this.api.DELETE("/v1/shopper/cart/items/{line_id}", {
        params: { path: { line_id: lineId }, header: writeKey(key) },
      }),
    );
  }
  previewShopperCheckout(body: Api.CheckoutPreviewRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/shopper/checkout/preview", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  shopperCheckout(checkoutId?: string) {
    return checkoutId
      ? unwrap(this.api.GET("/v1/shopper/checkout/{checkout_id}", {
          params: { path: { checkout_id: checkoutId } },
        }))
      : unwrap(this.api.GET("/v1/shopper/checkout/current"));
  }
  confirmShopperCheckout(body: Api.CheckoutConfirmRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/shopper/checkout/confirm", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
  deleteShopperMemory(memoryId: string, key: string) {
    return unwrap(
      this.api.DELETE("/v1/shopper/memories/{memory_id}", {
        params: {
          path: { memory_id: memoryId },
          header: writeKey(key),
        },
      }),
    );
  }
  chatWithShopper(body: Api.ShopperChatRequest, key: string) {
    return unwrap(
      this.api.POST("/v1/shopper/chat", {
        body,
        params: { header: writeKey(key) },
      }),
    );
  }
}

export function createOpenCommerceClient(baseUrl: string): OpenCommerceClient {
  return new OpenCommerceClient({ baseUrl });
}
