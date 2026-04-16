# Guards Multi-Account Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scope-aware Guards experience with `Global` and `Per Account` modes, backed by new account-scoped guard APIs and per-account guard storage.

**Architecture:** Keep the existing global guard API and UI behavior intact for shared settings, then add a parallel account-scoped path keyed by broker profile/account id. Reuse the existing grouped guard response shape so the frontend can share rendering between global and per-account views while making scope explicit in the UI.

**Tech Stack:** FastAPI, Pydantic, Supabase, React, Next.js App Router, TanStack Query, Vitest/Pytest

---

## File Map

**Backend**
- Modify: `src/api_guards.py`
  - Keep existing global endpoints
  - Add account list endpoint
  - Add account-scoped GET/PATCH endpoints
- Create: `src/services/account_guard_settings.py`
  - Read/write per-account guard settings
  - Apply fallback to global defaults
- Modify: `src/core/guard_rails/guard_registry.py`
  - Add scope metadata for each guard (`global`, `account`, `mixed`)
- Modify: `src/core/broker_profiles.py`
  - Reuse active broker profile loading helpers for account selector data
- Create: `tests/test_api_guards_account_scope.py`
  - API tests for account listing, account guard reads, and account guard writes

**Frontend**
- Modify: `frontend/src/hooks/useGuards.ts`
  - Split hooks into global and account-scoped queries/mutations
- Modify: `frontend/src/components/rules/GuardsPanel.tsx`
  - Add `Global / Per Account` sub-tabs
- Create: `frontend/src/components/rules/AccountGuardsView.tsx`
  - Account selector + account-scoped grouped guard list
- Create: `frontend/src/components/rules/GlobalGuardsView.tsx`
  - Existing global grouped guard list wrapper
- Create: `frontend/src/components/rules/GuardGroupList.tsx`
  - Shared grouped rendering for guard cards
- Modify: `frontend/src/app/risk/__tests__/page.test.tsx`
  - Ensure Guards tab still renders under Risk & Rules
- Create: `frontend/src/components/rules/__tests__/GuardsPanel.test.tsx`
  - Frontend tests for scope switching and account selection

**Docs**
- Modify: `docs/superpowers/specs/2026-04-16-guards-multi-account-design.md`
  - If implementation decisions diverge slightly, update the approved spec after implementation

---

### Task 1: Add Guard Scope Metadata

**Files:**
- Modify: `src/core/guard_rails/guard_registry.py`
- Test: `tests/test_api_guards_account_scope.py`

- [ ] **Step 1: Write the failing backend test for guard scope classification**

```python
def test_global_and_account_guard_sets_are_classified():
    from src.core.guard_rails.guard_registry import get_all_guards

    guards = get_all_guards()
    by_id = {guard.guard_id: guard for guard in guards}

    assert by_id["staleness_guard"].scope == "global"
    assert by_id["daily_loss_limit"].scope == "account"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py::test_global_and_account_guard_sets_are_classified -v`

Expected: FAIL because `scope` is not defined on guard definitions yet.

- [ ] **Step 3: Add scope metadata to guard definitions**

```python
@dataclass(frozen=True)
class GuardDefinition:
    guard_id: str
    name: str
    description: str
    user_description: str
    tier: str
    group: str
    value_type: str
    setting_key: str
    default: Any
    scope: str = "global"
```

```python
GuardDefinition(
    guard_id="staleness_guard",
    name="Staleness Guard",
    scope="global",
    ...
)

GuardDefinition(
    guard_id="daily_loss_limit",
    name="Daily Loss Limit",
    scope="account",
    ...
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py::test_global_and_account_guard_sets_are_classified -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/guard_rails/guard_registry.py tests/test_api_guards_account_scope.py
git commit -m "DEV-108: classify guard scope metadata"
```

### Task 2: Add Per-Account Guard Settings Service

**Files:**
- Create: `src/services/account_guard_settings.py`
- Test: `tests/test_api_guards_account_scope.py`

- [ ] **Step 1: Write the failing service test for account-level override with fallback**

```python
def test_account_guard_setting_falls_back_to_global_default():
    from src.services.account_guard_settings import get_effective_account_guard_value

    value, source = get_effective_account_guard_value(
        account_id="acct-1",
        setting_key="daily_loss_limit_pct",
        global_default=4,
    )

    assert value == 4
    assert source == "global_default"
```

