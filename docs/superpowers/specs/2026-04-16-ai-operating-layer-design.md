# DEV-120 AI Operating Layer Design

## Summary

Design an AI Operating Layer that upgrades the current trading system with chart-aware analysis, Pine understanding, debate orchestration, memory and learning, and operator copilot workflows, while preserving the existing trading core as the trusted baseline. The new layer must be independently toggleable, degrade gracefully, and be globally disableable from the UI through panic mode.

## Goals

- Add chart awareness so AI can reason about setups instead of only numbers.
- Reuse and strengthen existing shadow debate agents with better inputs and outputs.
- Support post-trade review and pre-trade shadow analysis.
- Support multiple users, accounts, strategies, Pine systems, and AI modules.
- Make every upgrade easy to disable from the UI without breaking the legacy flow.
- Preserve the current live trading path as the fallback baseline.

## Non-Goals

- No direct dependency from live execution to TradingView MCP or any chart provider in v1.
- No automatic Pine editing in v1.
- No multi-pane or broad multi-timeframe analysis in v1.
- No behavioral influence on live trades in v1.
- No replacement of the existing webhook, worker, risk, or execution architecture.

## Existing Context

The current system already has:

- webhook ingress
- worker pipeline
- guard rails and risk logic
- broker execution
- an AI layer
- shadow post-trade debate agents

The current AI weakness is that it mostly sees numeric payloads, logs, and rule outputs. It does not reliably understand:

- how the setup looks on the chart
- Pine-generated chart artifacts
- whether the visible structure agrees with the signal
- whether debate-agent outputs are trustworthy and actionable

## Proposed System Shape

Introduce a new top-level architectural concept beside the trading core:

- Trading Core
  - webhook ingress
  - worker pipeline
  - guard rails
  - risk
  - execution
- AI Operating Layer
  - Chart Context Module
  - Pine Understanding Module
  - Debate and Review Module
  - Pre-Trade Advisory Module
  - Memory and Learning Module
  - Copilot Presentation Module
  - AI Control Plane

The Trading Core remains the source of truth for live processing. The AI Operating Layer enriches analysis and operator workflows but must never become a required dependency for trading in v1.

## Module Boundaries

### Chart Context Module

Purpose:
- fetch structured chart context and supporting screenshot evidence

Responsibilities:
- read one active 5-minute chart per signal in v1
- collect visible symbol, timeframe, Pine-rendered values, drawings, labels, zones, and screenshot evidence
- normalize outputs into a stable internal schema
- expose degradation status and reason

Constraints:
- optional only
- chart provider failure must not break the rest of the system

### Pine Understanding Module

Purpose:
- connect Pine source intent with visible chart outputs

Responsibilities:
- parse Pine source as read-only context
- relate Pine logic to what appears on the chart
- provide structured explanations of what the script is trying to detect
- support future suggestion workflows without changing Pine automatically

Constraints:
- no automatic Pine modification in v1

### Debate and Review Module

Purpose:
- run specialized agents over richer context and produce useful post-trade analysis

Responsibilities:
- reuse the current debate pattern
- improve agent inputs with chart context, Pine context, signal traces, and historical memory
- produce layered outputs:
  - simple verdict
  - structured scorecard
  - detailed agent agreement or disagreement

Constraints:
- shadow capable
- independently disableable

### Pre-Trade Advisory Module

Purpose:
- capture what the upgraded AI would have said at signal time

Responsibilities:
- run in shadow mode first
- generate advisory outputs without affecting execution
- record confidence, confluence, caution flags, and module degradation

Constraints:
- no blocking or veto behavior in v1

### Memory and Learning Module

Purpose:
- build a durable learning loop across trades and strategies

Responsibilities:
- store structured AI outputs tied to signals and trades
- retrieve similar historical setups
- identify recurring mistakes and recurring success patterns
- support future improvement suggestions

Constraints:
- suggestions only in early phases

### Copilot Presentation Module

Purpose:
- turn AI outputs into operator-usable UI artifacts

Responsibilities:
- show a compact summary in live surfaces later
- show deep drill-down on trade detail pages first
- present verdict, confidence, scorecard, evidence, disagreement, and degradation reasons

### AI Control Plane

Purpose:
- control, isolate, and safely roll back the AI Operating Layer

Responsibilities:
- module toggles
- scope inheritance
- admin overrides
- panic mode
- health, degraded status, and reason visibility

## Control Model

### Scope Hierarchy

Configuration must support:

- global
- user
- account
- strategy or Pine system

Precedence:

`strategy > account > user > global`

### State Model

Normal configuration state:

