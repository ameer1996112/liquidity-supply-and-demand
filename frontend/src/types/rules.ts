export interface SymbolRiskRule {
  id?: string;
  symbol: string;
  max_lot_size: number;
  min_lot_size: number;
  lot_step: number;
  risk_percent: number;
  pip_size: number;
  pip_value_per_lot: number;
  stop_loss_buffer_pips: number;
  max_positions: number;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface StrategyRule {
  id: string;
  content: string;
  metadata: Record<string, string>;
  embedding?: number[];
  created_at?: string;
}
