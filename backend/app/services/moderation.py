"""Prompt moderation (plan §2.3): deterministic deny list + imitation patterns + a policy classifier.

Protected names are NOT committed to source control (plan §16.1). The production deny list is curated by
trust & safety and injected with CV_DENYLIST_PATH (one term per line). Matching tolerates leetspeak,
accents, spacing tricks and small misspellings.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

POLICY_VERSION = "2026.11"
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "+": "t"})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"(?<=[a-z0-9])[!|](?=[a-z0-9])", "i", text)  # "st!rlance" -> "stirlance"
    text = text.translate(_LEET)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _squash_repeats(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text)


def levenshtein(a: str, b: str, limit: int) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            best = min(best, cur[j])
        if best > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _tolerance(term: str) -> int:
    n = len(term.replace(" ", ""))
    return 0 if n < 5 else 1 if n < 9 else 2


@dataclass
class ModerationResult:
    decision: str  # allow | flag | block
    reason_code: str | None = None
    matches: list[str] = field(default_factory=list)
    score: float = 0.0
    policy_version: str = POLICY_VERSION

    @property
    def blocked(self) -> bool:
        return self.decision == "block"


class DenyList:
    def __init__(self, terms: list[str]):
        self.terms = sorted({normalize(t) for t in terms if t.strip() and not t.strip().startswith("#")})

    @classmethod
    def from_file(cls, path: Path | None) -> DenyList:
        if path is None or not Path(path).exists():
            return cls([])
        return cls(Path(path).read_text(encoding="utf-8").splitlines())

    def matches(self, text: str) -> list[str]:
        norm = normalize(text)
        tokens = norm.split()
        squashed = _squash_repeats(norm.replace(" ", ""))
        found = []
        for term in self.terms:
            term_tokens = term.split()
            compact = _squash_repeats(term.replace(" ", ""))
            if compact and compact in squashed:
                found.append(term)
                continue
            tol = _tolerance(term)
            n = len(term_tokens)
            for i in range(0, max(len(tokens) - n + 1, 0)):
                window = " ".join(tokens[i : i + n])
                if levenshtein(window, term, tol) <= tol:
                    found.append(term)
                    break
            else:
                # tokens glued together, e.g. "star lance" vs "starlance" with a typo
                for i in range(0, len(tokens)):
                    for j in range(i + 1, min(len(tokens), i + n + 2) + 1):
                        glued = _squash_repeats("".join(tokens[i:j]))
                        if tol and levenshtein(glued, compact, tol) <= tol:
                            found.append(term)
                            break
                    if term in found:
                        break
        return found


class ImitationPatternClassifier:
    """Heuristic ContentModerationProvider. Swap for a hosted/local classifier via the provider interface."""

    name = "cv-heuristic-imitation"
    version = "1.0"
    terms_url = None

    def __init__(self, patterns: list[str]):
        self.patterns = [re.compile(rf"\b{p}\b") for p in patterns if p.strip() and not p.startswith("#")]

    @classmethod
    def default(cls) -> ImitationPatternClassifier:
        path = Path(__file__).parent / "policy" / "imitation_patterns_v1.txt"
        return cls(path.read_text(encoding="utf-8").splitlines())

    def score(self, text: str) -> tuple[float, list[str]]:
        norm = normalize(text)
        hits = [p.pattern.strip("\\b") for p in self.patterns if p.search(norm)]
        return min(1.0, 0.55 * len(hits)), hits


class Moderator:
    def __init__(self, deny_list: DenyList, classifier: ImitationPatternClassifier):
        self.deny_list = deny_list
        self.classifier = classifier

    def check(self, text: str) -> ModerationResult:
        if not text or not text.strip():
            return ModerationResult("allow")
        denied = self.deny_list.matches(text)
        if denied:
            return ModerationResult("block", "PROTECTED_CHARACTER_REFERENCE", denied, 1.0)
        score, hits = self.classifier.score(text)
        if score >= 1.0:
            return ModerationResult("block", "IMITATION_REQUEST", hits, score)
        if score > 0:
            return ModerationResult("flag", "POSSIBLE_IMITATION", hits, score)
        return ModerationResult("allow", None, [], 0.0)
