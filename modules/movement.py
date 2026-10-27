import math
import time


class MovementMonitor:
    def __init__(self, move_threshold=15, inactive_after=10.0):
        self.move_threshold = move_threshold  # pixels the face must shift to count as movement
        self.inactive_after = inactive_after  # seconds of stillness before "INACTIVE"
        self.state = {}

    def update(self, people, now=None):
        """people = the list returned by PresenceTracker.update().
        Returns {track_id: {"inactive_seconds": float, "inactive": bool}}"""
        now = time.time() if now is None else now
        result = {}
        seen = set()

        for p in people:
            tid = p["id"]
            x, y, w, h = p["box"]
            c = (x + w / 2, y + h / 2)
            seen.add(tid)

            if tid not in self.state:
                self.state[tid] = {"anchor": c, "last_move": now}
            else:
                s = self.state[tid]
                if math.dist(s["anchor"], c) > self.move_threshold:
                    s["anchor"] = c
                    s["last_move"] = now

            idle = now - self.state[tid]["last_move"]
            result[tid] = {
                "inactive_seconds": idle,
                "inactive": idle >= self.inactive_after,
            }

        for tid in list(self.state):
            if tid not in seen:
                del self.state[tid]

        return result