# wordle-bot-jev

**A simple [Laya](https://github.com/NandhaKishorM/laya) integration that plays Wordle.**

A classic Wordle solver does the real work. Laya, a general-purpose decision model, makes the last call: it picks the next guess from the solver's top five, through one multiple-choice question per turn. The bot plays [wordleunlimited.org](https://wordleunlimited.org/) in a real browser window, or runs games in your terminal.

> **What this project is, honestly.** Laya was not trained on Wordle and is not what makes this bot good. The solver is. In 1,000 simulated games:
> - Laya's picks average **3.49** guesses.
> - Always taking the solver's top word averages **3.47**.
> - Picking a *random* word from the same shortlist averages **3.49–3.53**.
>
> Read it as a worked example of wiring Laya's choice questions into a decision loop. It is not an AI that learned Wordle.

## Run it

**Linux / macOS:**

```bash
git clone https://github.com/c-o-u-s-c-o-u-s/wordle-bot-jev && cd wordle-bot-jev && ./run.sh
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/c-o-u-s-c-o-u-s/wordle-bot-jev; cd wordle-bot-jev; powershell -ExecutionPolicy Bypass -File run.ps1
```

The first run takes a few minutes:
1. It creates a local `.venv`.
2. It installs torch, Laya and Selenium.
3. It downloads the Laya checkpoint (about 0.8 GB).
4. It opens a browser at wordleunlimited.org.

Later runs start in seconds. Add any command after the script, e.g. `./run.sh sim --n 100` or `./run.sh web --games 5 --browser chrome`.

**Requirements:**
- Python 3.10 or newer, and Git.
- Firefox, Chrome or Edge. Selenium downloads the matching browser driver by itself.
- A GPU is optional. Laya runs on an NVIDIA GPU (CUDA), Apple silicon (MPS) or plain CPU, and picks the best one automatically.
- Disk: about 1–4 GB. Torch is about 0.2 GB as a CPU build and about 3 GB as a CUDA build; Laya is about 0.8 GB.

**Already in a Python environment?** Install it as a package:

```bash
pip install git+https://github.com/c-o-u-s-c-o-u-s/wordle-bot-jev
wordle-bot
```

## What happens each turn

1. **Filter.** The solver keeps every possible answer that fits all the colours so far. It searches the 2,315 original Wordle answers. If none fits, it falls back to all 12,972 accepted guesses.
2. **Shortlist.** It scores all 12,972 accepted guesses by how much they would narrow things down (expected information), with a small bonus for words that could win outright. It keeps the top 5. On the last try it only offers words that could be the answer.
3. **Ask Laya.** The board goes to Laya as plain text, with one `choice` question listing the five words. Laya's answer is the guess. When only one word is left, Laya isn't asked.
4. **Play.** The guess is typed into the game and the colours are read back. This repeats until the word is solved or six tries are used.

In the browser, the bot reads only the guesses and colours from the page. It never reads the stored answer.

Laya is deterministic: on a given machine, the same board always gets the same guess, so every game opens the same way (ROATE on the author's GPU). A CPU and a GPU can occasionally pick differently between near-tied words, because their floating-point arithmetic differs slightly.

## What Laya sees

The state, as text:

```
Wordle, guess 3 of 6.
SOARE: S gray, O gray, A yellow, R gray, E gray
CLINT: C gray, L yellow, I gray, N gray, T gray
Clues: A is in the word but not 3rd; L is in the word but not 2nd; not in the word: C E I N O R S T.
12 possible answers remain: amply, apply, awful, badly, balmy, bylaw, dally, gayly, laugh, madly, papal, pupal
```

The question: *"Pick the best next Wordle guess: a word that could be the answer, or one that leaves the fewest possible words."* There is one option per shortlisted word:

```
dampy: not the answer; leaves about 1.0 words, at most 1
balmy: could be the answer; leaves about 1.2 words, at most 2
...
```

The options carry the solver's numbers but not its ranking. Laya places options in parallel, so their order tells it nothing.

## How much Laya matters

These are 1,000 random answers (seed 1). Every picker won all 1,000 games.

| Who picks from the shortlist | Avg guesses |
|---|---|
| The solver's top word | 3.467 |
| **Laya** (default) | **3.486** |
| A random shortlisted word | 3.494 (3.494–3.534 over three seeds) |

Laya chose something other than the solver's top word in 82% of its decisions. Its probabilities across the five words are fairly flat, around 0.15–0.3 each. It tends to prefer words that could be the answer. A bigger shortlist made it worse: 3.507 with 8 words.

To reproduce, run `./run.sh sim --n 1000 --seed 1 --quiet --picker laya`, replacing `laya` with `solver` or `random` for the baselines.

Making Laya genuinely useful here would mean fine-tuning it on boards labelled by the solver. That hasn't been done.

## Commands

| Command | What it does |
|---|---|
| `wordle-bot` or `wordle-bot web` | Opens a browser and plays wordleunlimited.org. Options: `--games N`, `--browser firefox\|chrome\|edge`, `--headless`. |
| `wordle-bot sim --n 100` | Simulates games locally and reports win rate, average guesses and how Laya decided. Options: `--seed`, `--words cigar jazzy`, `-v` to show every shortlist. |
| `wordle-bot play` | Suggests guesses for any Wordle you play elsewhere. You type back the colours as five letters: `g` green, `y` yellow, `b` gray. |
| `wordle-bot next soare:bbybb clint:bybbb` | Prints the next guess for a board. `--json` gives machine-readable output. |

These options work with every command:
- `--picker laya|solver|random` chooses who picks from the shortlist.
- `--k N` sets the shortlist size (default 5).
- `--device cuda|mps|cpu` forces where Laya runs.
- `--min-confidence P` falls back to the solver's top word when Laya is less sure than `P`.

From a clone, `./run.sh <command>` and `.venv/bin/python -m wordle_bot <command>` work the same way.

## Platform notes

- **Linux without an NVIDIA GPU:** `run.sh` installs the CPU-only torch build.
- **Windows with an NVIDIA GPU:** PyPI's Windows torch is CPU-only. For CUDA, install a CUDA build of torch into `.venv` first, using the command from [pytorch.org](https://pytorch.org/get-started/locally/).
- **Older NVIDIA drivers** that the installed torch build doesn't support: Laya falls back to CPU automatically.
- **Servers without a display:** use `--headless`, or `sim`.
- **Window behind other windows:** browsers pause animations in hidden windows, and the game waits for each tile flip before accepting the next guess. The bot notices this and carries on, so you just won't see the flips.

## Development

```bash
.venv/bin/python -m unittest tests.test_wordle -v   # no GPU, browser or Laya needed
python scripts/fetch_words.py                        # re-download the word lists
```

CI runs the unit tests on Linux, macOS and Windows with Python 3.10 and 3.14. It also runs the one-command install on all three systems with Laya on CPU. A manual workflow plays one real game per browser.

## Credits and notices

- [Laya](https://github.com/NandhaKishorM/laya) and its checkpoint [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya) are Apache-2.0. Laya is installed as a dependency, not bundled.
- The word lists are the original Wordle answer and guess lists, as published by [cfreshman](https://gist.github.com/cfreshman). wordleunlimited.org uses the same lists.
- This project is not affiliated with wordleunlimited.org, The New York Times or the Laya authors.
- Code licensed under MIT; see [LICENSE](LICENSE).
