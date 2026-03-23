'use client';

import { useState } from 'react';
import { Plus, CheckCircle, GitBranch, Archive } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type Sprint } from '@/lib/types';
import { NewSprintModal } from './NewSprintModal';

interface Props {
  sprints: Sprint[];
  selectedId: number | 'backlog' | null;
  onSelect: (id: number | 'backlog') => void;
  onCompleteSprint: (sprint: Sprint) => void;
  onSprintCreated: (sprint: Sprint) => void;
}

export function SprintTabs({ sprints, selectedId, onSelect, onCompleteSprint, onSprintCreated }: Props) {
  const [showNew, setShowNew] = useState(false);

  const activeSprint = sprints.find((s) => s.status === 'active');
  // Show active first, then planned, then completed
  const ordered = [
    ...sprints.filter((s) => s.status === 'active'),
    ...sprints.filter((s) => s.status === 'planned'),
    ...sprints.filter((s) => s.status === 'completed'),
  ];

  return (
    <>
      <div className="flex items-center gap-1 border-b border-[#1f2335] px-6 py-0 shrink-0 overflow-x-auto">
        {ordered.map((sprint) => {
          const isActive = sprint.status === 'active';
          const isSelected = selectedId === sprint.id;
          return (
            <button
              key={sprint.id}
              onClick={() => onSelect(sprint.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2.5 text-[11px] font-mono whitespace-nowrap border-b-2 transition-colors',
                isSelected
                  ? 'border-amber-400 text-[#e2e8f0]'
                  : 'border-transparent text-[#475569] hover:text-[#94a3b8]'
              )}
            >
              {isActive && (
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              )}
              {sprint.status === 'completed' && (
                <CheckCircle className="h-3 w-3 text-emerald-500/50" />
              )}
              {sprint.status === 'planned' && (
                <GitBranch className="h-3 w-3 text-[#475569]" />
              )}
              {sprint.name}
            </button>
          );
        })}

        {/* Backlog tab */}
        <button
          onClick={() => onSelect('backlog')}
          className={cn(
            'flex items-center gap-1.5 px-3 py-2.5 text-[11px] font-mono whitespace-nowrap border-b-2 transition-colors',
            selectedId === 'backlog'
              ? 'border-[#94a3b8] text-[#e2e8f0]'
              : 'border-transparent text-[#475569] hover:text-[#94a3b8]'
          )}
        >
          <Archive className="h-3 w-3" />
          Backlog
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Complete sprint */}
        {activeSprint && selectedId === activeSprint.id && (
          <button
            onClick={() => onCompleteSprint(activeSprint)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] font-mono rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors mr-2 whitespace-nowrap"
          >
            <CheckCircle className="h-3 w-3" />
            Complete Sprint
          </button>
        )}

        {/* New sprint */}
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1 p-2 text-[#475569] hover:text-[#94a3b8] transition-colors"
          title="New Sprint"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      {showNew && (
        <NewSprintModal
          onClose={() => setShowNew(false)}
          onSaved={(sprint) => {
            onSprintCreated(sprint);
            setShowNew(false);
          }}
        />
      )}
    </>
  );
}
