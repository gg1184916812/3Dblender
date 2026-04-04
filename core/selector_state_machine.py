"""
Smart Align Pro - Selector State Machine  v7.5.5
Item 7: formal state machine for all interactive selectors.

States:
    IDLE          → nothing active
    HOVER         → cursor near geometry, no valid snap yet
    LIVE_SNAP     → valid non-RAY snap locked to cursor
    STICKY_SNAP   → cursor left geometry; last valid snap preserved
    CONFIRM_READY → sticky/live snap is ready, one click will confirm
    CONFIRMED     → point confirmed, advancing to next stage

Transitions are triggered by events from the operator modal.
This is a lightweight plain-Python SM; no Blender dependencies.
"""

from typing import Optional, Callable


# ─────────────────────────────────────────────────────────────
# State constants
# ─────────────────────────────────────────────────────────────

IDLE          = "IDLE"
HOVER         = "HOVER"
LIVE_SNAP     = "LIVE_SNAP"
STICKY_SNAP   = "STICKY_SNAP"
CONFIRM_READY = "CONFIRM_READY"
CONFIRMED     = "CONFIRMED"

ALL_STATES = (IDLE, HOVER, LIVE_SNAP, STICKY_SNAP, CONFIRM_READY, CONFIRMED)

# Human-readable labels (zh-TW)
STATE_LABELS = {
    IDLE:          "待機",
    HOVER:         "懸停",
    LIVE_SNAP:     "即時吸附",
    STICKY_SNAP:   "🔒 鎖定最後有效點",
    CONFIRM_READY: "準備確認",
    CONFIRMED:     "已確認",
}

# State colors for HUD (RGBA)
STATE_COLORS = {
    IDLE:          (0.5,  0.5,  0.5,  0.8),
    HOVER:         (0.8,  0.8,  0.2,  0.9),
    LIVE_SNAP:     (0.2,  0.9,  0.2,  1.0),
    STICKY_SNAP:   (1.0,  0.65, 0.1,  1.0),
    CONFIRM_READY: (0.2,  0.6,  1.0,  1.0),
    CONFIRMED:     (0.2,  1.0,  0.4,  1.0),
}


# ─────────────────────────────────────────────────────────────
# SelectorStateMachine
# ─────────────────────────────────────────────────────────────

class SelectorStateMachine:
    """
    Lightweight state machine for one pick-point slot inside a modal operator.

    Usage (inside a modal operator):
        self._sm = SelectorStateMachine()

        # on MOUSEMOVE:
        if got_live_snap:
            self._sm.on_live_snap()
        elif had_sticky:
            self._sm.on_sticky()
        else:
            self._sm.on_hover()

        # on LEFTMOUSE PRESS (after resolving effective snap):
        if effective_snap:
            self._sm.on_confirm()
        else:
            self._sm.on_miss()

        # read current state for HUD:
        color = self._sm.color
        label = self._sm.label
    """

    def __init__(self, on_state_change: Optional[Callable] = None):
        self._state: str = IDLE
        self._prev:  str = IDLE
        self._on_change = on_state_change

    # ── transitions ───────────────────────────────────────────

    def on_hover(self):
        """Cursor over geometry but no valid snap candidate."""
        self._transition(HOVER)

    def on_live_snap(self):
        """Valid non-RAY snap candidate is active under cursor."""
        self._transition(LIVE_SNAP)

    def on_sticky(self):
        """Cursor left geometry; sticky/last_valid snap is preserved."""
        self._transition(STICKY_SNAP)

    def on_idle(self):
        """Operator just started or was reset."""
        self._transition(IDLE)

    def on_confirm_ready(self):
        """Snap is locked and user can confirm; upgrade STICKY → CONFIRM_READY."""
        if self._state in (LIVE_SNAP, STICKY_SNAP):
            self._transition(CONFIRM_READY)

    def on_confirm(self):
        """User clicked and confirmed the snap point."""
        self._transition(CONFIRMED)

    def on_miss(self):
        """User clicked but no snap was available."""
        # Stay in current state; caller may show warning
        pass

    def on_advance(self):
        """Stage advanced to next pick point — reset for new slot."""
        self._transition(IDLE)

    def on_cancel(self):
        self._transition(IDLE)

    # ── read-only props ───────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def label(self) -> str:
        return STATE_LABELS.get(self._state, self._state)

    @property
    def color(self) -> tuple:
        return STATE_COLORS.get(self._state, (0.5, 0.5, 0.5, 0.8))

    @property
    def is_sticky(self) -> bool:
        return self._state in (STICKY_SNAP, CONFIRM_READY)

    @property
    def is_live(self) -> bool:
        return self._state == LIVE_SNAP

    @property
    def has_snap(self) -> bool:
        return self._state in (LIVE_SNAP, STICKY_SNAP, CONFIRM_READY)

    @property
    def changed(self) -> bool:
        return self._state != self._prev

    def reset_changed(self):
        self._prev = self._state

    # ── internal ──────────────────────────────────────────────

    # Legal transitions: None means any state may go there
    _LEGAL: dict = {
        IDLE:          {IDLE, HOVER, LIVE_SNAP, STICKY_SNAP},
        HOVER:         {IDLE, HOVER, LIVE_SNAP, STICKY_SNAP},
        LIVE_SNAP:     {IDLE, HOVER, LIVE_SNAP, STICKY_SNAP, CONFIRM_READY, CONFIRMED},
        STICKY_SNAP:   {IDLE, HOVER, LIVE_SNAP, STICKY_SNAP, CONFIRM_READY, CONFIRMED},
        CONFIRM_READY: {IDLE, HOVER, LIVE_SNAP, STICKY_SNAP, CONFIRM_READY, CONFIRMED},
        CONFIRMED:     {IDLE},
    }

    def _transition(self, new: str):
        if new not in ALL_STATES:
            return
        allowed = self._LEGAL.get(self._state, set(ALL_STATES))
        if new not in allowed:
            # Illegal transition: log but don't crash; force via IDLE
            print(f"[SAP][SM] illegal transition {self._state} → {new}, routing via IDLE")
            self._prev  = self._state
            self._state = IDLE
            if self._on_change:
                try: self._on_change(self._prev, IDLE)
                except Exception: pass
        self._prev  = self._state
        self._state = new
        if self._on_change and self._prev != self._state:
            try:
                self._on_change(self._prev, self._state)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# Module-level convenience
# ─────────────────────────────────────────────────────────────

def new_sm(on_change: Optional[Callable] = None) -> SelectorStateMachine:
    """Create a fresh SelectorStateMachine."""
    return SelectorStateMachine(on_change)
