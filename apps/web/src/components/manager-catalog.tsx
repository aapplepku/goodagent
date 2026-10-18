"use client";

import type {
  CatalogBrowseProduct,
  CatalogBrowseResponse,
} from "@open-commerce/sdk-typescript";
import { OpenCommerceApiError } from "@open-commerce/sdk-typescript";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Database,
  ImageOff,
  RefreshCw,
  Search,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiErrorMessage, createBrowserClient } from "@/lib/api";
import { useMerchantClient } from "@/lib/merchant-transport";
import styles from "./manager-catalog.module.css";
import { useStoreNavigation } from "./store-navigation";

export function ManagerCatalog({
  client: suppliedClient,
}: {
  client?: Pick<ReturnType<typeof createBrowserClient>, "managerCatalog">;
}) {
  const defaultClient = useMerchantClient();
  const client = suppliedClient ?? defaultClient;
  const onSessionExpired = useStoreNavigation()?.onSessionExpired;
  const [data, setData] = useState<CatalogBrowseResponse | null>(null);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState<"title" | "title_desc">("title");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    let active = true;
    let sessionExpired = false;
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    async function load() {
      try {
        const result = await client.managerCatalog({
          q: query,
          category,
          sort,
          offset,
          limit: 24,
        });
        if (!active) return;
        setData(result);
        setOffset(result.offset);
        setError(null);
        setCheckedAt(new Date());
      } catch (cause) {
        if (active) {
          setError(apiErrorMessage(cause));
          if (cause instanceof OpenCommerceApiError && cause.status === 401) {
            sessionExpired = true;
            setData(null);
            onSessionExpired?.();
          }
        }
      } finally {
        if (active) {
          setLoading(false);
          if (!sessionExpired) timer = setTimeout(() => void load(), 5000);
        }
      }
    }
    void load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [client, query, category, sort, offset, refresh, onSessionExpired]);

  const indexing = data?.indexing;
  const working =
    indexing?.status === "queued" || indexing?.status === "running";
  return (
    <main className={styles.page}>
      <nav className={styles.topbar}>
        <Link href="/manager">
          <ArrowLeft size={17} /> Workspace
        </Link>
        <strong>
          GoodAgent <span>/ Catalog</span>
        </strong>
      </nav>
      <div className={styles.scroll}>
        <header className={styles.heading}>
          <div>
            <p>STORE DATA</p>
            <h1>Catalog</h1>
          </div>
          <div className={styles.sync}>
            <span>
              {checkedAt
                ? `Checked ${checkedAt.toLocaleTimeString()}`
                : "Connecting"}
            </span>
            <button
              title="Refresh catalog"
              aria-label="Refresh catalog"
              disabled={loading}
              onClick={() => setRefresh((value) => value + 1)}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>
        {error && (
          <p className={styles.error} role="alert">
            {data ? "Showing last loaded data. " : ""}
            {error}
          </p>
        )}
        <section className={styles.source} aria-label="Indexed catalog">
          <Database size={21} />
          <div>
            <strong>
              {data?.catalog?.filename ??
                (data
                  ? "No indexed catalog"
                  : error
                    ? "Catalog unavailable"
                    : "Loading catalog")}
            </strong>
            <p>
              {data?.catalog
                ? `${data.catalog.product_count} products in the indexed catalog`
                : data
                  ? "Upload a catalog in the workspace to begin."
                  : "Waiting for verified catalog information."}
            </p>
          </div>
          {data?.catalog && (
            <span className={styles.ready}>
              <CheckCircle2 size={14} /> Indexed
            </span>
          )}
        </section>
        {data?.catalog && (
          <details className={styles.identity}>
            <summary>Source and indexing details</summary>
            <dl>
              <dt>Catalog ID</dt>
              <dd>{data.catalog.id}</dd>
              <dt>Source version</dt>
              <dd>{data.catalog.source_version}</dd>
              <dt>Index activated</dt>
              <dd>
                {data.catalog.published_at
                  ? new Date(data.catalog.published_at).toLocaleString()
                  : "Not recorded"}
              </dd>
            </dl>
          </details>
        )}
        {working && (
          <div className={styles.indexing} role="status">
            <strong>
              {indexing.status === "queued"
                ? "Queued for indexing"
                : "Indexing"}
              : {indexing.filename}
            </strong>
            <span>
              {indexing.indexed_product_count ?? 0} /{" "}
              {indexing.product_count ?? 0} products verified
              {data?.catalog
                ? ". Current catalog remains available."
                : ". Products will appear after verification."}
            </span>
            <progress
              aria-label="Catalog indexing"
              value={indexing.indexed_product_count ?? 0}
              max={Math.max(indexing.product_count ?? 0, 1)}
            />
          </div>
        )}
        {indexing?.status === "failed" && (
          <p className={styles.error} role="status">
            Indexing failed for {indexing.filename}:{" "}
            {indexing.error_code ?? "See the status agent"}.
            {data?.catalog
              ? " The previous catalog is still available."
              : " No catalog is indexed yet."}
          </p>
        )}
        <form
          className={styles.filters}
          onSubmit={(event) => {
            event.preventDefault();
            setOffset(0);
            setQuery(draft.trim());
          }}
        >
          <div className={styles.search}>
            <Search size={17} />
            <input
              aria-label="Find catalog products"
              placeholder="Title, brand or product ID"
              value={draft}
              maxLength={200}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button
              type="submit"
              title="Find products"
              aria-label="Find products"
            >
              <ArrowRight size={17} />
            </button>
          </div>
          <select
            aria-label="Category"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All categories</option>
            {category && !data?.categories.includes(category) && (
              <option value={category}>
                {category} (not in current catalog)
              </option>
            )}
            {data?.categories.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select
            aria-label="Sort products"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value as "title" | "title_desc");
              setOffset(0);
            }}
          >
            <option value="title">Name A to Z</option>
            <option value="title_desc">Name Z to A</option>
          </select>
        </form>
        <div className={styles.resultsHeader}>
          <strong>
            {data
              ? `${data.total} products${query || category ? " matching filters" : ""}`
              : "Products not loaded"}
          </strong>
          <span>Uploaded prices and availability</span>
        </div>
        <section
          className={styles.grid}
          aria-label="Catalog products"
          aria-busy={loading}
        >
          {data?.items.map((product) => (
            <CatalogTile
              key={`${data.catalog?.id}:${product.product_id}`}
              product={product}
            />
          ))}
        </section>
        {loading && !data && (
          <p role="status" className={styles.empty}>
            Loading catalog...
          </p>
        )}
        {!loading && data && !data.items.length && (
          <div className={styles.empty}>
            <ImageOff size={30} />
            <h2>
              {data.catalog ? "No matching products" : "No indexed products yet"}
            </h2>
            {query || category ? (
              <button
                onClick={() => {
                  setQuery("");
                  setDraft("");
                  setCategory("");
                  setOffset(0);
                }}
              >
                Clear filters
              </button>
            ) : (
              <Link href="/manager">Open workspace</Link>
            )}
          </div>
        )}
        {data && data.total > 0 && (
          <nav className={styles.pagination} aria-label="Catalog pages">
            <span>
              {data.offset + 1}-{Math.min(data.offset + data.limit, data.total)}{" "}
              of {data.total}
            </span>
            <button
              aria-label="Previous page"
              title="Previous page"
              disabled={loading || data.offset === 0}
              onClick={() => setOffset(Math.max(0, data.offset - data.limit))}
            >
              <ArrowLeft size={17} />
            </button>
            <button
              aria-label="Next page"
              title="Next page"
              disabled={loading || data.offset + data.limit >= data.total}
              onClick={() => setOffset(data.offset + data.limit)}
            >
              <ArrowRight size={17} />
            </button>
          </nav>
        )}
      </div>
    </main>
  );
}

