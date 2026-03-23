import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Jira · TradeOps',
  description: 'Project management for TradeOps',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen flex overflow-hidden bg-[#0d0f14]">
        {children}
      </body>
    </html>
  );
}
