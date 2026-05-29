// Compact top-3 support / resistance card for the Overview sidebar.
import type { KeyLevels, Level } from "@/types/api";

export function KeyLevelsMini({ keyLevels }: { keyLevels: KeyLevels }) {
  const supports = keyLevels.support.slice(0, 3);
  const resistances = keyLevels.resistance.slice(0, 3);

  return (
    <div className="rounded-md border border-border bg-panel">
      <h3 className="border-b border-border px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
        Key levels
      </h3>
      <div className="grid grid-cols-2 divide-x divide-border">
        <Column title="Support" tone="bull" levels={supports} />
        <Column title="Resistance" tone="bear" levels={resistances} />
      </div>
    </div>
  );
}

function Column({
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
    <div className="p-3">
      <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">
        {title}
      </h4>
      {levels.length === 0 ? (
        <p className="text-xs text-muted">None.</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {levels.map((lvl, i) => (
            <li key={`${lvl.price}-${i}`} className="flex items-center gap-2">
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} />
              <span className="font-mono text-primary">
                ${lvl.price.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
