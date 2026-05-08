# Signal Inspector Execution Desk Redesign

Date: 2026-05-08
Ticket: DEV-315
Status: Design approved for review

## Purpose

The Signal Inspector is an operational debugging surface for the trading bot. Its primary job is to help the user answer, quickly and confidently:

- Did this signal trigger a trade?
- If not, where did the pipeline stop?
- What exact reason should be fixed next?
- Is the setup data trustworthy enough to act on?

The current drawer feels like a beginner dashboard because it treats every section as a similar card, buries the execution outcome, and makes the AI Brain content feel like generic diagnostics. The redesign turns it into a premium execution audit console.

## Design Direction

Use an "Execution Desk" aesthetic: dense, sharp, institutional, and built for repeated operational use. The UI should feel like a professional trade operations console, not a marketing dashboard.

Key qualities:

- Compact hierarchy with strong first-screen answers.
- Dark terminal surface with restrained contrast and thin borders.
- Monospace numeric data, but not every label should feel like raw debug output.
- Fewer generic cards; more purposeful modules.
- Clear pass, fail, skipped, and no-entry states.
- No decorative hero treatment, oversized copy, or explanatory in-app tutorial text.

## Information Hierarchy

The top of the drawer must answer "what happened" before anything else.

1. Outcome
   - Prominent status rail: `OPEN`, `CLOSED`, `NO ENTRY`, `NO TRADE`, `EXEC FAIL`, or related status.
   - Side, symbol, entry, timestamp, and account context should remain visible near the outcome.

2. Reason
   - One high-signal reason line directly under the outcome.
   - Examples:
     - `Rejected: permission_file_missing: approved_candidates.json`
     - `Execution failed: broker adapter timeout`
     - `No entry: signal passed permission, broker execution not recorded`

3. Execution Path
   - A vertical or compact stepper that shows pipeline state:
     - Signal Received
     - Permission Gate
     - AI Brain
     - Risk Guard
     - Broker Execution
   - Each stage should have a state: pass, fail, skipped, pending, or unknown.
   - This path is the main differentiator: it shows where the bot stopped.

4. Trade Plan
   - Entry, SL, TP, risk, size, PnL, execution source, and mode.
   - Use tight rows and stable alignment. Long values must wrap inside the drawer.

5. AI Brain
   - AI decision summary, failing rules, RF/LLM context, zone facts, liquidity facts, and metrics.
   - Debug/raw model output stays behind an explicit secondary control.

6. Evidence
   - Zone screenshot, AI memo, debate transcript, and raw payload are secondary surfaces.
   - They should not compete with the execution outcome.

## Component Structure

Refactor `SignalInspector.tsx` into smaller local subcomponents first, then move to files only if the component remains too large.

Recommended units:

- `InspectorShell`: drawer surface, scroll area, spacing, tab container.
- `OutcomeHeader`: symbol, side, status, timestamp, account, main reason.
- `ExecutionPath`: derived pipeline stages with pass/fail/skipped state.
- `TradePlanPanel`: entry, SL, TP, risk, mode, broker source, PnL.
- `AiDecisionPanel`: decision summary, failing gates, RF and LLM context.
- `SetupFactsPanel`: zone, liquidity, setup score, legacy metrics.
- `EvidenceTabs`: AI memo and raw data sections.

Each unit should accept already-derived display data where practical. Keep parsing and status derivation in pure helper functions near the component.

## Data Derivation

Add helper functions for view-model style display data:

- `deriveOutcome(signal, ai)`:
  - Maps raw statuses into clear operational labels.
  - Distinguishes permission allowed from actual execution.
  - Produces tone, label, and reason.

- `deriveExecutionStages(signal, ai, aiRun)`:
  - Builds the pipeline stepper.
  - Uses signal status, filter reason, AI decision, execution source, and broker-related fields.
  - Handles unknowns explicitly rather than pretending pass/fail certainty.

- `deriveTradePlan(signal)`:
  - Formats entry, SL, TP, risk, position size, mode, action, and broker source.

These helpers should be deterministic and easy to test.

## Visual Treatment

Use the existing TradeOps dark design system and avoid introducing a new visual language that clashes with the app.

Specific choices:

- Drawer width can remain close to current width, but content must be designed for it.
- Replace stacks of equal cards with a stronger top command block plus slimmer modules.
- Use left accent rails for outcome tone:
  - Green: executed/open/approved.
  - Red: rejected/failed/no trade.
  - Amber: no entry, pending, skipped, incomplete.
  - Muted: closed/historical/unknown.
- Use compact status chips, never long raw enum badges as primary labels.
- Use `overflow-wrap:anywhere`, `min-w-0`, and single-column layouts inside the drawer.
- Use lucide icons only when they clarify state, not as decoration.
- Keep cards at 8px radius or less.
- Avoid nested card-on-card structure.

## Interaction

- Default tab should remain `Overview`, but Overview must become the execution summary, not a loose collection of cards.
- AI Brain should remain available as a tab, but the most important AI rejection reason should appear in the header and execution path.
- Raw Data remains a tab for deep debugging.
- Debug output remains hidden behind a `Show Debug` control.
- No new backend calls are required.

## Accessibility

- Preserve the sheet description and dialog semantics.
- Ensure status colors are paired with text labels.
- Keep buttons keyboard reachable.
- Maintain readable contrast for muted text on dark surfaces.
- Do not rely on hover-only information for critical reasons.

## Testing

Add or update tests in `frontend/src/components/SignalInspector.test.tsx` for:

- Permission rejection shows a clear outcome and reason.
- Permission allowed without broker execution does not imply an opened trade.
- Execution path renders the expected stopped stage.
- Long enum/reason values remain present in text and are not replaced by misleading labels.
- Existing AI memo and raw data behavior remains intact.

Run:

- `npx vitest run src/components/SignalInspector.test.tsx`
- `npm run build`

## Scope Boundaries

In scope:

- Refactor and redesign the Signal Inspector frontend.
- Add pure helpers and focused component splits.
- Update tests for the new semantics and layout.

Out of scope:

- Backend status model changes.
- Trading logic changes.
- Broker execution behavior.
- New API calls.
- Global dashboard redesign outside the inspector.

## Approval Notes

The user approved the "Execution Desk" direction in text-only brainstorming. The implementation should optimize for fast operational diagnosis over visual drama.
