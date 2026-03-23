'use client';

import { useEffect, useState, useCallback } from 'react';
import { Plus, GitBranch, Play, CheckCircle, Clock, Target } from 'lucide-react';
import { cn, sprintDaysLeft } from '@/lib/utils';
import { type Sprint, type Issue } from '@/lib/types';
import { fetchSprints, fetchIssues, createSprint, updateSprint } from '@/lib/supabase';

const STATUS_CONFIG: Record<Sprint['status'], { label: string; icon: typeof Play; color: string }> = {
  planned:   { label: 'Planned',   icon: Clock,         color: '#475569' },
  active:    { label: 'Active',    icon: Play,          color: '#f59e0b' },
  completed: { label: 'Completed', icon: CheckCircle,   color: '#10b981' },
};

export default function SprintsPage() {
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ name: '', goal: '', start_date: '', end_date: '' });
  const [isCreating, setIsCreating] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [ss, is] = await Promise.all([fetchSprints(), fetchIssues()]);
      setSprints(ss as Sprint[]);
      setIssues(is as Issue[]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sprintIssues = (sprintId: number) => issues.filter((i) => i.sprint_id === sprintId);

  const burndown = (sprintId: number) => {
    const sis = sprintIssues(sprintId);
    const total = sis.length;
    const done = sis.filter((i) => i.status === 'done').length;
    const totalPts = sis.reduce((sum, i) => sum + (i.story_points ?? 0), 0);
    const donePts = sis.filter((i) => i.status === 'done').reduce((sum, i) => sum + (i.story_points ?? 0), 0);
    return { total, done, totalPts, donePts, pct: total ? Math.round((done / total) * 100) : 0 };
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      const sprint = await createSprint({
        name: newForm.name,
        goal: newForm.goal || null,
        start_date: newForm.start_date || null,
        end_date: newForm.end_date || null,
        status: 'planned',
      });
      setSprints((prev) => [sprint as Sprint, ...prev]);
      setShowNew(false);
      setNewForm({ name: '', goal: '', start_date: '', end_date: '' });
    } finally {
      setIsCreating(false);
    }
  };

  const handleActivate = async (sprint: Sprint) => {
    // Deactivate any currently active sprint
    const active = sprints.find((s) => s.status === 'active');
    if (active) {
      await updateSprint(active.id, { status: 'planned' });
      setSprints((prev) => prev.map((s) => s.id === active.id ? { ...s, status: 'planned' } : s));
    }
    const updated = await updateSprint(sprint.id, { status: 'active' });
    setSprints((prev) => prev.map((s) => s.id === sprint.id ? updated as Sprint : s));
  };

  const handleComplete = async (sprint: Sprint) => {
    const updated = await updateSprint(sprint.id, { status: 'completed' });
    setSprints((prev) => prev.map((s) => s.id === sprint.id ? updated as Sprint : s));
  };

  const inputCls = 'w-full rounded border border-[#1f2335] bg-[#0d0f14] px-3 py-2 text-[12px] text-[#e2e8f0] placeholder:text-[#475569] outline-none focus:border-amber-500/30';
  const labelCls = 'block text-[9px] font-mono uppercase tracking-widest text-[#475569] mb-1';

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between border-b border-[#1f2335] px-6 py-3 shrink-0">
        <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Sprints</h1>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px] font-mono font-semibold text-amber-400 hover:bg-amber-500/15 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Sprint
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {isLoading ? (
          <p className="text-[11px] font-mono text-[#475569]">Loading…</p>
        ) : sprints.length === 0 ? (
          <div className="py-12 text-center rounded-xl border border-dashed border-[#1f2335]">
            <GitBranch className="mx-auto h-8 w-8 text-[#1f2335] mb-2" />
            <p className="text-[11px] font-mono text-[#475569]">No sprints yet. Create your first sprint.</p>
          </div>
        ) : (
          sprints.map((sprint) => {
            const config = STATUS_CONFIG[sprint.status];
            const StatusIcon = config.icon;
            const b = burndown(sprint.id);
            const daysLeft = sprintDaysLeft(sprint.end_date);

            return (
              <div key={sprint.id} className={cn('rounded-xl border bg-[#13161e] p-4 space-y-3', sprint.status === 'active' ? 'border-amber-500/30' : 'border-[#1f2335]')}>
                {/* Sprint header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className={cn('flex h-7 w-7 items-center justify-center rounded border', sprint.status === 'active' ? 'bg-amber-500/10 border-amber-500/25' : 'bg-[#1a1d28] border-[#1f2335]')}>
                      <StatusIcon className="h-3.5 w-3.5" style={{ color: config.color }} />
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-[#e2e8f0]">{sprint.name}</p>
                      {sprint.goal && <p className="text-[11px] text-[#94a3b8]">{sprint.goal}</p>}
                    </div>
                    <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded border" style={{ color: config.color, borderColor: config.color + '30' }}>
                      {config.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {sprint.status === 'planned' && (
                      <button onClick={() => handleActivate(sprint)} className="text-[10px] font-mono px-2.5 py-1 rounded border border-amber-500/30 text-amber-400 hover:bg-amber-500/10 transition-colors">
                        Activate
                      </button>
                    )}
                    {sprint.status === 'active' && (
                      <button onClick={() => handleComplete(sprint)} className="text-[10px] font-mono px-2.5 py-1 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors">
                        Complete
                      </button>
                    )}
                  </div>
                </div>

                {/* Sprint meta */}
                <div className="flex items-center gap-4 text-[10px] font-mono text-[#475569]">
                  {sprint.start_date && <span><Clock className="inline h-2.5 w-2.5 mr-1" />{sprint.start_date}</span>}
                  {sprint.end_date && (
                    <span className={cn(daysLeft !== null && daysLeft <= 2 ? 'text-rose-400' : daysLeft !== null && daysLeft <= 5 ? 'text-amber-400' : '')}>
                      <Target className="inline h-2.5 w-2.5 mr-1" />
                      {sprint.end_date}{daysLeft !== null && ` · ${daysLeft}d left`}
                    </span>
                  )}
                  <span>{b.total} issues · {b.done} done</span>
                  {b.totalPts > 0 && <span>{b.donePts}/{b.totalPts} pts</span>}
                </div>

                {/* Progress bar */}
                {b.total > 0 && (
                  <div className="space-y-1">
                    <div className="h-1.5 w-full rounded-full bg-[#1a1d28] overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${b.pct}%`, background: b.pct === 100 ? '#10b981' : '#f59e0b' }}
                      />
                    </div>
                    <p className="text-[9px] font-mono text-[#475569]">{b.pct}% complete</p>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* New sprint form */}
      {showNew && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowNew(false)}>
          <form
            onSubmit={handleCreate}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-xl border border-[#1f2335] bg-[#13161e] p-5 space-y-3 shadow-2xl"
          >
            <h2 className="text-[13px] font-bold font-mono text-[#e2e8f0]">New Sprint</h2>
            <div>
              <label className={labelCls}>Name *</label>
              <input value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))} placeholder="Sprint 1" className={inputCls} required autoFocus />
            </div>
            <div>
              <label className={labelCls}>Goal</label>
              <input value={newForm.goal} onChange={(e) => setNewForm((f) => ({ ...f, goal: e.target.value }))} placeholder="Ship ticket tracking MVP" className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Start date</label>
                <input type="date" value={newForm.start_date} onChange={(e) => setNewForm((f) => ({ ...f, start_date: e.target.value }))} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>End date</label>
                <input type="date" value={newForm.end_date} onChange={(e) => setNewForm((f) => ({ ...f, end_date: e.target.value }))} className={inputCls} />
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={() => setShowNew(false)} className="flex-1 py-2 rounded border border-[#1f2335] text-[11px] font-mono text-[#475569]">Cancel</button>
              <button type="submit" disabled={isCreating || !newForm.name} className="flex-1 py-2 rounded border border-amber-500/40 bg-amber-500/10 text-[11px] font-mono font-semibold text-amber-400 disabled:opacity-50">
                {isCreating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
