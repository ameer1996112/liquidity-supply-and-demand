# Add Account Wizard Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Replace the flat AddProfileForm with a premium 3-step wizard that supports Personal, Evaluation, and Funded account types with type-specific fields.

**Architecture:** The wizard lives fully inside `BrokerProfilesPanel.tsx` as a new `AddAccountWizard` component — no new files, no modal. Step 1 picks the account type, Step 2 shows type-specific fields, Step 3 is a review/confirm screen. On save it posts all fields to `POST /api/broker-profiles`.

**Tech Stack:** React, TypeScript, TanStack Query, Lucide icons, existing `var(--to-*)` CSS design tokens.

---

### Task 1: Extend backend `BrokerProfileCreate` schema

**Files:**
- Modify: `src/api_broker_profiles.py`

**Step 1: Add new optional fields to `BrokerProfileCreate`**

```python
class BrokerProfileCreate(BaseModel):
    name: str = Field(..., min_length=1)
    meta_api_account_id: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1)
    risk_pct: float = Field(default=1.0, ge=0.1, le=10.0)
    max_positions: int = Field(default=3, ge=1, le=20)
    run_mode: str = Field(default="LIVE")
    # New fields:
    account_type: str = Field(default="personal")  # personal | evaluation | funded
    prop_firm_name: Optional[str] = Field(default=None)
    evaluation_phase: Optional[str] = Field(default=None)  # phase1 | phase2 | funded
    max_daily_loss_pct: Optional[float] = Field(default=None, ge=0, le=100)
    max_drawdown_pct: Optional[float] = Field(default=None, ge=0, le=100)
    profit_target_usd: Optional[float] = Field(default=None, ge=0)
```

**Step 2: Update the `POST /api/broker-profiles` handler to persist new fields**

In the existing `create_broker_profile()` handler, add the new fields to the `upsert_data` dict:
```python
upsert_data = {
    ...existing fields...,
    "evaluation_mode": body.account_type in ("evaluation", "funded"),
    "evaluation_phase": body.evaluation_phase or ("funded" if body.account_type == "funded" else "phase1"),
    "max_daily_loss_pct": body.max_daily_loss_pct,
    "max_drawdown_pct": body.max_drawdown_pct,
    "profit_target_usd": body.profit_target_usd,
}
```

**Step 3: Run backend tests to confirm no regressions**
```bash
PYTHONPATH=. python -m pytest tests/ -v --ignore=tests/test_e2e.py -q 2>&1 | tail -5
```
Expected: all existing tests pass

**Step 4: Commit**
```bash
git add src/api_broker_profiles.py
git commit -m "feat: extend BrokerProfileCreate with account_type and prop firm fields"
```

---

### Task 2: Build `AddAccountWizard` component (Step 1 — Type Picker)

**Files:**
- Modify: `frontend/src/components/accounts/BrokerProfilesPanel.tsx`

**Step 1: Add `AccountType` type and `WizardStep` state to the wizard**

At top of file, below existing interfaces:
```typescript
type AccountType = 'personal' | 'evaluation' | 'funded';
type WizardStep = 1 | 2 | 3;
```

**Step 2: Build `TypePickerStep` component**

```tsx
const ACCOUNT_TYPES: { type: AccountType; icon: string; label: string; description: string }[] = [
  { type: 'personal', icon: '🧑', label: 'Personal', description: 'Your own live or demo account — no prop firm rules' },
  { type: 'evaluation', icon: '📋', label: 'Evaluation', description: 'Phase 1 or Phase 2 prop firm challenge with guardrails' },
  { type: 'funded', icon: '🏆', label: 'Funded', description: 'Passed your challenge — trading a funded account' },
];

function TypePickerStep({ onSelect }: { onSelect: (t: AccountType) => void }) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--to-text-dim)]">What kind of account is this?</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {ACCOUNT_TYPES.map((at) => (
          <button
            key={at.type}
            onClick={() => onSelect(at.type)}
            className="flex flex-col items-center gap-2 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4 text-center hover:border-[var(--to-warning)]/50 hover:bg-[var(--to-warning)]/5 transition-all"
          >
            <span className="text-2xl">{at.icon}</span>
            <span className="text-sm font-semibold text-[var(--to-text-primary)]">{at.label}</span>
            <span className="text-[11px] text-[var(--to-text-dim)] leading-snug">{at.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
```

