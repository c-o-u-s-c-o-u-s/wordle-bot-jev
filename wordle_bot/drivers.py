"""Where guesses go and feedback comes from."""
from .feedback import parse_pattern, score


class SimDriver:
    """Local game with a known answer, for benchmarking."""

    def __init__(self, answer: str, valid: set[str]):
        self.answer, self.valid = answer, valid

    def submit(self, word: str) -> str | None:
        return score(word, self.answer) if word in self.valid else None


class ManualDriver:
    """You play the guess in a real game and type back the colours."""

    def submit(self, word: str) -> str | None:
        print(f"\n  >>> play {word.upper()}")
        while True:
            try:
                text = input("  feedback (g/y/b, e.g. bygbb; ! if the game rejected the word): ").strip()
            except EOFError:
                raise SystemExit("\nbye")
            if text == "!":
                return None
            try:
                return parse_pattern(text)
            except ValueError as e:
                print(f"  {e}")
