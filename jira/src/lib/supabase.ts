import { createClient, SupabaseClient } from '@supabase/supabase-js';

let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (_client) return _client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    || process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error('Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_KEY env vars');
  }
  _client = createClient(url, key, {
    realtime: { params: { eventsPerSecond: 10 } },
  });
  return _client;
}

// ── Issues ────────────────────────────────────────────────────────────────────

export async function fetchIssues(filters: {
  status?: string;
  sprint_id?: number | null;
  includeArchived?: boolean;
} = {}) {
  const sb = getSupabase();
  let q = sb
    .from('project_tickets')
    .select('*')
    .order('rank', { ascending: true })
    .order('created_at', { ascending: false });

  if (!filters.includeArchived) q = q.neq('status', 'archived');
  if (filters.status) q = q.eq('status', filters.status);
  if (filters.sprint_id !== undefined) {
    q = filters.sprint_id === null
      ? q.is('sprint_id', null)
      : q.eq('sprint_id', filters.sprint_id);
  }
  const { data, error } = await q;
  if (error) throw error;
  return data ?? [];
}

export async function fetchIssue(id: string) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('project_tickets')
    .select('*')
    .eq('id', id)
    .single();
  if (error) throw error;
  return data;
}

export async function createIssue(payload: Record<string, unknown>) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('project_tickets')
    .insert(payload)
    .select()
    .single();
  if (error) throw error;
  return data;
}

export async function updateIssue(id: string, payload: Record<string, unknown>) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('project_tickets')
    .update(payload)
    .eq('id', id)
    .select()
    .single();
  if (error) throw error;
  return data;
}

export async function bulkUpdateIssues(ids: string[], payload: Record<string, unknown>) {
  if (ids.length === 0) return;
  await Promise.all(ids.map((id) => updateIssue(id, payload)));
}

export async function deleteIssue(id: string) {
  const sb = getSupabase();
  const { error } = await sb
    .from('project_tickets')
    .update({ status: 'archived' })
    .eq('id', id);
  if (error) throw error;
}

// ── Sprints ───────────────────────────────────────────────────────────────────

export async function fetchSprints() {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_sprints')
    .select('*')
    .order('created_at', { ascending: false });
  if (error) throw error;
  return data ?? [];
}

export async function createSprint(payload: Record<string, unknown>) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_sprints')
    .insert(payload)
    .select()
    .single();
  if (error) throw error;
  return data;
}

export async function updateSprint(id: number, payload: Record<string, unknown>) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_sprints')
    .update(payload)
    .eq('id', id)
    .select()
    .single();
  if (error) throw error;
  return data;
}

// ── Labels ────────────────────────────────────────────────────────────────────

export async function fetchLabels() {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_labels')
    .select('*')
    .order('name');
  if (error) throw error;
  return data ?? [];
}

export async function createLabel(name: string, color: string) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_labels')
    .insert({ name, color })
    .select()
    .single();
  if (error) throw error;
  return data;
}

// ── Comments ──────────────────────────────────────────────────────────────────

export async function fetchComments(issue_id: string) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_comments')
    .select('*')
    .eq('issue_id', issue_id)
    .order('created_at', { ascending: true });
  if (error) throw error;
  return data ?? [];
}

export async function createComment(issue_id: string, body_md: string, author = 'user', is_ai = false) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from('jira_comments')
    .insert({ issue_id, body_md, author, is_ai })
    .select()
    .single();
  if (error) throw error;
  return data;
}
