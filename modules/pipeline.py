import threading
import time

import cv2

from modules.vision import FaceDetector
from modules.tracker import PresenceTracker
from modules.head_pose import HeadPoseEstimator
from modules.movement import MovementMonitor
from modules.audio import AudioMonitor
from modules.engagement import EngagementScorer
from modules.recognition import FaceRecognizer
from modules.identity import IdentityManager

MIN_SESSION_SECONDS = 10


def empty_stats():
    return {
        "running": False,
        "error": None,
        "saved_session_id": None,
        "people": 0,
        "present": 0,
        "absent": 0,
        "total": 0,
        "engagement": None,
        "speaking": False,
        "audio_ok": True,
        "persons": [],
        "roster": [],
        "timeline": [],
        "attendance": [],
    }


class Pipeline:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.latest_jpeg = None
        self.stats = empty_stats()
        self.detector = None
        self.estimator = None
        self.info = None
        self.roster = []
        self.on_finish = None

    def start(self, info, roster, on_finish):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.latest_jpeg = None
            self.info = info
            self.roster = roster
            self.on_finish = on_finish
            self.stats = empty_stats()
            self.stats["running"] = True
            self.stats["total"] = len(roster)
            self.stats["absent"] = len(roster)
            self.stats["roster"] = [
                {"roll_no": s["roll_no"], "name": s["name"],
                 "status": "Not yet", "first_seen": None}
                for s in roster
            ]
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        with self.lock:
            self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def get_frame(self):
        with self.lock:
            return self.latest_jpeg

    def get_stats(self):
        with self.lock:
            return dict(self.stats)

    def clear_saved(self):
        with self.lock:
            if not self.running:
                self.stats["saved_session_id"] = None
                self.stats["error"] = None

    def _fail(self, message):
        with self.lock:
            self.running = False
            self.stats["running"] = False
            self.stats["error"] = message

    def _run(self):
        try:
            if self.detector is None:
                self.detector = FaceDetector()
                self.estimator = HeadPoseEstimator()
            recognizer = FaceRecognizer()
        except Exception as e:
            self._fail("Model load failed: %s" % e)
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self._fail("Could not open the webcam. Close any other app or window using it.")
            return

        tracker = PresenceTracker(presence_seconds=2.0)
        monitor = MovementMonitor(move_threshold=30, inactive_after=30.0)
        scorer = EngagementScorer(interval=5.0)
        identities = IdentityManager(recognizer, self.roster)

        audio = AudioMonitor()
        audio_ok = True
        try:
            audio.start()
        except Exception:
            audio_ok = False

        info = self.info
        total = len(self.roster)
        started_at = time.time()
        frame_no = 0

        try:
            while True:
                with self.lock:
                    if not self.running:
                        break

                ok, frame = cap.read()
                if not ok:
                    break
                frame_no += 1

                people = tracker.update(self.detector.detect(frame))
                moves = monitor.update(people)
                poses = self.estimator.estimate(frame)
                speaking = audio_ok and audio.is_speaking
                results = scorer.update(people, moves, poses, speaking)
                who = identities.update(frame, people, frame_no)

                persons = []
                for p, r in zip(people, results):
                    x, y, w, h = [int(v) for v in p["box"]]
                    ident = who[p["id"]]
                    if ident["state"] == "known":
                        color = (0, 200, 0) if r["score"] >= 60 else (0, 0, 255)
                    else:
                        color = (0, 165, 255)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame, "%s | %s %d" % (ident["label"], r["status"], r["score"]),
                                (x, max(y - 8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
                    persons.append({
                        "label": ident["label"],
                        "state": ident["state"],
                        "present": p["present"] and ident["state"] == "known",
                        "status": r["status"],
                        "score": r["score"],
                        "inactive": r["inactive"],
                    })

                enc_ok, buf = cv2.imencode(".jpg", frame)
                if not enc_ok:
                    continue

                avg = round(sum(r["score"] for r in results) / len(results), 1) if results else None
                present_total = len(identities.present_at)

                with self.lock:
                    self.latest_jpeg = buf.tobytes()
                    self.stats = {
                        "running": True,
                        "error": None,
                        "saved_session_id": None,
                        "people": len(people),
                        "present": present_total,
                        "absent": total - present_total,
                        "total": total,
                        "engagement": avg,
                        "speaking": bool(speaking),
                        "audio_ok": audio_ok,
                        "persons": persons,
                        "roster": identities.roster_status(running=True),
                        "timeline": list(scorer.timeline),
                        "attendance": list(identities.events),
                    }
        finally:
            cap.release()
            if audio_ok:
                audio.stop()
            scorer.finish()
            ended_at = time.time()

            saved_id = None
            save_error = None
            if ended_at - started_at < MIN_SESSION_SECONDS:
                save_error = ("The session was shorter than %d seconds, so it was not saved. "
                              "Let it run a little longer." % MIN_SESSION_SECONDS)
            else:
                try:
                    if self.on_finish:
                        saved_id = self.on_finish(info, started_at, ended_at,
                                                  list(scorer.timeline),
                                                  identities.results())
                except Exception as e:
                    save_error = "Could not save the session: %s" % e

            with self.lock:
                self.running = False
                self.stats["running"] = False
                self.stats["people"] = 0
                self.stats["persons"] = []
                self.stats["roster"] = identities.roster_status(running=False)
                self.stats["timeline"] = list(scorer.timeline)
                self.stats["attendance"] = list(identities.events)
                self.stats["saved_session_id"] = saved_id
                if save_error:
                    self.stats["error"] = save_error