function CatalogTile({ product }: { product: CatalogBrowseProduct }) {
  const [failed, setFailed] = useState(false);
  const imageUrl = safeImageUrl(product.image_url);
  return (
    <article className={styles.product}>
      <div className={styles.image}>
        {imageUrl && !failed ? (
          <Image
            src={imageUrl}
            referrerPolicy="no-referrer"
            alt={product.title}
            fill
            sizes="(max-width: 600px) 50vw, 260px"
            unoptimized
            onError={() => setFailed(true)}
          />
        ) : (
          <span>
            <ImageOff size={28} />
            Image unavailable
          </span>
        )}
      </div>
      <div className={styles.productCopy}>
        <span>{product.category || "Uncategorized"}</span>
        <h2>{product.title}</h2>
        <p>{product.brand || "No brand"}</p>
        <strong>
          {product.price.currency}{" "}
          {(product.price.amount_minor / 100).toFixed(2)}
        </strong>
        <small>
          {product.availability === "available"
            ? "Available"
            : product.availability === "unknown"
              ? "Availability unknown"
              : "Out of stock"}
        </small>
        <details>
          <summary>Product details</summary>
          <p>{product.title}</p>
          <p>{product.description || "No description provided."}</p>
          <p>ID: {product.product_id}</p>
          <p>Variant: {product.variant_id}</p>
          {product.provenance && <p>Source note: {product.provenance}</p>}
        </details>
      </div>
    </article>
  );
}

function safeImageUrl(value: string | null): string | null {
  if (!value || /[\s\\]/.test(value)) return null;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
