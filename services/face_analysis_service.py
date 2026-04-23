import io
import base64
import time
import threading
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import uvicorn

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[FaceService] mediapipe not available")

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("[FaceService] deepface not available")

from collections import deque, Counter, defaultdict

EAR_THRESHOLD = 0.25
EAR_CONSEC_FRAMES = 15
MAR_THRESHOLD = 0.7
NOD_THRESHOLD = 10
DEEPFACE_EMOTIONS = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
ANGRY_SMOOTH_WINDOW = 10
ANGRY_TEMPERATURE = 0.6
ANGRY_MIN_CONF = 0.30
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
NOSE_TIP_IDX = 1

blink_counter = defaultdict(int)
yawn_counter = defaultdict(int)
nod_counter = defaultdict(int)
prev_y = defaultdict(lambda: None)
emotion_history = defaultdict(lambda: deque(maxlen=15))
neutral_like_sad = defaultdict(int)
angry_prob_history = defaultdict(lambda: deque(maxlen=ANGRY_SMOOTH_WINDOW))

face_mesh_instance = None
face_mesh_lock = threading.Lock()
_haar_cascade = None


def get_haar_cascade():
    global _haar_cascade
    if _haar_cascade is None:
        _haar_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    return _haar_cascade


def get_face_mesh():
    global face_mesh_instance
    if face_mesh_instance is not None:
        return face_mesh_instance
    if not MEDIAPIPE_AVAILABLE:
        return None
    try:
        mp_face_mesh = mp.solutions.face_mesh
        face_mesh_instance = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=5,
            refine_landmarks=True
        )
        print("[FaceService] MediaPipe FaceMesh initialized (GPU).")
        return face_mesh_instance
    except Exception as e:
        print(f"[FaceService] MediaPipe FaceMesh init failed: {e}")
        face_mesh_instance = None
        return None


def eye_aspect_ratio(eye):
    A = np.linalg.norm(eye[1] - eye[5])
    B = np.linalg.norm(eye[2] - eye[4])
    C = np.linalg.norm(eye[0] - eye[3])
    return (A + B) / (2.0 * C)


def mouth_aspect_ratio_mediapipe(landmarks):
    top = landmarks[13]
    bottom = landmarks[14]
    left = landmarks[78]
    right = landmarks[308]
    mar = np.linalg.norm(top - bottom) / np.linalg.norm(left - right)
    return mar


def angry_softmax_temperature(probs_dict, temp=ANGRY_TEMPERATURE):
    vec = np.array([probs_dict.get(e, 0.0) for e in DEEPFACE_EMOTIONS], dtype=np.float64)
    vec = np.clip(vec, 1e-9, None)
    log_scaled = np.log(vec) / temp
    log_scaled -= log_scaled.max()
    scaled = np.exp(log_scaled)
    return scaled / scaled.sum()


def is_angry_by_probability(face_idx, raw_probs_dict):
    prob_vec = angry_softmax_temperature(raw_probs_dict)
    angry_prob_history[face_idx].append(prob_vec)
    mean_vec = np.mean(angry_prob_history[face_idx], axis=0)
    angry_idx = DEEPFACE_EMOTIONS.index('angry')
    return float(mean_vec[angry_idx]) >= ANGRY_MIN_CONF


def analyze_frame_deepface(face_crop):
    if not DEEPFACE_AVAILABLE:
        return "Unknown", {}
    try:
        result = DeepFace.analyze(
            face_crop, actions=['emotion'],
            enforce_detection=False,
            detector_backend='skip',
            silent=True
        )
        emotion = result[0]['dominant_emotion']
        raw_probs = result[0].get('emotion', {})
        emotion = emotion.capitalize() if isinstance(emotion, str) else emotion
        return emotion, raw_probs
    except Exception as e:
        print(f"[FaceService] DeepFace error: {e}")
        try:
            result = DeepFace.analyze(
                face_crop, actions=['emotion'],
                enforce_detection=False,
                detector_backend='opencv',
                silent=True
            )
            emotion = result[0]['dominant_emotion']
            raw_probs = result[0].get('emotion', {})
            emotion = emotion.capitalize() if isinstance(emotion, str) else emotion
            return emotion, raw_probs
        except Exception:
            return "Unknown", {}


