"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";

import { formatUsd } from "@/lib/format";
import { TickerLogo } from "@/components/TickerLogo";
import { useAccount } from "@/lib/queries";

export function TopBar() {
  const router = useRouter();
  const account = useAccount();
  const [q, setQ] = useState("");

  // Debounce the live logo preview so it doesn't fire a request per keystroke.
  const [preview, setPreview] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setPreview(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const sym = q.trim().toUpperCase();
    if (!sym) return;
    router.push(`/ticker/${encodeURIComponent(sym)}`);
    setQ("");
  }

  return (
    <header className="sticky top-0 z-40 h-12 border-b border-border bg-app/90 backdrop-blur">
      <div className="mx-auto flex h-full max-w-[1440px] items-center gap-6 px-4">
        <Link
          href="/"
          className="flex items-center gap-2 text-base font-bold tracking-tight text-primary"
        >
          <Image
            src="/logo.png"
            alt=""
            width={22}
            height={22}
            priority
            className="rounded-[5px]"
          />
          Bull
        </Link>

        <form onSubmit={onSubmit} className="max-w-md flex-1">
          <label className="flex items-center gap-2 rounded-full border border-border bg-elevated px-3 py-1.5">
            {preview ? (
              <TickerLogo ticker={preview} size={18} />
            ) : (
              <Search className="h-3.5 w-3.5 text-muted" aria-hidden />
            )}
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value.toUpperCase())}
              placeholder="Search ticker (e.g. NVDA)"
              className="w-full bg-transparent text-[13px] text-primary placeholder:text-muted focus:outline-none"
              maxLength={10}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
        </form>

        <div className="ml-auto hidden items-center gap-4 text-xs text-secondary sm:flex">
          {account.data ? (
            <>
              <span className="flex items-baseline gap-1.5">
                <span className="text-muted">Equity</span>
                <span className="font-mono text-primary">
                  {formatUsd(account.data.equity)}
                </span>
              </span>
              <span className="h-3 w-px bg-border-strong" />
              <span className="flex items-baseline gap-1.5">
                <span className="text-muted">Buying power</span>
                <span className="font-mono text-primary">
                  {formatUsd(account.data.buying_power)}
                </span>
              </span>
            </>
          ) : (
            <span className="text-muted">Paper</span>
          )}
        </div>
      </div>
    </header>
  );
}
