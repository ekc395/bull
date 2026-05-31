"use client";

// TradingView-style "About {company}" card: company profile facts (sector,
// industry, CEO, HQ, employees, IPO date, website) plus the business summary
// with a show-more toggle. Data from /fundamentals; renders nothing when the
// source has neither facts nor a description.

import { useState } from "react";

import { useFundamentals } from "@/lib/queries";
import type { FundamentalsResponse } from "@/types/api";

interface Item {
  label: string;
  value: string;
  href?: string;
}

const COLLAPSED = 360;

export function AboutCompanyCard({ ticker }: { ticker: string }) {
  const { data } = useFundamentals(ticker);
  const [expanded, setExpanded] = useState(false);

  if (!data) return null;
  const items = buildItems(data);
  const description = data.description?.trim() || "";
  if (items.length === 0 && !description) return null;

  const isLong = description.length > COLLAPSED;
  const shown =
    expanded || !isLong ? description : description.slice(0, COLLAPSED) + "…";

  return (
    <div className="overflow-hidden rounded-md border border-border bg-panel">
      <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        About {data.name || "the company"}
      </h3>

      {items.length > 0 && (
        <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3">
          {items.map((it) => (
            <div key={it.label} className="bg-panel p-4">
              <dt className="text-[11px] uppercase tracking-wide text-muted">
                {it.label}
              </dt>
              <dd className="mt-1 truncate text-sm font-medium text-primary">
                {it.href ? (
                  <a
                    href={it.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:text-accent-hover"
                  >
                    {it.value}
                  </a>
                ) : (
                  it.value
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {description && (
        <div className="border-t border-border p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-secondary">
            {shown}
          </p>
          {isLong && (
            <button
              type="button"
              onClick={() => setExpanded((s) => !s)}
              className="mt-2 text-xs font-medium text-accent hover:text-accent-hover"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function buildItems(d: FundamentalsResponse): Item[] {
  const items: Item[] = [];
  const push = (label: string, value?: string | null, href?: string) => {
    if (value) items.push({ label, value, href });
  };

  push("Sector", d.sector);
  push("Industry", d.industry);
  push("CEO", d.ceo);
  push("Headquarters", d.headquarters);
  push(
    "Employees",
    d.employees != null ? d.employees.toLocaleString("en-US") : null,
  );
  push("IPO date", formatDate(d.ipo_date));
  if (d.website) push("Website", hostname(d.website), d.website);

  return items;
}

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
