"""Convert the existing production selector's measured choice into a channel plan."""

from __future__ import annotations

from backend.models.network_channel import NetworkChannel


def candidate_from_analysis(channel: NetworkChannel, analysis: dict) -> dict | None:
    if analysis.get("status") != "success":
        return None
    trend = analysis.get("best_trend")
    if not isinstance(trend, dict):
        return None
    topic = str(trend.get("title") or "").strip()
    selection = trend.get("production_selection")
    if not topic or not isinstance(selection, dict):
        return None
    if selection.get("eligible") is not True or selection.get("selected") is not True:
        return None
    # The general six-format selector does not know a network channel's
    # editorial remit. Require explicit topic terms until it does.
    if not channel.allowed_topics or not any(
        term.casefold() in topic.casefold() for term in channel.allowed_topics
    ):
        return None
    if any(term.casefold() in topic.casefold() for term in channel.blocked_topics):
        return None
    try:
        quality = float(selection["production_score"]) / 100
        evidence = float(selection["research_confidence"]) / 100
        visual = float(selection["suitability_score"]) / 100
    except (TypeError, ValueError, KeyError):
        return None
    if not all(0 <= score <= 1 for score in (quality, evidence, visual)):
        return None
    return {"topic": topic, "selected_trend": trend,
            "quality": quality, "evidence": evidence, "visual": visual,
            # Provisional until the transactional originality reservation.
            "originality": 1.0}
