"use client";

import type { ReactNode } from "react";

import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

const TAB_DEFS = [
  { value: "overview", label: "Overview" },
  { value: "technicals", label: "Technicals" },
  { value: "report", label: "Report" },
  { value: "news", label: "News" },
] as const;

export type SymbolTabValue = (typeof TAB_DEFS)[number]["value"];

export function SymbolTabs({
  defaultValue = "overview",
  overview,
  technicals,
  report,
  news,
}: {
  defaultValue?: SymbolTabValue;
  overview: ReactNode;
  technicals: ReactNode;
  report: ReactNode;
  news: ReactNode;
}) {
  return (
    <Tabs defaultValue={defaultValue} className="mt-4">
      <div className="sticky top-12 z-30 -mx-4 border-b border-border bg-app/95 px-4 backdrop-blur">
        <TabsList className="border-0">
          {TAB_DEFS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      <TabsContent value="overview" className="pt-6">
        {overview}
      </TabsContent>
      <TabsContent value="technicals" className="pt-6">
        {technicals}
      </TabsContent>
      <TabsContent value="report" className="pt-6">
        {report}
      </TabsContent>
      <TabsContent value="news" className="pt-6">
        {news}
      </TabsContent>
    </Tabs>
  );
}
