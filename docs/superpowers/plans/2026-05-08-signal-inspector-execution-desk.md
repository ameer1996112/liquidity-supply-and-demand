# Signal Inspector Execution Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Signal Inspector into a premium Execution Desk that immediately shows whether a signal traded, why it stopped, and where the bot pipeline failed.

**Architecture:** Keep the refactor scoped to the frontend Signal Inspector. Add deterministic view-model helpers and small local subcomponents inside `SignalInspector.tsx` first, then update tests to lock in execution semantics and existing AI memo behavior. Avoid backend/API changes and do not touch trading logic.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS utilities, lucide-react icons, Radix/shadcn Sheet/Tabs/Badge components, Vitest with jsdom.

---

## File Structure

- Modify: `frontend/src/components/SignalInspector.tsx`
  - Add operational view-model helpers.
  - Add premium Execution Desk local components.
  - Recompose the drawer with outcome-first hierarchy.
  - Preserve AI memo, raw data, debug, and setup screenshot behavior.
- Modify: `frontend/src/components/SignalInspector.test.tsx`
  - Add tests for permission rejection, no-entry semantics, execution path stop stages, and long reason preservation.
  - Keep existing tests passing.
- Do not modify backend files, trading execution files, dashboard table files, or global design tokens unless a compiler error forces a tiny local import/style fix.

## Task 1: Add Outcome And Pipeline View Models

**Files:**
- Modify: `frontend/src/components/SignalInspector.tsx`
- Test: `frontend/src/components/SignalInspector.test.tsx`

- [ ] **Step 1: Add failing tests for outcome semantics**

Append these tests inside the existing `describe('SignalInspector decision summary', () => { ... })` block in `frontend/src/components/SignalInspector.test.tsx`.

```tsx
  it('shows permission rejection as a no-trade execution outcome', () => {
    const signal: TradingSignal = {
      id: 'sig-permission-rejected',
      created_at: '2026-05-08T07:55:02.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'trading_permission_rejected' as TradingSignal['status'],
      price: 1.35852,
      filter_reason: 'permission_file_missing:approved_candidates.json',
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'permission_file_missing:approved_candidates.json',
      },
    };

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('No Trade');
    expect(document.body.textContent).toContain('Permission Gate');
    expect(document.body.textContent).toContain('permission_file_missing:approved_candidates.json');
    expect(document.body.textContent).not.toContain('OPEN');
  });

  it('shows permission allowed without broker execution as no entry', () => {
    const signal: TradingSignal = {
      id: 'sig-permission-allowed',
      created_at: '2026-05-08T08:40:02.000Z',
      symbol: 'XAUUSD',
      side: 'sell',
      status: 'trading_permission_allowed' as TradingSignal['status'],
      price: 4714.11,
      execution_source: 'signal_only',
      run_mode: 'LIVE',
      ai_reasoning: {
        decision: 'GO',
        reason: 'Permission allowed, broker execution not recorded.',
      },
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.body.textContent).toContain('No Entry');
    expect(document.body.textContent).toContain('Broker Execution');
    expect(document.body.textContent).toContain('broker execution not recorded');
    expect(document.body.textContent).not.toContain('Opened trade');
  });
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx
```

Expected: FAIL because `No Trade`, `No Entry`, and the execution path labels are not rendered yet.

- [ ] **Step 3: Add view-model types and helpers**

In `frontend/src/components/SignalInspector.tsx`, add these types after `interface SignalInspectorProps`.

```tsx
type InspectorTone = 'success' | 'danger' | 'warning' | 'muted';
type PipelineStageState = 'pass' | 'fail' | 'skipped' | 'pending' | 'unknown';

interface OutcomeViewModel {
  label: string;
  eyebrow: string;
  tone: InspectorTone;
  reason: string;
}

interface PipelineStageViewModel {
  id: string;
  label: string;
  state: PipelineStageState;
  detail: string;
}

interface TradePlanItem {
  label: string;
  value: React.ReactNode;
  tone?: InspectorTone;
}
```

Add these helpers after `formatNum`.

