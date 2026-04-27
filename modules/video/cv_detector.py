import cv2

CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
_face_cascade = None


def _get_cascade():
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
    return _face_cascade


def detect_and_annotate(frame, emotion_text=""):
    cascade = _get_cascade()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
    annotated = frame.copy()
    coords = []
    for (x, y, w, h) in faces:
        coords.append((int(x), int(y), int(w), int(h)))
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
        if emotion_text:
            label = str(emotion_text)
            cv2.putText(
                annotated, label, (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )
    return annotated, coords
