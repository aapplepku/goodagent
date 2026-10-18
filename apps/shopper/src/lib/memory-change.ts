export type MemoryChange = { key: string; enabled: boolean };

export function loadMemoryChange(scope: string): MemoryChange | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(`memory-change:${scope}`) ?? "null");
    if (!value || typeof value !== "object") return null;
    const item = value as Record<string, unknown>;
    if (typeof item.enabled !== "boolean" || typeof item.key !== "string" ||
      !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(item.key)) return null;
    return { key: item.key, enabled: item.enabled };
  } catch { return null; }
}

export function saveMemoryChange(scope: string, change: MemoryChange | null): boolean {
  try {
    if (change) sessionStorage.setItem(`memory-change:${scope}`, JSON.stringify(change));
    else sessionStorage.removeItem(`memory-change:${scope}`);
    return true;
  } catch { return false; }
}
