import type { Metadata } from 'next';
import { QueryProvider } from '@/providers/QueryProvider';
import { SidebarProvider } from '@/providers/SidebarProvider';
import { TradingModeProvider } from '@/providers/TradingModeProvider';
import { ThemeProvider } from '@/providers/ThemeProvider';
import { ShellActionsProvider } from '@/providers/ShellActionsProvider';
import { AppShell } from '@/components/layout/AppShell';
import { ToastProvider } from '@/components/ui/toast';
import { AlertProvider } from '@/components/alerts/AlertProvider';
import { TimezoneProvider } from '@/providers/TimezoneProvider';
import { ActiveAccountProvider } from '@/providers/ActiveAccountProvider';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import '@fontsource/jetbrains-mono/600.css';
import '@fontsource/space-grotesk/400.css';
import '@fontsource/space-grotesk/500.css';
import '@fontsource/space-grotesk/600.css';
import '@fontsource/space-grotesk/700.css';
import '@fontsource/outfit/300.css';
import '@fontsource/outfit/400.css';
import '@fontsource/outfit/500.css';
import './globals.css';
import '@/styles/sovereign-terminal.css';

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
	    <html
	      lang='en'
	      data-theme='dark'
	      className='dark'
	    >
      <body className='antialiased font-sans'>
        <QueryProvider>
          <ToastProvider>
            <AlertProvider>
              <ThemeProvider>
                <TimezoneProvider>
                  <SidebarProvider>
                    <ActiveAccountProvider>
                    <TradingModeProvider>
                      <ShellActionsProvider>
                        <AppShell>{children}</AppShell>
                      </ShellActionsProvider>
                    </TradingModeProvider>
                    </ActiveAccountProvider>
                  </SidebarProvider>
                </TimezoneProvider>
              </ThemeProvider>
            </AlertProvider>
          </ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
