// List of recent news articles for a ticker, fetched via /news/{ticker}.
"use client";

import { useNews } from "@/lib/queries";

export function NewsList({ ticker }: { ticker: string }) {
  const news = useNews(ticker);

  if (news.isLoading) {
    return <p className="p-4 text-sm text-slate-500">Loading news…</p>;
  }
  if (news.isError) {
    return (
      <p className="p-4 text-sm text-red-600">
        Failed to load news for {ticker}.
      </p>
    );
  }
  const items = news.data?.items ?? [];
  if (items.length === 0) {
    return <p className="p-4 text-sm text-slate-500">No recent headlines.</p>;
  }

  return (
    <ul className="divide-y">
      {items.map((item, i) => (
        <li key={`${item.url}-${i}`} className="p-4">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block space-y-1 hover:underline"
          >
            <div className="break-words text-sm font-medium text-slate-900">
              {item.title}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
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
