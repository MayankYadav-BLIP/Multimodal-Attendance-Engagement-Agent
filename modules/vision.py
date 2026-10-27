import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "models", "face_detector.tflite"
)


class FaceDetector:
    def __init__(self, min_confidence=0.5):
        options = vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.IMAGE,
            min_detection_confidence=min_confidence,
        )
        self.detector = vision.FaceDetector.create_from_options(options)

    def detect(self, frame_bgr):
        """Takes an OpenCV BGR frame, returns a list of (x, y, w, h, score)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.detector.detect(mp_image)

        faces = []
        for d in result.detections:
            box = d.bounding_box
            score = d.categories[0].score
            faces.append((box.origin_x, box.origin_y, box.width, box.height, score))
        return faces