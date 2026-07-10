# Plan: Match RD Forex 5-Minute Zone Detection
_Locked via grill — by Claude + user_

## Goal
Make `SND_Raw_RD_Forex_LAB.pine` reproduce the protected RD Forex reference indicator's five-minute supply-and-demand zones without missed zones, extra zones, boundary mismatches, or repainting. The eventual goal is fully automated trading, but live execution remains blocked until zone detection passes a fixed multi-instrument validation set and a paper-trading period.

## Approach
1. Treat `SND_Raw_RD_Forex_LAB.pine` as the development source. Preserve `SND_Raw_RD_Forex.pine` as the baseline and promote verified logic to `SND_Raw_RD_Forex_PROD.pine` only after validation.
2. Encode the video rules explicitly for normal and accuracy zones. Normal zones use the full origin candle; accuracy bounds use the body/conditional wick rule from the video, including the candle-to-candle wick comparison that selects the accuracy boundary. Keep origin-candle selection and zone geometry deterministic and testable, including strict versus equal boundary comparisons.
3. Separate the lifecycle into three states: candidate detected, zone validated, and trade-eligible. Candidates remain visible in LAB with a reason and state even when later filters reject them.
4. Stop using the current fixed ATR/body thresholds as hard zone-detection rejection gates. Retain displacement measurements for diagnostics and scoring. Define the replacement predicate exactly: a standard demand/supply confirmation requires a directional closed candle or directional closed leg to close strictly beyond the corresponding full origin boundary; an accuracy confirmation must close strictly beyond the selected accuracy boundary. Wick-only breaks, dojis, equal highs/lows, and gaps are recorded as candidate diagnostics but do not become official confirmations without a qualifying close.
5. Implement the video lifecycle rules: the zone must remain untapped, associated liquidity must take its own high or low before trade eligibility, departure-move wicks do not count as a return tap, and any later candle wick entering the zone invalidates the untapped state. Make liquidity selection deterministic: demand uses the side-mirrored inducement-low then target-high sequence, supply uses inducement-high then target-low; cluster equal levels within the configured tick tolerance; search no farther than the configured liquidity window; prefer the closest qualifying candidate, then earliest pivot, then smallest price distance as tie-breakers; never select a future bar or an already-consumed level.
6. Make official zone creation and alerts closed-bar only. Track `origin_bar/time`, `detection_bar/time`, and `confirmation_bar/time` separately; emit `ZONE_CONFIRMED_NON_EXECUTABLE` at the confirmation-bar close, while the box may be visually anchored at the origin. Historical backfill must not pretend that a zone was created on the current bar. LAB may show candidates and lifecycle diagnostics, but only `TRADE_ELIGIBLE_EXECUTABLE` can be sent as an executable PROD event. Candidate, confirmation, liquidity, rejected, duplicate, touched, invalidated, and historical-state events must never reach the executable webhook.
7. Validate first on the same feed used for alerts and execution, then across the supplied examples: USDJPY, GBPJPY, GBPCAD, EURUSD, GBPUSD, NZDJPY, NAS100, XAUUSD, and XPTUSD, all on five-minute charts.
8. Build a versioned comparison set of at least 100 labeled reference zones from Bar Replay screenshots, with at least 10 core zones per instrument represented and both normal and accuracy models represented where the reference shows them. Continuation models are a later phase after the core detector gate. For each zone record symbol/feed, timeframe, origin candle, model/type, detection and confirmation times, boundaries, liquidity ownership/sequence, tap/invalidation state, and screenshot evidence. Use a JSON or CSV fixture plus a deterministic mismatch report. A second pass must adjudicate every label; exclusions are capped at 5%, categorized, justified, and cannot remove an entire instrument or model. After adjudication, require zero unresolved missed/extra zones, boundary differences greater than one minimum tick, or creation-time mismatches; any one-tick discrepancy must be explicitly reviewed rather than silently accepted.
9. Add a deterministic collection path for validation output: each LAB run receives a `run_id`, emits structured events to a dedicated non-execution debug endpoint or exported alert log, and retains the JSONL/CSV output with the fixture and replay metadata. The comparator consumes the fixture and actual-event file and produces a mismatch report listing missing, extra, boundary, timestamp, lifecycle, and repaint discrepancies. Chart-local labels are supplemental evidence, not the audit record.
10. Run at least two weeks of paper or alert-only validation with complete non-executable event logging before promoting LAB to PROD or enabling live orders. The debug event schema must include `run_id`, symbol/feed/timeframe, zone ID/model/side, origin/detection/confirmation timestamps, top/bottom, lifecycle state, rejection reason, liquidity fields, and tap/invalidation fields. Debug events use the dedicated non-execution channel and never enqueue Redis.
11. Phase 0, before any executable alert work, owns the backend safety boundary: add or verify a non-execution debug schema and a fail-closed execution gate that rejects this strategy/version unless the explicit paper/live validation flag is enabled. Executable payloads must include the backend-required strategy, side, entry, stop, target, size, and run-mode fields; lifecycle/debug payloads are invalid for execution. No executable RD alert is enabled until Phase 0 is complete.
12. Bound Pine runtime resources. Candidate/rejected debug labels and objects must use deterministic caps below the TradingView limits, prune oldest or lowest-priority diagnostics on overflow, and never cause object-limit/runtime failures in the full validation runs. The validation report must include the peak zone, box, line, and label counts.

