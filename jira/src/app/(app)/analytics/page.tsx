'use client';

import { useEffect, useState } from 'react';
import { BarChart3, TrendingUp, CheckCircle, Clock, AlertTriangle, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchIssues, fetchSprints } from '@/lib/supabase';
import { type Issue, type Sprint, PRIORITY_CONFIG, TYPE_CONFIG } from '@/lib/types';

export default function AnalyticsPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchIssues({ includeArchived: true }), fetchSprints()])
      .then(([is, ss]) => { setIssues(is as Issue[]); setSprints(ss as Sprint[]); })
      .finally(() => setIsLoading(false));
  }, []);

  const activeSprint = sprints.find((s) => s.status === 'active');
  const sprintIssues = activeSprint ? issues.filter((i) => i.sprint_id === activeSprint.id) : [];
  const done = sprintIssues.filter((i) => i.status === 'done').length;
  const total = sprintIssues.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  // All-time metrics
  const allDone = issues.filter((i) => i.status === 'done' || i.status === 'archived').length;
  const bugs = issues.filter((i) => i.type === 'bug').length;
  const features = issues.filter((i) => i.type === 'feature').length;
  const tasks = issues.filter((i) => i.type === 'task').length;

  // Priority breakdown (excluding done/archived)
  const active = issues.filter((i) => i.status !== 'done' && i.status !== 'archived');
  const criticalCount = active.filter((i) => i.priority === 'critical').length;
  const highCount = active.filter((i) => i.priority === 'high').length;

  // Velocity: avg done per sprint
  const completedSprints = sprints.filter((s) => s.status === 'completed');
  const velocity = completedSprints.length > 0
    ? Math.round(issues.filter((i) => i.status === 'done' || i.status === 'archived').length / completedSprints.length)
    : 0;

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 border-b border-[#1f2335] px-6 py-3 shrink-0">
        <BarChart3 className="h-4 w-4 text-[#475569]" />
        <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Analytics</h1>
        {isLoading && <span className="text-[9px] font-mono text-[#475569] animate-pulse">Loading…</span>}
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Sprint progress */}
        <section>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] mb-3">Active Sprint</p>
          {activeSprint ? (
            <div className="rounded-xl border border-[#1f2335] bg-[#13161e] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-semibold text-[#e2e8f0]">{activeSprint.name}</p>
                <span className={cn('text-[11px] font-mono font-bold', pct === 100 ? 'text-emerald-400' : pct > 50 ? 'text-amber-400' : 'text-rose-400')}>
                  {pct}%
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-[#1a1d28] overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${pct}%`, background: pct === 100 ? '#10b981' : '#f59e0b' }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-[#475569]">
                <span>{done} / {total} issues complete</span>
                {activeSprint.end_date && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    Ends {new Date(activeSprint.end_date).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-[#1f2335] bg-[#13161e] p-6 text-center">
              <p className="text-[11px] font-mono text-[#475569]">No active sprint</p>
            </div>
          )}
        </section>

        {/* KPI cards */}
        <section>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] mb-3">Overall Metrics</p>
          <div className="grid grid-cols-2 gap-3">
            <KpiCard icon={CheckCircle} label="Total Done" value={String(allDone)} color="#10b981" />
            <KpiCard icon={Zap} label="Velocity" value={`${velocity}/sprint`} color="#f59e0b" />
            <KpiCard icon={AlertTriangle} label="Critical Open" value={String(criticalCount)} color="#ef4444" />
            <KpiCard icon={TrendingUp} label="High Priority" value={String(highCount)} color="#f97316" />
          </div>
        </section>

        {/* Issue type breakdown */}
        <section>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] mb-3">Issue Types</p>
          <div className="rounded-xl border border-[#1f2335] bg-[#13161e] p-4 space-y-3">
            {[
              { label: 'Features', count: features, total: issues.length, color: TYPE_CONFIG.feature.color },
              { label: 'Tasks',    count: tasks,    total: issues.length, color: TYPE_CONFIG.task.color },
              { label: 'Bugs',     count: bugs,     total: issues.length, color: TYPE_CONFIG.bug.color },
            ].map(({ label, count, color }) => {
              const pct = issues.length > 0 ? Math.round((count / issues.length) * 100) : 0;
              return (
                <div key={label} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-[#94a3b8]">{label}</span>
                    <span style={{ color }}>{count} ({pct}%)</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[#1a1d28] overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Priority breakdown */}
        <section>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] mb-3">Priority Distribution (Active)</p>
          <div className="rounded-xl border border-[#1f2335] bg-[#13161e] p-4 space-y-2">
            {(['critical', 'high', 'medium', 'low'] as const).map((p) => {
              const cnt = active.filter((i) => i.priority === p).length;
              const pct = active.length > 0 ? Math.round((cnt / active.length) * 100) : 0;
              const cfg = PRIORITY_CONFIG[p];
              return (
                <div key={p} className="flex items-center gap-3">
                  <span className={`h-2 w-2 rounded-full shrink-0 ${cfg.dotClass}`} />
                  <span className="text-[11px] font-mono text-[#94a3b8] w-16">{cfg.label}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-[#1a1d28] overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: cfg.color }} />
                  </div>
                  <span className="text-[10px] font-mono text-[#475569] w-8 text-right">{cnt}</span>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, color }: { icon: typeof CheckCircle; label: string; value: string; color: string }) {
  return (
    <div className="rounded-xl border border-[#1f2335] bg-[#13161e] p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded" style={{ background: color + '20' }}>
          <Icon className="h-3.5 w-3.5" style={{ color }} />
        </div>
        <span className="text-[10px] font-mono text-[#475569]">{label}</span>
      </div>
      <p className="text-[20px] font-bold font-mono" style={{ color }}>{value}</p>
    </div>
  );
}
