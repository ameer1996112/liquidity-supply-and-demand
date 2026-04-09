# 2026-03-26 Add Account Wizard Design

## Goal
Replace the basic flat Add Account form with a premium 3-step wizard that supports Personal, Evaluation, and Funded account types with type-specific fields.

## Account Types

| Type | `evaluation_mode` | `evaluation_phase` | Extra fields |
|------|---|----|---|
| Personal | false | — | None |
| Evaluation | true | `phase1` or `phase2` | Prop firm, daily loss %, drawdown %, profit target |
| Funded | true | `funded` | Prop firm, daily loss %, drawdown % |

## Wizard Steps

### Step 1 — Account Type Picker
- Three full-width selectable cards with icon, label, 1-line description
- Icons: 🧑 Personal, 📋 Evaluation, 🏆 Funded
- Clicking a card immediately advances to Step 2

### Step 2 — Account Details
**All types share:** Name, MetaAPI Account ID, MetaAPI Token (masked), Risk %, Max Positions

**Evaluation adds:** Prop firm name, Phase selector (Phase 1 / Phase 2), optional Max Daily Loss %, optional Max Drawdown %, optional Profit Target $

**Funded adds:** Prop firm name, optional Max Daily Loss %, optional Max Drawdown %

### Step 3 — Review & Save
- Read-only summary of all fields
- "Back" to edit, "Save Account" to submit
- POST to `/api/broker-profiles` with all fields

## UI

- Inline in the BrokerProfilesPanel (no modal, slides down like the current form)
- Step indicator at the top (1 → 2 → 3)
- Back/Next navigation buttons
- Consistent dark theme with `var(--to-*)` design tokens

## API Changes
- `POST /api/broker-profiles` body needs new fields: `account_type`, `prop_firm_name`, `evaluation_phase`, `max_daily_loss_pct`, `max_drawdown_pct`, `profit_target_usd`
- Backend already has these columns from migration 021

## Files

- `frontend/src/components/accounts/BrokerProfilesPanel.tsx` — replace `AddProfileForm` with `AddAccountWizard`
