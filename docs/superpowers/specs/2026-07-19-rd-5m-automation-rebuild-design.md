# Evidence-Driven RD 5-Minute Automation Rebuild

Date: 2026-07-19
Status: Approved for planning
Tracking: Jira creation attempted on 2026-07-19 but Atlassian returned `404 Site temporarily unavailable`; work remains associated with the current `DEV-845` branch until tracking is restored.

## Purpose

Build a new, professional implementation of the five-minute Liquidity Supply and Demand strategy that detects every zone the user would approve manually, behaves consistently in historical replay and live markets, and can later drive automated trade execution without repainting or hidden delay.

The rebuild starts from strategy evidence and a new detector. Existing Pine implementations remain available as comparison material, but their code and assumptions are not the foundation of the new detector.

## Definition of Accuracy

"100% accurate" means all of the following:

- The detector agrees with every manually approved case in the versioned benchmark.
- It produces no missing or extra zones in that benchmark.
- Direction, formation model, origin bar, confirmation bar, and lifecycle result match the approved label.
- Zone boundaries match within one `syminfo.mintick`.
- Historical replay and live closed-bar processing produce the same events.
- A confirmed zone never moves, changes bounds, or appears earlier after a reload.
- Every rejection and invalidation has one deterministic reason code.

It does not mean every valid setup wins or that future market outcomes can be predicted with certainty.

## Scope

The first release target covers raw five-minute zone detection and lifecycle. It is delivered through separate detector and lifecycle phases:

- Demand and supply.
- Reversal and continuation formations.
- Standard and accuracy geometry.
- Formation-candle envelopes.
- Confirmation, freshness, taps, and invalidation.
- Debug evidence and parity reporting.

The initial benchmark markets are:

- `USDJPY`
- `GBPJPY`
- `GBPCAD`
- `EURUSD`
- `GBPUSD`
- `NZDJPY`
- `NAS100`
- `XAUUSD`
- `XPTUSD`

Liquidity, entries, exits, risk, alerts, backend execution, and MetaTrader integration follow as separately validated phases.

## Superseded Approach

This design supersedes the zone-detection and implementation direction in `docs/superpowers/specs/2026-05-13-youtube-snd-zone-refactor-design.md` for the new five-minute version.

That earlier design remains useful historical context, but it:

- Used five selected videos rather than a complete source inventory.
- Modified the existing strategy and `Core.Zone` model instead of starting with an isolated detector.
- Left displacement, expiry, distance, and confirmation behavior configurable before evidence was complete.
- Did not define a machine-readable, manually approved ground-truth corpus.

No existing live strategy or execution path is replaced until the new version passes its release gates.

## Source Corpus

The approved channels contain 392 videos as of 2026-07-19:

| Channel | Videos | Primary use |
|---|---:|---|
| RD Forex | 55 | Canonical RD rules and current five-minute model |
| Arger FX | 33 | Mechanical explanations and ambiguity resolution |
| Mangoe | 123 | Zone, entry, market, and worked-example coverage |
| RT Futures | 21 | Five-minute futures examples and cross-market behavior |
| CharneyFX | 79 | Rejected setups, filters, losses, and skipped trades |
| Trirex | 81 | Automation behavior, operational lessons, and performance evidence |

Videos are classified before extraction:

- `RULE_SOURCE`: courses, mechanical guides, zone construction, liquidity, entries, and explicit checklists.
- `EDGE_EVIDENCE`: live breakdowns, skipped trades, losses, backtests, and market-specific examples.
- `OPERATIONS_EVIDENCE`: automation, latency, drawdown, and bot behavior.
- `NON_RULE`: mindset, lifestyle, promotion, or performance claims without strategy mechanics.

Only the first three classes may affect the design. Performance claims never establish a detection rule by themselves.

## Rule Authority

When evidence conflicts, use this order:

1. A direct manual ruling from the user.
2. The latest applicable RD Forex five-minute rule.
3. Corroborating Arger FX, Mangoe, or RT Futures explanations.
4. CharneyFX filtering and skipped-trade evidence.
5. Trirex automation behavior and performance evidence.
6. The protected indicator output as comparison evidence.

Within one source, a newer explicit rule supersedes an older rule for the same model and timeframe. A rule for another timeframe or strategy variant cannot silently override a five-minute rule.

