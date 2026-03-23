'use client';

import { useEffect, useState } from 'react';
import { Plus, Tag } from 'lucide-react';
import { type Label } from '@/lib/types';
import { fetchLabels, createLabel } from '@/lib/supabase';

const PRESET_COLORS = [
  '#ef4444', '#f59e0b', '#10b981', '#3b82f6',
  '#8b5cf6', '#ec4899', '#06b6d4', '#475569',
];

export default function LabelsPage() {
  const [labels, setLabels] = useState<Label[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState('#3b82f6');
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    fetchLabels().then((l) => setLabels(l as Label[])).finally(() => setIsLoading(false));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setIsCreating(true);
    try {
      const label = await createLabel(newName.trim(), newColor);
      setLabels((prev) => [...prev, label as Label]);
      setNewName('');
      setShowNew(false);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between border-b border-[#1f2335] px-6 py-3 shrink-0">
        <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Labels</h1>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px] font-mono font-semibold text-amber-400 hover:bg-amber-500/15 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Label
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <p className="text-[11px] font-mono text-[#475569]">Loading…</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {labels.map((label) => (
              <div key={label.id} className="flex items-center gap-2.5 rounded-lg border border-[#1f2335] bg-[#13161e] px-3 py-2.5">
                <div className="h-3 w-3 rounded-full shrink-0" style={{ background: label.color }} />
                <span className="text-[12px] font-medium text-[#e2e8f0]">{label.name}</span>
              </div>
            ))}
            {showNew && (
              <form onSubmit={handleCreate} className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                <div className="relative shrink-0">
                  <div className="h-3 w-3 rounded-full cursor-pointer" style={{ background: newColor }} />
                  <input
                    type="color"
                    value={newColor}
                    onChange={(e) => setNewColor(e.target.value)}
                    className="absolute inset-0 opacity-0 cursor-pointer w-3 h-3"
                  />
                </div>
                <input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="label-name"
                  className="flex-1 bg-transparent text-[12px] text-[#e2e8f0] placeholder:text-[#475569] outline-none font-mono"
                />
                <button type="submit" disabled={isCreating || !newName.trim()} className="text-[9px] font-mono text-amber-400 disabled:opacity-40">Save</button>
              </form>
            )}
          </div>
        )}

        {/* Color presets */}
        {showNew && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[9px] font-mono text-[#475569]">Presets:</span>
            {PRESET_COLORS.map((c) => (
              <button key={c} onClick={() => setNewColor(c)} className="h-4 w-4 rounded-full border-2 transition-all" style={{ background: c, borderColor: newColor === c ? '#e2e8f0' : 'transparent' }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