```tsx
function formatStatusLabel(status: string | undefined): string {
  const raw = String(status || 'unknown').trim();
  if (!raw) return 'Unknown';
  return raw
    .replace(/^trading[_\s-]*/i, '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function isPermissionStatus(status: string | undefined): boolean {
  const normalized = String(status || '').toLowerCase();
  return normalized.includes('trading_permission') || normalized.includes('trade_permission');
}

function isPermissionBlocked(status: string | undefined): boolean {
  const normalized = String(status || '').toLowerCase();
  return (
    isPermissionStatus(status) &&
    (normalized.includes('rejected') ||
      normalized.includes('denied') ||
      normalized.includes('blocked'))
  );
}

function isBrokerExecuted(signal: TradingSignal): boolean {
  const status = String(signal.status || '').toLowerCase();
  const executionSource = String(signal.execution_source || '').toLowerCase();
  return (
    status === 'active' ||
    status === 'open' ||
    status === 'executed' ||
    executionSource === 'metaapi' ||
    executionSource === 'paper'
  );
}

function deriveOutcome(signal: TradingSignal, ai: AIReasoning | null): OutcomeViewModel {
  const status = String(signal.status || '').toLowerCase();
  const reason =
    signal.filter_reason ||
    ai?.reason ||
    getNotes(signal) ||
    'No explicit stop reason was recorded.';

  if (isPermissionBlocked(status)) {
    return {
      label: 'No Trade',
      eyebrow: 'Permission Gate Stopped',
      tone: 'danger',
      reason: `Rejected: ${reason}`,
    };
  }

  if (isPermissionStatus(status) && !isBrokerExecuted(signal)) {
    return {
      label: 'No Entry',
      eyebrow: 'Execution Not Recorded',
      tone: 'warning',
      reason: 'No entry: signal passed permission, broker execution not recorded.',
    };
  }

  if (status === 'failed' || status === 'execution_failed') {
    return {
      label: 'Exec Fail',
      eyebrow: 'Broker Execution Failed',
      tone: 'danger',
      reason: `Execution failed: ${reason}`,
    };
  }

  if (status === 'ai_rejected' || ai?.decision === 'NO_GO') {
    return {
      label: 'No Trade',
      eyebrow: 'AI Brain Rejected',
      tone: 'danger',
      reason: `Rejected: ${reason}`,
    };
  }

  if (status === 'active' || status === 'open' || status === 'executed') {
    return {
      label: 'Open',
      eyebrow: 'Broker Position Active',
      tone: 'success',
      reason: 'Opened trade: broker execution is recorded for this signal.',
    };
  }

  if (status === 'closed') {
    return {
      label: 'Closed',
      eyebrow: 'Trade Completed',
      tone: 'muted',
      reason: reason === 'No explicit stop reason was recorded.' ? 'Closed trade.' : reason,
    };
  }

  return {
    label: formatStatusLabel(signal.status),
    eyebrow: 'Signal State',
    tone: 'muted',
    reason,
  };
}

function deriveExecutionStages(
  signal: TradingSignal,
  ai: AIReasoning | null
): PipelineStageViewModel[] {
  const status = String(signal.status || '').toLowerCase();
  const permissionBlocked = isPermissionBlocked(status);
  const aiRejected = status === 'ai_rejected' || ai?.decision === 'NO_GO';
  const executionFailed = status === 'failed' || status === 'execution_failed';
  const brokerExecuted = isBrokerExecuted(signal);
  const permissionAllowed = isPermissionStatus(status) && !permissionBlocked;

  return [
    {
      id: 'received',
      label: 'Signal Received',
      state: 'pass',
      detail: 'Webhook signal stored in Latest Signals.',
    },
    {
      id: 'permission',
      label: 'Permission Gate',
      state: permissionBlocked ? 'fail' : permissionAllowed || brokerExecuted || aiRejected ? 'pass' : 'unknown',
      detail: permissionBlocked
        ? signal.filter_reason || 'Trading permission rejected this signal.'
        : permissionAllowed
          ? 'Permission allowed the signal to continue.'
          : 'No permission verdict recorded.',
    },
    {
      id: 'ai',
      label: 'AI Brain',
      state: aiRejected ? 'fail' : ai?.decision === 'GO' ? 'pass' : permissionBlocked ? 'skipped' : 'unknown',
      detail: aiRejected
        ? ai?.reason || 'AI rejected this signal.'
        : ai?.decision === 'GO'
          ? 'AI decision approved the setup.'
          : permissionBlocked
            ? 'Skipped after permission gate stopped the signal.'
            : 'No AI decision recorded.',
    },
    {
      id: 'risk',
      label: 'Risk Guard',
      state: brokerExecuted ? 'pass' : permissionBlocked || aiRejected ? 'skipped' : 'unknown',
      detail: brokerExecuted
        ? 'Risk checks did not prevent broker execution.'
        : permissionBlocked || aiRejected
          ? 'Skipped because an earlier gate stopped the signal.'
          : 'No risk result recorded.',
    },
    {
      id: 'broker',
      label: 'Broker Execution',
      state: brokerExecuted ? 'pass' : executionFailed ? 'fail' : permissionBlocked || aiRejected || permissionAllowed ? 'skipped' : 'unknown',
      detail: brokerExecuted
        ? 'Broker execution is recorded.'
        : executionFailed
          ? signal.filter_reason || 'Broker execution failed.'
          : 'No broker execution recorded.',
    },
  ];
}
```

