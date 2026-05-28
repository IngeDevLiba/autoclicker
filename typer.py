"""
Natural typing simulation for Selenium WebDriver.

Features
--------
* Variable keystroke delay (TYPING_SPEED_MIN_MS – TYPING_SPEED_MAX_MS).
* Random typos: a wrong adjacent key is occasionally pressed then corrected
  with Backspace, mimicking real human behaviour.
"""

import random
import time

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys

from config import TYPING_SPEED_MIN_MS, TYPING_SPEED_MAX_MS, TYPO_PROBABILITY

# Map each character to a set of "adjacent" keys on a QWERTY keyboard.
# Used to generate realistic typos.
_ADJACENT: dict[str, list[str]] = {
    "a": ["q", "w", "s", "z"],
    "b": ["v", "g", "h", "n"],
    "c": ["x", "d", "f", "v"],
    "d": ["s", "e", "r", "f", "c", "x"],
    "e": ["w", "s", "d", "r"],
    "f": ["d", "r", "t", "g", "v", "c"],
    "g": ["f", "t", "y", "h", "b", "v"],
    "h": ["g", "y", "u", "j", "n", "b"],
    "i": ["u", "j", "k", "o"],
    "j": ["h", "u", "i", "k", "m", "n"],
    "k": ["j", "i", "o", "l", "m"],
    "l": ["k", "o", "p"],
    "m": ["n", "j", "k"],
    "n": ["b", "h", "j", "m"],
    "o": ["i", "k", "l", "p"],
    "p": ["o", "l"],
    "q": ["w", "a"],
    "r": ["e", "d", "f", "t"],
    "s": ["a", "w", "e", "d", "x", "z"],
    "t": ["r", "f", "g", "y"],
    "u": ["y", "h", "j", "i"],
    "v": ["c", "f", "g", "b"],
    "w": ["q", "a", "s", "e"],
    "x": ["z", "s", "d", "c"],
    "y": ["t", "g", "h", "u"],
    "z": ["a", "s", "x"],
    " ": [" "],
}


def _delay() -> None:
    """Sleep for a random inter-keystroke interval."""
    ms = random.randint(TYPING_SPEED_MIN_MS, TYPING_SPEED_MAX_MS)
    time.sleep(ms / 1000.0)


def type_naturally(element: WebElement, text: str) -> None:
    """
    Type *text* into *element* with human-like speed and occasional typos.

    A typo is introduced by sending an adjacent wrong character first,
    then immediately correcting it with Backspace before continuing.
    """
    for char in text:
        if (
            random.random() < TYPO_PROBABILITY
            and char.lower() in _ADJACENT
            and len(_ADJACENT[char.lower()]) > 1
        ):
            # Send a wrong adjacent key
            wrong = random.choice(
                [k for k in _ADJACENT[char.lower()] if k != char.lower()]
            )
            wrong_char = wrong.upper() if char.isupper() else wrong
            element.send_keys(wrong_char)
            _delay()
            # Correct it
            element.send_keys(Keys.BACKSPACE)
            _delay()

        element.send_keys(char)
        _delay()
