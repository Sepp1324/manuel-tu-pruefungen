"""
FSRS (Free Spaced Repetition Scheduler) — v4.5/5 compatible implementation.

Pure-Python, no external deps. Implements the memory-state model with the
standard 19 default weights. Ratings:
    1 = Again  (nochmal / gar nicht gewusst)
    2 = Hard   (schwer)
    3 = Good   (gut)
    4 = Easy   (leicht)

Each card carries (stability, difficulty, state, last_review). The scheduler
returns the next interval in *days* for review cards, and uses short learning
steps (minutes) for new/relearning cards so ratings like "schwer -> 5 min" and
"leicht -> 1 Tag" behave intuitively.
"""

from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone

# FSRS-5 default parameters (19 weights)
DEFAULT_W = (
    0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046,
    1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315,
    2.9898, 0.51655, 0.6621,
)

DECAY = -0.5
FACTOR = 19.0 / 81.0  # 0.9 ** (1/DECAY) - 1

# States
NEW = 0
LEARNING = 1
REVIEW = 2
RELEARNING = 3

# Learning / relearning steps in MINUTES, indexed conceptually.
# We keep it simple: on a non-graduating rating in learning, schedule a short step.
LEARNING_STEPS_MIN = {
    1: 1,     # Again -> 1 min
    2: 5,     # Hard  -> 5 min
    3: 10,    # Good  -> 10 min (then graduates on next Good)
}
RELEARNING_STEP_MIN = {
    1: 5,     # Again -> 5 min
    2: 10,    # Hard  -> 10 min
    3: 10,
}


