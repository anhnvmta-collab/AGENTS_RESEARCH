# CS_FHSS_DOA_FPGA

This is a coverage and research-quality benchmark, not a literature review result.
RQ1-RQ10, fourteen perspectives and complementary query families are explicit inputs.
Expected families/concepts are probes; absent terms do not prove absent methods.
Seed references must have primary-source provenance and are deliberately nonexhaustive.
Paid live execution requires both --live and --confirm-paid-apis. Preparation does not use keys.

## Curated references (checked 2026-10-21)

- [Needell and Tropp, CoSaMP preprint](https://arxiv.org/abs/0803.2392): source identity and a short algorithm-operation excerpt.
- [Mishali and Eldar, sub-Nyquist sampling preprint](https://arxiv.org/abs/0902.4291): primary metadata, related journal DOI and a short limitation of a compared method. Preprint and journal years differ explicitly.
- [Nguyen et al., ETRI Journal](https://onlinelibrary.wiley.com/doi/full/10.4218/etrij.2019-0067): publisher identity and a short source-reported synthesis comparison. Online-first 2019 and citation/issue 2020 are recorded separately in notes.

These seeds cover selected foundational/implementation concepts. They are not an exhaustive FHSS,
UAV or DOA literature set. A known-answer fake-output test verifies extraction/grounding contracts;
it does not measure a real model's recall or entailment. Citation-chain recovery remains null until
independently verified expected directed DOI edges are added to expected_citation_edges.

Run `research-council validate-science --workspace workspace` for preparation only. Review the
23-section LIVE_SCIENTIFIC_VALIDATION.md and eight human_review files. Use config/phase11.live.example.yaml
as the live configuration starting point. Only the explicitly confirmed command can execute real
services. Search/model/deep-read budgets include failed attempts; source service fees are not
included in model token-cost estimates. Labels such as FPGA/RFSoC and 500-1000 hops/s remain inputs.
