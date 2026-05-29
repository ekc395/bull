// Collapsible cards: thesis, technical, fundamentals_and_supply_chain, news_sentiment, risks,
// plus deterministic key levels (support / resistance) from the verdict.
import type { KeyLevels, Level, Report } from "@/types/api";

const SECTIONS: { key: keyof Report; label: string }[] = [
  { key: "reasoning", label: "Thesis" },
  { key: "technical", label: "Technical" },
  { key: "fundamentals_and_supply_chain", label: "Fundamentals & supply chain" },
  { key: "news_sentiment", label: "News sentiment" },
  { key: "risks", label: "Risks" },
];

export function ReportSections({
  report,
  keyLevels,
  includeKeyLevels = true,
}: {
  report: Report;
  keyLevels: KeyLevels;
  includeKeyLevels?: boolean;
}) {
  return (
    <div className="space-y-2">
      {SECTIONS.map(({ key, label }, idx) => {
        const body = report[key];
        if (!body) return null;
        return (
          <details
            key={key}
            open={idx === 0}
            className="group rounded-md border border-border bg-panel"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-sm font-medium text-primary hover:bg-elevated">
              <span>{label}</span>
              <span className="text-xs text-muted transition-transform group-open:rotate-180">
                ▾
              </span>
            </summary>
            <div className="whitespace-pre-wrap border-t border-border px-4 py-3 text-sm leading-relaxed text-secondary">
              {body}
            </div>
          </details>
        );
      })}

      {includeKeyLevels && (
        <details className="group rounded-md border border-border bg-panel">
          <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-sm font-medium text-primary hover:bg-elevated">
            <span>Key levels</span>
            <span className="text-xs text-muted transition-transform group-open:rotate-180">
              ▾
            </span>
          </summary>
          <div className="grid gap-4 border-t border-border p-4 sm:grid-cols-2">
            <LevelColumn title="Support" tone="bull" levels={keyLevels.support} />
            <LevelColumn title="Resistance" tone="bear" levels={keyLevels.resistance} />
          </div>
        </details>
      )}
    </div>
  );
}

export function KeyLevelsPanel({ keyLevels }: { keyLevels: KeyLevels }) {
  return (
    <div className="rounded-md border border-border bg-panel">
      <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        Key levels
      </h3>
      <div className="grid gap-4 p-4 sm:grid-cols-2">
        <LevelColumn title="Support" tone="bull" levels={keyLevels.support} />
        <LevelColumn title="Resistance" tone="bear" levels={keyLevels.resistance} />
      </div>
    </div>
  );
}

function LevelColumn({
  title,
  tone,
  levels,
}: {
  title: string;
  tone: "bull" | "bear";
  levels: Level[];
}) {
  const dot = tone === "bull" ? "bg-bull" : "bg-bear";
  return (
    <div>
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {title}
      </h4>
      {levels.length === 0 ? (
        <p className="text-xs text-muted">None identified.</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {levels.map((lvl, i) => (
            <li key={`${lvl.price}-${i}`} className="flex items-start gap-2">
              <span className={`mt-1.5 inline-block h-2 w-2 rounded-full ${dot}`} />
              <div className="flex-1">
                <div className="font-mono font-medium text-primary">
                  ${lvl.price.toFixed(2)}
                </div>
                {lvl.note && (
                  <div className="text-xs text-secondary">{lvl.note}</div>
                )}
                {lvl.touch_count != null && (
                  <div className="text-xs text-muted">
                    {lvl.touch_count} touch{lvl.touch_count === 1 ? "" : "es"}
                    {lvl.last_touch_date ? ` · last ${lvl.last_touch_date}` : ""}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
