'use client';

import { useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { SymbolRiskRule } from '@/types/rules';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import {
  Pencil,
  Trash2,
  Plus,
  Save,
  X,
  Loader2,
} from 'lucide-react';

type EditingRow = Omit<SymbolRiskRule, 'id' | 'created_at' | 'updated_at'>;

type SymbolRulesResponse = { rules: SymbolRiskRule[]; count: number };
type SymbolRuleResponse = { rule: SymbolRiskRule };

const EMPTY_ROW: EditingRow = {
  symbol: '',
  max_lot_size: 1.0,
  min_lot_size: 0.01,
  lot_step: 0.01,
  risk_percent: 1.0,
  pip_size: 0.0001,
  pip_value_per_lot: 10.0,
  stop_loss_buffer_pips: 1.0,
  max_positions: 3,
  enabled: true,
};

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || 'Request failed');
  }

  return payload as T;
}

export function RiskRulesPanel() {
  const [rules, setRules] = useState<SymbolRiskRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [editRow, setEditRow] = useState<EditingRow>(EMPTY_ROW);
  const [addingNew, setAddingNew] = useState(false);
  const [error, setError] = useState('');

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await requestJson<SymbolRulesResponse>('/api/rules/symbols');
      setRules(payload.rules || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  const startEdit = (rule: SymbolRiskRule) => {
    setEditId(rule.id ?? rule.symbol);
    setEditRow({
      symbol: rule.symbol,
      max_lot_size: rule.max_lot_size,
      min_lot_size: rule.min_lot_size,
      lot_step: rule.lot_step,
      risk_percent: rule.risk_percent,
      pip_size: rule.pip_size,
      pip_value_per_lot: rule.pip_value_per_lot,
      stop_loss_buffer_pips: rule.stop_loss_buffer_pips,
      max_positions: rule.max_positions,
      enabled: rule.enabled,
    });
    setAddingNew(false);
  };

  const cancelEdit = () => {
    setEditId(null);
    setAddingNew(false);
    setEditRow(EMPTY_ROW);
  };

  const saveEdit = async () => {
    setSaving(true);
    setError('');
    const payload = {
      symbol: editRow.symbol.toUpperCase().trim(),
      max_lot_size: editRow.max_lot_size,
      min_lot_size: editRow.min_lot_size,
      lot_step: editRow.lot_step,
      risk_percent: editRow.risk_percent,
      pip_size: editRow.pip_size,
      pip_value_per_lot: editRow.pip_value_per_lot,
      stop_loss_buffer_pips: editRow.stop_loss_buffer_pips,
      max_positions: editRow.max_positions,
      enabled: editRow.enabled,
    };

    try {
      if (addingNew) {
        await requestJson<SymbolRuleResponse>('/api/rules/symbols', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      } else if (editId) {
        await requestJson<SymbolRuleResponse>(`/api/rules/symbols/${encodeURIComponent(payload.symbol)}`, {
          method: 'PUT',
          body: JSON.stringify({
            max_lot_size: payload.max_lot_size,
            min_lot_size: payload.min_lot_size,
            lot_step: payload.lot_step,
            risk_percent: payload.risk_percent,
            pip_size: payload.pip_size,
            pip_value_per_lot: payload.pip_value_per_lot,
            stop_loss_buffer_pips: payload.stop_loss_buffer_pips,
            max_positions: payload.max_positions,
            enabled: payload.enabled,
          }),
        });
      }
      cancelEdit();
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteRule = async (symbol: string) => {
    if (!confirm(`Delete risk rules for ${symbol}?`)) return;
    setError('');
    try {
      await requestJson<{ status: string }>(`/api/rules/symbols/${encodeURIComponent(symbol)}`, {
        method: 'DELETE',
      });
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const toggleEnabled = async (rule: SymbolRiskRule) => {
    try {
      await requestJson<SymbolRuleResponse>(`/api/rules/symbols/${encodeURIComponent(rule.symbol)}`, {
        method: 'PUT',
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Toggle failed');
    }
  };

  const inputCls =
    'bg-[#1e222d] border border-[#2a2e39] rounded px-2 py-1 text-xs font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-emerald-500 w-full';

  const renderEditableRow = (symbolLocked: boolean) => (
    <>
      <TableCell>
        {symbolLocked ? (
          <span className="text-xs font-mono text-[var(--to-text-primary)]">{editRow.symbol}</span>
        ) : (
          <input
            aria-label="Symbol"
            value={editRow.symbol}
            onChange={(e) => setEditRow({ ...editRow, symbol: e.target.value.toUpperCase() })}
            placeholder="XAUUSD"
            className={inputCls}
            style={{ width: 90 }}
          />
        )}
      </TableCell>
      <TableCell>
        <input
          aria-label="Max Lot"
          type="number"
          step="0.01"
          value={editRow.max_lot_size}
          onChange={(e) => setEditRow({ ...editRow, max_lot_size: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 72 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="Min Lot"
          type="number"
          step="0.01"
          value={editRow.min_lot_size}
          onChange={(e) => setEditRow({ ...editRow, min_lot_size: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 72 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="Lot Step"
          type="number"
          step="0.01"
          value={editRow.lot_step}
          onChange={(e) => setEditRow({ ...editRow, lot_step: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 72 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="Risk Percent"
          type="number"
          step="0.1"
          value={editRow.risk_percent}
          onChange={(e) => setEditRow({ ...editRow, risk_percent: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 64 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="Pip Size"
          type="number"
          step="0.0001"
          value={editRow.pip_size}
          onChange={(e) => setEditRow({ ...editRow, pip_size: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 82 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="Pip Value Per Lot"
          type="number"
          step="0.01"
          value={editRow.pip_value_per_lot}
          onChange={(e) => setEditRow({ ...editRow, pip_value_per_lot: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 82 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="SL Buffer Pips"
          type="number"
          step="0.1"
          value={editRow.stop_loss_buffer_pips}
          onChange={(e) => setEditRow({ ...editRow, stop_loss_buffer_pips: parseFloat(e.target.value) || 0 })}
          className={inputCls}
          style={{ width: 82 }}
        />
      </TableCell>
      <TableCell>
        <input
          aria-label="Max Positions"
          type="number"
          step="1"
          value={editRow.max_positions}
          onChange={(e) => setEditRow({ ...editRow, max_positions: parseInt(e.target.value, 10) || 1 })}
          className={inputCls}
          style={{ width: 52 }}
        />
      </TableCell>
      <TableCell>
        <button
          aria-label="Enabled"
          onClick={() => setEditRow({ ...editRow, enabled: !editRow.enabled })}
          className={cn(
            'w-8 h-4 rounded-full relative transition-colors',
            editRow.enabled ? 'bg-emerald-500' : 'bg-[var(--to-surface-raised)]'
          )}
        >
          <span
            className={cn(
              'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform',
              editRow.enabled ? 'left-4' : 'left-0.5'
            )}
          />
        </button>
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          <button
            aria-label="Save rule"
            onClick={saveEdit}
            disabled={saving || !editRow.symbol.trim()}
            className="p-1 text-[var(--to-long)] hover:text-emerald-300 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          </button>
          <button
            aria-label="Cancel edit"
            onClick={cancelEdit}
            className="p-1 text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </TableCell>
    </>
  );

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-[var(--to-short)]/10 border border-[var(--to-short)]/30 rounded-lg px-4 py-2 text-[var(--to-short)] text-xs font-mono">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--to-text-dim)] font-mono uppercase tracking-wider">
              Per-Symbol Risk Configuration
            </span>
            <Badge variant="secondary" className="text-[10px]">
              {rules.length} symbols
            </Badge>
          </div>
          <p className="text-[11px] text-[var(--to-text-dim)]">
            Backend calculates final position size at execution time from these rules.
          </p>
        </div>
        <button
          onClick={() => {
            setAddingNew(true);
            setEditId('__new__');
            setEditRow(EMPTY_ROW);
          }}
          disabled={addingNew}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono',
            'bg-[var(--to-long)]/10 text-[var(--to-long)] hover:bg-[var(--to-long)]/20 transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Plus className="w-3.5 h-3.5" />
          Add Symbol
        </button>
      </div>

      <div className="glow-card overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-[var(--to-text-dim)]" />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-[#2a2e39]">
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Symbol</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Max Lot</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Min Lot</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Lot Step</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Risk %</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Pip Size</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Pip Value/Lot</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">SL Buffer</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Max Pos</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase">Enabled</TableHead>
                <TableHead className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {addingNew && (
                <TableRow className="border-[#2a2e39] bg-emerald-500/5">
                  {renderEditableRow(false)}
                </TableRow>
              )}

              {rules.map((rule) =>
                editId === (rule.id ?? rule.symbol) ? (
                  <TableRow key={rule.id ?? rule.symbol} className="border-[#2a2e39] bg-blue-500/5">
                    {renderEditableRow(true)}
                  </TableRow>
                ) : (
                  <TableRow key={rule.id ?? rule.symbol} className="border-[#2a2e39]">
                    <TableCell className="text-xs font-mono text-[var(--to-text-primary)] font-semibold">
                      {rule.symbol}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.max_lot_size}</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.min_lot_size}</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.lot_step}</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.risk_percent}%</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.pip_size}</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">${rule.pip_value_per_lot}</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.stop_loss_buffer_pips}</TableCell>
                    <TableCell className="text-xs font-mono text-[var(--to-text-dim)]">{rule.max_positions}</TableCell>
                    <TableCell>
                      <button
                        aria-label={`Toggle ${rule.symbol}`}
                        onClick={() => toggleEnabled(rule)}
                        className={cn(
                          'w-8 h-4 rounded-full relative transition-colors',
                          rule.enabled ? 'bg-emerald-500' : 'bg-[var(--to-surface-raised)]'
                        )}
                      >
                        <span
                          className={cn(
                            'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform',
                            rule.enabled ? 'left-4' : 'left-0.5'
                          )}
                        />
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          aria-label={`Edit ${rule.symbol}`}
                          onClick={() => startEdit(rule)}
                          className="p-1 text-[var(--to-text-dim)] hover:text-blue-400 transition-colors"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          aria-label={`Delete ${rule.symbol}`}
                          onClick={() => deleteRule(rule.symbol)}
                          className="p-1 text-[var(--to-text-dim)] hover:text-[var(--to-short)] transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              )}
              {rules.length === 0 && !addingNew && (
                <TableRow className="border-[#2a2e39]">
                  <TableCell colSpan={11} className="text-center text-[var(--to-text-dim)] text-xs py-8">
                    No symbol rules configured. Click &quot;Add Symbol&quot; to create one.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