class Scheduler:
    def __init__(self, w=DEFAULT_W, request_retention=0.9, maximum_interval=36500):
        self.w = list(w)
        self.request_retention = request_retention
        self.maximum_interval = maximum_interval

    # ---- core FSRS formulas ----
    def _init_stability(self, rating: int) -> float:
        return max(self.w[rating - 1], 0.1)

    def _init_difficulty(self, rating: int) -> float:
        d = self.w[4] - math.exp(self.w[5] * (rating - 1)) + 1
        return self._clamp_d(d)

    def _clamp_d(self, d: float) -> float:
        return min(max(d, 1.0), 10.0)

    def _next_interval(self, stability: float, maximum_interval: int | None = None) -> int:
        interval = (stability / FACTOR) * (self.request_retention ** (1 / DECAY) - 1)
        interval = round(interval)
        cap = self.maximum_interval if maximum_interval is None else max(0, int(maximum_interval))
        return int(min(max(interval, 1), cap))

    def _retrievability(self, stability: float, elapsed_days: float) -> float:
        if stability <= 0:
            return 0.0
        return (1 + FACTOR * elapsed_days / stability) ** DECAY

    def _next_difficulty(self, d: float, rating: int) -> float:
        delta_d = -self.w[6] * (rating - 3)
        d_prime = d + delta_d * ((10 - d) / 9)
        # mean reversion toward difficulty of "Easy" init
        d_easy = self.w[4] - math.exp(self.w[5] * (4 - 1)) + 1
        d_new = self.w[7] * d_easy + (1 - self.w[7]) * d_prime
        return self._clamp_d(d_new)

    def _next_stability_recall(self, d: float, s: float, r: float, rating: int) -> float:
        hard_penalty = self.w[15] if rating == 2 else 1.0
        easy_bonus = self.w[16] if rating == 4 else 1.0
        s_inc = (
            math.exp(self.w[8])
            * (11 - d)
            * (s ** -self.w[9])
            * (math.exp(self.w[10] * (1 - r)) - 1)
            * hard_penalty
            * easy_bonus
        )
        return s * (s_inc + 1)

    def _next_stability_forget(self, d: float, s: float, r: float) -> float:
        s_forget = (
            self.w[11]
            * (d ** -self.w[12])
            * (((s + 1) ** self.w[13]) - 1)
            * math.exp(self.w[14] * (1 - r))
        )
        return min(s_forget, s)

    # ---- public API ----
    def review(self, card: dict, rating: int, now: datetime | None = None,
               max_interval_days: int | None = None) -> dict:
        """
        card: dict with keys state, stability, difficulty, last_review (iso or None), reps, lapses
        rating: 1..4
        returns updated card dict plus 'due' (iso) and 'scheduled_minutes'
        """
        now = now or datetime.now(timezone.utc)
        state = card.get("state", NEW)
        stability = card.get("stability") or 0.0
        difficulty = card.get("difficulty") or 0.0
        reps = card.get("reps", 0)
        lapses = card.get("lapses", 0)
        last = card.get("last_review")
        if isinstance(last, str) and last:
            last_dt = datetime.fromisoformat(last)
        else:
            last_dt = None
        elapsed_days = 0.0
        if last_dt is not None:
            elapsed_days = max((now - last_dt).total_seconds() / 86400.0, 0.0)

        scheduled_minutes = None

        if state == NEW:
            stability = self._init_stability(rating)
            difficulty = self._init_difficulty(rating)
            if rating == 4:  # Easy graduates straight to review
                state = REVIEW
                interval_days = self._next_interval(stability, max_interval_days)
                due = now + timedelta(days=interval_days)
            else:
                state = LEARNING
                mins = LEARNING_STEPS_MIN.get(rating, 10)
                scheduled_minutes = mins
                due = now + timedelta(minutes=mins)
        elif state in (LEARNING, RELEARNING):
            r = self._retrievability(stability, elapsed_days)
            if rating == 1:
                stability = self._next_stability_forget(difficulty, stability, r)
                difficulty = self._next_difficulty(difficulty, rating)
                mins = (LEARNING_STEPS_MIN if state == LEARNING else RELEARNING_STEP_MIN).get(1, 5)
                scheduled_minutes = mins
                due = now + timedelta(minutes=mins)
            elif rating in (2, 3):
                difficulty = self._next_difficulty(difficulty, rating)
                if rating == 3:
                    # graduate
                    state = REVIEW
                    interval_days = self._next_interval(stability, max_interval_days)
                    due = now + timedelta(days=interval_days)
                else:
                    mins = (LEARNING_STEPS_MIN if state == LEARNING else RELEARNING_STEP_MIN).get(2, 5)
                    scheduled_minutes = mins
                    due = now + timedelta(minutes=mins)
            else:  # Easy -> graduate with a bit more
                difficulty = self._next_difficulty(difficulty, rating)
                state = REVIEW
                interval_days = max(self._next_interval(stability, max_interval_days), 0)
                due = now + timedelta(days=interval_days)
        else:  # REVIEW
            r = self._retrievability(stability, elapsed_days)
            difficulty = self._next_difficulty(difficulty, rating)
            if rating == 1:
                lapses += 1
                stability = self._next_stability_forget(difficulty, stability, r)
                state = RELEARNING
                mins = RELEARNING_STEP_MIN.get(1, 5)
                scheduled_minutes = mins
                due = now + timedelta(minutes=mins)
            else:
                stability = self._next_stability_recall(difficulty, stability, r, rating)
                interval_days = self._next_interval(stability, max_interval_days)
                due = now + timedelta(days=interval_days)

        reps += 1
        return {
            "state": state,
            "stability": round(stability, 4),
            "difficulty": round(difficulty, 4),
            "reps": reps,
            "lapses": lapses,
            "last_review": now.isoformat(),
            "due": due.isoformat(),
            "scheduled_minutes": scheduled_minutes,
        }

    def preview(self, card: dict, now: datetime | None = None,
                max_interval_days: int | None = None) -> dict:
        """Return a human label of the next interval for each of the 4 ratings."""
        now = now or datetime.now(timezone.utc)
        out = {}
        for rating in (1, 2, 3, 4):
            res = self.review(dict(card), rating, now, max_interval_days=max_interval_days)
            due = datetime.fromisoformat(res["due"])
            delta = due - now
            out[rating] = _human_delta(delta)
        return out


def _human_delta(delta: timedelta) -> str:
    secs = delta.total_seconds()
    mins = secs / 60
    if mins < 60:
        return f"{max(round(mins),1)} min"
    hours = mins / 60
    if hours < 24:
        return f"{round(hours)} h"
    days = hours / 24
    if days < 30:
        return f"{round(days)} d"
    months = days / 30
    if months < 12:
        return f"{round(months)} mo"
    return f"{days/365:.1f} a"
