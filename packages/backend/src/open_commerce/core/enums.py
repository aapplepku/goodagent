"""Finite domain enums used across the runtime."""

from enum import Enum


class GoalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class AutonomyMode(str, Enum):
    DEMO = "demo"
    SHADOW = "shadow"
    APPROVAL_REQUIRED = "approval_required"
    BOUNDED_AUTO = "bounded_auto"


class ObjectiveDirection(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    REACH = "reach"


class MetricName(str, Enum):
    NEW_CUSTOMERS = "new_customers"
    CAC = "cac"
    REVENUE = "revenue"
    CONTRIBUTION_PROFIT = "contribution_profit"
    CONTRIBUTION_MARGIN_RATE = "contribution_margin_rate"
    CONVERSION_RATE = "conversion_rate"
    DISCOUNT_RATE = "discount_rate"
    UNITS_SOLD = "units_sold"
    INVENTORY_DAYS_OF_SUPPLY = "inventory_days_of_supply"
    SEARCH_CONVERSION_RATE = "search_conversion_rate"
    SEARCH_ATTRIBUTED_PURCHASES = "search_attributed_purchases"


class MetricUnit(str, Enum):
    COUNT = "count"
    MONEY_MINOR = "money_minor"
    RATE = "rate"
    DAYS = "days"


class ConstraintOperator(str, Enum):
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    GTE = "gte"
    GT = "gt"


class ActionType(str, Enum):
    CREATE_DISCOUNT = "create_discount"
    DISABLE_DISCOUNT = "disable_discount"
    SET_VARIANT_PRICE = "set_variant_price"
    SET_SEARCH_BOOST = "set_search_boost"
    SET_RECOMMENDATION_POLICY = "set_recommendation_policy"
    SET_CAMPAIGN_BUDGET = "set_campaign_budget"
    NO_OP = "no_op"


class ActionStatus(str, Enum):
    DRAFT = "draft"
    COMPILED = "compiled"
    DENIED = "denied"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTABLE = "executable"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    ROLLBACK_PROPOSED = "rollback_proposed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RiskTier(str, Enum):
    R0_READ_ONLY = "r0_read_only"
    R1_REVERSIBLE_LOW = "r1_reversible_low"
    R2_REVERSIBLE_MATERIAL = "r2_reversible_material"
    R3_HIGH_IMPACT = "r3_high_impact"
    R4_PROHIBITED = "r4_prohibited"


class PolicyOutcome(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    RECONCILED = "reconciled"


class ActorRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    OWNER = "owner"
    ADMIN = "admin"
    SYSTEM = "system"


class FreshnessState(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


class DataSource(str, Enum):
    CATALOG = "catalog"
    INVENTORY = "inventory"
    ORDERS = "orders"
    DISCOUNTS = "discounts"
    BEHAVIORAL_EVENTS = "behavioral_events"
    CAMPAIGNS = "campaigns"
    SPEND = "spend"


class Capability(str, Enum):
    READ_CATALOG = "read_catalog"
    WRITE_PRODUCT_CONTENT = "write_product_content"
    WRITE_PRICE = "write_price"
    READ_INVENTORY = "read_inventory"
    WRITE_INVENTORY = "write_inventory"
    READ_ORDERS = "read_orders"
    READ_CUSTOMER_COHORTS = "read_customer_cohorts"
    READ_DISCOUNTS = "read_discounts"
    WRITE_DISCOUNTS = "write_discounts"
    READ_BEHAVIOR_EVENTS = "read_behavior_events"
    WRITE_MERCHANDISING = "write_merchandising"
    READ_CAMPAIGNS = "read_campaigns"
    WRITE_CAMPAIGN_BUDGET = "write_campaign_budget"
    WRITE_CAMPAIGN_STATUS = "write_campaign_status"


class ProviderType(str, Enum):
    SIMULATOR = "simulator"
    SHOPIFY = "shopify"
    ADS = "ads"
    SEARCH = "search"


class AuditEventType(str, Enum):
    GOAL_CREATED = "goal_created"
    GOAL_UPDATED = "goal_updated"
    POLICY_CHANGED = "policy_changed"
    ACTION_TRANSITIONED = "action_transitioned"
    APPROVAL_RECORDED = "approval_recorded"
    BUDGET_RESERVED = "budget_reserved"
    BUDGET_COMMITTED = "budget_committed"
    BUDGET_RELEASED = "budget_released"
    EXECUTION_STATUS_CHANGED = "execution_status_changed"
    CART_UPDATED = "cart_updated"
    CHECKOUT_PREVIEWED = "checkout_previewed"
    PAYMENT_STATUS_CHANGED = "payment_status_changed"
    ORDER_CREATED = "order_created"
    INVENTORY_RESERVATION_CHANGED = "inventory_reservation_changed"


class BudgetEntryType(str, Enum):
    RESERVED = "reserved"
    COMMITTED = "committed"
    RELEASED = "released"
    ADJUSTED = "adjusted"


class EventType(str, Enum):
    SEARCH_SUBMITTED = "search_submitted"
    PRODUCT_IMPRESSION = "product_impression"
    PRODUCT_CLICKED = "product_clicked"
    PRODUCT_VIEWED = "product_viewed"
    ADD_TO_CART = "add_to_cart"
    CHECKOUT_STARTED = "checkout_started"
    PURCHASE = "purchase"
    DISCOUNT_EXPOSED = "discount_exposed"
    DISCOUNT_REDEEMED = "discount_redeemed"
