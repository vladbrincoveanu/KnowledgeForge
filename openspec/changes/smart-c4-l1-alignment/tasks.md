## 1. Backend canonical model and sources

- [ ] 1.1 Add canonical schema module with field mapping, mandatory flags, and confidence thresholds.
- [ ] 1.2 Implement optional `service-universe.yaml` detector for canonical fields.
- [ ] 1.3 Refactor `ContextManager` to construct canonical properties first, then map/add legacy aliases.
- [ ] 1.4 Add deterministic `human_review` calculation from confidence and mandatory-field checks.

## 2. Facts persistence and feedback integration

- [ ] 2.1 Implement `facts_store` for per-repo `facts.yml` load/save/merge.
- [ ] 2.2 Extend context feedback endpoint payload model with business process/compliance confirmation fields.
- [ ] 2.3 Persist accepted feedback to facts and mark canonical fields as human-confirmed.
- [ ] 2.4 Merge facts data during extraction and enforce post-confirmation confidence floor.

## 3. Derived metrics and relationship behavior

- [ ] 3.1 Add contributor spread and risk indicator derivation in metadata/context assembly.
- [ ] 3.2 Add external-system collapse behavior (max 8, plus `Other Systems`) for context output.
- [ ] 3.3 Improve context relationship labels with deterministic business-friendly defaults.

## 4. UI review and detail surfaces

- [ ] 4.1 Update context review trigger to use backend `human_review` with legacy fallback.
- [ ] 4.2 Extend `ContextReviewDialog` and API client typing for new feedback fields.
- [ ] 4.3 Update `NodeDetailsPanel` to render canonical confidence/source and risk indicator metadata.

## 5. Tests and validation

- [ ] 5.1 Add backend tests for canonical mapping, confidence gating, optional YAML source, and facts persistence.
- [ ] 5.2 Add endpoint tests for extended feedback payload and additive response fields.
- [ ] 5.3 Add UI tests for backend-driven review trigger and expanded payload submission.
- [ ] 5.4 Run `openspec validate --type change smart-c4-l1-alignment --strict` and fix any validation errors.
