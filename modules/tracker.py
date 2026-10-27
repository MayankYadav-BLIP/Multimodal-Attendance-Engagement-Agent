import math
import time


class PresenceTracker:
    def __init__(self, max_distance=80, max_missing=2.0, presence_seconds=5.0):
        self.max_distance = max_distance          # pixels a face may move between frames
        self.max_missing = max_missing            # seconds a face can vanish before track is dropped
        self.presence_seconds = presence_seconds  # seconds of sustained presence needed
        self.tracks = {}
        self.next_id = 1
        self.attendance_log = []

    @staticmethod
    def _centroid(face):
        x, y, w, h = face[:4]
        return (x + w / 2, y + h / 2)

    def _log(self, track_id, event, now):
        self.attendance_log.append({
            "id": track_id,
            "event": event,
            "time": time.strftime("%H:%M:%S", time.localtime(now)),
        })

    def update(self, faces, now=None):
        now = time.time() if now is None else now
        centroids = [self._centroid(f) for f in faces]
        unmatched = set(range(len(centroids)))

        # match existing tracks to detections, closest pairs first
        pairs = []
        for tid, t in self.tracks.items():
            for i in unmatched:
                d = math.dist(t["centroid"], centroids[i])
                if d <= self.max_distance:
                    pairs.append((d, tid, i))
        pairs.sort()

        used_tracks = set()
        for d, tid, i in pairs:
            if tid in used_tracks or i not in unmatched:
                continue
            t = self.tracks[tid]
            t["centroid"] = centroids[i]
            t["box"] = faces[i][:4]
            t["last_seen"] = now
            used_tracks.add(tid)
            unmatched.discard(i)

        # new tracks for detections that matched nothing
        for i in unmatched:
            self.tracks[self.next_id] = {
                "centroid": centroids[i],
                "box": faces[i][:4],
                "first_seen": now,
                "last_seen": now,
                "present": False,
            }
            self.next_id += 1

        # mark present after sustained presence, drop stale tracks
        for tid in list(self.tracks):
            t = self.tracks[tid]
            if now - t["last_seen"] > self.max_missing:
                self._log(tid, "left", now)
                del self.tracks[tid]
            elif not t["present"] and now - t["first_seen"] >= self.presence_seconds:
                t["present"] = True
                self._log(tid, "marked_present", now)

        return [
            {
                "id": tid,
                "box": t["box"],
                "present": t["present"],
                "seconds": now - t["first_seen"],
            }
            for tid, t in self.tracks.items()
            if t["last_seen"] == now
        ]