If precedence does not resolve a material conflict, the setup remains `UNRESOLVED` and is not executable. The conflict is placed in a small manual review queue rather than guessed.

## Evidence Records

Each extracted rule is stored as a structured record with:

- Stable `rule_id`.
- Normalized concept and model.
- Testable statement in original words only when a short excerpt is essential; otherwise a paraphrase.
- Preconditions and expected outcome.
- Market and timeframe scope.
- Source channel, video ID, URL, timestamp, and publication date.
- Relevant chart-frame timestamp or local evidence reference.
- Confidence and status: `CONFIRMED`, `CORROBORATED`, `CONFLICTING`, `UNVERIFIED`, or `SUPERSEDED`.
- IDs of rules it supports, conflicts with, or supersedes.
- IDs of benchmark cases that prove the rule.

Full third-party transcripts and videos are temporary research inputs and are not committed. The repository keeps derived rule records, timestamps, source URLs, hashes, and user-owned or structured test fixtures.

## Ground-Truth Cases

Every benchmark case records:

- `case_id`, symbol, feed, timeframe, and time range.
- OHLC data needed to reproduce the decision.
- Expected zones with direction, model, origin time, confirmation time, top, bottom, and lifecycle status.
- Expected rejected candidates and their reason codes when relevant.
- Protected-indicator observation, if available.
- Manual decision and notes.
- Supporting rule IDs and evidence timestamps.
- Label status: `PROVISIONAL` or `APPROVED`.

Only `APPROVED` cases are release gates. A newly discovered mismatch must first become a fixture, then receive a rule-level fix. Symbol-specific patches without a general approved rule are prohibited.

## New Detector Architecture

Development begins with one canonical Pine indicator:

`scripts/pinescript/indicators/SND_RD_5M_V1_LAB.pine`

The LAB indicator owns raw detection, deterministic lifecycle transitions, debug rendering, and versioned diagnostic events. It contains no `strategy.*` calls and cannot open a trade.

There is no separately maintained PROD or strategy copy during detector development. Once raw detection graduates, stable pure logic may be extracted into a new versioned Pine library shared by thin indicator and strategy wrappers. A release artifact must be generated or imported from the same canonical logic; manual copy drift is not allowed.

Existing files are legacy comparison sources only:

- `SND_Core.pine`
- `SND_Utils.pine`
- `SND_Strategy.pine`
- `SND_Raw_RD_Forex.pine`
- `SND_Raw_RD_Forex_LAB.pine`
- `SND_Raw_RD_Forex_PROD.pine`

## Zone Model

Formation direction and geometry are independent dimensions.

Direction:

- `DEMAND`
- `SUPPLY`

Formation:

- `REVERSAL`: drop-base-rally for demand or rally-base-drop for supply.
- `CONTINUATION`: rally-base-rally for demand or drop-base-drop for supply.

Geometry:

- `STANDARD`: begins with the complete origin-candle range.
- `ACCURACY`: begins with the origin-candle body. For demand, the bearish origin high must be greater than the first bullish departure high. For supply, the bullish origin low must be less than the first bearish departure low.

The model name is composed from these dimensions, so continuation zones cannot be accidentally disabled by geometry logic.

Each distinct formation event remains independently addressable. Spatial overlap, containment, or matching prices do not make two zones duplicates. Deduplication requires the same direction, origin time, geometry model, and confirmation event.

## Formation Envelope

The origin candle is not always the complete final range.

For demand:

- Begin with the approved standard or accuracy origin bounds.
- While the departure is still forming, consecutive bullish formation candles may extend only the distal boundary downward with their lows.
- The proximal boundary remains derived from the origin geometry.

For supply:

- Begin with the approved standard or accuracy origin bounds.
- While the departure is still forming, consecutive bearish formation candles may extend only the distal boundary upward with their highs.
- The proximal boundary remains derived from the origin geometry.

These same-direction wicks are part of formation and do not count as taps. Boundaries freeze on confirmation. Any later overlap is a lifecycle event and can never resize the zone.

The USDJPY example supplied on 2026-07-19 is the first positive fixture for this rule: the bullish departure wick extends below the bearish demand origin candle.

The exact end of the formation window is evidence-driven. The initial contract uses the first confirmed departure; it must not scan arbitrary later candles or expand after an opposite-direction interruption.

## Detection State Machine

