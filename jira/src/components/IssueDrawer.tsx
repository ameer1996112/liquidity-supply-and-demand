'use client';

import { useEffect, useState, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import {
  X, Bug, Sparkles, CheckSquare, ExternalLink,
  Bot, MessageSquare, Clock, ChevronDown, ChevronRight,
  Save, Trash2,
} from 'lucide-react';
import { cn, relativeTime } from '@/lib/utils';
import {
  type Issue, type Comment,
  PRIORITY_CONFIG, TYPE_CONFIG, STATUS_COLUMNS,
} from '@/lib/types';
import { fetchComments, createComment, updateIssue, deleteIssue } from '@/lib/supabase';

const TYPE_ICONS = { bug: Bug, feature: Sparkles, task: CheckSquare } as const;

interface Props {
  issue: Issue;
  onClose: () => void;
  onUpdate: (updated: Issue) => void;
  onDelete: (id: string) => void;
}

export function IssueDrawer({ issue, onClose, onUpdate, onDelete }: Props) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentDraft, setCommentDraft] = useState('');
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);
  const [showAiLog, setShowAiLog] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [localStatus, setLocalStatus] = useState(issue.status);
  const [localPriority, setLocalPriority] = useState(issue.priority);
  const [localTitle, setLocalTitle] = useState(issue.title);

  const TypeIcon = TYPE_ICONS[issue.type];
  const typeConfig = TYPE_CONFIG[issue.type];

  // Description editor
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: 'Add a description…' }),
    ],
    content: issue.description || '',
    editorProps: { attributes: { class: 'tiptap' } },
  });

  // Load comments
  useEffect(() => {
    fetchComments(issue.id).then(setComments).catch(console.error);
  }, [issue.id]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const updated = await updateIssue(issue.id, {
        title: localTitle,
        description: editor?.getHTML() || null,
        status: localStatus,
        priority: localPriority,
      });
      onUpdate(updated as Issue);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  }, [issue.id, localTitle, localStatus, localPriority, editor, onUpdate]);

  const handleAddComment = async () => {
    if (!commentDraft.trim()) return;
    setIsSubmittingComment(true);
    try {
      const c = await createComment(issue.id, commentDraft.trim());
      setComments((prev) => [...prev, c as Comment]);
      setCommentDraft('');
    } catch (e) {
      console.error(e);
    } finally {
      setIsSubmittingComment(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Archive this issue?')) return;
    await deleteIssue(issue.id);
    onDelete(issue.id);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div
        className="h-full w-full max-w-xl flex flex-col border-l border-[#1f2335] bg-[#13161e] animate-slide-in overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-start gap-3 border-b border-[#1f2335] p-4 shrink-0">
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded mt-0.5"
            style={{ background: typeConfig.bg }}
          >
            <TypeIcon className="h-4 w-4" style={{ color: typeConfig.color }} />
          </div>
          <div className="flex-1 min-w-0">
            <input
              value={localTitle}
              onChange={(e) => setLocalTitle(e.target.value)}
              className="w-full bg-transparent text-[14px] font-semibold text-[#e2e8f0] outline-none placeholder:text-[#475569] border-b border-transparent focus:border-[#1f2335]"
            />
            <p className="text-[10px] font-mono text-[#475569] mt-0.5 capitalize">
              {issue.type} · {relativeTime(issue.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={handleDelete}
              className="p-1.5 rounded text-[#475569] hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded text-[#475569] hover:text-[#e2e8f0] hover:bg-[#1a1d28] transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">

          {/* Meta grid */}
          <div className="grid grid-cols-2 gap-2">
            {/* Status */}
            <div className="space-y-1">
              <p className="text-[9px] font-mono uppercase tracking-widest text-[#475569]">Status</p>
              <select
                value={localStatus}
                onChange={(e) => setLocalStatus(e.target.value as typeof localStatus)}
                className="w-full rounded border border-[#1f2335] bg-[#1a1d28] px-2.5 py-1.5 text-[11px] font-mono text-[#e2e8f0] outline-none focus:border-amber-500/40"
              >
                {STATUS_COLUMNS.map((s) => (
                  <option key={s.key} value={s.key}>{s.label}</option>
                ))}
              </select>
            </div>
            {/* Priority */}
            <div className="space-y-1">
              <p className="text-[9px] font-mono uppercase tracking-widest text-[#475569]">Priority</p>
              <select
                value={localPriority}
                onChange={(e) => setLocalPriority(e.target.value as typeof localPriority)}
                className="w-full rounded border border-[#1f2335] bg-[#1a1d28] px-2.5 py-1.5 text-[11px] font-mono text-[#e2e8f0] outline-none focus:border-amber-500/40"
              >
                {(['critical', 'high', 'medium', 'low'] as const).map((p) => (
                  <option key={p} value={p}>{PRIORITY_CONFIG[p].label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Labels */}
          {issue.labels.length > 0 && (
            <div className="space-y-1">
              <p className="text-[9px] font-mono uppercase tracking-widest text-[#475569]">Labels</p>
              <div className="flex flex-wrap gap-1.5">
                {issue.labels.map((l) => (
                  <span key={l} className="text-[10px] font-mono px-2 py-0.5 rounded border border-[#1f2335] text-[#94a3b8]">{l}</span>
                ))}
              </div>
            </div>
          )}

          {/* Signal link */}
          {issue.signal_id && (
            <div className="flex items-center gap-2 rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2">
              <ExternalLink className="h-3.5 w-3.5 text-blue-400 shrink-0" />
              <span className="text-[11px] font-mono text-blue-400">Linked to Signal #{issue.signal_id}</span>
            </div>
          )}

          {/* Description (Tiptap) */}
          <div className="space-y-1.5">
            <p className="text-[9px] font-mono uppercase tracking-widest text-[#475569]">Description</p>
            <div className="rounded-lg border border-[#1f2335] bg-[#0d0f14] px-3 py-2.5 min-h-[100px]">
              <EditorContent editor={editor} />
            </div>
          </div>

          {/* ── AI Changelog ── */}
          {(issue.ai_changelog?.length ?? 0) > 0 && (
            <div className="space-y-2">
              <button
                onClick={() => setShowAiLog((v) => !v)}
                className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-violet-400"
              >
                <Bot className="h-3 w-3" />
                AI Changelog ({issue.ai_changelog?.length ?? 0})
                {showAiLog ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
              {showAiLog && (
                <div className="space-y-2">
                  {[...issue.ai_changelog].reverse().map((entry, i) => (
                    <div key={i} className="rounded-lg border border-violet-500/15 bg-violet-500/5 px-3 py-2.5 space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <Bot className="h-2.5 w-2.5 text-violet-400" />
                          <span className="text-[9px] font-mono text-violet-400 font-semibold">{entry.agent}</span>
                          <span className="text-[9px] font-mono text-[#475569]">{entry.old_status} → {entry.new_status}</span>
                        </div>
                        <div className="flex items-center gap-1 text-[#475569]">
                          <Clock className="h-2.5 w-2.5" />
                          <span className="text-[9px] font-mono">{relativeTime(entry.timestamp)}</span>
                        </div>
                      </div>
                      <p className="text-[11px] text-[#94a3b8] leading-relaxed">{entry.summary}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Comments ── */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-3.5 w-3.5 text-[#475569]" />
              <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569]">
                Comments ({comments.length})
              </p>
            </div>

            {comments.map((c) => (
              <div key={c.id} className="space-y-1">
                <div className="flex items-center gap-2">
                  {c.is_ai ? (
                    <Bot className="h-3 w-3 text-violet-400" />
                  ) : (
                    <div className="h-4 w-4 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                      <span className="text-[8px] font-bold text-amber-400">{c.author[0].toUpperCase()}</span>
                    </div>
                  )}
                  <span className={cn('text-[10px] font-semibold font-mono', c.is_ai ? 'text-violet-400' : 'text-[#94a3b8]')}>
                    {c.is_ai ? `${c.author} (AI)` : c.author}
                  </span>
                  <span className="text-[9px] font-mono text-[#475569]">{relativeTime(c.created_at)}</span>
                </div>
                <div className="ml-6 text-[12px] text-[#94a3b8] leading-relaxed whitespace-pre-wrap">
                  {c.body_md}
                </div>
              </div>
            ))}

            {/* Add comment */}
            <div className="space-y-2">
              <textarea
                value={commentDraft}
                onChange={(e) => setCommentDraft(e.target.value)}
                placeholder="Add a comment…"
                rows={2}
                className="w-full rounded-lg border border-[#1f2335] bg-[#0d0f14] px-3 py-2 text-[12px] text-[#e2e8f0] placeholder:text-[#475569] outline-none focus:border-amber-500/30 resize-none"
              />
              <button
                onClick={handleAddComment}
                disabled={isSubmittingComment || !commentDraft.trim()}
                className="text-[10px] font-mono font-semibold uppercase tracking-wider px-3 py-1.5 rounded border border-[#1f2335] text-[#94a3b8] hover:text-[#e2e8f0] hover:border-[#2a2d3e] transition-colors disabled:opacity-40"
              >
                {isSubmittingComment ? 'Posting…' : 'Post'}
              </button>
            </div>
          </div>
        </div>

        {/* ── Save bar ── */}
        <div className="border-t border-[#1f2335] px-4 py-3 flex gap-2 shrink-0">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-4 py-1.5 text-[11px] font-mono font-semibold uppercase tracking-wider text-amber-400 hover:bg-amber-500/15 transition-colors disabled:opacity-50"
          >
            <Save className="h-3 w-3" />
            {isSaving ? 'Saving…' : 'Save'}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded border border-[#1f2335] text-[11px] font-mono text-[#475569] hover:text-[#94a3b8] transition-colors"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
