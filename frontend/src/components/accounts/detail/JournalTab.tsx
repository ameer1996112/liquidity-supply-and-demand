'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { BookOpen, Plus, Tag, Upload, X, Star, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { getPortfolioControlUrl } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface JournalTabProps {
  accountName: string;
}

interface JournalEntry {
  id: number;
  signal_id: number;
  symbol: string;
  note_text: string;
  tags: string[];
  screenshot_urls: string[];
  trade_rating: number | null;
  emotional_state: string | null;
  created_at: string;
  trade_outcome: 'win' | 'loss' | 'open';
  trade_pnl: number | null;
}

async function fetchJournalEntries(
  accountName: string,
  tagFilter?: string,
): Promise<JournalEntry[]> {
  const url = getPortfolioControlUrl(
    `/accounts/${encodeURIComponent(accountName)}/journal${tagFilter ? `?tag=${encodeURIComponent(tagFilter)}` : ''}`,
  );
  if (!url) throw new Error('Backend API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!res.ok)
    throw new Error(`Failed to fetch journal entries (${res.status})`);
  const data = await res.json();
  return data.entries || [];
}

async function createJournalEntry(
  accountName: string,
  entry: {
    signal_id?: number;
    note_text: string;
    tags?: string[];
    trade_rating?: number;
    emotional_state?: string;
  },
): Promise<JournalEntry> {
  const url = getPortfolioControlUrl(
    `/accounts/${encodeURIComponent(accountName)}/journal`,
  );
  if (!url) throw new Error('Backend API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok)
    throw new Error(`Failed to create journal entry (${res.status})`);
  return res.json();
}

async function deleteJournalEntry(journalId: number): Promise<void> {
  const url = getPortfolioControlUrl(`/journal/${journalId}`);
  if (!url) throw new Error('Backend API URL not configured');
  const res = await fetch(url, {
    method: 'DELETE',
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok)
    throw new Error(`Failed to delete journal entry (${res.status})`);
}

export function JournalTab({ accountName }: JournalTabProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [rating, setRating] = useState<number | null>(null);
  const [emotionalState, setEmotionalState] = useState('');
  const [tagFilter, setTagFilter] = useState<string | undefined>();
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const {
    data: entries,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['account-journal', accountName, tagFilter],
    queryFn: () => fetchJournalEntries(accountName, tagFilter),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (entry: Parameters<typeof createJournalEntry>[1]) =>
      createJournalEntry(accountName, entry),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['account-journal', accountName],
      });
      setShowAddForm(false);
      setNoteText('');
      setSelectedTags([]);
      setRating(null);
      setEmotionalState('');
      addToast({
        title: 'Journal entry added',
        message: 'Your note has been saved successfully',
        severity: 'success',
        duration: 4000,
      });
    },
    onError: (error: Error) => {
      addToast({
        title: 'Failed to save note',
        message: error.message,
        severity: 'critical',
        duration: 6000,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteJournalEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['account-journal', accountName],
      });
      addToast({
        title: 'Entry deleted',
        message: 'Journal entry has been removed',
        severity: 'success',
        duration: 3000,
      });
    },
    onError: (error: Error) => {
      addToast({
        title: 'Delete failed',
        message: error.message,
        severity: 'critical',
        duration: 5000,
      });
    },
  });

  const handleAddTag = () => {
    const tag = tagInput.trim();
    if (tag && !selectedTags.includes(tag)) {
      setSelectedTags([...selectedTags, tag]);
      setTagInput('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setSelectedTags(selectedTags.filter((t) => t !== tag));
  };

  const handleSubmit = () => {
    if (!noteText.trim()) {
      addToast({
        title: 'Note required',
        message: 'Please write a note before submitting',
        severity: 'warning',
        duration: 4000,
      });
      return;
    }

    createMutation.mutate({
      note_text: noteText,
      tags: selectedTags.length > 0 ? selectedTags : undefined,
      trade_rating: rating || undefined,
      emotional_state: emotionalState || undefined,
    });
  };

  // Extract all unique tags from entries
  const allTags = entries
    ? Array.from(new Set(entries.flatMap((e) => e.tags || [])))
    : [];

  return (
    <div className='space-y-6'>
      {/* Header */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-3'>
          <BookOpen className='h-4 w-4 text-emerald-500' />
          <h3 className='text-sm font-medium text-zinc-300'>Trading Journal</h3>
          {!isLoading && entries && (
            <span className='text-xs text-zinc-500'>
              {entries.length} entries
            </span>
          )}
        </div>
        <Button
          variant='outline'
          size='sm'
          className='border-[#2a2e39] text-zinc-400 hover:bg-[#2a2e39] hover:text-zinc-200'
          onClick={() => setShowAddForm(!showAddForm)}
        >
          <Plus className='h-3.5 w-3.5 mr-1.5' />
          Add Note
        </Button>
      </div>

      {/* Add Entry Form */}
      {showAddForm && (
        <div className='tv-card p-4 space-y-4'>
          <div>
            <label className='block text-xs text-zinc-500 mb-2'>Note</label>
            <textarea
              id='journal-note-text'
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder='What did you learn from this trade? What went well? What could improve?'
              rows={4}
              className='w-full px-3 py-2 text-sm rounded border border-[#2a2e39] bg-[#1e222d] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500'
            />
          </div>

          <div className='grid grid-cols-2 gap-4'>
            <div>
              <label className='block text-xs text-zinc-500 mb-2'>Tags</label>
              <div className='flex gap-2'>
                <input
                  id='journal-tag-input'
                  type='text'
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
                  placeholder='Add tag (e.g., revenge-trade)'
                  className='flex-1 px-3 py-1.5 text-sm rounded border border-[#2a2e39] bg-[#1e222d] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500'
                />
                <Button
                  variant='outline'
                  size='sm'
                  onClick={handleAddTag}
                  className='border-[#2a2e39]'
                >
                  <Plus className='h-3 w-3' />
                </Button>
              </div>
              {selectedTags.length > 0 && (
                <div className='flex flex-wrap gap-1.5 mt-2'>
                  {selectedTags.map((tag) => (
                    <span
                      key={tag}
                      className='px-2 py-1 text-xs font-mono rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1'
                    >
                      {tag}
                      <button onClick={() => handleRemoveTag(tag)}>
                        <X className='h-3 w-3' />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className='block text-xs text-zinc-500 mb-2'>
                Rating (1-5)
              </label>
              <div className='flex gap-1'>
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    onClick={() => setRating(n)}
                    className={cn(
                      'p-1.5 rounded transition-colors',
                      rating && n <= rating
                        ? 'text-amber-500'
                        : 'text-zinc-600 hover:text-amber-500',
                    )}
                  >
                    <Star
                      className='h-4 w-4'
                      fill={rating && n <= rating ? 'currentColor' : 'none'}
                    />
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className='block text-xs text-zinc-500 mb-2'>
              Emotional State (Optional)
            </label>
            <select
              id='journal-emotional-state'
              value={emotionalState}
              onChange={(e) => setEmotionalState(e.target.value)}
              className='w-full px-3 py-1.5 text-sm rounded border border-[#2a2e39] bg-[#1e222d] text-zinc-300 focus:outline-none focus:border-emerald-500'
            >
              <option value=''>Select state...</option>
              <option value='calm'>Calm & Focused</option>
              <option value='anxious'>Anxious</option>
              <option value='confident'>Confident</option>
              <option value='frustrated'>Frustrated</option>
              <option value='revenge'>Revenge Trading</option>
              <option value='fomo'>FOMO</option>
            </select>
          </div>

          <div className='flex items-center justify-end gap-2'>
            <Button
              variant='ghost'
              size='sm'
              onClick={() => setShowAddForm(false)}
              className='text-zinc-500'
            >
              Cancel
            </Button>
            <Button
              variant='outline'
              size='sm'
              onClick={handleSubmit}
              disabled={createMutation.isPending}
              className='border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10'
            >
              {createMutation.isPending ? 'Saving...' : 'Save Note'}
            </Button>
          </div>
        </div>
      )}

      {/* Tag Filter */}
      {allTags.length > 0 && (
        <div className='flex items-center gap-2'>
          <Tag className='h-3.5 w-3.5 text-zinc-500' />
          <span className='text-xs text-zinc-500'>Filter:</span>
          <button
            onClick={() => setTagFilter(undefined)}
            className={cn(
              'px-2 py-1 text-xs rounded',
              !tagFilter
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'text-zinc-500 hover:text-zinc-300',
            )}
          >
            All
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setTagFilter(tag)}
              className={cn(
                'px-2 py-1 text-xs font-mono rounded',
                tagFilter === tag
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-[#2a2e39]',
              )}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* Journal Entries List */}
      {isLoading ? (
        <div className='space-y-3'>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className='h-32 bg-[#1e222d]' />
          ))}
        </div>
      ) : error ? (
        <div className='rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600'>
          Journal endpoints not yet implemented. This will show your trade
          notes, tags, and ratings.
        </div>
      ) : !entries || entries.length === 0 ? (
        <div className='flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-16 text-zinc-500'>
          <BookOpen className='h-10 w-10 mb-3 opacity-50' />
          <p className='text-sm font-mono'>No journal entries yet</p>
          <p className='text-xs text-zinc-600 mt-1 max-w-md text-center'>
            Click "Add Note" to start documenting your trading journey. Track
            what works, what doesn't, and your emotional state.
          </p>
        </div>
      ) : (
        <div className='space-y-3'>
          {entries.map((entry) => (
            <div key={entry.id} className='tv-card p-4 space-y-3'>
              <div className='flex items-start justify-between'>
                <div className='flex-1'>
                  <div className='flex items-center gap-3 mb-2'>
                    <span className='font-mono text-xs font-semibold text-zinc-200'>
                      {entry.symbol || 'General Note'}
                    </span>
                    {entry.trade_outcome && entry.trade_outcome !== 'open' && (
                      <span
                        className={cn(
                          'px-1.5 py-0.5 text-[9px] font-mono rounded',
                          entry.trade_outcome === 'win'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20',
                        )}
                      >
                        {entry.trade_outcome.toUpperCase()}
                        {entry.trade_pnl &&
                          ` ${entry.trade_pnl >= 0 ? '+' : ''}$${entry.trade_pnl.toFixed(2)}`}
                      </span>
                    )}
                    {entry.trade_rating && (
                      <div className='flex items-center gap-0.5'>
                        {Array.from({ length: entry.trade_rating }).map(
                          (_, i) => (
                            <Star
                              key={i}
                              className='h-3 w-3 text-amber-500'
                              fill='currentColor'
                            />
                          ),
                        )}
                      </div>
                    )}
                    <span
                      suppressHydrationWarning
                      className='text-xs text-zinc-600'
                    >
                      {new Date(entry.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <p className='text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap'>
                    {entry.note_text}
                  </p>

                  {entry.emotional_state && (
                    <div className='mt-2 text-xs text-zinc-500'>
                      <span className='text-zinc-600'>Mood:</span>{' '}
                      {entry.emotional_state}
                    </div>
                  )}

                  {entry.tags && entry.tags.length > 0 && (
                    <div className='flex flex-wrap gap-1.5 mt-2'>
                      {entry.tags.map((tag, idx) => (
                        <span
                          key={idx}
                          className='px-1.5 py-0.5 text-[10px] font-mono rounded bg-zinc-700/30 text-zinc-400'
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => deleteMutation.mutate(entry.id)}
                  className='p-1.5 rounded hover:bg-[#2a2e39] text-zinc-600 hover:text-red-500 transition-colors'
                  title='Delete entry'
                >
                  <Trash2 className='h-3.5 w-3.5' />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Screenshot Upload Placeholder */}
      {showAddForm && (
        <div className='rounded-lg border border-dashed border-[#2a2e39] bg-[#1e222d]/30 px-4 py-8 text-center text-xs text-zinc-600'>
          <Upload className='h-6 w-6 mx-auto mb-2 text-zinc-600' />
          <p className='font-mono'>Screenshot Upload</p>
          <p className='mt-1'>Coming soon: Drag & drop chart screenshots</p>
        </div>
      )}
    </div>
  );
}
