import type { Metadata } from "next";

import { QueryProvider } from "../components/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bull",
  description: "Swing trading agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
