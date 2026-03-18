# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | M001 | arch | Prop firm rules data source | Curated database in Supabase — not web scraping or API integration | No prop firm exposes public APIs. Scraping is fragile. Curated DB with versioning and staleness warnings is the reliable approach — same strategy used by every tool in the space. | Yes — if a major firm launches a public API |
| D002 | M001 | arch | Per-account enforcement model | prop_guard accepts per-account params, not global settings | Multiple accounts with different firms need different kill thresholds simultaneously. Global settings model can't support this. | No |
| D003 | M001 | scope | MyFundedFX removal | Remove all MyFundedFX references — firm shut down Feb 2026 | Stale presets for a dead firm erodes trust. Confirmed shutdown via multiple sources. | No |
| D004 | M001 | arch | Phase advancement trigger | Auto-advance when profit target reached + all conditions met (min days, consistency, no breaches) | Manual phase switching is error-prone and can leave stale limits active. User confirmed preference for auto-advance. | Yes — if user wants manual confirmation later |
| D005 | M001 | arch | Dashboard consolidation | Merge /prop-firm page into account detail ChallengeTab | User wants accounts page as single hub. Current split causes duplicated logic and inconsistent account selection. | No |
