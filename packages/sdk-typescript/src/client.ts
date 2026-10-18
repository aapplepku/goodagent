/* Generated from openapi/openapi.json by openapi-typescript. Do not edit. */
/* Schema SHA-256: de5406f78c09e439fb63d70da523377302794f637d569778fe50250024672ed2 */
export interface paths {
  "/health/live": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Live */
    get: operations["live_health_live_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/health/ready": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Ready */
    get: operations["ready_health_ready_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Actions
     * @description List controller actions.
     */
    get: operations["list_actions_v1_actions_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Action
     * @description Return one controller action.
     */
    get: operations["get_action_v1_actions__action_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}/approve": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Approve Action
     * @description Approve an action by exact version hash.
     */
    post: operations["approve_action_v1_actions__action_id__approve_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}/audit": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Action Audit
     * @description Return action audit entries.
     */
    get: operations["get_action_audit_v1_actions__action_id__audit_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}/cancel": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Cancel Action
     * @description Cancel one action.
     */
    post: operations["cancel_action_v1_actions__action_id__cancel_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}/execute": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Execute Action
     * @description Execute one action through the controller executor.
     */
    post: operations["execute_action_v1_actions__action_id__execute_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}/reject": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reject Action
     * @description Reject an action by exact version hash.
     */
    post: operations["reject_action_v1_actions__action_id__reject_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/actions/{action_id}/rollback": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Rollback Action
     * @description Rollback one executed simulator action.
     */
    post: operations["rollback_action_v1_actions__action_id__rollback_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/audit": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Audit Feed
     * @description Return a redacted tenant audit feed from controller action records.
     */
    get: operations["list_audit_feed_v1_audit_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/capabilities": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Capabilities
     * @description Return local-demo capabilities and current request context.
     */
    get: operations["get_capabilities_v1_capabilities_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/catalog/inventory": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Catalog Inventory
     * @description Return inventory summaries.
     */
    get: operations["get_catalog_inventory_v1_catalog_inventory_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/catalog/products": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Catalog Products
     * @description Return a cursor page of simulator products.
     */
    get: operations["list_catalog_products_v1_catalog_products_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/catalog/products/{product_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Catalog Product
     * @description Return one simulator product detail.
     */
    get: operations["get_catalog_product_v1_catalog_products__product_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/controller/graph": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Controller Graph
     * @description Return the documented controller graph and write boundary.
     */
    get: operations["get_controller_graph_v1_controller_graph_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/events/batch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Ingest Event Batch
     * @description Ingest pseudonymous search/product events.
     */
    post: operations["ingest_event_batch_v1_events_batch_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Goals
     * @description List local-demo goals.
     */
    get: operations["list_goals_v1_goals_get"];
    put?: never;
    /**
     * Create Goal
     * @description Create a tenant-scoped local-demo goal.
     */
    post: operations["create_goal_v1_goals_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/{goal_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Goal
     * @description Return one goal.
     */
    get: operations["get_goal_v1_goals__goal_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Update Goal
     * @description Patch one goal.
     */
    patch: operations["update_goal_v1_goals__goal_id__patch"];
    trace?: never;
  };
  "/v1/goals/{goal_id}/activate": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Activate Goal
     * @description Activate a goal.
     */
    post: operations["activate_goal_v1_goals__goal_id__activate_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/{goal_id}/archive": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Archive Goal
     * @description Archive a goal.
     */
    post: operations["archive_goal_v1_goals__goal_id__archive_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/{goal_id}/merchandising/{view}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Merchandising Evidence
     * @description Bounded tenant-owned, read-only observed economics and serving investigation.
     */
    get: operations["get_merchandising_evidence_v1_goals__goal_id__merchandising__view__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/{goal_id}/pause": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Pause Goal
     * @description Pause a goal.
     */
    post: operations["pause_goal_v1_goals__goal_id__pause_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/{goal_id}/progress": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Goal Progress
     * @description Return goal progress.
     */
    get: operations["get_goal_progress_v1_goals__goal_id__progress_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/{goal_id}/run": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Run Goal
     * @description Run the deterministic controller graph for a goal.
     */
    post: operations["run_goal_v1_goals__goal_id__run_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/draft": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Draft Goal Route */
    post: operations["draft_goal_route_v1_goals_draft_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/goals/review": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Review Goal Configuration
     * @description Review a typed configuration without inference, activation or an invented parser claim.
     */
    post: operations["review_goal_configuration_v1_goals_review_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/interventions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Interventions
     * @description Return action/intervention summaries.
     */
    get: operations["list_interventions_v1_interventions_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/kill-switch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Kill Switch
     * @description Return kill-switch state.
     */
    get: operations["get_kill_switch_v1_kill_switch_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/kill-switch/disable": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Disable Kill Switch
     * @description Disable the tenant kill switch.
     */
    post: operations["disable_kill_switch_v1_kill_switch_disable_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/kill-switch/enable": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Enable Kill Switch
     * @description Enable the tenant kill switch.
     */
    post: operations["enable_kill_switch_v1_kill_switch_enable_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/activity": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Manager Activity */
    get: operations["manager_activity_v1_manager_activity_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/activity/rules": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Manager Activity Rule */
    post: operations["manager_activity_rule_v1_manager_activity_rules_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/catalog": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Browse Manager Catalog
     * @description Browse the verified active upload; pending uploads never replace it early.
     */
    get: operations["browse_manager_catalog_v1_manager_catalog_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/commerce/overview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Manager Commerce Overview
     * @description Return observed inventory and local reservation/order/payment state.
     */
    get: operations["get_manager_commerce_overview_v1_manager_commerce_overview_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/connectors/shopify/check": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Check Shopify */
    post: operations["check_shopify_v1_manager_connectors_shopify_check_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/connectors/shopify/import": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Import Shopify */
    post: operations["import_shopify_v1_manager_connectors_shopify_import_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/memories": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Manager Memories
     * @description Inspect explicit long-term preferences and immutable periodic summaries.
     */
    get: operations["list_manager_memories_v1_manager_memories_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/memories/{memory_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /**
     * Delete Manager Memory
     * @description Forget an explicit long-term preference; periodic summaries are immutable.
     */
    delete: operations["delete_manager_memory_v1_manager_memories__memory_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/ranking": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Ranking Overview */
    get: operations["ranking_overview_v1_manager_ranking_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/ranking/approve": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Approve Ranking */
    post: operations["approve_ranking_v1_manager_ranking_approve_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/ranking/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Preview Ranking */
    post: operations["preview_ranking_v1_manager_ranking_preview_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/ranking/train": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Train Ranking */
    post: operations["train_ranking_v1_manager_ranking_train_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/runs/{run_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Manager Run */
    get: operations["get_manager_run_v1_manager_runs__run_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/runs/{run_id}/cancel": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Cancel Manager Run */
    post: operations["cancel_manager_run_v1_manager_runs__run_id__cancel_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/runs/{run_id}/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Manager Run Events */
    get: operations["get_manager_run_events_v1_manager_runs__run_id__events_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/status": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Manager Runtime Status
     * @description Return live read-only service and commerce-surface status.
     */
    get: operations["get_manager_runtime_status_v1_manager_status_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/threads": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Manager Threads
     * @description List tenant-scoped conversations newest first.
     */
    get: operations["list_manager_threads_v1_manager_threads_get"];
    put?: never;
    /**
     * Create Manager Thread
     * @description Create one durable manager conversation with an initial assistant turn.
     */
    post: operations["create_manager_thread_v1_manager_threads_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/threads/{channel_id}/messages/{root_message_id}/replies": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Manager Reply Thread
     * @description Load one durable, one-level reply history.
     */
    get: operations["get_manager_reply_thread_v1_manager_threads__channel_id__messages__root_message_id__replies_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/threads/{channel_id}/replies": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Create Manager Reply Thread
     * @description Create or return one durable reply thread for a channel message.
     */
    post: operations["create_manager_reply_thread_v1_manager_threads__channel_id__replies_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/threads/{thread_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Manager Thread
     * @description Load conversation history, working state, and recalled durable memories.
     */
    get: operations["get_manager_thread_v1_manager_threads__thread_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Update Manager Thread
     * @description Rename, archive, or restore one tenant-scoped channel.
     */
    patch: operations["update_manager_thread_v1_manager_threads__thread_id__patch"];
    trace?: never;
  };
  "/v1/manager/threads/{thread_id}/datasets/profile": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Profile Manager Dataset
     * @description Profile a bounded CSV attachment and retain only safe structural metadata.
     */
    post: operations["profile_manager_dataset_v1_manager_threads__thread_id__datasets_profile_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/threads/{thread_id}/messages": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Send Manager Message
     * @description Prepare one bounded agent response and record the completed turn atomically.
     */
    post: operations["send_manager_message_v1_manager_threads__thread_id__messages_post"];
    /**
     * Clear Manager Channel History
     * @description Clear one agent channel and its reply branches, retaining long-term memory.
     */
    delete: operations["clear_manager_channel_history_v1_manager_threads__thread_id__messages_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/threads/{thread_id}/runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Create Manager Run */
    post: operations["create_manager_run_v1_manager_threads__thread_id__runs_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/workspace": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Manager Workspace
     * @description Load workspace navigation, onboarding state, and agent capabilities.
     */
    get: operations["get_manager_workspace_v1_manager_workspace_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/workspace/bootstrap": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Bootstrap Manager Workspace
     * @description Start the bounded interview and create eligible default channels once.
     */
    post: operations["bootstrap_manager_workspace_v1_manager_workspace_bootstrap_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/manager/workspace/reset": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reset Manager Workspace
     * @description Reset manager-only workspace state after an explicit confirmation token.
     */
    post: operations["reset_manager_workspace_v1_manager_workspace_reset_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/assets/{asset_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Owner Asset */
    get: operations["get_owner_asset_v1_merchant_assets__asset_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Login Owner */
    post: operations["login_owner_v1_merchant_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Logout Owner */
    post: operations["logout_owner_v1_merchant_auth_logout_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Owner Me */
    get: operations["owner_me_v1_merchant_auth_me_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/oidc/callback": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Oidc Callback */
    get: operations["oidc_callback_v1_merchant_auth_oidc_callback_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/oidc/start": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Oidc Start */
    get: operations["oidc_start_v1_merchant_auth_oidc_start_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/recover": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Recover Owner */
    post: operations["recover_owner_v1_merchant_auth_recover_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/sessions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Owner Sessions */
    get: operations["owner_sessions_v1_merchant_auth_sessions_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/sessions/{session_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Revoke Owner Session */
    delete: operations["revoke_owner_session_v1_merchant_auth_sessions__session_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/setup": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Setup Owner */
    post: operations["setup_owner_v1_merchant_auth_setup_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/auth/status": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Setup Status */
    get: operations["setup_status_v1_merchant_auth_status_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/{import_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Import */
    get: operations["get_import_v1_merchant_imports__import_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/{import_id}/cancel": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Cancel Import */
    post: operations["cancel_import_v1_merchant_imports__import_id__cancel_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/{import_id}/confirm": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Confirm Import */
    post: operations["confirm_import_v1_merchant_imports__import_id__confirm_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/{import_id}/mapping": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Map Import */
    put: operations["map_import_v1_merchant_imports__import_id__mapping_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/{import_id}/retry": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Retry Import */
    post: operations["retry_import_v1_merchant_imports__import_id__retry_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/sample": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Sample Catalog */
    post: operations["sample_catalog_v1_merchant_imports_sample_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/imports/upload": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Upload Catalog */
    post: operations["upload_catalog_v1_merchant_imports_upload_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/store": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Store */
    get: operations["get_store_v1_merchant_store_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /** Update Store */
    patch: operations["update_store_v1_merchant_store_patch"];
    trace?: never;
  };
  "/v1/merchant/store/check-ai": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Check Ai */
    post: operations["check_ai_v1_merchant_store_check_ai_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/store/measurements": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Measurements */
    get: operations["get_measurements_v1_merchant_store_measurements_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/store/monitors": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Setup Monitor */
    put: operations["setup_monitor_v1_merchant_store_monitors_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/store/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Preview Store */
    post: operations["preview_store_v1_merchant_store_preview_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/merchant/store/sharing": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Share Store */
    post: operations["share_store_v1_merchant_store_sharing_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/meta": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Meta */
    get: operations["meta_v1_meta_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/metrics/definitions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Metric Definitions
     * @description Return supported metric definitions.
     */
    get: operations["get_metric_definitions_v1_metrics_definitions_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/metrics/series": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Metrics Series
     * @description Return one simulator metric series.
     */
    get: operations["get_metrics_series_v1_metrics_series_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/metrics/summary": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Metrics Summary
     * @description Return aggregate simulator metrics for the selected or latest instance.
     */
    get: operations["get_metrics_summary_v1_metrics_summary_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/policy": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Policy
     * @description Return tenant policy.
     */
    get: operations["get_policy_v1_policy_get"];
    /**
     * Update Policy
     * @description Update tenant policy.
     */
    put: operations["update_policy_v1_policy_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/policy/history": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Policy History
     * @description Return tenant policy history.
     */
    get: operations["get_policy_history_v1_policy_history_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/policy/validate": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Validate Policy
     * @description Validate a policy patch.
     */
    post: operations["validate_policy_v1_policy_validate_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/recommendations": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Recommend Products
     * @description Return tenant-scoped product recommendations.
     */
    post: operations["recommend_products_v1_recommendations_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Runs
     * @description List controller runs.
     */
    get: operations["list_runs_v1_runs_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/runs/{run_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Run
     * @description Return one controller run.
     */
    get: operations["get_run_v1_runs__run_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/runs/{run_id}/cancel": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Cancel Run
     * @description Cancel a run.
     */
    post: operations["cancel_run_v1_runs__run_id__cancel_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/runs/{run_id}/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Run Events
     * @description Stream ordered run events with sequence-based resumption.
     */
    get: operations["get_run_events_v1_runs__run_id__events_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/runs/{run_id}/resume": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Resume Run
     * @description Resume a run for inspection.
     */
    post: operations["resume_run_v1_runs__run_id__resume_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/runs/{run_id}/trace": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Run Trace
     * @description Return ordered run trace.
     */
    get: operations["get_run_trace_v1_runs__run_id__trace_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/search": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Search Products
     * @description Search tenant-scoped products.
     */
    post: operations["search_products_v1_search_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/search/evaluate": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Evaluate Search
     * @description Evaluate a search result set.
     */
    post: operations["evaluate_search_v1_search_evaluate_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/search/parse": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Parse Search
     * @description Parse a search query without touching indexed documents.
     */
    post: operations["parse_search_v1_search_parse_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/search/rules": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Search Rules
     * @description List tenant-scoped search rules.
     */
    get: operations["list_search_rules_v1_search_rules_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/activity": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Shopper Activity */
    get: operations["shopper_activity_v1_shopper_activity_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/activity/rules": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Shopper Activity Rule */
    post: operations["shopper_activity_rule_v1_shopper_activity_rules_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/assets/{asset_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Asset */
    get: operations["get_asset_v1_shopper_assets__asset_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/guest": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Guest Shopper */
    post: operations["guest_shopper_v1_shopper_auth_guest_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Login Shopper */
    post: operations["login_shopper_v1_shopper_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Logout Shopper */
    post: operations["logout_shopper_v1_shopper_auth_logout_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/merge": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Merge Shopper */
    post: operations["merge_shopper_v1_shopper_auth_merge_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/recover": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Recover Shopper */
    post: operations["recover_shopper_v1_shopper_auth_recover_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/register": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Register Shopper */
    post: operations["register_shopper_v1_shopper_auth_register_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/auth/sessions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Shopper Sessions */
    get: operations["shopper_sessions_v1_shopper_auth_sessions_get"];
    put?: never;
    post?: never;
    /** Revoke Shopper Sessions */
    delete: operations["revoke_shopper_sessions_v1_shopper_auth_sessions_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/cart": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Shopper Cart
     * @description Return the authenticated shopper's open cart.
     */
    get: operations["get_shopper_cart_v1_shopper_cart_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/cart/items": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Add Shopper Cart Item
     * @description Add a server-priced active-catalog product to the open cart.
     */
    post: operations["add_shopper_cart_item_v1_shopper_cart_items_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/cart/items/{line_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /**
     * Delete Shopper Cart Item
     * @description Remove one account-scoped cart line.
     */
    delete: operations["delete_shopper_cart_item_v1_shopper_cart_items__line_id__delete"];
    options?: never;
    head?: never;
    /**
     * Update Shopper Cart Item
     * @description Change a cart quantity after re-reading price and observed stock.
     */
    patch: operations["update_shopper_cart_item_v1_shopper_cart_items__line_id__patch"];
    trace?: never;
  };
  "/v1/shopper/catalog": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Browse Shopper Catalog
     * @description The store's published products, available only to signed-in shoppers.
     */
    get: operations["browse_shopper_catalog_v1_shopper_catalog_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/chat": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Chat With Shopper Agent */
    post: operations["chat_with_shopper_agent_v1_shopper_chat_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/checkout/{checkout_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Shopper Checkout */
    get: operations["get_shopper_checkout_v1_shopper_checkout__checkout_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/checkout/confirm": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Confirm Shopper Checkout
     * @description Run the local test provider and create at most one order.
     */
    post: operations["confirm_shopper_checkout_v1_shopper_checkout_confirm_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/checkout/current": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Current Shopper Checkout */
    get: operations["current_shopper_checkout_v1_shopper_checkout_current_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/checkout/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Preview Shopper Checkout
     * @description Validate price/stock and create a short-lived local reservation.
     */
    post: operations["preview_shopper_checkout_v1_shopper_checkout_preview_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/conversations": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Shopper Conversations */
    get: operations["list_shopper_conversations_v1_shopper_conversations_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/conversations/{conversation_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Shopper Conversation */
    get: operations["get_shopper_conversation_v1_shopper_conversations__conversation_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/discovery": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Shopper Discovery
     * @description Return starter prompts grounded in the manager's active catalog.
     */
    get: operations["get_shopper_discovery_v1_shopper_discovery_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Shopper Account */
    get: operations["get_shopper_account_v1_shopper_me_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/memories": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Shopper Memories */
    get: operations["list_shopper_memories_v1_shopper_memories_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/memories/{memory_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete Shopper Memory */
    delete: operations["delete_shopper_memory_v1_shopper_memories__memory_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/orders": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Shopper Orders */
    get: operations["shopper_orders_v1_shopper_orders_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/preferences": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /** Set Preferences */
    patch: operations["set_preferences_v1_shopper_preferences_patch"];
    trace?: never;
  };
  "/v1/shopper/product-selections": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Record Product Selection */
    post: operations["record_product_selection_v1_shopper_product_selections_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/shopping-data": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete Shopping Data */
    delete: operations["delete_shopping_data_v1_shopper_shopping_data_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/shopper/store": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Storefront */
    get: operations["get_storefront_v1_shopper_store_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Create Simulator Instance Alias
     * @description Create a simulator instance through the contract root route.
     */
    post: operations["create_simulator_instance_alias_v1_simulator_instances_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Simulator Instance Alias
     * @description Return simulator instance state through the contract root route.
     */
    get: operations["get_simulator_instance_alias_v1_simulator_instances__instance_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}/advance": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Advance Simulator Instance
     * @description Advance simulator virtual time by hours.
     */
    post: operations["advance_simulator_instance_v1_simulator_instances__instance_id__advance_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}/compare-baseline": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Compare Simulator Baseline
     * @description Compare current simulator outcomes with a no-intervention baseline.
     */
    get: operations["compare_simulator_baseline_v1_simulator_instances__instance_id__compare_baseline_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}/metrics": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Simulator Metrics
     * @description Return simulator metrics.
     */
    get: operations["get_simulator_metrics_v1_simulator_instances__instance_id__metrics_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}/reset": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reset Simulator Instance
     * @description Reset a simulator instance to its scenario start.
     */
    post: operations["reset_simulator_instance_v1_simulator_instances__instance_id__reset_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}/run-until": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Run Simulator Until
     * @description Run simulator virtual time until a timestamp.
     */
    post: operations["run_simulator_until_v1_simulator_instances__instance_id__run_until_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/instances/{instance_id}/state": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Simulator State
     * @description Return simulator instance state.
     */
    get: operations["get_simulator_state_v1_simulator_instances__instance_id__state_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/scenarios": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Simulator Scenarios
     * @description List available deterministic simulator scenarios.
     */
    get: operations["list_simulator_scenarios_v1_simulator_scenarios_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/simulator/scenarios/{scenario_id}/instances": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Create Simulator Instance
     * @description Create a tenant-scoped simulator instance.
     */
    post: operations["create_simulator_instance_v1_simulator_scenarios__scenario_id__instances_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/v1/stores/{slug}/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Exchange Preview */
    post: operations["exchange_preview_v1_stores__slug__preview_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /**
     * ActionApprovalRequest
     * @description Approve or reject an action bound to its current version hash.
     */
    ActionApprovalRequest: {
      /** Action Version Hash */
      action_version_hash: string;
      /**
       * Actor Id
       * @default local-operator
       */
      actor_id?: string;
      /** Comment */
      comment?: string | null;
    };
    /**
     * ActionAuditEntry
     * @description Controller-local action audit entry.
     */
    ActionAuditEntry: {
      /**
       * Action Id
       * Format: uuid
       */
      action_id: string;
      actor_role: components["schemas"]["ActorRole"];
      /** Details */
      details?: {
        [key: string]: unknown;
      };
      /** Event Type */
      event_type: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Message */
      message: string;
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * ActionAuditResponse
     * @description Action audit response.
     */
    ActionAuditResponse: {
      /**
       * Action Id
       * Format: uuid
       */
      action_id: string;
      /** Items */
      items: components["schemas"]["ActionAuditEntry"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * ActionListResponse
     * @description Action list response.
     */
    ActionListResponse: {
      /** Items */
      items: components["schemas"]["ControllerActionRecord"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * ActionStatus
     * @enum {string}
     */
    ActionStatus:
      | "draft"
      | "compiled"
      | "denied"
      | "awaiting_approval"
      | "approved"
      | "executable"
      | "executing"
      | "succeeded"
      | "failed"
      | "uncertain"
      | "evaluating"
      | "completed"
      | "rollback_proposed"
      | "rolling_back"
      | "rolled_back"
      | "rollback_failed"
      | "expired"
      | "cancelled";
    /**
     * ActionType
     * @enum {string}
     */
    ActionType:
      | "create_discount"
      | "disable_discount"
      | "set_variant_price"
      | "set_search_boost"
      | "set_recommendation_policy"
      | "set_campaign_budget"
      | "no_op";
    /** ActivityCheck */
    ActivityCheck: {
      /**
       * Checked At
       * Format: date-time
       */
      checked_at: string;
      /**
       * Sample Count
       * @default 0
       */
      sample_count?: number;
      /**
       * State
       * @enum {string}
       */
      state: "ok" | "alert" | "insufficient_data" | "paused" | "log_only" | "pending";
      /**
       * Truncated
       * @default false
       */
      truncated?: boolean;
      /** Value */
      value?: number | null;
    };
    /** ActivityEvent */
    ActivityEvent: {
      /** Duration Ms */
      duration_ms: number;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      kind: components["schemas"]["ActivityKind"];
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
      /** Result Count */
      result_count?: number | null;
      /**
       * Status
       * @enum {string}
       */
      status: "ok" | "error" | "fallback";
    };
    /**
     * ActivityKind
     * @enum {string}
     */
    ActivityKind:
      | "chat"
      | "search"
      | "memory_save"
      | "catalog_browse"
      | "product_select"
      | "cart_add"
      | "cart_change"
      | "checkout_preview"
      | "checkout_confirm";
    /** ActivityOverview */
    ActivityOverview: {
      /** Available Fields */
      available_fields?: string[];
      /** Available Kinds */
      available_kinds?: components["schemas"]["ActivityKind"][];
      /**
       * Checked At
       * Format: date-time
       */
      checked_at: string;
      /**
       * Event Limit
       * @default 100
       */
      event_limit?: number;
      /** Events */
      events: components["schemas"]["ActivityEvent"][];
      /**
       * Limitation
       * @default Operational events only; no chat text, queries, account identifiers or preference contents. Ad-hoc views use these fields, not arbitrary new tracking. Test checkout events do not represent real revenue. Monitors report in-app, not external alerts.
       */
      limitation?: string;
      /** Observed Counts */
      observed_counts: {
        [key: string]: number;
      };
      /**
       * Retention Days
       * @default 30
       */
      retention_days?: number;
      /** Rules */
      rules: components["schemas"]["ActivityRule"][];
      /**
       * Scope
       * @enum {string}
       */
      scope: "my_activity" | "store_activity";
    };
    /** ActivityQuery */
    ActivityQuery: {
      /**
       * Empty Results Only
       * @default false
       */
      empty_results_only?: boolean;
      /**
       * Include Test Sessions
       * @default false
       */
      include_test_sessions?: boolean;
      kind?: components["schemas"]["ActivityKind"] | null;
      /** Status */
      status?: ("ok" | "error" | "fallback") | null;
      /**
       * Window Minutes
       * @default 1440
       */
      window_minutes?: number;
    };
    /** ActivityRule */
    ActivityRule: {
      check: components["schemas"]["ActivityCheck"];
      definition: components["schemas"]["ActivityRuleInput"];
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Next Check At */
      next_check_at?: string | null;
    };
    /** ActivityRuleInput */
    ActivityRuleInput: {
      /**
       * Enabled
       * @default true
       */
      enabled?: boolean;
      /**
       * Interval Minutes
       * @default 5
       */
      interval_minutes?: number;
      /**
       * Metric
       * @default count
       * @enum {string}
       */
      metric?: "count" | "error_rate" | "empty_result_rate" | "p95_duration_ms";
      /**
       * Minimum Samples
       * @default 5
       */
      minimum_samples?: number;
      /** Name */
      name: string;
      query?: components["schemas"]["ActivityQuery"];
      /** Threshold */
      threshold?: number | null;
    };
    /**
     * ActorRef
     * @description Actor that initiated a domain event or decision.
     */
    ActorRef: {
      /** Id */
      id: string;
      /** Roles */
      roles?: string[];
      /** Type */
      type: string;
    };
    /**
     * ActorRole
     * @enum {string}
     */
    ActorRole: "viewer" | "operator" | "owner" | "admin" | "system";
    /**
     * AdvanceSimulatorRequest
     * @description Advance a simulator instance by virtual hours.
     */
    AdvanceSimulatorRequest: {
      /**
       * Hours
       * @default 24
       */
      hours?: number;
    };
    /**
     * AgentStep
     * @description A safe stage summary, never hidden model chain-of-thought.
     */
    AgentStep: {
      /** Detail */
      detail: string;
      /**
       * Stage
       * @enum {string}
       */
      stage: "recall" | "understand" | "act" | "observe" | "respond";
      /**
       * Status
       * @default completed
       * @enum {string}
       */
      status?: "completed" | "simulated" | "needs_input" | "failed";
      /** Title */
      title: string;
      /** Tool */
      tool?: string | null;
    };
    /** AIConnection */
    AIConnection: {
      /** Configured */
      configured: boolean;
      /** Connected */
      connected: boolean;
      /** Detail */
      detail: string;
    };
    /**
     * ApiError
     * @description Stable redacted API error body.
     */
    ApiError: {
      /** Code */
      code: string;
      /** Details */
      details?: {
        [key: string]: unknown;
      };
      /** Message */
      message: string;
      /** Request Id */
      request_id: string;
      /**
       * Retryable
       * @default false
       */
      retryable?: boolean;
      /**
       * Type
       * @enum {string}
       */
      type:
        | "validation_error"
        | "authentication_error"
        | "authorization_error"
        | "not_found"
        | "conflict"
        | "precondition_failed"
        | "policy_denied"
        | "provider_error"
        | "rate_limited"
        | "temporarily_unavailable"
        | "internal_error";
    };
    /**
     * Approval
     * @description Human decision bound to an approval request and action hash.
     */
    Approval: {
      /** Action Version Hash */
      action_version_hash: string;
      actor: components["schemas"]["ActorRef"];
      /** Comment */
      comment?: string | null;
      /**
       * Decided At
       * Format: date-time
       */
      decided_at: string;
      /** Decision */
      decision: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Request Id
       * Format: uuid
       */
      request_id: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * ApprovalRequest
     * @description Approval request bound to an exact action version hash.
     */
    ApprovalRequest: {
      /**
       * Action Id
       * Format: uuid
       */
      action_id: string;
      /** Action Version Hash */
      action_version_hash: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Required Roles */
      required_roles: components["schemas"]["ActorRole"][];
      /** Status */
      status: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * AuditFeedEntry
     * @description Redacted audit feed item.
     */
    AuditFeedEntry: {
      /**
       * Action Id
       * Format: uuid
       */
      action_id: string;
      /** Actor Role */
      actor_role: string;
      /** Details */
      details: {
        [key: string]: unknown;
      };
      /** Event Type */
      event_type: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Message */
      message: string;
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
    };
    /**
     * AuditFeedResponse
     * @description Tenant audit feed cursor page.
     */
    AuditFeedResponse: {
      /** Items */
      items: components["schemas"]["AuditFeedEntry"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * AutonomyMode
     * @enum {string}
     */
    AutonomyMode: "demo" | "shadow" | "approval_required" | "bounded_auto";
    /**
     * AutonomyPolicy
     * @description Goal-level autonomy policy with per-action overrides.
     */
    AutonomyPolicy: {
      /** @default approval_required */
      default_mode?: components["schemas"]["AutonomyMode"];
      /** Per Action */
      per_action?: {
        [key: string]: components["schemas"]["AutonomyMode"];
      };
    };
    /**
     * BaselineComparisonResponse
     * @description Current scenario outcome compared with a no-intervention baseline.
     */
    BaselineComparisonResponse: {
      baseline: components["schemas"]["MetricTotals"];
      /** Baseline Hash */
      baseline_hash: string;
      current: components["schemas"]["MetricTotals"];
      delta: components["schemas"]["MetricTotals"];
      /**
       * Instance Id
       * Format: uuid
       */
      instance_id: string;
      /**
       * Scenario Id
       * @enum {string}
       */
      scenario_id: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /** Scenario Version */
      scenario_version: string;
      /** Seed */
      seed: number;
    };
    /**
     * BudgetReservationRequest
     * @description Budget capacity requested by a compiled action.
     */
    BudgetReservationRequest: {
      amount: components["schemas"]["Money"];
      /** Budget Kind */
      budget_kind: string;
      /** Operation Id */
      operation_id: string;
    };
    /**
     * BudgetSpec
     * @description Budget allocated to a goal.
     */
    BudgetSpec: {
      amount: components["schemas"]["Money"];
      /** Kind */
      kind: string;
      period?: components["schemas"]["TimeWindow"] | null;
    };
    /**
     * CampaignSummary
     * @description Compact campaign status.
     */
    CampaignSummary: {
      /** Active */
      active: boolean;
      /** Channel Id */
      channel_id: string;
      /** Daily Budget Minor */
      daily_budget_minor: number;
      /** Id */
      id: string;
      /** Name */
      name: string;
    };
    /**
     * CapabilitiesResponse
     * @description Release-facing capability and context summary.
     */
    CapabilitiesResponse: {
      /** Actor Id */
      actor_id: string;
      /**
       * Api Version
       * @default v1
       * @constant
       */
      api_version?: "v1";
      /** Capabilities */
      capabilities: components["schemas"]["CapabilitySummary"][];
      default_autonomy: components["schemas"]["AutonomyMode"];
      /** Limitations */
      limitations: string[];
      /**
       * Mode
       * @default local_demo
       * @enum {string}
       */
      mode?: "local_demo" | "self_hosted";
      /** Roles */
      roles: string[];
      /** Supported Action Types */
      supported_action_types: components["schemas"]["ActionType"][];
      /** Supported Scenarios */
      supported_scenarios: ("acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1")[];
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * Capability
     * @enum {string}
     */
    Capability:
      | "read_catalog"
      | "write_product_content"
      | "write_price"
      | "read_inventory"
      | "write_inventory"
      | "read_orders"
      | "read_customer_cohorts"
      | "read_discounts"
      | "write_discounts"
      | "read_behavior_events"
      | "write_merchandising"
      | "read_campaigns"
      | "write_campaign_budget"
      | "write_campaign_status";
    /**
     * CapabilitySummary
     * @description Local-demo capability exposed to the UI.
     */
    CapabilitySummary: {
      /** Detail */
      detail: string;
      /** Key */
      key: string;
      /** Label */
      label: string;
      /**
       * Status
       * @enum {string}
       */
      status: "available" | "disabled" | "teaser";
    };
    /** Cart */
    Cart: {
      /** Id */
      id?: string | null;
      /**
       * Item Count
       * @default 0
       */
      item_count?: number;
      /** Lines */
      lines?: components["schemas"]["CartLine"][];
      /**
       * Status
       * @default open
       * @enum {string}
       */
      status?: "open" | "converted" | "abandoned";
      subtotal?: components["schemas"]["Money"];
      total?: components["schemas"]["Money"];
      /** Updated At */
      updated_at?: string | null;
      /**
       * Version
       * @default 0
       */
      version?: number;
    };
    /** CartChoiceLine */
    CartChoiceLine: {
      /** Quantity */
      quantity: number;
      /** Title */
      title: string;
      /** Variant Title */
      variant_title: string;
    };
    /** CartItemAddRequest */
    CartItemAddRequest: {
      /** Product Id */
      product_id: string;
      /**
       * Quantity
       * @default 1
       */
      quantity?: number;
      /** Variant Id */
      variant_id?: string | null;
    };
    /** CartItemUpdateRequest */
    CartItemUpdateRequest: {
      /** Quantity */
      quantity: number;
    };
    /** CartLine */
    CartLine: {
      /** Available Quantity */
      available_quantity?: number | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Image Url */
      image_url?: string | null;
      line_total: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Quantity */
      quantity: number;
      /** Sellable Quantity */
      sellable_quantity?: number | null;
      /** Title */
      title: string;
      unit_price: components["schemas"]["Money"];
      /** Variant Id */
      variant_id: string;
      /** Variant Title */
      variant_title: string;
    };
    /** CatalogBrowseProduct */
    CatalogBrowseProduct: {
      /**
       * Availability
       * @enum {string}
       */
      availability: "available" | "out_of_stock" | "unknown";
      /** Brand */
      brand: string | null;
      /** Category */
      category: string;
      /** Description */
      description: string;
      /** Image Url */
      image_url: string | null;
      price: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Provenance */
      provenance: string | null;
      /** Title */
      title: string;
      /** Variant Id */
      variant_id: string;
      /** Variants */
      variants?: components["schemas"]["CatalogVariant"][];
    };
    /** CatalogBrowseResponse */
    CatalogBrowseResponse: {
      catalog: components["schemas"]["PublishedCatalog"] | null;
      /** Categories */
      categories: string[];
      indexing: components["schemas"]["CatalogIndexStatus"];
      /** Items */
      items: components["schemas"]["CatalogBrowseProduct"][];
      /** Limit */
      limit: number;
      /** Offset */
      offset: number;
      /** Total */
      total: number;
    };
    /** CatalogConnection */
    CatalogConnection: {
      /** Configured */
      configured: boolean;
      /** Connected */
      connected: boolean;
      /** Detail */
      detail: string;
      /**
       * Provider
       * @default shopify
       */
      provider?: string;
      /** Shop */
      shop?: string | null;
    };
    /** CatalogIndexStatus */
    CatalogIndexStatus: {
      /** Catalog Id */
      catalog_id?: string | null;
      /** Completed At */
      completed_at?: string | null;
      /** Created At */
      created_at?: string | null;
      /** Error Code */
      error_code?: string | null;
      /** Filename */
      filename?: string | null;
      /**
       * Indexed Product Count
       * @default 0
       */
      indexed_product_count?: number;
      /** Job Id */
      job_id?: string | null;
      /**
       * Product Count
       * @default 0
       */
      product_count?: number;
      /** Serving Catalog Id */
      serving_catalog_id?: string | null;
      /**
       * Serving Product Count
       * @default 0
       */
      serving_product_count?: number;
      /** Source Version */
      source_version?: string | null;
      /**
       * Status
       * @default not_configured
       * @enum {string}
       */
      status?: "not_configured" | "queued" | "running" | "ready" | "failed";
      /** Updated At */
      updated_at?: string | null;
    };
    /** CatalogProductInput */
    CatalogProductInput: {
      /** Attributes */
      attributes?: {
        [key: string]: string | number | boolean | string[];
      };
      /** Brand */
      brand?: string | null;
      /** Category Path */
      category_path?: string[];
      /**
       * Description Text
       * @default
       */
      description_text?: string;
      /** Primary Image Url */
      primary_image_url?: string | null;
      /** Source Product Id */
      source_product_id: string;
      /**
       * Source Updated At
       * Format: date-time
       */
      source_updated_at: string;
      /** Tags */
      tags?: string[];
      /** Title */
      title: string;
      /** Variants */
      variants: components["schemas"]["CatalogVariantInput"][];
    };
    /** CatalogSelection */
    CatalogSelection: {
      /**
       * Catalog Id
       * Format: uuid
       */
      catalog_id: string;
    };
    /**
     * CatalogSummary
     * @description Compact catalog status for APIs and CLI.
     */
    CatalogSummary: {
      /** Cold Start Products */
      cold_start_products: number;
      /** Excess Inventory Products */
      excess_inventory_products: number;
      /** Inventory Units */
      inventory_units: number;
      /** Low Stock Products */
      low_stock_products: number;
      /** Product Count */
      product_count: number;
      /** Variant Count */
      variant_count: number;
    };
    /** CatalogVariant */
    CatalogVariant: {
      /**
       * Availability
       * @default unknown
       * @enum {string}
       */
      availability?: "available" | "out_of_stock" | "unknown";
      /** Available */
      available: boolean;
      /** Id */
      id: string;
      /** Options */
      options: {
        [key: string]: string | number | boolean | string[];
      };
      price: components["schemas"]["Money"];
      /** Title */
      title: string;
    };
    /** CatalogVariantInput */
    CatalogVariantInput: {
      /** Available */
      available: boolean;
      /** Currency */
      currency: string;
      /** Inventory Quantity */
      inventory_quantity?: number | null;
      /** Option Values */
      option_values?: {
        [key: string]: string;
      };
      /** Price Minor */
      price_minor: number;
      /** Sku */
      sku?: string | null;
      /** Source Variant Id */
      source_variant_id: string;
      /** Title */
      title: string;
    };
    /** CheckoutConfirmation */
    CheckoutConfirmation: {
      /**
       * Checkout Id
       * Format: uuid
       */
      checkout_id: string;
      /** Failure Code */
      failure_code?: string | null;
      /** Message */
      message: string;
      order?: components["schemas"]["OrderSummary"] | null;
      /**
       * Status
       * @enum {string}
       */
      status:
        | "requires_confirmation"
        | "processing"
        | "requires_payment_method"
        | "succeeded"
        | "cancelled";
    };
    /** CheckoutConfirmRequest */
    CheckoutConfirmRequest: {
      /**
       * Checkout Id
       * Format: uuid
       */
      checkout_id: string;
      /**
       * Payment Method
       * @enum {string}
       */
      payment_method: "test_success" | "test_decline";
    };
    /** CheckoutLine */
    CheckoutLine: {
      line_total: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Quantity */
      quantity: number;
      /** Title */
      title: string;
      unit_price: components["schemas"]["Money"];
      /** Variant Id */
      variant_id: string;
    };
    /** CheckoutPreview */
    CheckoutPreview: {
      /**
       * Cart Id
       * Format: uuid
       */
      cart_id: string;
      /** Cart Version */
      cart_version: number;
      /**
       * Checkout Id
       * Format: uuid
       */
      checkout_id: string;
      /** Lines */
      lines: components["schemas"]["CheckoutLine"][];
      /**
       * Payment Mode
       * @default local_test
       * @constant
       */
      payment_mode?: "local_test";
      policy: components["schemas"]["CommercePolicyDecision"];
      /**
       * Reservation Expires At
       * Format: date-time
       */
      reservation_expires_at: string;
      /**
       * Status
       * @enum {string}
       */
      status:
        | "requires_confirmation"
        | "processing"
        | "requires_payment_method"
        | "succeeded"
        | "cancelled";
      subtotal: components["schemas"]["Money"];
      total: components["schemas"]["Money"];
    };
    /** CheckoutPreviewRequest */
    CheckoutPreviewRequest: {
      /** Cart Version */
      cart_version: number;
    };
    /** CheckoutRecovery */
    CheckoutRecovery: {
      /**
       * Checkout Id
       * Format: uuid
       */
      checkout_id: string;
      confirmation?: components["schemas"]["CheckoutConfirmation"] | null;
      /** Message */
      message: string;
      preview?: components["schemas"]["CheckoutPreview"] | null;
      /**
       * Status
       * @enum {string}
       */
      status:
        | "requires_confirmation"
        | "processing"
        | "requires_payment_method"
        | "succeeded"
        | "cancelled"
        | "expired";
    };
    /** CommerceInventoryItem */
    CommerceInventoryItem: {
      /** Image Url */
      image_url?: string | null;
      /** Observed At */
      observed_at?: string | null;
      /** Observed Quantity */
      observed_quantity?: number | null;
      /** Product Id */
      product_id: string;
      /**
       * Reserved Quantity
       * @default 0
       */
      reserved_quantity?: number;
      /** Sellable Quantity */
      sellable_quantity?: number | null;
      /** Sku */
      sku?: string | null;
      /**
       * State
       * @enum {string}
       */
      state: "healthy" | "low" | "out" | "unknown";
      /** Title */
      title: string;
      /** Variant Id */
      variant_id: string;
      /** Variant Title */
      variant_title: string;
    };
    /** CommerceOverview */
    CommerceOverview: {
      /**
       * Generated At
       * Format: date-time
       */
      generated_at: string;
      /** Inventory */
      inventory: components["schemas"]["CommerceInventoryItem"][];
      /**
       * Inventory Writes Enabled
       * @default false
       * @constant
       */
      inventory_writes_enabled?: false;
      /** Orders */
      orders: components["schemas"]["OrderSummary"][];
      /**
       * Payment Mode
       * @default local_test
       * @constant
       */
      payment_mode?: "local_test";
      /** Payments */
      payments: components["schemas"]["PaymentAttemptSummary"][];
      /** Reservations */
      reservations: components["schemas"]["ReservationSummary"][];
    };
    /** CommercePolicyDecision */
    CommercePolicyDecision: {
      /** Allowed */
      allowed: boolean;
      /** Code */
      code: string;
      /** Preconditions */
      preconditions?: string[];
      /** Reason */
      reason: string;
      /** Rollback Strategy */
      rollback_strategy: string;
    };
    /**
     * CompiledAction
     * @description Action intent resolved against current authoritative state.
     */
    CompiledAction: {
      /** Budget Reservations */
      budget_reservations: components["schemas"]["BudgetReservationRequest"][];
      estimated_cost: components["schemas"]["Money"];
      expected_impact: components["schemas"]["ImpactEstimate"];
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /**
       * Goal Id
       * Format: uuid
       */
      goal_id: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Idempotency Key */
      idempotency_key: string;
      /** Intent */
      intent:
        | components["schemas"]["CreateDiscountIntent"]
        | components["schemas"]["DisableDiscountIntent"]
        | components["schemas"]["SetVariantPriceIntent"]
        | components["schemas"]["SetSearchBoostIntent"]
        | components["schemas"]["SetRecommendationPolicyIntent"]
        | components["schemas"]["SetCampaignBudgetIntent"]
        | components["schemas"]["NoOpIntent"];
      /** Normalized Parameters */
      normalized_parameters: {
        [key: string]: unknown;
      };
      /** Preconditions */
      preconditions: components["schemas"]["Precondition"][];
      risk?: components["schemas"]["RiskAssessment"];
      rollback_plan: components["schemas"]["RollbackPlan"];
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /** @default compiled */
      status?: components["schemas"]["ActionStatus"];
      target_provider: components["schemas"]["ProviderRef"];
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * ConfidenceInterval
     * @description Numeric interval for impact estimates and observed metrics.
     */
    ConfidenceInterval: {
      /** Level */
      level: string;
      /** Lower */
      lower: string;
      /** Point */
      point: string;
      /** Upper */
      upper: string;
    };
    /**
     * ConstraintOperator
     * @enum {string}
     */
    ConstraintOperator: "lt" | "lte" | "eq" | "gte" | "gt";
    /**
     * ConstraintSpec
     * @description Typed metric constraint with a finite operator.
     */
    "ConstraintSpec-Input": {
      /**
       * Hard
       * @default true
       */
      hard?: boolean;
      metric: components["schemas"]["MetricName"];
      operator: components["schemas"]["ConstraintOperator"];
      /** Value */
      value: number | string | components["schemas"]["Money"];
    };
    /**
     * ConstraintSpec
     * @description Typed metric constraint with a finite operator.
     */
    "ConstraintSpec-Output": {
      /**
       * Hard
       * @default true
       */
      hard?: boolean;
      metric: components["schemas"]["MetricName"];
      operator: components["schemas"]["ConstraintOperator"];
      /** Value */
      value: string | components["schemas"]["Money"];
    };
    /** ContinuityResponse */
    ContinuityResponse: {
      account: components["schemas"]["ShopperAccount"];
      /**
       * Account Cart Items
       * @default 0
       */
      account_cart_items?: number;
      /** Account Cart Lines */
      account_cart_lines?: components["schemas"]["CartChoiceLine"][];
      /**
       * Guest Cart Items
       * @default 0
       */
      guest_cart_items?: number;
      /** Guest Cart Lines */
      guest_cart_lines?: components["schemas"]["CartChoiceLine"][];
      /** Merge Token */
      merge_token?: string | null;
      /** Recovery Code */
      recovery_code?: string | null;
    };
    /**
     * ControllerActionRecord
     * @description Stored action proposal and execution state.
     */
    ControllerActionRecord: {
      action: components["schemas"]["CompiledAction"];
      /** Action Version Hash */
      action_version_hash: string;
      approval?: components["schemas"]["Approval"] | null;
      /** Approval Policy Version */
      approval_policy_version?: number | null;
      approval_request?: components["schemas"]["ApprovalRequest"] | null;
      /** Audit */
      audit?: components["schemas"]["ActionAuditEntry"][];
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      execution_result?: components["schemas"]["ProviderResult"] | null;
      measurement?: components["schemas"]["MeasurementSchedule"] | null;
      outcome?: components["schemas"]["MeasurementOutcome"] | null;
      policy_decision: components["schemas"]["PolicyDecision"];
      /**
       * Policy Version
       * @default 1
       */
      policy_version?: number;
      reconciliation?: components["schemas"]["ReconciliationResult"] | null;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /**
     * ControllerGraphResponse
     * @description Documented controller graph and effect boundary.
     */
    ControllerGraphResponse: {
      /** Nodes */
      nodes: (
        | "load_goal_and_policy"
        | "acquire_run_lock"
        | "build_snapshot"
        | "detect_opportunities"
        | "generate_hypotheses"
        | "generate_action_intents"
        | "compile_actions"
        | "estimate"
        | "evaluate_policy"
        | "select_portfolio"
        | "persist_proposals"
        | "approval_interrupt"
        | "execute_actions"
        | "reconcile"
        | "schedule_measurement"
        | "summarize"
      )[];
      /**
       * Provider Write Node
       * @enum {string}
       */
      provider_write_node:
        | "load_goal_and_policy"
        | "acquire_run_lock"
        | "build_snapshot"
        | "detect_opportunities"
        | "generate_hypotheses"
        | "generate_action_intents"
        | "compile_actions"
        | "estimate"
        | "evaluate_policy"
        | "select_portfolio"
        | "persist_proposals"
        | "approval_interrupt"
        | "execute_actions"
        | "reconcile"
        | "schedule_measurement"
        | "summarize";
      /** Side Effect Boundaries */
      side_effect_boundaries: {
        [key: string]: unknown;
      };
    };
    /**
     * ControllerPolicyConfig
     * @description Tenant policy controls enforced before every simulator write.
     */
    ControllerPolicyConfig: {
      /** Allowed Action Types */
      allowed_action_types?: components["schemas"]["ActionType"][];
      /** Blocked Provider Resources */
      blocked_provider_resources?: string[];
      /**
       * Campaign Budget Max Change Rate
       * @default 0.25
       */
      campaign_budget_max_change_rate?: string;
      /** @default approval_required */
      default_mode?: components["schemas"]["AutonomyMode"];
      /**
       * Discount Max Percentage
       * @default 0.15
       */
      discount_max_percentage?: string;
      /**
       * Discount Minimum Margin Rate
       * @default 0.25
       */
      discount_minimum_margin_rate?: string;
      /**
       * Kill Switch Enabled
       * @default false
       */
      kill_switch_enabled?: boolean;
      /**
       * Max Actions Per Run
       * @default 5
       */
      max_actions_per_run?: number;
      /**
       * Max Data Age Minutes
       * @default 120
       */
      max_data_age_minutes?: number;
      /**
       * Max Parallel Interventions
       * @default 3
       */
      max_parallel_interventions?: number;
      max_total_estimated_cost?: components["schemas"]["Money"];
      /**
       * Min Action Confidence
       * @default 0.75
       */
      min_action_confidence?: string;
      /**
       * Min Observations For Auto Action
       * @default 500
       */
      min_observations_for_auto_action?: number;
      /** Per Action Modes */
      per_action_modes?: {
        [key: string]: components["schemas"]["AutonomyMode"];
      };
      /**
       * Policy Version
       * @default 1
       */
      policy_version?: number;
      /**
       * Price Max Delta Rate
       * @default 0.10
       */
      price_max_delta_rate?: string;
      /**
       * Search Boost Max Multiplier
       * @default 1.15
       */
      search_boost_max_multiplier?: string;
      /**
       * Search Boost Min Relevance
       * @default 0.55
       */
      search_boost_min_relevance?: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /**
     * ControllerRunRecord
     * @description Stored controller run state.
     */
    ControllerRunRecord: {
      /** Action Ids */
      action_ids?: string[];
      /** Completed At */
      completed_at?: string | null;
      /**
       * Goal Id
       * Format: uuid
       */
      goal_id: string;
      /** Hypotheses */
      hypotheses?: components["schemas"]["Hypothesis"][];
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Intent Drafts */
      intent_drafts?: components["schemas"]["IntentDraft"][];
      /** Next Run At */
      next_run_at?: string | null;
      /** Opportunities */
      opportunities?: components["schemas"]["Opportunity"][];
      /**
       * Simulator Instance Id
       * Format: uuid
       */
      simulator_instance_id: string;
      snapshot?: components["schemas"]["ObservationSnapshot"] | null;
      /**
       * Started At
       * Format: date-time
       */
      started_at: string;
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "awaiting_approval" | "completed" | "cancelled" | "failed";
      /** Summary */
      summary?: {
        [key: string]: unknown;
      };
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /** Trace */
      trace?: components["schemas"]["ControllerTraceEvent"][];
    };
    /**
     * ControllerRunRequest
     * @description Optional run controls for a manual controller run.
     */
    ControllerRunRequest: {
      /**
       * Execute Bounded Auto
       * @default false
       */
      execute_bounded_auto?: boolean;
    };
    /**
     * ControllerTraceEvent
     * @description Ordered public trace event for a controller run.
     */
    ControllerTraceEvent: {
      /** Details */
      details?: {
        [key: string]: unknown;
      };
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Message */
      message: string;
      /**
       * Node
       * @enum {string}
       */
      node:
        | "load_goal_and_policy"
        | "acquire_run_lock"
        | "build_snapshot"
        | "detect_opportunities"
        | "generate_hypotheses"
        | "generate_action_intents"
        | "compile_actions"
        | "estimate"
        | "evaluate_policy"
        | "select_portfolio"
        | "persist_proposals"
        | "approval_interrupt"
        | "execute_actions"
        | "reconcile"
        | "schedule_measurement"
        | "summarize";
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /** Sequence */
      sequence: number;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * CreateDiscountIntent
     * @description Intent to create a bounded discount.
     */
    CreateDiscountIntent: {
      /** Code */
      code?: string | null;
      customer_scope: components["schemas"]["CustomerScope"];
      /**
       * Discount Kind
       * @enum {string}
       */
      discount_kind: "percentage" | "fixed_amount";
      /**
       * Ends At
       * Format: date-time
       */
      ends_at: string;
      /** Maximum Cost Minor */
      maximum_cost_minor?: number | null;
      /** Minimum Subtotal Minor */
      minimum_subtotal_minor?: number | null;
      /** Opportunity Ids */
      opportunity_ids: string[];
      product_scope: components["schemas"]["ProductScope"];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * Starts At
       * Format: date-time
       */
      starts_at: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "create_discount";
      /** Value */
      value: string;
    };
    /**
     * CreateSimulatorInstanceAliasRequest
     * @description Create a simulator instance through the contract root route.
     */
    CreateSimulatorInstanceAliasRequest: {
      /**
       * Scenario Id
       * @default acquisition_v1
       * @enum {string}
       */
      scenario_id?: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /** Seed */
      seed?: number | null;
    };
    /**
     * CreateSimulatorInstanceRequest
     * @description Create a simulator instance from a scenario.
     */
    CreateSimulatorInstanceRequest: {
      /** Seed */
      seed?: number | null;
    };
    /**
     * CustomerScope
     * @description Coarse customer targeting scope without PII.
     */
    CustomerScope: {
      /**
       * New Customers Only
       * @default false
       */
      new_customers_only?: boolean;
      /**
       * Segment
       * @default all
       */
      segment?: string;
    };
    /**
     * DailyMetrics
     * @description Materialized simulator metrics for one virtual day.
     */
    DailyMetrics: {
      /** Ad Spend Minor */
      ad_spend_minor: number;
      /** Cac Minor */
      cac_minor: number | null;
      /** Carts */
      carts: number;
      /** Clicks */
      clicks: number;
      /** Cogs Minor */
      cogs_minor: number;
      /** Contribution Margin Rate */
      contribution_margin_rate: string;
      /** Contribution Profit Minor */
      contribution_profit_minor: number;
      /** Conversion Rate */
      conversion_rate: string;
      /** Day Index */
      day_index: number;
      /** Discount Rate */
      discount_rate: string;
      /** Discounts Minor */
      discounts_minor: number;
      /** Ending Inventory Units */
      ending_inventory_units: number;
      /** Gross Revenue Minor */
      gross_revenue_minor: number;
      /** Impressions */
      impressions: number;
      /**
       * Is History
       * @default false
       */
      is_history?: boolean;
      /**
       * Metric Date
       * Format: date
       */
      metric_date: string;
      /** New Customers */
      new_customers: number;
      /** Orders */
      orders: number;
      /** Search Attributed Purchases */
      search_attributed_purchases: number;
      /** Sessions */
      sessions: number;
      /** Units Sold */
      units_sold: number;
      /** Variable Fees Minor */
      variable_fees_minor: number;
    };
    /**
     * DatasetProfile
     * @description Safe structural facts retained after transient CSV validation.
     */
    DatasetProfile: {
      /** Byte Count */
      byte_count: number;
      /** Columns */
      columns: string[];
      /** Content Sha256 */
      content_sha256: string;
      /**
       * Dataset Kind
       * @enum {string}
       */
      dataset_kind: "catalog" | "engagement";
      /** Detected Mappings */
      detected_mappings?: {
        [key: string]: string;
      };
      /** Filename */
      filename: string;
      /** Missing Required */
      missing_required?: string[];
      /**
       * Profiled At
       * Format: date-time
       */
      profiled_at: string;
      /** Row Count */
      row_count: number;
      /** Warnings */
      warnings?: string[];
    };
    /**
     * DataSourceDraft
     * @description Non-secret source configuration collected during onboarding.
     */
    DataSourceDraft: {
      /** Account Identifier */
      account_identifier?: string | null;
      /**
       * Connection Test Status
       * @default not_run
       * @constant
       */
      connection_test_status?: "not_run";
      /**
       * Credential Status
       * @default not_configured
       * @constant
       */
      credential_status?: "not_configured";
      /** Database */
      database?: string | null;
      /**
       * Dataset Kind
       * @enum {string}
       */
      dataset_kind: "catalog" | "engagement";
      /** Display Name */
      display_name?: string | null;
      /** Mapping Document Name */
      mapping_document_name?: string | null;
      /** Object Uri */
      object_uri?: string | null;
      profile?: components["schemas"]["DatasetProfile"] | null;
      /** Relation */
      relation?: string | null;
      /** Role */
      role?: string | null;
      /** Schema Name */
      schema_name?: string | null;
      /**
       * Source Kind
       * @enum {string}
       */
      source_kind: "csv_upload" | "snowflake" | "object_storage";
      /** Warehouse */
      warehouse?: string | null;
    };
    /**
     * DependencyStatus
     * @description Readiness status for one external dependency.
     * @example {
     *       "name": "postgres",
     *       "ok": true
     *     }
     */
    DependencyStatus: {
      /** Detail */
      detail?: string | null;
      /** Latency Ms */
      latency_ms?: number | null;
      /** Name */
      name: string;
      /** Ok */
      ok: boolean;
    };
    /**
     * DisableDiscountIntent
     * @description Intent to disable an existing discount.
     */
    DisableDiscountIntent: {
      /** Opportunity Ids */
      opportunity_ids: string[];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Provider Discount Id */
      provider_discount_id: string;
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "disable_discount";
    };
    /**
     * DiscoveryObjectiveDraft
     * @description Finite discovery-model objective assembled across conversation turns.
     */
    DiscoveryObjectiveDraft: {
      /**
       * Minimum Relevance
       * @default 0.45
       */
      minimum_relevance?: string;
      /** Missing Fields */
      missing_fields?: string[];
      /** Popularity Strength */
      popularity_strength?: ("light" | "balanced" | "strong") | null;
      /** Ranking Signals */
      ranking_signals?: ("relevance" | "popularity" | "quality")[];
      /** Recommendation Strategy */
      recommendation_strategy?: ("similar" | "popular" | "complements") | null;
      /** Retrieval Mode */
      retrieval_mode?: ("lexical" | "semantic" | "hybrid") | null;
      /** Review Hash */
      review_hash?: string | null;
      /**
       * Status
       * @default collecting
       * @enum {string}
       */
      status?: "collecting" | "needs_clarification" | "ready_for_review";
      /** Surface */
      surface?: ("search" | "recommendations" | "both") | null;
    };
    /** EngagementSummary */
    EngagementSummary: {
      /**
       * End At
       * Format: date-time
       */
      end_at: string;
      /** Event Count */
      event_count: number;
      /** Event Counts */
      event_counts: {
        [key: string]: number;
      };
      /** Fingerprint */
      fingerprint: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Product Count */
      product_count: number;
      /** Session Count */
      session_count: number;
      /**
       * Start At
       * Format: date-time
       */
      start_at: string;
    };
    /**
     * ErrorEnvelope
     * @description Common public error envelope.
     */
    ErrorEnvelope: {
      error: components["schemas"]["ApiError"];
    };
    /**
     * EvaluateSearchRequest
     * @description Request to evaluate an existing result set.
     */
    EvaluateSearchRequest: {
      filters?: components["schemas"]["ProductFilters"] | null;
      /** Goal Context Id */
      goal_context_id?: string | null;
      /** Query */
      query: string;
      /** Results */
      results: components["schemas"]["RankedCandidate-Input"][];
    };
    /**
     * EvaluationSchedule
     * @description Cadence for goal evaluation.
     */
    EvaluationSchedule: {
      /** Cadence */
      cadence: string;
      /**
       * Timezone
       * @default UTC
       */
      timezone?: string;
    };
    /**
     * EventBatchRequest
     * @description Batch event ingestion request.
     */
    EventBatchRequest: {
      /** Events */
      events: components["schemas"]["SearchEventInput"][];
    };
    /**
     * EventBatchResponse
     * @description Batch event ingestion result.
     */
    EventBatchResponse: {
      /** Accepted */
      accepted: number;
      /** Deduplicated */
      deduplicated: number;
    };
    /**
     * EventType
     * @enum {string}
     */
    EventType:
      | "search_submitted"
      | "product_impression"
      | "product_clicked"
      | "product_viewed"
      | "add_to_cart"
      | "checkout_started"
      | "purchase"
      | "discount_exposed"
      | "discount_redeemed";
    /**
     * EvidenceItem
     * @description Evidence attached to a deterministic controller observation.
     */
    EvidenceItem: {
      /** Key */
      key: string;
      /** Source */
      source: string;
      /** Value */
      value: {
        [key: string]: unknown;
      };
    };
    /**
     * ExecutionStatus
     * @enum {string}
     */
    ExecutionStatus: "pending" | "succeeded" | "failed" | "uncertain" | "reconciled";
    /**
     * GoalAssessment
     * @description Descriptive progress and conservative feasibility, not a causal forecast.
     */
    GoalAssessment: {
      /** Current Value */
      current_value: string | null;
      /**
       * Feasibility
       * @enum {string}
       */
      feasibility: "infeasible" | "not_ruled_out";
      /**
       * Forecast Method
       * @default recent_rate_heuristic_not_calibrated
       * @constant
       */
      forecast_method?: "recent_rate_heuristic_not_calibrated";
      metric: components["schemas"]["MetricName"];
      /** Physical Upper Bound */
      physical_upper_bound: string | null;
      /** Projected Value */
      projected_value: string | null;
      /** Reason Codes */
      reason_codes: string[];
      /**
       * Scope
       * @enum {string}
       */
      scope: "store" | "excess_inventory";
      /** Target Value */
      target_value: string | null;
      /**
       * Trajectory
       * @enum {string}
       */
      trajectory: "achieved" | "on_track" | "at_risk" | "no_target" | "insufficient_data";
    };
    /**
     * GoalCreateRequest
     * @description Create a local-demo goal. Tenant comes from request context.
     */
    "GoalCreateRequest-Input": {
      /** Allowed Action Types */
      allowed_action_types?: components["schemas"]["ActionType"][];
      budget?: components["schemas"]["Money"];
      /** Constraints */
      constraints?: components["schemas"]["ConstraintSpec-Input"][] | null;
      daily_budget?: components["schemas"]["Money"];
      /** @default approval_required */
      default_mode?: components["schemas"]["AutonomyMode"];
      /**
       * Horizon Days
       * @default 30
       */
      horizon_days?: number;
      merchandising?: components["schemas"]["MerchandisingConstraints-Input"] | null;
      /**
       * Name
       * @default Simulator goal
       */
      name?: string;
      objective_direction?: components["schemas"]["ObjectiveDirection"] | null;
      objective_metric?: components["schemas"]["MetricName"] | null;
      /** Objective Scope */
      objective_scope?: ("store" | "excess_inventory") | null;
      /** Per Action Modes */
      per_action_modes?: {
        [key: string]: components["schemas"]["AutonomyMode"];
      };
      /**
       * Planning Mode
       * @default deterministic
       * @enum {string}
       */
      planning_mode?: "deterministic" | "model_backed";
      /** Review Hash */
      review_hash?: string | null;
      /**
       * Scenario Id
       * @default acquisition_v1
       * @enum {string}
       */
      scenario_id?: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /**
       * Seed
       * @default 42
       */
      seed?: number;
      /** Soft Preferences */
      soft_preferences?: string[];
      /** Target Value */
      target_value?: number | string | null;
    };
    /**
     * GoalCreateRequest
     * @description Create a local-demo goal. Tenant comes from request context.
     */
    "GoalCreateRequest-Output": {
      /** Allowed Action Types */
      allowed_action_types?: components["schemas"]["ActionType"][];
      budget?: components["schemas"]["Money"];
      /** Constraints */
      constraints?: components["schemas"]["ConstraintSpec-Output"][] | null;
      daily_budget?: components["schemas"]["Money"];
      /** @default approval_required */
      default_mode?: components["schemas"]["AutonomyMode"];
      /**
       * Horizon Days
       * @default 30
       */
      horizon_days?: number;
      merchandising?: components["schemas"]["MerchandisingConstraints-Output"] | null;
      /**
       * Name
       * @default Simulator goal
       */
      name?: string;
      objective_direction?: components["schemas"]["ObjectiveDirection"] | null;
      objective_metric?: components["schemas"]["MetricName"] | null;
      /** Objective Scope */
      objective_scope?: ("store" | "excess_inventory") | null;
      /** Per Action Modes */
      per_action_modes?: {
        [key: string]: components["schemas"]["AutonomyMode"];
      };
      /**
       * Planning Mode
       * @default deterministic
       * @enum {string}
       */
      planning_mode?: "deterministic" | "model_backed";
      /** Review Hash */
      review_hash?: string | null;
      /**
       * Scenario Id
       * @default acquisition_v1
       * @enum {string}
       */
      scenario_id?: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /**
       * Seed
       * @default 42
       */
      seed?: number;
      /** Soft Preferences */
      soft_preferences?: string[];
      /** Target Value */
      target_value?: string | null;
    };
    /**
     * GoalDraftRequest
     * @description Natural-language goal draft request for local deterministic parsing.
     */
    GoalDraftRequest: {
      /**
       * Planning Mode
       * @default deterministic
       * @enum {string}
       */
      planning_mode?: "deterministic" | "model_backed";
      /**
       * Seed
       * @default 42
       */
      seed?: number;
      /** Text */
      text: string;
    };
    /**
     * GoalDraftResponse
     * @description Structured goal draft plus warnings requiring merchant confirmation.
     */
    GoalDraftResponse: {
      /** Ambiguities */
      ambiguities?: string[];
      draft: components["schemas"]["GoalCreateRequest-Output"] | null;
      /** Inference Ref */
      inference_ref?: string | null;
      /**
       * Interpretation Mode
       * @default deterministic
       * @enum {string}
       */
      interpretation_mode?: "deterministic" | "model_backed" | "replay" | "typed_review";
      /**
       * Status
       * @enum {string}
       */
      status: "ready_for_review" | "clarification_required" | "unsupported";
      /**
       * Template Version
       * @default goal-interpretation-v1
       */
      template_version?: string;
      /** Unsupported Requests */
      unsupported_requests?: string[];
      /** Warnings */
      warnings?: string[];
    };
    /**
     * GoalListResponse
     * @description Goal list response.
     */
    GoalListResponse: {
      /** Items */
      items: components["schemas"]["GoalRecord"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * GoalProgressResponse
     * @description Goal progress summary derived from simulator state and controller actions.
     */
    GoalProgressResponse: {
      assessment?: components["schemas"]["GoalAssessment"] | null;
      /** Current Value */
      current_value: string | null;
      /** Denied Actions */
      denied_actions: number;
      /** Executable Actions */
      executable_actions: number;
      /**
       * Goal Id
       * Format: uuid
       */
      goal_id: string;
      /** Latest Run Id */
      latest_run_id: string | null;
      objective_metric: components["schemas"]["MetricName"];
      /** Pending Approvals */
      pending_approvals: number;
      status: components["schemas"]["GoalStatus"];
      /** Succeeded Actions */
      succeeded_actions: number;
      /** Target Value */
      target_value: string | null;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * GoalRecord
     * @description Stored tenant goal plus simulator binding.
     */
    GoalRecord: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Planning Mode
       * @default deterministic
       * @enum {string}
       */
      planning_mode?: "deterministic" | "model_backed";
      /**
       * Revision
       * @default 1
       */
      revision?: number;
      /**
       * Scenario Id
       * @enum {string}
       */
      scenario_id: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /** Seed */
      seed: number;
      /**
       * Simulator Instance Id
       * Format: uuid
       */
      simulator_instance_id: string;
      /** Soft Preferences */
      soft_preferences?: string[];
      spec: components["schemas"]["GoalSpec"];
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /**
     * GoalSpec
     * @description Canonical merchant goal specification.
     */
    GoalSpec: {
      /** Allowed Action Types */
      allowed_action_types: components["schemas"]["ActionType"][];
      autonomy: components["schemas"]["AutonomyPolicy"];
      /** Budgets */
      budgets: components["schemas"]["BudgetSpec"][];
      /** Constraints */
      constraints: components["schemas"]["ConstraintSpec-Output"][];
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      evaluation_schedule: components["schemas"]["EvaluationSchedule"];
      horizon: components["schemas"]["HorizonSpec"];
      /**
       * Id
       * Format: uuid
       */
      id: string;
      merchandising?: components["schemas"]["MerchandisingConstraints-Output"] | null;
      /** Name */
      name: string;
      objective: components["schemas"]["ObjectiveSpec"];
      status: components["schemas"]["GoalStatus"];
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * GoalStatus
     * @enum {string}
     */
    GoalStatus: "draft" | "active" | "paused" | "archived" | "completed";
    /**
     * GoalUpdateRequest
     * @description Patch a goal's editable local-demo fields.
     */
    GoalUpdateRequest: {
      /** Allowed Action Types */
      allowed_action_types?: components["schemas"]["ActionType"][] | null;
      default_mode?: components["schemas"]["AutonomyMode"] | null;
      /** Expected Revision */
      expected_revision?: number | null;
      /** Name */
      name?: string | null;
      replacement?: components["schemas"]["GoalCreateRequest-Input"] | null;
    };
    /**
     * HorizonSpec
     * @description Goal horizon.
     */
    HorizonSpec: {
      /**
       * End At
       * Format: date-time
       */
      end_at: string;
      /**
       * Start At
       * Format: date-time
       */
      start_at: string;
    };
    /**
     * Hypothesis
     * @description Planner hypothesis derived from opportunities.
     */
    Hypothesis: {
      /** Confidence */
      confidence: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Opportunity Ids */
      opportunity_ids: string[];
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /**
       * Source
       * @default deterministic_planner
       * @constant
       */
      source?: "deterministic_planner";
      /** Statement */
      statement: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * ImpactEstimate
     * @description Conservative deterministic estimate for a compiled action.
     */
    ImpactEstimate: {
      /** Assumptions */
      assumptions?: string[];
      /** Feature Snapshot Ref */
      feature_snapshot_ref?: string | null;
      interval: components["schemas"]["ConfidenceInterval"] | null;
      /** Method */
      method: string;
      /** Metric */
      metric: string;
      /**
       * Out Of Distribution
       * @default false
       */
      out_of_distribution?: boolean;
    };
    /** ImportConfirmRequest */
    ImportConfirmRequest: {
      /** Expected Review Fingerprint */
      expected_review_fingerprint: string;
    };
    /** ImportIssue */
    ImportIssue: {
      /** Message */
      message: string;
      /** Row */
      row: number;
    };
    /** ImportMapping */
    ImportMapping: {
      /** Currency */
      currency?: ("USD" | "EUR" | "GBP" | "CAD" | "AUD") | null;
      /** Mapping */
      mapping?: {
        [key: string]: string;
      };
    };
    /** ImportReview */
    ImportReview: {
      /** Catalog Id */
      catalog_id?: string | null;
      /** Columns */
      columns: string[];
      /** Currency */
      currency: string | null;
      /** Errors */
      errors?: components["schemas"]["ImportIssue"][];
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /** Filename */
      filename: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      indexing?: components["schemas"]["CatalogIndexStatus"] | null;
      /** Mapping */
      mapping: {
        [key: string]: string;
      };
      /**
       * Product Count
       * @default 0
       */
      product_count?: number;
      /** Products */
      products?: components["schemas"]["CatalogProductInput"][];
      /** Review Fingerprint */
      review_fingerprint?: string | null;
      /** Row Count */
      row_count: number;
      /**
       * Sample Data
       * @default false
       */
      sample_data?: boolean;
      /** Status */
      status: string;
      /** Warnings */
      warnings?: string[];
    };
    /**
     * IntentDraft
     * @description Untrusted planner output that must be compiled before policy/execution.
     */
    IntentDraft: {
      action_type: components["schemas"]["ActionType"];
      /** Confidence */
      confidence: string;
      /**
       * Hypothesis Id
       * Format: uuid
       */
      hypothesis_id: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Opportunity Ids */
      opportunity_ids: string[];
      /** Parameters */
      parameters: {
        [key: string]: unknown;
      };
      /** Rationale */
      rationale: string;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * InterventionListResponse
     * @description Intervention cursor page.
     */
    InterventionListResponse: {
      /** Items */
      items: components["schemas"]["InterventionSummary"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * InterventionSummary
     * @description Controller action summarized for dashboard/intervention lists.
     */
    InterventionSummary: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Goal Id
       * Format: uuid
       */
      goal_id: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Policy Outcome */
      policy_outcome: string;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      status: components["schemas"]["ActionStatus"];
      /** Summary */
      summary: string;
      type: components["schemas"]["ActionType"];
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /**
     * InventoryItem
     * @description Inventory row for operator UI.
     */
    InventoryItem: {
      /** Category */
      category: string;
      /** Inventory Units */
      inventory_units: number;
      /** Product Id */
      product_id: string;
      /**
       * Stock State
       * @enum {string}
       */
      stock_state: "out" | "low" | "normal" | "excess";
      /** Title */
      title: string;
    };
    /**
     * InventoryResponse
     * @description Inventory cursor page.
     */
    InventoryResponse: {
      /** Items */
      items: components["schemas"]["InventoryItem"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * KillSwitchResponse
     * @description Current tenant kill-switch state.
     */
    KillSwitchResponse: {
      /** Enabled */
      enabled: boolean;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /**
     * LiveResponse
     * @description Liveness response.
     */
    LiveResponse: {
      /**
       * Status
       * @default live
       * @constant
       */
      status?: "live";
    };
    /** ManagerAgentCapabilities */
    ManagerAgentCapabilities: {
      /**
       * Code Context
       * @default true
       */
      code_context?: boolean;
      /**
       * Complex Tools Simulated
       * @default true
       */
      complex_tools_simulated?: boolean;
      /**
       * Conversation Model
       * @default bounded-rule-interpreter
       */
      conversation_model?: string;
      /**
       * Conversation Provider
       * @default deterministic
       */
      conversation_provider?: string;
      /** Learned Semantics */
      learned_semantics: boolean;
      /**
       * Model Backed
       * @default false
       */
      model_backed?: boolean;
      /**
       * Search Testing
       * @default true
       */
      search_testing?: boolean;
      /** Semantic Backend */
      semantic_backend: string;
      /**
       * Service Status
       * @default true
       */
      service_status?: boolean;
      /** Supported Ranking Signals */
      supported_ranking_signals?: ("relevance" | "popularity" | "quality")[];
      /** Supported Surfaces */
      supported_surfaces?: ("search" | "recommendations" | "both")[];
    };
    /** ManagerAgentReply */
    ManagerAgentReply: {
      assistant_message: components["schemas"]["ManagerMessage"];
      capabilities: components["schemas"]["ManagerAgentCapabilities"];
      /** Memories */
      memories: components["schemas"]["ManagerMemory"][];
      onboarding: components["schemas"]["ManagerDataOnboarding"];
      periodic_memory_created?: components["schemas"]["ManagerMemory"] | null;
      thread: components["schemas"]["ManagerThread"];
      user_message: components["schemas"]["ManagerMessage"];
      /**
       * Workspace Changed
       * @default false
       */
      workspace_changed?: boolean;
    };
    /** ManagerChannelClearResponse */
    ManagerChannelClearResponse: {
      /** Deleted Message Count */
      deleted_message_count: number;
      /** Deleted Reply Thread Count */
      deleted_reply_thread_count: number;
      detail: components["schemas"]["ManagerThreadDetail"];
    };
    /**
     * ManagerDataOnboarding
     * @description Tenant-level data intake draft shared by every manager conversation.
     */
    ManagerDataOnboarding: {
      /** Cadence */
      cadence?: ("manual" | "hourly" | "six_hourly" | "daily" | "weekly") | null;
      catalog?: components["schemas"]["DataSourceDraft"] | null;
      /**
       * Catalog Decision
       * @default pending
       * @enum {string}
       */
      catalog_decision?: "pending" | "provide" | "defer";
      /** Completed At */
      completed_at?: string | null;
      /** Completed Fields */
      completed_fields?: (
        | "workspace_name"
        | "business_summary"
        | "manager_role"
        | "primary_goal"
        | "starter_agents"
        | "priority_surfaces"
        | "search_baseline"
        | "recommendation_surfaces"
        | "buy_again_strategy"
        | "catalog_decision"
        | "engagement_decision"
        | "cadence"
        | "success_metrics"
        | "guardrails"
        | "operating_mode"
        | "response_style"
        | "review"
      )[];
      /** Created At */
      created_at?: string | null;
      current_prompt?: components["schemas"]["OnboardingPrompt"] | null;
      engagement?: components["schemas"]["DataSourceDraft"] | null;
      /**
       * Engagement Decision
       * @default pending
       * @enum {string}
       */
      engagement_decision?: "pending" | "provide" | "skip";
      /** Incremental Mode */
      incremental_mode?: ("full_refresh" | "watermark") | null;
      /**
       * Limited Mode
       * @default false
       */
      limited_mode?: boolean;
      /**
       * Scheduled Loads Active
       * @default false
       * @constant
       */
      scheduled_loads_active?: false;
      /**
       * Status
       * @default needs_catalog
       * @enum {string}
       */
      status?:
        | "needs_catalog"
        | "needs_engagement_decision"
        | "needs_schedule"
        | "ready_for_review";
      /**
       * Status Refresh Minutes
       * @default 5
       */
      status_refresh_minutes?: number;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /**
       * Timezone
       * @default UTC
       * @constant
       */
      timezone?: "UTC";
      /** Updated At */
      updated_at?: string | null;
      /** Watermark Column */
      watermark_column?: string | null;
      workspace_profile?: components["schemas"]["ManagerWorkspaceProfile"];
      /**
       * Workspace Status
       * @default not_started
       * @enum {string}
       */
      workspace_status?: "not_started" | "in_progress" | "review" | "completed";
    };
    /** ManagerDatasetProfileReply */
    ManagerDatasetProfileReply: {
      assistant_message: components["schemas"]["ManagerMessage"];
      capabilities: components["schemas"]["ManagerAgentCapabilities"];
      catalog_index?: components["schemas"]["CatalogIndexStatus"];
      /** Memories */
      memories: components["schemas"]["ManagerMemory"][];
      onboarding: components["schemas"]["ManagerDataOnboarding"];
      profile: components["schemas"]["DatasetProfile"];
      thread: components["schemas"]["ManagerThread"];
      user_message: components["schemas"]["ManagerMessage"];
    };
    /** ManagerDatasetProfileRequest */
    ManagerDatasetProfileRequest: {
      /** Catalog Currency */
      catalog_currency?: ("USD" | "EUR" | "GBP" | "CAD" | "AUD") | null;
      /** Csv Text */
      csv_text: string;
      /**
       * Dataset Kind
       * @enum {string}
       */
      dataset_kind: "catalog" | "engagement";
      /** Filename */
      filename: string;
    };
    /** ManagerMemory */
    ManagerMemory: {
      /** Content */
      content: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Layer
       * @enum {string}
       */
      layer: "long_term" | "working" | "periodic";
      /** Period End */
      period_end?: string | null;
      /** Period Start */
      period_start?: string | null;
      /**
       * Source
       * @enum {string}
       */
      source: "explicit_manager" | "working_state" | "periodic_summary";
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /** Thread Id */
      thread_id?: string | null;
      /** Title */
      title: string;
    };
    /** ManagerMemoryDeleteResponse */
    ManagerMemoryDeleteResponse: {
      /** Deleted */
      deleted: boolean;
      /**
       * Memory Id
       * Format: uuid
       */
      memory_id: string;
    };
    /** ManagerMemoryListResponse */
    ManagerMemoryListResponse: {
      /** Items */
      items: components["schemas"]["ManagerMemory"][];
    };
    /** ManagerMessage */
    ManagerMessage: {
      /** Content */
      content: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Reply Count
       * @default 0
       */
      reply_count?: number;
      /**
       * Role
       * @enum {string}
       */
      role: "user" | "assistant";
      /** Steps */
      steps?: components["schemas"]["AgentStep"][];
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /**
       * Thread Id
       * Format: uuid
       */
      thread_id: string;
    };
    /** ManagerMessageRequest */
    ManagerMessageRequest: {
      /** Content */
      content: string;
    };
    /** ManagerReplyThreadCreateRequest */
    ManagerReplyThreadCreateRequest: {
      /**
       * Root Message Id
       * Format: uuid
       */
      root_message_id: string;
    };
    /** ManagerRun */
    ManagerRun: {
      /** Assistant Message Id */
      assistant_message_id?: string | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Error Code */
      error_code?: string | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Phase */
      phase: string;
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "waiting" | "completed" | "failed" | "cancelled";
      /**
       * Thread Id
       * Format: uuid
       */
      thread_id: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
      /**
       * User Message Id
       * Format: uuid
       */
      user_message_id: string;
    };
    /** ManagerRunEvent */
    ManagerRunEvent: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Detail */
      detail: string;
      /**
       * Kind
       * @enum {string}
       */
      kind:
        | "queued"
        | "model"
        | "tool_started"
        | "tool_result"
        | "waiting"
        | "completed"
        | "failed"
        | "cancelled";
      /** Sequence */
      sequence: number;
      /** Title */
      title: string;
      /** Tool */
      tool?: string | null;
    };
    /** ManagerRunEvents */
    ManagerRunEvents: {
      /** Items */
      items: components["schemas"]["ManagerRunEvent"][];
      /** Next Cursor */
      next_cursor: number;
      run: components["schemas"]["ManagerRun"];
    };
    /**
     * ManagerRuntimeComponent
     * @description One dynamic operational status displayed in the manager workspace.
     */
    ManagerRuntimeComponent: {
      /** Detail */
      detail: string;
      /**
       * Evidence Kind
       * @default derived
       * @enum {string}
       */
      evidence_kind?: "probe" | "derived" | "configuration" | "model_call";
      /** Key */
      key: string;
      /** Label */
      label: string;
      /** Latency Ms */
      latency_ms?: number | null;
      /** Observed At */
      observed_at?: string | null;
      /**
       * Repair Available
       * @default false
       */
      repair_available?: boolean;
      /**
       * State
       * @enum {string}
       */
      state: "green" | "yellow" | "red" | "unknown";
    };
    /**
     * ManagerRuntimeStatus
     * @description Dynamic service and commerce-surface health for the local workspace.
     */
    ManagerRuntimeStatus: {
      /** Components */
      components: components["schemas"]["ManagerRuntimeComponent"][];
      /**
       * Generated At
       * Format: date-time
       */
      generated_at: string;
    };
    /** ManagerThread */
    ManagerThread: {
      /**
       * Channel Kind
       * @default custom
       */
      channel_kind?:
        | ("onboarding" | "status" | "search" | "recommendations" | "buy_again" | "custom")
        | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Description */
      description?: string | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Parent Thread Id */
      parent_thread_id?: string | null;
      /**
       * Position
       * @default 100
       */
      position?: number;
      /** Root Message Id */
      root_message_id?: string | null;
      /** Slug */
      slug?: string | null;
      /**
       * Status
       * @default active
       * @enum {string}
       */
      status?: "active" | "archived";
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /**
       * Thread Type
       * @default channel
       * @enum {string}
       */
      thread_type?: "channel" | "reply";
      /** Title */
      title: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
      /**
       * User Turn Count
       * @default 0
       */
      user_turn_count?: number;
      /**
       * Version
       * @default 1
       */
      version?: number;
      working_memory?: components["schemas"]["ManagerWorkingMemory"];
    };
    /** ManagerThreadCreateRequest */
    ManagerThreadCreateRequest: {
      /** Description */
      description?: string | null;
      /**
       * Title
       * @default Discovery strategy
       */
      title?: string;
    };
    /** ManagerThreadDetail */
    ManagerThreadDetail: {
      active_run?: components["schemas"]["ManagerRun"] | null;
      capabilities: components["schemas"]["ManagerAgentCapabilities"];
      /** Memories */
      memories: components["schemas"]["ManagerMemory"][];
      /** Messages */
      messages: components["schemas"]["ManagerMessage"][];
      onboarding: components["schemas"]["ManagerDataOnboarding"];
      root_message?: components["schemas"]["ManagerMessage"] | null;
      thread: components["schemas"]["ManagerThread"];
    };
    /** ManagerThreadListResponse */
    ManagerThreadListResponse: {
      /** Items */
      items: components["schemas"]["ManagerThread"][];
    };
    /** ManagerThreadUpdateRequest */
    ManagerThreadUpdateRequest: {
      /** Description */
      description?: string | null;
      /** Status */
      status?: ("active" | "archived") | null;
      /** Title */
      title?: string | null;
    };
    /**
     * ManagerWorkingMemory
     * @description Bounded, replaceable context for one active conversation.
     */
    ManagerWorkingMemory: {
      /** Current Topic */
      current_topic?: string | null;
      objective?: components["schemas"]["DiscoveryObjectiveDraft"] | null;
      /** Open Question */
      open_question?: string | null;
      /** Recent Decisions */
      recent_decisions?: string[];
    };
    /**
     * ManagerWorkspaceProfile
     * @description Bounded, non-secret context collected during the first-run interview.
     */
    ManagerWorkspaceProfile: {
      /** Business Summary */
      business_summary?: string | null;
      /** Buy Again Strategy */
      buy_again_strategy?: ("important" | "later" | "not_applicable" | "unknown") | null;
      /** Guardrails */
      guardrails?: ("relevance" | "availability" | "margin" | "brand" | "diversity" | "privacy")[];
      /** Manager Role */
      manager_role?: ("merchandising" | "search" | "growth" | "operations" | "mixed") | null;
      /** Operating Mode */
      operating_mode?: ("draft_only" | "approval_required") | null;
      /** Primary Goal */
      primary_goal?: string | null;
      /** Priority Surfaces */
      priority_surfaces?: (
        | "search"
        | "pdp_recommendations"
        | "home_recommendations"
        | "cart"
        | "buy_again"
      )[];
      /** Recommendation Surfaces */
      recommendation_surfaces?: ("none" | "pdp" | "home" | "cart" | "post_purchase" | "email")[];
      /** Response Style */
      response_style?: ("concise" | "balanced" | "detailed") | null;
      /** Search Baseline */
      search_baseline?: ("none" | "keyword" | "semantic" | "hybrid" | "unknown") | null;
      /** Starter Agents */
      starter_agents?: (
        | "general"
        | "status"
        | "search"
        | "recommendations"
        | "buy_again"
        | "analysis"
      )[];
      /** Success Metrics */
      success_metrics?: (
        | "conversion"
        | "revenue_per_session"
        | "search_success"
        | "recommendation_ctr"
        | "repeat_purchase"
        | "margin"
      )[];
      /** Workspace Name */
      workspace_name?: string | null;
    };
    /** ManagerWorkspaceResetRequest */
    ManagerWorkspaceResetRequest: {
      /**
       * Confirmation
       * @constant
       */
      confirmation: "RESET";
    };
    /** ManagerWorkspaceResetResponse */
    ManagerWorkspaceResetResponse: {
      /** Deleted Channel Count */
      deleted_channel_count: number;
      /** Deleted Memory Count */
      deleted_memory_count: number;
      /** Deleted Message Count */
      deleted_message_count: number;
      workspace: components["schemas"]["ManagerWorkspaceResponse"];
    };
    /** ManagerWorkspaceResponse */
    ManagerWorkspaceResponse: {
      capabilities: components["schemas"]["ManagerAgentCapabilities"];
      catalog_index?: components["schemas"]["CatalogIndexStatus"];
      /** Channels */
      channels: components["schemas"]["ManagerThread"][];
      onboarding: components["schemas"]["ManagerDataOnboarding"];
    };
    /**
     * MeasurementOutcome
     * @description Persisted descriptive outcome; no causal action lift is claimed.
     */
    MeasurementOutcome: {
      /** Conclusion */
      conclusion: string;
      /**
       * Evaluated At
       * Format: date-time
       */
      evaluated_at: string;
      /**
       * Guardrail Status
       * @enum {string}
       */
      guardrail_status: "breached" | "clear" | "insufficient_data";
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Method */
      method: string;
      /** Metric Results */
      metric_results: {
        [key: string]: unknown;
      };
      /** Sample Size */
      sample_size: number | null;
    };
    /**
     * MeasurementSchedule
     * @description Deterministic post-execution measurement window.
     */
    MeasurementSchedule: {
      /**
       * Action Id
       * Format: uuid
       */
      action_id: string;
      /**
       * Baseline Kind
       * @default unavailable
       * @enum {string}
       */
      baseline_kind?: "recent_runtime" | "historical_prior" | "unavailable";
      /** Baseline Ref */
      baseline_ref: string;
      /** Baseline Totals */
      baseline_totals?: {
        [key: string]: unknown;
      };
      /** Cac Ceiling Minor */
      cac_ceiling_minor?: number | null;
      /**
       * Ends At
       * Format: date-time
       */
      ends_at: string;
      /**
       * Margin Floor
       * @default 0.25
       */
      margin_floor?: string;
      /** Metric Names */
      metric_names: components["schemas"]["MetricName"][];
      /**
       * Minimum Days
       * @default 2
       */
      minimum_days?: number;
      /**
       * Minimum Sample
       * @default 500
       */
      minimum_sample?: number;
      /**
       * Starts At
       * Format: date-time
       */
      starts_at: string;
    };
    /**
     * MerchandisingConstraints
     * @description Hard action/redemption bounds, not guarantees about realized store outcomes.
     */
    "MerchandisingConstraints-Input": {
      /**
       * Max Base Price Change
       * @default 0.10
       */
      max_base_price_change?: number | string;
      /**
       * Max Cumulative Price Change
       * @default 0.15
       */
      max_cumulative_price_change?: number | string;
      /**
       * Max Duration Hours
       * @default 168
       */
      max_duration_hours?: number;
      /**
       * Max Effective Discount
       * @default 0.15
       */
      max_effective_discount?: number | string;
      /**
       * Minimum Relevance
       * @default 0.55
       */
      minimum_relevance?: number | string;
      /**
       * Minimum Unit Margin
       * @default 0.25
       */
      minimum_unit_margin?: number | string;
      /**
       * Price Cooldown Hours
       * @default 72
       */
      price_cooldown_hours?: number;
      /** Prohibited Actions */
      prohibited_actions?: components["schemas"]["ActionType"][];
      /**
       * Promotion Cap Minor
       * @default 0
       */
      promotion_cap_minor?: number;
      /**
       * Require Available
       * @default true
       * @constant
       */
      require_available?: true;
    };
    /**
     * MerchandisingConstraints
     * @description Hard action/redemption bounds, not guarantees about realized store outcomes.
     */
    "MerchandisingConstraints-Output": {
      /**
       * Max Base Price Change
       * @default 0.10
       */
      max_base_price_change?: string;
      /**
       * Max Cumulative Price Change
       * @default 0.15
       */
      max_cumulative_price_change?: string;
      /**
       * Max Duration Hours
       * @default 168
       */
      max_duration_hours?: number;
      /**
       * Max Effective Discount
       * @default 0.15
       */
      max_effective_discount?: string;
      /**
       * Minimum Relevance
       * @default 0.55
       */
      minimum_relevance?: string;
      /**
       * Minimum Unit Margin
       * @default 0.25
       */
      minimum_unit_margin?: string;
      /**
       * Price Cooldown Hours
       * @default 72
       */
      price_cooldown_hours?: number;
      /** Prohibited Actions */
      prohibited_actions?: components["schemas"]["ActionType"][];
      /**
       * Promotion Cap Minor
       * @default 0
       */
      promotion_cap_minor?: number;
      /**
       * Require Available
       * @default true
       * @constant
       */
      require_available?: true;
    };
    /** MerchandisingEvidenceResponse */
    MerchandisingEvidenceResponse: {
      /** Data */
      data: {
        [key: string]: unknown;
      };
      /** Evidence Ref */
      evidence_ref: string;
      /** Limitations */
      limitations: string[];
      /** Observation Version */
      observation_version: string;
      /**
       * View
       * @enum {string}
       */
      view:
        | "economics"
        | "pricing"
        | "products"
        | "inventory"
        | "outcomes"
        | "search"
        | "recommendations";
    };
    /** MerchandisingSummary */
    MerchandisingSummary: {
      /**
       * Catalog Version
       * @default merchandising-catalog-v1
       */
      catalog_version?: string;
      /** Contribution Profit Minor */
      contribution_profit_minor: number;
      /**
       * Incoming Traffic
       * @default fixed_external_no_acquisition
       * @constant
       */
      incoming_traffic?: "fixed_external_no_acquisition";
      /** Net Revenue Minor */
      net_revenue_minor: number;
      /** Promotion Cap Minor */
      promotion_cap_minor: number;
      /** Promotion Redeemed Value Minor */
      promotion_redeemed_value_minor: number;
      /** Promotion Remaining Minor */
      promotion_remaining_minor: number;
      /** Recommendation Policy Version */
      recommendation_policy_version: number;
      /**
       * Recommendation Strategy
       * @enum {string}
       */
      recommendation_strategy: "alternatives" | "complements";
      /** Recorded Checkouts */
      recorded_checkouts: number;
      /** Serving Batches */
      serving_batches: number;
    };
    /** MergeSelection */
    MergeSelection: {
      /**
       * Cart Choice
       * @enum {string}
       */
      cart_choice: "keep_guest" | "keep_account";
      /**
       * Token
       * Format: password
       */
      token: string;
    };
    /**
     * MetaResponse
     * @description Service metadata exposed to the frontend and generated SDK.
     */
    MetaResponse: {
      /** App Name */
      app_name: string;
      /** Dependencies */
      dependencies: components["schemas"]["DependencyStatus"][];
      /** Environment */
      environment: string;
      /**
       * Status
       * @enum {string}
       */
      status: "ready" | "not_ready";
      /** Version */
      version: string;
    };
    /**
     * MetricDefinition
     * @description Public metric definition for UI labels and guardrails.
     */
    MetricDefinition: {
      /** Description */
      description: string;
      /**
       * Freshness
       * @enum {string}
       */
      freshness: "fresh" | "stale" | "empty";
      /** Label */
      label: string;
      name: components["schemas"]["MetricName"];
      /**
       * Unit
       * @enum {string}
       */
      unit: "count" | "money" | "rate" | "minor_money";
      /** Version */
      version: string;
    };
    /**
     * MetricName
     * @enum {string}
     */
    MetricName:
      | "new_customers"
      | "cac"
      | "revenue"
      | "contribution_profit"
      | "contribution_margin_rate"
      | "conversion_rate"
      | "discount_rate"
      | "units_sold"
      | "inventory_days_of_supply"
      | "search_conversion_rate"
      | "search_attributed_purchases";
    /**
     * MetricsDefinitionsResponse
     * @description Metric definition collection.
     */
    MetricsDefinitionsResponse: {
      /** Items */
      items: components["schemas"]["MetricDefinition"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * MetricSeriesPoint
     * @description One metric series point; null means unavailable, not a measured zero.
     */
    MetricSeriesPoint: {
      /**
       * Timestamp
       * Format: date-time
       */
      timestamp: string;
      /** Value */
      value: string | null;
    };
    /**
     * MetricsSeriesResponse
     * @description Metric time series with release-facing metadata.
     */
    MetricsSeriesResponse: {
      /** Attribution Model */
      attribution_model: string;
      /** Completeness Warnings */
      completeness_warnings: string[];
      /** Definition Version */
      definition_version: string;
      /**
       * Freshness
       * @enum {string}
       */
      freshness: "fresh" | "stale" | "empty";
      /** Items */
      items: components["schemas"]["MetricSeriesPoint"][];
      metric: components["schemas"]["MetricName"];
      /** Next Cursor */
      next_cursor?: string | null;
      /** Timezone */
      timezone: string;
    };
    /**
     * MetricsSummaryResponse
     * @description Current simulator outcome summary.
     */
    MetricsSummaryResponse: {
      /** Definitions */
      definitions: components["schemas"]["MetricDefinition"][];
      /**
       * Freshness
       * @enum {string}
       */
      freshness: "fresh" | "stale" | "empty";
      /** Instance Id */
      instance_id: string | null;
      latest: components["schemas"]["DailyMetrics"] | null;
      /** Scenario Id */
      scenario_id: ("acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1") | null;
      /** Seed */
      seed: number | null;
      totals: components["schemas"]["MetricTotals"];
    };
    /**
     * MetricTotals
     * @description Aggregated simulator outcome totals.
     */
    MetricTotals: {
      /** Ad Spend Minor */
      ad_spend_minor: number;
      /** Cac Minor */
      cac_minor: number | null;
      /** Cogs Minor */
      cogs_minor: number;
      /** Contribution Margin Rate */
      contribution_margin_rate: string;
      /** Contribution Profit Minor */
      contribution_profit_minor: number;
      /** Conversion Rate */
      conversion_rate: string;
      /** Days */
      days: number;
      /** Discounts Minor */
      discounts_minor: number;
      /** Gross Revenue Minor */
      gross_revenue_minor: number;
      /** New Customers */
      new_customers: number;
      /** Orders */
      orders: number;
      /** Search Attributed Purchases */
      search_attributed_purchases: number;
      /** Sessions */
      sessions: number;
      /** Units Sold */
      units_sold: number;
      /** Variable Fees Minor */
      variable_fees_minor: number;
    };
    /**
     * Money
     * @description Money represented as integer minor units plus ISO-4217 currency.
     */
    Money: {
      /** Amount Minor */
      amount_minor: number;
      /** Currency */
      currency: string;
    };
    /** MonitoringPreset */
    MonitoringPreset: {
      /** Enabled */
      enabled: boolean;
      /**
       * Name
       * @enum {string}
       */
      name: "failed_imports" | "unavailable_ai" | "empty_results";
    };
    /**
     * NoOpIntent
     * @description Explicit no-op decision.
     */
    NoOpIntent: {
      /** Opportunity Ids */
      opportunity_ids: string[];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "no_op";
    };
    /**
     * ObjectiveDirection
     * @enum {string}
     */
    ObjectiveDirection: "maximize" | "minimize" | "reach";
    /**
     * ObjectiveSpec
     * @description A finite measurable objective.
     */
    ObjectiveSpec: {
      direction: components["schemas"]["ObjectiveDirection"];
      metric: components["schemas"]["MetricName"];
      /**
       * Scope
       * @default store
       * @enum {string}
       */
      scope?: "store" | "excess_inventory";
      /** Target */
      target?: string | null;
    };
    /**
     * ObservationSnapshot
     * @description Read-only simulator/search snapshot for one controller run.
     */
    ObservationSnapshot: {
      /** Campaign Summary */
      campaign_summary: {
        [key: string]: unknown;
      }[];
      /** Catalog Summary */
      catalog_summary: {
        [key: string]: unknown;
      };
      /** Data Age Minutes */
      data_age_minutes: {
        [key: string]: number;
      };
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Metric Summary */
      metric_summary: {
        [key: string]: unknown;
      };
      /**
       * Observed At
       * Format: date-time
       */
      observed_at: string;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /** Sample Size */
      sample_size: number;
      /**
       * Scenario Id
       * @enum {string}
       */
      scenario_id: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /**
       * Simulator Instance Id
       * Format: uuid
       */
      simulator_instance_id: string;
      /** State Hash */
      state_hash: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /** OnboardingChoice */
    OnboardingChoice: {
      /** Description */
      description?: string | null;
      /** Label */
      label: string;
      /** Value */
      value: string;
    };
    /** OnboardingPrompt */
    OnboardingPrompt: {
      /** Choices */
      choices?: components["schemas"]["OnboardingChoice"][];
      /**
       * Field
       * @enum {string}
       */
      field:
        | "workspace_name"
        | "business_summary"
        | "manager_role"
        | "primary_goal"
        | "starter_agents"
        | "priority_surfaces"
        | "search_baseline"
        | "recommendation_surfaces"
        | "buy_again_strategy"
        | "catalog_decision"
        | "engagement_decision"
        | "cadence"
        | "success_metrics"
        | "guardrails"
        | "operating_mode"
        | "response_style"
        | "review";
      /**
       * Input Kind
       * @enum {string}
       */
      input_kind: "text" | "single_select" | "multi_select" | "dataset" | "review";
      /** Intro */
      intro?: string | null;
      /** Ordinal */
      ordinal: number;
      /** Question */
      question: string;
      /**
       * Required
       * @default true
       */
      required?: boolean;
      /** Section */
      section: string;
      /**
       * Total
       * @default 8
       */
      total?: number;
    };
    /**
     * Opportunity
     * @description A deterministic opportunity detected from read-only evidence.
     */
    Opportunity: {
      /** Confidence */
      confidence: string;
      /** Description */
      description: string;
      /**
       * Detected At
       * Format: date-time
       */
      detected_at: string;
      /** Evidence */
      evidence: components["schemas"]["EvidenceItem"][];
      expected_metric: components["schemas"]["MetricName"];
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
      /** Title */
      title: string;
      /**
       * Type
       * @enum {string}
       */
      type:
        | "merchandising_investigation"
        | "conversion_gap"
        | "excess_inventory"
        | "campaign_efficiency"
        | "search_exposure_gap"
        | "guardrail_review";
    };
    /** OrderSummary */
    OrderSummary: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Lines */
      lines: components["schemas"]["CheckoutLine"][];
      /** Order Number */
      order_number: string;
      /**
       * Status
       * @enum {string}
       */
      status: "paid" | "cancelled";
      total: components["schemas"]["Money"];
    };
    /** OwnerAuthResponse */
    OwnerAuthResponse: {
      /** Recovery Code */
      recovery_code?: string | null;
      store: components["schemas"]["StoreProfile"];
      /**
       * User Id
       * Format: uuid
       */
      user_id: string;
    };
    /** OwnerLoginRequest */
    OwnerLoginRequest: {
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /** OwnerRecoveryRequest */
    OwnerRecoveryRequest: {
      /**
       * Password
       * Format: password
       */
      password: string;
      /**
       * Recovery Code
       * Format: password
       */
      recovery_code: string;
      /** Username */
      username: string;
    };
    /** OwnerSetupRequest */
    OwnerSetupRequest: {
      /**
       * Bootstrap Token
       * Format: password
       */
      bootstrap_token: string;
      /**
       * Currency
       * @default USD
       * @enum {string}
       */
      currency?: "USD" | "EUR" | "GBP" | "CAD" | "AUD";
      /**
       * Description
       * @default
       */
      description?: string;
      /**
       * Goal
       * @default Help shoppers find suitable products
       */
      goal?: string;
      /** Name */
      name: string;
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /**
     * ParseSearchResponse
     * @description Search parser response.
     */
    ParseSearchResponse: {
      interpretation: components["schemas"]["SearchIntent"];
    };
    /** PaymentAttemptSummary */
    PaymentAttemptSummary: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Failure Code */
      failure_code?: string | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Provider
       * @default local_test
       * @constant
       */
      provider?: "local_test";
      /** Provider Reference */
      provider_reference: string;
      /**
       * Status
       * @enum {string}
       */
      status:
        | "requires_confirmation"
        | "processing"
        | "requires_payment_method"
        | "succeeded"
        | "cancelled";
      total: components["schemas"]["Money"];
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /**
     * PolicyDecision
     * @description Deterministic policy outcome for one action version.
     */
    PolicyDecision: {
      /** Evaluated Rules */
      evaluated_rules: components["schemas"]["RuleEvaluation"][];
      outcome: components["schemas"]["PolicyOutcome"];
      /** Reason Codes */
      reason_codes: string[];
      /** Required Approver Roles */
      required_approver_roles?: components["schemas"]["ActorRole"][];
      /**
       * Valid Until
       * Format: date-time
       */
      valid_until: string;
    };
    /**
     * PolicyHistoryEntry
     * @description Tenant policy version history entry.
     */
    PolicyHistoryEntry: {
      /**
       * Changed At
       * Format: date-time
       */
      changed_at: string;
      /** Idempotency Key */
      idempotency_key: string;
      /** New Hash */
      new_hash: string;
      /** Previous Hash */
      previous_hash: string;
      /** Version */
      version: number;
    };
    /**
     * PolicyHistoryResponse
     * @description Policy history response.
     */
    PolicyHistoryResponse: {
      /** Items */
      items: components["schemas"]["PolicyHistoryEntry"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * PolicyOutcome
     * @enum {string}
     */
    PolicyOutcome: "allow" | "require_approval" | "deny";
    /**
     * PolicyUpdateRequest
     * @description Patchable tenant policy settings. Tenant comes from request context.
     */
    PolicyUpdateRequest: {
      /** Allowed Action Types */
      allowed_action_types?: components["schemas"]["ActionType"][] | null;
      /** Blocked Provider Resources */
      blocked_provider_resources?: string[] | null;
      /** Campaign Budget Max Change Rate */
      campaign_budget_max_change_rate?: number | string | null;
      default_mode?: components["schemas"]["AutonomyMode"] | null;
      /** Discount Max Percentage */
      discount_max_percentage?: number | string | null;
      /** Discount Minimum Margin Rate */
      discount_minimum_margin_rate?: number | string | null;
      /** Kill Switch Enabled */
      kill_switch_enabled?: boolean | null;
      /** Max Actions Per Run */
      max_actions_per_run?: number | null;
      /** Max Data Age Minutes */
      max_data_age_minutes?: number | null;
      /** Max Parallel Interventions */
      max_parallel_interventions?: number | null;
      max_total_estimated_cost?: components["schemas"]["Money"] | null;
      /** Min Action Confidence */
      min_action_confidence?: number | string | null;
      /** Min Observations For Auto Action */
      min_observations_for_auto_action?: number | null;
      /** Per Action Modes */
      per_action_modes?: {
        [key: string]: components["schemas"]["AutonomyMode"];
      } | null;
      /** Price Max Delta Rate */
      price_max_delta_rate?: number | string | null;
      /** Search Boost Max Multiplier */
      search_boost_max_multiplier?: number | string | null;
      /** Search Boost Min Relevance */
      search_boost_min_relevance?: number | string | null;
    };
    /**
     * PolicyValidateRequest
     * @description Dry-run validation payload for a policy update.
     */
    PolicyValidateRequest: {
      policy: components["schemas"]["PolicyUpdateRequest"];
    };
    /**
     * PolicyValidationResponse
     * @description Result of validating a policy patch.
     */
    PolicyValidationResponse: {
      effective_policy: components["schemas"]["ControllerPolicyConfig"];
      /** Reason Codes */
      reason_codes: string[];
      /** Valid */
      valid: boolean;
    };
    /**
     * Precondition
     * @description Optimistic-concurrency precondition for a write.
     */
    Precondition: {
      /** Field */
      field: string;
      /** Operator */
      operator: string;
      /** Value */
      value: unknown;
    };
    /** PreferenceSettings */
    PreferenceSettings: {
      /** Enabled */
      enabled: boolean;
    };
    /** PreviewExchange */
    PreviewExchange: {
      /**
       * Token
       * Format: password
       */
      token: string;
    };
    /** PreviewResponse */
    PreviewResponse: {
      /**
       * Catalog Id
       * Format: uuid
       */
      catalog_id: string;
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /** Store Slug */
      store_slug: string;
      /** Token */
      token: string;
    };
    /**
     * PriceRange
     * @description Integer-minor-unit price range.
     */
    PriceRange: {
      /**
       * Currency
       * @default USD
       */
      currency?: string;
      /** Max Price Minor */
      max_price_minor?: number | null;
      /** Min Price Minor */
      min_price_minor?: number | null;
    };
    /**
     * ProductDetail
     * @description Catalog product detail safe for local operator UI.
     */
    ProductDetail: {
      /** Active Action Count */
      active_action_count: number | null;
      /** Attributes */
      attributes: {
        [key: string]: string;
      };
      /** Brand */
      brand: string;
      /** Category */
      category: string;
      /** Description Text */
      description_text: string;
      /**
       * Index Status
       * @enum {string}
       */
      index_status: "indexed" | "pending" | "not_checked";
      /** Inventory Units */
      inventory_units: number;
      /** Popularity Score */
      popularity_score: string;
      price: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Quality Score */
      quality_score: string;
      /** Search Document Preview */
      search_document_preview: string;
      /**
       * Source Updated At
       * Format: date-time
       */
      source_updated_at: string;
      /**
       * Stock State
       * @enum {string}
       */
      stock_state: "out" | "low" | "normal" | "excess";
      /** Tags */
      tags: string[];
      /** Title */
      title: string;
      /** Variants */
      variants: components["schemas"]["ProductVariantSummary"][];
    };
    /**
     * ProductFilters
     * @description Structured product filters accepted by public APIs.
     */
    ProductFilters: {
      /** Attributes */
      attributes?: {
        [key: string]: string[];
      };
      /** Brand */
      brand?: string | null;
      /** Category */
      category?: string | null;
      /** Currency */
      currency?: string | null;
      /** Excluded Attributes */
      excluded_attributes?: {
        [key: string]: string[];
      };
      /**
       * In Stock
       * @default true
       */
      in_stock?: boolean | null;
      /** Max Price Minor */
      max_price_minor?: number | null;
      /** Min Price Minor */
      min_price_minor?: number | null;
    };
    /**
     * ProductListResponse
     * @description Product cursor page.
     */
    ProductListResponse: {
      /** Items */
      items: components["schemas"]["ProductSummary"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * ProductScope
     * @description Product targeting scope.
     */
    ProductScope: {
      /** Category Paths */
      category_paths?: string[];
      /** Product Ids */
      product_ids?: string[];
      /** Tags */
      tags?: string[];
    };
    /**
     * ProductSummary
     * @description Catalog product summary without provider secrets or customer data.
     */
    ProductSummary: {
      /** Active Action Count */
      active_action_count: number | null;
      /** Brand */
      brand: string;
      /** Category */
      category: string;
      /**
       * Index Status
       * @enum {string}
       */
      index_status: "indexed" | "pending" | "not_checked";
      /** Inventory Units */
      inventory_units: number;
      /** Popularity Score */
      popularity_score: string;
      price: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Quality Score */
      quality_score: string;
      /**
       * Source Updated At
       * Format: date-time
       */
      source_updated_at: string;
      /**
       * Stock State
       * @enum {string}
       */
      stock_state: "out" | "low" | "normal" | "excess";
      /** Tags */
      tags: string[];
      /** Title */
      title: string;
    };
    /**
     * ProductVariantSummary
     * @description Catalog variant details safe for operator UI.
     */
    ProductVariantSummary: {
      /** Available */
      available: boolean;
      /** Id */
      id: string;
      /** Inventory */
      inventory: number;
      original_price: components["schemas"]["Money"];
      price: components["schemas"]["Money"];
      /** Sku */
      sku: string;
      /** Title */
      title: string;
    };
    /**
     * ProviderRef
     * @description Provider target for a compiled action.
     */
    ProviderRef: {
      /** Integration Id */
      integration_id: string | null;
      /** Provider Type */
      provider_type: string;
      /** Resource Id */
      resource_id: string;
      /** Resource Type */
      resource_type: string;
    };
    /**
     * ProviderResult
     * @description Redacted provider write result.
     */
    ProviderResult: {
      /** After State */
      after_state?: {
        [key: string]: unknown;
      } | null;
      /** Before State */
      before_state: {
        [key: string]: unknown;
      };
      error?: components["schemas"]["SafeError"] | null;
      /** Provider Request Id */
      provider_request_id?: string | null;
      /** Provider Resource Id */
      provider_resource_id?: string | null;
      /**
       * Reconciliation Required
       * @default false
       */
      reconciliation_required?: boolean;
      status: components["schemas"]["ExecutionStatus"];
    };
    /** PublicationRequest */
    PublicationRequest: {
      /**
       * Acknowledge Demo Checkout
       * @default false
       */
      acknowledge_demo_checkout?: boolean;
      /**
       * Acknowledge Image Issues
       * @default false
       */
      acknowledge_image_issues?: boolean;
      /**
       * Catalog Id
       * Format: uuid
       */
      catalog_id: string;
      /** Enabled */
      enabled: boolean;
    };
    /** PublishedCatalog */
    PublishedCatalog: {
      /** Filename */
      filename: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Product Count */
      product_count: number;
      /** Published At */
      published_at: string | null;
      /** Source Version */
      source_version: string;
    };
    /**
     * RankedCandidate
     * @description Search result card with debug-safe trace components.
     */
    "RankedCandidate-Input": {
      /** Branch Ranks */
      branch_ranks: {
        [key: string]: number | null;
      };
      /** Brand */
      brand: string | null;
      /** Category Path */
      category_path: string[];
      /** Constraint Matches */
      constraint_matches: {
        [key: string]: boolean;
      };
      /** Highlights */
      highlights: string[];
      /** Image Url */
      image_url?: string | null;
      price: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Score */
      score: number | string;
      score_components: components["schemas"]["ScoreComponents-Input"];
      /** Title */
      title: string;
      /** Url */
      url?: string | null;
    };
    /**
     * RankedCandidate
     * @description Search result card with debug-safe trace components.
     */
    "RankedCandidate-Output": {
      /** Branch Ranks */
      branch_ranks: {
        [key: string]: number | null;
      };
      /** Brand */
      brand: string | null;
      /** Category Path */
      category_path: string[];
      /** Constraint Matches */
      constraint_matches: {
        [key: string]: boolean;
      };
      /** Highlights */
      highlights: string[];
      /** Image Url */
      image_url?: string | null;
      price: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Score */
      score: string;
      score_components: components["schemas"]["ScoreComponents-Output"];
      /** Title */
      title: string;
      /** Url */
      url?: string | null;
    };
    /** RankingApproval */
    RankingApproval: {
      /** Artifact Hash */
      artifact_hash?: string | null;
      /**
       * Confirm
       * @enum {string}
       */
      confirm: "APPLY_LOCAL_RANKING" | "DISABLE_LOCAL_RANKING";
      /** Expected Active Id */
      expected_active_id: string | null;
      /** Model Id */
      model_id: string | null;
    };
    /** RankingModel */
    RankingModel: {
      /** Active */
      active: boolean;
      /** Artifact Hash */
      artifact_hash: string | null;
      /**
       * Catalog Id
       * Format: uuid
       */
      catalog_id: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Dataset Id
       * Format: uuid
       */
      dataset_id: string;
      /** Error */
      error: string | null;
      /** Goal */
      goal: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Method
       * @enum {string}
       */
      method: "popularity" | "logistic_regression";
      /** Metrics */
      metrics: {
        [key: string]: number | string | boolean | null;
      };
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "ready" | "failed";
      /**
       * Target
       * @enum {string}
       */
      target: "product_view" | "click" | "add_to_cart" | "purchase";
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /** RankingOverview */
    RankingOverview: {
      /** Catalog Id */
      catalog_id: string | null;
      dataset: components["schemas"]["EngagementSummary"] | null;
      /** Models */
      models: components["schemas"]["RankingModel"][];
    };
    /** RankingPreview */
    RankingPreview: {
      baseline: components["schemas"]["SearchResponse"];
      candidate: components["schemas"]["SearchResponse"];
    };
    /** RankingPreviewInput */
    RankingPreviewInput: {
      /**
       * Model Id
       * Format: uuid
       */
      model_id: string;
      /** Query */
      query: string;
    };
    /**
     * ReadinessResponse
     * @description Readiness response with per-dependency status.
     */
    ReadinessResponse: {
      /** Dependencies */
      dependencies: components["schemas"]["DependencyStatus"][];
      /**
       * Status
       * @enum {string}
       */
      status: "ready" | "not_ready";
    };
    /**
     * RecommendationControls
     * @description One PDP surface. Complements require explicit pairwise catalog evidence.
     */
    RecommendationControls: {
      /** Excluded Product Ids */
      excluded_product_ids?: string[];
      /**
       * Inventory Priority
       * @default 0
       */
      inventory_priority?: string;
      /**
       * Limit
       * @default 4
       */
      limit?: number;
      /**
       * Max Per Brand
       * @default 2
       */
      max_per_brand?: number;
      /**
       * Minimum Relevance
       * @default 0.55
       */
      minimum_relevance?: string;
      /**
       * Require Available
       * @default true
       * @constant
       */
      require_available?: true;
      /**
       * Strategy
       * @default alternatives
       * @enum {string}
       */
      strategy?: "alternatives" | "complements";
      /**
       * Surface
       * @default product_detail
       * @constant
       */
      surface?: "product_detail";
    };
    /**
     * RecommendationRequest
     * @description Recommendation request body.
     */
    RecommendationRequest: {
      /** Anchor Product Ids */
      anchor_product_ids?: string[];
      /**
       * Debug
       * @default false
       */
      debug?: boolean;
      /** Goal Context Id */
      goal_context_id?: string | null;
      /** Session Id */
      session_id?: string | null;
      /**
       * Surface
       * @default product_detail
       * @enum {string}
       */
      surface?: "product_detail" | "cart" | "home" | "search";
      /**
       * Top K
       * @default 10
       */
      top_k?: number;
      user_context?: components["schemas"]["SearchUserContext"] | null;
    };
    /**
     * RecommendationResponse
     * @description Recommendation response.
     */
    RecommendationResponse: {
      /** Policy Active */
      policy_active?: boolean | null;
      /** Policy Version */
      policy_version?: number | null;
      /**
       * Query Id
       * Format: uuid
       */
      query_id: string;
      /** Results */
      results: components["schemas"]["RankedCandidate-Output"][];
      /** Strategy */
      strategy: string;
      trace?: components["schemas"]["SearchTrace"] | null;
    };
    /**
     * ReconciliationResult
     * @description Observed provider state after a write attempt.
     */
    ReconciliationResult: {
      /** Details */
      details?: {
        [key: string]: unknown;
      };
      /**
       * Execution Id
       * Format: uuid
       */
      execution_id: string;
      /** Observed Remote State */
      observed_remote_state: {
        [key: string]: unknown;
      };
      status: components["schemas"]["ExecutionStatus"];
    };
    /** ReservationSummary */
    ReservationSummary: {
      /**
       * Checkout Id
       * Format: uuid
       */
      checkout_id: string;
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Product Id */
      product_id: string;
      /** Quantity */
      quantity: number;
      /**
       * Status
       * @enum {string}
       */
      status: "active" | "released" | "consumed" | "expired";
      /** Variant Id */
      variant_id: string;
    };
    /**
     * ResetSimulatorRequest
     * @description Reset an instance, optionally replacing the seed.
     */
    ResetSimulatorRequest: {
      /** Seed */
      seed?: number | null;
    };
    /**
     * ResultSetEvaluation
     * @description Evaluation of one result set.
     */
    ResultSetEvaluation: {
      /** Confidence */
      confidence: string;
      /** Coverage By Constraint */
      coverage_by_constraint: {
        [key: string]: string;
      };
      /**
       * Decision
       * @enum {string}
       */
      decision: "answer" | "clarify" | "retry" | "no_result";
      /** Hard Constraint Violations */
      hard_constraint_violations: string[];
      /** Result Diversity */
      result_diversity: string;
      retry_plan?: components["schemas"]["SearchRetryPlan"] | null;
    };
    /**
     * RiskAssessment
     * @description Risk tier and supporting details for a compiled action.
     */
    RiskAssessment: {
      /** Confidence */
      confidence: string;
      /** Reasons */
      reasons?: string[];
      tier: components["schemas"]["RiskTier"];
    };
    /**
     * RiskTier
     * @enum {string}
     */
    RiskTier:
      | "r0_read_only"
      | "r1_reversible_low"
      | "r2_reversible_material"
      | "r3_high_impact"
      | "r4_prohibited";
    /**
     * RollbackPlan
     * @description Rollback metadata prepared before execution.
     */
    RollbackPlan: {
      /** Action Type */
      action_type?: string | null;
      /** Available */
      available: boolean;
      /** Non Reversible Reason */
      non_reversible_reason?: string | null;
      /** Parameters */
      parameters?: {
        [key: string]: unknown;
      };
      /** Summary */
      summary: string;
    };
    /**
     * RuleEvaluation
     * @description Result of one explicit policy rule.
     */
    RuleEvaluation: {
      /** Code */
      code: string;
      /** Details */
      details?: {
        [key: string]: unknown;
      };
      /** Passed */
      passed: boolean;
      /** Reason */
      reason: string;
    };
    /**
     * RunListResponse
     * @description Run list response.
     */
    RunListResponse: {
      /** Items */
      items: components["schemas"]["ControllerRunRecord"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * RunTraceResponse
     * @description Trace response.
     */
    RunTraceResponse: {
      /** Items */
      items: components["schemas"]["ControllerTraceEvent"][];
      /** Next Cursor */
      next_cursor?: string | null;
      /**
       * Run Id
       * Format: uuid
       */
      run_id: string;
    };
    /**
     * RunUntilSimulatorRequest
     * @description Advance virtual time until a timestamp.
     */
    RunUntilSimulatorRequest: {
      /**
       * Timestamp
       * Format: date-time
       */
      timestamp: string;
    };
    /**
     * SafeError
     * @description Redacted error payload suitable for storage and APIs.
     */
    SafeError: {
      /** Code */
      code: string;
      /** Details */
      details?: {
        [key: string]: unknown;
      };
      /** Message */
      message: string;
      /**
       * Retryable
       * @default false
       */
      retryable?: boolean;
    };
    /**
     * ScenarioListResponse
     * @description Scenario collection response.
     */
    ScenarioListResponse: {
      /** Items */
      items: components["schemas"]["ScenarioSummary"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * ScenarioSummary
     * @description Public scenario listing item.
     */
    ScenarioSummary: {
      /** Capabilities */
      capabilities: components["schemas"]["Capability"][];
      /** Categories */
      categories: string[];
      /** Default Goal */
      default_goal: {
        [key: string]: unknown;
      };
      /** Default Policy */
      default_policy: {
        [key: string]: unknown;
      };
      /** Default Seed */
      default_seed: number;
      /** Description */
      description: string;
      /** Display Name */
      display_name: string;
      /**
       * Id
       * @enum {string}
       */
      id: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /** Product Count */
      product_count: number;
      /** Version */
      version: string;
    };
    /**
     * ScoreComponents
     * @description Inspectable score components.
     */
    "ScoreComponents-Input": {
      /** Dense */
      dense: number | string;
      /**
       * Engagement Boost
       * @default 0
       */
      engagement_boost?: number | string;
      /**
       * Exact Identifier
       * @default false
       */
      exact_identifier?: boolean;
      /** Final */
      final: number | string;
      /**
       * Goal Boost
       * @default 0
       */
      goal_boost?: number | string;
      /** Relevance */
      relevance: number | string;
      /** Rrf */
      rrf: number | string;
      /** Sparse */
      sparse: number | string;
      /**
       * Stock Penalty
       * @default 0
       */
      stock_penalty?: number | string;
    };
    /**
     * ScoreComponents
     * @description Inspectable score components.
     */
    "ScoreComponents-Output": {
      /** Dense */
      dense: string;
      /**
       * Engagement Boost
       * @default 0
       */
      engagement_boost?: string;
      /**
       * Exact Identifier
       * @default false
       */
      exact_identifier?: boolean;
      /** Final */
      final: string;
      /**
       * Goal Boost
       * @default 0
       */
      goal_boost?: string;
      /** Relevance */
      relevance: string;
      /** Rrf */
      rrf: string;
      /** Sparse */
      sparse: string;
      /**
       * Stock Penalty
       * @default 0
       */
      stock_penalty?: string;
    };
    /**
     * SearchEventInput
     * @description Public event batch item. Tenant comes from request context.
     */
    SearchEventInput: {
      /** Anonymous User Id */
      anonymous_user_id?: string | null;
      /** Event Id */
      event_id: string;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
      /** Position */
      position?: number | null;
      /** Product Id */
      product_id?: string | null;
      /** Query Id */
      query_id?: string | null;
      /** Ranking Version */
      ranking_version?: string | null;
      /** Session Id */
      session_id: string;
      /**
       * Surface
       * @enum {string}
       */
      surface: "search" | "product_detail" | "cart" | "home";
      type: components["schemas"]["EventType"];
      /** Variant Id */
      variant_id?: string | null;
    };
    /**
     * SearchIntent
     * @description Deterministic query interpretation.
     */
    SearchIntent: {
      /** Ambiguity */
      ambiguity?: string[];
      budget?: components["schemas"]["PriceRange"] | null;
      /** Category Hints */
      category_hints: string[];
      /** Confidence */
      confidence: string;
      /** Excluded Attributes */
      excluded_attributes?: {
        [key: string]: string[];
      };
      /** Lexical Terms */
      lexical_terms: string[];
      /** Normalized Query */
      normalized_query: string;
      /** Preferred Attributes */
      preferred_attributes?: {
        [key: string]: string[];
      };
      required_filters: components["schemas"]["ProductFilters"];
      /** Semantic Query */
      semantic_query: string;
      /**
       * Sort Preference
       * @default relevance
       * @enum {string}
       */
      sort_preference?: "relevance" | "price_asc" | "price_desc";
    };
    /**
     * SearchRequest
     * @description Public search request body. Tenant comes from request context.
     */
    SearchRequest: {
      /**
       * Debug
       * @default false
       */
      debug?: boolean;
      filters?: components["schemas"]["ProductFilters"] | null;
      /** Goal Context Id */
      goal_context_id?: string | null;
      /**
       * Mode
       * @default hybrid
       * @enum {string}
       */
      mode?: "sparse" | "dense" | "hybrid" | "hybrid_reranked" | "hybrid_boosted";
      /** Query */
      query: string;
      /** Session Id */
      session_id?: string | null;
      /**
       * Top K
       * @default 20
       */
      top_k?: number;
      user_context?: components["schemas"]["SearchUserContext"] | null;
    };
    /**
     * SearchResponse
     * @description Public search response.
     */
    SearchResponse: {
      /** Clarification */
      clarification?: string | null;
      evaluation: components["schemas"]["ResultSetEvaluation"];
      interpretation: components["schemas"]["SearchIntent"];
      /**
       * Query Id
       * Format: uuid
       */
      query_id: string;
      /** Ranking Version */
      ranking_version: string;
      /** Relaxed Preferences */
      relaxed_preferences?: string[];
      /** Results */
      results: components["schemas"]["RankedCandidate-Output"][];
      trace?: components["schemas"]["SearchTrace"] | null;
    };
    /**
     * SearchRetryPlan
     * @description Deterministic retry plan.
     */
    SearchRetryPlan: {
      /** Reason */
      reason: string;
      /** Relaxed Preferences */
      relaxed_preferences?: string[];
    };
    /**
     * SearchRule
     * @description Tenant-owned search boost rule.
     */
    SearchRule: {
      /** Category */
      category?: string | null;
      /**
       * Ends At
       * Format: date-time
       */
      ends_at: string;
      /** Evaluation Time */
      evaluation_time?: string | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Multiplier */
      multiplier: string;
      /** Product Ids */
      product_ids?: string[];
      /** Query Text */
      query_text: string;
      /** Reason */
      reason: string;
      /** Reason Action Id */
      reason_action_id?: string | null;
      /**
       * Starts At
       * Format: date-time
       */
      starts_at: string;
      /**
       * Status
       * @default active
       * @enum {string}
       */
      status?: "active" | "deleted";
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /**
     * SearchRuleListResponse
     * @description Search rule collection response.
     */
    SearchRuleListResponse: {
      /** Items */
      items: components["schemas"]["SearchRule"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * SearchTrace
     * @description Debug trace for search retrieval and ranking.
     */
    SearchTrace: {
      /**
       * Query Id
       * Format: uuid
       */
      query_id: string;
      /** Ranking Version */
      ranking_version: string;
      /** Results */
      results?: {
        [key: string]: unknown;
      }[];
      /** Retries */
      retries?: {
        [key: string]: unknown;
      }[];
      /** Retrieval */
      retrieval: {
        [key: string]: unknown;
      };
    };
    /**
     * SearchUserContext
     * @description Pseudonymous search context.
     */
    SearchUserContext: {
      /** Recent Product Ids */
      recent_product_ids?: string[];
    };
    /** SessionInfo */
    SessionInfo: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Current */
      current: boolean;
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
    };
    /** SessionList */
    SessionList: {
      /** Items */
      items: components["schemas"]["SessionInfo"][];
    };
    /**
     * SetCampaignBudgetIntent
     * @description Intent to change a simulated or future ads campaign budget.
     */
    SetCampaignBudgetIntent: {
      /** Campaign Id */
      campaign_id: string;
      current_budget: components["schemas"]["Money"];
      new_budget: components["schemas"]["Money"];
      /** Opportunity Ids */
      opportunity_ids: string[];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "set_campaign_budget";
    };
    /**
     * SetRecommendationPolicyIntent
     * @description Replace one finite, versioned PDP policy for a bounded window.
     */
    SetRecommendationPolicyIntent: {
      controls: components["schemas"]["RecommendationControls"];
      /** Expected Version */
      expected_version: number;
      /** Opportunity Ids */
      opportunity_ids: string[];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "set_recommendation_policy";
      window: components["schemas"]["TimeWindow"];
    };
    /**
     * SetSearchBoostIntent
     * @description Intent to create an internal search boost rule.
     */
    SetSearchBoostIntent: {
      /**
       * Ends At
       * Format: date-time
       */
      ends_at: string;
      /** Multiplier */
      multiplier: string;
      /** Opportunity Ids */
      opportunity_ids: string[];
      product_scope: components["schemas"]["ProductScope"];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Query Pattern */
      query_pattern: {
        [key: string]: unknown;
      };
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * Starts At
       * Format: date-time
       */
      starts_at: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "set_search_boost";
    };
    /** SetupStatus */
    SetupStatus: {
      /**
       * Login Method
       * @enum {string}
       */
      login_method: "local" | "oidc" | "legacy";
      /**
       * Profile
       * @enum {string}
       */
      profile: "legacy_demo" | "self_hosted" | "hosted";
      /** Setup Required */
      setup_required: boolean;
    };
    /**
     * SetVariantPriceIntent
     * @description Intent to set one or more variant prices.
     */
    SetVariantPriceIntent: {
      /** Changes */
      changes: components["schemas"]["VariantPriceChange"][];
      /** Current Versions */
      current_versions?: {
        [key: string]: number;
      } | null;
      /** Opportunity Ids */
      opportunity_ids: string[];
      /**
       * Proposed At
       * Format: date-time
       */
      proposed_at: string;
      /** Rationale */
      rationale: string;
      requested_by: components["schemas"]["ActorRef"];
      /**
       * Source Run Id
       * Format: uuid
       */
      source_run_id: string;
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "set_variant_price";
      window?: components["schemas"]["TimeWindow"] | null;
    };
    /** ShopperAccount */
    ShopperAccount: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Display Name */
      display_name: string;
      /** Expires At */
      expires_at?: string | null;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Is Guest
       * @default false
       */
      is_guest?: boolean;
      /**
       * Memory Enabled
       * @default true
       */
      memory_enabled?: boolean;
      /** Username */
      username: string;
    };
    /** ShopperAgentStep */
    ShopperAgentStep: {
      /** Detail */
      detail: string;
      /**
       * Stage
       * @enum {string}
       */
      stage: "understand" | "search" | "observe" | "respond" | "remember";
      /**
       * Status
       * @default completed
       * @enum {string}
       */
      status?: "completed" | "fallback" | "needs_input";
      /** Title */
      title: string;
    };
    /** ShopperAuthResponse */
    ShopperAuthResponse: {
      account: components["schemas"]["ShopperAccount"];
      /** Recovery Code */
      recovery_code?: string | null;
    };
    /** ShopperChatRequest */
    ShopperChatRequest: {
      /** Content */
      content: string;
      /** Conversation Id */
      conversation_id?: string | null;
      /** Expected Account Id */
      expected_account_id?: string | null;
    };
    /** ShopperChatResponse */
    ShopperChatResponse: {
      assistant_message: components["schemas"]["ShopperMessage"];
      conversation: components["schemas"]["ShopperConversation"];
      /** Memories Saved */
      memories_saved?: components["schemas"]["ShopperMemory"][];
      memory_created?: components["schemas"]["ShopperMemory"] | null;
      user_message: components["schemas"]["ShopperMessage"];
    };
    /** ShopperConversation */
    ShopperConversation: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Title */
      title: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
      /** Version */
      version: number;
    };
    /** ShopperConversationDetail */
    ShopperConversationDetail: {
      conversation: components["schemas"]["ShopperConversation"];
      /** Messages */
      messages: components["schemas"]["ShopperMessage"][];
    };
    /** ShopperConversationList */
    ShopperConversationList: {
      /** Items */
      items: components["schemas"]["ShopperConversation"][];
    };
    /**
     * ShopperDiscoveryResponse
     * @description Current manager-owned catalog state and bounded starter prompts.
     */
    ShopperDiscoveryResponse: {
      /** Catalog Name */
      catalog_name?: string | null;
      /**
       * Catalog Status
       * @default not_configured
       * @enum {string}
       */
      catalog_status?: "not_configured" | "queued" | "running" | "ready" | "failed";
      /**
       * Conversation Mode
       * @description Provider availability, not a connectivity check or answer-quality claim.
       * @default unknown
       * @enum {string}
       */
      conversation_mode?: "unknown" | "basic" | "model_configured";
      /**
       * Product Count
       * @default 0
       */
      product_count?: number;
      /** Suggestions */
      suggestions?: components["schemas"]["ShopperDiscoverySuggestion"][];
    };
    /**
     * ShopperDiscoverySuggestion
     * @description One catalog-grounded starter prompt for the shopper home view.
     */
    ShopperDiscoverySuggestion: {
      /** Category */
      category?: string | null;
      /** Image Url */
      image_url?: string | null;
      /** Label */
      label: string;
      /** Query */
      query: string;
    };
    /** ShopperGuestResponse */
    ShopperGuestResponse: {
      account: components["schemas"]["ShopperAccount"];
      /** Created */
      created: boolean;
      /** Recovery Code */
      recovery_code?: string | null;
    };
    /** ShopperLoginRequest */
    ShopperLoginRequest: {
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /** ShopperMemory */
    ShopperMemory: {
      /** Content */
      content: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
    };
    /** ShopperMemoryDeleteResponse */
    ShopperMemoryDeleteResponse: {
      /** Deleted */
      deleted: boolean;
      /**
       * Memory Id
       * Format: uuid
       */
      memory_id: string;
    };
    /** ShopperMemoryList */
    ShopperMemoryList: {
      /** Items */
      items: components["schemas"]["ShopperMemory"][];
    };
    /** ShopperMessage */
    ShopperMessage: {
      /** Content */
      content: string;
      /**
       * Conversation Id
       * Format: uuid
       */
      conversation_id: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Products */
      products?: components["schemas"]["ShopperProductCard"][];
      /**
       * Role
       * @enum {string}
       */
      role: "user" | "assistant";
      /** Steps */
      steps?: components["schemas"]["ShopperAgentStep"][];
    };
    /** ShopperOrderList */
    ShopperOrderList: {
      /** Items */
      items: components["schemas"]["OrderSummary"][];
      /** Next Offset */
      next_offset?: number | null;
      /**
       * Payment Mode
       * @default local_test
       * @constant
       */
      payment_mode?: "local_test";
    };
    /** ShopperProductCard */
    ShopperProductCard: {
      /** Brand */
      brand?: string | null;
      /**
       * Category
       * @default
       */
      category?: string;
      /** Currency */
      currency: string;
      /** Highlights */
      highlights?: string[];
      /** Image Url */
      image_url?: string | null;
      /** Price Minor */
      price_minor: number;
      /** Product Id */
      product_id: string;
      /** Score */
      score: string;
      /** Title */
      title: string;
      /** Url */
      url?: string | null;
    };
    /** ShopperRecovery */
    ShopperRecovery: {
      /**
       * Code
       * Format: password
       */
      code: string;
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /** ShopperRegisterRequest */
    ShopperRegisterRequest: {
      /** Display Name */
      display_name: string;
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /**
     * SimulatorMetricsResponse
     * @description Daily metric series response.
     */
    SimulatorMetricsResponse: {
      /**
       * Instance Id
       * Format: uuid
       */
      instance_id: string;
      /** Items */
      items: components["schemas"]["DailyMetrics"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * SimulatorStateResponse
     * @description Public state summary for a simulator instance.
     */
    SimulatorStateResponse: {
      /** Active Discounts */
      active_discounts: number;
      /** Active Search Boosts */
      active_search_boosts: number;
      /** Campaigns */
      campaigns: components["schemas"]["CampaignSummary"][];
      catalog: components["schemas"]["CatalogSummary"];
      /** Command Count */
      command_count: number;
      /**
       * Current Time
       * Format: date-time
       */
      current_time: string;
      /** Day */
      day: number;
      /** Engine Version */
      engine_version: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      latest_metrics: components["schemas"]["DailyMetrics"] | null;
      merchandising?: components["schemas"]["MerchandisingSummary"] | null;
      /**
       * Scenario Id
       * @enum {string}
       */
      scenario_id: "acquisition_v1" | "excess_inventory_v1" | "search_conversion_v1";
      /** Scenario Version */
      scenario_version: string;
      /** Seed */
      seed: number;
      /**
       * Start At
       * Format: date-time
       */
      start_at: string;
      /** State Hash */
      state_hash: string;
      /**
       * Status
       * @enum {string}
       */
      status: "created" | "running" | "completed";
      /**
       * Tenant Id
       * Format: uuid
       */
      tenant_id: string;
    };
    /** Storefront */
    Storefront: {
      /**
       * Checkout Mode
       * @default demo
       */
      checkout_mode?: string;
      /** Currency */
      currency: string;
      /** Description */
      description: string;
      /** Name */
      name: string;
      /**
       * Preview
       * @default false
       */
      preview?: boolean;
      /**
       * Sample Data
       * @default false
       */
      sample_data?: boolean;
      /** Slug */
      slug: string;
    };
    /** StoreImageIssue */
    StoreImageIssue: {
      /**
       * Next Action
       * @default Replace this product's image URL in a new catalog upload.
       */
      next_action?: string;
      /** Product Id */
      product_id: string;
      /** Title */
      title: string;
    };
    /** StoreMeasurements */
    StoreMeasurements: {
      /** Ai Requests Today */
      ai_requests_today: number;
      /** Cart Additions */
      cart_additions: number;
      /** Demo Checkouts */
      demo_checkouts: number;
      /**
       * Preview And Sample Excluded
       * @default true
       */
      preview_and_sample_excluded?: boolean;
      /** Product Selections */
      product_selections: number;
      /** Reserved Tokens Today */
      reserved_tokens_today: number;
      /**
       * Searchers With Selection
       * @default 0
       */
      searchers_with_selection?: number;
      /**
       * Searching Accounts
       * @default 0
       */
      searching_accounts?: number;
      /** Seconds To First Preview */
      seconds_to_first_preview: number | null;
      /** Setup Complete */
      setup_complete: boolean;
      /** Successful Searches */
      successful_searches: number;
    };
    /** StoreProfile */
    StoreProfile: {
      /**
       * Currency
       * @default USD
       */
      currency?: string;
      /**
       * Description
       * @default
       */
      description?: string;
      /**
       * Goal
       * @default Help shoppers find suitable products
       */
      goal?: string;
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /** Published Catalog Id */
      published_catalog_id?: string | null;
      /** Readiness */
      readiness?: {
        [key: string]: boolean | string | number | null;
      };
      /**
       * Sample Data
       * @default false
       */
      sample_data?: boolean;
      /**
       * Sharing Enabled
       * @default false
       */
      sharing_enabled?: boolean;
      /** Slug */
      slug: string;
    };
    /** StoreProfileUpdate */
    StoreProfileUpdate: {
      /**
       * Currency
       * @default USD
       * @enum {string}
       */
      currency?: "USD" | "EUR" | "GBP" | "CAD" | "AUD";
      /**
       * Description
       * @default
       */
      description?: string;
      /**
       * Goal
       * @default Help shoppers find suitable products
       */
      goal?: string;
      /** Name */
      name: string;
    };
    /** StoreReadiness */
    StoreReadiness: {
      /** Checklist */
      checklist: {
        [key: string]: boolean;
      };
      /** Image Failures */
      image_failures: number;
      /** Image Issues */
      image_issues?: components["schemas"]["StoreImageIssue"][];
      /**
       * Image Issues Truncated
       * @default false
       */
      image_issues_truncated?: boolean;
      indexing: components["schemas"]["CatalogIndexStatus"];
      /** Latest Import Id */
      latest_import_id: string | null;
      store: components["schemas"]["StoreProfile"];
    };
    /**
     * TimeWindow
     * @description Inclusive-exclusive time window.
     */
    TimeWindow: {
      /**
       * End At
       * Format: date-time
       */
      end_at: string;
      /**
       * Start At
       * Format: date-time
       */
      start_at: string;
    };
    /** TrainRankingInput */
    TrainRankingInput: {
      /** Goal */
      goal: string;
      /**
       * Method
       * @enum {string}
       */
      method: "popularity" | "logistic_regression";
      /**
       * Target
       * @enum {string}
       */
      target: "product_view" | "click" | "add_to_cart" | "purchase";
    };
    /**
     * VariantPriceChange
     * @description Requested variant price change.
     */
    VariantPriceChange: {
      current_price: components["schemas"]["Money"];
      new_price: components["schemas"]["Money"];
      /** Product Id */
      product_id: string;
      /** Variant Id */
      variant_id: string;
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  live_health_live_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LiveResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  ready_health_ready_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ReadinessResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ReadinessResponse"];
        };
      };
    };
  };
  list_actions_v1_actions_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        goal_id?: string | null;
        limit?: number;
        run_id?: string | null;
        status?: components["schemas"]["ActionStatus"] | null;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ActionListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_action_v1_actions__action_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerActionRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  approve_action_v1_actions__action_id__approve_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ActionApprovalRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerActionRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_action_audit_v1_actions__action_id__audit_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ActionAuditResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  cancel_action_v1_actions__action_id__cancel_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerActionRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  execute_action_v1_actions__action_id__execute_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerActionRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  reject_action_v1_actions__action_id__reject_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ActionApprovalRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerActionRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  rollback_action_v1_actions__action_id__rollback_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        action_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerActionRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_audit_feed_v1_audit_get: {
    parameters: {
      query?: {
        action_id?: string | null;
        cursor?: string | null;
        event_type?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AuditFeedResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_capabilities_v1_capabilities_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CapabilitiesResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_catalog_inventory_v1_catalog_inventory_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        instance_id?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["InventoryResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_catalog_products_v1_catalog_products_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        instance_id?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ProductListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_catalog_product_v1_catalog_products__product_id__get: {
    parameters: {
      query?: {
        instance_id?: string | null;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        product_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ProductDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_controller_graph_v1_controller_graph_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerGraphResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  ingest_event_batch_v1_events_batch_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EventBatchRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventBatchResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_goals_v1_goals_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  create_goal_v1_goals_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["GoalCreateRequest-Input"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_goal_v1_goals__goal_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  update_goal_v1_goals__goal_id__patch: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["GoalUpdateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  activate_goal_v1_goals__goal_id__activate_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  archive_goal_v1_goals__goal_id__archive_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_merchandising_evidence_v1_goals__goal_id__merchandising__view__get: {
    parameters: {
      query?: {
        category?: string | null;
        product_id?: string | null;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
        view:
          | "economics"
          | "pricing"
          | "products"
          | "inventory"
          | "outcomes"
          | "search"
          | "recommendations";
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MerchandisingEvidenceResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  pause_goal_v1_goals__goal_id__pause_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_goal_progress_v1_goals__goal_id__progress_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalProgressResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  run_goal_v1_goals__goal_id__run_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        goal_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ControllerRunRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerRunRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  draft_goal_route_v1_goals_draft_post: {
    parameters: {
      query?: never;
      header?: {
        "Idempotency-Key"?: string | null;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["GoalDraftRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalDraftResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  review_goal_configuration_v1_goals_review_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["GoalCreateRequest-Input"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GoalDraftResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_interventions_v1_interventions_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
        status?: components["schemas"]["ActionStatus"] | null;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["InterventionListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_kill_switch_v1_kill_switch_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KillSwitchResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  disable_kill_switch_v1_kill_switch_disable_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KillSwitchResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  enable_kill_switch_v1_kill_switch_enable_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KillSwitchResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  manager_activity_v1_manager_activity_get: {
    parameters: {
      query?: {
        empty_results_only?: boolean;
        include_test_sessions?: boolean;
        kind?: components["schemas"]["ActivityKind"] | null;
        status?: ("ok" | "error" | "fallback") | null;
        window_minutes?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ActivityOverview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  manager_activity_rule_v1_manager_activity_rules_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ActivityRuleInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ActivityRule"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  browse_manager_catalog_v1_manager_catalog_get: {
    parameters: {
      query?: {
        category?: string;
        in_stock?: boolean;
        limit?: number;
        offset?: number;
        product_id?: string | null;
        q?: string;
        sort?: "title" | "title_desc" | "price_asc" | "price_desc";
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CatalogBrowseResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_commerce_overview_v1_manager_commerce_overview_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CommerceOverview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  check_shopify_v1_manager_connectors_shopify_check_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CatalogConnection"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  import_shopify_v1_manager_connectors_shopify_import_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CatalogIndexStatus"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_manager_memories_v1_manager_memories_get: {
    parameters: {
      query?: {
        layer?: ("long_term" | "working" | "periodic") | null;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerMemoryListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  delete_manager_memory_v1_manager_memories__memory_id__delete: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        memory_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerMemoryDeleteResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  ranking_overview_v1_manager_ranking_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RankingOverview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  approve_ranking_v1_manager_ranking_approve_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RankingApproval"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RankingOverview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  preview_ranking_v1_manager_ranking_preview_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RankingPreviewInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RankingPreview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  train_ranking_v1_manager_ranking_train_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TrainRankingInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RankingModel"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_run_v1_manager_runs__run_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerRun"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  cancel_manager_run_v1_manager_runs__run_id__cancel_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerRun"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_run_events_v1_manager_runs__run_id__events_get: {
    parameters: {
      query?: {
        after?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerRunEvents"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_runtime_status_v1_manager_status_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerRuntimeStatus"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_manager_threads_v1_manager_threads_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerThreadListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  create_manager_thread_v1_manager_threads_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerThreadCreateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerThreadDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_reply_thread_v1_manager_threads__channel_id__messages__root_message_id__replies_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        channel_id: string;
        root_message_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerThreadDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  create_manager_reply_thread_v1_manager_threads__channel_id__replies_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        channel_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerReplyThreadCreateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerThreadDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_thread_v1_manager_threads__thread_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        thread_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerThreadDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  update_manager_thread_v1_manager_threads__thread_id__patch: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        thread_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerThreadUpdateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerThreadDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  profile_manager_dataset_v1_manager_threads__thread_id__datasets_profile_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        thread_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerDatasetProfileRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerDatasetProfileReply"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  send_manager_message_v1_manager_threads__thread_id__messages_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        thread_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerMessageRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerAgentReply"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  clear_manager_channel_history_v1_manager_threads__thread_id__messages_delete: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        thread_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerChannelClearResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  create_manager_run_v1_manager_threads__thread_id__runs_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        thread_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerMessageRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerRun"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_manager_workspace_v1_manager_workspace_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerWorkspaceResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  bootstrap_manager_workspace_v1_manager_workspace_bootstrap_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerWorkspaceResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  reset_manager_workspace_v1_manager_workspace_reset_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManagerWorkspaceResetRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerWorkspaceResetResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_owner_asset_v1_merchant_assets__asset_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        asset_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  login_owner_v1_merchant_auth_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["OwnerLoginRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["OwnerAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  logout_owner_v1_merchant_auth_logout_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  owner_me_v1_merchant_auth_me_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["OwnerAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  oidc_callback_v1_merchant_auth_oidc_callback_get: {
    parameters: {
      query: {
        code: string;
        state: string;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  oidc_start_v1_merchant_auth_oidc_start_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  recover_owner_v1_merchant_auth_recover_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["OwnerRecoveryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["OwnerAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  owner_sessions_v1_merchant_auth_sessions_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SessionList"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  revoke_owner_session_v1_merchant_auth_sessions__session_id__delete: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        session_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  setup_owner_v1_merchant_auth_setup_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["OwnerSetupRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["OwnerAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  setup_status_v1_merchant_auth_status_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SetupStatus"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_import_v1_merchant_imports__import_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        import_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  cancel_import_v1_merchant_imports__import_id__cancel_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        import_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  confirm_import_v1_merchant_imports__import_id__confirm_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        import_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ImportConfirmRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  map_import_v1_merchant_imports__import_id__mapping_put: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        import_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ImportMapping"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  retry_import_v1_merchant_imports__import_id__retry_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        import_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  sample_catalog_v1_merchant_imports_sample_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  upload_catalog_v1_merchant_imports_upload_post: {
    parameters: {
      query?: {
        filename?: string;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportReview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_store_v1_merchant_store_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreReadiness"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  update_store_v1_merchant_store_patch: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["StoreProfileUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreProfile"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  check_ai_v1_merchant_store_check_ai_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AIConnection"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_measurements_v1_merchant_store_measurements_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreMeasurements"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  setup_monitor_v1_merchant_store_monitors_put: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MonitoringPreset"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreReadiness"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  preview_store_v1_merchant_store_preview_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CatalogSelection"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  share_store_v1_merchant_store_sharing_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PublicationRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreProfile"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  meta_v1_meta_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MetaResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_metric_definitions_v1_metrics_definitions_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MetricsDefinitionsResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_metrics_series_v1_metrics_series_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        instance_id?: string | null;
        limit?: number;
        metric?: components["schemas"]["MetricName"];
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MetricsSeriesResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_metrics_summary_v1_metrics_summary_get: {
    parameters: {
      query?: {
        instance_id?: string | null;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MetricsSummaryResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_policy_v1_policy_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerPolicyConfig"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  update_policy_v1_policy_put: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PolicyUpdateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerPolicyConfig"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_policy_history_v1_policy_history_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PolicyHistoryResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  validate_policy_v1_policy_validate_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PolicyValidateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PolicyValidationResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  recommend_products_v1_recommendations_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecommendationRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RecommendationResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_runs_v1_runs_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        goal_id?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RunListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_run_v1_runs__run_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerRunRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  cancel_run_v1_runs__run_id__cancel_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerRunRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_run_events_v1_runs__run_id__events_get: {
    parameters: {
      query?: never;
      header?: {
        "Last-Event-ID"?: string | null;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "text/event-stream": unknown;
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  resume_run_v1_runs__run_id__resume_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ControllerRunRecord"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_run_trace_v1_runs__run_id__trace_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RunTraceResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  search_products_v1_search_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SearchRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SearchResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  evaluate_search_v1_search_evaluate_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EvaluateSearchRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ResultSetEvaluation"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  parse_search_v1_search_parse_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SearchRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ParseSearchResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_search_rules_v1_search_rules_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        goal_context_id?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SearchRuleListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  shopper_activity_v1_shopper_activity_get: {
    parameters: {
      query?: {
        empty_results_only?: boolean;
        include_test_sessions?: boolean;
        kind?: components["schemas"]["ActivityKind"] | null;
        status?: ("ok" | "error" | "fallback") | null;
        window_minutes?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ActivityOverview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  shopper_activity_rule_v1_shopper_activity_rules_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ActivityRuleInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ActivityRule"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_asset_v1_shopper_assets__asset_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        asset_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  guest_shopper_v1_shopper_auth_guest_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperGuestResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  login_shopper_v1_shopper_auth_login_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ShopperLoginRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ContinuityResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  logout_shopper_v1_shopper_auth_logout_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  merge_shopper_v1_shopper_auth_merge_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MergeSelection"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ContinuityResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  recover_shopper_v1_shopper_auth_recover_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ShopperRecovery"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  register_shopper_v1_shopper_auth_register_post: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ShopperRegisterRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  shopper_sessions_v1_shopper_auth_sessions_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SessionList"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  revoke_shopper_sessions_v1_shopper_auth_sessions_delete: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_shopper_cart_v1_shopper_cart_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Cart"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  add_shopper_cart_item_v1_shopper_cart_items_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CartItemAddRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Cart"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  delete_shopper_cart_item_v1_shopper_cart_items__line_id__delete: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path: {
        line_id: string;
      };
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Cart"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  update_shopper_cart_item_v1_shopper_cart_items__line_id__patch: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path: {
        line_id: string;
      };
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CartItemUpdateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Cart"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  browse_shopper_catalog_v1_shopper_catalog_get: {
    parameters: {
      query?: {
        category?: string;
        in_stock?: boolean;
        limit?: number;
        offset?: number;
        product_id?: string | null;
        q?: string;
        sort?: "title" | "title_desc" | "price_asc" | "price_desc";
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CatalogBrowseResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  chat_with_shopper_agent_v1_shopper_chat_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ShopperChatRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperChatResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_shopper_checkout_v1_shopper_checkout__checkout_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path: {
        checkout_id: string;
      };
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CheckoutRecovery"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  confirm_shopper_checkout_v1_shopper_checkout_confirm_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CheckoutConfirmRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CheckoutConfirmation"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  current_shopper_checkout_v1_shopper_checkout_current_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CheckoutRecovery"] | null;
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  preview_shopper_checkout_v1_shopper_checkout_preview_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CheckoutPreviewRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CheckoutPreview"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_shopper_conversations_v1_shopper_conversations_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperConversationList"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_shopper_conversation_v1_shopper_conversations__conversation_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path: {
        conversation_id: string;
      };
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperConversationDetail"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_shopper_discovery_v1_shopper_discovery_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperDiscoveryResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_shopper_account_v1_shopper_me_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_shopper_memories_v1_shopper_memories_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperMemoryList"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  delete_shopper_memory_v1_shopper_memories__memory_id__delete: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path: {
        memory_id: string;
      };
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperMemoryDeleteResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  shopper_orders_v1_shopper_orders_get: {
    parameters: {
      query?: {
        limit?: number;
        offset?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperOrderList"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  set_preferences_v1_shopper_preferences_patch: {
    parameters: {
      query?: never;
      header?: {
        "Idempotency-Key"?: string | null;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PreferenceSettings"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShopperAuthResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  record_product_selection_v1_shopper_product_selections_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CartItemAddRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  delete_shopping_data_v1_shopper_shopping_data_delete: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
        /** @description Expected current shopper; a precondition, not authentication. */
        "X-Shopper-Account-Id"?: string | null;
      };
      path?: never;
      cookie?: {
        open_commerce_shopper_session?: string | null;
      };
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_storefront_v1_shopper_store_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Storefront"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  create_simulator_instance_alias_v1_simulator_instances_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateSimulatorInstanceAliasRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_simulator_instance_alias_v1_simulator_instances__instance_id__get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  advance_simulator_instance_v1_simulator_instances__instance_id__advance_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AdvanceSimulatorRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  compare_simulator_baseline_v1_simulator_instances__instance_id__compare_baseline_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BaselineComparisonResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_simulator_metrics_v1_simulator_instances__instance_id__metrics_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorMetricsResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  reset_simulator_instance_v1_simulator_instances__instance_id__reset_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ResetSimulatorRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  run_simulator_until_v1_simulator_instances__instance_id__run_until_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RunUntilSimulatorRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  get_simulator_state_v1_simulator_instances__instance_id__state_get: {
    parameters: {
      query?: never;
      header?: {
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        instance_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  list_simulator_scenarios_v1_simulator_scenarios_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ScenarioListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  create_simulator_instance_v1_simulator_scenarios__scenario_id__instances_post: {
    parameters: {
      query?: never;
      header: {
        "Idempotency-Key": string;
        /** @description Expected owner; supply with X-Merchant-Store-Id. */
        "X-Merchant-Owner-Id"?: string | null;
        /** @description Expected store; supply with X-Merchant-Owner-Id. */
        "X-Merchant-Store-Id"?: string | null;
      };
      path: {
        scenario_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateSimulatorInstanceRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SimulatorStateResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
  exchange_preview_v1_stores__slug__preview_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        slug: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["PreviewExchange"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Storefront"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Method Not Allowed */
      405: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Precondition Failed */
      412: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Entity Too Large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Request Header Fields Too Large */
      431: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
      /** @description Service Unavailable */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorEnvelope"];
        };
      };
    };
  };
}

export type AIConnection = components["schemas"]["AIConnection"];
export type ActionApprovalRequest = components["schemas"]["ActionApprovalRequest"];
export type ActionAuditEntry = components["schemas"]["ActionAuditEntry"];
export type ActionAuditResponse = components["schemas"]["ActionAuditResponse"];
export type ActionListResponse = components["schemas"]["ActionListResponse"];
export type ActionStatus = components["schemas"]["ActionStatus"];
export type ActionType = components["schemas"]["ActionType"];
export type ActivityCheck = components["schemas"]["ActivityCheck"];
export type ActivityEvent = components["schemas"]["ActivityEvent"];
export type ActivityKind = components["schemas"]["ActivityKind"];
export type ActivityOverview = components["schemas"]["ActivityOverview"];
export type ActivityQuery = components["schemas"]["ActivityQuery"];
export type ActivityRule = components["schemas"]["ActivityRule"];
export type ActivityRuleInput = components["schemas"]["ActivityRuleInput"];
export type ActorRef = components["schemas"]["ActorRef"];
export type ActorRole = components["schemas"]["ActorRole"];
export type AdvanceSimulatorRequest = components["schemas"]["AdvanceSimulatorRequest"];
export type AgentStep = components["schemas"]["AgentStep"];
export type ApiError = components["schemas"]["ApiError"];
export type Approval = components["schemas"]["Approval"];
export type ApprovalRequest = components["schemas"]["ApprovalRequest"];
export type AuditFeedEntry = components["schemas"]["AuditFeedEntry"];
export type AuditFeedResponse = components["schemas"]["AuditFeedResponse"];
export type AutonomyMode = components["schemas"]["AutonomyMode"];
export type AutonomyPolicy = components["schemas"]["AutonomyPolicy"];
export type BaselineComparisonResponse = components["schemas"]["BaselineComparisonResponse"];
export type BudgetReservationRequest = components["schemas"]["BudgetReservationRequest"];
export type BudgetSpec = components["schemas"]["BudgetSpec"];
export type CampaignSummary = components["schemas"]["CampaignSummary"];
export type CapabilitiesResponse = components["schemas"]["CapabilitiesResponse"];
export type Capability = components["schemas"]["Capability"];
export type CapabilitySummary = components["schemas"]["CapabilitySummary"];
export type Cart = components["schemas"]["Cart"];
export type CartChoiceLine = components["schemas"]["CartChoiceLine"];
export type CartItemAddRequest = components["schemas"]["CartItemAddRequest"];
export type CartItemUpdateRequest = components["schemas"]["CartItemUpdateRequest"];
export type CartLine = components["schemas"]["CartLine"];
export type CatalogBrowseProduct = components["schemas"]["CatalogBrowseProduct"];
export type CatalogBrowseResponse = components["schemas"]["CatalogBrowseResponse"];
export type CatalogConnection = components["schemas"]["CatalogConnection"];
export type CatalogIndexStatus = components["schemas"]["CatalogIndexStatus"];
export type CatalogProductInput = components["schemas"]["CatalogProductInput"];
export type CatalogSelection = components["schemas"]["CatalogSelection"];
export type CatalogSummary = components["schemas"]["CatalogSummary"];
export type CatalogVariant = components["schemas"]["CatalogVariant"];
export type CatalogVariantInput = components["schemas"]["CatalogVariantInput"];
export type CheckoutConfirmRequest = components["schemas"]["CheckoutConfirmRequest"];
export type CheckoutConfirmation = components["schemas"]["CheckoutConfirmation"];
export type CheckoutLine = components["schemas"]["CheckoutLine"];
export type CheckoutPreview = components["schemas"]["CheckoutPreview"];
export type CheckoutPreviewRequest = components["schemas"]["CheckoutPreviewRequest"];
export type CheckoutRecovery = components["schemas"]["CheckoutRecovery"];
export type CommerceInventoryItem = components["schemas"]["CommerceInventoryItem"];
export type CommerceOverview = components["schemas"]["CommerceOverview"];
export type CommercePolicyDecision = components["schemas"]["CommercePolicyDecision"];
export type CompiledAction = components["schemas"]["CompiledAction"];
export type ConfidenceInterval = components["schemas"]["ConfidenceInterval"];
export type ConstraintOperator = components["schemas"]["ConstraintOperator"];
export type ConstraintSpecInput = components["schemas"]["ConstraintSpec-Input"];
export type ConstraintSpec = components["schemas"]["ConstraintSpec-Output"];
export type ContinuityResponse = components["schemas"]["ContinuityResponse"];
export type ControllerActionRecord = components["schemas"]["ControllerActionRecord"];
export type ControllerGraphResponse = components["schemas"]["ControllerGraphResponse"];
export type ControllerPolicyConfig = components["schemas"]["ControllerPolicyConfig"];
export type ControllerRunRecord = components["schemas"]["ControllerRunRecord"];
export type ControllerRunRequest = components["schemas"]["ControllerRunRequest"];
export type ControllerTraceEvent = components["schemas"]["ControllerTraceEvent"];
export type CreateDiscountIntent = components["schemas"]["CreateDiscountIntent"];
export type CreateSimulatorInstanceAliasRequest =
  components["schemas"]["CreateSimulatorInstanceAliasRequest"];
export type CreateSimulatorInstanceRequest =
  components["schemas"]["CreateSimulatorInstanceRequest"];
export type CustomerScope = components["schemas"]["CustomerScope"];
export type DailyMetrics = components["schemas"]["DailyMetrics"];
export type DataSourceDraft = components["schemas"]["DataSourceDraft"];
export type DatasetProfile = components["schemas"]["DatasetProfile"];
export type DependencyStatus = components["schemas"]["DependencyStatus"];
export type DisableDiscountIntent = components["schemas"]["DisableDiscountIntent"];
export type DiscoveryObjectiveDraft = components["schemas"]["DiscoveryObjectiveDraft"];
export type EngagementSummary = components["schemas"]["EngagementSummary"];
export type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];
export type EvaluateSearchRequest = components["schemas"]["EvaluateSearchRequest"];
export type EvaluationSchedule = components["schemas"]["EvaluationSchedule"];
export type EventBatchRequest = components["schemas"]["EventBatchRequest"];
export type EventBatchResponse = components["schemas"]["EventBatchResponse"];
export type EventType = components["schemas"]["EventType"];
export type EvidenceItem = components["schemas"]["EvidenceItem"];
export type ExecutionStatus = components["schemas"]["ExecutionStatus"];
export type GoalAssessment = components["schemas"]["GoalAssessment"];
export type GoalCreateRequestInput = components["schemas"]["GoalCreateRequest-Input"];
export type GoalCreateRequest = components["schemas"]["GoalCreateRequest-Output"];
export type GoalDraftRequest = components["schemas"]["GoalDraftRequest"];
export type GoalDraftResponse = components["schemas"]["GoalDraftResponse"];
export type GoalListResponse = components["schemas"]["GoalListResponse"];
export type GoalProgressResponse = components["schemas"]["GoalProgressResponse"];
export type GoalRecord = components["schemas"]["GoalRecord"];
export type GoalSpec = components["schemas"]["GoalSpec"];
export type GoalStatus = components["schemas"]["GoalStatus"];
export type GoalUpdateRequest = components["schemas"]["GoalUpdateRequest"];
export type HorizonSpec = components["schemas"]["HorizonSpec"];
export type Hypothesis = components["schemas"]["Hypothesis"];
export type ImpactEstimate = components["schemas"]["ImpactEstimate"];
export type ImportConfirmRequest = components["schemas"]["ImportConfirmRequest"];
export type ImportIssue = components["schemas"]["ImportIssue"];
export type ImportMapping = components["schemas"]["ImportMapping"];
export type ImportReview = components["schemas"]["ImportReview"];
export type IntentDraft = components["schemas"]["IntentDraft"];
export type InterventionListResponse = components["schemas"]["InterventionListResponse"];
export type InterventionSummary = components["schemas"]["InterventionSummary"];
export type InventoryItem = components["schemas"]["InventoryItem"];
export type InventoryResponse = components["schemas"]["InventoryResponse"];
export type KillSwitchResponse = components["schemas"]["KillSwitchResponse"];
export type LiveResponse = components["schemas"]["LiveResponse"];
export type ManagerAgentCapabilities = components["schemas"]["ManagerAgentCapabilities"];
export type ManagerAgentReply = components["schemas"]["ManagerAgentReply"];
export type ManagerChannelClearResponse = components["schemas"]["ManagerChannelClearResponse"];
export type ManagerDataOnboarding = components["schemas"]["ManagerDataOnboarding"];
export type ManagerDatasetProfileReply = components["schemas"]["ManagerDatasetProfileReply"];
export type ManagerDatasetProfileRequest = components["schemas"]["ManagerDatasetProfileRequest"];
export type ManagerMemory = components["schemas"]["ManagerMemory"];
export type ManagerMemoryDeleteResponse = components["schemas"]["ManagerMemoryDeleteResponse"];
export type ManagerMemoryListResponse = components["schemas"]["ManagerMemoryListResponse"];
export type ManagerMessage = components["schemas"]["ManagerMessage"];
export type ManagerMessageRequest = components["schemas"]["ManagerMessageRequest"];
export type ManagerReplyThreadCreateRequest =
  components["schemas"]["ManagerReplyThreadCreateRequest"];
export type ManagerRun = components["schemas"]["ManagerRun"];
export type ManagerRunEvent = components["schemas"]["ManagerRunEvent"];
export type ManagerRunEvents = components["schemas"]["ManagerRunEvents"];
export type ManagerRuntimeComponent = components["schemas"]["ManagerRuntimeComponent"];
export type ManagerRuntimeStatus = components["schemas"]["ManagerRuntimeStatus"];
export type ManagerThread = components["schemas"]["ManagerThread"];
export type ManagerThreadCreateRequest = components["schemas"]["ManagerThreadCreateRequest"];
export type ManagerThreadDetail = components["schemas"]["ManagerThreadDetail"];
export type ManagerThreadListResponse = components["schemas"]["ManagerThreadListResponse"];
export type ManagerThreadUpdateRequest = components["schemas"]["ManagerThreadUpdateRequest"];
export type ManagerWorkingMemory = components["schemas"]["ManagerWorkingMemory"];
export type ManagerWorkspaceProfile = components["schemas"]["ManagerWorkspaceProfile"];
export type ManagerWorkspaceResetRequest = components["schemas"]["ManagerWorkspaceResetRequest"];
export type ManagerWorkspaceResetResponse = components["schemas"]["ManagerWorkspaceResetResponse"];
export type ManagerWorkspaceResponse = components["schemas"]["ManagerWorkspaceResponse"];
export type MeasurementOutcome = components["schemas"]["MeasurementOutcome"];
export type MeasurementSchedule = components["schemas"]["MeasurementSchedule"];
export type MerchandisingConstraintsInput = components["schemas"]["MerchandisingConstraints-Input"];
export type MerchandisingConstraints = components["schemas"]["MerchandisingConstraints-Output"];
export type MerchandisingEvidenceResponse = components["schemas"]["MerchandisingEvidenceResponse"];
export type MerchandisingSummary = components["schemas"]["MerchandisingSummary"];
export type MergeSelection = components["schemas"]["MergeSelection"];
export type MetaResponse = components["schemas"]["MetaResponse"];
export type MetricDefinition = components["schemas"]["MetricDefinition"];
export type MetricName = components["schemas"]["MetricName"];
export type MetricSeriesPoint = components["schemas"]["MetricSeriesPoint"];
export type MetricTotals = components["schemas"]["MetricTotals"];
export type MetricsDefinitionsResponse = components["schemas"]["MetricsDefinitionsResponse"];
export type MetricsSeriesResponse = components["schemas"]["MetricsSeriesResponse"];
export type MetricsSummaryResponse = components["schemas"]["MetricsSummaryResponse"];
export type Money = components["schemas"]["Money"];
export type MonitoringPreset = components["schemas"]["MonitoringPreset"];
export type NoOpIntent = components["schemas"]["NoOpIntent"];
export type ObjectiveDirection = components["schemas"]["ObjectiveDirection"];
export type ObjectiveSpec = components["schemas"]["ObjectiveSpec"];
export type ObservationSnapshot = components["schemas"]["ObservationSnapshot"];
export type OnboardingChoice = components["schemas"]["OnboardingChoice"];
export type OnboardingPrompt = components["schemas"]["OnboardingPrompt"];
export type Opportunity = components["schemas"]["Opportunity"];
export type OrderSummary = components["schemas"]["OrderSummary"];
export type OwnerAuthResponse = components["schemas"]["OwnerAuthResponse"];
export type OwnerLoginRequest = components["schemas"]["OwnerLoginRequest"];
export type OwnerRecoveryRequest = components["schemas"]["OwnerRecoveryRequest"];
export type OwnerSetupRequest = components["schemas"]["OwnerSetupRequest"];
export type ParseSearchResponse = components["schemas"]["ParseSearchResponse"];
export type PaymentAttemptSummary = components["schemas"]["PaymentAttemptSummary"];
export type PolicyDecision = components["schemas"]["PolicyDecision"];
export type PolicyHistoryEntry = components["schemas"]["PolicyHistoryEntry"];
export type PolicyHistoryResponse = components["schemas"]["PolicyHistoryResponse"];
export type PolicyOutcome = components["schemas"]["PolicyOutcome"];
export type PolicyUpdateRequest = components["schemas"]["PolicyUpdateRequest"];
export type PolicyValidateRequest = components["schemas"]["PolicyValidateRequest"];
export type PolicyValidationResponse = components["schemas"]["PolicyValidationResponse"];
export type Precondition = components["schemas"]["Precondition"];
export type PreferenceSettings = components["schemas"]["PreferenceSettings"];
export type PreviewExchange = components["schemas"]["PreviewExchange"];
export type PreviewResponse = components["schemas"]["PreviewResponse"];
export type PriceRange = components["schemas"]["PriceRange"];
export type ProductDetail = components["schemas"]["ProductDetail"];
export type ProductFilters = components["schemas"]["ProductFilters"];
export type ProductListResponse = components["schemas"]["ProductListResponse"];
export type ProductScope = components["schemas"]["ProductScope"];
export type ProductSummary = components["schemas"]["ProductSummary"];
export type ProductVariantSummary = components["schemas"]["ProductVariantSummary"];
export type ProviderRef = components["schemas"]["ProviderRef"];
export type ProviderResult = components["schemas"]["ProviderResult"];
export type PublicationRequest = components["schemas"]["PublicationRequest"];
export type PublishedCatalog = components["schemas"]["PublishedCatalog"];
export type RankedCandidateInput = components["schemas"]["RankedCandidate-Input"];
export type RankedCandidate = components["schemas"]["RankedCandidate-Output"];
export type RankingApproval = components["schemas"]["RankingApproval"];
export type RankingModel = components["schemas"]["RankingModel"];
export type RankingOverview = components["schemas"]["RankingOverview"];
export type RankingPreview = components["schemas"]["RankingPreview"];
export type RankingPreviewInput = components["schemas"]["RankingPreviewInput"];
export type ReadinessResponse = components["schemas"]["ReadinessResponse"];
export type RecommendationControls = components["schemas"]["RecommendationControls"];
export type RecommendationRequest = components["schemas"]["RecommendationRequest"];
export type RecommendationResponse = components["schemas"]["RecommendationResponse"];
export type ReconciliationResult = components["schemas"]["ReconciliationResult"];
export type ReservationSummary = components["schemas"]["ReservationSummary"];
export type ResetSimulatorRequest = components["schemas"]["ResetSimulatorRequest"];
export type ResultSetEvaluation = components["schemas"]["ResultSetEvaluation"];
export type RiskAssessment = components["schemas"]["RiskAssessment"];
export type RiskTier = components["schemas"]["RiskTier"];
export type RollbackPlan = components["schemas"]["RollbackPlan"];
export type RuleEvaluation = components["schemas"]["RuleEvaluation"];
export type RunListResponse = components["schemas"]["RunListResponse"];
export type RunTraceResponse = components["schemas"]["RunTraceResponse"];
export type RunUntilSimulatorRequest = components["schemas"]["RunUntilSimulatorRequest"];
export type SafeError = components["schemas"]["SafeError"];
export type ScenarioListResponse = components["schemas"]["ScenarioListResponse"];
export type ScenarioSummary = components["schemas"]["ScenarioSummary"];
export type ScoreComponentsInput = components["schemas"]["ScoreComponents-Input"];
export type ScoreComponents = components["schemas"]["ScoreComponents-Output"];
export type SearchEventInput = components["schemas"]["SearchEventInput"];
export type SearchIntent = components["schemas"]["SearchIntent"];
export type SearchRequest = components["schemas"]["SearchRequest"];
export type SearchResponse = components["schemas"]["SearchResponse"];
export type SearchRetryPlan = components["schemas"]["SearchRetryPlan"];
export type SearchRule = components["schemas"]["SearchRule"];
export type SearchRuleListResponse = components["schemas"]["SearchRuleListResponse"];
export type SearchTrace = components["schemas"]["SearchTrace"];
export type SearchUserContext = components["schemas"]["SearchUserContext"];
export type SessionInfo = components["schemas"]["SessionInfo"];
export type SessionList = components["schemas"]["SessionList"];
export type SetCampaignBudgetIntent = components["schemas"]["SetCampaignBudgetIntent"];
export type SetRecommendationPolicyIntent = components["schemas"]["SetRecommendationPolicyIntent"];
export type SetSearchBoostIntent = components["schemas"]["SetSearchBoostIntent"];
export type SetVariantPriceIntent = components["schemas"]["SetVariantPriceIntent"];
export type SetupStatus = components["schemas"]["SetupStatus"];
export type ShopperAccount = components["schemas"]["ShopperAccount"];
export type ShopperAgentStep = components["schemas"]["ShopperAgentStep"];
export type ShopperAuthResponse = components["schemas"]["ShopperAuthResponse"];
export type ShopperChatRequest = components["schemas"]["ShopperChatRequest"];
export type ShopperChatResponse = components["schemas"]["ShopperChatResponse"];
export type ShopperConversation = components["schemas"]["ShopperConversation"];
export type ShopperConversationDetail = components["schemas"]["ShopperConversationDetail"];
export type ShopperConversationList = components["schemas"]["ShopperConversationList"];
export type ShopperDiscoveryResponse = components["schemas"]["ShopperDiscoveryResponse"];
export type ShopperDiscoverySuggestion = components["schemas"]["ShopperDiscoverySuggestion"];
export type ShopperGuestResponse = components["schemas"]["ShopperGuestResponse"];
export type ShopperLoginRequest = components["schemas"]["ShopperLoginRequest"];
export type ShopperMemory = components["schemas"]["ShopperMemory"];
export type ShopperMemoryDeleteResponse = components["schemas"]["ShopperMemoryDeleteResponse"];
export type ShopperMemoryList = components["schemas"]["ShopperMemoryList"];
export type ShopperMessage = components["schemas"]["ShopperMessage"];
export type ShopperOrderList = components["schemas"]["ShopperOrderList"];
export type ShopperProductCard = components["schemas"]["ShopperProductCard"];
export type ShopperRecovery = components["schemas"]["ShopperRecovery"];
export type ShopperRegisterRequest = components["schemas"]["ShopperRegisterRequest"];
export type SimulatorMetricsResponse = components["schemas"]["SimulatorMetricsResponse"];
export type SimulatorStateResponse = components["schemas"]["SimulatorStateResponse"];
export type StoreImageIssue = components["schemas"]["StoreImageIssue"];
export type StoreMeasurements = components["schemas"]["StoreMeasurements"];
export type StoreProfile = components["schemas"]["StoreProfile"];
export type StoreProfileUpdate = components["schemas"]["StoreProfileUpdate"];
export type StoreReadiness = components["schemas"]["StoreReadiness"];
export type Storefront = components["schemas"]["Storefront"];
export type TimeWindow = components["schemas"]["TimeWindow"];
export type TrainRankingInput = components["schemas"]["TrainRankingInput"];
export type VariantPriceChange = components["schemas"]["VariantPriceChange"];
export type ScenarioId = components["schemas"]["ScenarioSummary"]["id"];
export type RankingMode = NonNullable<components["schemas"]["SearchRequest"]["mode"]>;
export type ServiceStatus = components["schemas"]["MetaResponse"]["status"];