## Key decisions & tradeoffs
- The protected reference indicator is the behavioral oracle; visual/time-stamped examples are the comparison data because its internal code is unavailable.
- Accuracy is defined as zero mismatches on the approved labeled set, not as a subjective visual similarity.
- Candidate detection is intentionally broader than trade eligibility so debugging can expose false negatives without weakening execution safety.
- The video rules take precedence over arbitrary thresholds currently present in the LAB implementation; numeric displacement values become diagnostics unless the labeled data proves they are required.
- The official confirmation predicate is close-based and deterministic. Wick-only, doji, equal-boundary, and gap cases remain visible as diagnostic candidates but cannot silently become trade-ready.
- Accuracy bounds must be validated for metals and indices as well as forex; the current symbol-based suppression cannot remain unexplained. Either remove it or document a video-backed exception with labeled cases.
- Visual/debug lifecycle events are separate from executable alerts. Event names are explicit: `ZONE_CANDIDATE`, `ZONE_CONFIRMED_NON_EXECUTABLE`, `LIQUIDITY_LINKED`, `ZONE_TOUCHED`, `ZONE_INVALIDATED`, and `TRADE_ELIGIBLE_EXECUTABLE`. Only the last event is allowed through the executable path.
- Liquidity ownership, equal-level clustering, search window, inducement/target sequence, and tie-breaks are deterministic and side-mirrored; no visual judgment is used at runtime.
- The dedicated non-execution debug transport and backend fail-closed gate are Phase 0 deliverables. No alert contract is considered complete until the receiver cannot enqueue a lifecycle event.
- A promotion from LAB to PROD requires a reviewed diff and a recorded checklist; the three files may not drift silently. Intentional production-only differences must be listed.
- Development is staged through LAB, then PROD, then paper trading, then live execution. The retired `SND_Strategy.pine` is out of the implementation path.
- Validation must use the production data feed for each instrument because feed-specific highs, lows, and spreads can change liquidity and zone results.

## Risks / open questions
- Protected-reference behavior cannot be compared programmatically; screenshots and manual labels must be maintained carefully.
- The video contains visual rules whose exact candle relationships may need to be resolved from additional labeled examples.
- Different feeds can produce legitimate candle-level differences, so a zone mismatch may be data-related rather than algorithmic.
- The current three raw indicator files already differ; their shared logic and intentional differences must be compared before promotion.
- Fully automated order routing, sizing, exits, and broker execution remain to be specified after detection is proven.
- The exact implementation of the dedicated non-execution debug endpoint or alert-log collector remains an engineering choice, but one must be selected and owned in Phase 0; chart-local labels alone are insufficient.

## Out of scope
- Editing or relying on the retired `scripts/pinescript/strategies/SND_Strategy.pine`.
- Enabling live orders during zone-detector development.
- Treating candidate or rejected zones as live signals.
- Sending lifecycle/debug alerts to the executable `/webhook` endpoint.
- Replacing the protected reference indicator or attempting to recover its source.
- Changing broker execution, risk sizing, or production alert contracts before the zone-detection gate passes; the fail-closed validation gate is a prerequisite, not live trading behavior.
