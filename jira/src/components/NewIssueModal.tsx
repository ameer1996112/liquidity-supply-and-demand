'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type IssueType, type IssuePriority } from '@/lib/types';
import { createIssue } from '@/lib/supabase';

interface Props {
  onClose: () => void;
  onCreated: (issue: unknown) => void;
  sprints?: { id: number; name: string }[];
}

export function NewIssueModal({ onClose, onCreated, sprints = [] }: Props) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    type: 'task' as IssueType,
    priority: 'medium' as IssuePriority,
    story_points: '',
    signal_id: '',
    sprint_id: '',
    labels: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const field = <K extends keyof typeof form>(key: K) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setIsSubmitting(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        type: form.type,
        priority: form.priority,
        labels: form.labels ? form.labels.split(',').map((l) => l.trim()).filter(Boolean) : [],
        ai_changelog: [],
        rank: Date.now(),
      };
      if (form.story_points) payload.story_points = parseInt(form.story_points, 10);
      if (form.signal_id) payload.signal_id = parseInt(form.signal_id, 10);
      if (form.sprint_id) payload.sprint_id = parseInt(form.sprint_id, 10);

      const created = await createIssue(payload);
      onCreated(created);
      onClose();
    } catch (err) {
      setError(String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputCls = 'w-full rounded border border-[#1f2335] bg-[#0d0f14] px-3 py-2 text-[12px] text-[#e2e8f0] placeholder:text-[#475569] outline-none focus:border-amber-500/30 font-sans';
  const selectCls = 'w-full rounded border border-[#1f2335] bg-[#0d0f14] px-3 py-2 text-[11px] font-mono text-[#e2e8f0] outline-none focus:border-amber-500/30';
  const labelCls = 'block text-[9px] font-mono uppercase tracking-widest text-[#475569] mb-1';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-[#1f2335] bg-[#13161e] shadow-2xl p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[13px] font-bold font-mono text-[#e2e8f0]">New Issue</h2>
          <button onClick={onClose} className="text-[#475569] hover:text-[#94a3b8]"><X className="h-4 w-4" /></button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className={labelCls}>Title *</label>
            <input autoFocus {...field('title')} placeholder="Short descriptive title…" className={inputCls} required />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={labelCls}>Type</label>
              <select {...field('type')} className={selectCls}>
                <option value="task">Task</option>
                <option value="bug">Bug</option>
                <option value="feature">Feature</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Priority</label>
              <select {...field('priority')} className={selectCls}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Points</label>
              <input type="number" {...field('story_points')} placeholder="SP" className={inputCls} min="0" max="99" />
            </div>
          </div>

          {sprints.length > 0 && (
            <div>
              <label className={labelCls}>Sprint</label>
              <select {...field('sprint_id')} className={selectCls}>
                <option value="">No sprint</option>
                {sprints.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className={labelCls}>Labels (comma separated)</label>
            <input {...field('labels')} placeholder="frontend, api, trading…" className={inputCls} />
          </div>

          <div>
            <label className={labelCls}>Description</label>
            <textarea {...field('description')} placeholder="Add context, steps to reproduce, or acceptance criteria…" rows={3} className={cn(inputCls, 'resize-none')} />
          </div>

          <div>
            <label className={labelCls}>Link to Signal ID (optional)</label>
            <input type="number" {...field('signal_id')} placeholder="e.g. 206" className={inputCls} />
          </div>

          {error && <p className="text-[10px] font-mono text-rose-400">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded border border-[#1f2335] text-[11px] font-mono text-[#475569] hover:text-[#94a3b8] transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={isSubmitting || !form.title.trim()}
              className="flex-1 py-2 rounded border border-amber-500/40 bg-amber-500/10 text-[11px] font-mono font-semibold text-amber-400 hover:bg-amber-500/15 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? 'Creating…' : 'Create Issue'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