- [ ] **Step 4: Wire helpers into `SignalInspector`**

Inside `SignalInspector`, after `const executionPlan = deriveExecutionPlan(signal);`, add:

```tsx
  const outcome = deriveOutcome(signal, ai);
  const executionStages = deriveExecutionStages(signal, ai);
```

- [ ] **Step 5: Temporarily render minimal outcome/path to pass tests**

Just below `<SheetDescription ...>`, before `<ScrollArea className='h-full'>`, add a temporary hidden diagnostic block:

```tsx
        <div className='sr-only'>
          <span>{outcome.label}</span>
          <span>{outcome.reason}</span>
          {executionStages.map((stage) => (
            <span key={stage.id}>
              {stage.label}: {stage.detail}
            </span>
          ))}
        </div>
```

This keeps the TDD loop green before the premium UI is built in Task 2. Remove this `sr-only` block in Task 2 when the visible components render the same text.

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add frontend/src/components/SignalInspector.tsx frontend/src/components/SignalInspector.test.tsx
git commit -m "DEV-315: add signal inspector execution view model"
```

## Task 2: Build Premium Outcome Header And Execution Path

**Files:**
- Modify: `frontend/src/components/SignalInspector.tsx`
- Test: `frontend/src/components/SignalInspector.test.tsx`

- [ ] **Step 1: Add visible structure test**

Append this test to `frontend/src/components/SignalInspector.test.tsx`.

```tsx
  it('renders the execution desk header and pipeline path visibly', () => {
    const signal: TradingSignal = {
      id: 'sig-desk',
      created_at: '2026-05-08T08:40:02.000Z',
      symbol: 'GBPNZD',
      side: 'buy',
      status: 'trading_permission_allowed' as TradingSignal['status'],
      price: 2.28225,
      run_mode: 'LIVE',
      execution_source: 'signal_only',
      ai_reasoning: {
        decision: 'GO',
        reason: 'Setup approved by AI.',
      },
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.querySelector('[data-testid="execution-desk-header"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="execution-path"]')).not.toBeNull();
    expect(document.body.textContent).toContain('No Entry');
    expect(document.body.textContent).toContain('Signal Received');
    expect(document.body.textContent).toContain('Broker Execution');
  });
```

- [ ] **Step 2: Run the specific test and verify it fails**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx -t "execution desk header"
```

Expected: FAIL because `data-testid="execution-desk-header"` and `execution-path` do not exist yet.

- [ ] **Step 3: Add tone styles and compact primitives**

In `frontend/src/components/SignalInspector.tsx`, add these helpers after `deriveExecutionStages`.

