"""Choose the next guess from the solver's shortlist with a Laya choice question."""
import os
import random
import warnings
from dataclasses import dataclass

from .feedback import clues, describe
from .solver import MAX_TRIES, Option, Turn

MODEL = "convaiinnovations/laya"
INSTRUCTIONS = "Pick the best next Wordle guess: a word that could be the answer, or one that leaves the fewest possible words."
LIST_CANDIDATES = 20  # name the remaining answers in the state when there are at most this many


@dataclass
class Pick:
    word: str
    source: str                         # "laya", "solver" (baseline or fallback) or "forced" (one option)
    confidence: float | None = None     # Laya's probability for its own answer
    probabilities: dict | None = None   # Laya's probability per shortlisted word


def board_state(turn: Turn) -> str:
    """The board as text: one line per guess with tile colours, the clues, and what is left."""
    lines = [f"Wordle, guess {len(turn.history) + 1} of {MAX_TRIES}."]
    lines += [describe(g, p) for g, p in turn.history] or ["No guesses yet."]
    lines.append("Clues: " + clues(turn.history) + ".")
    n = len(turn.candidates)
    remaining = f"{n} possible answer{'s' if n != 1 else ''} remain"
    lines.append(remaining + (": " + ", ".join(turn.candidates) if n <= LIST_CANDIDATES else "."))
    return "\n".join(lines)


def option_text(o: Option) -> str:
    kind = "could be the answer" if o.candidate else "not the answer"
    return f"{kind}; leaves about {o.expected_left:.1f} words, at most {o.worst}"


def question(turn: Turn) -> dict:
    return {"guess": {"type": "choice", "instructions": INSTRUCTIONS,
                      "criteria": {o.word: option_text(o) for o in turn.options}}}


class SolverPicker:
    """Baseline: always the solver's top-ranked word."""

    def pick(self, turn: Turn) -> Pick:
        return Pick(turn.options[0].word, "forced" if len(turn.options) == 1 else "solver")


class RandomPicker:
    """Baseline: a uniformly random word from the same shortlist Laya gets."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def pick(self, turn: Turn) -> Pick:
        if len(turn.options) == 1:
            return Pick(turn.options[0].word, "forced")
        return Pick(self.rng.choice(turn.options).word, "random")


def best_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():  # Apple silicon
        return "mps"
    return "cpu"


class LayaPicker:
    def __init__(self, device: str | None = None, min_confidence: float = 0.0, model: str = MODEL):
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        warnings.filterwarnings("ignore", module="laya")
        import laya

        self.device = device or best_device()
        self.agent = laya.load(model, device=self.device)
        self.min_confidence = min_confidence

    def pick(self, turn: Turn) -> Pick:
        if len(turn.options) == 1:
            return Pick(turn.options[0].word, "forced")
        result = self.agent.predict(board_state(turn), question(turn))
        if result["usage"]["truncated"]:
            warnings.warn(f"Laya truncated the board state: {result['usage']}")
        answer = result["answers"]["guess"]
        word, confidence = answer["choice"], answer["answer_confidence"]
        if word not in {o.word for o in turn.options} or confidence < self.min_confidence:
            return Pick(turn.options[0].word, "solver", confidence, answer["probabilities"])
        return Pick(word, "laya", confidence, answer["probabilities"])