**Step 3: Add step indicator component**

```tsx
function StepIndicator({ step, total }: { step: WizardStep; total: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }, (_, i) => i + 1).map((s) => (
        <div key={s} className="flex items-center gap-2">
          <div className={cn(
            'h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold',
            s < step ? 'bg-[var(--to-long)] text-black' : s === step ? 'bg-[var(--to-warning)] text-black' : 'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]'
          )}>{s < step ? '✓' : s}</div>
          {s < total && <div className={cn('h-px w-6', s < step ? 'bg-[var(--to-long)]' : 'bg-[var(--to-border)]')} />}
        </div>
      ))}
    </div>
  );
}
```

**Step 4: Commit**
```bash
git add frontend/src/components/accounts/BrokerProfilesPanel.tsx
git commit -m "feat: wizard step 1 — account type picker with step indicator"
```

---

### Task 3: Build Step 2 — Account Details Form

**Files:**
- Modify: `frontend/src/components/accounts/BrokerProfilesPanel.tsx`

**Step 1: Define unified form state**

```typescript
interface WizardForm {
  accountType: AccountType;
  name: string;
  meta_api_account_id: string;
  token: string;
  risk_pct: number;
  max_positions: number;
  prop_firm_name: string;
  evaluation_phase: 'phase1' | 'phase2';
  max_daily_loss_pct: string;
  max_drawdown_pct: string;
  profit_target_usd: string;
}

const defaultForm = (type: AccountType): WizardForm => ({
  accountType: type,
  name: '', meta_api_account_id: '', token: '',
  risk_pct: 1.0, max_positions: 3,
  prop_firm_name: '', evaluation_phase: 'phase1',
  max_daily_loss_pct: '', max_drawdown_pct: '', profit_target_usd: '',
});
```

**Step 2: Build `DetailsStep` component** — shared fields always shown, conditional sections for evaluation/funded:

```tsx
function DetailsStep({ form, onChange, accountType, onBack, onNext }: { ... }) {
  const [showToken, setShowToken] = useState(false);
  const isPropFirm = accountType !== 'personal';
  const isEval = accountType === 'evaluation';
  const invalid = !form.name || !form.meta_api_account_id || !form.token;
  return (
    <div className="space-y-4">
      {/* Shared fields: Name, Account ID, Token, Risk %, Max Positions */}
      {/* Conditional: prop_firm_name for evaluation/funded */}
      {/* Conditional: evaluation_phase selector for evaluation only */}
      {/* Conditional: optional fields (daily loss, drawdown, profit target) in a collapsible "Advanced Risk Rules" section */}
      <div className="flex gap-2 pt-2">
        <Button variant="ghost" size="sm" onClick={onBack}>← Back</Button>
        <Button size="sm" disabled={invalid} onClick={onNext}>Review →</Button>
      </div>
    </div>
  );
}
```

**Step 3: Commit**
```bash
git add frontend/src/components/accounts/BrokerProfilesPanel.tsx
git commit -m "feat: wizard step 2 — type-specific account details form"
```

---

### Task 4: Build Step 3 — Review & Save

**Files:**
- Modify: `frontend/src/components/accounts/BrokerProfilesPanel.tsx`

**Step 1: Build `ReviewStep` component**

```tsx
function ReviewStep({ form, onBack, onSave, isSaving }: { ... }) {
  const rows = [
    { label: 'Type', value: form.accountType },
    { label: 'Name', value: form.name },
    { label: 'Account ID', value: `${form.meta_api_account_id.slice(0,8)}…` },
    { label: 'Token', value: '••••••••' + form.token.slice(-4) },
    { label: 'Risk %', value: `${form.risk_pct}%` },
    { label: 'Max Positions', value: form.max_positions },
    ...(form.accountType !== 'personal' ? [
      { label: 'Prop Firm', value: form.prop_firm_name || '—' },
      { label: 'Phase', value: form.accountType === 'funded' ? 'Funded' : form.evaluation_phase },
    ] : []),
    ...(form.max_daily_loss_pct ? [{ label: 'Max Daily Loss', value: `${form.max_daily_loss_pct}%` }] : []),
    ...(form.max_drawdown_pct ? [{ label: 'Max Drawdown', value: `${form.max_drawdown_pct}%` }] : []),
    ...(form.profit_target_usd ? [{ label: 'Profit Target', value: `$${form.profit_target_usd}` }] : []),
  ];
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-[var(--to-border)] divide-y divide-[var(--to-border)]">
        {rows.map(r => (
          <div key={r.label} className="flex justify-between px-4 py-2 text-xs">
            <span className="text-[var(--to-text-dim)]">{r.label}</span>
            <span className="font-mono text-[var(--to-text-primary)]">{r.value}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={onBack}>← Back</Button>
        <Button size="sm" className="bg-[var(--to-warning)] text-black" disabled={isSaving} onClick={onSave}>
          {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          {isSaving ? 'Saving…' : 'Save Account'}
        </Button>
      </div>
    </div>
  );
}
```

