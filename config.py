"""
Configuration constants for the Microsoft Rewards autoclicker.
Adjust these values to fine-tune timing and behaviour.
"""

# ------------------------------------------------------------------
# Typing simulation
# ------------------------------------------------------------------
TYPING_SPEED_MIN_MS: int = 80   # Minimum delay between keystrokes (ms)
TYPING_SPEED_MAX_MS: int = 120  # Maximum delay between keystrokes (ms)

# Probability (0–1) of introducing a random typo on a given keystroke
TYPO_PROBABILITY: float = 0.04

# ------------------------------------------------------------------
# Searches per day
# ------------------------------------------------------------------
DAILY_SEARCHES_MIN: int = 30
DAILY_SEARCHES_MAX: int = 40

# ------------------------------------------------------------------
# Delays between searches (seconds)
# ------------------------------------------------------------------
BETWEEN_SEARCHES_MIN: int = 10
BETWEEN_SEARCHES_MAX: int = 30

# ------------------------------------------------------------------
# Article reading dwell time (seconds)
# ------------------------------------------------------------------
ARTICLE_DWELL_MIN: int = 20
ARTICLE_DWELL_MAX: int = 40

# Interval between simulated scroll/click actions while reading (seconds)
SCROLL_INTERVAL_MIN: int = 5
SCROLL_INTERVAL_MAX: int = 12

# Probability of opening a visible news item on the Bing homepage before a search
NEWS_READ_PROBABILITY: float = 0.50

# ------------------------------------------------------------------
# Daily schedule: blocks throughout the day
# Each entry is (start_hour, end_hour, fraction_of_daily_searches).
# Fractions must sum to 1.0.
# ------------------------------------------------------------------
DAILY_BLOCKS: list[tuple[int, int, float]] = [
    (8, 11, 0.35),   # Morning
    (14, 17, 0.35),  # Afternoon
    (20, 23, 0.30),  # Evening
]

# Extra random offset in seconds added between blocks
BLOCK_GAP_MIN: int = 60
BLOCK_GAP_MAX: int = 300

# ------------------------------------------------------------------
# Browser / Bing
# ------------------------------------------------------------------
BING_URL: str = "https://www.bing.com"
SEARCH_BAR_SELECTOR: str = "textarea#sb_form_q, input#sb_form_q"

# News/article selectors used to detect visible news cards on Bing
NEWS_CARD_SELECTORS: list[str] = [
    "a[href*='/news/']",
    ".news-card a",
    ".tabbed_news_card a",
    ".b_promoteItem a",
    "main a[href*='news']",
]

# Delay (seconds) after opening Bing before starting to type
PAGE_LOAD_WAIT_MIN: float = 1.5
PAGE_LOAD_WAIT_MAX: float = 3.5

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
LOG_DIR: str = "logs"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
