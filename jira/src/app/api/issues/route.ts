import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const TYPE_PREFIX: Record<string, string> = { bug: 'BUG', feature: 'FEAT', task: 'TASK' };

function getServiceSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
  return createClient(url, key);
}

async function nextTicketId(sb: ReturnType<typeof getServiceSupabase>, type: string): Promise<string> {
  const prefix = TYPE_PREFIX[type] ?? 'TASK';
  const { data } = await sb
    .from('project_tickets')
    .select('ticket_id')
    .like('ticket_id', `${prefix}-%`)
    .order('ticket_id', { ascending: false })
    .limit(1);
  const last = data?.[0]?.ticket_id as string | undefined;
  const num = last ? parseInt(last.split('-')[1] ?? '0', 10) + 1 : 1;
  return `${prefix}-${String(num).padStart(3, '0')}`;
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { title, description, type = 'task', status = 'todo', priority = 'medium', sprint_id } = body;

  if (!title?.trim()) {
    return NextResponse.json({ error: 'title is required' }, { status: 422 });
  }

  const sb = getServiceSupabase();
  const ticket_id = await nextTicketId(sb, type);

  const { data, error } = await sb
    .from('project_tickets')
    .insert({ ticket_id, title, description, type, status, priority, sprint_id, ai_changelog: [] })
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
