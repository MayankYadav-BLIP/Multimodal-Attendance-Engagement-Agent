import time
from collections import Counter
from modules.attention import classify


def match_pose(box, poses):
    """Find the head pose whose nose point lies inside this tracked face box."""
    x, y, w, h = box
    for p in poses:
        cx, cy = p["center"]
        if x <= cx <= x + w and y <= cy <= y + h:
            return p
    return None


class EngagementScorer:
    def __init__(self, interval=5.0):
        self.interval = interval
        self.window_start = None
        self.timeline = []
        self._reset_window()

    def _reset_window(self):
        self.frame_scores = []
        self.frame_people = []
        self.frame_speaking = []
        self.status_counts = Counter()
        self.inactive_count = 0
        self.person_frames = 0

    @staticmethod
    def person_score(attentive, inactive):
        # 60 points for facing the front, 40 points for not being inactive
        return (60 if attentive else 0) + (0 if inactive else 40)

    def update(self, people, moves, poses, speaking, now=None):
        now = time.time() if now is None else now
        if self.window_start is None:
            self.window_start = now

        results = []
        for p in people:
            pose = match_pose(p["box"], poses)
            if pose is None:
                status, attentive = "NO POSE", False
            else:
                status, attentive = classify(pose["yaw"], pose["pitch"])
            inactive = moves[p["id"]]["inactive"]

            self.status_counts[status] += 1
            self.person_frames += 1
            if inactive:
                self.inactive_count += 1

            results.append({
                "id": p["id"],
                "status": status,
                "attentive": attentive,
                "inactive": inactive,
                "score": self.person_score(attentive, inactive),
            })

        if results:
            self.frame_scores.append(sum(r["score"] for r in results) / len(results))
        self.frame_people.append(len(results))
        self.frame_speaking.append(1 if speaking else 0)

        if now - self.window_start >= self.interval:
            self._close_window(now)

        return results

    def _close_window(self, now):
        n = len(self.frame_people)
        pf = self.person_frames
        entry = {
            "time": time.strftime("%H:%M:%S", time.localtime(now)),
            "avg_people": round(sum(self.frame_people) / n, 1) if n else 0,
            "engagement": round(sum(self.frame_scores) / len(self.frame_scores), 1)
            if self.frame_scores else None,
            "speaking_pct": round(100 * sum(self.frame_speaking) / n) if n else 0,
            "inactive_pct": round(100 * self.inactive_count / pf) if pf else 0,
            "status_pct": {s: round(100 * c / pf) for s, c in self.status_counts.items()}
            if pf else {},
        }
        self.timeline.append(entry)
        self.window_start = now
        self._reset_window()

    def finish(self, now=None):
        now = time.time() if now is None else now
        if self.frame_people:
            self._close_window(now)