import { supabase } from './supabase';

export type TicketType = 'bug' | 'task' | 'feature' | 'research';
export type Priority = 'critical' | 'high' | 'medium' | 'low';
export type TicketStatus = 'backlog' | 'todo' | 'in_progress' | 'done';

export interface Ticket {
  id: string;
  ticket_id: string;
  type: TicketType;
  title: string;
  description?: string;
  component: string;
  priority: Priority;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface CreateTicketInput {
  type: TicketType;
  title: string;
  description?: string;
  component: string;
  priority: Priority;
  status?: TicketStatus;
}

/** Fetch all tickets ordered by created_at desc */
export async function fetchTickets(): Promise<Ticket[]> {
  if (!supabase) return MOCK_TICKETS;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data, error } = await (supabase as any)
    .from('project_tickets')
    .select('*')
    .order('created_at', { ascending: false });
  if (error) throw error;
  return (data ?? []) as Ticket[];
}

/** Create a new ticket; auto-generates ticket_id like BUG-023 */
export async function createTicket(input: CreateTicketInput): Promise<Ticket> {
  if (!supabase) throw new Error('Supabase unavailable');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = supabase as any;
  const prefix =
    input.type === 'bug'
      ? 'BUG'
      : input.type === 'feature'
        ? 'FEAT'
        : input.type === 'research'
          ? 'RES'
          : 'TASK';
  const { data: existing } = await db
    .from('project_tickets')
    .select('ticket_id')
    .ilike('ticket_id', `${prefix}-%`)
    .order('ticket_id', { ascending: false })
    .limit(1);
  const lastNum =
    existing?.[0]?.ticket_id
      ? parseInt(String(existing[0].ticket_id).split('-')[1], 10)
      : 0;
  const ticket_id = `${prefix}-${String(lastNum + 1).padStart(3, '0')}`;

  const { data, error } = await db
    .from('project_tickets')
    .insert({ ...input, ticket_id, status: input.status ?? 'backlog' })
    .select()
    .single();
  if (error) throw error;
  return data as Ticket;
}

/** Update ticket status (card quick-move) */
export async function updateTicketStatus(
  id: string,
  status: TicketStatus
): Promise<void> {
  if (!supabase) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = supabase as any;
  const patch: Record<string, unknown> = { status };
  if (status === 'done') patch.completed_at = new Date().toISOString();
  const { error } = await db.from('project_tickets').update(patch).eq('id', id);
  if (error) throw error;
}

/** Update any ticket fields (used by agent webhook proxy) */
export async function updateTicket(
  id: string,
  patch: Partial<Ticket>
): Promise<void> {
  if (!supabase) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { error } = await (supabase as any)
    .from('project_tickets')
    .update(patch)
    .eq('id', id);
  if (error) throw error;
}

// ── Mock fallback when Supabase is not configured ─────────────────────────────
// Static timestamps avoid server/client hydration mismatch (React error #418)
const MOCK_TICKETS: Ticket[] = [
  {
    id: '1',
    ticket_id: 'BUG-012',
    type: 'bug',
    title: '"Council" column showing empty on dashboard',
    component: 'Frontend (React)',
    priority: 'critical',
    status: 'in_progress',
    created_at: '2026-03-15T00:00:00.000Z',
    updated_at: '2026-03-15T00:00:00.000Z',
  },
  {
    id: '2',
    ticket_id: 'TASK-009',
    type: 'task',
    title: 'Audit Pine Script webhook payload for council JSON key',
    component: 'Pine Script',
    priority: 'high',
    status: 'todo',
    created_at: '2026-03-15T00:00:00.000Z',
    updated_at: '2026-03-15T00:00:00.000Z',
  },
  {
    id: '3',
    ticket_id: 'BUG-014',
    type: 'bug',
    title: 'ML Guardian occasionally blocks valid high-confidence signals',
    component: 'AI / ML Pipeline',
    priority: 'medium',
    status: 'backlog',
    created_at: '2026-03-15T00:00:00.000Z',
    updated_at: '2026-03-15T00:00:00.000Z',
  },
  {
    id: '4',
    ticket_id: 'BUG-011',
    type: 'bug',
    title: 'Next.js App Router aggressive caching on Supabase calls',
    component: 'Frontend (React)',
    priority: 'high',
    status: 'done',
    created_at: '2026-03-15T00:00:00.000Z',
    updated_at: '2026-03-15T00:00:00.000Z',
  },
];
