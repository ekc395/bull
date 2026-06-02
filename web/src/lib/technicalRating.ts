// Composite technical rating for the TradingView-style speedometer gauge.
// Tallies a handful of classic signals (RSI, MACD vs signal, MACD histogram,
// price vs SMA 20/50/200) into a buy / sell / neutral count and a -1..1 score.
// This is a lightweight client-side summary, not investment advice.

import type { Indicators } from "@/types/api";

export type RatingLabel =
  | "Strong sell"
  | "Sell"
  | "Neutral"
  | "Buy"
  | "Strong buy";

export interface TechnicalRating {
  score: number; // -1 (strong sell) .. +1 (strong buy)
  label: RatingLabel;
  buy: number;
  neutral: number;
  sell: number;
  total: number;
}

type Signal = "buy" | "sell" | "neutral";

export function computeTechnicalRating(
  ind: Indicators,
  price: number,
): TechnicalRating {
  const signals: Signal[] = [];

  // RSI: oversold leans buy, overbought leans sell.
  if (ind.rsi_14 != null) {
    signals.push(
      ind.rsi_14 <= 30 ? "buy" : ind.rsi_14 >= 70 ? "sell" : "neutral",
    );
  }

  // MACD line vs its signal line.
  if (ind.macd != null && ind.macd_signal != null) {
    signals.push(ind.macd > ind.macd_signal ? "buy" : "sell");
  }

  // MACD histogram momentum.
  if (ind.macd_hist != null) {
    signals.push(ind.macd_hist > 0 ? "buy" : "sell");
  }

  // Price relative to each moving average.
  for (const ma of [ind.sma_20, ind.sma_50, ind.sma_200]) {
    if (ma != null) signals.push(price > ma ? "buy" : "sell");
  }

  const buy = signals.filter((s) => s === "buy").length;
  const sell = signals.filter((s) => s === "sell").length;
  const neutral = signals.filter((s) => s === "neutral").length;
  const total = signals.length;

  const score = total === 0 ? 0 : (buy - sell) / total;

  return { score, label: labelFor(score), buy, neutral, sell, total };
}

function labelFor(score: number): RatingLabel {
  if (score >= 0.5) return "Strong buy";
  if (score >= 0.1) return "Buy";
  if (score > -0.1) return "Neutral";
  if (score > -0.5) return "Sell";
  return "Strong sell";
}