```python
def test_account_guard_setting_prefers_account_override():
    from src.services.account_guard_settings import get_effective_account_guard_value

    value, source = get_effective_account_guard_value(
        account_id="acct-1",
        setting_key="daily_loss_limit_pct",
        global_default=4,
        account_overrides={"daily_loss_limit_pct": 2},
    )

    assert value == 2
    assert source == "account"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py -k account_guard_setting -v`

Expected: FAIL because the service does not exist yet.

- [ ] **Step 3: Write the minimal account guard settings service**

```python
def get_effective_account_guard_value(
    *,
    account_id: str,
    setting_key: str,
    global_default: Any,
    account_overrides: dict[str, Any] | None = None,
) -> tuple[Any, str]:
    overrides = account_overrides or {}
    if setting_key in overrides:
        return overrides[setting_key], "account"
    return global_default, "global_default"
```

```python
def load_account_guard_overrides(account_id: str) -> dict[str, Any]:
    row = (
        get_supabase()
        .table("account_guard_settings")
        .select("settings")
        .eq("account_id", account_id)
        .maybe_single()
        .execute()
    )
    return (row.data or {}).get("settings") or {}
```

```python
def update_account_guard_override(account_id: str, setting_key: str, value: Any) -> dict[str, Any]:
    current = load_account_guard_overrides(account_id)
    current[setting_key] = value
    get_supabase().table("account_guard_settings").upsert(
        {"account_id": account_id, "settings": current},
        on_conflict="account_id",
    ).execute()
    return current
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py -k account_guard_setting -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/account_guard_settings.py tests/test_api_guards_account_scope.py
git commit -m "DEV-108: add account guard settings service"
```

### Task 3: Add Account-Scoped Guards API Endpoints

**Files:**
- Modify: `src/api_guards.py`
- Modify: `src/core/broker_profiles.py`
- Test: `tests/test_api_guards_account_scope.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_list_guard_accounts_returns_active_profiles(client, monkeypatch):
    monkeypatch.setattr(
        "src.api_guards.get_active_profiles",
        lambda: [{"id": "acct-1", "name": "ACG-DEMO-2", "run_mode": "LIVE"}],
    )

    response = client.get("/api/v1/guards/accounts")
    assert response.status_code == 200
    assert response.json()["accounts"][0]["id"] == "acct-1"
```

```python
def test_account_guards_config_filters_to_account_scoped_guards(client, monkeypatch):
    response = client.get("/api/v1/guards/config/account/acct-1")
    assert response.status_code == 200
    assert "capital_protection" in response.json()["groups"]
```

```python
def test_patch_account_guard_does_not_update_global_setting(client, monkeypatch):
    response = client.patch(
        "/api/v1/guards/config/account/acct-1/daily_loss_limit",
        json={"value": 2, "change_reason": "test"},
    )
    assert response.status_code == 200
    assert response.json()["guard_id"] == "daily_loss_limit"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py -k "guard_accounts or account_guards_config or patch_account_guard" -v`

Expected: FAIL with 404s for missing endpoints.

- [ ] **Step 3: Implement the new API endpoints**

```python
@router.get("/accounts")
def list_guard_accounts():
    from src.core.broker_profiles import get_active_profiles

    profiles = get_active_profiles()
    return {
        "accounts": [
            {
                "id": profile["id"],
                "name": profile["name"],
                "run_mode": profile.get("run_mode"),
            }
            for profile in profiles
        ]
    }
```

```python
@router.get("/config/account/{account_id}", response_model=GuardsConfigResponse)
def get_account_guards_config(account_id: str):
    guards = [guard for guard in get_all_guards() if guard.scope == "account"]
    overrides = load_account_guard_overrides(account_id)
    return _build_guards_response(guards=guards, account_id=account_id, overrides=overrides)
```

