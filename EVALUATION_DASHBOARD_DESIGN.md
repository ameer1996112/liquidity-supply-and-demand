# Prop Firm Evaluation Dashboard Design

## Overview
Transform the dashboard to track funded account evaluations (FTMO, MyFundedFX, etc.) with real-time progress monitoring, rule compliance, and phase completion tracking.

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [PHASE BADGE]    Day 5/30    |    Progress: 4.2% / 8%               │
│  ✓ Daily Loss OK  ✓ Max DD OK  ✓ Min Days OK  ⚠ Consistency 60%    │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┬──────────────────────┬──────────────────────┐
│  PROFIT TARGET       │  MAX DAILY LOSS      │  MAX DRAWDOWN        │
│  +$2,120 / $5,000    │  -$125 / $500        │  2.1% / 5%           │
│  [Progress Bar 42%]  │  [Safe Zone 25%]     │  [Safe 42%]          │
└──────────────────────┴──────────────────────┴──────────────────────┘

┌──────────────────────────────────┬────────────────────────────────┐
│  PHASE COMPLETION CHECKLIST      │  EVALUATION STATS              │
│  ✓ Profit Target: $2,120 / $5k   │  Total Trades: 47              │
│  ✓ Min Trading Days: 5 / 4       │  Win Rate: 63.2%               │
│  ✓ Max Daily Loss: OK            │  Avg R:R: 1:2.4                │
│  ✓ Max Drawdown: OK              │  Best Day: +$420               │
│  ⚠ Consistency: 60% / 70%        │  Worst Day: -$180              │
│  🔒 UPGRADE TO PHASE 2 (3 days)  │  Avg Win: $95 | Avg Loss: $42  │
└──────────────────────────────────┴────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  📊 DAILY PNL CHART (Last 30 Days)                                  │
│  [Line chart with profit target line, max DD line, daily bars]      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ⚡ RECENT SIGNALS (with LIVE/PAPER badges)                         │
│  [Existing Recent Signals table]                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics to Track

### 1. **Phase Status**
```typescript
interface EvaluationPhase {
  phase: 'phase1' | 'phase2' | 'funded';
  start_date: string;
  current_day: number;
  total_days: number;
  profit_target: number;
  current_profit: number;
  max_daily_loss: number;
  max_drawdown_pct: number;
  min_trading_days: number;
  consistency_target_pct: number; // e.g., 70% (at least 70% of days profitable)
}
```

### 2. **Daily Limits**
- **Max Daily Loss**: Track today's PnL vs max allowed loss
- **Max Drawdown**: Track from account high-water mark
- **Trailing Drawdown**: For funded accounts (loss from highest balance)

### 3. **Phase Completion Rules**
- **Profit Target**: Must reach $5,000 (Phase 1) or $2,500 (Phase 2)
- **Min Trading Days**: Must trade at least 4-5 days
- **Consistency Rule**: 70% of trading days must be profitable
- **No Violations**: Must not breach daily loss or max drawdown

### 4. **Rule Violations**
```typescript
interface RuleViolation {
  type: 'daily_loss' | 'max_drawdown' | 'trading_hours' | 'news_trading';
  timestamp: string;
  description: string;
  severity: 'warning' | 'breach';
}
```

---

## Implementation Plan

### Backend (Python FastAPI)

#### 1. **New Settings for Evaluation Mode**
```python
# config/settings.py
class Settings(BaseSettings):
    # ... existing fields ...

    # Evaluation Mode
    evaluation_mode: bool = False
    evaluation_phase: str = "phase1"  # phase1, phase2, funded
    evaluation_start_date: str = ""

    # Phase 1 Rules
    phase1_profit_target: float = 5000.0
    phase1_max_daily_loss: float = 500.0
    phase1_max_drawdown_pct: float = 5.0
    phase1_min_trading_days: int = 4

    # Phase 2 Rules
    phase2_profit_target: float = 2500.0
    phase2_max_daily_loss: float = 500.0
    phase2_max_drawdown_pct: float = 5.0
    phase2_min_trading_days: int = 4

    # Funded Rules
    funded_max_daily_loss: float = 500.0
    funded_max_drawdown_pct: float = 10.0  # Trailing drawdown

    # Consistency
    consistency_target_pct: float = 70.0  # 70% of days profitable
```

