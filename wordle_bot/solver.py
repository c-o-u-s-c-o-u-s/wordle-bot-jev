"""Candidate filtering and guess ranking (expected information, vectorised with numpy)."""
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .feedback import SOLVED, pattern_code

DATA = Path(__file__).resolve().parent / "data"
OPENING_FILE = "opening.json"
MAX_TRIES = 6
SHORTLIST = 5  # options offered to the picker; best of 3/5/8 in 1,000-game sims
SOLVED_CODE = pattern_code(SOLVED)
_POW3 = 3 ** np.arange(5)
_EARLIER = np.tril(np.ones((5, 5), dtype=bool), -1)  # [i, k]: k is left of i


def load_words(name: str) -> list[str]:
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"{path} missing - reinstall, or run: python scripts/fetch_words.py")
    return path.read_text(encoding="utf-8").split()


def encode(words: list[str]) -> np.ndarray:
    """(N, 5) array of letter indices 0-25."""
    return np.frombuffer("".join(words).encode(), dtype=np.uint8).reshape(-1, 5) - ord("a")


def pattern_matrix(guesses: np.ndarray, answers: np.ndarray, chunk_pairs: int = 1_000_000) -> np.ndarray:
    """Pattern codes (see feedback.pattern_code) for every (guess, answer) pair, shape (G, A).

    Same rule as feedback.score: a non-green guess letter is yellow while the number of
    earlier non-green copies of it in the guess is below its unmatched copies in the answer.
    """
    out = np.empty((len(guesses), len(answers)), dtype=np.uint8)
    step = max(1, chunk_pairs // max(len(answers), 1))
    for s in range(0, len(guesses), step):
        g = guesses[s:s + step]
        eq = g[:, None, :, None] == answers[None, :, None, :]  # (c, A, i, j): guess[i] == answer[j]
        green = np.diagonal(eq, axis1=2, axis2=3)              # (c, A, 5)
        free = ~green
        unmatched = (eq & free[:, :, None, :]).sum(-1)          # unmatched answer copies of guess[i]
        same = (g[:, :, None] == g[:, None, :]) & _EARLIER      # (c, i, k): earlier copy of guess[i]
        rank = (same[:, None] & free[:, :, None, :]).sum(-1)    # earlier non-green copies of guess[i]
        yellow = free & (rank < unmatched)
        out[s:s + step] = (green.astype(np.uint8) * 2 + yellow) @ _POW3
    return out


@dataclass(frozen=True)
class Option:
    word: str
    candidate: bool       # could still be the answer
    entropy: float        # expected bits of information from the feedback
    expected_left: float  # expected words still possible afterwards (0 when it wins)
    worst: int            # most words it can leave possible (excluding a win)
    score: float          # ranking key, higher is better


@dataclass
class Turn:
    history: list[tuple[str, str]]
    candidates: list[str]  # words still possible
    options: list[Option]  # shortlist, best first
    fallback: bool         # no listed answer fits, so candidates come from all valid words

    @property
    def tries_left(self) -> int:
        return MAX_TRIES - len(self.history)


class Solver:
    def __init__(self, answers: list[str] | None = None, valid: list[str] | None = None):
        self.answers = answers or load_words("answers.txt")
        self.words = valid or load_words("valid.txt")
        self.index = {w: i for i, w in enumerate(self.words)}
        self.codes = encode(self.words)
        self.answer_ids = np.array([self.index[w] for w in self.answers])
        self._cache: dict = {}

    def candidates(self, history: list[tuple[str, str]]) -> tuple[np.ndarray, bool]:
        """Word indices consistent with every (guess, pattern), and whether the fallback pool was needed."""
        for fallback, pool in ((False, self.answer_ids), (True, np.arange(len(self.words)))):
            cand = pool
            for guess, pattern in history:
                cand = cand[pattern_matrix(encode([guess]), self.codes[cand])[0] == pattern_code(pattern)]
            if cand.size:
                return cand, fallback
        raise ValueError("no valid word fits this board - check the feedback")

    def rank(self, cand: np.ndarray, tries_left: int, exclude: frozenset[str] = frozenset(), limit: int = 50) -> list[Option]:
        """Best guesses for the candidate set, by expected information plus a bonus for possibly winning now."""
        key = (cand.tobytes(), tries_left, exclude, limit)
        if key not in self._cache:
            opening = cand.size == len(self.answer_ids) and tries_left == MAX_TRIES and not exclude
            options = self._load_opening(limit) if opening else None
            if options is None:
                options = self._rank(cand, tries_left, exclude, limit)
                if opening:
                    self._save_opening(options)
            self._cache[key] = options
        return self._cache[key]

    def _rank(self, cand: np.ndarray, tries_left: int, exclude: frozenset[str], limit: int) -> list[Option]:
        n = cand.size
        # Last try or a coin flip: only a word that can win is worth guessing.
        pool = cand if tries_left == 1 or n <= 2 else np.arange(len(self.words))
        if exclude:
            pool = pool[~np.isin(pool, [self.index[w] for w in exclude if w in self.index])]
        if pool.size == 0:
            return []
        pats = pattern_matrix(self.codes[pool], self.codes[cand]).astype(np.int64)
        counts = np.bincount((pats + 243 * np.arange(pool.size)[:, None]).ravel(),
                             minlength=243 * pool.size).reshape(pool.size, 243)
        p = counts / n
        entropy = -(p * np.log2(np.where(p > 0, p, 1))).sum(1) + 0.0  # + 0.0 turns -0.0 into 0.0
        is_cand = counts[:, SOLVED_CODE] > 0
        left = counts.copy()
        left[:, SOLVED_CODE] = 0
        expected_left = (left ** 2).sum(1) / n
        worst = left.max(1)
        # Guessing a candidate wins outright with probability 1/n, saving roughly log2(n) bits of work.
        score = entropy + is_cand * np.log2(max(n, 2)) / n
        if tries_left == 2:
            score = score + 100 * (worst <= 1)  # guarantees a win on the last try
        order = np.lexsort((pool, -score))[:limit]
        return [Option(self.words[pool[i]], bool(is_cand[i]), float(entropy[i]), float(expected_left[i]),
                       int(worst[i]), float(score[i])) for i in order]

    def turn(self, history: list[tuple[str, str]], k: int = SHORTLIST, exclude: set[str] = frozenset()) -> Turn:
        """Filter the candidates for this board and shortlist the k best next guesses."""
        if len(history) >= MAX_TRIES or (history and history[-1][1] == SOLVED):
            raise ValueError("game is already over")
        cand, fallback = self.candidates(history)
        exclude = frozenset(exclude) | {g for g, _ in history}
        tries_left = MAX_TRIES - len(history)
        options = self.rank(cand, tries_left, exclude)[:k]
        if tries_left == 2 and options and options[0].worst <= 1:
            # Some guess guarantees a win on the last try; offer nothing that could lose.
            options = [o for o in options if o.worst <= 1]
        return Turn(history, [self.words[i] for i in cand], options, fallback)

    # The opening shortlist needs all 12,972 x 2,315 patterns (~7 s), so it ships precomputed in
    # data/opening.json, tagged with a digest of the word lists it was computed from.
    def _digest(self) -> str:
        return hashlib.sha1(("\n".join(self.answers) + "|" + "\n".join(self.words)).encode()).hexdigest()[:12]

    def _load_opening(self, limit: int) -> list[Option] | None:
        try:
            saved = json.loads((DATA / OPENING_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if saved.get("digest") != self._digest() or len(saved.get("options", [])) < limit:
            return None
        return [Option(**row) for row in saved["options"][:limit]]

    def _save_opening(self, options: list[Option]) -> None:
        try:
            (DATA / OPENING_FILE).write_text(
                json.dumps({"digest": self._digest(), "options": [asdict(o) for o in options]}, indent=0),
                encoding="utf-8")
        except OSError:
            pass  # read-only install: recompute next run
