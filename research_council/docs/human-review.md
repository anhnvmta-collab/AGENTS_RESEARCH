# Human scientific review

Workflow approval grants permission to continue. Scientific attestation records a person's
explicit review of a particular claim and its source evidence. They are separate actions.

Enable human approval in the run configuration. At the `before_final_report` pause, inspect
the claim register, original publications, evidence locations, identity and retraction status.
If review supports a claim, create a JSON file inside that run's workspace:

```json
{
  "claim_id": "REPLACE_WITH_ACTUAL_CLAIM_UUID",
  "reviewer": "Reviewer's name",
  "note": "Explain the source and scientific entailment checks performed.",
  "source_identity_checked": true,
  "source_locations_checked": true,
  "scientific_entailment_checked": true,
  "retraction_status_checked": true
}
```

```powershell
research-council attest-claim RUN_ID --attestation review.json --workspace workspace
research-council approve RUN_ID --workspace workspace
research-council continue RUN_ID --workspace workspace
```

Attestation validates source grounding and refuses fixtures, missing sources, hypotheses,
retracted papers and unresolved contradictions. It persists the named human review, promotes
only the selected claim and its evidence, and recomputes publication readiness. Every primary
claim and each source paper needs claim-specific review. General paper-level verification
cannot authorize unrelated claims. Novelty runs still require Gate 2.

This is a local trusted-user interface, not an authenticated multi-user review service. It
records the reviewer's attestation; it cannot establish that a person actually read a source.

## Evidence conflict review

While a run is paused, inspect both supporting and contradicting quotations. Create a
workspace-relative `resolution.json` containing:

```json
{
  "conflict_id": "REPLACE_WITH_CONFLICT_UUID",
  "reviewer": "Reviewer's name",
  "note": "Explain the opposing evidence, scope and documented resolution.",
  "resolution_status": "RESOLVED"
}
```

Run `research-council resolve-conflict RUN_ID --resolution resolution.json` with the same
workspace. `UNRESOLVED` can also be recorded. This action keeps all evidence, resets the
claim to UNVERIFIED and never supplies scientific entailment. A separate attestation is
required at the final pause. Contradicted source identity/location/retraction audits cannot
be cleared through this evidence-only resolution mechanism.
