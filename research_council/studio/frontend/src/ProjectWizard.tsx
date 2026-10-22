import { useState } from "react";
import { api, type Data } from "./api";
import { useText, type TextKey } from "./i18n";
export function ProjectWizard({
  done,
  close,
  onError,
}: {
  done: (project: Data) => void;
  close: () => void;
  onError: (error: string) => void;
}) {
  const t = useText(),
    [step, setStep] = useState(0),
    [busy, setBusy] = useState(false);
  const [form, setForm] = useState<Data>({
    title: "",
    topic: "",
    objective: "",
    questions: "",
    domain: "",
    keywords: "",
    constraints: "",
    hardware_constraints: "",
    target_journal: "",
    publication_type: "Research article",
    date_range: "",
    max_papers: 12,
    mode: "novelty",
    budget: 5,
    notes: "",
    practice: true,
    providers: [],
  });
  const groups = [
    ["title", "topic", "objective", "questions", "domain", "keywords"],
    [
      "constraints",
      "hardware_constraints",
      "target_journal",
      "publication_type",
      "date_range",
      "notes",
    ],
    ["max_papers", "mode", "budget"],
  ];
  const labels: Record<string, TextKey> = {
    title: "title",
    topic: "topic",
    objective: "objective",
    questions: "questions",
    domain: "domain",
    keywords: "keywords",
    constraints: "constraints",
    hardware_constraints: "hardwareConstraints",
    target_journal: "journal",
    publication_type: "publication",
    date_range: "dates",
    notes: "notes",
    max_papers: "maxPapers",
    mode: "mode",
    budget: "budget",
  };
  async function save() {
    setBusy(true);
    try {
      const project = await api("/projects", "POST", {
        ...form,
        questions: form.questions.split("\n").filter(Boolean),
        constraints: form.constraints.split("\n").filter(Boolean),
        keywords: form.keywords
          .split(",")
          .map((s: string) => s.trim())
          .filter(Boolean),
      });
      done(project);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={t("newProject")}
      >
        <div className="panel-title">
          <h2>{t("newProject")}</h2>
          <button onClick={close}>{t("close")}</button>
        </div>
        <div className="tabs">
          {groups.map((_, i) => (
            <button
              key={i}
              className={step === i ? "active" : ""}
              onClick={() => setStep(i)}
            >
              {`${i + 1} / ${t("phases").split(" / ")[i]}`}
            </button>
          ))}
        </div>
        <div className="form-grid">
          {groups[step].map((key) => (
            <label
              key={key}
              className={
                [
                  "topic",
                  "objective",
                  "questions",
                  "constraints",
                  "notes",
                ].includes(key)
                  ? "wide"
                  : ""
              }
            >
              {t(labels[key])}
              {key === "mode" ? (
                <select
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                >
                  {["QUICK", "REVIEW", "DEEP", "NOVELTY", "AUDIT"].map((m) => (
                    <option key={m} value={m.toLowerCase()}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : ["questions", "constraints", "notes", "objective"].includes(
                  key,
                ) ? (
                <textarea
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              ) : (
                <input
                  aria-label={t(labels[key])}
                  type={
                    ["budget", "max_papers"].includes(key) ? "number" : "text"
                  }
                  value={form[key]}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      [key]:
                        e.target.type === "number"
                          ? Number(e.target.value)
                          : e.target.value,
                    })
                  }
                />
              )}
            </label>
          ))}
        </div>
        {step === 2 && (
          <>
            {form.mode === "audit" && (
              <label>
                {t("auditClaim")}
                <textarea
                  value={form.audit_claim || ""}
                  onChange={(e) =>
                    setForm({ ...form, audit_claim: e.target.value })
                  }
                />
              </label>
            )}
            <label className="check section-space">
              <input
                type="checkbox"
                checked={form.practice}
                onChange={(e) =>
                  setForm({ ...form, practice: e.target.checked })
                }
              />
              {t("synthetic")}
            </label>
            <div className="row section-space">
              {["openai", "anthropic", "google"].map((provider) => (
                <label key={provider} className="check">
                  <input
                    type="checkbox"
                    disabled={form.practice}
                    checked={form.providers.includes(provider)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        providers: e.target.checked
                          ? [...form.providers, provider]
                          : form.providers.filter(
                              (p: string) => p !== provider,
                            ),
                      })
                    }
                  />
                  {provider}
                </label>
              ))}
            </div>
            <p className="section-space">{t("localPapers")}</p>
          </>
        )}
        <div className="actions">
          {step > 0 && (
            <button onClick={() => setStep(step - 1)}>{t("back")}</button>
          )}
          {step < 2 ? (
            <button className="primary" onClick={() => setStep(step + 1)}>
              {t("next")}
            </button>
          ) : (
            <button
              className="primary"
              disabled={
                busy ||
                form.title.length < 3 ||
                form.topic.length < 3 ||
                (form.mode === "audit" &&
                  (form.audit_claim || "").trim().length < 3)
              }
              onClick={save}
            >
              {t("create")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
