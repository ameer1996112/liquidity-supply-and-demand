// Terminal route gets its own layout — bypasses the global AppShell
// so the dashboard can be truly full-screen with no sidebar/topbar chrome.
export default function TerminalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
