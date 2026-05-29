import type { ReactNode } from "react";

import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-app text-primary">
      <TopBar />
      <main className="mx-auto w-full max-w-[1440px] px-4 py-6">{children}</main>
      <footer className="border-t border-border px-4 py-6 text-center text-[11px] text-muted">
        Not financial advice. For research and educational use only.
      </footer>
    </div>
  );
}
