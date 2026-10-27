import time

MAX_FAST_ATTEMPTS = 25   # tries (about 4 per second) before a face is shown as Unknown
VOTES_NEEDED = 3         # the same student must match this many times before we trust it


def face_for_box(box, rows):
    """Finds the recognizer's face row whose centre lies inside a tracked box."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    best, best_d = None, None
    for row in rows:
        rx, ry, rw, rh = row[:4]
        rcx, rcy = rx + rw / 2, ry + rh / 2
        if not (x <= rcx <= x + w and y <= rcy <= y + h):
            continue
        d = (rcx - cx) ** 2 + (rcy - cy) ** 2
        if best is None or d < best_d:
            best, best_d = row, d
    return best


class IdentityManager:
    """Works out which student each tracked face is, and marks students present."""

    def __init__(self, recognizer, roster):
        self.rec = recognizer
        self.roster = roster      # list of {"id", "roll_no", "name", "embedding"}
        self.identity = {}        # track id -> index in roster
        self.votes = {}
        self.attempts = {}
        self.present_at = {}      # student id -> "HH:MM:SS" when first marked present
        self.events = []

    def update(self, frame, people, frame_no, now=None):
        due = []
        for p in people:
            tid = p["id"]
            if tid in self.identity:
                continue
            step = 4 if self.attempts.get(tid, 0) < MAX_FAST_ATTEMPTS else 20
            if frame_no % step == 0:
                due.append(p)

        if due:
            rows = self.rec.detect(frame)
            for p in due:
                row = face_for_box(p["box"], rows)
                if row is None:
                    continue
                tid = p["id"]
                self.attempts[tid] = self.attempts.get(tid, 0) + 1
                idx, _ = self.rec.best_match(self.rec.embed(frame, row), self.roster)
                if idx is not None:
                    v = self.votes.setdefault(tid, {})
                    v[idx] = v.get(idx, 0) + 1
                    if v[idx] >= VOTES_NEEDED:
                        self.identity[tid] = idx

        stamp = time.strftime("%H:%M:%S", time.localtime(now if now else time.time()))
        info = {}
        for p in people:
            tid = p["id"]
            idx = self.identity.get(tid)
            if idx is not None:
                student = self.roster[idx]
                label = "Roll %s %s" % (student["roll_no"], student["name"])
                if p["present"] and student["id"] not in self.present_at:
                    self.present_at[student["id"]] = stamp
                    self.events.append({"label": label, "event": "marked_present", "time": stamp})
                state = "known"
            elif self.attempts.get(tid, 0) >= MAX_FAST_ATTEMPTS:
                state, label = "unknown", "Unknown"
            else:
                state, label = "identifying", "Identifying..."
            info[tid] = {"label": label, "state": state}
        return info

    def roster_status(self, running=True):
        rows = []
        for s in self.roster:
            seen = self.present_at.get(s["id"])
            if seen:
                status = "Present"
            else:
                status = "Not yet" if running else "Absent"
            rows.append({"roll_no": s["roll_no"], "name": s["name"],
                         "status": status, "first_seen": seen})
        return rows

    def results(self):
        return [
            {
                "student_id": s["id"],
                "roll_no": s["roll_no"],
                "name": s["name"],
                "status": "present" if s["id"] in self.present_at else "absent",
                "first_seen": self.present_at.get(s["id"]),
            }
            for s in self.roster
        ]