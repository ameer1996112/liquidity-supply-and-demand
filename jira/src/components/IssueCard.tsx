'use client';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Bug, Sparkles, CheckSquare, ExternalLink } from 'lucide-react';
import { cn, relativeTime } from '@/lib/utils';
import { type Issue, PRIORITY_CONFIG, TYPE_CONFIG } from '@/lib/types';

const TYPE_ICONS = {
  bug:     Bug,
  feature: Sparkles,
  task:    CheckSquare,
} as const;

interface Props {
  issue: Issue;
  onClick: (issue: Issue) => void;
}

export function IssueCard({ issue, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: issue.id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  const TypeIcon = TYPE_ICONS[issue.type];
  const typeConfig = TYPE_CONFIG[issue.type];
  const priorityConfig = PRIORITY_CONFIG[issue.priority];

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={() => onClick(issue)}
      className={cn(
        'group relative cursor-pointer select-none',
        'rounded-lg border border-[#1f2335] bg-[#13161e] p-3 space-y-2',
        'transition-all duration-150',
        'hover:border-[#2a2d3e] hover:bg-[#1a1d28] hover:shadow-lg',
        isDragging && 'dragging shadow-2xl',
      )}
    >
      {/* Top row: type icon + priority dot + ai badge */}
      <div className="flex items-center justify-between">
        <div
          className="flex h-5 w-5 items-center justify-center rounded"
          style={{ background: typeConfig.bg }}
        >
          <TypeIcon className="h-3 w-3" style={{ color: typeConfig.color }} />
        </div>
        <div className="flex items-center gap-1.5">
          {(issue.ai_changelog?.length ?? 0) > 0 && (
            <span className="text-[8px] font-mono text-violet-400/70 border border-violet-500/20 rounded px-1">AI</span>
          )}
          <span
            className={cn('h-2 w-2 rounded-full', priorityConfig.dotClass)}
            title={priorityConfig.label}
          />
        </div>
      </div>

      {/* Title */}
      <p className="text-[12px] font-medium text-[#e2e8f0] leading-snug line-clamp-2 group-hover:text-white">
        {issue.title}
      </p>

      {/* Labels */}
      {issue.labels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {issue.labels.slice(0, 3).map((label) => (
            <span
              key={label}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#1f2335] text-[#94a3b8]"
            >
              {label}
            </span>
          ))}
          {issue.labels.length > 3 && (
            <span className="text-[9px] font-mono text-[#475569]">+{issue.labels.length - 3}</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {issue.signal_id && (
            <span className="flex items-center gap-0.5 text-[9px] font-mono text-blue-400/70">
              <ExternalLink className="h-2.5 w-2.5" />
              #{issue.signal_id}
            </span>
          )}
          {issue.story_points != null && (
            <span className="text-[9px] font-mono text-[#475569] border border-[#1f2335] rounded px-1">
              {issue.story_points}pt
            </span>
          )}
        </div>
        <span className="text-[9px] font-mono text-[#475569]">
          {relativeTime(issue.created_at)}
        </span>
      </div>
    </div>
  );
}
