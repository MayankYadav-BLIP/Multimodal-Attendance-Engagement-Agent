import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "models", "face_landmarker.task"
)

# landmark indices
NOSE_TIP, LEFT_EYE_OUTER, RIGHT_EYE_OUTER, CHIN = 1, 33, 263, 152


class HeadPoseEstimator:
    def __init__(self, max_faces=5):
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=max_faces,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

    def estimate(self, frame_bgr):
        """Returns a list of dicts: center (x, y in pixels), yaw, pitch.
        yaw   ~0.5 = facing camera, towards 0 or 1 = turned sideways
        pitch ~ ratio of nose position between eye line and chin
        """
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect(mp_image)

        poses = []
        for lm in result.face_landmarks:
            nose, le, re, chin = lm[NOSE_TIP], lm[LEFT_EYE_OUTER], lm[RIGHT_EYE_OUTER], lm[CHIN]

            eye_span = re.x - le.x
            if abs(eye_span) < 1e-6:
                continue
            yaw = (nose.x - le.x) / eye_span

            eye_y = (le.y + re.y) / 2
            face_h = chin.y - eye_y
            if abs(face_h) < 1e-6:
                continue
            pitch = (nose.y - eye_y) / face_h

            poses.append({
                "center": (int(nose.x * w), int(nose.y * h)),
                "yaw": yaw,
                "pitch": pitch,
            })
        return poses