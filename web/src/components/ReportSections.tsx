// Collapsible cards: technical, fundamentals_and_supply_chain, news_sentiment, risks, reasoning,
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
}: {
  report: Report;
  keyLevels: KeyLevels;
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
            className="group rounded-lg border bg-white"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-sm font-medium text-slate-800 hover:bg-slate-50">
              <span>{label}</span>
              <span className="text-xs text-slate-400 group-open:rotate-180 transition-transform">
                ▾
              </span>
            </summary>
            <div className="whitespace-pre-wrap border-t px-4 py-3 text-sm leading-relaxed text-slate-700">
              {body}
            </div>
          </details>
        );
      })}

      <details className="group rounded-lg border bg-white">
        <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-sm font-medium text-slate-800 hover:bg-slate-50">
          <span>Key levels</span>
          <span className="text-xs text-slate-400 group-open:rotate-180 transition-transform">
            ▾
          </span>
        </summary>
        <div className="grid gap-4 border-t p-4 sm:grid-cols-2">
          <LevelColumn title="Support" tone="emerald" levels={keyLevels.support} />
          <LevelColumn title="Resistance" tone="rose" levels={keyLevels.resistance} />
        </div>
      </details>
    </div>
  );
}

function LevelColumn({
  title,
  tone,
  levels,
}: {
  title: string;
  tone: "emerald" | "rose";
  levels: Level[];
}) {
  const dot = tone === "emerald" ? "bg-emerald-500" : "bg-rose-500";
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h4>
      {levels.length === 0 ? (
        <p className="text-xs text-slate-400">None identified.</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {levels.map((lvl, i) => (
            <li key={`${lvl.price}-${i}`} className="flex items-start gap-2">
              <span className={`mt-1.5 inline-block h-2 w-2 rounded-full ${dot}`} />
              <div className="flex-1">
                <div className="font-mono font-medium text-slate-800">
                  ${lvl.price.toFixed(2)}
                </div>
                {lvl.note && (
                  <div className="text-xs text-slate-600">{lvl.note}</div>
                )}
                {lvl.touch_count != null && (
                  <div className="text-xs text-slate-500">
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