- inherit
- enabled
- disabled

Admin override state:

- forced-on
- forced-off

### Panic Mode

Provide one global panic switch in the UI that disables the entire non-core AI Operating Layer and returns the system to legacy behavior immediately.

Panic mode disables:

- Chart Context Module
- Pine Understanding Module
- Debate and Review Module
- Pre-Trade Advisory Module
- Memory and Learning Module
- Copilot Presentation Module
- existing shadow debate agents if they are part of the upgraded AI layer

Panic mode does not disable:

- webhook ingress
- worker pipeline
- guard rails
- risk
- execution
- core required safety checks

## Failure and Degradation Rules

- All AI Operating Layer modules fail open back to the legacy flow.
- Chart-provider outages degrade analysis; they do not fail the AI run unless no useful fallback remains.
- The UI must show both module status and a short human-readable reason.
- Example: `Chart Context: degraded - TradingView provider unavailable, using non-chart fallback`
- Confidence and completeness should reflect missing context.

## Data Flow

### Signal-Time Flow

1. A signal arrives through the existing system.
2. The Trading Core processes it exactly as it does today.
3. In parallel, the AI Operating Layer opens an AI analysis run.
4. The run gathers:
   - signal payload
   - user, account, strategy context
   - Pine source context
   - Pine chart output context
   - screenshot evidence when available
   - historical memory and analog trades
5. Modules run in stages:
   - context collection
   - Pine understanding
   - advisory or debate reasoning
   - scorecard and verdict generation
   - UI formatting
6. Results are stored as structured artifacts tied to the signal or trade.

### Post-Trade Flow

1. After trade completion, the upgraded Debate and Review Module runs with:
   - pre-trade shadow analysis
   - trade outcome
   - chart and Pine evidence
   - historical analogs
2. The system produces:
   - simple verdict
   - structured scorecard
   - deep debate breakdown
   - learning artifacts

## Output Model

Each AI run should produce a layered output:

### Top Layer

- one operator-friendly verdict such as good setup, weak setup, or unclear

### Middle Layer

- setup scorecard
- reasons
- risks
- confluence
- confidence
- caution flags
- degradation notices

### Deep Layer

- agent-by-agent positions
- agreement and disagreement
- chart evidence
- Pine intent alignment
- analog trade references

## Multi-Tenant Requirements

The architecture must support:

- multiple users
- multiple accounts
- multiple strategies
- multiple Pine systems
- multiple AI modules

Artifacts, policies, toggles, and memory must all support scoping and isolation across those dimensions.

## Recommended External-Integration Role

TradingView MCP or a similar provider should be treated as an optional chart-context sidecar, not a primary market-data or execution dependency.

Why:

- it is valuable for chart state, Pine output, screenshots, and setup visibility
- it is not stable enough to be the live trading backbone
- it should enrich AI analysis, not control execution in v1

## First Implementation Slice

Build:

- Chart-Aware Post-Trade Review with Shadow Pre-Trade Analysis

Include:

- one active 5-minute chart per signal
- Pine source as read-only context
- visible Pine chart outputs
- richer inputs for debate agents
- shadow pre-trade analysis capture
- post-trade full review output
- trade-detail-page-first UI presentation
- AI Control Plane basics:
  - per-module toggles
  - scope inheritance
  - admin overrides
  - global panic mode
  - degraded status and reasons

Exclude from this slice:

- live trade influence
- automatic Pine editing
- full strategy lab
- multi-pane chart support
- scoped panic modes

## Rollout Plan

### Phase 1

- keep all upgraded modules execution-independent
- run post-trade review fully
- run pre-trade analysis in shadow
- surface outputs on trade detail pages

### Phase 2

- add compact summaries to the live dashboard and signal feed
- improve historical comparison and learning outputs

### Phase 3

- consider policy-controlled influence for selected modules only after shadow and UI validation proves useful

## Key Design Decisions

- Start with one active 5-minute chart because the user is currently scalping on 5-minute setups.
- Prioritize Pine outputs and Pine source because Pine currently handles the setup logic.
- Optimize first for liquidity sweeps, zones, and Pine-rendered levels rather than generic chart interpretation.
- Keep all upgrades modular and easily disableable from the UI.
- Treat the current debate system as a reusable subsystem to improve, not as something to discard.

## Open Expansion Paths

Future upgrades can add:

- multi-timeframe context
- strategy lab workflows
- Pine suggestion workflows
- consensus agents
- regime awareness
- policy-driven influence
- scoped panic controls
- richer operator workspaces

These are intentionally deferred so the first implementation slice stays focused and safe.
