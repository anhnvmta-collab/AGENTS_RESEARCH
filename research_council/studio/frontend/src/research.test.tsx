import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RecordInspector } from "./ResearchData";
import { LocaleContext, vi } from "./i18n";

describe("scientific presentation safety", () => {
  it("escapes untrusted source text while preserving clickable evidence trails", () => {
    const state = {
      candidates: [
        {
          paper: {
            paper_id: "p1",
            metadata: {
              title: "<script>alert(1)</script>",
              authors: ["Source author"],
              year: 2024,
            },
            provenance: "fixture",
            source_kind: "fixture",
            source_text: "<img src=x onerror=alert(1)>",
            page_texts: {},
          },
        },
      ],
      evidence: [
        {
          evidence_id: "e1",
          paper_id: "p1",
          verification_status: "UNVERIFIED",
          source_location: "synthetic source",
          confidence: 0,
          verbatim_excerpt: "<img src=x onerror=alert(1)>",
          normalized_statement: "Untrusted source",
        },
      ],
      claims: [{ claim_id: "c1", evidence_ids: ["e1"] }],
      gaps: [{ gap_id: "g1", evidence_ids: ["e1"] }],
      novelty_candidates: [
        { candidate_id: "n1", gap_ids: ["g1"], revision: 1 },
      ],
    };
    const html = renderToStaticMarkup(
      <LocaleContext.Provider value={{ lang: "vi", t: (key) => vi[key] }}>
        <RecordInspector
          state={state}
          selected={{ kind: "evidence", id: "e1" }}
          select={() => {}}
        />
      </LocaleContext.Provider>,
    );
    expect(html).toContain("UNVERIFIED");
    expect(html).toContain("&lt;img");
    expect(html).not.toContain("<img src=x");
    expect(html).toContain("Chuỗi bằng chứng");
    for (const id of ["p1", "e1", "c1", "g1", "n1"]) expect(html).toContain(id);
  });
});
