'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
} from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Plus, RefreshCw, GitBranch, Zap } from 'lucide-react';
import { cn, sprintDaysLeft } from '@/lib/utils';
import { type Issue, type Sprint, STATUS_COLUMNS } from '@/lib/types';
import { fetchIssues, fetchSprints, updateIssue } from '@/lib/supabase';
import { IssueCard } from '@/components/IssueCard';
import { IssueDrawer } from '@/components/IssueDrawer';
import { NewIssueModal } from '@/components/NewIssueModal';

export default function BoardPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [activeSprint, setActiveSprint] = useState<Sprint | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeIssue, setActiveIssue] = useState<Issue | null>(null);
  const [drawerIssue, setDrawerIssue] = useState<Issue | null>(null);
  const [showNew, setShowNew] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [is, ss] = await Promise.all([fetchIssues(), fetchSprints()]);
      setIssues(is as Issue[]);
      setSprints(ss as Sprint[]);
      setActiveSprint((ss as Sprint[]).find((s) => s.status === 'active') ?? null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const byStatus = (status: string) =>
    issues.filter((i) => i.status === status);

  const handleDragStart = (e: DragStartEvent) => {
    setActiveId(String(e.active.id));
    setActiveIssue(issues.find((i) => i.id === e.active.id) ?? null);
  };

  const handleDragEnd = async (e: DragEndEvent) => {
    setActiveId(null);
    setActiveIssue(null);
    const { active, over } = e;
    if (!over) return;
    const newStatus = over.id as string;
    if (!STATUS_COLUMNS.find((c) => c.key === newStatus)) return;
    const issue = issues.find((i) => i.id === active.id);
    if (!issue || issue.status === newStatus) return;
    // Optimistic update
    setIssues((prev) => prev.map((i) => i.id === issue.id ? { ...i, status: newStatus as Issue['status'] } : i));
    try {
      await updateIssue(issue.id, { status: newStatus });
    } catch {
      // Revert
      setIssues((prev) => prev.map((i) => i.id === issue.id ? { ...i, status: issue.status } : i));
    }
  };

  const handleUpdate = (updated: Issue) => {
    setIssues((prev) => prev.map((i) => i.id === updated.id ? updated : i));
    setDrawerIssue(updated);
  };

  const handleDelete = (id: string) => {
    setIssues((prev) => prev.filter((i) => i.id !== id));
  };

  const daysLeft = activeSprint ? sprintDaysLeft(activeSprint.end_date) : null;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <header className="flex items-center justify-between border-b border-[#1f2335] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Board</h1>
          {activeSprint && (
            <div className="flex items-center gap-2 rounded-md border border-[#1f2335] bg-[#1a1d28] px-3 py-1">
              <GitBranch className="h-3 w-3 text-amber-400" />
              <span className="text-[10px] font-mono text-[#94a3b8]">
                {activeSprint.name}
              </span>
              {daysLeft !== null && (
                <span className={cn(
                  'text-[9px] font-mono font-bold',
                  daysLeft <= 2 ? 'text-rose-400' : daysLeft <= 5 ? 'text-amber-400' : 'text-emerald-400'
                )}>
                  {daysLeft}d left
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={isLoading}
            className="p-1.5 rounded border border-[#1f2335] text-[#475569] hover:text-[#94a3b8] hover:border-[#2a2d3e] transition-colors"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
          </button>
          <button
            onClick={() => setShowNew(true)}
            className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px] font-mono font-semibold text-amber-400 hover:bg-amber-500/15 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            New Issue
          </button>
        </div>
      </header>

      {/* ── Kanban Columns ── */}
      <div className="flex-1 overflow-x-auto">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-4 p-6 h-full min-w-max">
            {STATUS_COLUMNS.map((col) => {
              const colIssues = byStatus(col.key);
              return (
                <div
                  key={col.key}
                  id={col.key}
                  className={cn(
                    'flex flex-col w-72 shrink-0 rounded-xl border bg-[#13161e]',
                    'border-[#1f2335] transition-colors duration-150',
                  )}
                >
                  {/* Column header */}
                  <div
                    className="flex items-center justify-between px-3 py-2.5 border-b-2 rounded-t-xl"
                    style={{ borderBottomColor: col.color + '40' }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ background: col.color }} />
                      <span className="text-[11px] font-mono font-bold uppercase tracking-widest" style={{ color: col.color }}>
                        {col.label}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[#475569] bg-[#1a1d28] border border-[#1f2335] rounded px-1.5 py-0.5">
                      {colIssues.length}
                    </span>
                  </div>

                  {/* Cards */}
                  <SortableContext items={colIssues.map((i) => i.id)} strategy={verticalListSortingStrategy}>
                    <div
                      id={col.key}
                      className={cn(
                        'flex-1 p-2 space-y-2 overflow-y-auto min-h-[200px]',
                        activeId && 'drag-over rounded-b-xl',
                      )}
                    >
                      {colIssues.length === 0 && !activeId && (
                        <div className="py-8 text-center">
                          <p className="text-[10px] font-mono text-[#475569]">No issues</p>
                        </div>
                      )}
                      {colIssues.map((issue) => (
                        <IssueCard
                          key={issue.id}
                          issue={issue}
                          onClick={setDrawerIssue}
                        />
                      ))}
                    </div>
                  </SortableContext>
                </div>
              );
            })}
          </div>

          <DragOverlay>
            {activeIssue && (
              <div className="rotate-1 scale-105 opacity-90">
                <IssueCard issue={activeIssue} onClick={() => {}} />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      </div>

      {/* Drawer */}
      {drawerIssue && (
        <IssueDrawer
          issue={drawerIssue}
          onClose={() => setDrawerIssue(null)}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
        />
      )}

      {/* New issue modal */}
      {showNew && (
        <NewIssueModal
          onClose={() => setShowNew(false)}
          onCreated={(issue) => { setIssues((prev) => [issue as Issue, ...prev]); }}
          sprints={sprints}
        />
      )}
    </div>
  );
}
