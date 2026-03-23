'use client';

import { useEffect, useState, useCallback } from 'react';
import { Plus, Search, Filter } from 'lucide-react';
import { cn, relativeTime } from '@/lib/utils';
import { type Issue, type Sprint, PRIORITY_CONFIG, TYPE_CONFIG } from '@/lib/types';
import { fetchIssues, fetchSprints } from '@/lib/supabase';
import { IssueDrawer } from '@/components/IssueDrawer';
import { NewIssueModal } from '@/components/NewIssueModal';

const STATUS_BADGE: Record<string, string> = {
  todo:        'text-[#475569] border-[#1f2335]',
  in_progress: 'text-amber-400 border-amber-500/30',
  review:      'text-violet-400 border-violet-500/30',
  done:        'text-emerald-400 border-emerald-500/30',
};

export default function BacklogPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [drawerIssue, setDrawerIssue] = useState<Issue | null>(null);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [is, ss] = await Promise.all([
        fetchIssues({ sprint_id: null }), // backlog = no sprint
        fetchSprints(),
      ]);
      setIssues(is as Issue[]);
      setSprints(ss as Sprint[]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = issues.filter((i) => {
    if (search && !i.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterType !== 'all' && i.type !== filterType) return false;
    if (filterPriority !== 'all' && i.priority !== filterPriority) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between border-b border-[#1f2335] px-6 py-3 shrink-0">
        <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Backlog</h1>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px] font-mono font-semibold text-amber-400 hover:bg-amber-500/15 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Issue
        </button>
      </header>

      {/* Filters */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-[#1f2335] shrink-0">
        <div className="flex items-center gap-1.5 flex-1 max-w-xs rounded border border-[#1f2335] bg-[#0d0f14] px-2.5 py-1.5">
          <Search className="h-3 w-3 text-[#475569] shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search issues…"
            className="flex-1 bg-transparent text-[12px] text-[#e2e8f0] placeholder:text-[#475569] outline-none"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="h-3 w-3 text-[#475569]" />
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="rounded border border-[#1f2335] bg-[#0d0f14] px-2 py-1 text-[11px] font-mono text-[#94a3b8] outline-none">
            <option value="all">All Types</option>
            <option value="bug">Bug</option>
            <option value="feature">Feature</option>
            <option value="task">Task</option>
          </select>
          <select value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)} className="rounded border border-[#1f2335] bg-[#0d0f14] px-2 py-1 text-[11px] font-mono text-[#94a3b8] outline-none">
            <option value="all">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        <span className="text-[10px] font-mono text-[#475569] ml-auto">{filtered.length} issues</span>
      </div>

      {/* Issue list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="py-12 text-center"><p className="text-[11px] font-mono text-[#475569]">Loading…</p></div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center"><p className="text-[11px] font-mono text-[#475569]">No issues in backlog.</p></div>
        ) : (
          <div className="divide-y divide-[#1f2335]">
            {filtered.map((issue) => {
              const typeConfig = TYPE_CONFIG[issue.type];
              const priorityConfig = PRIORITY_CONFIG[issue.priority];
              return (
                <button
                  key={issue.id}
                  onClick={() => setDrawerIssue(issue)}
                  className="w-full flex items-center gap-3 px-6 py-3 text-left hover:bg-[#1a1d28] transition-colors"
                >
                  <span className={cn('h-2 w-2 rounded-full shrink-0', priorityConfig.dotClass)} />
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border" style={{ color: typeConfig.color, borderColor: typeConfig.color + '30', background: typeConfig.bg }}>
                    {typeConfig.label}
                  </span>
                  <span className="flex-1 text-[12px] font-medium text-[#e2e8f0] truncate">{issue.title}</span>
                  {issue.labels.slice(0, 2).map((l) => (
                    <span key={l} className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#1f2335] text-[#475569]">{l}</span>
                  ))}
                  {issue.story_points != null && (
                    <span className="text-[9px] font-mono text-[#475569] border border-[#1f2335] rounded px-1">{issue.story_points}pt</span>
                  )}
                  <span className={cn('text-[9px] font-mono px-1.5 py-0.5 rounded border capitalize', STATUS_BADGE[issue.status] ?? '')}>
                    {issue.status.replace('_', ' ')}
                  </span>
                  <span className="text-[9px] font-mono text-[#475569] shrink-0">{relativeTime(issue.created_at)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {drawerIssue && (
        <IssueDrawer
          issue={drawerIssue}
          onClose={() => setDrawerIssue(null)}
          onUpdate={(u) => { setIssues((p) => p.map((i) => i.id === u.id ? u : i)); setDrawerIssue(u); }}
          onDelete={(id) => { setIssues((p) => p.filter((i) => i.id !== id)); setDrawerIssue(null); }}
        />
      )}
      {showNew && (
        <NewIssueModal
          onClose={() => setShowNew(false)}
          onCreated={(issue) => { setIssues((p) => [issue as Issue, ...p]); }}
          sprints={sprints}
        />
      )}
    </div>
  );
}
