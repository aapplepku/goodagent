import { describe, expect, it, vi } from "vitest";
import { loadMemoryChange, saveMemoryChange } from "./memory-change";

describe("pending memory setting", () => {
  it("persists only a typed command in its account/store scope and clears it", () => {
    const change = { key: crypto.randomUUID(), enabled: false };
    expect(saveMemoryChange("store:account", change)).toBe(true);
    expect(loadMemoryChange("store:account")).toEqual(change);
    expect(loadMemoryChange("other:account")).toBeNull();
    expect(saveMemoryChange("store:account", null)).toBe(true);
    expect(loadMemoryChange("store:account")).toBeNull();
  });
  it.each(["broken", "{}", '{"key":"not-an-id","enabled":true}', '{"key":"12345678-1234-1234-1234-123456789012","enabled":"false"}'])("rejects malformed stored data: %s", (value) => {
    sessionStorage.setItem("memory-change:invalid", value);
    expect(loadMemoryChange("invalid")).toBeNull();
  });
  it("reports unavailable tab storage before a setting is sent", () => {
    vi.stubGlobal("sessionStorage", { setItem() { throw new Error("blocked"); } });
    try {
      expect(saveMemoryChange("blocked", { key: crypto.randomUUID(), enabled: true })).toBe(false);
    } finally { vi.unstubAllGlobals(); }
  });
});
