import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

export interface AgentUpdatePayload {
  /** Ticket ID like "BUG-012" */
  ticket_id: string;
  /** Human-readable message to post to the activity feed */
  message: string;
  /** Optional: new status to move the ticket to */
  new_status?: 'backlog' | 'todo' | 'in_progress' | 'done';
  /** Optional: agent identifier shown in feed */
  agent_name?: string;
  /** Optional: event type for feed icon/styling */
  event_type?: 'update' | 'move' | 'create' | 'close';
}

/**
 * POST /api/board/agent-update
 *
 * Called by AI agents to post progress updates and move tickets on the board.
 *
 * Example:
 *   curl -X POST http://localhost:3000/api/board/agent-update \
 *     -H "Content-Type: application/json" \
 *     -d '{"ticket_id":"BUG-012","message":"Root cause identified. Starting fix.","new_status":"in_progress"}'
 */
export async function POST(req: NextRequest) {
  // Create client per-request so env vars are read at runtime, not build time
  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? '',
    process.env.SUPABASE_SERVICE_ROLE_KEY ??
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
      ''
  );

  let body: AgentUpdatePayload;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { ticket_id, message, new_status, agent_name, event_type } = body;

  if (!ticket_id || !message) {
    return NextResponse.json(
      { error: 'ticket_id and message are required' },
      { status: 400 }
    );
  }

  // 1. If new_status provided, update the ticket row
  if (new_status) {
    const patch: Record<string, unknown> = { status: new_status };
    if (new_status === 'done') patch.completed_at = new Date().toISOString();
    const { error } = await supabaseAdmin
      .from('project_tickets')
      .update(patch)
      .eq('ticket_id', ticket_id);
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
  }

  // 2. Insert feed event (triggers Supabase Realtime → AgentFeed component)
  const derivedEventType =
    event_type ??
    (new_status === 'done' ? 'close' : new_status ? 'move' : 'update');

  const { error: feedError } = await supabaseAdmin
    .from('ticket_agent_events')
    .insert({
      ticket_id,
      message,
      event_type: derivedEventType,
      agent_name: agent_name ?? 'Antigravity Agent',
    });

  if (feedError) {
    return NextResponse.json({ error: feedError.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true, ticket_id, new_status });
}