```tsx
const toneClasses: Record<InspectorTone, { rail: string; text: string; bg: string; border: string }> = {
  success: {
    rail: 'bg-[var(--to-long)]',
    text: 'text-[var(--to-long)]',
    bg: 'bg-[var(--to-long)]/8',
    border: 'border-[var(--to-long)]/25',
  },
  danger: {
    rail: 'bg-[var(--to-short)]',
    text: 'text-[var(--to-short)]',
    bg: 'bg-[var(--to-short)]/8',
    border: 'border-[var(--to-short)]/25',
  },
  warning: {
    rail: 'bg-[var(--to-warning)]',
    text: 'text-[var(--to-warning)]',
    bg: 'bg-[var(--to-warning)]/8',
    border: 'border-[var(--to-warning)]/25',
  },
  muted: {
    rail: 'bg-[var(--to-text-dim)]',
    text: 'text-[var(--to-text-secondary)]',
    bg: 'bg-muted/35',
    border: 'border-border',
  },
};

const stageClasses: Record<PipelineStageState, string> = {
  pass: 'border-[var(--to-long)]/25 bg-[var(--to-long)]/7 text-[var(--to-long)]',
  fail: 'border-[var(--to-short)]/25 bg-[var(--to-short)]/7 text-[var(--to-short)]',
  skipped: 'border-[var(--to-warning)]/25 bg-[var(--to-warning)]/7 text-[var(--to-warning)]',
  pending: 'border-[var(--to-warning)]/25 bg-[var(--to-warning)]/7 text-[var(--to-warning)]',
  unknown: 'border-border bg-muted/20 text-muted-foreground',
};

function StageGlyph({ state }: { state: PipelineStageState }) {
  if (state === 'pass') return <Check className='h-3 w-3' />;
  if (state === 'fail') return <X className='h-3 w-3' />;
  if (state === 'skipped') return <AlertTriangle className='h-3 w-3' />;
  if (state === 'pending') return <Activity className='h-3 w-3' />;
  return <Shield className='h-3 w-3' />;
}
```

- [ ] **Step 4: Add `OutcomeHeader` component**

Add this component before `export function SignalInspector`.

