"use client";
import { useEffect } from "react";
export function PreviewRedirect({ origin }: { origin: string }) {
  useEffect(() => {
    const store = new URLSearchParams(location.search).get("store");
    if (!store || !/^[a-z0-9-]{1,120}$/.test(store)) return;
    location.replace(`${origin}/s/${store}${location.hash}`);
  }, [origin]);
  return <p>Opening the store...</p>;
}
