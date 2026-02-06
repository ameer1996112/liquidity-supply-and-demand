'use client';

import { useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { supabase } from '@/lib/supabase';

// Untyped accessor for tables not in the Database generic
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any;
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

const EMPTY_ROW: EditingRow = {
  symbol: '',
  max_lot_size: 1.0,
  risk_percent: 1.0,
  pip_size: 0.0001,
  pip_value_per_lot: 10.0,
  max_positions: 3,
  enabled: true,
};

export function RiskRulesPanel() {
  const [rules, setRules] = useState<SymbolRiskRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [editRow, setEditRow] = useState<EditingRow>(EMPTY_ROW);
  const [addingNew, setAddingNew] = useState(false);
  const [error, setError] = useState('');

  const fetchRules = useCallback(async () => {
    if (!supabase) return;
    setLoading(true);
    setError('');
    try {
      const { data, error: err } = await db
        .from('symbol_risk_rules')
        .select('*')
        .order('symbol', { ascending: true });
      if (err) throw err;
      setRules((data as SymbolRiskRule[]) || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const startEdit = (rule: SymbolRiskRule) => {
    setEditId(rule.id);
    setEditRow({
      symbol: rule.symbol,
      max_lot_size: rule.max_lot_size,
      risk_percent: rule.risk_percent,
      pip_size: rule.pip_size,
      pip_value_per_lot: rule.pip_value_per_lot,
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
    if (!supabase) return;
    setSaving(true);
    setError('');
    try {
      if (addingNew) {
        const { error: err } = await db
          .from('symbol_risk_rules')
          .insert({
            symbol: editRow.symbol.toUpperCase().trim(),
            max_lot_size: editRow.max_lot_size,
            risk_percent: editRow.risk_percent,
            pip_size: editRow.pip_size,
            pip_value_per_lot: editRow.pip_value_per_lot,
            max_positions: editRow.max_positions,
            enabled: editRow.enabled,
          });
        if (err) throw err;
      } else if (editId) {
        const { error: err } = await db
          .from('symbol_risk_rules')
          .update({
            max_lot_size: editRow.max_lot_size,
            risk_percent: editRow.risk_percent,
            pip_size: editRow.pip_size,
            pip_value_per_lot: editRow.pip_value_per_lot,
            max_positions: editRow.max_positions,
            enabled: editRow.enabled,
            updated_at: new Date().toISOString(),
          })
          .eq('id', editId);
        if (err) throw err;
      }
      cancelEdit();
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteRule = async (id: string, symbol: string) => {
    if (!supabase) return;
    if (!confirm(`Delete risk rules for ${symbol}?`)) return;
    setError('');
    try {
      const { error: err } = await db
        .from('symbol_risk_rules')
        .delete()
        .eq('id', id);
      if (err) throw err;
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const toggleEnabled = async (rule: SymbolRiskRule) => {
    if (!supabase) return;
    try {
      const { error: err } = await db
        .from('symbol_risk_rules')
        .update({ enabled: !rule.enabled, updated_at: new Date().toISOString() })
        .eq('id', rule.id);
      if (err) throw err;
      await fetchRules();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Toggle failed');
    }
  };

  const inputCls =
    'bg-[#1e222d] border border-[#2a2e39] rounded px-2 py-1 text-xs font-mono text-zinc-200 focus:outline-none focus:border-emerald-500 w-full';

  if (!supabase) {
    return (
      <div className="tv-card p-6 text-center text-zinc-500 text-sm">
        Supabase not configured. Set environment variables to manage rules.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-red-400 text-xs font-mono">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 font-mono uppercase tracking-wider">
            Per-Symbol Risk Configuration
          </span>
          <Badge variant="secondary" className="text-[10px]">
            {rules.length} symbols
          </Badge>
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
            'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Plus className="w-3.5 h-3.5" />
          Add Symbol
        </button>
      </div>

      <div className="tv-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-[#2a2e39]">
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Symbol</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Max Lot</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Risk %</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Pip Size</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Pip Value/Lot</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Max Pos</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase">Enabled</TableHead>
                <TableHead className="text-[10px] text-zinc-500 font-mono uppercase text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {addingNew && (
                <TableRow className="border-[#2a2e39] bg-emerald-500/5">
                  <TableCell>
                    <input
                      value={editRow.symbol}
                      onChange={(e) => setEditRow({ ...editRow, symbol: e.target.value })}
                      placeholder="XAUUSD"
                      className={inputCls}
                      style={{ width: 90 }}
                    />
                  </TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="0.01"
                      value={editRow.max_lot_size}
                      onChange={(e) => setEditRow({ ...editRow, max_lot_size: parseFloat(e.target.value) || 0 })}
                      className={inputCls}
                      style={{ width: 70 }}
                    />
                  </TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="0.1"
                      value={editRow.risk_percent}
                      onChange={(e) => setEditRow({ ...editRow, risk_percent: parseFloat(e.target.value) || 0 })}
                      className={inputCls}
                      style={{ width: 60 }}
                    />
                  </TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="0.0001"
                      value={editRow.pip_size}
                      onChange={(e) => setEditRow({ ...editRow, pip_size: parseFloat(e.target.value) || 0 })}
                      className={inputCls}
                      style={{ width: 80 }}
                    />
                  </TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="1"
                      value={editRow.pip_value_per_lot}
                      onChange={(e) => setEditRow({ ...editRow, pip_value_per_lot: parseFloat(e.target.value) || 0 })}
                      className={inputCls}
                      style={{ width: 80 }}
                    />
                  </TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="1"
                      value={editRow.max_positions}
                      onChange={(e) => setEditRow({ ...editRow, max_positions: parseInt(e.target.value) || 1 })}
                      className={inputCls}
                      style={{ width: 50 }}
                    />
                  </TableCell>
                  <TableCell>
                    <button
                      onClick={() => setEditRow({ ...editRow, enabled: !editRow.enabled })}
                      className={cn(
                        'w-8 h-4 rounded-full relative transition-colors',
                        editRow.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
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
                        onClick={saveEdit}
                        disabled={saving || !editRow.symbol.trim()}
                        className="p-1 text-emerald-400 hover:text-emerald-300 disabled:opacity-50"
                      >
                        {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                      </button>
                      <button onClick={cancelEdit} className="p-1 text-zinc-500 hover:text-zinc-300">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {rules.map((rule) =>
                editId === rule.id ? (
                  <TableRow key={rule.id} className="border-[#2a2e39] bg-blue-500/5">
                    <TableCell>
                      <span className="text-xs font-mono text-zinc-200">{rule.symbol}</span>
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        step="0.01"
                        value={editRow.max_lot_size}
                        onChange={(e) => setEditRow({ ...editRow, max_lot_size: parseFloat(e.target.value) || 0 })}
                        className={inputCls}
                        style={{ width: 70 }}
                      />
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        step="0.1"
                        value={editRow.risk_percent}
                        onChange={(e) => setEditRow({ ...editRow, risk_percent: parseFloat(e.target.value) || 0 })}
                        className={inputCls}
                        style={{ width: 60 }}
                      />
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        step="0.0001"
                        value={editRow.pip_size}
                        onChange={(e) => setEditRow({ ...editRow, pip_size: parseFloat(e.target.value) || 0 })}
                        className={inputCls}
                        style={{ width: 80 }}
                      />
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        step="1"
                        value={editRow.pip_value_per_lot}
                        onChange={(e) => setEditRow({ ...editRow, pip_value_per_lot: parseFloat(e.target.value) || 0 })}
                        className={inputCls}
                        style={{ width: 80 }}
                      />
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        step="1"
                        value={editRow.max_positions}
                        onChange={(e) => setEditRow({ ...editRow, max_positions: parseInt(e.target.value) || 1 })}
                        className={inputCls}
                        style={{ width: 50 }}
                      />
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={() => setEditRow({ ...editRow, enabled: !editRow.enabled })}
                        className={cn(
                          'w-8 h-4 rounded-full relative transition-colors',
                          editRow.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
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
                          onClick={saveEdit}
                          disabled={saving}
                          className="p-1 text-emerald-400 hover:text-emerald-300 disabled:opacity-50"
                        >
                          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                        </button>
                        <button onClick={cancelEdit} className="p-1 text-zinc-500 hover:text-zinc-300">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  <TableRow key={rule.id} className="border-[#2a2e39]">
                    <TableCell className="text-xs font-mono text-zinc-200 font-semibold">
                      {rule.symbol}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-zinc-400">{rule.max_lot_size}</TableCell>
                    <TableCell className="text-xs font-mono text-zinc-400">{rule.risk_percent}%</TableCell>
                    <TableCell className="text-xs font-mono text-zinc-400">{rule.pip_size}</TableCell>
                    <TableCell className="text-xs font-mono text-zinc-400">${rule.pip_value_per_lot}</TableCell>
                    <TableCell className="text-xs font-mono text-zinc-400">{rule.max_positions}</TableCell>
                    <TableCell>
                      <button
                        onClick={() => toggleEnabled(rule)}
                        className={cn(
                          'w-8 h-4 rounded-full relative transition-colors',
                          rule.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
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
                          onClick={() => startEdit(rule)}
                          className="p-1 text-zinc-500 hover:text-blue-400 transition-colors"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => deleteRule(rule.id, rule.symbol)}
                          className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
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
                  <TableCell colSpan={8} className="text-center text-zinc-500 text-xs py-8">
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