```tsx
function OutcomeHeader({
  signal,
  symbol,
  side,
  entryPrice,
  outcome,
}: {
  signal: TradingSignal;
  symbol: string;
  side: string;
  entryPrice: number | undefined;
  outcome: OutcomeViewModel;
}) {
  const tone = toneClasses[outcome.tone];
  const isBuy = side === 'buy';

  return (
    <section
      data-testid='execution-desk-header'
      className={cn(
        'relative overflow-hidden rounded-md border bg-[#0b1017] p-4',
        tone.border
      )}
    >
      <div className={cn('absolute inset-y-0 left-0 w-1', tone.rail)} />
      <div className='flex min-w-0 flex-col gap-4 pl-2'>
        <div className='flex min-w-0 flex-wrap items-center gap-2'>
          <Badge
            className={cn(
              'border-0 px-2.5 py-1 text-[10px] font-bold uppercase',
              isBuy
                ? 'bg-[var(--to-long)]/14 text-[var(--to-long)]'
                : 'bg-[var(--to-short)]/14 text-[var(--to-short)]'
            )}
          >
            {side.toUpperCase()}
          </Badge>
          <Badge className={cn('border px-2 py-0.5 text-[10px]', tone.bg, tone.text, tone.border)}>
            {outcome.eyebrow}
          </Badge>
          <span className='ml-auto font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground'>
            {format(new Date(signal.created_at), 'MMM d, HH:mm')}
          </span>
        </div>

        <div className='grid gap-3'>
          <div className='flex min-w-0 items-end justify-between gap-3'>
            <div className='min-w-0'>
              <div className='font-mono text-2xl font-bold text-foreground'>
                {symbol}
                {entryPrice != null && (
                  <span className='ml-2 text-base font-medium text-muted-foreground'>
                    @{formatNum(entryPrice, symbol.includes('JPY') ? 3 : symbol.includes('BTC') ? 2 : 5)}
                  </span>
                )}
              </div>
              <p className='mt-1 text-xs leading-relaxed text-muted-foreground break-words [overflow-wrap:anywhere]'>
                {outcome.reason}
              </p>
            </div>
            <div className={cn('shrink-0 rounded px-3 py-2 text-right', tone.bg)}>
              <div className={cn('font-mono text-xl font-bold', tone.text)}>
                {outcome.label}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Add `ExecutionPath` component**

Add this component after `OutcomeHeader`.

```tsx
function ExecutionPath({ stages }: { stages: PipelineStageViewModel[] }) {
  return (
    <section data-testid='execution-path' className='rounded-md border border-border bg-card/80'>
      <div className='border-b border-border px-3 py-2'>
        <span className='text-[11px] uppercase tracking-[0.16em] text-muted-foreground'>
          Execution Path
        </span>
      </div>
      <div className='divide-y divide-border/70'>
        {stages.map((stage, index) => (
          <div key={stage.id} className='grid grid-cols-[24px_1fr] gap-3 px-3 py-2.5'>
            <div className='relative flex justify-center'>
              {index < stages.length - 1 && (
                <span className='absolute top-6 h-[calc(100%+10px)] w-px bg-border' />
              )}
              <span
                className={cn(
                  'relative z-10 flex h-5 w-5 items-center justify-center rounded border',
                  stageClasses[stage.state]
                )}
              >
                <StageGlyph state={stage.state} />
              </span>
            </div>
            <div className='min-w-0'>
              <div className='flex min-w-0 items-center justify-between gap-2'>
                <span className='text-xs font-semibold text-foreground'>
                  {stage.label}
                </span>
                <span className='font-mono text-[10px] uppercase text-muted-foreground'>
                  {stage.state}
                </span>
              </div>
              <p className='mt-0.5 text-[11px] leading-relaxed text-muted-foreground break-words [overflow-wrap:anywhere]'>
                {stage.detail}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Replace the old header and remove temporary sr-only block**

In `SignalInspector`, delete the temporary `sr-only` diagnostic block from Task 1.

Replace the entire `<SheetHeader className='mb-6'>...</SheetHeader>` block with:

```tsx
            <SheetHeader className='sr-only'>
              <SheetTitle>{symbol} Signal Inspector</SheetTitle>
            </SheetHeader>

            <div className='space-y-3'>
              <OutcomeHeader
                signal={signal}
                symbol={symbol}
                side={side}
                entryPrice={entryPrice}
                outcome={outcome}
              />
              <ExecutionPath stages={executionStages} />
            </div>
```

- [ ] **Step 7: Run the targeted test**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx -t "execution desk header"
```

Expected: PASS.

- [ ] **Step 8: Run all inspector tests**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add frontend/src/components/SignalInspector.tsx frontend/src/components/SignalInspector.test.tsx
git commit -m "DEV-315: add execution desk header"
```

## Task 3: Replace Overview With Trade Plan And Setup Evidence Modules

**Files:**
- Modify: `frontend/src/components/SignalInspector.tsx`
- Test: `frontend/src/components/SignalInspector.test.tsx`

- [ ] **Step 1: Add test for the trade plan module**

Append this test to `frontend/src/components/SignalInspector.test.tsx`.

```tsx
  it('renders compact trade plan facts in the overview tab', () => {
    const signal: TradingSignal = {
      id: 'sig-plan',
      created_at: '2026-05-08T09:00:00.000Z',
      symbol: 'USDJPY',
      side: 'buy',
      status: 'active',
      entry: 156.659,
      sl: 156.579,
      tp: 156.859,
      risk_usd: 125.11,
      position_size: 0.4,
      execution_source: 'metaapi',
      run_mode: 'LIVE',
    } as TradingSignal;

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    expect(document.querySelector('[data-testid="trade-plan-panel"]')).not.toBeNull();
    expect(document.body.textContent).toContain('Trade Plan');
    expect(document.body.textContent).toContain('Entry');
    expect(document.body.textContent).toContain('156.659');
    expect(document.body.textContent).toContain('$125.11');
    expect(document.body.textContent).toContain('MetaApi MT5 bridge');
  });
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx -t "compact trade plan"
```

Expected: FAIL because `data-testid="trade-plan-panel"` is not rendered.

- [ ] **Step 3: Add trade plan derivation**

Add this helper after `deriveExecutionStages`.

```tsx
function formatSignalPrice(symbol: string, value?: number | null): string {
  if (value == null) return '--';
  const normalized = symbol.toUpperCase();
  const decimals = normalized.includes('JPY')
    ? 3
    : normalized.includes('XAU') || normalized.includes('GOLD') || normalized.includes('BTC')
      ? 2
      : 5;
  return Number(value).toFixed(decimals);
}

function deriveTradePlanItems(
  signal: TradingSignal,
  symbol: string,
  executionPlan: ReturnType<typeof deriveExecutionPlan>,
  pnl: number | null
): TradePlanItem[] {
  const entry = signal.price ?? signal.entry;
  const stopLoss = signal.stop_loss ?? signal.sl;
  const takeProfit = signal.take_profit ?? signal.tp;
  const risk = signal.risk_usd ?? signal.target_risk_usd;

  return [
    { label: 'Action', value: executionPlan.actionLabel },
    { label: 'Mode / Broker', value: executionPlan.brokerLabel },
    { label: 'Entry', value: formatSignalPrice(symbol, entry) },
    { label: 'Stop Loss', value: formatSignalPrice(symbol, stopLoss), tone: 'danger' },
    { label: 'Take Profit', value: formatSignalPrice(symbol, takeProfit), tone: 'success' },
    { label: 'Risk', value: risk != null ? `$${formatNum(risk, 2)}` : '--', tone: risk != null ? 'danger' : 'muted' },
    { label: 'Size', value: signal.position_size != null ? `${signal.position_size} lots` : '--' },
    { label: 'PnL', value: pnl != null ? `${pnl >= 0 ? '+' : ''}$${formatNum(pnl, 2)}` : '--', tone: pnl == null ? 'muted' : pnl >= 0 ? 'success' : 'danger' },
  ];
}
```

Inside `SignalInspector`, after `const executionStages = deriveExecutionStages(signal, ai);`, add:

```tsx
  const tradePlanItems = deriveTradePlanItems(signal, symbol, executionPlan, pnl);
```

- [ ] **Step 4: Add `TradePlanPanel` component**

Add this component after `ExecutionPath`.

```tsx
function TradePlanPanel({ items }: { items: TradePlanItem[] }) {
  return (
    <section data-testid='trade-plan-panel' className='rounded-md border border-border bg-card/80'>
      <div className='border-b border-border px-3 py-2'>
        <span className='text-[11px] uppercase tracking-[0.16em] text-muted-foreground'>
          Trade Plan
        </span>
      </div>
      <div className='grid grid-cols-2 gap-px bg-border/60'>
        {items.map((item) => {
          const tone = item.tone ? toneClasses[item.tone] : null;
          return (
            <div key={item.label} className='min-w-0 bg-card px-3 py-2'>
              <div className='text-[10px] uppercase tracking-[0.14em] text-muted-foreground'>
                {item.label}
              </div>
              <div className={cn('mt-1 min-w-0 font-mono text-xs text-foreground break-words [overflow-wrap:anywhere]', tone?.text)}>
                {item.value}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Replace old overview technical setup**

Inside `<TabsContent value='overview' ...>`, keep the notes, filter reason, setup image, and AI Confidence sections if present, but delete the old `Technical Setup` card.

Insert this at the top of the Overview tab:

```tsx
                <TradePlanPanel items={tradePlanItems} />
```

The Overview order should be:

```tsx
<TradePlanPanel items={tradePlanItems} />
{notes && (...)}
{signal.filter_reason && ...}
{setupImageUrl && (...)}
{score !== null && (...)}
```

- [ ] **Step 6: Run the targeted test**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx -t "compact trade plan"
```

Expected: PASS.

- [ ] **Step 7: Run all inspector tests**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add frontend/src/components/SignalInspector.tsx frontend/src/components/SignalInspector.test.tsx
git commit -m "DEV-315: add inspector trade plan panel"
```

## Task 4: Upgrade AI Brain Into Diagnostic Evidence Panels

**Files:**
- Modify: `frontend/src/components/SignalInspector.tsx`
- Test: `frontend/src/components/SignalInspector.test.tsx`

- [ ] **Step 1: Add AI Brain diagnostic panel test**

Append this test to `frontend/src/components/SignalInspector.test.tsx`.

```tsx
  it('renders AI brain as diagnostic evidence with the failing reason preserved', () => {
    const signal: TradingSignal = {
      id: 'sig-ai-evidence',
      created_at: '2026-05-08T07:55:02.000Z',
      symbol: 'GBPUSD',
      side: 'sell',
      status: 'ai_rejected',
      price: 1.35852,
      ai_reasoning: {
        decision: 'NO_GO',
        reason: 'RF probability 33.6% < 63% threshold',
        llm_status: 'skipped',
        decision_trace: {
          rf_probability_pct: 33.6,
          threshold_pct: 63,
          rules: [
            {
              rule_id: 'rf_threshold',
              passed: false,
              message: 'RF probability 33.6% < 63% threshold',
            },
          ],
        },
      },
    };

    const queryClient = new QueryClient();
    act(() => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SignalInspector signal={signal} open={true} onOpenChange={() => {}} />
        </QueryClientProvider>
      );
    });

    const aiTab = Array.from(document.querySelectorAll('button')).find((el) =>
      el.textContent?.includes('AI Brain')
    );
    act(() => {
      aiTab?.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
      aiTab?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(document.querySelector('[data-testid="ai-decision-panel"]')).not.toBeNull();
    expect(document.body.textContent).toContain('AI Decision');
    expect(document.body.textContent).toContain('NO_GO');
    expect(document.body.textContent).toContain('RF probability 33.6% < 63% threshold');
    expect(document.body.textContent).toContain('LLM Context');
  });
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx -t "diagnostic evidence"
```

Expected: FAIL because `data-testid="ai-decision-panel"` does not exist.

- [ ] **Step 3: Add `SectionShell` component**

Add this component after `TradePlanPanel`.

```tsx
function SectionShell({
  title,
  icon,
  children,
  testId,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section data-testid={testId} className='rounded-md border border-border bg-card/80'>
      <div className='flex items-center gap-2 border-b border-border px-3 py-2'>
        <span className='text-muted-foreground'>{icon}</span>
        <span className='text-[11px] uppercase tracking-[0.16em] text-muted-foreground'>
          {title}
        </span>
      </div>
      <div className='p-3'>
        {children}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add `AiDecisionPanel` component**

Add this component after `SectionShell`.

```tsx
function AiDecisionPanel({
  ai,
  decisionValue,
  rejectedRuleMessage,
  llmStatus,
  llmContextMessage,
  traceRules,
  failingRules,
}: {
  ai: AIReasoning;
  decisionValue: string;
  rejectedRuleMessage: string;
  llmStatus: string;
  llmContextMessage: string | null;
  traceRules: Array<Record<string, unknown>>;
  failingRules: Array<Record<string, unknown>>;
}) {
  const visibleRules = decisionValue === 'NO_GO' && failingRules.length > 0 ? failingRules : traceRules;

  return (
    <SectionShell
      title='AI Decision'
      icon={<Brain className='h-4 w-4' />}
      testId='ai-decision-panel'
    >
      <div className='space-y-3'>
        <div className='flex min-w-0 flex-col gap-2'>
          <Badge className='w-fit border border-border bg-muted px-2 py-0.5 font-mono text-xs text-foreground'>
            {decisionValue}
          </Badge>
          <p className='text-sm leading-relaxed text-foreground/90 break-words [overflow-wrap:anywhere]'>
            {decisionValue === 'GO'
              ? 'Approved: all active gates passed.'
              : decisionValue === 'MODEL_ERROR'
                ? `Model error: ${rejectedRuleMessage}`
                : `Rejected: ${rejectedRuleMessage}`}
          </p>
        </div>

        {(llmStatus || visibleRules.some((rule) => rule?.rule_id === 'llm_context')) && (
          <div className='rounded border border-border bg-background/40 px-2.5 py-2 text-xs text-muted-foreground'>
            <span className='font-semibold text-foreground'>LLM Context: </span>
            <span className={cn('font-semibold', llmStatus === 'ok' ? 'text-[var(--to-long)]' : 'text-[var(--to-warning)]')}>
              {llmStatus === 'ok' ? 'OK' : llmStatus === 'error' ? 'ERROR (NON-BLOCKING)' : 'SKIPPED'}
            </span>
            {llmContextMessage && <span className='ml-2'>{llmContextMessage}</span>}
          </div>
        )}

        {visibleRules.length > 0 && (
          <div className='space-y-2'>
            {visibleRules.map((rule, idx) => {
              const badge = getRuleBadge(rule, ai);
              const ruleMessage = rule?.message != null ? String(rule.message) : '';
              return (
                <div
                  key={`${getRuleDisplayId(rule)}-${idx}`}
                  className={cn('rounded border px-2.5 py-2 text-xs', badge.rowClass)}
                >
                  <div className='flex min-w-0 items-start justify-between gap-3'>
                    <div className='min-w-0'>
                      <div className='font-mono text-foreground/90 break-words [overflow-wrap:anywhere]'>
                        {getRuleDisplayId(rule)}
                      </div>
                      {ruleMessage && (
                        <div className='mt-0.5 text-muted-foreground break-words [overflow-wrap:anywhere]'>
                          {ruleMessage}
                        </div>
                      )}
                    </div>
                    <span className={cn('shrink-0 text-[10px] font-semibold uppercase', badge.textClass)}>
                      {badge.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </SectionShell>
  );
}
```

- [ ] **Step 5: Replace the old Ensemble Decision card**

Inside `<TabsContent value='ai' ...>`, delete the old "Ensemble Decision Summary" card block from `{/* Ensemble Decision Summary */}` through its closing `</div>`.

Insert this in its place:

```tsx
                    <AiDecisionPanel
                      ai={ai}
                      decisionValue={decisionValue}
                      rejectedRuleMessage={rejectedRuleMessage}
                      llmStatus={llmStatus}
                      llmContextMessage={llmContextMessage}
                      traceRules={traceRules as Array<Record<string, unknown>>}
                      failingRules={failingRules as Array<Record<string, unknown>>}
                    />
```

Keep the existing Zone Analysis, Liquidity Analysis, AI Metrics, narrative/rules if still present, and `Show Debug` functionality. If `Show Debug` was inside the deleted block, place the same button and debug JSON block immediately after `AiDecisionPanel`.

- [ ] **Step 6: Run targeted and full tests**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx -t "diagnostic evidence"
cd frontend && npx vitest run src/components/SignalInspector.test.tsx
```

Expected: both PASS.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add frontend/src/components/SignalInspector.tsx frontend/src/components/SignalInspector.test.tsx
git commit -m "DEV-315: redesign ai brain evidence panel"
```

## Task 5: Final Polish, Build, And Ticket Closure

**Files:**
- Modify: `frontend/src/components/SignalInspector.tsx`

- [ ] **Step 1: Polish drawer spacing and tab styling**

In `SignalInspector.tsx`, make these final styling adjustments:

- `SheetContent` should keep `w-full sm:max-w-xl bg-background border-border p-0`.
- Main inner container should use `className='min-w-0 space-y-4 p-5'`.
- `TabsList` should use compact command styling:

```tsx
<TabsList className='w-full rounded-md border border-border bg-card/80 p-1'>
```

- Each `TabsTrigger` should keep icon+text but use:

```tsx
className='flex-1 data-[state=active]:bg-muted text-xs font-mono uppercase'
```

- Ensure every panel class uses `rounded-md`, not `rounded-lg`, for the premium dense style.

- [ ] **Step 2: Run focused tests**

Run:

```bash
cd frontend && npx vitest run src/components/SignalInspector.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run production build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS. The build may print the existing Supabase mock-data warning when env vars are missing.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git diff -- frontend/src/components/SignalInspector.tsx frontend/src/components/SignalInspector.test.tsx
git status --short
```

Expected:

- Only `frontend/src/components/SignalInspector.tsx` and `frontend/src/components/SignalInspector.test.tsx` should be modified by this redesign.
- Any pre-existing unrelated change such as `mcp/tradingview-mcp` must remain untouched.

- [ ] **Step 5: Close Jira ticket**

Run:

```bash
curl -s -X POST "http://localhost:8000/api/tickets/DEV-315/ai-update" \
  -H "Content-Type: application/json" \
  -d '{"new_status":"done","summary_of_work":"Redesigned Signal Inspector into an Execution Desk experience with outcome-first header, execution path, compact trade plan, and AI diagnostic evidence panels. Added tests for permission rejection, no-entry semantics, and execution path clarity. Verified inspector tests and frontend build.","agent":"codex"}'
```

Expected response:

```json
{"status":"ok","ticket_id":"DEV-315","new_status":"done","changelog_entries":1}
```

- [ ] **Step 6: Commit final polish**

Run:

```bash
git add frontend/src/components/SignalInspector.tsx frontend/src/components/SignalInspector.test.tsx
git commit -m "DEV-315: polish signal inspector execution desk"
```

## Self-Review Checklist

- Spec coverage:
  - Outcome-first hierarchy is covered in Task 2.
  - Reason line and no-entry/no-trade semantics are covered in Tasks 1 and 2.
  - Execution path is covered in Tasks 1 and 2.
  - Trade plan is covered in Task 3.
  - AI Brain diagnostic evidence is covered in Task 4.
  - Accessibility and clipping constraints are covered through visible text, labels, wrapping, and build verification.
- Placeholder scan:
  - No task contains deferred implementation language.
  - All code steps include concrete snippets.
- Type consistency:
  - `InspectorTone`, `PipelineStageState`, `OutcomeViewModel`, `PipelineStageViewModel`, and `TradePlanItem` are defined before use.
  - `deriveOutcome`, `deriveExecutionStages`, and `deriveTradePlanItems` names are consistent across tasks.
  - `OutcomeHeader`, `ExecutionPath`, `TradePlanPanel`, and `AiDecisionPanel` receive explicit props.
