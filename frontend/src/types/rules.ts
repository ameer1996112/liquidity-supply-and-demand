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

export interface SymbolRiskRuleSuggestion {
  id?: number;
  symbol: string;
  suggested_risk_percent: number;
  suggested_max_lot_size: number;
  suggested_pip_size: number;
  suggested_pip_value_per_lot: number;
  status: 'pending' | 'approved' | 'rejected' | 'superseded';
  optimizer_run_id?: string;
  created_at?: string;
  approved_at?: string;
  approved_by?: string;
  source_payload?: Record<string, unknown>;
}

export interface SymbolRiskRuleReviewRow {
  symbol: string;
  active_rule?: SymbolRiskRule | null;
  latest_suggestion?: SymbolRiskRuleSuggestion | null;
  suggestion_status?: string | null;
  has_pending_changes: boolean;
}

export interface StrategyRule {
  id: string;
  content: string;
  metadata: Record<string, string>;
  embedding?: number[];
  created_at?: string;
}
