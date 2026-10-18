"""Import all ORM models so Alembic can see metadata."""

from open_commerce.persistence.models.actions import (
    ActionExecution,
    ActionIntentRecord,
    ActionReconciliation,
    ApprovalRecord,
    ApprovalRequestRecord,
    CompiledActionRecord,
    Intervention,
    InterventionOutcome,
    PolicyDecisionRecord,
)
from open_commerce.persistence.models.audit import AuditEventRecord
from open_commerce.persistence.models.budgets import BudgetAccountRecord, BudgetLedgerEntryRecord
from open_commerce.persistence.models.catalog import InventorySnapshot, Product, ProductVariant
from open_commerce.persistence.models.commerce import (
    InventoryReservationRecord,
    PaymentAttemptRecord,
    ShopperCartLineRecord,
    ShopperCartRecord,
    ShopperOrderRecord,
)
from open_commerce.persistence.models.events import BehavioralEventRecord
from open_commerce.persistence.models.goals import (
    Goal,
    GoalBudget,
    GoalConstraint,
    GoalRevisionRecord,
    PolicyVersion,
)
from open_commerce.persistence.models.identity import Tenant, TenantMembership, User
from open_commerce.persistence.models.inference import InferenceCall
from open_commerce.persistence.models.integrations import Integration, IntegrationCredential
from open_commerce.persistence.models.manager_agent import (
    ManagerDataOnboardingRecord,
    ManagerMemoryRecord,
    ManagerMessageRecord,
    ManagerThreadRecord,
)
from open_commerce.persistence.models.manager_runs import (
    ManagerRunEventRecord,
    ManagerRunRecord,
    RuntimeOperationRecord,
)
from open_commerce.persistence.models.model_usage import ModelUsageRecord
from open_commerce.persistence.models.orders import CustomerFact, Order, OrderLine
from open_commerce.persistence.models.ranking import EngagementSnapshot, RankingModelRecord
from open_commerce.persistence.models.runs import (
    GoalRun,
    GoalRunStep,
    ObservationSnapshotRecord,
    OpportunityRecord,
)
from open_commerce.persistence.models.search import (
    CatalogIndexJob,
    SearchBoostRule,
    SearchIndexVersion,
)
from open_commerce.persistence.models.shopper import (
    ShopperAccountRecord,
    ShopperConversationRecord,
    ShopperMemoryRecord,
    ShopperMessageRecord,
    ShopperSessionRecord,
)
from open_commerce.persistence.models.shopper_activity import (
    ActivityCheckRecord,
    ActivityRuleRecord,
    ShopperActivityRecord,
)
from open_commerce.persistence.models.simulator import (
    SimulatorBaselineRecord,
    SimulatorCommandRecordModel,
    SimulatorDailyMetricRecord,
    SimulatorEventRecord,
    SimulatorInstanceRecord,
    SimulatorSnapshotRecord,
)
from open_commerce.persistence.models.store_setup import (
    AuthTicketRecord,
    MerchantCredentialRecord,
    MerchantSessionRecord,
    SetupEventRecord,
    StoreSetupRecord,
)
from open_commerce.persistence.models.sync import SourceMapping, SyncJob, WebhookReceipt
from open_commerce.persistence.models.workflow import IdempotencyRecord, TenantRuntime, WorkflowJob

__all__ = [
    "ActionExecution",
    "ActionIntentRecord",
    "ActionReconciliation",
    "ActivityCheckRecord",
    "ActivityRuleRecord",
    "ApprovalRecord",
    "ApprovalRequestRecord",
    "AuditEventRecord",
    "AuthTicketRecord",
    "BehavioralEventRecord",
    "BudgetAccountRecord",
    "BudgetLedgerEntryRecord",
    "CatalogAssetRecord",
    "CatalogImportRecord",
    "CatalogIndexJob",
    "CompiledActionRecord",
    "CustomerFact",
    "EngagementSnapshot",
    "Goal",
    "GoalBudget",
    "GoalConstraint",
    "GoalRevisionRecord",
    "GoalRun",
    "GoalRunStep",
    "IdempotencyRecord",
    "InferenceCall",
    "Integration",
    "IntegrationCredential",
    "Intervention",
    "InterventionOutcome",
    "InventoryReservationRecord",
    "InventorySnapshot",
    "ManagerDataOnboardingRecord",
    "ManagerMemoryRecord",
    "ManagerMessageRecord",
    "ManagerRunEventRecord",
    "ManagerRunRecord",
    "ManagerThreadRecord",
    "MerchantCredentialRecord",
    "MerchantSessionRecord",
    "ModelUsageRecord",
    "ObservationSnapshotRecord",
    "OpportunityRecord",
    "Order",
    "OrderLine",
    "PaymentAttemptRecord",
    "PolicyDecisionRecord",
    "PolicyVersion",
    "Product",
    "ProductVariant",
    "RankingModelRecord",
    "RuntimeOperationRecord",
    "SearchBoostRule",
    "SearchIndexVersion",
    "SetupEventRecord",
    "ShopperAccountRecord",
    "ShopperActivityRecord",
    "ShopperCartLineRecord",
    "ShopperCartRecord",
    "ShopperConversationRecord",
    "ShopperMemoryRecord",
    "ShopperMessageRecord",
    "ShopperOrderRecord",
    "ShopperSessionRecord",
    "SimulatorBaselineRecord",
    "SimulatorCommandRecordModel",
    "SimulatorDailyMetricRecord",
    "SimulatorEventRecord",
    "SimulatorInstanceRecord",
    "SimulatorSnapshotRecord",
    "SourceMapping",
    "StoreSetupRecord",
    "SyncJob",
    "Tenant",
    "TenantMembership",
    "TenantRuntime",
    "User",
    "WebhookReceipt",
    "WorkflowJob",
]
from open_commerce.persistence.models.catalog_import import CatalogAssetRecord, CatalogImportRecord
