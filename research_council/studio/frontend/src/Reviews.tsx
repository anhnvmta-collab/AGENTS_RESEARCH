import { useEffect, useState } from "react";
import { api, short, type Data } from "./api";
import { Badge, Json } from "./App";
import { Fields } from "./Novelty";
import { useText } from "./i18n";
export function Reviews({
  snapshot,
  onError,
}: {
  snapshot: Data;
  onError: (message: string) => void;
}) {
  const t = useText(),
    { run, state } = snapshot,
    [history, setHistory] = useState<Data[]>([]),
    [reviewer, setReviewer] = useState(""),
    [note, setNote] = useState(""),
    [claim, setClaim] = useState(""),
    [checked, setChecked] = useState<string[]>([]);
  const checks = [
    "source_identity_checked",
    "source_locations_checked",
    "scientific_entailment_checked",
    "retraction_status_checked",
  ];
  useEffect(() => {
    api<Data[]>("/runs/" + run.run_id + "/decisions")
      .then(setHistory)
      .catch((e) => onError(e.message));
  }, [run.run_id, onError, state.pending_approval]);
  async function attest() {
    try {
      await api("/runs/" + run.run_id + "/attest", "POST", {
        claim_id: claim,
        reviewer,
        note,
        ...Object.fromEntries(checks.map((key) => [key, true])),
      });
      setChecked([]);
    } catch (e) {
      onError((e as Error).message);
    }
  }
  return (
    <>
      <div className="grid2">
        <section className="panel">
          <h3>{t("reviews")}</h3>
          {history.map((r: Data, i: number) => (
            <div className="record" key={i}>
              <div>
                <strong>{r.reviewer}</strong>
                <p>{r.comment || r.note}</p>
                <small>{r.at}</small>
              </div>
              <Badge>{r.action || r.kind}</Badge>
            </div>
          ))}
        </section>
        <section className="panel">
          <h3>Scientific quality gates</h3>
          {state.gates.map((g: Data) => (
            <div className="card section-space" key={g.gate_id}>
              <Badge tone={g.passed ? "SUCCESS" : "BLOCKED"}>
                GATE {g.gate} / {g.passed ? "PASS" : "BLOCKED"}
              </Badge>
              <Fields
                value={g}
                keys={["reasons", "candidate_id", "candidate_revision"]}
              />
            </div>
          ))}
        </section>
      </div>
      <section className="panel">
        <h3>ReviewerTwo / independent skeptical reviews</h3>
        {state.reviews.map((r: Data) => (
          <div className="card section-space" key={r.review_id}>
            <div className="panel-title">
              <h4>
                {short(r.candidate_id)} / v{r.revision}
              </h4>
              <Badge>
                {r.verdict} / {r.provider_independence}
              </Badge>
            </div>
            <Fields value={r} keys={["complete", "provider", "reasons"]} />
          </div>
        ))}
      </section>
      <section className="panel">
        <h3>Scientific source attestation</h3>
        <div className="notice">
          Workflow approval does not verify a claim. Source identity, location,
          entailment and retraction checks must be performed by the named
          researcher. Synthetic evidence cannot be attested.
        </div>
        <div className="form-grid">
          <label>
            Claim
            <select value={claim} onChange={(e) => setClaim(e.target.value)}>
              <option value="">—</option>
              {state.claims.map((c: Data) => (
                <option key={c.claim_id} value={c.claim_id}>
                  {short(c.claim_id)} / {c.statement.slice(0, 80)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("reviewer")}
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
            />
          </label>
          <label className="wide">
            Review note (at least 20 characters)
            <textarea value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {checks.map((key) => (
            <label className="check" key={key}>
              <input
                type="checkbox"
                checked={checked.includes(key)}
                onChange={(e) =>
                  setChecked(
                    e.target.checked
                      ? [...checked, key]
                      : checked.filter((c) => c !== key),
                  )
                }
              />
              {key.replaceAll("_", " ")}
            </label>
          ))}
        </div>
        <button
          className="primary section-space"
          disabled={
            run.provenance === "fixture" ||
            checked.length !== 4 ||
            !claim ||
            reviewer.trim().length < 2 ||
            note.length < 20 ||
            state.pending_approval !== "before_final_report"
          }
          onClick={attest}
        >
          {t("save")}
        </button>
        <details>
          <summary>Citation audit records</summary>
          <Json value={state.audits} />
        </details>
      </section>
    </>
  );
}
