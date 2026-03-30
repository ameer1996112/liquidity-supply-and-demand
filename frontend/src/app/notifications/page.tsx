'use client';

import { Bell } from 'lucide-react';
import { RoutingPanel } from '@/components/notifications/RoutingPanel';
import { WhitelistPanel } from '@/components/notifications/WhitelistPanel';
import { CommandLogPanel } from '@/components/notifications/CommandLogPanel';

export default function NotificationsPage() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Bell className="h-4 w-4 text-[var(--to-text-dim)]" />
        <h1 className="text-sm font-semibold text-[var(--to-text-primary)]">Notification Settings</h1>
      </div>

      <RoutingPanel />
      <WhitelistPanel />
      <CommandLogPanel />
    </div>
  );
}
