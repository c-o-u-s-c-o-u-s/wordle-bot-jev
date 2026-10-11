import random
import unittest

from wordle_bot.drivers import SimDriver
from wordle_bot.feedback import clues, parse_history, parse_pattern, pattern_code, score
from wordle_bot.game import play
from wordle_bot.laya_picker import SolverPicker
from wordle_bot.solver import Solver, encode, pattern_matrix

SOLVER = Solver()


class FeedbackTest(unittest.TestCase):
    def test_duplicate_letters(self):
        self.assertEqual(score("speed", "abide"), "bbyby")  # second E gray: the answer has one E
        self.assertEqual(score("allee", "eagle"), "yybyg")
        self.assertEqual(score("lolly", "llama"), "gbybb")  # green L used first, then one yellow
        self.assertEqual(score("eerie", "geese"), "ygbbg")
        self.assertEqual(score("crane", "crane"), "ggggg")

    def test_vectorised_matches_reference(self):
        rng = random.Random(1)
        guesses = rng.sample(SOLVER.words, 200) + ["speed", "allee", "eerie", "lolly", "mamma"]
        answers = rng.sample(SOLVER.answers, 200) + ["abide", "eagle", "geese", "llama", "sassy"]
        got = pattern_matrix(encode(guesses), encode(answers))
        for i, g in enumerate(guesses):
            for j, a in enumerate(answers):
                self.assertEqual(got[i, j], pattern_code(score(g, a)), (g, a))

    def test_parsing(self):
        self.assertEqual(parse_pattern("G.y-X"), "gbybb")
        self.assertEqual(parse_pattern("20110"), "gbyyb")
        self.assertEqual(parse_history("soare:bbybb, CLINT=bybbb"), [("soare", "bbybb"), ("clint", "bybbb")])
        with self.assertRaises(ValueError):
            parse_pattern("gyb")
        with self.assertRaises(ValueError):
            parse_history("soare")

    def test_clues(self):
        text = clues([("soare", "bbybb"), ("clint", "bybbb")])
        self.assertIn("A is in the word but not 3rd", text)
        self.assertIn("not in the word: C E I N O R S T", text)


class SolverTest(unittest.TestCase):
    def test_true_answer_never_filtered_out(self):
        rng = random.Random(2)
        for answer in rng.sample(SOLVER.answers, 50):
            history = []
            for guess in rng.sample(SOLVER.words, 4):
                history.append((guess, score(guess, answer)))
                cand, fallback = SOLVER.candidates(history)
                self.assertFalse(fallback)
                self.assertIn(answer, [SOLVER.words[i] for i in cand])

    def test_last_try_only_offers_possible_answers(self):
        history = [(w, score(w, "pupal")) for w in ["fuzzy", "jumbo", "civic", "wreck", "ghost"]]
        turn = SOLVER.turn(history)
        self.assertTrue(turn.options and all(o.candidate for o in turn.options))
        self.assertIn("pupal", turn.candidates)

    def test_second_to_last_try_keeps_only_sure_wins(self):
        rng = random.Random(3)
        for answer in rng.sample(SOLVER.answers, 30):
            history = [(g, score(g, answer)) for g in rng.sample(SOLVER.words, 4)]
            if answer in (g for g, _ in history):
                continue
            options = SOLVER.turn(history).options
            if options[0].worst <= 1:
                self.assertTrue(all(o.worst <= 1 for o in options), (answer, history))

    def test_fallback_when_answer_not_in_answer_list(self):
        # aahed is a valid guess but never an answer; after these two no listed answer fits
        turn = SOLVER.turn([(g, score(g, "aahed")) for g in ["soare", "ahead"]])
        self.assertTrue(turn.fallback)
        self.assertIn("aahed", turn.candidates)

    def test_inconsistent_board_raises(self):
        with self.assertRaises(ValueError):
            SOLVER.turn([("soare", "ggggb"), ("soare", "bbbbb")])

    def test_solver_wins(self):
        valid = set(SOLVER.words)
        for answer in ["cigar", "jazzy", "fluff", "vivid", "mummy", "eerie"]:
            game = play(SOLVER, SolverPicker(), SimDriver(answer, valid))
            self.assertTrue(game.won, (answer, game.history))


if __name__ == "__main__":
    unittest.main()
