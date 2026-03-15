import { KanbanBoard } from '@/components/board/KanbanBoard';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'TradeOps | Task & Bug Board',
  description:
    'Kanban board for tracking bugs, tasks, and features — with AI agent integration',
};

export default function BoardPage() {
  return <KanbanBoard />;
}
