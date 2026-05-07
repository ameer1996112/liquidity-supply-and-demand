# Latest Signals Trading Blotter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Dashboard Latest Signals area into a full-width professional trading blotter with calmer typography, clearer columns, and preserved signal behavior.

**Architecture:** Keep the work scoped to the existing dashboard surface. `frontend/src/components/dashboard/SignalTable.tsx` owns the blotter grid, row hierarchy, filtering, sorting, and rendering. `frontend/src/app/page.tsx` owns the horizontal relationship between Latest Signals and Live Log so the table gets enough width on desktop while Live Log remains available.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS utilities, Vitest/jsdom.

---

## File Structure

- Modify: `frontend/src/components/dashboard/SignalTable.tsx`
  - Replace the grouped `Entry / SL / TP` presentation with separate `Entry`, `SL`, and `TP` columns.
  - Reduce badge weight, reserve mono typography for numeric values, and use sans typography for labels and symbols.
  - Keep existing filtering, sorting, row selection, P&L source, risk display, council display, and status behavior.
- Modify: `frontend/src/app/page.tsx`
  - Make the Latest Signals section dominate the row.
  - Reduce the Live Log desktop width and make the two-column split less damaging to the table.
- Modify: `frontend/src/components/dashboard/SignalTable.test.tsx`
  - Update expectations for the final column labels.
  - Add coverage that Entry, SL, TP, Risk, Setup, AI, and Status remain visible.

---

## Task 1: Lock The Blotter Labels In Tests

**Files:**
- Modify: `frontend/src/components/dashboard/SignalTable.test.tsx`
- Test: `frontend/src/components/dashboard/SignalTable.test.tsx`

- [ ] **Step 1: Update the strategy/filter rendering test to assert the final operator labels**

In the first test, after rendering the harness and before clicking the strategy filter, ensure these expectations exist:

```tsx
expect(container.textContent).toContain('Time');
expect(container.textContent).toContain('Symbol');
expect(container.textContent).toContain('Side');
expect(container.textContent).toContain('Entry');
expect(container.textContent).toContain('SL');
expect(container.textContent).toContain('TP');
expect(container.textContent).toContain('P&L');
expect(container.textContent).toContain('Risk');
expect(container.textContent).toContain('Setup');
expect(container.textContent).toContain('AI');
expect(container.textContent).toContain('Status');
expect(container.textContent).not.toContain('Entry / SL / TP');
expect(container.textContent).not.toContain('Market');
expect(container.textContent).not.toContain('Bias');
expect(container.textContent).not.toContain('Plan');
```

- [ ] **Step 2: Run the targeted test to verify it fails before implementation**

Run:

```bash
cd frontend && npx vitest run src/components/dashboard/SignalTable.test.tsx
```

Expected: fail because `Entry / SL / TP` is still present and separate `SL` / `TP` headers are not rendered.

- [ ] **Step 3: Commit the failing test**

```bash
git add frontend/src/components/dashboard/SignalTable.test.tsx
git commit -m "DEV-306: cover latest signals blotter labels"
```

---

## Task 2: Redefine The Signal Grid

**Files:**
- Modify: `frontend/src/components/dashboard/SignalTable.tsx`
- Test: `frontend/src/components/dashboard/SignalTable.test.tsx`

- [ ] **Step 1: Replace the grid definition with separate trade-plan columns**

In `SignalTable.tsx`, replace `SIGNAL_GRID_STYLE` with:

```tsx
const SIGNAL_GRID_STYLE = {
  gridTemplateColumns:
    '64px minmax(150px,1.2fr) 64px minmax(92px,0.8fr) minmax(92px,0.8fr) minmax(92px,0.8fr) 96px 96px 76px 64px 92px',
} as const;

const SIGNAL_TABLE_MIN_WIDTH = 'min-w-[1120px]';
```

- [ ] **Step 2: Update `SignalBlotterHeader` labels**

Replace the current header body with:

```tsx
<SortHeader field='created_at' label='Time' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='symbol' label='Symbol' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='side' label='Side' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='entry' label='Entry' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='entry' label='SL' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='entry' label='TP' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='pnl' label='P&L' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='risk' label='Risk' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
<SortHeader field='setup_score' label='Setup' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
```

Keep the existing custom AI button, but ensure its visible text is exactly:

```tsx
<span>AI</span>
```

Keep the final status header as:

```tsx
<SortHeader field='status' label='Status' sortField={sortField} sortDir={sortDir} onSort={onSort} />
```

