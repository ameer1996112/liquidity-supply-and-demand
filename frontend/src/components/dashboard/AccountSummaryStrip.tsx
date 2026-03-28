'use client'

import { useRouter } from 'next/navigation'
import type { AccountSummaryItem } from '@/types/trading'

interface Props {
  accounts: AccountSummaryItem[]
  isLoading: boolean
}

const ACCOUNT_TYPE_COLORS: Record<string, string> = {
  funded: 'var(--acct-funded)',
  evaluation: 'var(--acct-evaluation)',
  personal: 'var(--acct-personal)',
}

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  funded: 'Funded',
  evaluation: 'Eval',
  personal: 'Personal',
}

function LiveDot({ status, runMode }: { status: string; runMode: string }) {
  const isLive = runMode === 'LIVE' && status === 'connected'
  return (
    <span
      style={{
        display: 'inline-block',
        width: 7,
        height: 7,
        borderRadius: '50%',
        backgroundColor: isLive
          ? 'var(--live-blue)'
          : status === 'error'
          ? 'var(--negative)'
          : 'var(--text-muted)',
        boxShadow: isLive ? '0 0 6px var(--live-blue)' : 'none',
        animation: isLive ? 'st-pulse 2s ease-in-out infinite' : 'none',
        flexShrink: 0,
      }}
    />
  )
}

function AccountCard({ account }: { account: AccountSummaryItem }) {
  const router = useRouter()
  const accentColor = ACCOUNT_TYPE_COLORS[account.account_type] || 'var(--acct-personal)'
  const pnlColor = account.pnl_today >= 0 ? 'var(--positive)' : 'var(--negative)'
  const pnlSign = account.pnl_today >= 0 ? '+' : ''

  return (
    <div
      onClick={() => router.push(`/accounts/${encodeURIComponent(account.name)}`)}
      style={{
        position: 'relative',
        minWidth: 200,
        maxWidth: 220,
        padding: '14px 16px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: 8,
        cursor: 'pointer',
        transition: 'transform 120ms ease, box-shadow 120ms ease, background 120ms ease',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        const el = e.currentTarget
        el.style.transform = 'translateY(-2px)'
        el.style.boxShadow = `0 4px 20px rgba(0,0,0,0.4), 0 0 0 1px ${accentColor}40`
        el.style.background = 'var(--bg-card-hover)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        el.style.transform = 'translateY(0)'
        el.style.boxShadow = 'none'
        el.style.background = 'var(--bg-card)'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        <LiveDot status={account.connection_status} runMode={account.run_mode} />
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {account.name}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 600,
            color: accentColor,
            background: `${accentColor}18`,
            padding: '2px 5px',
            borderRadius: 3,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            flexShrink: 0,
          }}
        >
          {ACCOUNT_TYPE_LABELS[account.account_type] || account.account_type}
        </span>
      </div>

      {/* PnL Today */}
      <div style={{ marginBottom: 8 }}>
        <div
          style={{
            fontSize: 10,
            color: 'var(--text-muted)',
            marginBottom: 2,
            fontFamily: 'var(--font-display)',
          }}
        >
          Today
        </div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 18,
            fontWeight: 600,
            color: pnlColor,
            letterSpacing: '-0.02em',
          }}
        >
          {pnlSign}${Math.abs(account.pnl_today).toFixed(2)}
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 12 }}>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            Positions
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
            {account.positions_count}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            Win Rate
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
            {account.win_rate}%
          </div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            Mode
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              fontWeight: 600,
              color: account.run_mode === 'LIVE' ? 'var(--live-blue)' : 'var(--text-muted)',
            }}
          >
            {account.run_mode}
          </div>
        </div>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div
      style={{
        minWidth: 200,
        height: 130,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: '3px solid var(--border)',
        borderRadius: 8,
        flexShrink: 0,
        animation: 'st-shimmer 1.5s ease-in-out infinite',
      }}
    />
  )
}

export function AccountSummaryStrip({ accounts, isLoading }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        overflowX: 'auto',
        paddingBottom: 4,
        scrollbarWidth: 'thin',
        scrollbarColor: 'var(--border) transparent',
      }}
    >
      <style>{`
        @keyframes st-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
        @keyframes st-shimmer {
          0%, 100% { opacity: 0.35; }
          50% { opacity: 0.6; }
        }
      `}</style>

      {isLoading ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : (
        <>
          {accounts.map(account => (
            <AccountCard key={account.id} account={account} />
          ))}
          <div
            onClick={() => (window.location.href = '/accounts')}
            style={{
              minWidth: 48,
              height: 130,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 8,
              cursor: 'pointer',
              color: 'var(--text-muted)',
              fontSize: 20,
              flexShrink: 0,
              transition: 'border-color 120ms ease, color 120ms ease',
            }}
            onMouseEnter={e => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--accent-gold)'
              el.style.color = 'var(--accent-gold)'
            }}
            onMouseLeave={e => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--border)'
              el.style.color = 'var(--text-muted)'
            }}
            title="Manage accounts"
          >
            +
          </div>
        </>
      )}
    </div>
  )
}
