import { TradingSignal, getSymbol, getSide, getScore, getPnl } from '@/types/trading';
import { format } from 'date-fns';

export function exportTradesToCsv(signals: TradingSignal[], filename?: string) {
  const SESSION_LABELS: Record<number, string> = { 0: 'Asia', 1: 'LDN', 2: 'NY', 3: 'Off' };

  const headers = [
    'Date',
    'Symbol',
    'Side',
    'Status',
    'Zone Type',
    'Zone Grade',
    'Entry Model',
    'Session',
    'Mode',
    'Entry',
    'Stop Loss',
    'Take Profit',
    'Exit Price',
    'Exit Type',
    'SL Pips',
    'R:R',
    'AI Score',
    'PnL ($)',
    'PnL (%)',
  ];

  const rows = signals.map((s) => [
    format(new Date(s.created_at), 'yyyy-MM-dd HH:mm:ss'),
    getSymbol(s),
    getSide(s).toUpperCase(),
    (s.status || '').toUpperCase(),
    s.zone_type ?? '',
    s.zone_grade ?? '',
    s.entry_model ?? '',
    s.session != null ? (SESSION_LABELS[s.session] || s.session) : '',
    s.mode || s.run_mode || '',
    s.price ?? s.entry ?? '',
    s.stop_loss ?? s.sl ?? '',
    s.take_profit ?? s.tp ?? '',
    s.exit_price ?? '',
    s.exit_type ?? '',
    s.sl_pips ?? '',
    s.rr_ratio ?? '',
    getScore(s) ?? '',
    getPnl(s) ?? '',
    s.pnl_percentage ?? '',
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map((row) =>
      row.map((cell) => {
        const str = String(cell);
        return str.includes(',') ? `"${str}"` : str;
      }).join(',')
    ),
  ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || `trades_${format(new Date(), 'yyyy-MM-dd')}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
