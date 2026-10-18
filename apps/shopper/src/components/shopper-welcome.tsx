"use client";

import type { ShopperDiscoveryResponse, Storefront } from "@open-commerce/sdk-typescript";
import { ImageOff, ShoppingBag } from "lucide-react";
import Image from "next/image";
import { useCallback, useState } from "react";
import { CatalogArtwork } from "./catalog-artwork";
import styles from "./shopper-welcome.module.css";

function storeImage(value: string | null | undefined, slug: string): string | null {
  if (!value) return null;
  try {
    const url = new URL(value, "https://store.invalid");
    // Accept only the exact relative URL emitted by ingestion, without URL normalization aliases.
    return /^\/api\/runtime\/v1\/shopper\/assets\/[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/.test(url.pathname)
      && value === `${url.pathname}?store=${slug}` ? value : null;
  } catch {
    return null;
  }
}

function Thumbnail({ source, failed, onFailure }: {
  source: string;
  failed: boolean;
  onFailure: (source: string) => void;
}) {
  // Next Image reattaches its ref when onError changes, resetting an unchanged src.
  const handleError = useCallback(() => onFailure(source), [onFailure, source]);
  return (
    <span className={styles.thumbnail} aria-hidden="true">
      {failed ? <ImageOff size={18} /> : (
        <Image key={source} src={source} alt="" width={30} height={30} unoptimized
          referrerPolicy="no-referrer" onError={handleError} />
      )}
    </span>
  );
}

export function ShopperWelcome({ discovery, store, disabled, onPrompt, welcome }: {
  discovery: ShopperDiscoveryResponse | null;
  store?: Storefront;
  disabled: boolean;
  onPrompt: (value: string) => void;
  welcome: string;
}) {
  const [failedImages, setFailedImages] = useState<ReadonlySet<string>>(() => new Set());
  const recordFailure = useCallback((source: string) => {
    setFailedImages((failed) => failed.has(source) ? failed : new Set(failed).add(source));
  }, []);
  const prompts = (discovery?.suggestions ?? []).map((prompt) => ({
    ...prompt,
    // Storefront is absent only for the explicit legacy entry, which retains its image contract.
    image: store ? storeImage(prompt.image_url, store.slug) : prompt.image_url,
  }));
  const showSampleCredit = store?.sample_data && prompts.some(({ image }) => image && !failedImages.has(image));

  return (
    <div className="empty-conversation">
      {!store && <div className="empty-visual"><CatalogArtwork /></div>}
      <span><ShoppingBag size={18} /></span>
      <h1>What are we shopping for?</h1>
      <p>{discovery?.catalog_status === "ready"
        ? welcome
        : "The store operator is still preparing the catalog. Starter ideas will appear as soon as it is searchable."}</p>
      {prompts.length > 0 && (
        <div className="prompt-row">
          {prompts.map((prompt) => (
            <button type="button" key={prompt.query} disabled={disabled} onClick={() => onPrompt(prompt.query)}>
              {prompt.image && (
                <Thumbnail source={prompt.image} failed={failedImages.has(prompt.image)} onFailure={recordFailure} />
              )}
              {prompt.label}
            </button>
          ))}
        </div>
      )}
      {showSampleCredit && (
        <div className={styles.credit}>
          Sample catalog photos: {" "}
          <a href="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html">Amazon.com / ABO</a>
          {" · "}<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
        </div>
      )}
    </div>
  );
}
