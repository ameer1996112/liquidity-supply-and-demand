import type { Metadata } from 'next';
import { QueryProvider } from '@/providers/QueryProvider';
import { SidebarProvider } from '@/providers/SidebarProvider';
import { AppShell } from '@/components/layout/AppShell';
import { ToastProvider } from '@/components/ui/toast';
import { AlertProvider } from '@/components/alerts/AlertProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'TradeOps | Trading Dashboard',
  description: 'Professional trading bot monitoring and analytics dashboard',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased font-sans">
        <QueryProvider>
          <ToastProvider>
            <AlertProvider>
              <SidebarProvider>
                <AppShell>{children}</AppShell>
              </SidebarProvider>
            </AlertProvider>
          </ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
