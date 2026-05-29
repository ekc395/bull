"use client";

import {
  createContext,
  useCallback,
  useContext,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

interface TabsCtx {
  value: string;
  setValue: (v: string) => void;
  baseId: string;
  registerTrigger: (value: string, el: HTMLButtonElement | null) => void;
  focusAdjacent: (current: string, delta: 1 | -1) => void;
}

const Ctx = createContext<TabsCtx | null>(null);

function useTabs() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("Tabs components must be nested inside <Tabs>");
  return ctx;
}

export function Tabs({
  defaultValue,
  value: controlled,
  onValueChange,
  className,
  children,
}: {
  defaultValue: string;
  value?: string;
  onValueChange?: (v: string) => void;
  className?: string;
  children: ReactNode;
}) {
  const [internal, setInternal] = useState(defaultValue);
  const value = controlled ?? internal;
  const setValue = useCallback(
    (v: string) => {
      if (controlled === undefined) setInternal(v);
      onValueChange?.(v);
    },
    [controlled, onValueChange],
  );

  const baseId = useId();
  const triggers = useRef<Map<string, HTMLButtonElement>>(new Map());

  const registerTrigger = useCallback(
    (val: string, el: HTMLButtonElement | null) => {
      if (el) triggers.current.set(val, el);
      else triggers.current.delete(val);
    },
    [],
  );

  const focusAdjacent = useCallback((current: string, delta: 1 | -1) => {
    const order = Array.from(triggers.current.keys());
    const idx = order.indexOf(current);
    if (idx === -1) return;
    const next = order[(idx + delta + order.length) % order.length];
    triggers.current.get(next)?.focus();
  }, []);

  const ctx = useMemo(
    () => ({ value, setValue, baseId, registerTrigger, focusAdjacent }),
    [value, setValue, baseId, registerTrigger, focusAdjacent],
  );

  return (
    <Ctx.Provider value={ctx}>
      <div className={className}>{children}</div>
    </Ctx.Provider>
  );
}

export function TabsList({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      role="tablist"
      className={cn(
        "flex items-center gap-6 border-b border-border",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function TabsTrigger({
  value,
  className,
  children,
}: {
  value: string;
  className?: string;
  children: ReactNode;
}) {
  const t = useTabs();
  const selected = t.value === value;
  const id = `${t.baseId}-tab-${value}`;
  const panelId = `${t.baseId}-panel-${value}`;

  return (
    <button
      ref={(el) => t.registerTrigger(value, el)}
      type="button"
      role="tab"
      id={id}
      aria-controls={panelId}
      aria-selected={selected}
      tabIndex={selected ? 0 : -1}
      onClick={() => t.setValue(value)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") {
          e.preventDefault();
          t.focusAdjacent(value, 1);
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          t.focusAdjacent(value, -1);
        }
      }}
      className={cn(
        "relative -mb-px py-3 text-[13px] font-medium transition-colors focus:outline-none",
        selected
          ? "text-primary after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:bg-accent"
          : "text-muted hover:text-primary",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function TabsContent({
  value,
  className,
  children,
}: {
  value: string;
  className?: string;
  children: ReactNode;
}) {
  const t = useTabs();
  const id = `${t.baseId}-panel-${value}`;
  const labelledBy = `${t.baseId}-tab-${value}`;
  if (t.value !== value) return null;
  return (
    <div
      role="tabpanel"
      id={id}
      aria-labelledby={labelledBy}
      tabIndex={0}
      className={cn("focus:outline-none", className)}
    >
      {children}
    </div>
  );
}
