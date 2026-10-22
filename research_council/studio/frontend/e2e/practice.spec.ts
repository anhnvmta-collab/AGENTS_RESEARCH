import { test, expect, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import type { Data } from "../src/api";

async function snapshot(page: Page, id: string): Promise<Data> {
  return (await page.request.get("/api/runs/" + id)).json();
}
async function shot(page: Page, name: string) {
  await mkdir("../../docs/screenshots", { recursive: true });
  await page.screenshot({
    path: "../../docs/screenshots/" + name + ".png",
    fullPage: true,
  });
}
async function tab(page: Page, label: string) {
  await page
    .getByRole("navigation", { name: "Research workspace" })
    .getByRole("button", { name: label, exact: true })
    .click();
}

test("full Practice workflow, human reviews, evidence and adversarial novelty", async ({
  page,
}) => {
  const errors: string[] = [],
    external: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) => {
    if (new URL(route.request().url()).hostname !== "127.0.0.1") {
      external.push(route.request().url());
      return route.abort();
    }
    return route.continue();
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Practice with demo" }).click();
  await expect(
    page.getByText("PRACTICE MODE — SYNTHETIC DATA", { exact: true }),
  ).toBeVisible();
  const id = new URL(page.url()).searchParams.get("run")!;
  await page.getByRole("button", { name: "Start", exact: true }).click();
  const approvals: string[] = [];
  let result: Data = {};
  for (let step = 0; step < 15; step++) {
    await expect
      .poll(
        async () => {
          result = await snapshot(page, id);
          return (
            !result.worker_active &&
            (!!result.state.pending_approval ||
              result.run.status === "COMPLETED")
          );
        },
        { timeout: 45000 },
      )
      .toBeTruthy();
    if (result.run.status === "COMPLETED") break;
    approvals.push(result.state.pending_approval);
    if (result.state.pending_approval === "after_core_selection") {
      await tab(page, "Papers");
      await page.locator("tbody tr").first().click();
      await expect(
        page.getByRole("dialog", { name: "paper detail" }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Close", exact: true }).click();
    }
    if (result.state.pending_approval === "after_gaps") {
      await tab(page, "Evidence");
      await page.locator("tbody tr").first().click();
      await expect(
        page.getByRole("dialog", { name: "evidence detail" }),
      ).toContainText("PARTIALLY_VERIFIED");
      await page.getByRole("button", { name: "Close", exact: true }).click();
    }
    if (result.state.pending_approval === "before_accepting_novelty") {
      await tab(page, "Novelty");
      await page
        .getByRole("button", { name: "Novelty battle", exact: true })
        .first()
        .click();
      await expect(
        page.getByText("REVIEWER #2", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("MAJOR_REVISION", { exact: true }),
      ).toBeVisible();
    }
    const review = page.locator(".review-banner");
    await review
      .getByRole("textbox", { name: "Reviewer name", exact: true })
      .fill("Studio E2E researcher");
    await review
      .getByRole("textbox", { name: "Comment", exact: true })
      .fill(
        "Synthetic training only; scientific verification remains blocked.",
      );
    await expect(
      review.getByRole("button", { name: "Approve", exact: true }),
    ).toBeEnabled();
    await review.getByRole("button", { name: "Approve", exact: true }).click();
    await expect
      .poll(async () => (await snapshot(page, id)).state.pending_approval)
      .toBeNull();
    await page.getByRole("button", { name: "Resume", exact: true }).click();
    if (result.state.pending_approval === "after_gaps") {
      await expect(
        page.getByRole("button", { name: "Pause", exact: true }),
      ).toBeEnabled();
      await page.getByRole("button", { name: "Pause", exact: true }).click();
      await expect
        .poll(
          async () => {
            const s = await snapshot(page, id);
            return s.run.status === "PAUSED" && !s.worker_active;
          },
          { timeout: 45000 },
        )
        .toBeTruthy();
      const paused = await snapshot(page, id);
      expect(paused.state.pending_approval).toBeNull();
      await page.getByRole("button", { name: "Resume", exact: true }).click();
    }
  }
  expect(result.run.status).toBe("COMPLETED");
  expect(
    result.models.every(
      (r: Data) => r.provider === "fake" && r.estimated_cost === 0,
    ),
  ).toBeTruthy();
  expect(result.practice_design.experiments.length).toBeGreaterThan(0);
  expect(
    result.state.evidence.every(
      (e: Data) => e.verification_status !== "VERIFIED",
    ),
  ).toBeTruthy();
  expect(result.state.experiments).toHaveLength(0);
  expect(approvals).toContain("before_final_report");
  for (const [label, name] of [
    ["Overview", "studio-practice-completed"],
    ["Workflow", "studio-workflow"],
    ["Agents", "studio-agents"],
    ["Papers", "studio-paper-library"],
    ["Evidence", "studio-evidence-explorer"],
    ["Gaps", "studio-gap-board"],
    ["Novelty", "studio-novelty-lab"],
    ["Hardware", "studio-hardware-lab"],
    ["Paper", "studio-paper-builder"],
  ]) {
    await tab(page, label);
    if (label === "Workflow")
      await expect(page.locator(".workflow-node.COMPLETED")).toHaveCount(20);
    if (label === "Agents")
      await expect(page.locator(".agent-card")).toHaveCount(20);
    if (
      label === "Novelty" &&
      (await page.getByText("NOVELTY GENERATOR", { exact: true }).isVisible())
    )
      await page
        .getByRole("button", { name: "NOVELTY LAB", exact: true })
        .click();
    if (label === "Paper")
      await expect(page.locator(".section-nav button")).toHaveCount(14);
    await shot(page, name);
  }
  await tab(page, "Novelty");
  await page
    .getByRole("button", { name: "Novelty battle", exact: true })
    .first()
    .click();
  await shot(page, "studio-novelty-battle");
  await tab(page, "Agents");
  await page.locator(".agent-card").filter({ hasText: "ReviewerTwo" }).click();
  await expect(
    page.getByRole("dialog", { name: "ReviewerTwo", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(
    "SAME_PROVIDER_FALLBACK",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await tab(page, "Experiments");
  await expect(
    page.getByText("ADVISORY / SYNTHETIC", { exact: true }),
  ).toBeVisible();
  await tab(page, "Reviews");
  await expect(
    page.getByRole("button", { name: "Save", exact: true }),
  ).toBeDisabled();
  await tab(page, "Cost");
  await expect(page.getByText("BOUNDED RUN", { exact: true })).toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "spent" }),
  ).toContainText("$0.00");
  await expect(page.getByText("model calls", { exact: true })).toBeVisible();
  await shot(page, "pilot01-cost-offline");
  const zip = await page.request.get("/api/runs/" + id + "/export");
  expect(zip.status()).toBe(200);
  expect(zip.headers()["content-type"]).toContain("application/zip");
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Dashboard", exact: true })
    .click();
  await shot(page, "studio-dashboard");
  await page
    .getByRole("button", { name: "Providers & models", exact: true })
    .click();
  await expect(
    page.getByText("BLOCKED", { exact: true }).first(),
  ).toBeVisible();
  const readiness = page.getByRole("region", { name: "Service readiness" });
  await expect(readiness.locator("tbody tr")).toHaveCount(6);
  await expect(readiness.getByText("NOT_TESTED", { exact: true })).toHaveCount(
    6,
  );
  await shot(page, "pilot01-readiness-offline");
  await shot(page, "studio-provider-settings");
  await mkdir("../../docs/audits", { recursive: true });
  await writeFile(
    "../../docs/audits/studio-practice-result.json",
    JSON.stringify(
      {
        run_id: id,
        status: result.run.status,
        approvals,
        papers: result.state.candidates.length,
        evidence: result.state.evidence.length,
        claims: result.state.claims.length,
        gaps: result.state.gaps.length,
        novelty_revisions: result.state.novelty_candidates.length,
        reviews: result.state.reviews.length,
        agent_names: [
          ...new Set(result.executions.map((r: Data) => r.agent_id)),
        ],
        advisory_design: !!result.practice_design,
        canonical_gate_failures: result.state.gates.filter(
          (g: Data) => !g.passed,
        ).length,
        model_calls: result.models.length,
        paid_model_calls: 0,
        live_research_executed: false,
        srl: result.srl,
        browser_errors: errors,
        external_requests: external,
      },
      null,
      2,
    ),
  );
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("Pilot role overrides remain editable and real preflight discloses routes before confirmation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) =>
    new URL(route.request().url()).hostname === "127.0.0.1"
      ? route.continue()
      : route.abort(),
  );
  const data = await (await page.request.get("/api/settings")).json();
  const config = data.settings;
  for (const routes of [
    ...Object.values(config.models),
    ...Object.values(config.role_routes),
  ] as Data[][])
    for (const route of routes)
      Object.assign(route, {
        enabled: true,
        model: "offline-ui-" + route.provider,
        input_cost_per_million: 1,
        output_cost_per_million: 1,
      });
  const routes = config.models.SEARCH_PLANNING;
  for (const role of [
    "PaperScout",
    "CitationScout",
    "LocalDocumentScout",
    "PriorArtHunter",
  ])
    config.role_routes[role] = [
      routes.find((r: Data) => r.provider === "openai"),
      routes.find((r: Data) => r.provider === "google"),
    ];
  config.research.novelty_review_each_revision = true;
  config.search.adapters = ["crossref", "openalex", "arxiv"];
  config.live_research_budget = {
    max_total_cost: 5,
    max_model_calls: 80,
    max_search_calls: 500,
    max_core_papers: 12,
    max_deep_reads: 10,
    max_novelty_iterations: 3,
  };
  expect(
    (await page.request.put("/api/settings", { data: config })).status(),
  ).toBe(200);
  const project = await (
    await page.request.post("/api/projects", {
      data: {
        title: "Pilot 01 preflight offline",
        topic: "Pilot 01 preflight offline",
        practice: false,
      },
    })
  ).json();
  await page.goto("/");
  await page
    .getByRole("button", { name: "Providers & models", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "PaperScout route 0", exact: true })
    .selectOption("google");
  await expect(
    page.getByRole("combobox", { name: "PaperScout route 0", exact: true }),
  ).toHaveValue("google");
  await page
    .getByRole("combobox", { name: "PaperScout route 0", exact: true })
    .selectOption("openai");
  await page.getByRole("button", { name: "Save", exact: true }).first().click();
  await expect
    .poll(
      async () =>
        (await (await page.request.get("/api/settings")).json()).settings
          .role_routes.PaperScout[0].provider,
    )
    .toBe("openai");
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Dashboard", exact: true })
    .click();
  await page
    .getByRole("button")
    .filter({ hasText: "Pilot 01 preflight offline" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configuration preflight" });
  await expect(dialog).toBeVisible();
  for (const term of [
    "anthropic_blocked_roles",
    "PaperScout",
    "PriorArtHunter",
    "role_routes",
    "max_deep_reads",
    "human_approval_required",
    "novelty_review_each_revision",
    "crossref",
    "openalex",
    "arxiv",
    "offline-ui-openai",
  ])
    await expect(dialog).toContainText(term);
  await expect(
    dialog.getByRole("button", { name: "START REAL RESEARCH", exact: true }),
  ).toBeVisible();
  await shot(page, "pilot01-preflight-offline");
  // Never confirm or start this configured real project.
  expect(
    (await (await page.request.get("/api/projects/" + project.id)).json()).runs,
  ).toHaveLength(0);
  expect(errors).toEqual([]);
});

test("Vietnamese project wizard, localization, theme and cooperative controls", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("combobox", { name: "Language" }).selectOption("vi");
  await expect(
    page.getByRole("heading", { name: "Tổng quan", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Dự án nghiên cứu mới", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Tên dự án", exact: true })
    .fill("Phân tích máy thu FHSS");
  await page
    .getByRole("textbox", { name: "Chủ đề nghiên cứu", exact: true })
    .fill("Đánh giá độ phức tạp sparse recovery trên FPGA");
  await page.getByRole("button", { name: "Tiếp theo", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp theo", exact: true }).click();
  await page
    .getByRole("combobox")
    .filter({ has: page.locator('option[value="quick"]') })
    .selectOption("quick");
  await page.getByRole("button", { name: "Tạo dự án", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Đánh giá độ phức tạp sparse recovery trên FPGA",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("combobox", { name: "Ngôn ngữ" }).selectOption("en");
  await page.getByRole("button", { name: "Switch theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  const id = new URL(page.url()).searchParams.get("run")!;
  await expect
    .poll(async () => !!(await snapshot(page, id)).state.pending_approval)
    .toBeTruthy();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect
    .poll(async () => (await snapshot(page, id)).run.status)
    .toBe("REJECTED");
  await page.reload();
  await expect(page.locator(".page-heading")).toContainText("REJECTED");
});
