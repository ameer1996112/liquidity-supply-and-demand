'use client';

import { useState, useCallback } from 'react';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Plus, Pencil, Trash2, Save, X, Loader2 } from 'lucide-react';
import {
  useSymbolRiskRulesSupabase,
  useCreateSymbolRiskRuleSupabase,
  useUpdateSymbolRiskRuleSupabase,
  useDeleteSymbolRiskRuleSupabase,
} from '@/hooks/useSymbolRiskRulesSupabase';
import type { SymbolRiskRule } from '@/types/rules';
import { cn } from '@/lib/utils';

type EditingRow = Partial<SymbolRiskRule> & { symbol: string };
const EMPTY: EditingRow = {
  symbol: '',
  risk_percent: 1,
  max_lot_size: 1,
  pip_size: 0.0001,
  pip_value_per_lot: 10,
  max_positions: 3,
  enabled: true,
};

export function SymbolOverrideTable() {
  const { data: rules = [], isLoading, error } = useSymbolRiskRulesSupabase();
  const createRule = useCreateSymbolRiskRuleSupabase();
  const updateRule = useUpdateSymbolRiskRuleSupabase();
  const deleteRule = useDeleteSymbolRiskRuleSupabase();

  const [adding, setAdding] = useState(false);
  const [editSymbol, setEditSymbol] = useState<string | null>(null);
  const [editRow, setEditRow] = useState<EditingRow>(EMPTY);

  const startAdd = useCallback(() => {
    setAdding(true);
    setEditSymbol(null);
    setEditRow({ ...EMPTY });
  }, []);

  const cancelAdd = useCallback(() => {
    setAdding(false);
    setEditRow(EMPTY);
  }, []);

  const startEdit = useCallback((rule: SymbolRiskRule) => {
    setAdding(false);
    setEditSymbol(rule.symbol);
    setEditRow({
      symbol: rule.symbol,
      risk_percent: rule.risk_percent,
      max_lot_size: rule.max_lot_size,
      pip_size: rule.pip_size,
      pip_value_per_lot: rule.pip_value_per_lot,
      max_positions: rule.max_positions,
      enabled: rule.enabled,
    });
  }, []);

  const cancelEdit = useCallback(() => {
    setEditSymbol(null);
    setEditRow(EMPTY);
  }, []);

  const saveNew = useCallback(async () => {
    const symbol = (editRow.symbol ?? '').trim().toUpperCase();
    if (!symbol) return;
    try {
      await createRule.mutateAsync({
        symbol,
        risk_percent: editRow.risk_percent ?? 1,
        max_lot_size: editRow.max_lot_size ?? 1,
        pip_size: editRow.pip_size ?? 0.0001,
        pip_value_per_lot: editRow.pip_value_per_lot ?? 10,
        max_positions: editRow.max_positions ?? 3,
        enabled: editRow.enabled ?? true,
      });
      cancelAdd();
    } catch {
      // Error handled by mutation
    }
  }, [editRow, createRule, cancelAdd]);

  const saveEdit = useCallback(async () => {
    if (!editSymbol) return;
    try {
      await updateRule.mutateAsync({
        symbol: editSymbol,
        updates: {
          risk_percent: editRow.risk_percent,
          max_lot_size: editRow.max_lot_size,
          pip_size: editRow.pip_size,
          pip_value_per_lot: editRow.pip_value_per_lot,
          max_positions: editRow.max_positions,
          enabled: editRow.enabled,
        },
      });
      cancelEdit();
    } catch {
      //
    }
  }, [editSymbol, editRow, updateRule, cancelEdit]);

  const remove = useCallback(
    async (symbol: string) => {
      if (!confirm(`Remove override for ${symbol}?`)) return;
      try {
        await deleteRule.mutateAsync(symbol);
      } catch {
        //
      }
    },
    [deleteRule]
  );

  if (isLoading) {
    return (
      <div className="rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 p-8 text-center text-[var(--to-text-dim)] text-sm">
        Loading symbol overrides…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-amber-600 text-sm">
        Failed to load symbol overrides. Ensure Supabase is configured.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-mono text-[var(--to-text-dim)] uppercase tracking-wider">
          Per-symbol risk & leverage
        </p>
        {!adding && !editSymbol && (
          <Button
            variant="outline"
            size="xs"
            onClick={startAdd}
            className="border-[#2a2e39] bg-[#1e222d] text-[var(--to-text-secondary)] hover:bg-[#2a2e39]"
          >
            <Plus className="h-3 w-3" />
            Add override
          </Button>
        )}
      </div>

      <div className="rounded-lg border border-[#2a2e39] overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-[#2a2e39] hover:bg-transparent">
              <TableHead className="text-[var(--to-text-dim)] font-mono text-[11px]">
                Symbol
              </TableHead>
              <TableHead className="text-[var(--to-text-dim)] font-mono text-[11px]">
                Risk %
              </TableHead>
              <TableHead className="text-[var(--to-text-dim)] font-mono text-[11px]">
                Max lot
              </TableHead>
              <TableHead className="text-[var(--to-text-dim)] font-mono text-[11px]">
                Max pos
              </TableHead>
              <TableHead className="text-[var(--to-text-dim)] font-mono text-[11px]">
                Status
              </TableHead>
              <TableHead className="w-[100px] text-right text-[var(--to-text-dim)] font-mono text-[11px]">
                Actions
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {adding && (
              <TableRow className="border-[#2a2e39] bg-[#1e222d]/50">
                <TableCell>
                  <input
                    type="text"
                    placeholder="e.g. XAUUSD"
                    value={editRow.symbol}
                    onChange={(e) =>
                      setEditRow((r) => ({ ...r, symbol: e.target.value }))
                    }
                    className="w-24 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                  />
                </TableCell>
                <TableCell>
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    value={editRow.risk_percent ?? 1}
                    onChange={(e) =>
                      setEditRow((r) => ({
                        ...r,
                        risk_percent: parseFloat(e.target.value) || 1,
                      }))
                    }
                    className="w-16 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                  />
                </TableCell>
                <TableCell>
                  <input
                    type="number"
                    min={0.01}
                    step={0.01}
                    value={editRow.max_lot_size ?? 1}
                    onChange={(e) =>
                      setEditRow((r) => ({
                        ...r,
                        max_lot_size: parseFloat(e.target.value) || 1,
                      }))
                    }
                    className="w-16 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                  />
                </TableCell>
                <TableCell>
                  <input
                    type="number"
                    min={1}
                    value={editRow.max_positions ?? 3}
                    onChange={(e) =>
                      setEditRow((r) => ({
                        ...r,
                        max_positions: parseInt(e.target.value, 10) || 3,
                      }))
                    }
                    className="w-14 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                  />
                </TableCell>
                <TableCell>-</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      onClick={saveNew}
                      disabled={
                        !(editRow.symbol ?? '').trim() || createRule.isPending
                      }
                    >
                      {createRule.isPending ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Save className="h-3 w-3 text-[var(--to-long)]" />
                      )}
                    </Button>
                    <Button size="icon-xs" variant="ghost" onClick={cancelAdd}>
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {rules.map((rule) => {
              const isEditing = editSymbol === rule.symbol;
              const row = isEditing ? editRow : rule;

              return (
                <TableRow
                  key={rule.symbol}
                  className="border-[#2a2e39] hover:bg-[#1e222d]/50"
                >
                  <TableCell className="font-mono text-xs text-[var(--to-text-primary)]">
                    {isEditing ? (
                      <input
                        type="text"
                        value={row.symbol}
                        readOnly
                        className="w-24 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-dim)]"
                      />
                    ) : (
                      rule.symbol
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-[var(--to-text-secondary)]">
                    {isEditing ? (
                      <input
                        type="number"
                        min={0.1}
                        max={10}
                        step={0.1}
                        value={row.risk_percent ?? 1}
                        onChange={(e) =>
                          setEditRow((r) => ({
                            ...r,
                            risk_percent:
                              parseFloat(e.target.value) || 1,
                          }))
                        }
                        className="w-16 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                      />
                    ) : (
                      `${rule.risk_percent}%`
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-[var(--to-text-secondary)]">
                    {isEditing ? (
                      <input
                        type="number"
                        min={0.01}
                        step={0.01}
                        value={row.max_lot_size ?? 1}
                        onChange={(e) =>
                          setEditRow((r) => ({
                            ...r,
                            max_lot_size:
                              parseFloat(e.target.value) || 1,
                          }))
                        }
                        className="w-16 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                      />
                    ) : (
                      rule.max_lot_size
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-[var(--to-text-secondary)]">
                    {isEditing ? (
                      <input
                        type="number"
                        min={1}
                        value={row.max_positions ?? 3}
                        onChange={(e) =>
                          setEditRow((r) => ({
                            ...r,
                            max_positions:
                              parseInt(e.target.value, 10) || 3,
                          }))
                        }
                        className="w-14 rounded border border-[#2a2e39] bg-[#0f1117] px-2 py-1 font-mono text-xs text-[var(--to-text-primary)]"
                      />
                    ) : (
                      rule.max_positions
                    )}
                  </TableCell>
                  <TableCell>
                    {rule.enabled ? (
                      <Badge className="bg-[var(--to-long)]/20 text-[var(--to-long)] text-[10px]">
                        On
                      </Badge>
                    ) : (
                      <Badge className="bg-[var(--to-surface-raised)]/30 text-[var(--to-text-dim)] text-[10px]">
                        Off
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {isEditing ? (
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={saveEdit}
                          disabled={updateRule.isPending}
                        >
                          {updateRule.isPending ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Save className="h-3 w-3 text-[var(--to-long)]" />
                          )}
                        </Button>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={cancelEdit}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={() => startEdit(rule)}
                          className="text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]"
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          onClick={() => remove(rule.symbol)}
                          disabled={deleteRule.isPending}
                          className="text-[var(--to-text-dim)] hover:text-[var(--to-short)]"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {rules.length === 0 && !adding && (
        <p className="py-4 text-center text-xs text-[var(--to-text-dim)]">
          No symbol overrides. Add one to set custom risk or leverage per pair.
        </p>
      )}
    </div>
  );
}