- [ ] **Step 3: Apply the shared min-width constant to header, rows, and table shell**

Use `SIGNAL_TABLE_MIN_WIDTH` in the three className locations:

```tsx
className={cn(
  'sticky top-0 z-10 grid items-center border-b border-[var(--to-border)] bg-[#0d1219]/95 px-3 py-2 backdrop-blur',
  SIGNAL_TABLE_MIN_WIDTH,
)}
```

```tsx
className={cn(
  'group grid items-center border-b border-[var(--to-border)]/40 px-3 py-2 text-left transition-colors duration-150',
  SIGNAL_TABLE_MIN_WIDTH,
  'bg-[#0d1218]/90 hover:bg-[#121821]',
  'border-l-2',
  sideBorderColor(signal.side),
  broker?.is_stale && 'opacity-70',
  isOpenStatus(signal.status) && 'bg-[#101824]',
)}
```

```tsx
<div className={cn(
  'overflow-hidden rounded-md border border-[var(--to-border)]/60 bg-[#090d13]',
  SIGNAL_TABLE_MIN_WIDTH,
)}>
```

- [ ] **Step 4: Run the targeted test**

Run:

```bash
cd frontend && npx vitest run src/components/dashboard/SignalTable.test.tsx
```

Expected: label assertions pass or only row rendering assertions fail because row cells are not split yet.

---

## Task 3: Rebuild Row Cells For Scanability

**Files:**
- Modify: `frontend/src/components/dashboard/SignalTable.tsx`
- Test: `frontend/src/components/dashboard/SignalTable.test.tsx`

- [ ] **Step 1: Add a small numeric cell helper above `SignalBlotterRow`**

```tsx
function PriceCell({
  symbol,
  value,
  tone = 'neutral',
}: {
  symbol: string;
  value?: number | null;
  tone?: 'neutral' | 'long' | 'short';
}) {
  const toneClass =
    tone === 'long'
      ? 'text-[var(--to-long)]'
      : tone === 'short'
        ? 'text-[var(--to-short)]'
        : 'text-[var(--to-text-secondary)]';

  return (
    <span className={cn('block text-right font-mono text-[11px] font-medium tabular-nums', toneClass)}>
      {formatSignalPrice(symbol, value)}
    </span>
  );
}
```

- [ ] **Step 2: Replace the current grouped Entry/SL/TP cell in `SignalBlotterRow`**

Remove the current `<div className='flex flex-col items-end gap-1 font-mono...'>...</div>` that renders Entry, SL, and TP together. Replace it with three separate cells:

```tsx
<div title={`Entry: ${formatSignalPrice(signal.symbol, entry)}`}>
  <PriceCell symbol={signal.symbol} value={entry} />
</div>

<div title={`Stop Loss: ${formatSignalPrice(signal.symbol, sl)}`}>
  <PriceCell symbol={signal.symbol} value={sl} tone='short' />
</div>

<div title={`Take Profit: ${formatSignalPrice(signal.symbol, tp)}`}>
  <PriceCell symbol={signal.symbol} value={tp} tone='long' />
</div>
```

- [ ] **Step 3: Calm the symbol cell**

Replace the symbol block with:

```tsx
<div className='flex min-w-0 flex-col gap-0.5'>
  <span className='truncate text-[13px] font-semibold text-[var(--to-text-primary)]'>
    {signal.symbol}
  </span>
  <div className='flex min-w-0 items-center gap-1.5 text-[9px] text-[var(--to-text-dim)]'>
    {(signal as any).account_name && (
      <span className='truncate'>
        {(signal as any).account_name}
      </span>
    )}
    {(signal as any).account_name && getSignalStrategyBadge(signal) && (
      <span className='text-[var(--to-border)]'>/</span>
    )}
    {getSignalStrategyBadge(signal) && (
      <span className='truncate'>
        {getSignalStrategyBadge(signal)}
      </span>
    )}
  </div>
</div>
```

- [ ] **Step 4: Calm the time, P&L, risk, AI, and status cells**

Use this time class:

```tsx
className='inline-flex w-fit items-center rounded border border-[var(--to-border)]/45 bg-black/10 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-[var(--to-text-secondary)]'
```

Use this risk pill class:

```tsx
className='inline-flex items-center gap-1 rounded border border-[var(--to-short)]/15 bg-[var(--to-short)]/7 px-1.5 py-0.5 font-mono text-[10px] font-medium tabular-nums text-[var(--to-short)]'
```

Use this AI cell class:

