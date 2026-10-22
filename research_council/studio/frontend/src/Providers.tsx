import { useCallback, useEffect, useState } from "react";
import { Check, KeyRound, ShieldCheck } from "lucide-react";
import { api, money, type Data } from "./api";
import { Badge, Empty, Json } from "./App";
import { useText } from "./i18n";
export default function Providers({
  onError,
}: {
  onError: (message: string) => void;
}) {
  const t = useText(),
    [data, setData] = useState<Data | null>(null),
    [config, setConfig] = useState<Data | null>(null),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const result = await api("/settings");
      setData(result);
      setConfig(result.settings);
    } catch (e) {
      onError((e as Error).message);
    }
  }, [onError]);
  useEffect(() => {
    refresh();
  }, [refresh]);
  if (!data || !config) return <Empty />;
  const groups = [
    ...Object.entries(config.models),
    ...Object.entries(config.role_routes),
  ] as [string, Data[]][];
  function providerRoute(provider: string) {
    return groups
      .flatMap(([, routes]) => routes)
      .find((r) => r.provider === provider)!;
  }
  function change(provider: string, key: string, value: unknown) {
    const next = structuredClone(config!);
    for (const routes of [
      ...Object.values(next.models),
      ...Object.values(next.role_routes),
    ] as Data[][])
      for (const route of routes)
        if (route.provider === provider) route[key] = value;
    setConfig(next);
    setSaved(false);
  }
  function reorder(profile: string, index: number, provider: string) {
    const next = structuredClone(config!);
    const target = profile === "NoveltyJudge" ? next.role_routes : next.models;
    const routes = [...target[profile]];
    if (!provider) routes.splice(index, 1);
    else routes[index] = { ...providerRoute(provider) };
    target[profile] = routes;
    setConfig(next);
    setSaved(false);
  }
  async function save() {
    setBusy(true);
    try {
      await api("/settings", "PUT", config);
      setSaved(true);
      await refresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="notice">
        <ShieldCheck size={16} /> API credentials stay in the local environment.
        Studio shows presence only. Compatibility below is an offline contract
        assessment; model access and service availability have not been tested.
      </div>
      <div className="grid3">
        {data.providers.map((p: Data) => {
          const route = providerRoute(p.provider);
          return (
            <section className="panel" key={p.provider}>
              <div className="panel-title">
                <h2 className="provider-name">
                  {p.provider === "openai"
                    ? "OpenAI"
                    : p.provider === "anthropic"
                      ? "Anthropic"
                      : "Google"}
                </h2>
                <label className="check">
                  <input
                    aria-label={p.provider + " enabled"}
                    type="checkbox"
                    checked={route.enabled}
                    onChange={(e) =>
                      change(p.provider, "enabled", e.target.checked)
                    }
                  />
                  Enabled
                </label>
              </div>
              <p>
                <KeyRound size={13} /> {t("keyPresent")}:{" "}
                <Badge tone={p.key_present ? "teal" : "BLOCKED"}>
                  {p.key_present ? "YES" : "NO"}
                </Badge>
              </p>
              <label>
                Model ID
                <input
                  aria-label={p.provider + " model"}
                  value={route.model}
                  onChange={(e) => change(p.provider, "model", e.target.value)}
                />
              </label>
              <div className="form-grid section-space">
                {["input_cost_per_million", "output_cost_per_million"].map(
                  (key) => (
                    <label key={key}>
                      {key.startsWith("input") ? "Input" : "Output"} / 1M tokens
                      (USD)
                      <input
                        aria-label={p.provider + " " + key}
                        type="number"
                        min="0"
                        step=".01"
                        value={route[key] ?? ""}
                        onChange={(e) =>
                          change(
                            p.provider,
                            key,
                            e.target.value === ""
                              ? null
                              : Number(e.target.value),
                          )
                        }
                      />
                    </label>
                  ),
                )}
              </div>
              <label className="section-space">
                Pricing verified on
                <input
                  type="date"
                  value={route.pricing_verified_on || ""}
                  onChange={(e) =>
                    change(
                      p.provider,
                      "pricing_verified_on",
                      e.target.value || null,
                    )
                  }
                />
              </label>
              <div className="agent-stats">
                <span>{p.calls} calls</span>
                <span>{p.tokens} tokens</span>
                <span>{money(p.cost)}</span>
                <span>{p.average_latency.toFixed(2)}s</span>
              </div>
            </section>
          );
        })}
      </div>
      <section className="panel">
        <div className="panel-title">
          <h3>{t("routes")}</h3>
          <button className="primary" disabled={busy} onClick={save}>
            {saved ? <Check size={15} /> : null}
            {t("save")}
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("profile")}</th>
                <th>Preferred</th>
                <th>Fallback 1</th>
                <th>Fallback 2</th>
                <th>Max output tokens</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(([profile, routes]) => (
                <tr key={profile}>
                  <td className="mono">{profile}</td>
                  {[0, 1, 2].map((index) => (
                    <td key={index}>
                      <select
                        aria-label={profile + " route " + index}
                        value={routes[index]?.provider || ""}
                        onChange={(e) =>
                          reorder(profile, index, e.target.value)
                        }
                      >
                        <option value="">—</option>
                        {["openai", "anthropic", "google"].map((p) => (
                          <option key={p} value={p}>
                            {p} / {providerRoute(p).model}
                          </option>
                        ))}
                      </select>
                    </td>
                  ))}
                  <td>
                    <input
                      type="number"
                      min="128"
                      max="32768"
                      value={routes[0]?.max_output_tokens || 4096}
                      onChange={(e) => {
                        const next = structuredClone(config);
                        const target =
                          profile === "NoveltyJudge"
                            ? next.role_routes
                            : next.models;
                        target[profile].forEach(
                          (r: Data) =>
                            (r.max_output_tokens = Number(e.target.value)),
                        );
                        setConfig(next);
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <h3>Sources / limits</h3>
        <div className="row section-space">
          {["crossref", "openalex", "arxiv"].map((source) => (
            <label key={source} className="check">
              <input
                type="checkbox"
                checked={config.search.adapters.includes(source)}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    search: {
                      ...config.search,
                      adapters: e.target.checked
                        ? [...config.search.adapters, source]
                        : config.search.adapters.filter(
                            (s: string) => s !== source,
                          ),
                    },
                  })
                }
              />
              {source}
            </label>
          ))}
        </div>
        <div className="form-grid section-space">
          {Object.entries(config.live_research_budget || {}).map(
            ([key, value]) => (
              <label key={key}>
                {key.replaceAll("_", " ")}
                <input
                  type="number"
                  min="0"
                  step={key === "max_total_cost" ? ".01" : "1"}
                  max={key === "max_novelty_iterations" ? 3 : undefined}
                  value={Number(value)}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      live_research_budget: {
                        ...config.live_research_budget,
                        [key]: Number(e.target.value),
                      },
                    })
                  }
                />
              </label>
            ),
          )}
          <label>
            Request timeout (seconds, up to 600)
            <input
              type="number"
              min="1"
              max="600"
              value={config.timeout_seconds}
              onChange={(e) =>
                setConfig({
                  ...config,
                  timeout_seconds: Number(e.target.value),
                })
              }
            />
          </label>
        </div>
        <button
          className="primary section-space"
          disabled={busy}
          onClick={save}
        >
          {t("save")}
        </button>
      </section>
      <section className="panel">
        <h3>{t("compatibility")}</h3>
        <div className="table-wrap section-space">
          <table>
            <thead>
              <tr>
                <th>Agent output contract</th>
                <th>OpenAI</th>
                <th>Anthropic</th>
                <th>Google</th>
                <th>Constraint / fallback</th>
              </tr>
            </thead>
            <tbody>
              {data.compatibility.map((c: Data) => (
                <tr key={c.agent}>
                  <td>{c.agent}</td>
                  <td>
                    <Badge tone="teal">{c.openai}</Badge>
                  </td>
                  <td>
                    <Badge
                      tone={c.anthropic === "BLOCKED" ? "BLOCKED" : "teal"}
                    >
                      {c.anthropic}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone="teal">{c.google}</Badge>
                  </td>
                  <td>{c.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
export function Budget({
  runId,
  onError,
}: {
  runId: string;
  onError: (message: string) => void;
}) {
  const t = useText(),
    [data, setData] = useState<Data | null>(null);
  useEffect(() => {
    let live = true;
    const refresh = () =>
      api("/runs/" + runId + "/cost")
        .then((d) => {
          if (live) setData(d);
        })
        .catch((e) => onError(e.message));
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [runId, onError]);
  if (!data) return <Empty />;
  return (
    <section className="panel">
      <div className="panel-title">
        <h3>{t("costTab")}</h3>
        <Badge tone={data.hard_stop ? "BLOCKED" : "teal"}>
          {data.hard_stop ? "HARD STOP" : "BOUNDED RUN"}
        </Badge>
      </div>
      <div className="stats">
        {["budget", "spent", "reserved", "remaining"].map((key) => (
          <div className="stat" key={key}>
            <small>{key}</small>
            <strong>{money(data[key])}</strong>
          </div>
        ))}
      </div>
      <div className="progress">
        <div
          style={{
            width:
              Math.min(
                100,
                ((data.spent + data.reserved) / Math.max(data.budget, 0.001)) *
                  100,
              ) + "%",
          }}
        />
      </div>
      <div className="row section-space">
        {[50, 75, 90].map((n) => (
          <Badge key={n} tone={data.warnings.includes(n) ? "BLOCKED" : ""}>
            {n}%
          </Badge>
        ))}
      </div>
      <div className="grid2 section-space">
        {[
          "model_calls",
          "search_calls",
          "deep_reads",
          "novelty_iterations",
        ].map((key) => (
          <div className="stat" key={key}>
            <small>{key.replaceAll("_", " ")}</small>
            <strong>{data[key]}</strong>
          </div>
        ))}
      </div>
      <Json value={data} />
    </section>
  );
}