```text
CANDIDATE
  -> FORMING
  -> CONFIRMED_FRESH
  -> TAPPED
  -> INACTIVE

CANDIDATE | FORMING
  -> REJECTED

CONFIRMED_FRESH
  -> INVALIDATED
  -> EXPIRED (only if an approved expiry rule exists)
```

State meanings:

- `CANDIDATE`: a possible opposite-color base exists.
- `FORMING`: same-direction departure candles are being evaluated and may extend the distal boundary.
- `CONFIRMED_FRESH`: required closed-bar departure evidence exists and no disallowed return occurred.
- `TAPPED`: a post-confirmation candle first overlaps the zone.
- `INACTIVE`: a later phase has consumed the zone; exact use is introduced with liquidity and entries.
- `REJECTED`: formation never met an approved rule.
- `INVALIDATED`: confirmed geometry was broken under an approved lifecycle rule.
- `EXPIRED`: optional time-based end state, disabled until supported by rule evidence.

Each transition stores the deciding bar and exactly one reason code.

### Non-Executable Setup Handoff

Liquidity eligibility and raw-zone lifecycle feed a separate setup state machine:

```text
WAITING_FOR_ELIGIBILITY
  -> ARMED
  -> TRIGGERED

WAITING_FOR_ELIGIBILITY | ARMED
  -> REJECTED

ARMED
  -> WAITING_FOR_ELIGIBILITY (when a closer primary liquidity swing is unswept)
```

- `ARMED` means qualifying liquidity took its own extreme while the target was still fresh.
- `TRIGGERED` means the first later closed five-minute bar tapped the armed target without invalidating it.
- `REJECTED` covers a target tap before eligibility, target invalidation on return, an expired route, or unresolved same-bar route ordering.
- This state is diagnostic only. It neither chooses an entry model nor emits an executable order.
- A liquidity sweep and target tap on the same five-minute bar fails closed because OHLC cannot prove event order. A simultaneous target and intervening opposite-zone tap also fails closed.
- Setup state never controls raw-zone visibility.

## Determinism and Latency

- The production decision clock is the closed five-minute bar unless a later phase explicitly implements an approved intrabar flip-entry model.
- Historical loops may identify an origin bar, but the emitted `confirmation_time` must be the first bar when all required evidence was actually knowable.
- Future bars cannot influence candidate selection, geometry, confirmation, deduplication, or lifecycle.
- Reloading the chart must reproduce the same ordered event stream.
- The detector reports decision latency as the difference between confirmation close time and event emission time when the platform exposes it.
- "No delay" means no avoidable processing or transport delay after evidence exists; it does not permit acting before an approved close-based rule is knowable.

## Reason Codes

Reason codes are stable contracts, not debug prose. Initial families include:

- `REJECT_BASE_DIRECTION`
- `REJECT_NO_APPROVED_DEPARTURE`
- `REJECT_FORMATION_INTERRUPTED`
- `REJECT_CLOSE_INSIDE`
- `REJECT_PRECONFIRM_RETURN`
- `REJECT_DUPLICATE_EVENT`
- `REJECT_UNRESOLVED_RULE`
- `CONFIRM_STANDARD_REVERSAL`
- `CONFIRM_STANDARD_CONTINUATION`
- `CONFIRM_ACCURACY_REVERSAL`
- `CONFIRM_ACCURACY_CONTINUATION`
- `EXTEND_DEMAND_FORMATION_LOW`
- `EXTEND_SUPPLY_FORMATION_HIGH`
- `INVALIDATE_DISTAL_BREAK`
- `INVALIDATE_POST_CONFIRM_RULE`

New reason codes require a rule ID and at least one positive or negative fixture.

## Visual Behavior

Clean mode shows only approved zone states and uses stable colors for demand, supply, and optional accuracy distinction.

Debug mode can show:

- Candidate origin and confirmation bars.
- Initial and final formation bounds.
- Formation-envelope extensions.
- State and reason code.
- First invalidating bar.
- IDs needed to match exported events to fixtures.

Debug objects are bounded and pruned independently of trading state. Removing a drawing cannot remove or reactivate a zone.

## Validation

Validation has five layers:

1. **Static Pine contract tests**
   - No future references or negative-step loops.
   - Bounded arrays, scans, boxes, lines, and labels.
   - Required event fields and reason codes exist.

2. **Structured fixture comparison**
   - Compare direction, formation, geometry, origin, confirmation, bounds, and lifecycle.
   - Report missing, extra, boundary, timing, and state mismatches separately.