```tsx
<div className='flex justify-end font-mono text-[11px] font-medium tabular-nums'>
  <span className={cn(scoreColor)}>{score == null ? '—' : Math.round(score)}</span>
</div>
```

Keep `StatusBadge`, `SideBadge`, `SetupScoreBadge`, and `CouncilBadge` behavior intact.

- [ ] **Step 5: Run the targeted test**

Run:

```bash
cd frontend && npx vitest run src/components/dashboard/SignalTable.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit the row rebuild**

```bash
git add frontend/src/components/dashboard/SignalTable.tsx frontend/src/components/dashboard/SignalTable.test.tsx
git commit -m "DEV-306: rebuild latest signals blotter rows"
```

---

## Task 4: Give The Table More Width Beside Live Log

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Test: `frontend/src/components/dashboard/SignalTable.test.tsx`

- [ ] **Step 1: Reduce the Live Log desktop width**

In `frontend/src/app/page.tsx`, replace:

```tsx
<aside className='flex min-h-0 w-full flex-col gap-2 xl:w-[320px]'>
```

with:

```tsx
<aside className='flex min-h-0 w-full flex-col gap-2 xl:w-[260px] 2xl:w-[300px]'>
```

- [ ] **Step 2: Reduce Latest Signals padding slightly**

In the same block, replace:

```tsx
<div className='h-0 flex-1 overflow-hidden p-2'>
```

with:

```tsx
<div className='h-0 flex-1 overflow-hidden p-1.5'>
```

- [ ] **Step 3: Run the targeted component test**

Run:

```bash
cd frontend && npx vitest run src/components/dashboard/SignalTable.test.tsx
```

Expected: pass.

- [ ] **Step 4: Commit the parent layout adjustment**

```bash
git add frontend/src/app/page.tsx
git commit -m "DEV-306: widen latest signals workspace"
```

---

## Task 5: Build Verification

**Files:**
- Verify: `frontend/src/components/dashboard/SignalTable.tsx`
- Verify: `frontend/src/app/page.tsx`
- Verify: `frontend/src/components/dashboard/SignalTable.test.tsx`

- [ ] **Step 1: Run the targeted tests**

```bash
cd frontend && npx vitest run src/components/dashboard/SignalTable.test.tsx
```

Expected: pass. Existing React `act(...)` warnings may appear if they already appear in this test file, but the command must exit successfully.

- [ ] **Step 2: Run the frontend production build**

```bash
cd frontend && npm run build
```

Expected: pass.

- [ ] **Step 3: Inspect the diff for scope**

```bash
git diff --stat HEAD~3..HEAD
git diff HEAD~3..HEAD -- frontend/src/components/dashboard/SignalTable.tsx frontend/src/app/page.tsx frontend/src/components/dashboard/SignalTable.test.tsx
```

Expected: only the dashboard table, dashboard parent layout, and targeted tests changed.

- [ ] **Step 4: Close the ticket**

```bash
curl -s -X POST "http://localhost:8000/api/tickets/DEV-306/ai-update" \
  -H "Content-Type: application/json" \
  -d '{"new_status":"done","summary_of_work":"Redesigned Latest Signals as a professional trading blotter with separate Entry, SL, TP, P&L, Risk, Setup, AI, and Status columns; calmed typography and badges; widened the dashboard workspace beside Live Log; and verified targeted tests plus frontend build.","agent":"codex"}'
```

Expected response includes:

```json
{"status":"ok","ticket_id":"DEV-306","new_status":"done"}
```

---

## Self-Review

Spec coverage:

- Full-width professional blotter: Tasks 2, 3, and 4.
- Clear operator labels: Tasks 1 and 2.
- Sans for identity and labels, mono for numbers: Task 3.
- Separate Entry, SL, TP values: Tasks 1, 2, and 3.
- Risk remains visible: Tasks 1 and 3.
- Filtering, sorting, row selection, P&L source, status behavior preserved: Tasks 2 and 3 keep existing logic and Task 5 verifies tests.
- Live Log relationship: Task 4.
- No trading logic changes: file structure and tasks are frontend-only.

Placeholder scan:

- No incomplete implementation placeholders are present.
- Missing-value behavior remains handled by `formatSignalPrice`, `formatJournalRisk`, `PnLText`, and existing council/status components.

Type consistency:

- `SIGNAL_GRID_STYLE`, `SIGNAL_TABLE_MIN_WIDTH`, and `PriceCell` are defined before use.
- Existing `SortField` values are reused; SL and TP headers sort by `entry` because no separate sort fields exist and the spec does not require new sorting behavior.
