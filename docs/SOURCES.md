# Primary Sources and Implementation References

This file is a reading list, not a substitute for checking the latest API documentation before implementation. Platform APIs, scopes, versions, and app-review requirements change.

## Coding-agent workflow

- OpenAI, **Custom instructions with AGENTS.md**  
  https://developers.openai.com/codex/guides/agents-md/

- OpenAI, **Codex prompting and workflow best practices**  
  https://developers.openai.com/codex/guides/prompting/

Use `AGENTS.md` for durable repository rules. Give Codex one milestone with explicit context, constraints, and definition of done rather than asking it to generate the entire product at once.

## Shopify authentication and access

- Shopify, **Authentication and authorization**  
  https://shopify.dev/docs/apps/build/authentication-authorization

- Shopify, **Access tokens / token exchange**  
  https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens

Implementation note: isolate token lifecycle behind a credential provider and support expiring offline-token refresh for public-app readiness.

## Shopify GraphQL and synchronization

- Shopify, **Perform bulk operations with the GraphQL Admin API**  
  https://shopify.dev/docs/api/usage/bulk-operations/queries

- Shopify, **Webhook subscriptions**  
  https://shopify.dev/docs/apps/build/webhooks/subscribe

- Shopify, **Orders access**  
  https://shopify.dev/docs/api/usage/access-scopes#orders-permissions

- Shopify, **Protected customer data**  
  https://shopify.dev/docs/apps/launch/protected-customer-data

Implementation note: use bulk operations for initial loads, webhooks plus authoritative rereads for incremental updates, and data minimization for customer-derived features.

## Shopify writes

- Shopify, **productVariantsBulkUpdate**  
  https://shopify.dev/docs/api/admin-graphql/latest/mutations/productVariantsBulkUpdate

- Shopify, **discountAutomaticBasicCreate**  
  https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountAutomaticBasicCreate

- Shopify, **discountCodeBasicCreate**  
  https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountCodeBasicCreate

Implementation note: re-read target state, enforce policy, write, then reconcile. Keep price changes approval-gated in the initial release.

## Shopify storefront behavior

- Shopify, **Web Pixels API standard events**  
  https://shopify.dev/docs/api/web-pixels-api/standard-events

- Shopify, **Customer privacy and Web Pixels**  
  https://shopify.dev/docs/apps/build/marketing-analytics/pixels

- Shopify, **Theme app extensions / app embed blocks**  
  https://shopify.dev/docs/apps/build/online-store/theme-app-extensions

Implementation note: the project’s search boosts affect its own search API/theme extension, not Shopify’s proprietary ranking.

## Agent runtime

- LangChain, **LangGraph persistence**  
  https://docs.langchain.com/oss/python/langgraph/persistence

- LangChain, **LangGraph interrupts / human-in-the-loop**  
  https://docs.langchain.com/oss/python/langgraph/interrupts

- LangChain, **Durable execution**  
  https://docs.langchain.com/oss/python/langgraph/durable-execution

- LangChain, **PostgreSQL checkpointer**  
  https://docs.langchain.com/oss/python/langgraph/add-memory#use-in-production

Implementation note: use persistence and interrupts for restartable runs and approvals, while keeping side effects idempotent in domain/executor code.

## Hybrid retrieval

- Qdrant, **Hybrid queries**  
  https://qdrant.tech/documentation/concepts/hybrid-queries/

- Qdrant, **Sparse vectors / BM25 and IDF**  
  https://qdrant.tech/documentation/concepts/indexing/#sparse-vector-index

- Qdrant, **Search relevance and reranking tutorials**  
  https://qdrant.tech/documentation/search-precision/

Implementation note: use dense plus sparse retrieval, payload filters, RRF, optional reranking, and explicit relevance gating before business-objective boosts.

## Future connectors

- WooCommerce, **REST API authentication and products/orders**  
  https://woocommerce.github.io/woocommerce-rest-api-docs/

- WooCommerce, **Webhooks**  
  https://woocommerce.com/document/webhooks/

- TikTok Shop, **Developer guide / authorization**  
  https://partner.tiktokshop.com/docv2/page/tts-developer-guide

- Google Ads, **Campaign budgets**  
  https://developers.google.com/google-ads/api/docs/campaigns/budgets/create-budgets

Implementation note: verify current regional availability, review requirements, scopes, quotas, and API versions before building each connector.