def analyze_with_mediapipe(frame, face_mesh):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    h, w, _ = frame.shape
    all_results = []
    if not results.multi_face_landmarks:
        return frame, []
    for face_idx, face_landmarks in enumerate(results.multi_face_landmarks):
        landmarks = np.array([(int(lm.x * w), int(lm.y * h)) for lm in face_landmarks.landmark])
        nose_point = landmarks[NOSE_TIP_IDX]
        xs, ys = landmarks[:, 0], landmarks[:, 1]
        x_min, x_max = xs.min(), xs.max()
        y_min, y_max = ys.min(), ys.max()
        margin = 30
        x_min_c = max(x_min - margin, 0)
        x_max_c = min(x_max + margin, w)
        y_min_c = max(y_min - margin, 0)
        y_max_c = min(y_max + margin, h)
        face_crop = frame[y_min_c:y_max_c, x_min_c:x_max_c]
        emotion, raw_probs = analyze_frame_deepface(face_crop)
        leftEye = landmarks[LEFT_EYE_IDX]
        rightEye = landmarks[RIGHT_EYE_IDX]
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0
        mar = mouth_aspect_ratio_mediapipe(landmarks)
        if emotion == "Fear":
            if mar < 0.5 and ear < 0.3:
                emotion = "Neutral"
        if raw_probs:
            if is_angry_by_probability(face_idx, raw_probs):
                emotion = "Angry"
            elif emotion == "Angry":
                emotion = "Neutral"
        if emotion == "Surprise":
            if ear < 0.22 or mar < 0.32:
                emotion = "Neutral"
        if (ear > 0.28 and mar > 0.5) and emotion in ["Fear", "Neutral"]:
            emotion = "Surprise"
        drowsy = False
        EYES_CLOSED_FRAMES = 50
        eyes_closed_long = blink_counter[face_idx] >= EYES_CLOSED_FRAMES
        head_center_y = (y_min + y_max) // 2
        head_center_x = (x_max + x_min) // 2
        head_tilted = abs(nose_point[0] - head_center_x) > 10 and nose_point[1] > head_center_y + 5
        if eyes_closed_long and head_tilted:
            drowsy = True
        if ear < EAR_THRESHOLD:
            blink_counter[face_idx] += 1
        else:
            blink_counter[face_idx] = 0
        yawning = False
        if mar > MAR_THRESHOLD:
            yawn_counter[face_idx] += 1
            if yawn_counter[face_idx] > 0:
                yawning = True
        else:
            yawn_counter[face_idx] = 0
        nodding = False
        if prev_y[face_idx] is not None and abs(prev_y[face_idx] - nose_point[1]) > NOD_THRESHOLD:
            nod_counter[face_idx] += 1
            if nod_counter[face_idx] > 0:
                nodding = True
        prev_y[face_idx] = nose_point[1]
        if emotion == "Sad":
            if mar < 0.3 and ear > EAR_THRESHOLD:
                neutral_like_sad[face_idx] += 1
            else:
                neutral_like_sad[face_idx] = 0
            if neutral_like_sad[face_idx] >= 5:
                emotion = "Neutral"
        left_corner_y = landmarks[78][1]
        right_corner_y = landmarks[308][1]
        center_top_y = landmarks[13][1]
        center_bottom_y = landmarks[14][1]
        center_y = (center_top_y + center_bottom_y) / 2
        if left_corner_y > center_y and right_corner_y > center_y:
            emotion = "Sad"
        emotion_history[face_idx].append(emotion)
        fear_count = sum([e == "Fear" for e in emotion_history[face_idx]])
        if fear_count < 0.4 * len(emotion_history[face_idx]):
            most_common_emotion = Counter(emotion_history[face_idx]).most_common(1)[0][0]
            display_emotion = most_common_emotion
        else:
            display_emotion = "Fear"
        color = (0, 0, 255) if display_emotion == "Angry" else (0, 255, 0)
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)
        cv2.putText(frame, f"Emotion: {display_emotion}", (x_min, y_min - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        if drowsy:
            state = "Drowsiness"
        elif yawning:
            state = "Yawning"
        elif nodding:
            state = "Head Nodding"
        else:
            state = display_emotion
        all_results.append({
            "emotion": display_emotion,
            "state": state,
            "ear": float(ear),
            "mar": float(mar),
            "raw_probs": {k: float(v) for k, v in raw_probs.items()} if raw_probs else {}
        })
    return frame, all_results


def analyze_with_haar(frame):
    cascade = get_haar_cascade()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return frame, []
    (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
    margin = 30
    x1 = max(x - margin, 0)
    y1 = max(y - margin, 0)
    x2 = min(x + w + margin, frame.shape[1])
    y2 = min(y + h + margin, frame.shape[0])
    face_crop = frame[y1:y2, x1:x2]
    if (w / frame.shape[1]) < 0.05:
        return frame, []
    emotion, raw_probs = analyze_frame_deepface(face_crop)
    max_prob = max(raw_probs.values()) if raw_probs else 0
    if max_prob < 0.25:
        emotion = "Neutral"
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(frame, emotion, (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    return frame, [{
        "emotion": emotion,
        "state": emotion,
        "raw_probs": {k: float(v) for k, v in raw_probs.items()} if raw_probs else {}
    }]


app = FastAPI(title="Face Analysis Service", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_mesh = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mediapipe": MEDIAPIPE_AVAILABLE,
        "deepface": DEEPFACE_AVAILABLE,
        "face_mesh_loaded": _mesh is not None
    }


@app.post("/analyze")
async def analyze(frame: UploadFile = File(...)):
    global _mesh
    content = await frame.read()
    np_arr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(content={"error": "invalid_frame"}, status_code=400)

    if _mesh is not None:
        try:
            annotated, results = analyze_with_mediapipe(img, _mesh)
            if results:
                _, img_encoded = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                return {
                    "method": "mediapipe+deepface",
                    "faces": results,
                    "annotated_frame_b64": base64.b64encode(img_encoded).decode('utf-8')
                }
        except Exception as e:
            print(f"[FaceService] MediaPipe analysis failed, falling back to Haar: {e}")
            _mesh = None

    annotated, results = analyze_with_haar(img)
    _, img_encoded = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return {
        "method": "haar+deepface",
        "faces": results,
        "annotated_frame_b64": base64.b64encode(img_encoded).decode('utf-8')
    }


@app.on_event("startup")
def startup():
    global _mesh
    _mesh = get_face_mesh()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)