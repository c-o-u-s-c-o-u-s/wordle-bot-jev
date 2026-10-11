"""wordle-bot: a simple Laya integration that plays Wordle.

  wordle-bot web                       open a browser and play wordleunlimited.org (the default)
  wordle-bot sim --n 100               self-play against random answers, with stats
  wordle-bot play                      you relay a real game's colours (g/y/b)
  wordle-bot next soare:bbybb ...      print the next guess for a board

Every command takes --picker laya|solver|random (laya is the default; the other two are baselines).
"""
import argparse
import json
import random
import sys
import time
from collections import Counter

from .drivers import ManualDriver, SimDriver
from .feedback import parse_history
from .game import play
from .laya_picker import LayaPicker, RandomPicker, SolverPicker
from .solver import MAX_TRIES, SHORTLIST, Solver

BROWSERS = ("firefox", "chrome", "edge")  # see web.launch


def status(message: str) -> None:
    print(message, file=sys.stderr, flush=True)  # stderr keeps `next --json` output clean


def make_picker(args):
    if args.picker == "solver":
        return SolverPicker()
    if args.picker == "random":
        return RandomPicker(getattr(args, "seed", None))
    status("Loading Laya...")
    try:
        picker = LayaPicker(device=args.device, min_confidence=args.min_confidence)
    except Exception as e:  # network, disk or GPU problems surface here
        sys.exit(f"error: could not load Laya ({type(e).__name__}: {e})\n"
                 "The first run downloads about 0.8 GB from Hugging Face. "
                 "Use --picker solver to play without Laya.")
    status(f"Laya ready on {picker.device}.")
    return picker


def show_turn(turn, pick) -> None:
    n = len(turn.candidates)
    head = f"\nGuess {len(turn.history) + 1}/{MAX_TRIES}: {n} possible"
    if n <= 10:
        head += " (" + ", ".join(turn.candidates) + ")"
    if turn.fallback:
        head += " [no listed answer fits; searching all valid words]"
    print(head)
    for o in turn.options:
        prob = (pick.probabilities or {}).get(o.word)
        print(f"  {'->' if o.word == pick.word else '  '} {o.word}  {'answer?' if o.candidate else 'probe  '}"
              f"  {o.entropy:4.2f} bits  avg left {o.expected_left:6.1f}  worst {o.worst:4d}"
              + (f"  laya {prob:.2f}" if prob is not None else ""))
    conf = f", confidence {pick.confidence:.2f}" if pick.confidence is not None else ""
    print(f"  pick {pick.word.upper()} ({pick.source}{conf})", flush=True)


class Tally:
    """Counts who made each decision and how often Laya agreed with the solver's top pick."""

    def __init__(self, verbose: bool):
        self.verbose, self.counts = verbose, Counter()

    def __call__(self, turn, pick) -> None:
        self.counts[pick.source] += 1
        if pick.source == "laya":
            self.counts["laya_top1"] += pick.word == turn.options[0].word
        if self.verbose:
            show_turn(turn, pick)


def cmd_sim(args) -> None:
    solver, picker = Solver(), make_picker(args)
    valid = set(solver.words)
    answers = args.words or random.Random(args.seed).sample(solver.answers, args.n)
    tally, dist = Tally(args.verbose), Counter()
    for i, answer in enumerate(answers, 1):
        game = play(solver, picker, SimDriver(answer, valid), k=args.k, on_turn=tally)
        dist[len(game.history) if game.won else "X"] += 1
        if not args.quiet:
            print(f"{i:4d} {answer}  {'WIN ' if game.won else 'LOSS'} {len(game.history)}  "
                  + " ".join(w for w, _ in game.history), flush=True)
    wins = sum(v for k, v in dist.items() if k != "X")
    avg = sum(k * v for k, v in dist.items() if k != "X") / max(wins, 1)
    print(f"\npicker={args.picker}  won {wins}/{len(answers)} ({100 * wins / len(answers):.1f}%)  "
          f"avg {avg:.3f} guesses on wins")
    print("distribution: " + "  ".join(f"{k}:{dist[k]}" for k in [*range(1, MAX_TRIES + 1), "X"]))
    c = tally.counts
    if args.picker == "laya":
        print(f"decisions: {c['laya']} by Laya (agreed with solver top pick {100 * c['laya_top1'] / max(c['laya'], 1):.0f}%), "
              f"{c['solver']} low-confidence fallbacks to solver, {c['forced']} forced (one option)")