#### 2. **New API Endpoint: `/evaluation/stats`**
```python
# src/api_evaluation.py
from fastapi import APIRouter

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

@router.get("/stats")
def get_evaluation_stats():
    """Get evaluation progress metrics."""
    s = get_settings()

    if not s.evaluation_mode:
        return {"error": "Evaluation mode not enabled"}

    # Calculate metrics
    stats = calculate_evaluation_metrics()

    return {
        "phase": s.evaluation_phase,
        "current_day": stats["current_day"],
        "total_days": stats["total_days"],
        "profit_target": stats["profit_target"],
        "current_profit": stats["current_profit"],
        "profit_progress_pct": stats["profit_progress_pct"],
        "max_daily_loss": stats["max_daily_loss"],
        "today_pnl": stats["today_pnl"],
        "daily_loss_buffer": stats["daily_loss_buffer"],
        "max_drawdown_pct": stats["max_drawdown_pct"],
        "current_drawdown_pct": stats["current_drawdown_pct"],
        "min_trading_days": stats["min_trading_days"],
        "actual_trading_days": stats["actual_trading_days"],
        "consistency_pct": stats["consistency_pct"],
        "consistency_target_pct": s.consistency_target_pct,
        "rules_passed": stats["rules_passed"],
        "violations": stats["violations"],
        "can_upgrade": stats["can_upgrade"],
    }

def calculate_evaluation_metrics():
    from datetime import date, timedelta
    from src.adapters.supabase import init_supabase, supabase

    init_supabase()
    s = get_settings()

    # Determine phase rules
    if s.evaluation_phase == "phase1":
        profit_target = s.phase1_profit_target
        max_daily_loss = s.phase1_max_daily_loss
        max_dd_pct = s.phase1_max_drawdown_pct
        min_days = s.phase1_min_trading_days
        total_days = 30
    elif s.evaluation_phase == "phase2":
        profit_target = s.phase2_profit_target
        max_daily_loss = s.phase2_max_daily_loss
        max_dd_pct = s.phase2_max_drawdown_pct
        min_days = s.phase2_min_trading_days
        total_days = 60
    else:  # funded
        profit_target = 0  # No target for funded
        max_daily_loss = s.funded_max_daily_loss
        max_dd_pct = s.funded_max_drawdown_pct
        min_days = 0
        total_days = 365

    # Calculate current day
    start = datetime.fromisoformat(s.evaluation_start_date).date()
    current_day = (date.today() - start).days + 1

    # Get all closed trades since evaluation start
    resp = supabase.table("trading_signals").select("*").eq("status", "closed").gte("created_at", s.evaluation_start_date).execute()
    trades = resp.data or []

    # Calculate total profit
    current_profit = sum(float(t.get("pnl_usd") or t.get("pnl") or 0) for t in trades)

    # Calculate today's PnL
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    today_trades = [t for t in trades if t["created_at"] >= today_start]
    today_pnl = sum(float(t.get("pnl_usd") or t.get("pnl") or 0) for t in today_trades)

    # Calculate drawdown
    cumulative_pnl = []
    running_sum = s.account_balance
    for t in sorted(trades, key=lambda x: x["created_at"]):
        running_sum += float(t.get("pnl_usd") or t.get("pnl") or 0)
        cumulative_pnl.append(running_sum)

    if cumulative_pnl:
        peak = max(cumulative_pnl)
        current = cumulative_pnl[-1]
        current_drawdown_pct = ((peak - current) / peak * 100) if peak > 0 else 0
    else:
        current_drawdown_pct = 0

    # Calculate trading days (days with at least 1 closed trade)
    trading_days_set = set(t["created_at"][:10] for t in trades)
    actual_trading_days = len(trading_days_set)

    # Calculate consistency (% of profitable days)
    daily_pnls = {}
    for t in trades:
        day = t["created_at"][:10]
        pnl = float(t.get("pnl_usd") or t.get("pnl") or 0)
        daily_pnls[day] = daily_pnls.get(day, 0) + pnl

    profitable_days = sum(1 for pnl in daily_pnls.values() if pnl > 0)
    consistency_pct = (profitable_days / len(daily_pnls) * 100) if daily_pnls else 0

    # Check rules
    rules_passed = {
        "profit_target": current_profit >= profit_target if s.evaluation_phase != "funded" else True,
        "min_trading_days": actual_trading_days >= min_days,
        "max_daily_loss": today_pnl >= -max_daily_loss,
        "max_drawdown": current_drawdown_pct <= max_dd_pct,
        "consistency": consistency_pct >= s.consistency_target_pct,
    }

    violations = []
    if not rules_passed["max_daily_loss"]:
        violations.append({"type": "daily_loss", "message": f"Daily loss ${abs(today_pnl):.2f} exceeds max ${max_daily_loss}"})
    if not rules_passed["max_drawdown"]:
        violations.append({"type": "max_drawdown", "message": f"Drawdown {current_drawdown_pct:.1f}% exceeds max {max_dd_pct}%"})

    can_upgrade = all(rules_passed.values()) and current_day >= min_days

    return {
        "current_day": current_day,
        "total_days": total_days,
        "profit_target": profit_target,
        "current_profit": current_profit,
        "profit_progress_pct": (current_profit / profit_target * 100) if profit_target > 0 else 0,
        "max_daily_loss": max_daily_loss,
        "today_pnl": today_pnl,
        "daily_loss_buffer": max_daily_loss + today_pnl,
        "max_drawdown_pct": max_dd_pct,
        "current_drawdown_pct": current_drawdown_pct,
        "min_trading_days": min_days,
        "actual_trading_days": actual_trading_days,
        "consistency_pct": consistency_pct,
        "rules_passed": rules_passed,
        "violations": violations,
        "can_upgrade": can_upgrade,
    }
```