```python
@router.patch("/config/account/{account_id}/{guard_id}", response_model=GuardUpdateResponse)
def update_account_guard_config(account_id: str, guard_id: str, body: GuardUpdateRequest):
    guard = get_guard(guard_id)
    if not guard or guard.scope != "account":
        raise HTTPException(404, "Account-scoped guard not found")

    new_value = _validate_value(guard, body.value)
    update_account_guard_override(account_id, guard.setting_key, new_value)
    return GuardUpdateResponse(
        guard_id=guard.guard_id,
        setting_key=guard.setting_key,
        old_value=guard.default,
        new_value=new_value,
        confirmed_value=new_value,
        threshold_updates={},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py -v`

Expected: PASS for new account list and account config endpoints.

- [ ] **Step 5: Commit**

```bash
git add src/api_guards.py src/core/broker_profiles.py src/services/account_guard_settings.py tests/test_api_guards_account_scope.py
git commit -m "DEV-108: add account-scoped guards api"
```

### Task 4: Split Frontend Guard Hooks by Scope

**Files:**
- Modify: `frontend/src/hooks/useGuards.ts`
- Test: `frontend/src/components/rules/__tests__/GuardsPanel.test.tsx`

- [ ] **Step 1: Write the failing frontend hook usage test**

```tsx
it('loads global guards by default and account guards when account mode is selected', async () => {
  render(<GuardsPanel />);
  expect(await screen.findByText('Global')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx`

Expected: FAIL because the scoped panel behavior and hooks do not exist yet.

- [ ] **Step 3: Replace single-scope hooks with scoped hooks**

```ts
export function useGlobalGuardsConfig() {
  return useQuery({
    queryKey: ['guards', 'global'],
    queryFn: () => apiFetch<GuardsConfigResponse>('/api/v1/guards/config'),
  });
}

export function useGuardAccounts() {
  return useQuery({
    queryKey: ['guards', 'accounts'],
    queryFn: () => apiFetch<{ accounts: GuardAccount[] }>('/api/v1/guards/accounts'),
  });
}

export function useAccountGuardsConfig(accountId: string | null) {
  return useQuery({
    queryKey: ['guards', 'account', accountId],
    enabled: Boolean(accountId),
    queryFn: () => apiFetch<GuardsConfigResponse>(`/api/v1/guards/config/account/${accountId}`),
  });
}
```

