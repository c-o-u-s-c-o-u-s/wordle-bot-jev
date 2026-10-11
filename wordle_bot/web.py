"""Play wordleunlimited.org in a browser window driven by Selenium.

The page is a clone of the original NYT Wordle: a <game-app> element holds the board in
`boardState`/`evaluations` and reads keys from window keydown events. This driver types
through those events and reads only the guesses and colours, never the stored solution.
"""
import time

from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException

URL = "https://wordleunlimited.org/"
KEY_DELAY = 0.12      # seconds between letters, so you can watch it type
REVEAL_TIMEOUT = 6.0  # the tile flip takes about 2 s; longer means the window is hidden
COLOURS = {"correct": "g", "present": "y", "absent": "b"}

STATE_JS = """
const app = document.querySelector("game-app");
if (!app || !app.boardState) return null;
return {status: app.gameStatus, row: app.rowIndex, canInput: app.canInput, evaluations: app.evaluations};
"""
KEY_JS = 'window.dispatchEvent(new KeyboardEvent("keydown", {key: arguments[0]}));'
# Same steps as the site's own close button, minus the slide-out animation.
CLOSE_POPUPS_JS = """
const root = document.querySelector("game-app").shadowRoot;
for (const el of root.querySelectorAll("game-modal[open], game-page[open]")) {
  el.replaceChildren();
  el.removeAttribute("open");
}
"""
# What the stats popup's "Play again!" button does: a blank game dated 1970 makes the page
# pick a new random word on reload (and skips the "How to play" popup).
NEW_GAME_JS = """
localStorage.setItem("gameState", JSON.stringify({
  boardState: Array(6).fill(""), evaluations: Array(6).fill(null), rowIndex: 0, solution: null,
  gameStatus: "IN_PROGRESS", lastPlayedTs: 1, lastCompletedTs: 1, restoringFromLocalStorage: null,
  hardMode: document.querySelector("game-app").hardMode,
}));
location.reload();
"""
UNLOCK_JS = 'document.querySelector("game-app").canInput = true;'


def launch(browser: str, headless: bool) -> webdriver.Remote:
    """Start a fresh browser with a temporary profile. Selenium Manager fetches the driver."""
    if browser == "firefox":
        opts = webdriver.FirefoxOptions()
        opts.set_preference("privacy.trackingprotection.enabled", True)  # Firefox's own blocker keeps ad overlays off the board
        if headless:
            opts.add_argument("-headless")
        factory = webdriver.Firefox
    elif browser in ("chrome", "edge"):
        opts = webdriver.ChromeOptions() if browser == "chrome" else webdriver.EdgeOptions()
        if headless:
            opts.add_argument("--headless=new")
        factory = webdriver.Chrome if browser == "chrome" else webdriver.Edge
    else:
        raise ValueError(f"unknown browser {browser!r}; choose firefox, chrome or edge")
    opts.page_load_strategy = "eager"  # don't wait for the ads to finish loading
    return factory(options=opts)


class WordleUnlimited:
    """Driver for game.play(): types each guess into the site and reads the colours back."""

    def __init__(self, browser: str = "firefox", headless: bool = False):
        self.driver = launch(browser, headless)
        self.driver.get(URL)
        self._unlock_noted = False

    def close(self) -> None:
        self.driver.quit()

    def new_game(self) -> None:
        """Make sure a fresh, untouched game is on screen."""
        state = self._wait(lambda s: True, 30, "the game to load")
        if state["status"] != "IN_PROGRESS" or state["row"] > 0:
            self._js(NEW_GAME_JS)
            self._wait(lambda s: s["status"] == "IN_PROGRESS" and s["row"] == 0, 30, "a new game")

    def submit(self, word: str) -> str | None:
        """Type `word` and press Enter; return its colours, or None if the site rejected it."""
        row = self._ready()["row"]
        self._js(CLOSE_POPUPS_JS)  # first-visit "How to play" covers the board
        for _ in range(5):
            self._js(KEY_JS, "Backspace")
        for letter in word:
            self._js(KEY_JS, letter)
            time.sleep(KEY_DELAY)
        self._js(KEY_JS, "Enter")
        try:
            state = self._wait(lambda s: s["row"] > row, 2.0, "the guess to register")
        except TimeoutError:  # "Not in word list": the letters stay in the row
            for _ in range(5):
                self._js(KEY_JS, "Backspace")
            return None
        return "".join(COLOURS[e] for e in state["evaluations"][row])

    def _ready(self) -> dict:
        """Wait for the previous guess's tiles to finish flipping."""
        try:
            return self._wait(lambda s: s["canInput"], REVEAL_TIMEOUT, "the tiles to flip")
        except TimeoutError:
            # Firefox pauses animations in a hidden window, and the game only accepts input
            # again when the flip ends. The colours are already recorded, so lift the lock.
            if not self._unlock_noted:
                print("  (window hidden: skipping the tile animation)")
                self._unlock_noted = True
            self._js(UNLOCK_JS)
            return self._wait(lambda s: s["canInput"], 2.0, "the game to accept input")

    def _js(self, script: str, *args):
        try:
            return self.driver.execute_script(script, *args)
        except (NoSuchWindowException, InvalidSessionIdException):
            raise SystemExit("Firefox window was closed")
        except WebDriverException:
            return None  # mid-reload

    def _wait(self, ready, timeout: float, what: str) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self._js(STATE_JS)
            if state and ready(state):
                return state
            time.sleep(0.1)
        raise TimeoutError(f"timed out waiting for {what}")
