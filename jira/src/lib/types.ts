export type IssueType = 'bug' | 'feature' | 'task';
export type IssueStatus = 'todo' | 'in_progress' | 'review' | 'done' | 'archived';
export type IssuePriority = 'low' | 'medium' | 'high' | 'critical';
export type SprintStatus = 'planned' | 'active' | 'completed';
export type RelationType = 'blocks' | 'relates' | 'duplicates';

export interface Sprint {
  id: number;
  name: string;
  goal: string | null;
  start_date: string | null;
  end_date: string | null;
  status: SprintStatus;
  created_at: string;
  updated_at: string;
}

export interface Label {
  id: number;
  name: string;
  color: string;
}

export interface AiChangelogEntry {
  timestamp: string;
  agent: string;
  old_status: string;
  new_status: string;
  summary: string;
}

export interface Issue {
  id: string;
  title: string;
  description: string | null;
  type: IssueType;
  status: IssueStatus;
  priority: IssuePriority;
  assignee: string | null;
  signal_id: number | null;
  sprint_id: number | null;
  labels: string[];
  parent_id: string | null;
  rank: number;
  story_points: number | null;
  ai_changelog: AiChangelogEntry[];
  created_at: string;
  updated_at: string;
  // joined
  sprint?: Sprint | null;
  children?: Issue[];
}

export interface Comment {
  id: string;
  issue_id: string;
  body_md: string;
  author: string;
  is_ai: boolean;
  created_at: string;
  updated_at: string;
}

export interface Relation {
  id: number;
  source_id: string;
  target_id: string;
  type: RelationType;
}

// UI helpers
export const STATUS_COLUMNS: { key: IssueStatus; label: string; color: string }[] = [
  { key: 'todo',        label: 'To Do',       color: '#475569' },
  { key: 'in_progress', label: 'In Progress', color: '#f59e0b' },
  { key: 'review',      label: 'Review',      color: '#8b5cf6' },
  { key: 'done',        label: 'Done',        color: '#10b981' },
];

export const PRIORITY_CONFIG: Record<IssuePriority, { label: string; dotClass: string; color: string }> = {
  critical: { label: 'Critical', dotClass: 'priority-critical', color: '#ef4444' },
  high:     { label: 'High',     dotClass: 'priority-high',     color: '#f59e0b' },
  medium:   { label: 'Medium',   dotClass: 'priority-medium',   color: '#3b82f6' },
  low:      { label: 'Low',      dotClass: 'priority-low',      color: '#475569' },
};

export const TYPE_CONFIG: Record<IssueType, { label: string; color: string; bg: string }> = {
  bug:     { label: 'Bug',     color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
  feature: { label: 'Feature', color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' },
  task:    { label: 'Task',    color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
};
