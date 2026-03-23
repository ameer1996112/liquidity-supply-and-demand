'use client';

import { useState } from 'react';
import { type Sprint } from '@/lib/types';
import { createSprint, updateSprint } from '@/lib/supabase';

interface Props {
  sprint?: Sprint; // if provided, edit mode
  onClose: () => void;
  onSaved: (sprint: Sprint) => void;
}

const inputCls = 'w-full rounded border border-[#1f2335] bg-[#0d0f14] px-3 py-2 text-[12px] text-[#e2e8f0] placeholder:text-[#475569] outline-none focus:border-amber-500/30';
const labelCls = 'block text-[9px] font-mono uppercase tracking-widest text-[#475569] mb-1';

export function NewSprintModal({ sprint, onClose, onSaved }: Props) {
  const isEdit = !!sprint;
  const [form, setForm] = useState({
    name: sprint?.name ?? '',
    goal: sprint?.goal ?? '',
    start_date: sprint?.start_date ?? '',
    end_date: sprint?.end_date ?? '',
  });
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        name: form.name,
        goal: form.goal || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      };
      const result = isEdit
        ? await updateSprint(sprint!.id, payload)
        : await createSprint({ ...payload, status: 'planned' });
      onSaved(result as Sprint);
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl border border-[#1f2335] bg-[#13161e] p-5 space-y-3 shadow-2xl"
      >
        <h2 className="text-[13px] font-bold font-mono text-[#e2e8f0]">
          {isEdit ? 'Edit Sprint' : 'New Sprint'}
        </h2>

        <div>
          <label className={labelCls}>Name *</label>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Sprint 1"
            className={inputCls}
            required
            autoFocus
          />
        </div>

        <div>
          <label className={labelCls}>Goal</label>
          <input
            value={form.goal}
            onChange={(e) => setForm((f) => ({ ...f, goal: e.target.value }))}
            placeholder="Ship sprint board MVP"
            className={inputCls}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Start date</label>
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>End date</label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
              className={inputCls}
            />
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2 rounded border border-[#1f2335] text-[11px] font-mono text-[#475569] hover:text-[#94a3b8] transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSaving || !form.name}
            className="flex-1 py-2 rounded border border-amber-500/40 bg-amber-500/10 text-[11px] font-mono font-semibold text-amber-400 disabled:opacity-50 hover:bg-amber-500/15 transition-colors"
          >
            {isSaving ? 'Saving…' : isEdit ? 'Save' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  );
}
