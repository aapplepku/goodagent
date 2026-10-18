import type { CatalogIndexStatus } from "@open-commerce/sdk-typescript";
import styles from "./catalog-index-progress.module.css";

export function CatalogIndexProgress({ index }: { index: CatalogIndexStatus }) {
  if (!["queued", "running", "failed"].includes(index.status ?? "")) return null;
  const total = Math.max(0, index.product_count ?? 0);
  const verified = Math.min(total, Math.max(0, index.indexed_product_count ?? 0));
  const failed = index.status === "failed";
  const queued = index.status === "queued";
  return (
    <section className={styles.progress} aria-label="Catalog indexing status" data-failed={failed}>
      <div className={styles.heading} role="status">
        <strong>{failed ? "Indexing needs attention" : queued ? "Catalog queued for indexing" : "Indexing your catalog"}</strong>
        <span>{verified} / {total || "unknown"} products verified</span>
      </div>
      {index.filename && <small className={styles.filename}>{index.filename}</small>}
      {!failed && <progress
        aria-label="Catalog indexing"
        aria-valuetext={queued ? "Waiting for the indexing worker" : `${verified} of ${total || "unknown"} products verified`}
        max={Math.max(total, 1)}
        value={queued || !total ? undefined : verified}
      />}
      <p>{failed
        ? `The index could not be verified${index.error_code ? ` (${index.error_code})` : ""}. Review catalog status and retry indexing.`
        : queued ? "Waiting for the indexing worker. You can keep using the workspace."
          : "Preparing products, images, and the search index."}
        {index.serving_catalog_id ? " Your previous catalog remains available." : " Products become searchable after verification."}
      </p>
    </section>
  );
}
