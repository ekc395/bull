// Per-ticker analysis view. Triggers /analyze on mount, renders verdict + chart + report.
export default function TickerPage({ params }: { params: { symbol: string } }) {
  return (
    <main className="container mx-auto p-6">
      <h1 className="text-2xl font-semibold">{params.symbol.toUpperCase()}</h1>
      {/*
        TODO:
          - useAnalyze(symbol) on mount
          - VerdictBanner
          - DeeperAnalysisPrompt (yellow card with escalation_reasons + "$0.12" button)
          - PriceChart
          - IndicatorTable
          - ReportSections
          - NewsList
          - "Execute on paper" button
      */}
    </main>
  );
}
