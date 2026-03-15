import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

export interface CreateTicketPayload {
  type: 'bug' | 'task' | 'feature' | 'research';
  title: string;
  description?: string;
  component: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status?: 'backlog' | 'todo' | 'in_progress' | 'done';
  /** Optional: agent identifier shown in feed */
  agent_name?: string;
}

/**
 * POST /api/board/create-ticket
 *
 * Called by AI agents to open a new ticket on the board.
 * Auto-generates a ticket_id (BUG-###, TASK-###, FEAT-###, RES-###).
 *
 * Example:
 *   curl -X POST http://localhost:3000/api/board/create-ticket \
 *     -H "Content-Type: application/json" \
 *     -d '{"type":"bug","title":"Position sizing off by 10x on NZDJPY","component":"Python Backend","priority":"critical","description":"Root cause: missing JPY pip value override."}'
 */
export async function POST(req: NextRequest) {
  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? '',
    process.env.SUPABASE_SERVICE_ROLE_KEY ??
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
      ''
  );

  let body: CreateTicketPayload;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { type, title, component, priority, description, status, agent_name } = body;

  if (!type || !title || !component || !priority) {
    return NextResponse.json(
      { error: 'type, title, component, and priority are required' },
      { status: 400 }
    );
  }

  // Auto-generate ticket_id (BUG-001, TASK-001, etc.)
  const prefix =
    type === 'bug' ? 'BUG' : type === 'feature' ? 'FEAT' : type === 'research' ? 'RES' : 'TASK';

  const { data: existing } = await supabaseAdmin
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

  // Insert ticket
  const { data: ticket, error: ticketError } = await supabaseAdmin
    .from('project_tickets')
    .insert({
      ticket_id,
      type,
      title,
      description,
      component,
      priority,
      status: status ?? 'backlog',
    })
    .select()
    .single();

  if (ticketError) {
    return NextResponse.json({ error: ticketError.message }, { status: 500 });
  }

  // Log agent event in feed
  const { error: feedError } = await supabaseAdmin.from('ticket_agent_events').insert({
    ticket_id,
    message: `Opened ${type} ticket: ${title}`,
    event_type: 'create',
    agent_name: agent_name ?? 'Claude Agent',
  });

  if (feedError) {
    // Non-fatal — ticket was created, just feed log failed
    console.error('Failed to insert agent feed event:', feedError.message);
  }

  return NextResponse.json({ ok: true, ticket_id, ticket });
}
