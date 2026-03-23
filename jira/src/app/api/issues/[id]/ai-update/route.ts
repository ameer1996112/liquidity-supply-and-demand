import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

function getServiceSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
  return createClient(url, key);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  const body = await request.json();
  const { new_status, summary_of_work, agent = 'antigravity' } = body;

  if (!['todo', 'in_progress', 'review', 'done'].includes(new_status)) {
    return NextResponse.json({ error: 'Invalid status' }, { status: 422 });
  }
  if (!summary_of_work?.trim()) {
    return NextResponse.json({ error: 'summary_of_work is required' }, { status: 422 });
  }

  const sb = getServiceSupabase();

  // Fetch current
  const { data: current, error: fetchErr } = await sb
    .from('project_tickets')
    .select('status, ai_changelog')
    .eq('id', id)
    .single();

  if (fetchErr || !current) {
    return NextResponse.json({ error: 'Issue not found' }, { status: 404 });
  }

  const entry = {
    timestamp: new Date().toISOString(),
    agent,
    old_status: current.status,
    new_status,
    summary: summary_of_work,
  };

  const updated_changelog = [...(current.ai_changelog ?? []), entry];

  const { error: updateErr } = await sb
    .from('project_tickets')
    .update({ status: new_status, ai_changelog: updated_changelog })
    .eq('id', id);

  if (updateErr) {
    return NextResponse.json({ error: updateErr.message }, { status: 500 });
  }

  // Also add AI comment
  await sb.from('jira_comments').insert({
    issue_id: id,
    body_md: `**Status updated:** ${current.status} → ${new_status}\n\n${summary_of_work}`,
    author: agent,
    is_ai: true,
  });

  return NextResponse.json({
    status: 'ok',
    ticket_id: id,
    old_status: current.status,
    new_status,
    changelog_entries: updated_changelog.length,
  });
}
