"""Re-download the standard Wordle word lists into wordle_bot/data/ (they already ship with the repo).

answers.txt: the 2,315 original NYT answers (wordleunlimited.org's SOLUTION_LIST).
valid.txt:   every accepted guess, answers included (12,972 words).
"""
import re
import sys
import urllib.request
from pathlib import Path

ANSWERS_URL = "https://gist.githubusercontent.com/cfreshman/a03ef2cba789d8cf00c08f767e0fad7b/raw/wordle-answers-alphabetical.txt"
ALLOWED_URL = "https://gist.githubusercontent.com/cfreshman/cdcdf777450c5b5301e439061d29694c/raw/wordle-allowed-guesses.txt"
DATA = Path(__file__).resolve().parent.parent / "wordle_bot" / "data"


def fetch(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        text = resp.read().decode("ascii")
    words = text.split()
    bad = [w for w in words if not re.fullmatch(r"[a-z]{5}", w)]
    if bad:
        sys.exit(f"{url}: unexpected entries {bad[:5]}")
    return words


def main() -> None:
    answers = sorted(set(fetch(ANSWERS_URL)))
    allowed = set(fetch(ALLOWED_URL))
    if len(answers) != 2315 or len(allowed) != 10657:
        sys.exit(f"unexpected sizes: {len(answers)} answers, {len(allowed)} allowed")
    valid = sorted(allowed | set(answers))
    DATA.mkdir(exist_ok=True)
    (DATA / "answers.txt").write_text("\n".join(answers) + "\n")
    (DATA / "valid.txt").write_text("\n".join(valid) + "\n")
    print(f"wrote {len(answers)} answers, {len(valid)} valid guesses to {DATA}")


if __name__ == "__main__":
    main()