```ts
export function useUpdateAccountGuard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, guardId, ...body }: GuardUpdateRequest & { accountId: string; guardId: string }) =>
      apiFetch<GuardUpdateResponse>(`/api/v1/guards/config/account/${accountId}/${guardId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    onSuccess: (_result, vars) => {
      queryClient.invalidateQueries({ queryKey: ['guards', 'account', vars.accountId] });
    },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx`

Expected: PASS or move past the previous missing-hook failure into the next UI failure.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useGuards.ts frontend/src/components/rules/__tests__/GuardsPanel.test.tsx
git commit -m "DEV-108: split guards hooks by scope"
```

### Task 5: Add Global / Per Account Guards UI Split

**Files:**
- Modify: `frontend/src/components/rules/GuardsPanel.tsx`
- Create: `frontend/src/components/rules/GlobalGuardsView.tsx`
- Create: `frontend/src/components/rules/AccountGuardsView.tsx`
- Create: `frontend/src/components/rules/GuardGroupList.tsx`
- Test: `frontend/src/components/rules/__tests__/GuardsPanel.test.tsx`

- [ ] **Step 1: Write the failing UI tests**

```tsx
it('shows Global and Per Account sub-tabs', async () => {
  render(<GuardsPanel />);
  expect(await screen.findByRole('tab', { name: /Global/i })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: /Per Account/i })).toBeInTheDocument();
});
```

```tsx
it('renders an account selector in Per Account mode', async () => {
  render(<GuardsPanel />);
  await user.click(await screen.findByRole('tab', { name: /Per Account/i }));
  expect(await screen.findByLabelText(/Account/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx`

Expected: FAIL because the sub-tabs and selector are not rendered yet.

- [ ] **Step 3: Refactor the panel into scope-aware views**

```tsx
export function GuardsPanel() {
  const [scope, setScope] = useState<'global' | 'account'>('global');

  return (
    <div className="space-y-4">
      <Tabs value={scope} onValueChange={(value) => setScope(value as 'global' | 'account')}>
        <TabsList>
          <TabsTrigger value="global">Global</TabsTrigger>
          <TabsTrigger value="account">Per Account</TabsTrigger>
        </TabsList>
        <TabsContent value="global">
          <GlobalGuardsView />
        </TabsContent>
        <TabsContent value="account">
          <AccountGuardsView />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

```tsx
export function AccountGuardsView() {
  const { data: accounts } = useGuardAccounts();
  const [accountId, setAccountId] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId && accounts?.accounts?.length) {
      setAccountId(accounts.accounts[0].id);
    }
  }, [accountId, accounts]);

  const { data } = useAccountGuardsConfig(accountId);

  return (
    <div className="space-y-4">
      <label className="text-xs text-[var(--to-text-dim)]">
        Account
        <select value={accountId ?? ''} onChange={(e) => setAccountId(e.target.value)}>
          {accounts?.accounts?.map((account) => (
            <option key={account.id} value={account.id}>{account.name}</option>
          ))}
        </select>
      </label>
      {data ? <GuardGroupList data={data} scopeLabel={`Account: ${accountId}`} /> : null}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/rules/GuardsPanel.tsx frontend/src/components/rules/GlobalGuardsView.tsx frontend/src/components/rules/AccountGuardsView.tsx frontend/src/components/rules/GuardGroupList.tsx frontend/src/components/rules/__tests__/GuardsPanel.test.tsx
git commit -m "DEV-108: add global and per-account guards views"
```

### Task 6: Add Scope Labels and Mutation Safety

**Files:**
- Modify: `frontend/src/components/rules/GuardGroupList.tsx`
- Modify: `frontend/src/components/rules/AccountGuardsView.tsx`
- Modify: `frontend/src/components/rules/GlobalGuardsView.tsx`
- Test: `frontend/src/components/rules/__tests__/GuardsPanel.test.tsx`

- [ ] **Step 1: Write the failing scope-label test**

```tsx
it('shows Global scope labels in global mode and Account scope labels in account mode', async () => {
  render(<GuardsPanel />);
  expect(await screen.findByText(/Global/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx`

Expected: FAIL because guard cards do not yet show explicit scope labels.

- [ ] **Step 3: Add scope labels to guard cards**

```tsx
<span className="text-[10px] font-mono text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] px-1.5 py-0.5 rounded">
  {scopeLabel}
</span>
```

```tsx
<GuardCard
  key={guard.guard_id}
  guard={guard}
  scopeLabel="Global"
  ...
/>
```

```tsx
<GuardCard
  key={guard.guard_id}
  guard={guard}
  scopeLabel={`Account: ${selectedAccount.name}`}
  ...
/>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/rules/GuardGroupList.tsx frontend/src/components/rules/AccountGuardsView.tsx frontend/src/components/rules/GlobalGuardsView.tsx frontend/src/components/rules/__tests__/GuardsPanel.test.tsx
git commit -m "DEV-108: label guard scope in ui"
```

### Task 7: Full Verification

**Files:**
- Modify: none
- Test: `tests/test_api_guards_account_scope.py`
- Test: `frontend/src/components/rules/__tests__/GuardsPanel.test.tsx`

- [ ] **Step 1: Run backend tests**

Run: `source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_guards_account_scope.py -v`

Expected: PASS

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run src/components/rules/__tests__/GuardsPanel.test.tsx src/app/risk/__tests__/page.test.tsx`

Expected: PASS

- [ ] **Step 3: Run lightweight syntax/build verification**

Run: `source ./venv/bin/activate && python -m py_compile src/api_guards.py src/services/account_guard_settings.py`

Expected: no output

Run: `cd frontend && npm run build`

Expected: successful production build

- [ ] **Step 4: Commit final verification-only state if needed**

```bash
git status --short
```

Expected: clean working tree

- [ ] **Step 5: Update docs if implementation diverged**

```bash
git add docs/superpowers/specs/2026-04-16-guards-multi-account-design.md docs/superpowers/plans/2026-04-16-guards-multi-account.md
git commit -m "DEV-108: document guards multi-account rollout"
```

---

## Self-Review

- Spec coverage: covered UI split, backend account endpoints, per-account storage, scope labels, and test coverage
- Placeholder scan: no `TODO`, `TBD`, or deferred implementation markers remain
- Type consistency: plan uses `account_id`, `guard_id`, `scope`, and `GuardsConfigResponse` consistently across backend and frontend tasks
