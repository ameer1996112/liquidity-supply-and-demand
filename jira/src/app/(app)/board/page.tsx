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
import { Plus, RefreshCw } from 'lucide-react';
import { cn, sprintDaysLeft } from '@/lib/utils';
import { type Issue, type Sprint, STATUS_COLUMNS } from '@/lib/types';
import { fetchIssues, fetchSprints, updateIssue, updateSprint, bulkUpdateIssues, createSprint, getSupabase } from '@/lib/supabase';
import { IssueCard } from '@/components/IssueCard';
import { IssueDrawer } from '@/components/IssueDrawer';
import { NewIssueModal } from '@/components/NewIssueModal';
import { SprintTabs } from '@/components/SprintTabs';

export default function BoardPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [selectedSprintId, setSelectedSprintId] = useState<number | 'backlog' | null>(null);
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
      // Default to active sprint, or backlog if none
      const active = (ss as Sprint[]).find((s) => s.status === 'active');
      setSelectedSprintId((prev) => {
        if (prev !== null) return prev; // keep user's selection on reload
        return active ? active.id : 'backlog';
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Realtime subscription ──────────────────────────────────────────────────
  useEffect(() => {
    const sb = getSupabase();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const channel = sb.channel('board-issues-realtime').on<any>(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'project_tickets' },
      (payload) => {
        const { eventType, new: next, old: prev } = payload;
        if (eventType === 'INSERT') {
          const added = next as unknown as Issue;
          setIssues((all) => all.find((i) => i.id === added.id) ? all : [added, ...all]);
        } else if (eventType === 'UPDATE') {
          const updated = next as unknown as Issue;
          setIssues((all) => all.map((i) => i.id === updated.id ? updated : i));
        } else if (eventType === 'DELETE') {
          const removed = prev as { id: string };
          setIssues((all) => all.filter((i) => i.id !== removed.id));
        }
      }
    ).subscribe();
    return () => { sb.removeChannel(channel); };
  }, []);

  // Filter issues by selected sprint
  const filteredIssues = issues.filter((i) => {
    if (selectedSprintId === 'backlog') return i.sprint_id === null || i.sprint_id === undefined;
    if (selectedSprintId === null) return true;
    return i.sprint_id === selectedSprintId;
  });

  const byStatus = (status: string) => filteredIssues.filter((i) => i.status === status);

  // Sprint progress for selected sprint
  const activeSprint = sprints.find((s) => s.status === 'active') ?? null;
  const selectedSprint = typeof selectedSprintId === 'number'
    ? sprints.find((s) => s.id === selectedSprintId) ?? null
    : null;
  const displaySprint = selectedSprint;
  const sprintIssues = typeof selectedSprintId === 'number'
    ? issues.filter((i) => i.sprint_id === selectedSprintId)
    : [];
  const sprintDone = sprintIssues.filter((i) => i.status === 'done').length;
  const sprintTotal = sprintIssues.length;
  const sprintPct = sprintTotal > 0 ? Math.round((sprintDone / sprintTotal) * 100) : 0;
  const daysLeft = displaySprint ? sprintDaysLeft(displaySprint.end_date) : null;

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
    setIssues((prev) => prev.map((i) => i.id === issue.id ? { ...i, status: newStatus as Issue['status'] } : i));
    try {
      await updateIssue(issue.id, { status: newStatus });
    } catch {
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

  const handleCompleteSprint = async (sprint: Sprint) => {
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
      setSprints((prev) => [...prev, nextSprint!]);
    }

    // Move all incomplete tickets to next sprint
    const incompleteIds = issues
      .filter((i) => i.sprint_id === sprint.id && i.status !== 'done')
      .map((i) => i.id);
    await bulkUpdateIssues(incompleteIds, { sprint_id: nextSprint.id });

    // Mark sprint complete
    await updateSprint(sprint.id, { status: 'completed' });

    // Reload everything
    setSelectedSprintId(null); // reset so load() picks active/backlog default
    await load();
  };

  const handleSprintCreated = (sprint: Sprint) => {
    setSprints((prev) => [sprint, ...prev]);
    setSelectedSprintId(sprint.id);
  };

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <header className="flex items-center justify-between border-b border-[#1f2335] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Board</h1>
          {/* Sprint progress */}
          {displaySprint && sprintTotal > 0 && (
            <div className="flex items-center gap-2">
              <div className="w-24 h-1.5 rounded-full bg-[#1a1d28] overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${sprintPct}%`, background: sprintPct === 100 ? '#10b981' : '#f59e0b' }}
                />
              </div>
              <span className="text-[9px] font-mono text-[#475569]">
                {sprintDone}/{sprintTotal}
                {daysLeft !== null && (
                  <span className={cn(
                    'ml-1.5',
                    daysLeft <= 2 ? 'text-rose-400' : daysLeft <= 5 ? 'text-amber-400' : 'text-emerald-400'
                  )}>
                    {daysLeft}d left
                  </span>
                )}
              </span>
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

      {/* ── Sprint Tabs ── */}
      <SprintTabs
        sprints={sprints}
        selectedId={selectedSprintId}
        onSelect={setSelectedSprintId}
        onCompleteSprint={handleCompleteSprint}
        onSprintCreated={handleSprintCreated}
      />

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
