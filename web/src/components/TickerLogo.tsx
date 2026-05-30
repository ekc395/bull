"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const LOGO_TOKEN = process.env.NEXT_PUBLIC_LOGO_DEV_TOKEN;

// Muted, dark-UI-friendly backgrounds for the monogram fallback. Light text on top.
const MONOGRAM_COLORS = [
  "#2F4A7A",
  "#1F6F6A",
  "#4A3B6B",
  "#6B3B4A",
  "#3B6B4A",
  "#6B5333",
  "#3B4A6B",
  "#5A3B5A",
];

// Stable hash so a given ticker always lands on the same color.
function colorFor(ticker: string): string {
  let hash = 0;
  for (let i = 0; i < ticker.length; i++) {
    hash = (hash * 31 + ticker.charCodeAt(i)) | 0;
  }
  return MONOGRAM_COLORS[Math.abs(hash) % MONOGRAM_COLORS.length];
}

// First two alphanumeric characters (handles symbols like BRK.B).
function monogram(ticker: string): string {
  const letters = ticker.toUpperCase().replace(/[^A-Z0-9]/g, "");
  return letters.slice(0, 2) || "?";
}

function logoUrl(ticker: string, size: number): string | null {
  if (!LOGO_TOKEN) return null;
  const params = new URLSearchParams({
    token: LOGO_TOKEN,
    retina: "true",
    format: "png",
    size: String(size * 2),
    fallback: "404", // 404 instead of logo.dev's own placeholder → our monogram fires
  });
  return `https://img.logo.dev/ticker/${encodeURIComponent(ticker)}?${params}`;
}

export function TickerLogo({
  ticker,
  size = 24,
  className,
}: {
  ticker: string;
  size?: number;
  className?: string;
}) {
  const [errored, setErrored] = useState(false);

  // Reset the error state when the ticker changes (e.g. live search preview).
  useEffect(() => {
    setErrored(false);
  }, [ticker]);

  const url = logoUrl(ticker, size);
  const showFallback = !url || errored;

  if (showFallback) {
    return (
      <span
        aria-hidden
        className={cn(
          "inline-flex shrink-0 items-center justify-center rounded-[5px] font-semibold uppercase leading-none text-white/90",
          className,
        )}
        style={{
          width: size,
          height: size,
          backgroundColor: colorFor(ticker.toUpperCase()),
          fontSize: Math.max(9, Math.round(size * 0.42)),
        }}
      >
        {monogram(ticker)}
      </span>
    );
  }

  return (
    <Image
      src={url}
      alt=""
      width={size}
      height={size}
      onError={() => setErrored(true)}
      className={cn("shrink-0 rounded-[5px] object-contain", className)}
      style={{ width: size, height: size }}
      unoptimized
    />
  );
}