#### 3. **Register Router**
```python
# src/api.py
from src.api_evaluation import router as evaluation_router

app.include_router(evaluation_router)
```

---

### Frontend (Next.js)

#### 1. **New Component: `EvaluationDashboard.tsx`**
```tsx
// frontend/src/components/evaluation/EvaluationDashboard.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, Lock, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EvaluationStats {
  phase: 'phase1' | 'phase2' | 'funded';
  current_day: number;
  total_days: number;
  profit_target: number;
  current_profit: number;
  profit_progress_pct: number;
  max_daily_loss: number;
  today_pnl: number;
  daily_loss_buffer: number;
  max_drawdown_pct: number;
  current_drawdown_pct: number;
  min_trading_days: number;
  actual_trading_days: number;
  consistency_pct: number;
  consistency_target_pct: number;
  rules_passed: {
    profit_target: boolean;
    min_trading_days: boolean;
    max_daily_loss: boolean;
    max_drawdown: boolean;
    consistency: boolean;
  };
  violations: Array<{ type: string; message: string }>;
  can_upgrade: boolean;
}

async function fetchEvaluationStats(): Promise<EvaluationStats> {
  const res = await fetch('/evaluation/stats');
  if (!res.ok) throw new Error('Failed to fetch evaluation stats');
  return res.json();
}

export function EvaluationDashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['evaluation-stats'],
    queryFn: fetchEvaluationStats,
    refetchInterval: 10_000, // Refresh every 10 seconds
  });

  if (isLoading || !stats) return <div>Loading evaluation data...</div>;

  const phaseLabels = {
    phase1: 'Phase 1',
    phase2: 'Phase 2',
    funded: 'Funded Account',
  };

  const phaseBadgeColors = {
    phase1: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    phase2: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    funded: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  };

  return (
    <div className="space-y-4">
      {/* Phase Header */}
      <div className="tv-card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge className={cn('font-mono text-xs font-bold px-3 py-1 border', phaseBadgeColors[stats.phase])}>
              {phaseLabels[stats.phase]}
            </Badge>
            <span className="text-sm text-zinc-400 font-mono">
              Day {stats.current_day}/{stats.total_days}
            </span>
            <span className="text-sm text-zinc-400 font-mono">
              Progress: {stats.profit_progress_pct.toFixed(1)}% / 100%
            </span>
          </div>
          <div className="flex items-center gap-2">
            {stats.rules_passed.max_daily_loss ? (
              <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border text-[10px]">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Daily Loss OK
              </Badge>
            ) : (
              <Badge className="bg-rose-500/15 text-rose-400 border-rose-500/30 border text-[10px]">
                <AlertTriangle className="w-3 h-3 mr-1" />
                Daily Loss Breach
              </Badge>
            )}
            {stats.rules_passed.max_drawdown ? (
              <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border text-[10px]">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Max DD OK
              </Badge>
            ) : (
              <Badge className="bg-rose-500/15 text-rose-400 border-rose-500/30 border text-[10px]">
                <AlertTriangle className="w-3 h-3 mr-1" />
                Max DD Breach
              </Badge>
            )}
            {stats.rules_passed.consistency ? (
              <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border text-[10px]">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Consistency {stats.consistency_pct.toFixed(0)}%
              </Badge>
            ) : (
              <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 border text-[10px]">
                <AlertTriangle className="w-3 h-3 mr-1" />
                Consistency {stats.consistency_pct.toFixed(0)}%
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-4">
        {/* Profit Target */}
        <div className="tv-card p-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono block mb-2">
            Profit Target
          </span>
          <div className="flex items-baseline gap-2 mb-2">
            <span className={cn('text-2xl font-bold tabular-nums', stats.current_profit >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
              ${stats.current_profit.toFixed(2)}
            </span>
            <span className="text-sm text-zinc-600">/ ${stats.profit_target.toFixed(0)}</span>
          </div>
          <Progress value={Math.min(stats.profit_progress_pct, 100)} className="h-2" />
          <span className="text-[10px] text-zinc-600 font-mono mt-1 block">
            {stats.profit_progress_pct.toFixed(1)}%
          </span>
        </div>

        {/* Max Daily Loss */}
        <div className="tv-card p-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono block mb-2">
            Max Daily Loss
          </span>
          <div className="flex items-baseline gap-2 mb-2">
            <span className={cn('text-2xl font-bold tabular-nums', stats.today_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
              ${stats.today_pnl.toFixed(2)}
            </span>
            <span className="text-sm text-zinc-600">/ -${stats.max_daily_loss.toFixed(0)}</span>
          </div>
          <Progress
            value={Math.min((Math.abs(stats.today_pnl) / stats.max_daily_loss) * 100, 100)}
            className="h-2"
          />
          <span className="text-[10px] text-zinc-600 font-mono mt-1 block">
            Buffer: ${stats.daily_loss_buffer.toFixed(2)}
          </span>
        </div>

        {/* Max Drawdown */}
        <div className="tv-card p-4">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono block mb-2">
            Max Drawdown
          </span>
          <div className="flex items-baseline gap-2 mb-2">
            <span className={cn('text-2xl font-bold tabular-nums', stats.current_drawdown_pct <= stats.max_drawdown_pct * 0.7 ? 'text-emerald-400' : 'text-rose-400')}>
              {stats.current_drawdown_pct.toFixed(1)}%
            </span>
            <span className="text-sm text-zinc-600">/ {stats.max_drawdown_pct.toFixed(1)}%</span>
          </div>
          <Progress
            value={Math.min((stats.current_drawdown_pct / stats.max_drawdown_pct) * 100, 100)}
            className="h-2"
          />
          <span className="text-[10px] text-zinc-600 font-mono mt-1 block">
            {(100 - (stats.current_drawdown_pct / stats.max_drawdown_pct) * 100).toFixed(1)}% safe
          </span>
        </div>
      </div>

      {/* Completion Checklist */}
      <div className="grid grid-cols-2 gap-4">
        <div className="tv-card p-4">
          <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold block mb-3">
            Phase Completion Checklist
          </span>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500">Profit Target</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-300">
                  ${stats.current_profit.toFixed(2)} / ${stats.profit_target.toFixed(0)}
                </span>
                {stats.rules_passed.profit_target ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Lock className="w-4 h-4 text-zinc-600" />
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500">Min Trading Days</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-300">
                  {stats.actual_trading_days} / {stats.min_trading_days}
                </span>
                {stats.rules_passed.min_trading_days ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Lock className="w-4 h-4 text-zinc-600" />
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500">Max Daily Loss</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-300">OK</span>
                {stats.rules_passed.max_daily_loss ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500">Max Drawdown</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-300">OK</span>
                {stats.rules_passed.max_drawdown ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500">Consistency</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-zinc-300">
                  {stats.consistency_pct.toFixed(0)}% / {stats.consistency_target_pct.toFixed(0)}%
                </span>
                {stats.rules_passed.consistency ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                )}
              </div>
            </div>
            {stats.can_upgrade && (
              <button className="w-full mt-3 px-4 py-2 bg-emerald-500/20 text-emerald-400 rounded font-mono text-xs font-semibold hover:bg-emerald-500/30 transition-colors flex items-center justify-center gap-2">
                <TrendingUp className="w-4 h-4" />
                UPGRADE TO {stats.phase === 'phase1' ? 'PHASE 2' : 'FUNDED'}
              </button>
            )}
          </div>
        </div>

        <div className="tv-card p-4">
          <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold block mb-3">
            Evaluation Stats
          </span>
          <div className="space-y-2 text-[11px]">
            <div className="flex justify-between">
              <span className="text-zinc-500">Trading Days</span>
              <span className="font-mono text-zinc-300">{stats.actual_trading_days} days</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Consistency</span>
              <span className="font-mono text-zinc-300">{stats.consistency_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Today PnL</span>
              <span className={cn('font-mono font-semibold', stats.today_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                ${stats.today_pnl.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Current Drawdown</span>
              <span className="font-mono text-zinc-300">{stats.current_drawdown_pct.toFixed(2)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Violations */}
      {stats.violations.length > 0 && (
        <div className="tv-card p-4 bg-rose-500/5 border border-rose-500/30">
          <span className="text-xs uppercase tracking-wider text-rose-400 font-semibold block mb-2">
            ⚠️ Rule Violations
          </span>
          <div className="space-y-1">
            {stats.violations.map((v, i) => (
              <div key={i} className="text-[11px] text-rose-300">
                • {v.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

#### 2. **Update Main Dashboard Page**
```tsx
// frontend/src/app/page.tsx
import { EvaluationDashboard } from '@/components/evaluation/EvaluationDashboard';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [activeMode, setActiveMode] = useState<TradingMode>('LIVE');
  const [showEvaluation, setShowEvaluation] = useState(true); // Toggle for evaluation view

  // ... existing code ...

  return (
    <div className="h-[calc(100vh-5rem)]">
      {/* Toggle between Normal Dashboard and Evaluation Dashboard */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold text-zinc-100">
          {showEvaluation ? 'Evaluation Dashboard' : 'Trading Dashboard'}
        </h1>
        <button
          onClick={() => setShowEvaluation(!showEvaluation)}
          className="px-3 py-1 bg-[#1e222d] text-zinc-400 rounded text-xs font-mono hover:bg-[#2a2e39] transition-colors"
        >
          {showEvaluation ? 'Switch to Trading View' : 'Switch to Evaluation View'}
        </button>
      </div>

      {showEvaluation ? (
        <EvaluationDashboard />
      ) : (
        // ... existing dashboard layout ...
      )}
    </div>
  );
}
```

---

## Summary

### What This Design Provides:

1. **Real-Time Phase Tracking**: See your progress towards Phase 2 or Funded status
2. **Rule Compliance Monitoring**: Visual indicators for all evaluation rules
3. **Violation Alerts**: Immediate warnings when approaching or breaching limits
4. **Consistency Tracking**: Monitor percentage of profitable days
5. **Upgrade Button**: When all rules are met, upgrade to next phase
6. **Dual Mode**: Toggle between evaluation view and normal trading view

### Next Steps:

1. **Run the migration**: `migrations/006_update_alert_rules_run_mode.sql`
2. **Add evaluation settings** to your `.env`
3. **Implement backend API** (`src/api_evaluation.py`)
4. **Create frontend component** (`EvaluationDashboard.tsx`)
5. **Configure your evaluation phase** in settings

Would you like me to generate the full implementation code for any of these components?
