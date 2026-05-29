import type { Metadata } from "next";

import { AppShell } from "../components/AppShell";
import { QueryProvider } from "../components/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bull",
  description: "Swing trading agent",
  icons: { icon: "/logo.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-app text-primary antialiased">
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
