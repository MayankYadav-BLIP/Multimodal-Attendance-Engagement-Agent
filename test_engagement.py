import time
import cv2
from modules.vision import FaceDetector
from modules.tracker import PresenceTracker
from modules.head_pose import HeadPoseEstimator
from modules.movement import MovementMonitor
from modules.audio import AudioMonitor
from modules.engagement import EngagementScorer

detector = FaceDetector()
estimator = HeadPoseEstimator()
tracker = PresenceTracker(presence_seconds=2.0)
monitor = MovementMonitor(move_threshold=30, inactive_after=5.0)
audio = AudioMonitor()
scorer = EngagementScorer(interval=5.0)

audio.start()
cap = cv2.VideoCapture(0)
start = time.time()
while True:
    ok, frame = cap.read()
    if not ok:
        break

    people = tracker.update(detector.detect(frame))
    moves = monitor.update(people)
    poses = estimator.estimate(frame)
    speaking = audio.is_speaking
    results = scorer.update(people, moves, poses, speaking)

    for p, r in zip(people, results):
        x, y, w, h = p["box"]
        color = (0, 200, 0) if r["score"] >= 60 else (0, 0, 255)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(frame, f"ID {p['id']} {r['status']} score {r['score']}",
                    (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    audio_text = "Audio: SPEAKING" if speaking else "Audio: quiet"
    cv2.putText(frame, audio_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    elapsed = time.time() - start
    if elapsed >= 30:
        break
    if elapsed < 10:
        phase = "1: FACE FRONT, COUNT ALOUD"
    elif elapsed < 20:
        phase = "2: TURN HEAD LEFT, QUIET"
    else:
        phase = "3: FACE FRONT, STILL, QUIET"
    cv2.putText(frame, f"{elapsed:.0f}s  Phase {phase}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.imshow("Engagement test (press q to quit)", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
audio.stop()
scorer.finish()

print("\nTIMELINE (one row per 5 seconds)")
for row in scorer.timeline:
    print(row)