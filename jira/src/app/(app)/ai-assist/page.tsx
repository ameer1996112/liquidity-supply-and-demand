'use client';

import { useState } from 'react';
import { Bot, Send, Sparkles, Clock, RefreshCw, Plus, Zap, AlertTriangle, GitBranch } from 'lucide-react';
import { cn } from '@/lib/utils';
import { createIssue } from '@/lib/supabase';
import { type IssueType, type IssuePriority } from '@/lib/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface AiAction {
  id: string;
  type: 'create_ticket' | 'bulk_create' | 'gsd_sync' | 'incident' | 'sprint_plan';
  label: string;
  description: string;
  icon: typeof Bot;
  color: string;
  execute: () => Promise<string>;
}

interface Message {
  role: 'user' | 'ai';
  text: string;
  timestamp: string;
}

export default function AiAssistPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', text: 'Hey! I\'m your AI PM assistant. I can create tickets, sync GSD phases to Jira, report incidents, and help plan your sprint. What do you need?', timestamp: new Date().toISOString() },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const addMessage = (role: 'user' | 'ai', text: string) => {
    setMessages((prev) => [...prev, { role, text, timestamp: new Date().toISOString() }]);
  };

  const runAction = async (action: AiAction) => {
    setIsLoading(true);
    addMessage('user', `Run: ${action.label}`);
    try {
      const result = await action.execute();
      addMessage('ai', result);
    } catch (err) {
      addMessage('ai', `⚠️ Action failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    addMessage('user', text);
    setIsLoading(true);
    try {
      // Simple NLP-style routing
      const lower = text.toLowerCase();
      let reply = '';

      if (lower.includes('create ticket') || lower.includes('new issue') || lower.includes('add task')) {
        // Extract title from message
        const title = text.replace(/create ticket|new issue|add task/gi, '').trim() || 'New task from AI Assist';
        const created = await createIssue({ title, type: 'task', priority: 'medium', labels: ['ai-created'] });
        reply = `✅ Created ticket **${(created as { id: string }).id}**: "${title}"\n\nThe ticket is now visible on the board with label \`ai-created\`.`;
      } else if (lower.includes('sync') && lower.includes('gsd')) {
        const res = await fetch(`${API_BASE}/api/tickets/gsd-sync`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phase_num: '?', phase_name: 'Manual sync', event: 'phase_start', goal: text }),
        });
        const data = await res.json();
        reply = res.ok
          ? `✅ GSD sync triggered. Jira ticket: **${data.ticket_id ?? 'created'}** (${data.action ?? 'ok'})`
          : `⚠️ Sync failed: ${data.detail ?? 'API error'}`;
      } else if (lower.includes('incident') || lower.includes('report error') || lower.includes('bug found')) {
        const res = await fetch(`${API_BASE}/api/incidents`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'generic', title: text, summary: text, source: 'ai-assist', priority: 'P3' }),
        });
        const data = await res.json();
        reply = res.ok
          ? `✅ Incident reported (${data.incident_id}).\n${data.jira_key ? `Jira ticket: **${data.jira_key}**` : 'Jira API unavailable — incident logged locally.'}`
          : `⚠️ Report failed.`;
      } else if (lower.includes('sprint') && (lower.includes('plan') || lower.includes('status'))) {
        const res = await fetch(`${API_BASE}/api/tickets/active-sprint`);
        const data = await res.json();
        reply = res.ok && data.sprint_id
          ? `📋 Active sprint: **${data.name}** (ID: ${data.sprint_id})\n\nOpen the Analytics page to see sprint velocity and completion metrics.`
          : '📋 No active sprint found. Create one in the Sprints page.';
      } else if (lower.includes('help') || lower.includes('what can you do')) {
        reply = `I can help you with:\n\n• **Create ticket** — "Create ticket: Fix login bug"\n• **Report incident** — "Report incident: Worker crashed with OOM"\n• **Sync GSD** — "Sync GSD phase 3 to Jira"\n• **Sprint status** — "What's the sprint status?"\n\nOr click one of the quick actions below 👇`;
      } else {
        reply = `Got it: "${text}"\n\nI don't have a specific handler for that yet. Try: "Create ticket: [title]", "Report incident: [description]", or "Sprint status".`;
      }
      addMessage('ai', reply);
    } catch (err) {
      addMessage('ai', `⚠️ Error: ${err instanceof Error ? err.message : 'Unknown'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const QUICK_ACTIONS: AiAction[] = [
    {
      id: 'sync-epics',
      type: 'gsd_sync',
      label: 'Sync Roadmap Epics',
      description: 'Create Jira epics for all ROADMAP.md phases',
      icon: GitBranch,
      color: '#a78bfa',
      execute: async () => {
        const res = await fetch(`${API_BASE}/api/tickets/gsd-sync-epics`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '[]',
        });
        const data = await res.json();
        return res.ok ? `✅ Synced ${data.count ?? 0} roadmap epics to Jira.` : `⚠️ Sync failed`;
      },
    },
    {
      id: 'create-bug',
      type: 'create_ticket',
      label: 'Quick Bug Ticket',
      description: 'Create a high-priority bug ticket now',
      icon: AlertTriangle,
      color: '#ef4444',
      execute: async () => {
        const title = prompt('Bug title:') ?? 'Untitled bug';
        const created = await createIssue({ title, type: 'bug' as IssueType, priority: 'high' as IssuePriority, labels: ['ai-created'] });
        return `✅ Bug ticket created: **${(created as { id: string }).id}** — "${title}"`;
      },
    },
    {
      id: 'report-incident',
      type: 'incident',
      label: 'Report Incident',
      description: 'Report a system incident to auto-create P2 ticket',
      icon: Zap,
      color: '#f59e0b',
      execute: async () => {
        const title = prompt('Incident title:') ?? 'Unnamed incident';
        const res = await fetch(`${API_BASE}/api/incidents`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'generic', title, summary: title, source: 'ai-assist', priority: 'P2' }),
        });
        const data = await res.json();
        return res.ok
          ? `✅ Incident reported. ${data.jira_key ? `Jira: **${data.jira_key}**` : '(no Jira)'}`
          : '⚠️ API unavailable';
      },
    },
  ];

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 border-b border-[#1f2335] px-6 py-3 shrink-0">
        <Bot className="h-4 w-4 text-violet-400" />
        <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">AI Assist</h1>
        <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-violet-500/30 text-violet-400/80">BETA</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Chat panel */}
        <div className="flex flex-col flex-1 border-r border-[#1f2335]">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={cn('flex gap-2.5', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                {msg.role === 'ai' && (
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/15 border border-violet-500/30 mt-0.5">
                    <Bot className="h-3 w-3 text-violet-400" />
                  </div>
                )}
                <div className={cn(
                  'max-w-[75%] rounded-xl px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap',
                  msg.role === 'user'
                    ? 'bg-amber-500/10 border border-amber-500/20 text-amber-100'
                    : 'bg-[#1a1d28] border border-[#1f2335] text-[#e2e8f0]'
                )}>
                  {msg.text}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-2.5">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/15 border border-violet-500/30 mt-0.5">
                  <RefreshCw className="h-3 w-3 text-violet-400 animate-spin" />
                </div>
                <div className="bg-[#1a1d28] border border-[#1f2335] rounded-xl px-3 py-2">
                  <span className="text-[10px] font-mono text-[#475569] animate-pulse">thinking…</span>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-[#1f2335] p-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="Create ticket, report incident, sync GSD..."
              className="flex-1 rounded-lg border border-[#1f2335] bg-[#0d0f14] px-3 py-2 text-[12px] text-[#e2e8f0] placeholder-[#475569] focus:border-violet-500/40 focus:outline-none transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="flex items-center justify-center h-9 w-9 rounded-lg border border-violet-500/30 bg-violet-500/10 text-violet-400 hover:bg-violet-500/20 transition-colors disabled:opacity-40"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Quick actions sidebar */}
        <div className="w-56 shrink-0 p-3 space-y-3">
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] px-1">Quick Actions</p>
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.id}
                onClick={() => runAction(action)}
                disabled={isLoading}
                className="w-full flex flex-col gap-1 rounded-xl border border-[#1f2335] bg-[#13161e] p-3 text-left hover:border-[#2a2d3e] hover:bg-[#1a1d28] transition-colors disabled:opacity-50"
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-3.5 w-3.5" style={{ color: action.color }} />
                  <span className="text-[11px] font-medium text-[#e2e8f0]">{action.label}</span>
                </div>
                <p className="text-[9px] font-mono text-[#475569] leading-relaxed">{action.description}</p>
              </button>
            );
          })}

          <div className="border-t border-[#1f2335] pt-3">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] px-1 mb-2">Recent Actions</p>
            {messages.filter((m) => m.role === 'user').slice(-3).reverse().map((m, i) => (
              <div key={i} className="flex items-start gap-1.5 py-1">
                <Clock className="h-2.5 w-2.5 text-[#475569] shrink-0 mt-0.5" />
                <p className="text-[9px] font-mono text-[#475569] line-clamp-2">{m.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
