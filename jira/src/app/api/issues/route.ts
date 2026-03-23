import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

function getServiceSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
  return createClient(url, key);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { title, description, type = 'task', status = 'todo', priority = 'medium', assignee, sprint_id } = body;

  if (!title?.trim()) {
    return NextResponse.json({ error: 'title is required' }, { status: 422 });
  }

  const sb = getServiceSupabase();
  const { data, error } = await sb
    .from('project_tickets')
    .insert({ title, description, type, status, priority, assignee, sprint_id, ai_changelog: [] })
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
