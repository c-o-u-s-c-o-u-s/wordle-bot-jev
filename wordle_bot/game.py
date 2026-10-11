"""The play loop: filter -> shortlist -> pick -> submit -> feedback, until solved or out of tries."""
from dataclasses import dataclass, field

from .feedback import SOLVED
from .solver import MAX_TRIES, SHORTLIST, Solver

MAX_REJECTIONS = 10  # words the game refused ("not in word list") before giving up


@dataclass
class GameResult:
    history: list[tuple[str, str]] = field(default_factory=list)
    picks: list = field(default_factory=list)  # laya_picker.Pick per guess

    @property
    def won(self) -> bool:
        return bool(self.history) and self.history[-1][1] == SOLVED


def play(solver: Solver, picker, driver, k: int = SHORTLIST, on_turn=None) -> GameResult:
    """`driver.submit(word)` returns the feedback pattern, or None if the game rejected the word."""
    game, rejected = GameResult(), set()
    while len(game.history) < MAX_TRIES and not game.won:
        turn = solver.turn(game.history, k=k, exclude=rejected)
        if not turn.options:
            raise RuntimeError("every remaining word was rejected")
        pick = picker.pick(turn)
        if on_turn:
            on_turn(turn, pick)
        pattern = driver.submit(pick.word)
        if pattern is None:
            rejected.add(pick.word)
            if len(rejected) > MAX_REJECTIONS:
                raise RuntimeError(f"game rejected {len(rejected)} words: {sorted(rejected)}")
            continue
        game.history.append((pick.word, pattern))
        game.picks.append(pick)
    return game
