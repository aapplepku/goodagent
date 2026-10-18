"use client";

import type {
  CatalogBrowseProduct,
  CatalogBrowseResponse,
} from "@open-commerce/sdk-typescript";
import {
  ArrowLeft,
  ArrowRight,
  ImageOff,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useState } from "react";
import { createShopperClient, shopperErrorMessage } from "@/lib/api";
import { useShopperSessionError } from "@/lib/session-errors";
import styles from "./catalog-browser.module.css";

function productCount(count: number): string {
  return `${count} ${count === 1 ? "product" : "products"}`;
}

export function CatalogBrowser({
  client,
  pendingProduct,
  onAdd,
  onAsk,
  storeName,
  onInspect,
}: {
  client: Pick<ReturnType<typeof createShopperClient>, "shopperCatalog">;
  pendingProduct: string | null;
  onAdd: (product: Pick<CatalogBrowseProduct, "product_id">) => Promise<void>;
  onAsk: (query: string) => void;
  storeName?: string;
  onInspect?: (product: CatalogBrowseProduct) => void;
}) {
  const handleSessionError = useShopperSessionError();
  const [data, setData] = useState<CatalogBrowseResponse | null>(null);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<
    "title" | "title_desc" | "price_asc" | "price_desc"
  >("title");
  const [inStock, setInStock] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    async function load() {
      let intervalMs = 5000;
      try {
        const result = await client.shopperCatalog({
          q: query,
          category,
          sort,
          in_stock: inStock,
          offset,
          limit: 24,
        });
        if (!active) return;
        setData(result);
        setOffset(result.offset);
        setError(null);
        if (result.indexing.status === "ready") intervalMs = 30000;
      } catch (cause) {
        if (!active) return;
        if (handleSessionError(cause)) {
          active = false;
          return;
        }
        setError(shopperErrorMessage(cause));
      } finally {
        if (active) {
          setLoading(false);
          timer = setTimeout(() => void load(), intervalMs);
        }
      }
    }
    void load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [client, query, category, sort, inStock, offset, refresh, handleSessionError]);

  const working =
    data?.indexing.status === "queued" || data?.indexing.status === "running";
  const hasFilters = Boolean(query || category || inStock);
  return (
    <section className={styles.browser} aria-label="Browse store catalog">
      <header className={styles.heading}>
        <div>
          <span>GoodAgent Shop</span>
          <h1>Browse the store</h1>
          <p>
            {data?.catalog
              ? storeName
                ? `${productCount(data.catalog.product_count)} at ${storeName}`
                : `${productCount(data.catalog.product_count)} from ${data.catalog.filename}`
              : error
                ? "Catalog information is unavailable"
                : "Waiting for the store's catalog"}
          </p>
        </div>
        <button
          title="Refresh catalog"
          aria-label="Refresh catalog"
          disabled={loading}
          onClick={() => setRefresh((value) => value + 1)}
        >
          <RefreshCw size={17} />
        </button>
      </header>
      {error && (
        <p className={styles.error} role="alert">
          {data ? "Showing last loaded data. " : ""}
          {error}
        </p>
      )}
      {working && (
        <div className={styles.notice} role="status">
          <strong>
            {data.indexing.status === "queued"
              ? "Catalog update queued"
              : "Catalog update in progress"}
          </strong>
          <span>
            {data.indexing.indexed_product_count ?? 0} /{" "}
            {productCount(data.indexing.product_count ?? 0)} verified.
            {data.catalog
              ? " You can still browse the published catalog."
              : " Products will appear after verification."}
          </span>
          <progress
            aria-label="Catalog indexing"
            value={data.indexing.indexed_product_count ?? 0}
            max={Math.max(1, data.indexing.product_count ?? 0)}
          />
        </div>
      )}
      {data?.indexing.status === "failed" && (
        <p className={styles.notice} role="status">
          The latest catalog update could not finish.{" "}
          {data.catalog
            ? "The previous catalog is still available."
            : "No products are published yet."}
        </p>
      )}
      <form
        className={styles.filters}
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(draft.trim());
          setOffset(0);
        }}
      >
        <div className={styles.search}>
          <Search size={17} />
          <input
            aria-label="Find catalog products"
            placeholder="Find a product or brand"
            maxLength={200}
            value={draft}
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
            <option value={category}>{category} (no longer available)</option>
          )}
          {data?.categories.map((item) => <option key={item}>{item}</option>)}
        </select>
        <select
          aria-label="Sort products"
          value={sort}
          onChange={(event) => {
            setSort(event.target.value as typeof sort);
            setOffset(0);
          }}
        >
          <option value="title">Name A to Z</option>
          <option value="title_desc">Name Z to A</option>
          <option value="price_asc">Price low to high</option>
          <option value="price_desc">Price high to low</option>
        </select>
        <label>
          <input
            type="checkbox"
            checked={inStock}
            onChange={(e) => {
              setInStock(e.target.checked);
              setOffset(0);
            }}
          />
          In stock
        </label>
      </form>
      <div className={styles.results}>
        <strong role="status">
          {data
            ? loading
              ? "Updating results..."
              : error
                ? "Previous results"
                : `${productCount(data.total)}${hasFilters ? " matching filters" : ""}`
            : "Products not loaded"}
        </strong>
        <span>Local demo prices</span>
      </div>
      <div
        className={styles.grid}
        aria-label="Catalog products"
        aria-busy={loading}
      >
        {data?.items.map((product) => (
          <Product
            key={`${data.catalog?.id}:${product.product_id}`}
            product={product}
            disabled={loading || Boolean(pendingProduct) || Boolean(error)}
            pending={pendingProduct === product.product_id}
            onAdd={onAdd}
            onInspect={onInspect}
            onAsk={onAsk}
          />
        ))}
      </div>
      {loading && !data && (
        <p role="status" className={styles.empty}>
          Loading catalog...
        </p>
      )}
      {!loading && data && !data.items.length && (
        <div className={styles.empty}>
          <ImageOff size={30} />
          <h2>
            {data.catalog
              ? "No matching products"
              : "The shelves are not ready yet"}
          </h2>
          {hasFilters && (
            <button
              onClick={() => {
                setQuery("");
                setDraft("");
                setCategory("");
                setInStock(false);
                setOffset(0);
              }}
            >
              Clear filters
            </button>
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
    </section>
  );
}

function Product({
  product,
  disabled,
  pending,
  onAdd,
  onAsk,
  onInspect,
}: {
  product: CatalogBrowseProduct;
  disabled: boolean;
  pending: boolean;
  onAdd: (product: Pick<CatalogBrowseProduct, "product_id">) => Promise<void>;
  onAsk: (query: string) => void;
  onInspect?: (product: CatalogBrowseProduct) => void;
}) {
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
            sizes="(max-width: 720px) 50vw, 250px"
            unoptimized
            onError={() => setFailed(true)}
          />
        ) : (
          <span>
            <ImageOff size={26} />
            Image unavailable
          </span>
        )}
      </div>
      <div className={styles.copy}>
        <span>{product.category || "Store catalog"}</span>
        <h2>{product.title}</h2>
        {onInspect && (
          <button onClick={() => onInspect(product)}>View product</button>
        )}
        <p>{product.brand}</p>
        <div className={styles.price}>
          <strong>
            {product.price.currency}{" "}
            {(product.price.amount_minor / 100).toFixed(2)}
          </strong>
          <button
            title={`Add ${product.title} to cart`}
            aria-label={`Add ${product.title} to cart`}
            disabled={disabled || product.availability !== "available"}
            onClick={() => void onAdd({ product_id: product.product_id })}
          >
            <Plus size={16} />
          </button>
        </div>
        <small>
          {pending
            ? "Adding to cart..."
            : product.availability === "available"
              ? "Available"
              : product.availability === "unknown"
                ? "Availability unconfirmed"
                : "Out of stock"}
        </small>
        <details>
          <summary>Details</summary>
          <p>{product.title}</p>
          <p>{product.description || "No description provided."}</p>
          <p>Product ID: {product.product_id}</p>
          {product.provenance && <p>Source note: {product.provenance}</p>}
          <button
            disabled={disabled}
            onClick={() =>
              onAsk(
                `Tell me about ${product.title} (product ${product.product_id}) and compare similar products.`,
              )
            }
          >
            Ask the assistant
          </button>
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
