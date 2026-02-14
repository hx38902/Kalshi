"""
News-to-Ticker NLP Agent (OpenAI gpt-4o)
==========================================
Monitors primary-source news feeds (NOAA weather, BLS CPI, Fed) and uses
GPT-4o to:
  1. Summarize the headline / data release.
  2. Map it to relevant Kalshi tickers.
  3. Estimate the directional probability shift (≥10 % to be actionable).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from kalshi_alpha_suite.config import SuiteConfig
from kalshi_alpha_suite.models import Side, Signal, SignalSource

logger = logging.getLogger(__name__)

# Curated RSS / API endpoints for primary-source data
DEFAULT_FEEDS: Dict[str, str] = {
    "NOAA_ALERTS": "https://api.weather.gov/alerts/active?status=actual&limit=5",
    "BLS_CPI": "https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?latest=true",
    "FED_RSS": "https://www.federalreserve.gov/feeds/press_all.xml",
}

SYSTEM_PROMPT = """\
You are a quantitative analyst for a prediction-market trading desk.

Given a news headline or data release, you must:
1. Determine if it is relevant to any prediction-market contract on Kalshi.
2. If relevant, output a JSON array of objects with these fields:
   - "ticker_keyword": a short keyword that would appear in the Kalshi ticker
     (e.g. "CPI", "FED-RATE", "HURRICANE", "TEMP").
   - "side": "yes" or "no" — the direction the news pushes the probability.
   - "prob_shift": a float between -1.0 and 1.0 representing the estimated
     absolute shift in the YES probability (e.g. +0.15 means +15 pp).
   - "confidence": 0.0-1.0 how confident you are.
   - "rationale": one sentence.
3. If not relevant, return an empty JSON array: []

Return ONLY valid JSON. No markdown fences.
"""


@dataclass
class NLPSignalRaw:
    ticker_keyword: str
    side: str
    prob_shift: float
    confidence: float
    rationale: str


class NLPAgent:
    """Fetches news, runs GPT-4o analysis, and produces trading signals."""

    def __init__(self, cfg: SuiteConfig, feeds: Optional[Dict[str, str]] = None) -> None:
        self.cfg = cfg
        self.feeds = feeds or DEFAULT_FEEDS
        self._openai = AsyncOpenAI(api_key=cfg.openai_api_key)
        self._http = httpx.AsyncClient(timeout=15.0)

    # ------------------------------------------------------------------
    # Feed fetching
    # ------------------------------------------------------------------

    async def fetch_feed(self, name: str, url: str) -> str:
        """Fetch raw text from a feed URL."""
        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            # Truncate to avoid blowing the context window
            return resp.text[:6000]
        except Exception:
            logger.warning("Failed to fetch feed %s (%s)", name, url, exc_info=True)
            return ""

    async def fetch_all_feeds(self) -> Dict[str, str]:
        results: Dict[str, str] = {}
        for name, url in self.feeds.items():
            text = await self.fetch_feed(name, url)
            if text:
                results[name] = text
        return results

    # ------------------------------------------------------------------
    # GPT-4o analysis
    # ------------------------------------------------------------------

    async def analyze_headline(self, headline: str) -> List[NLPSignalRaw]:
        """Send a headline to GPT-4o and parse the structured response."""
        try:
            resp = await self._openai.chat.completions.create(
                model=self.cfg.openai_model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": headline},
                ],
            )
        except Exception:
            logger.error("OpenAI API call failed", exc_info=True)
            return []

        raw_text = resp.choices[0].message.content or "[]"
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("GPT returned non-JSON: %s", raw_text[:200])
            return []

        if not isinstance(parsed, list):
            parsed = [parsed]

        signals: List[NLPSignalRaw] = []
        for item in parsed:
            try:
                signals.append(
                    NLPSignalRaw(
                        ticker_keyword=item["ticker_keyword"],
                        side=item["side"],
                        prob_shift=float(item["prob_shift"]),
                        confidence=float(item["confidence"]),
                        rationale=item.get("rationale", ""),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Skipping malformed GPT item: %s (%s)", item, exc)
        return signals

    # ------------------------------------------------------------------
    # Ticker resolution
    # ------------------------------------------------------------------

    async def resolve_tickers(
        self,
        keyword: str,
        kalshi_client: Any,
    ) -> List[str]:
        """Search Kalshi open markets for tickers matching a keyword."""
        try:
            resp = await kalshi_client.get_markets(status="open", limit=50)
            markets = resp.get("markets", [])
            return [
                m["ticker"]
                for m in markets
                if keyword.lower() in m.get("ticker", "").lower()
                or keyword.lower() in m.get("title", "").lower()
            ]
        except Exception:
            logger.warning("Ticker resolution failed for '%s'", keyword, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def run(self, kalshi_client: Any) -> List[Signal]:
        """Fetch feeds → GPT analysis → resolve tickers → emit signals."""
        feeds = await self.fetch_all_feeds()
        all_signals: List[Signal] = []

        for feed_name, text in feeds.items():
            # Use first ~500 chars as the "headline"
            headline = f"[{feed_name}] {text[:500]}"
            raw_signals = await self.analyze_headline(headline)

            for raw in raw_signals:
                if abs(raw.prob_shift) < self.cfg.nlp_prob_shift_min:
                    logger.debug(
                        "Skipping sub-threshold signal: %s shift=%.2f",
                        raw.ticker_keyword,
                        raw.prob_shift,
                    )
                    continue

                tickers = await self.resolve_tickers(raw.ticker_keyword, kalshi_client)
                if not tickers:
                    logger.info(
                        "No matching tickers for keyword '%s'", raw.ticker_keyword,
                    )
                    continue

                side = Side.YES if raw.prob_shift > 0 else Side.NO
                for ticker in tickers:
                    signal = Signal(
                        source=SignalSource.NLP,
                        ticker=ticker,
                        side=side,
                        implied_prob=0.5,  # placeholder; refined downstream
                        estimated_fair_prob=0.5 + raw.prob_shift,
                        edge=abs(raw.prob_shift),
                        confidence=raw.confidence,
                        rationale=f"[{feed_name}] {raw.rationale}",
                    )
                    all_signals.append(signal)
                    logger.info("NLP SIGNAL %s %s shift=%.2f", ticker, side.value, raw.prob_shift)

        logger.info("NLP agent produced %d signals", len(all_signals))
        return all_signals

    async def close(self) -> None:
        await self._http.aclose()
