"""Wordle feedback: scoring a guess against an answer and parsing typed boards.

A pattern is a 5-char string over g (green), y (yellow), b (gray), e.g. "bygbb".
"""
from collections import Counter

SOLVED = "ggggg"
_ALIASES = {"g": "g", "2": "g", "y": "y", "1": "y", "b": "b", "0": "b", ".": "b", "-": "b", "_": "b", "x": "b"}
_NAMES = {"g": "green", "y": "yellow", "b": "gray"}


def score(guess: str, answer: str) -> str:
    """Feedback for `guess` if the hidden word is `answer`.

    Greens are assigned first; each remaining guess letter is yellow only while
    unmatched copies of it are left in the answer, scanning left to right.
    """
    pattern = ["b"] * 5
    unmatched = Counter()
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            pattern[i] = "g"
        else:
            unmatched[a] += 1
    for i, g in enumerate(guess):
        if pattern[i] != "g" and unmatched[g] > 0:
            pattern[i] = "y"
            unmatched[g] -= 1
    return "".join(pattern)


def pattern_code(pattern: str) -> int:
    """Base-3 code, position 0 least significant (b=0, y=1, g=2); 242 means solved."""
    return sum("byg".index(c) * 3**i for i, c in enumerate(pattern))


def parse_pattern(text: str) -> str:
    """Normalise user feedback: g/2 green, y/1 yellow, b/0/x/./-/_ gray."""
    text = text.strip().lower()
    if len(text) != 5 or any(c not in _ALIASES for c in text):
        raise ValueError(f"feedback must be 5 of g/y/b (got {text!r})")
    return "".join(_ALIASES[c] for c in text)


def parse_history(tokens: list[str] | str) -> list[tuple[str, str]]:
    """Parse "crane:bybbg slate:ggbbb" (or a list of such tokens) into (guess, pattern) pairs."""
    if isinstance(tokens, str):
        tokens = tokens.replace(",", " ").split()
    history = []
    for tok in tokens:
        word, sep, pat = tok.replace("=", ":").partition(":")
        word = word.strip().lower()
        if not sep or len(word) != 5 or not (word.isascii() and word.isalpha()):
            raise ValueError(f"expected word:pattern like crane:bybbg (got {tok!r})")
        history.append((word, parse_pattern(pat)))
    return history


def describe(guess: str, pattern: str) -> str:
    """'CRANE: C gray, R yellow, A gray, N gray, E green'."""
    tiles = ", ".join(f"{g.upper()} {_NAMES[p]}" for g, p in zip(guess, pattern))
    return f"{guess.upper()}: {tiles}"


def clues(history: list[tuple[str, str]]) -> str:
    """Plain-English summary of what the board has established."""
    fixed, present, absent = {}, {}, set()
    for guess, pattern in history:
        for i, (g, p) in enumerate(zip(guess, pattern)):
            if p == "g":
                fixed[i] = g
            elif p == "y":
                present.setdefault(g, set()).add(i)
        hit = {g for g, p in zip(guess, pattern) if p != "b"}
        absent |= {g for g, p in zip(guess, pattern) if p == "b" and g not in hit}
    ordinal = ["1st", "2nd", "3rd", "4th", "5th"]
    parts = [f"{g.upper()} is {ordinal[i]}" for i, g in sorted(fixed.items())]
    parts += [f"{g.upper()} is in the word but not {'/'.join(ordinal[i] for i in sorted(pos))}"
              for g, pos in sorted(present.items())]
    absent -= set(fixed.values()) | set(present)
    if absent:
        parts.append("not in the word: " + " ".join(sorted(c.upper() for c in absent)))
    return "; ".join(parts) if parts else "no clues yet"
