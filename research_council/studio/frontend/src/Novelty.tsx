import { useState } from "react";
import { ShieldAlert, Swords, ArrowRight, Lightbulb } from "lucide-react";
import { api, short, type Data } from "./api";
import { Badge, Empty } from "./App";
import { RecordInspector, type Selection } from "./ResearchData";
import { useText } from "./i18n";
export function Fields({ value, keys }: { value: Data; keys: string[] }) {
  return (
    <>
      {keys.map((key) => (
        <div className="kv" key={key}>
          <span>{key.replaceAll("_", " ")}</span>
          <div>
            {Array.isArray(value[key])
              ? value[key].length
                ? value[key].map((v: unknown, i: number) => (
                    <div key={i}>
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </div>
                  ))
                : "—"
              : value[key] === undefined ||
                  value[key] === null ||
                  value[key] === ""
                ? "—"
                : typeof value[key] === "object"
                  ? Object.entries(value[key]).map(([k, v]) => (
                      <div key={k}>
                        {k}: {String(v)}
                      </div>
                    ))
                  : String(value[key])}
          </div>
        </div>
      ))}
    </>
  );
}
export function NoveltyViews({
  snapshot,
  gaps,
  onError,
}: {
  snapshot: Data;
  gaps: boolean;
  onError: (error: string) => void;
}) {
  const t = useText(),
    { state, run } = snapshot,
    [selected, select] = useState<Selection>(null),
    [battle, setBattle] = useState(false),
    [active, setActive] = useState(""),
    [revision, setRevision] = useState(0),
    [notice, setNotice] = useState("");
  async function propose(agent: string, task: string) {
    try {
      const p = await api("/agents/" + agent + "/propose-action", "POST", {
        run_id: run.run_id,
        task,
      });
      setNotice(
        "Proposal " +
          short(p.id) +
          " awaits named approval in Agents → " +
          agent,
      );
    } catch (e) {
      onError((e as Error).message);
    }
  }
  const ids = [
    ...new Set<string>(
      state.novelty_candidates.map((n: Data) => n.candidate_id),
    ),
  ];
  const revisions = state.novelty_candidates
    .filter((n: Data) => n.candidate_id === (active || ids[0]))
    .sort((a: Data, b: Data) => a.revision - b.revision);
  const candidate =
    revisions.find((n: Data) => n.revision === revision) || revisions.at(-1);
  const art = state.prior_art.find(
    (p: Data) =>
      p.candidate_id === candidate?.candidate_id &&
      p.revision === candidate?.revision,
  );
  const review = state.reviews.find(
    (p: Data) =>
      p.candidate_id === candidate?.candidate_id &&
      p.revision === candidate?.revision,
  );
  const decision = state.decisions.find(
    (p: Data) =>
      p.candidate_id === candidate?.candidate_id &&
      p.revision === candidate?.revision,
  );
  return (
    <>
      <div className="panel-title">
        <div>
          <div className="eyebrow">EVIDENCE → LIMITATION → CONTRIBUTION</div>
          <h3>{gaps ? t("gaps") : battle ? t("battle") : "NOVELTY LAB"}</h3>
        </div>
        {!gaps && (
          <button onClick={() => setBattle(!battle)}>
            <Swords size={16} />
            {battle ? "NOVELTY LAB" : t("battle")}
          </button>
        )}
      </div>
      {notice && <div className="notice">{notice}</div>}
      {gaps ? (
        <>
          {!state.gaps.length ? (
            <Empty />
          ) : (
            <div className="grid2">
              {state.gaps.map((gap: Data) => (
                <section className="panel" key={gap.gap_id}>
                  <div className="panel-title">
                    <Badge>{gap.gap_type}</Badge>
                    <Badge>{short(gap.gap_id)}</Badge>
                  </div>
                  <h2 className="gap-title">{gap.opportunity}</h2>
                  <Fields
                    value={gap}
                    keys={[
                      "known_prior_approaches",
                      "limitation",
                      "consequence",
                      "confidence",
                      "potential_counterexample",
                      "search_scope",
                    ]}
                  />
                  <div className="row section-space">
                    <button
                      className="link"
                      onClick={() => select({ kind: "gap", id: gap.gap_id })}
                    >
                      {gap.evidence_ids.length} evidence → {t("trace")}
                    </button>
                  </div>
                  <div className="row section-space">
                    {[
                      ["GapMiner", t("investigate")],
                      ["PriorArtHunter", t("askPriorArt")],
                      ["NoveltyGenerator", t("generateNovelty")],
                      ["GapMiner", t("rejectGap")],
                      ["GapMiner", t("addNote")],
                    ].map(([agent, label]) => (
                      <button
                        key={label}
                        onClick={() => {
                          const instruction = window.prompt(
                            label,
                            label + " " + gap.gap_id,
                          );
                          if (instruction) propose(agent, instruction);
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </>
      ) : !candidate ? (
        <Empty />
      ) : (
        <>
          <div className="row section-space">
            <select
              aria-label="Novelty candidate"
              value={active || ids[0]}
              onChange={(e) => {
                setActive(e.target.value);
                setRevision(0);
              }}
            >
              {ids.map((id) => (
                <option key={id} value={id}>
                  {short(id)}
                </option>
              ))}
            </select>
            <Badge>{candidate.risk_level}</Badge>
            <Badge>v{candidate.revision}</Badge>
            <Badge>{decision?.verdict || "UNRESOLVED"}</Badge>
          </div>
          <div className="timeline section-space">
            {revisions.map((n: Data, i: number) => (
              <div key={n.revision}>
                <button
                  className={candidate.revision === n.revision ? "primary" : ""}
                  onClick={() => setRevision(n.revision)}
                >
                  v{n.revision}
                  <small>
                    {n.revision_summary || "Initial / requested revision"}
                  </small>
                </button>
                <span>
                  <ShieldAlert size={12} /> Prior art → ReviewerTwo → Judge
                </span>
                {i < revisions.length - 1 && <ArrowRight size={15} />}
              </div>
            ))}
          </div>
          {!battle ? (
            <div className="grid2">
              <section className="panel">
                <div className="panel-title">
                  <Lightbulb size={21} />
                  <Badge>{short(candidate.candidate_id)}</Badge>
                </div>
                <h2 className="gap-title">{candidate.normalized_claim}</h2>
                <Fields
                  value={candidate}
                  keys={[
                    "what_is_new",
                    "why_it_matters",
                    "why_prior_methods_insufficient",
                    "proposed_method",
                    "mathematical_change",
                    "implementation_change",
                    "validation_plan",
                    "falsification_test",
                  ]}
                />
                <button
                  className="link section-space"
                  onClick={() =>
                    select({ kind: "novelty", id: candidate.candidate_id })
                  }
                >
                  {t("trace")} → {candidate.evidence_ids.length} evidence
                </button>
              </section>
              <section className="panel">
                <h3>{t("timeline")}</h3>
                <Fields
                  value={candidate}
                  keys={[
                    "revision_summary",
                    "change_reason",
                    "trigger_prior_art_ids",
                    "risk_level",
                    "generator_provider",
                    "generation_execution_id",
                  ]}
                />
                {candidate.revision > 1 && (
                  <div className="notice">
                    {Object.keys(candidate)
                      .filter(
                        (key) =>
                          typeof candidate[key] === "string" &&
                          candidate[key] !==
                            revisions.find(
                              (n: Data) =>
                                n.revision === candidate.revision - 1,
                            )?.[key],
                      )
                      .map((key) => (
                        <div key={key}>
                          <strong>{key.replaceAll("_", " ")}:</strong>{" "}
                          {candidate[key]}
                        </div>
                      ))}
                  </div>
                )}
                <h4 className="section-space">Closest prior art</h4>
                {art?.matches?.length ? (
                  art.matches.map((m: Data) => (
                    <div className="card" key={m.match_id}>
                      <button
                        className="link"
                        onClick={() =>
                          select({ kind: "paper", id: m.paper_id })
                        }
                      >
                        {short(m.paper_id)} → source
                      </button>
                      <Fields
                        value={m}
                        keys={[
                          "overlap",
                          "similarity",
                          "invalidates",
                          "severity",
                        ]}
                      />
                    </div>
                  ))
                ) : (
                  <p>
                    No grounded overlap match recorded. This does not establish
                    novelty.
                  </p>
                )}
                <button onClick={() => setBattle(true)}>
                  <Swords size={15} />
                  {t("battle")}
                </button>
              </section>
            </div>
          ) : (
            <div className="battle-grid">
              <section className="panel">
                <Badge tone="teal">NOVELTY GENERATOR</Badge>
                <h3 className="section-space">{candidate.normalized_claim}</h3>
                <Fields
                  value={candidate}
                  keys={[
                    "what_is_new",
                    "proposed_method",
                    "validation_plan",
                    "evidence_ids",
                    "revision_summary",
                  ]}
                />
              </section>
              <section className="panel">
                <Badge>PRIOR ART HUNTER</Badge>
                {art ? (
                  <>
                    <Badge tone={art.complete ? "SUCCESS" : "BLOCKED"}>
                      {art.complete ? "COMPLETE" : "INCOMPLETE"}
                    </Badge>
                    <Fields
                      value={art}
                      keys={[
                        "queries",
                        "matches",
                        "search_failures",
                        "discovered_evidence",
                      ]}
                    />
                  </>
                ) : (
                  <Empty />
                )}
              </section>
              <section className="panel">
                <Badge>REVIEWER #2</Badge>
                {review ? (
                  <>
                    <h3 className="section-space">{review.verdict}</h3>
                    <Badge>{review.provider_independence}</Badge>
                    {review.reasons.map((r: Data, i: number) => (
                      <div className="card section-space" key={i}>
                        <Badge tone={r.severity === "HIGH" ? "BLOCKED" : ""}>
                          {r.severity} / {r.category}
                        </Badge>
                        <p>{r.explanation}</p>
                        <small>{r.resolved ? "RESOLVED" : "OPEN"}</small>
                      </div>
                    ))}
                  </>
                ) : (
                  <Empty />
                )}
              </section>
              <section className="panel">
                <Badge>NOVELTY JUDGE</Badge>
                {decision ? (
                  <>
                    <h2 className="section-space">{decision.verdict}</h2>
                    <Fields
                      value={decision}
                      keys={[
                        "novelty_confidence",
                        "closest_prior_art",
                        "required_followup_searches",
                        "remaining_risks",
                        "model_verdict",
                        "policy_overrides",
                      ]}
                    />
                  </>
                ) : (
                  <Empty />
                )}
              </section>
            </div>
          )}
        </>
      )}
      <RecordInspector state={state} selected={selected} select={select} />
    </>
  );
}
