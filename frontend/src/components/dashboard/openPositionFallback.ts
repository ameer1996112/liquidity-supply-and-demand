import type { ActivePosition } from '@/hooks/usePositions';
import type { TradingSignal } from '@/types/trading';

const OPEN_SIGNAL_STATUSES = new Set(['open', 'active', 'executed', 'pending', 'spin']);

export function buildOpenPositionFallback(
  signals: TradingSignal[],
  nowMs: number = Date.now()
): ActivePosition[] {
  return signals
    .filter((signal) => {
      const status = String(signal.status || '').toLowerCase();
      if (!OPEN_SIGNAL_STATUSES.has(status)) return false;
      if (signal.closed_at || signal.exit_price != null) return false;
      if (status === 'executed' && !signal.broker_order_id && !signal.broker_profile_id) return false;
      return true;
    })
    .map((signal, index) => {
      const parsedId = Number(signal.id);
      const stableId = Number.isFinite(parsedId) ? parsedId : -(index + 1);
      const createdAt = signal.opened_at || signal.created_at || new Date(nowMs).toISOString();
      const openedAtMs = new Date(createdAt).getTime();
      const holdDurationSeconds = Number.isFinite(openedAtMs)
        ? Math.max(0, Math.floor((nowMs - openedAtMs) / 1000))
        : 0;

      return {
        id: stableId,
        account_name: signal.account_name?.trim() || 'Unassigned',
        broker_profile_id: signal.broker_profile_id ?? null,
        symbol: signal.symbol,
        side: signal.side,
        entry: signal.entry ?? signal.price ?? null,
        sl: signal.sl ?? signal.stop_loss ?? null,
        tp: signal.tp ?? signal.take_profit ?? null,
        size: signal.position_size ?? signal.size ?? 0,
        broker_order_id: signal.broker_order_id ?? null,
        current_price: null,
        live_pnl: signal.pnl_usd ?? signal.pnl ?? null,
        live_pnl_pct: signal.pnl_percentage ?? null,
        hold_duration_seconds: holdDurationSeconds,
        created_at: createdAt,
        zone_type: signal.zone_type ?? null,
        entry_model: signal.entry_model ?? null,
        rr_ratio: signal.rr_ratio ?? null,
        is_stale: false,
        broker_exists: true,
      };
    });
}