**Step 2: Wire mutation to map `WizardForm` → POST body**

```typescript
const payload = {
  name: form.name,
  meta_api_account_id: form.meta_api_account_id,
  token: form.token,
  risk_pct: form.risk_pct,
  max_positions: form.max_positions,
  account_type: form.accountType,
  prop_firm_name: form.prop_firm_name || undefined,
  evaluation_phase: form.accountType === 'funded' ? 'funded' : form.evaluation_phase,
  max_daily_loss_pct: form.max_daily_loss_pct ? parseFloat(form.max_daily_loss_pct) : undefined,
  max_drawdown_pct: form.max_drawdown_pct ? parseFloat(form.max_drawdown_pct) : undefined,
  profit_target_usd: form.profit_target_usd ? parseFloat(form.profit_target_usd) : undefined,
};
```

**Step 3: Commit**
```bash
git add frontend/src/components/accounts/BrokerProfilesPanel.tsx
git commit -m "feat: wizard step 3 — review and save, wire mutation"
```

---

### Task 5: Assemble `AddAccountWizard` and swap into `BrokerProfilesPanel`

**Files:**
- Modify: `frontend/src/components/accounts/BrokerProfilesPanel.tsx`

**Step 1: Build the `AddAccountWizard` wrapper**

```tsx
function AddAccountWizard({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) {
  const [step, setStep] = useState<WizardStep>(1);
  const [form, setForm] = useState<WizardForm | null>(null);
  const qc = useQueryClient();
  const { addToast } = useToast();

  const save = useMutation({
    mutationFn: (payload: Parameters<typeof createProfile>[0]) => createProfile(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account added', message: 'New account saved.', severity: 'success' });
      onSuccess();
    },
    onError: (e: Error) => addToast({ title: 'Failed', message: e.message, severity: 'critical' }),
  });

  return (
    <div className="border border-[var(--to-warning)]/30 rounded-xl bg-[var(--to-warning)]/5 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold">Add MetaAPI Account</h3>
        <StepIndicator step={step} total={3} />
      </div>
      {step === 1 && <TypePickerStep onSelect={(t) => { setForm(defaultForm(t)); setStep(2); }} />}
      {step === 2 && form && <DetailsStep form={form} onChange={(f) => setForm(f)} accountType={form.accountType} onBack={() => setStep(1)} onNext={() => setStep(3)} />}
      {step === 3 && form && <ReviewStep form={form} onBack={() => setStep(2)} onSave={() => save.mutate(form as any)} isSaving={save.isPending} />}
      {step === 1 && <Button size="sm" variant="ghost" className="text-xs h-7" onClick={onCancel}>Cancel</Button>}
    </div>
  );
}
```

**Step 2: Replace `AddProfileForm` with `AddAccountWizard` in `BrokerProfilesPanel`**

Search for `showAdd && <AddProfileForm` and replace with `showAdd && <AddAccountWizard`.

Delete the old `AddProfileForm` function entirely.

**Step 3: Run TypeScript check**
```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i "BrokerProfiles\|accounts/page" | head -10
```
Expected: no output (no errors)

**Step 4: Commit and push**
```bash
git add frontend/src/components/accounts/BrokerProfilesPanel.tsx src/api_broker_profiles.py
git commit -m "feat: 3-step Add Account wizard (Personal / Evaluation / Funded)"
git push origin main
```