def cmd_play(args) -> None:
    solver, picker = Solver(), make_picker(args)
    print("Play each suggested word in your game, then type the colours back: "
          "g = green, y = yellow, b = gray (e.g. bygbb).")
    game = play(solver, picker, ManualDriver(), k=args.k, on_turn=show_turn)
    print(f"\nSolved in {len(game.history)}!" if game.won else "\nOut of tries.")


def cmd_next(args) -> None:
    solver = Solver()
    try:
        turn = solver.turn(parse_history(args.board), k=args.k, exclude=set(args.exclude))
    except ValueError as e:
        sys.exit(f"error: {e}")
    if not turn.options:
        sys.exit("error: every remaining word is excluded")
    pick = make_picker(args).pick(turn)
    if args.json:
        print(json.dumps({"guess": pick.word, "source": pick.source, "confidence": pick.confidence,
                          "remaining": len(turn.candidates),
                          "shortlist": [{"word": o.word, "candidate": o.candidate, "laya": (pick.probabilities or {}).get(o.word)}
                                        for o in turn.options]}))
        return
    if args.verbose:
        show_turn(turn, pick)
    print(pick.word)


def cmd_web(args) -> None:
    from selenium.common.exceptions import WebDriverException

    from .web import WordleUnlimited

    picker = make_picker(args)  # before the browser, so a Laya failure doesn't leave a window open
    status(f"Opening {args.browser}...")
    try:
        site = WordleUnlimited(browser=args.browser, headless=args.headless)
    except WebDriverException as e:
        sys.exit(f"error: could not start {args.browser}: {(e.msg or str(e)).splitlines()[0]}\n"
                 f"Is {args.browser} installed? Try --browser firefox, chrome or edge.")
    try:
        solver, wins = Solver(), 0
        for i in range(1, args.games + 1):
            site.new_game()
            print(f"\n=== Game {i}/{args.games} ===")
            game = play(solver, picker, site, k=args.k, on_turn=show_turn)
            wins += game.won
            words = " ".join(w.upper() for w, _ in game.history)
            print(f"\n{'Solved in ' + str(len(game.history)) if game.won else 'Lost'}: {words}", flush=True)
            time.sleep(3)  # let the last row finish flipping before the next game
        print(f"\nWon {wins}/{args.games}")
        if not args.headless and sys.stdin.isatty():
            input("Press Enter to close the browser... ")
    except TimeoutError as e:
        sys.exit(f"error: {e}. wordleunlimited.org may be unreachable or may have changed.")
    except KeyboardInterrupt:
        print()
    finally:
        site.close()


def main(argv: list[str] | None = None) -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--picker", choices=["laya", "solver", "random"], default="laya",
                        help="who picks from the shortlist: laya (default), or a baseline: "
                             "solver (its top word) or random (any shortlisted word)")
    common.add_argument("--k", type=int, default=SHORTLIST, help=f"shortlist size (default {SHORTLIST})")
    common.add_argument("--min-confidence", type=float, default=0.0,
                        help="use the solver's top word when Laya's confidence is below this (default 0: always Laya)")
    common.add_argument("--device", help="torch device for Laya: cuda, mps or cpu (default: best available)")
    common.add_argument("-v", "--verbose", action="store_true", help="show every shortlist")

    ap = argparse.ArgumentParser(prog="wordle-bot", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    web = sub.add_parser("web", parents=[common], help="open a browser and play wordleunlimited.org")
    web.add_argument("--games", type=int, default=1, help="games to play in a row (default 1)")
    web.add_argument("--browser", choices=BROWSERS, default="firefox", help="default: firefox")
    web.add_argument("--headless", action="store_true", help="no visible window")
    sim = sub.add_parser("sim", parents=[common], help="self-play against random answers")
    sim.add_argument("--n", type=int, default=100, help="games (default 100)")
    sim.add_argument("--seed", type=int, default=0, help="picks the answers (and the random picker's choices)")
    sim.add_argument("--words", nargs="+", help="play these answers instead of a random sample")
    sim.add_argument("-q", "--quiet", action="store_true", help="summary only")
    sub.add_parser("play", parents=[common], help="interactive: you type the colours from a real game")
    nxt = sub.add_parser("next", parents=[common], help="print the next guess for a board")
    nxt.add_argument("board", nargs="*", help="guesses so far as word:pattern, e.g. soare:bbybb")
    nxt.add_argument("--exclude", nargs="+", default=[], help="words the game rejected")
    nxt.add_argument("--json", action="store_true", help="machine-readable output")

    argv = sys.argv[1:] if argv is None else argv
    args = ap.parse_args(argv or ["web"])  # no arguments: play in the browser
    {"web": cmd_web, "sim": cmd_sim, "play": cmd_play, "next": cmd_next}[args.cmd](args)


if __name__ == "__main__":
    main()
