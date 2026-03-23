'use client';

import { useEffect, useState, useCallback } from 'react';
import { Plus, GitBranch, Play, CheckCircle, Clock, Target, Pencil, RefreshCw, Zap } from 'lucide-react';
import { cn, sprintDaysLeft } from '@/lib/utils';
import { type Sprint, type Issue } from '@/lib/types';
import { fetchSprints, fetchIssues, updateSprint, bulkUpdateIssues, createSprint } from '@/lib/supabase';
import { NewSprintModal } from '@/components/NewSprintModal';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

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
  const [editingSprint, setEditingSprint] = useState<Sprint | null>(null);

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

  const handleActivate = async (sprint: Sprint) => {
    const active = sprints.find((s) => s.status === 'active');
    if (active) {
      await updateSprint(active.id, { status: 'planned' });
      setSprints((prev) => prev.map((s) => s.id === active.id ? { ...s, status: 'planned' } : s));
    }
    const updated = await updateSprint(sprint.id, { status: 'active' });
    setSprints((prev) => prev.map((s) => s.id === sprint.id ? updated as Sprint : s));
  };

  const handleComplete = async (sprint: Sprint) => {
    // Find or create next planned sprint
    let nextSprint = sprints.find((s) => s.status === 'planned');
    if (!nextSprint) {
      nextSprint = await createSprint({
        name: 'Next Sprint',
        status: 'planned',
        goal: null,
        start_date: null,
        end_date: null,
      }) as Sprint;
    }
    // Move incomplete tickets
    const incompleteIds = issues
      .filter((i) => i.sprint_id === sprint.id && i.status !== 'done')
      .map((i) => i.id);
    await bulkUpdateIssues(incompleteIds, { sprint_id: nextSprint.id });
    await updateSprint(sprint.id, { status: 'completed' });
    await load();
  };

  const handleSaved = (saved: Sprint) => {
    setSprints((prev) => {
      const exists = prev.find((s) => s.id === saved.id);
      return exists
        ? prev.map((s) => s.id === saved.id ? saved : s)
        : [saved, ...prev];
    });
  };

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
                    <button
                      onClick={() => setEditingSprint(sprint)}
                      className="p-1.5 rounded text-[#475569] hover:text-[#94a3b8] hover:bg-[#1a1d28] transition-colors"
                      title="Edit sprint"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
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

      {showNew && (
        <NewSprintModal
          onClose={() => setShowNew(false)}
          onSaved={(sprint) => { handleSaved(sprint); setShowNew(false); }}
        />
      )}

      {editingSprint && (
        <NewSprintModal
          sprint={editingSprint}
          onClose={() => setEditingSprint(null)}
          onSaved={(sprint) => { handleSaved(sprint); setEditingSprint(null); }}
        />
      )}
    </div>
  );
}
