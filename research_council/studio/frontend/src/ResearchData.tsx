import { useState } from "react";
import { Upload, ArrowRight } from "lucide-react";
import { api, short, type Data } from "./api";
import { Badge, Empty, Json } from "./App";
import { useText } from "./i18n";
export type Selection = { kind: string; id: string } | null;
export function RecordInspector({
  state,
  selected,
  select,
}: {
  state: Data;
  selected: Selection;
  select: (value: Selection) => void;
}) {
  const t = useText();
  if (!selected) return null;
  const { kind, id } = selected,
    field: Record<string, string> = {
      paper: "candidates",
      evidence: "evidence",
      claim: "claims",
      gap: "gaps",
      novelty: "novelty_candidates",
    };
  const item = state[field[kind]].find(
    (x: Data) =>
      (kind === "paper"
        ? x.paper.paper_id
        : x[kind === "novelty" ? "candidate_id" : kind + "_id"]) === id,
  );
  if (!item) return null;
  const paper = kind === "paper" ? item.paper : null;
  const evidence =
    kind === "paper"
      ? state.evidence.filter((e: Data) => e.paper_id === id)
      : kind === "evidence"
        ? [item]
        : state.evidence.filter((e: Data) =>
            (item.evidence_ids || []).includes(e.evidence_id),
          );
  const claims = state.claims.filter(
    (c: Data) =>
      (kind === "claim" && c.claim_id === id) ||
      c.evidence_ids.some((eid: string) =>
        evidence.some((e: Data) => e.evidence_id === eid),
      ),
  );
  const gaps = state.gaps.filter(
    (g: Data) =>
      (kind === "gap" && g.gap_id === id) ||
      g.evidence_ids.some((eid: string) =>
        evidence.some((e: Data) => e.evidence_id === eid),
      ),
  );
  const novelty = state.novelty_candidates.filter(
    (n: Data) =>
      (kind === "novelty" && n.candidate_id === id) ||
      n.gap_ids.some((gid: string) => gaps.some((g: Data) => g.gap_id === gid)),
  );
  const papers = state.candidates.filter(
    (p: Data) =>
      paper?.paper_id === p.paper.paper_id ||
      evidence.some((e: Data) => e.paper_id === p.paper.paper_id),
  );
  return (
    <div className="modal-backdrop">
      <div className="modal large" role="dialog" aria-label={kind + " detail"}>
        <div className="panel-title">
          <div>
            <Badge>
              {kind.toUpperCase()} / {short(id)}
            </Badge>
            <h2 className="section-space">
              {paper?.metadata.title ||
                item.normalized_statement ||
                item.statement ||
                item.opportunity ||
                item.what_is_new}
            </h2>
          </div>
          <button onClick={() => select(null)}>{t("close")}</button>
        </div>
        <h3>{t("trace")}</h3>
        <div className="trace-graph">
          {[
            ["paper", papers.map((p: Data) => p.paper)],
            ["evidence", evidence],
            ["claim", claims],
            ["gap", gaps],
            ["novelty", novelty],
          ].map(([k, rows], index) => (
            <div className="trace-column" key={k as string}>
              {index > 0 && <ArrowRight size={13} />}
              <h4>{String(k).toUpperCase()}</h4>
              {(rows as Data[]).map((r: Data, i: number) => {
                const key = r[k === "novelty" ? "candidate_id" : k + "_id"];
                return (
                  <button
                    className="link"
                    key={key + ":" + i}
                    onClick={() => select({ kind: k as string, id: key })}
                  >
                    {short(key)} {r.revision ? "v" + r.revision : ""}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        {kind === "evidence" && (
          <>
            <Badge tone={item.verification_status}>
              {item.verification_status}
            </Badge>
            <blockquote>{item.verbatim_excerpt}</blockquote>
            <div className="kv">
              <span>Location</span>
              <div>
                {item.source_location} · p.{item.page || "—"} ·{" "}
                {item.section || "—"}
              </div>
            </div>
            <div className="kv">
              <span>Interpretation</span>
              <div>{item.agent_interpretation || "—"}</div>
            </div>
            <div className="kv">
              <span>Confidence</span>
              <div>{item.confidence}</div>
            </div>
            <h4 className="section-space">{t("sourceContext")}</h4>
            <pre className="json">
              {papers[0]?.paper.page_texts?.[item.page] ||
                papers[0]?.paper.source_text ||
                "Source context unavailable"}
            </pre>
          </>
        )}
        {paper && (
          <>
            <div className="kv">
              <span>Authors / year / venue</span>
              <div>
                {paper.metadata.authors.join(", ")} ·{" "}
                {paper.metadata.year || "—"} · {paper.metadata.venue || "—"}
              </div>
            </div>
            <div className="kv">
              <span>DOI / provenance</span>
              <div>
                {paper.metadata.doi || "—"} · {paper.provenance} /{" "}
                {paper.source_kind}
              </div>
            </div>
            <p className="section-space">
              {paper.metadata.abstract || "Abstract unavailable"}
            </p>
            <h4>
              Extracted methodology / signal model / hardware / results /
              limitations
            </h4>
            <Json
              value={
                state.matrix.find((r: Data) => r.paper_id === id) || {
                  status: "Not extracted at this checkpoint",
                }
              }
            />
            <h4>Related papers</h4>
            {state.candidates
              .filter((c: Data) => c.paper.paper_id !== id)
              .map((c: Data) => (
                <button
                  key={c.paper.paper_id}
                  className="link"
                  onClick={() =>
                    select({ kind: "paper", id: c.paper.paper_id })
                  }
                >
                  {c.paper.metadata.title}
                </button>
              ))}
          </>
        )}
        <details>
          <summary>Canonical structured record</summary>
          <Json value={item} />
        </details>
      </div>
    </div>
  );
}
export function ResearchData({
  snapshot,
  view,
  onError,
}: {
  snapshot: Data;
  view: string;
  onError: (message: string) => void;
}) {
  const t = useText(),
    { state, run } = snapshot,
    [selected, select] = useState<Selection>(null),
    [query, setQuery] = useState(""),
    [year, setYear] = useState(""),
    [source, setSource] = useState(""),
    [core, setCore] = useState(false),
    [doi, setDoi] = useState(false),
    [score, setScore] = useState(0),
    [category, setCategory] = useState<Data | null>(null),
    [uploads, setUploads] = useState<Data[]>([]),
    [busy, setBusy] = useState(false);
  async function upload(files: FileList | File[] | null) {
    if (!files) return;
    setBusy(true);
    try {
      const form = new FormData();
      Array.from(files).forEach((file) => form.append("files", file));
      const result = await api<Data[]>(
        "/projects/" + run.project_id + "/documents",
        "POST",
        form,
      );
      setUploads((old) => [...old, ...result]);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  let candidates = state.candidates.filter((c: Data) => {
    const text = JSON.stringify([
      c.paper.metadata,
      state.matrix.find((r: Data) => r.paper_id === c.paper.paper_id)?.fields,
    ]).toLowerCase();
    return (
      text.includes(query.toLowerCase()) &&
      (!year || String(c.paper.metadata.year) === year) &&
      (!source ||
        c.discovery_sources.includes(source) ||
        c.paper.metadata.metadata_source === source) &&
      (!core || state.core_paper_ids.includes(c.paper.paper_id)) &&
      (!doi || (c.paper.metadata.doi && c.paper.metadata.metadata_verified)) &&
      (c.aggregate_score || 0) >= score &&
      (!category || category.paper_ids.includes(c.paper.paper_id))
    );
  });
  if (view !== "papers" && view !== "literature") candidates = [];
  const sources = [
    ...new Set<string>(
      state.candidates.flatMap((c: Data) => [
        ...c.discovery_sources,
        c.paper.metadata.metadata_source,
      ]),
    ),
  ];
  function mapNode(node: Data, depth = 0): React.ReactNode {
    return (
      <div key={node.topic} style={{ marginLeft: depth ? 15 : 0 }}>
        <button className="map-node" onClick={() => setCategory(node)}>
          <span>{node.topic}</span>
          <Badge>{node.paper_ids.length}</Badge>
        </button>
        {node.subtopics.map((n: Data) => mapNode(n, depth + 1))}
      </div>
    );
  }
  return (
    <>
      <div className="panel-title">
        <h3>
          {t(
            view === "literature"
              ? "literature"
              : view === "papers"
                ? "papers"
                : view === "claims"
                  ? "claims"
                  : "evidence",
          )}
        </h3>
        <Badge>{run.provenance}</Badge>
      </div>
      {(view === "papers" || view === "literature") && (
        <>
          {view === "papers" && (
            <div
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                upload(e.dataTransfer.files);
              }}
            >
              <Upload size={22} />
              <p>{t("uploadHint")}</p>
              <label className="upload-label">
                {busy ? "PARSING…" : t("upload")}
                <input
                  aria-label={t("upload")}
                  type="file"
                  accept="application/pdf"
                  multiple
                  disabled={busy}
                  onChange={(e) => upload(e.target.files)}
                />
              </label>
              <small>
                LocalDocumentScout · parsed files join a run before first start,
                otherwise the next run.
              </small>
              {uploads.map((u) => (
                <div className="record" key={u.id}>
                  {u.filename}
                  <Badge tone={u.status === "FAILED" ? "FAILED" : "SUCCESS"}>
                    {u.status} / {u.job_status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
          <div className="filters">
            <input
              aria-label={t("search")}
              placeholder={t("search")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <input
              aria-label={t("year")}
              placeholder={t("year")}
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
            />
            <select
              aria-label={t("source")}
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option value="">
                {t("all")} / {t("source")}
              </option>
              {sources.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <label className="check">
              <input
                type="checkbox"
                checked={core}
                onChange={(e) => setCore(e.target.checked)}
              />
              {t("core")}
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={doi}
                onChange={(e) => setDoi(e.target.checked)}
              />
              {t("verifiedDoi")}
            </label>
            <label>
              {t("relevance")}
              <input
                type="number"
                step=".1"
                min="0"
                max="1"
                value={score}
                onChange={(e) => setScore(Number(e.target.value))}
              />
            </label>
          </div>
          <div className={view === "literature" ? "map-grid" : ""}>
            {view === "literature" && (
              <section className="panel">
                <p>{t("observed")}</p>
                {mapNode(snapshot.observed_map)}
                {category && (
                  <button onClick={() => setCategory(null)}>{t("all")}</button>
                )}
              </section>
            )}
            <section className="panel table-wrap">
              {!candidates.length ? (
                <Empty />
              ) : (
                <table>
                  <thead>
                    <tr>
                      {[
                        "Title / authors",
                        "Year / venue",
                        "DOI / source",
                        "Score / priority",
                        "Read / evidence",
                        "Citation",
                      ].map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c: Data) => {
                      const p = c.paper,
                        e = state.evidence.filter(
                          (e: Data) => e.paper_id === p.paper_id,
                        ),
                        audit = state.audits.find(
                          (a: Data) => a.paper_id === p.paper_id,
                        );
                      return (
                        <tr
                          className="clickable"
                          key={p.paper_id}
                          onClick={() =>
                            select({ kind: "paper", id: p.paper_id })
                          }
                        >
                          <td className="title-cell">
                            <strong>{p.metadata.title}</strong>
                            <small>{p.metadata.authors.join(", ")}</small>
                          </td>
                          <td>
                            {p.metadata.year || "—"}
                            <small>{p.metadata.venue || "—"}</small>
                          </td>
                          <td>
                            {p.metadata.doi || "—"}
                            <small>{c.discovery_sources.join(", ")}</small>
                          </td>
                          <td>
                            {(c.aggregate_score || 0).toFixed(3)}
                            <small>
                              {state.core_paper_ids.includes(p.paper_id)
                                ? "CORE"
                                : c.aggregate_score >= 0.5
                                  ? "IMPORTANT"
                                  : "SUPPORTING"}
                            </small>
                          </td>
                          <td>
                            <Badge tone={e.length ? "SUCCESS" : ""}>
                              {e.length ? "READ" : "UNREAD"}
                            </Badge>
                            <small>{e.length} evidence</small>
                          </td>
                          <td>
                            <Badge tone={audit?.status}>
                              {audit?.status || "UNVERIFIED"}
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </section>
          </div>
        </>
      )}
      {view === "evidence" && (
        <section className="panel">
          {!state.evidence.length ? (
            <Empty />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID / paper</th>
                    <th>Location</th>
                    <th>Excerpt / statement</th>
                    <th>Verification</th>
                    <th>Confidence / claims</th>
                  </tr>
                </thead>
                <tbody>
                  {state.evidence.map((e: Data) => (
                    <tr
                      className="clickable"
                      key={e.evidence_id}
                      onClick={() =>
                        select({ kind: "evidence", id: e.evidence_id })
                      }
                    >
                      <td>
                        {short(e.evidence_id)}
                        <small>
                          {
                            state.candidates.find(
                              (c: Data) => c.paper.paper_id === e.paper_id,
                            )?.paper.metadata.title
                          }
                        </small>
                      </td>
                      <td>
                        {e.source_location}
                        <small>
                          p.{e.page || "—"} / {e.section || "—"}
                        </small>
                      </td>
                      <td className="title-cell">
                        <blockquote>{e.verbatim_excerpt}</blockquote>
                        <small>{e.normalized_statement}</small>
                      </td>
                      <td>
                        <Badge tone={e.verification_status}>
                          {e.verification_status}
                        </Badge>
                        <small>{e.provenance}</small>
                      </td>
                      <td>
                        {e.confidence}
                        <small>
                          {
                            state.claims.filter((c: Data) =>
                              c.evidence_ids.includes(e.evidence_id),
                            ).length
                          }{" "}
                          linked claims
                        </small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {view === "claims" && (
        <section className="panel">
          <h3>{t("trace")}</h3>
          <div className="graph">
            {["PAPER", "EVIDENCE", "CLAIM", "GAP", "NOVELTY"].map((name) => (
              <div className="graph-node" key={name}>
                {name}
                <ArrowRight size={15} />
              </div>
            ))}
          </div>
          {!state.claims.length ? (
            <Empty />
          ) : (
            state.claims.map((c: Data) => (
              <div className="card" key={c.claim_id}>
                <div className="panel-title">
                  <Badge>{c.claim_type}</Badge>
                  <Badge tone={c.verification_status}>
                    {c.verification_status}
                  </Badge>
                </div>
                <h4>{c.statement}</h4>
                <button
                  className="link"
                  onClick={() => select({ kind: "claim", id: c.claim_id })}
                >
                  {t("trace")} → {short(c.claim_id)}
                </button>
                <div className="row">
                  {c.evidence_ids.map((id: string) => (
                    <button
                      className="link"
                      key={id}
                      onClick={() => select({ kind: "evidence", id })}
                    >
                      Evidence {short(id)}
                    </button>
                  ))}
                </div>
              </div>
            ))
          )}
        </section>
      )}
      <RecordInspector state={state} selected={selected} select={select} />
    </>
  );
}
