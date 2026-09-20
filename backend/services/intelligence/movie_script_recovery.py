"""Bounded, extractive recovery; creative writing and entailment stay upstream.

Never pad or truncate a claim to hit a word count. Whole source sentences
retain their original evidence IDs. A length-feasible script is not a quality
approval: the main generator must still run lexical and semantic validation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.services.intelligence.claim_evidence_validator import ClaimEvidenceValidator


@dataclass(frozen=True)
class _Line:
    text: str
    ids: tuple[str, ...]
    original_slot: int = -1

    @property
    def words(self):
        return len(self.text.split())


def recover_movie_script(data, *, topic, research, minimum=75, maximum=110):
    """Return four grounded lines, or None when evidence cannot support them.

    Search is bounded (80 source candidates, 256 states per slot). Labels are
    required: inventing local IDs would break the downstream evidence contract.
    """
    evidence = ClaimEvidenceValidator._parse_evidence(research)
    if not evidence:
        return None
    validator = ClaimEvidenceValidator()
    topic_terms = validator._terms(topic)

    def on_angle(text: str, ids: tuple[str, ...]) -> bool:
        supported = " ".join(evidence.get(x, "") for x in ids)
        # Require the cited source—not merely a coincidental word in the
        # narration—to overlap the requested angle. Two terms prevents broad
        # film-name matches from admitting unrelated trivia.
        return len(topic_terms & validator._terms(supported)) >= 2
    data = data if isinstance(data, dict) else {}
    lines = data.get("script_lines", [])
    citations = data.get("evidence_ids", [])
    if not isinstance(lines, list):
        lines = []
    if not isinstance(citations, list):
        citations = []
    originals = {}
    for slot, text in enumerate(lines[:4]):
        ids = citations[slot] if slot < len(citations) else []
        if not isinstance(text, str) or not isinstance(ids, list):
            continue
        text = " ".join(text.split())
        ids = tuple(dict.fromkeys(str(x).strip().upper() for x in ids))
        if not 5 <= len(text.split()) <= 29 or not ids or any(x not in evidence for x in ids):
            continue
        support = " ".join(evidence[x] for x in ids)
        if len(validator._shared_terms(text, support)) >= 2 and on_angle(text, ids):
            originals[slot] = _Line(text, ids, slot)

    if len(originals) == 4:
        original_lines = [originals[i].text for i in range(4)]
        total = sum(len(x.split()) for x in original_lines)
        if minimum <= total <= maximum and len(set(original_lines)) == 4:
            return {**data, "script_lines": original_lines,
                    "evidence_ids": [list(originals[i].ids) for i in range(4)]}

    candidates = []
    seen = set()
    for evidence_id, source in evidence.items():
        # Keep complete sentences, including their punctuation and qualifiers.
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", source)
        for i, sentence in enumerate(sentences):
            for text in (sentence, " ".join(sentences[i:i + 2])):
                text = " ".join(text.split())
                key = text.casefold()
                if key in seen or not 5 <= len(text.split()) <= 29:
                    continue
                if not re.search(r"[.!?][\"']?$", text):
                    continue
                if re.search(r"https?://|[{}]|\[(?:E\d+|\d+)\]", text):
                    continue
                if len(validator._shared_terms(text, source)) < 2:
                    continue
                seen.add(key)
                candidate = _Line(text, (evidence_id,))
                if on_angle(text, candidate.ids):
                    candidates.append(candidate)
    terms = topic_terms
    candidates.sort(key=lambda x: (-len(terms & validator._terms(x.text)), abs(x.words - 23), x.text))
    candidates = candidates[:80]
    # (score, total words, chosen lines). Prefer usable creative lines, then
    # source overlap with the topic; never reuse overlapping source sentences.
    states = [(0, 0, ())]
    for slot in range(4):
        expanded = []
        options = ([originals[slot]] if slot in originals else []) + candidates
        for score, total, chosen in states:
            for option in options:
                key = option.text.casefold()
                if any(key in x.text.casefold() or x.text.casefold() in key for x in chosen):
                    continue
                count = total + option.words
                remaining = 3 - slot
                if count > maximum or count + 29 * remaining < minimum:
                    continue
                gain = (30 if option.original_slot == slot else 0) + len(terms & validator._terms(option.text))
                expanded.append((score + gain, count, chosen + (option,)))
        # Keep diversity in total length to avoid pruning feasible solutions.
        by_total = {}
        for state in sorted(expanded, key=lambda s: (-s[0], abs(s[1] - 23 * (slot + 1)))):
            group = by_total.setdefault(state[1], [])
            if len(group) < 4:
                group.append(state)
        states = [s for group in by_total.values() for s in group][:256]
        if not states:
            return None
    viable = [s for s in states if minimum <= s[1] <= maximum]
    if not viable:
        return None
    _, _, chosen = min(viable, key=lambda s: (0 if 88 <= s[1] <= 96 else 1, -s[0], abs(s[1] - 92)))
    output_lines = [x.text for x in chosen]
    output_ids = [list(x.ids) for x in chosen]
    if not validator.validate(script_lines=output_lines, evidence_ids=output_ids, research=research).valid:
        return None
    tags = data.get("hashtags")
    if not isinstance(tags, list) or len(tags) < 3 or not all(isinstance(x, str) and x.strip() for x in tags):
        tags = ["#film", "#movies", "#commentary"]
    return {**data, "title": str(data.get("title") or topic), "hashtags": tags,
            "script_lines": output_lines, "evidence_ids": output_ids}