3. **TradingView replay parity**
   - Replay each approved case bar by bar.
   - Reload and verify the identical event stream.
   - Confirm no zone appears earlier or changes retrospectively.

4. **Cross-market benchmark**
   - Exercise all nine initial markets.
   - Include reversal, continuation, standard, accuracy, formation-wick, rejection, and invalidation examples for both directions.

5. **Out-of-sample audit**
   - Select sessions not used during implementation.
   - Compare protected output and manual interpretation.
   - Convert every accepted mismatch into a new approved fixture before release.

## Failure Policy

- Unknown or conflicting logic fails closed.
- Missing market data produces no zone and a diagnostic event.
- Unsupported timeframe produces a visible status and no actionable event.
- Invalid price bounds or impossible timestamps reject the candidate.
- Object-limit pressure reduces debug rendering, never detection state.
- Backend or webhook failure cannot change Pine detection results.
- No alert from LAB is executable.
- Later production alerts require explicit strategy identity, version, event ID, and idempotency key.

## Delivery Phases

### Phase 0: Evidence and rule catalog

- Classify the 392-video inventory.
- Extract every rule-bearing five-minute source and relevant worked example.
- Build the versioned rule graph and conflict report.
- Establish initial approved zone fixtures.

### Phase 1: Raw zone detector

- Implement the new LAB indicator.
- Cover reversal, continuation, standard, accuracy, and formation-envelope behavior.
- Reach exact parity on approved raw-zone fixtures.

### Phase 2: Zone lifecycle

- Add freshness, pre-confirm returns, post-confirm taps, invalidation, and evidence-backed expiry.
- Verify historical/live event parity.

### Phase 3: Liquidity

- Add liquidity construction, minimum candle rules, one-candle exceptions, own-high/own-low proof, sweep ordering, and target logic.
- Maintain separate fixtures and reason codes from raw zone detection.

### Phase 4: Entries and exits

- Add standard close entries, higher-timeframe flip entries, restricted entry times, stop placement, target tables, and optional break-even behavior.
- Keep entry decisions non-executable in LAB.

### Phase 5: Strategy and paper execution

- Share the graduated detector through one canonical logic source.
- Backtest approved cases and broader historical periods.
- Connect versioned alerts to the existing backend in paper mode.
- Measure signal latency, duplicates, missed alerts, slippage, and broker mapping.

### Phase 6: Controlled production

- Enable one explicitly approved strategy version and account profile.
- Require risk limits, daily trade limits, idempotency, monitoring, and a kill switch.
- Roll out by market class only after its benchmark and paper gates pass.

## Release Gates

The zone-detection and lifecycle release is done only when:

- Every rule has evidence, scope, status, and test mapping.
- Every executable rule has at least one positive and one negative approved fixture.
- No material zone-detection conflict remains unresolved.
- Every approved benchmark case passes with zero missing or extra zones.
- Boundaries are within one tick and origin/confirmation bars match exactly.
- Historical reload and live replay event streams are identical.
- All nine initial markets have both demand and supply coverage.
- Reversal, continuation, standard, accuracy, and formation-wick cases are covered.
- TradingView compiles without runtime or object-limit failures.
- Focused repository tests pass and no unrelated files are changed.

Full automation is done only when:

- Each later phase passes its own equivalent fixture and replay gates.
- Paper execution demonstrates no contract, duplication, routing, or latency defects over an agreed observation window.
- Risk controls and kill-switch behavior are tested.
- Production remains disabled until the user explicitly approves activation.

## Autonomous Work Policy

The agent owns source inventory, transcript and frame analysis, rule extraction, fixture creation, implementation, debugging, tests, documentation, and integration.

The user is contacted only when:

- Two authoritative sources remain materially contradictory after applying precedence.
- Required TradingView or broker access cannot be completed locally.
- A decision would enable live trading or materially change financial risk.

All other uncertainty is resolved conservatively, recorded in the rule catalog, and kept non-executable until proven.

## Non-Goals

- Guaranteeing profitable outcomes or a 100% win rate.
- Cloning inaccessible source code from the protected indicator.
- Treating protected visuals as infallible ground truth.
- Tuning per symbol without a general evidence-backed rule.
- Reusing the existing monolithic strategy merely to reduce implementation effort.
- Enabling live execution during detector research or LAB validation.
