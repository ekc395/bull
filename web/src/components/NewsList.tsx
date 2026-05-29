// List of recent news articles for a ticker, fetched via /news/{ticker}.
"use client";

import { useNews } from "@/lib/queries";

export function NewsList({
  ticker,
  limit,
  compact = false,
}: {
  ticker: string;
  limit?: number;
  compact?: boolean;
}) {
  const news = useNews(ticker);

  if (news.isLoading) {
    return <p className="p-4 text-sm text-muted">Loading news…</p>;
  }
  if (news.isError) {
    return (
      <p className="p-4 text-sm text-bear">
        Failed to load news for {ticker}.
      </p>
    );
  }
  const all = news.data?.items ?? [];
  const items = limit ? all.slice(0, limit) : all;
  if (items.length === 0) {
    return <p className="p-4 text-sm text-muted">No recent headlines.</p>;
  }

  return (
    <ul className="overflow-hidden rounded-md border border-border bg-panel">
      {items.map((item, i) => (
        <li
          key={`${item.url}-${i}`}
          className="border-b border-border last:border-0"
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className={
              "block space-y-1 px-4 transition-colors hover:bg-elevated " +
              (compact ? "py-2.5" : "py-4")
            }
          >
            <div className="break-words text-sm font-medium text-primary">
              {item.title}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
              <span className="break-words">{item.source}</span>
              <span>·</span>
              <span>{new Date(item.published_at).toLocaleString()}</span>
            </div>
          </a>
        </li>
      ))}
    </ul>
  );
}
