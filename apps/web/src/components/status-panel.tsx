import type { DependencyStatus, MetaResponse } from "@open-commerce/sdk-typescript";

type StatusPanelProps = {
  meta: MetaResponse | null;
};

const expectedDependencies = ["postgres", "redis", "qdrant"] as const;

function statusClass(isReady: boolean): string {
  return isReady ? "badge ready" : "badge not-ready";
}

function dependencyRows(meta: MetaResponse | null): DependencyStatus[] {
  if (meta) {
    return meta.dependencies;
  }

  return expectedDependencies.map((name) => ({
    name,
    ok: false,
    latency_ms: null,
    detail: "api_unavailable"
  }));
}

export function StatusPanel({ meta }: StatusPanelProps) {
  const ready = meta?.status === "ready";
  const dependencies = dependencyRows(meta);
  const appName = meta?.app_name === "Open Commerce Agent" ? "GoodAgent" : meta?.app_name;

  return (
    <section className="panel" aria-label="Runtime status">
      <header className="panel-header">
        <div>
          <p className="label">{appName ?? "GoodAgent API"}</p>
          <p className="detail">
            {meta ? `${meta.environment} / ${meta.version}` : "api unavailable"}
          </p>
        </div>
        <span className={statusClass(ready)}>{ready ? "Ready" : "Not ready"}</span>
      </header>
      <div className="dependency-grid">
        {dependencies.map((dependency) => (
          <div className="panel-row" key={dependency.name}>
            <div>
              <p className="label">{dependency.name}</p>
              <p className="detail">
                {dependency.ok
                  ? `${dependency.latency_ms ?? 0} ms`
                  : dependency.detail ?? "unavailable"}
              </p>
            </div>
            <span className={statusClass(dependency.ok)}>
              {dependency.ok ? "Online" : "Offline"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
