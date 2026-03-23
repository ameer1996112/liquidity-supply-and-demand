import { Sidebar } from '@/components/Sidebar';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-full h-full">
          {children}
        </div>
      </main>
    </>
  );
}
