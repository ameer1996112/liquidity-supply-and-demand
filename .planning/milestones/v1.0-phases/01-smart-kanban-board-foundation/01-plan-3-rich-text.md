# Phase 1 Plan 3: Markdown Preview Editor in IssueDrawer

## Goal
Replace the plain `<textarea>` for ticket description in IssueDrawer with a toggle-able markdown editor (Edit mode = raw textarea, Preview mode = rendered HTML). Auto-saves on blur.

## Requirements
- UI-04: Rich text editor for ticket descriptions and inline comments

## Implementation

### File: `jira/src/components/IssueDrawer.tsx`

Add `mdPreview` state and toggle button, replace the existing description textarea block:

**State to add:**
```typescript
const [mdPreview, setMdPreview] = useState(false);
```

**Replace the description textarea section with:**
```tsx
{/* Description */}
<div className="space-y-1">
  <div className="flex items-center justify-between">
    <span className="text-[10px] font-mono text-[#475569] uppercase tracking-wider">Description</span>
    <button
      onClick={() => setMdPreview((p) => !p)}
      className="text-[9px] font-mono text-[#475569] hover:text-[#94a3b8] border border-[#1f2335] rounded px-1.5 py-0.5 transition-colors"
    >
      {mdPreview ? 'Edit' : 'Preview'}
    </button>
  </div>
  {mdPreview ? (
    <div
      className="min-h-[80px] rounded-lg border border-[#1f2335] bg-[#13161e] px-3 py-2 text-[12px] text-[#e2e8f0] leading-relaxed prose-dark"
      dangerouslySetInnerHTML={{
        __html: simpleMarkdown(local.description ?? '_No description_'),
      }}
    />
  ) : (
    <textarea
      value={local.description ?? ''}
      onChange={(e) => setLocal((p) => ({ ...p, description: e.target.value }))}
      onBlur={() => handleSave('description', local.description)}
      rows={4}
      placeholder="Add description (markdown supported)..."
      className="w-full rounded-lg border border-[#1f2335] bg-[#13161e] px-3 py-2 text-[12px] text-[#e2e8f0] placeholder-[#475569] resize-none focus:border-[#2a2d3e] focus:outline-none transition-colors"
    />
  )}
</div>
```

**Add simple markdown renderer (above component in file):**
```typescript
function simpleMarkdown(md: string): string {
  return md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3 style="font-size:13px;font-weight:700;margin:8px 0 4px;color:#e2e8f0">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:14px;font-weight:700;margin:10px 0 5px;color:#e2e8f0">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="font-size:15px;font-weight:700;margin:12px 0 6px;color:#e2e8f0">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#f1f5f9">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em style="color:#cbd5e1">$1</em>')
    .replace(/`(.+?)`/g, '<code style="font-family:monospace;font-size:11px;background:#1a1d28;border:1px solid #1f2335;border-radius:3px;padding:0 4px;color:#94a3b8">$1</code>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:12px;color:#cbd5e1">$1</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}
```

## Verification
- Open any ticket drawer — description area now has Edit/Preview toggle
- Switch to Preview — markdown renders with bold, italic, code, headings
- Edit and blur — description saves
- Comments section shows AI comments with purple "AI" tint (already in IssueDrawer)
