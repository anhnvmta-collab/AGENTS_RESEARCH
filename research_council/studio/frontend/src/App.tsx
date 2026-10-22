import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  FlaskConical,
  LayoutDashboard,
  Plus,
  Settings2,
  ShieldCheck,
  Sun,
  Network,
  FolderOpen,
} from "lucide-react";
import { api, money, type Data } from "./api";
import { en, vi, LocaleContext, useText } from "./i18n";
import { ProjectWizard } from "./ProjectWizard";
import Workspace from "./Workspace";
import Providers from "./Providers";

export function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Empty() {
  const t = useText();
  return (
    <div className="empty">
      <BookOpen size={28} />
      <p>{t("empty")}</p>
    </div>
  );
}
export function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
export default function App() {
  const [lang, setLang] = useState<"en" | "vi">(() =>
    localStorage.getItem("lang") === "vi" ? "vi" : "en",
  );
  const [dark, setDark] = useState(
    () => localStorage.getItem("theme") !== "light",
  );
  const [data, setData] = useState<Data>({ projects: [], runs: [] });
  const [page, setPage] = useState(
    new URLSearchParams(location.search).has("run") ? "workspace" : "dashboard",
  );
  const [error, setError] = useState("");
  const [wizard, setWizard] = useState(false),
    [runId, setRunId] = useState(
      new URLSearchParams(location.search).get("run") || "",
    ),
    [preflight, setPreflight] = useState<Data | null>(null);
  const t = useCallback(
    (key: keyof typeof en) => (lang === "vi" ? vi : en)[key],
    [lang],
  );
  const refresh = useCallback(
    () =>
      api("/dashboard")
        .then(setData)
        .catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    window.history.replaceState(
      null,
      "",
      page === "workspace" ? "?run=" + runId : location.pathname,
    );
  }, [page, runId]);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    localStorage.setItem("lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);
  async function openProject(project: Data) {
    try {
      const details = await api("/projects/" + project.id);
      if (!project.practice && !details.runs.length) {
        const report = await api(
          "/projects/" + project.id + "/preflight",
          "POST",
        );
        setPreflight({ ...report, project });
        return;
      }
      const snapshot = details.runs[0]
        ? { run: details.runs[0] }
        : await api("/projects/" + project.id + "/runs", "POST", {});
      setRunId(snapshot.run.run_id);
      setPage("workspace");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function demo() {
    try {
      const existing = data.projects.find(
        (p: Data) =>
          p.practice &&
          p.title === "Compressed Sensing for FHSS Detection and DOA",
      );
      const project =
        existing ||
        (await api("/projects", "POST", {
          title: "Compressed Sensing for FHSS Detection and DOA",
          topic: "Compressed Sensing for FHSS Detection and DOA",
          practice: true,
          mode: "novelty",
          hardware_constraints:
            "Synthetic FPGA latency and fixed-point exercise",
        }));
      await refresh();
      await openProject(project);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <LocaleContext.Provider value={{ lang, t }}>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-icon">
              <Network size={24} />
            </div>
            <div>
              RESEARCH
              <br />
              <strong>COUNCIL</strong>
              <small>STUDIO / LOCAL</small>
            </div>
          </div>
          <div className="nav-label">WORKSPACE</div>
          <button
            className={page === "dashboard" ? "nav active" : "nav"}
            onClick={() => setPage("dashboard")}
          >
            <LayoutDashboard size={18} />
            {t("dashboard")}
          </button>
          <button
            className={page === "projects" ? "nav active" : "nav"}
            onClick={() => setPage("projects")}
          >
            <FolderOpen size={18} />
            {t("projects")}
            <span className="nav-count">{data.projects.length}</span>
          </button>
          <button
            className={page === "providers" ? "nav active" : "nav"}
            onClick={() => setPage("providers")}
          >
            <Settings2 size={18} />
            {t("providers")}
          </button>
          <div className="sidebar-bottom">
            <ShieldCheck size={18} />
            <div>
              {t("local")}
              <small>127.0.0.1 · Evidence first</small>
            </div>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <span>{t("subtitle")}</span>
            <div className="row">
              <span className="connection">
                <i />
                {t("connected")}
              </span>
              <button
                className="icon"
                aria-label={t("theme")}
                onClick={() => setDark(!dark)}
              >
                <Sun size={17} />
              </button>
              <select
                aria-label={t("language")}
                value={lang}
                onChange={(e) => setLang(e.target.value as "en" | "vi")}
              >
                <option value="en">EN</option>
                <option value="vi">VI</option>
              </select>
              <span className="avatar">RC</span>
            </div>
          </header>
          <main>
            {error && (
              <div role="alert" className="error" onClick={() => setError("")}>
                {error}
              </div>
            )}
            {page !== "workspace" && (
              <div className="page-heading">
                <div>
                  <div className="eyebrow">RESEARCH COUNCIL STUDIO</div>
                  <h1>
                    {t(
                      page === "providers"
                        ? "providers"
                        : page === "projects"
                          ? "library"
                          : "dashboard",
                    )}
                  </h1>
                </div>
                <button className="primary" onClick={() => setWizard(true)}>
                  <Plus size={16} />
                  {t("newProject")}
                </button>
              </div>
            )}
            {page !== "providers" && page !== "workspace" && (
              <>
                <section className="welcome">
                  <div>
                    <Badge tone="teal">{t("recommended")}</Badge>
                    <h2>{t("welcome")}</h2>
                    <p>{t("welcomeText")}</p>
                    <div className="row">
                      <button className="primary" onClick={demo}>
                        <FlaskConical size={17} />
                        {t("practice")}
                        <ArrowUpRight size={16} />
                      </button>
                      <button onClick={() => setPage("projects")}>
                        {t("open")}
                      </button>
                      <button
                        className="text-button"
                        onClick={() => setPage("providers")}
                      >
                        {t("configure")}
                      </button>
                    </div>
                  </div>
                  <div className="orb">
                    <Network size={100} />
                    <span>
                      20 SPECIALIST AGENTS
                      <br />
                      ONE EVIDENCE TRAIL
                    </span>
                  </div>
                </section>
                <div className="stats">
                  {(
                    [
                      "papers",
                      "evidence",
                      "novelty",
                      "reviews",
                      "agents",
                      "cost",
                      "srl",
                    ] as const
                  ).map((key) => (
                    <div className="stat" key={key}>
                      <small>{t(key)}</small>
                      <strong>
                        {key === "cost"
                          ? money(data.cost)
                          : key === "srl"
                            ? "SRL-0"
                            : data[key === "agents" ? "running_agents" : key] ||
                              0}
                      </strong>
                      <span>
                        {key === "srl" ? "Evidence required" : t("local")}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="dashboard-grid">
                  <section className="panel">
                    <div className="panel-title">
                      <h3>{t("library")}</h3>
                      <Badge>{data.projects.length}</Badge>
                    </div>
                    {data.projects.length ? (
                      data.projects.map((p: Data) => (
                        <button
                          className="project-card"
                          key={p.id}
                          onClick={() => openProject(p)}
                        >
                          <FolderOpen />
                          <div>
                            <strong>{p.title}</strong>
                            <p>{p.topic}</p>
                          </div>
                          <Badge tone="teal">
                            {p.practice ? "PRACTICE" : "REAL"}
                          </Badge>
                          <ArrowUpRight size={17} />
                        </button>
                      ))
                    ) : (
                      <div className="empty">
                        <FlaskConical size={32} />
                        <p>{t("noProjects")}</p>
                      </div>
                    )}
                  </section>
                  <section className="panel">
                    <div className="panel-title">
                      <h3>{t("recent")}</h3>
                      <Activity size={17} />
                    </div>
                    {data.runs.length ? (
                      data.runs.map((r: Data) => (
                        <button
                          className="record run-record"
                          key={r.run_id}
                          onClick={() => {
                            setRunId(r.run_id);
                            setPage("workspace");
                          }}
                        >
                          <strong>{r.question.topic}</strong>
                          <Badge>{r.status}</Badge>
                        </button>
                      ))
                    ) : (
                      <div className="empty">
                        <Activity size={28} />
                        <p>{t("noRuns")}</p>
                      </div>
                    )}
                  </section>
                </div>
              </>
            )}
            {page === "workspace" && (
              <Workspace
                runId={runId}
                back={() => {
                  setPage("dashboard");
                  refresh();
                }}
                onError={setError}
              />
            )}
            {page === "providers" && <Providers onError={setError} />}
            {preflight && (
              <div className="modal-backdrop">
                <div
                  className="modal"
                  role="dialog"
                  aria-label={t("preflight")}
                >
                  <div className="panel-title">
                    <h2>{t("preflight")}</h2>
                    <button onClick={() => setPreflight(null)}>
                      {t("close")}
                    </button>
                  </div>
                  <p>{t("realConsent")}</p>
                  <Json value={preflight} />
                  <button
                    className="primary"
                    disabled={!preflight.ready}
                    onClick={async () => {
                      try {
                        const result = await api(
                          "/projects/" + preflight.project.id + "/runs",
                          "POST",
                          { confirmation: "START REAL RESEARCH" },
                        );
                        setRunId(result.run.run_id);
                        setPage("workspace");
                        setPreflight(null);
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    {t("confirmReal")}
                  </button>
                </div>
              </div>
            )}
            {wizard && (
              <ProjectWizard
                close={() => setWizard(false)}
                onError={setError}
                done={(project) => {
                  setWizard(false);
                  refresh();
                  openProject(project);
                }}
              />
            )}
          </main>
          <footer>
            RESEARCH COUNCIL <span>Evidence → Claims → Gaps → Novelty</span>
            <span>Scientific readiness requires independent review</span>
          </footer>
        </div>
      </div>
    </LocaleContext.Provider>
  );
}
