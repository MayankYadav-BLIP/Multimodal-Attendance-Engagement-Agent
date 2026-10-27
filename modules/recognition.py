import os

import cv2
import numpy as np

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
YUNET_PATH = os.path.join(BASE, "face_detector_yunet.onnx")
SFACE_PATH = os.path.join(BASE, "face_recognizer_sface.onnx")

# Cosine similarity needed to say "this is the same student".
# Higher = stricter (fewer wrong matches, more "Unknown"). Tune between 0.35 and 0.55.
MATCH_THRESHOLD = 0.40


class FaceRecognizer:
    def __init__(self, score_threshold=0.8):
        for path in (YUNET_PATH, SFACE_PATH):
            if not os.path.exists(path):
                raise FileNotFoundError("Missing model file: " + os.path.basename(path))
        self.detector = cv2.FaceDetectorYN.create(
            YUNET_PATH, "", (320, 320), score_threshold, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")

    def detect(self, frame_bgr):
        """Returns an N x 15 array: box, 5 landmarks, score. Empty if no faces."""
        h, w = frame_bgr.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame_bgr)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        return faces

    def embed(self, frame_bgr, face_row):
        """Turns one detected face into a 128-number fingerprint."""
        aligned = self.recognizer.alignCrop(frame_bgr, face_row)
        feature = self.recognizer.feature(aligned)
        return feature.flatten().astype(np.float32)

    @staticmethod
    def normalize(v):
        return v / (np.linalg.norm(v) + 1e-9)

    @staticmethod
    def similarity(a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    def best_match(self, embedding, roster):
        """roster = list of dicts that each have an 'embedding' (numpy array).
        Returns (index, similarity) if someone matches, else (None, best similarity)."""
        best_i, best_s = None, -1.0
        for i, student in enumerate(roster):
            s = self.similarity(embedding, student["embedding"])
            if s > best_s:
                best_i, best_s = i, s
        if best_i is not None and best_s >= MATCH_THRESHOLD:
            return best_i, best_s
        return None, best_s

    def template_from_images(self, images_bgr):
        """Builds one averaged fingerprint from several photos of one student.
        Returns (template or None, photos_used, photos_skipped)."""
        vectors = []
        skipped = 0
        for img in images_bgr:
            if img is None:
                skipped += 1
                continue

            h, w = img.shape[:2]
            if max(h, w) > 1280:
                scale = 1280.0 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))

            faces = self.detect(img)
            if len(faces) == 0:
                skipped += 1
                continue

            areas = sorted(((f[2] * f[3], i) for i, f in enumerate(faces)), reverse=True)
            if len(areas) > 1 and areas[1][0] > 0.5 * areas[0][0]:
                skipped += 1  # two similar-sized faces: not clear who this photo is of
                continue

            row = faces[areas[0][1]]
            vectors.append(self.normalize(self.embed(img, row)))

        if not vectors:
            return None, 0, skipped
        template = self.normalize(np.mean(vectors, axis=0))
        return template.astype(np.float32), len(vectors), skipped