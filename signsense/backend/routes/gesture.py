"""
Gesture detection route.
Uses mediapipe==0.10.14 which ships mp.solutions.hands on Python 3.10.
Built-in ASL dataset (Kaggle-inspired, 32 gestures).
"""

from utils.gesture_words import get_word_for_gesture
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64
import numpy as np
import cv2
from utils.db import execute_db, query_db

gesture_bp = Blueprint('gesture', __name__)

_mp_hands = None

def get_mp_hands():
    global _mp_hands
    if _mp_hands is None:
        import mediapipe as mp
        _mp_hands = mp.solutions.hands
    return _mp_hands

ASL_GESTURES = {
    'A': 'Fist with thumb resting against the side',
    'B': 'All four fingers straight up together, thumb tucked across palm',
    'C': 'Hand curved into a C-shape',
    'D': 'Index finger up, others curl to touch thumb',
    'E': 'All fingers bent and tucked, thumb tucked in',
    'F': 'Index and thumb form a circle, three fingers point up',
    'G': 'Index finger points sideways, thumb parallel',
    'H': 'Index and middle point sideways together',
    'I': 'Pinky finger raised, fist',
    'J': 'Pinky up, trace a J shape in the air',
    'K': 'Index and middle form a V, thumb between them',
    'L': 'L-shape: index points up, thumb points out',
    'M': 'Three fingers folded over the thumb',
    'N': 'Two fingers folded over the thumb',
    'O': 'All fingers curve to meet thumb in an O',
    'P': 'Like K but pointing downward',
    'Q': 'Like G but pointing downward',
    'R': 'Index and middle fingers crossed',
    'S': 'Fist with thumb placed over the fingers',
    'T': 'Thumb inserted between index and middle fingers',
    'U': 'Index and middle fingers held up together',
    'V': 'Index and middle fingers spread in a V (peace sign)',
    'W': 'Index, middle, and ring fingers spread upward',
    'X': 'Index finger hooked/bent inward',
    'Y': 'Thumb and pinky extended outward (hang loose)',
    'Z': 'Index finger traces the letter Z in the air',
    'TP':   'Thumb pointing up - approval',
    'TD': 'Thumb pointing down - disapproval',
    'P':       'Two-finger V - peace / victory',
    'Hi':   'All five fingers extended and spread',
    'FT':        'All fingers closed - fist',
    'P':    'Index finger extended, others closed',
}


def decode_image(data_url):
    try:
        if ',' in data_url:
            data_url = data_url.split(',')[1]
        arr = np.frombuffer(base64.b64decode(data_url), np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def finger_states(lm):
    thumb = 1 if abs(lm[4].x - lm[0].x) > abs(lm[3].x - lm[0].x) else 0
    fingers = [thumb]
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        fingers.append(1 if lm[tip].y < lm[pip].y else 0)
    return fingers


def classify_gesture(hand_landmarks):
    lm = hand_landmarks.landmark
    f = finger_states(lm)
    thumb, idx, mid, ring, pinky = f
    total = sum(f)

    if total >= 4:
        return 'OPEN_HAND', 0.96
    if total == 0:
        return 'FIST', 0.97

    if thumb and not idx and not mid and not ring and not pinky:
        return ('THUMBS_UP', 0.93) if lm[4].y < lm[0].y - 0.08 else ('THUMBS_DOWN', 0.90)

    if not thumb and idx and not mid and not ring and not pinky:
        return 'POINTING', 0.94
    if not thumb and not idx and not mid and not ring and pinky:
        return 'I', 0.91

    if thumb and idx and not mid and not ring and not pinky:
        return 'L', 0.90
    if thumb and not idx and not mid and not ring and pinky:
        return 'Y', 0.91
    if not thumb and idx and mid and not ring and not pinky:
        spread = abs(lm[8].x - lm[12].x)
        return ('V', 0.89) if spread > 0.06 else ('U', 0.88)
    if not thumb and idx and not mid and not ring and pinky:
        return 'R', 0.82

    if not thumb and idx and mid and ring and not pinky:
        return 'W', 0.88
    if thumb and idx and mid and not ring and not pinky:
        return 'K', 0.84
    if not thumb and idx and mid and ring and pinky:
        return 'B', 0.87

    if thumb and total == 2:
        return 'F', 0.79

    return 'UNKNOWN', 0.50


@gesture_bp.route('/detect', methods=['POST'])
@jwt_required()
def detect_gesture():
    user_id = get_jwt_identity()
    data = request.get_json()
    image_data = data.get('image')
    source = data.get('source', 'webcam')

    if not image_data:
        return jsonify({'error': 'No image provided'}), 400

    img = decode_image(image_data)
    if img is None:
        return jsonify({'error': 'Invalid image data'}), 400

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results_data = []
    mp_hands = get_mp_hands()

    with mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:
        results = hands.process(img_rgb)

        if not results.multi_hand_landmarks:
            return jsonify({'detected': False, 'message': 'No hand detected in image'}), 200

        for hand_landmarks in results.multi_hand_landmarks:
            gesture, confidence = classify_gesture(hand_landmarks)

            execute_db(
                'INSERT INTO gesture_logs (user_id, gesture_label, confidence, source) VALUES (%s,%s,%s,%s)',
                (user_id, gesture, confidence, source)
            )
            execute_db(
                '''INSERT INTO learning_progress (user_id, gesture_label, attempts, correct, last_practiced)
                   VALUES (%s,%s,1,%s,NOW())
                   ON DUPLICATE KEY UPDATE
                   attempts=attempts+1, correct=correct+%s, last_practiced=NOW()''',
                (user_id, gesture,
                 1 if confidence > 0.80 else 0,
                 1 if confidence > 0.80 else 0)
            )

            results_data.append({
                'gesture': gesture,
                'word': get_word_for_gesture(gesture),
                'confidence': round(confidence, 3),
                'description': ASL_GESTURES.get(gesture, 'Unknown gesture'),
            })

    return jsonify({'detected': True, 'results': results_data}), 200


@gesture_bp.route('/history', methods=['GET'])
@jwt_required()
def gesture_history():
    user_id = get_jwt_identity()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page

    logs = query_db(
        '''SELECT gesture_label, confidence, source, detected_at
           FROM gesture_logs WHERE user_id=%s
           ORDER BY detected_at DESC LIMIT %s OFFSET %s''',
        (user_id, per_page, offset)
    )
    for log in logs:
        if log['detected_at']:
            log['detected_at'] = log['detected_at'].isoformat()

    total = query_db('SELECT COUNT(*) as cnt FROM gesture_logs WHERE user_id=%s', (user_id,), one=True)
    return jsonify({'logs': logs, 'total': total['cnt'] if total else 0}), 200


@gesture_bp.route('/progress', methods=['GET'])
@jwt_required()
def user_progress():
    user_id = get_jwt_identity()

    progress = query_db(
        '''SELECT gesture_label, attempts, correct, last_practiced,
           ROUND(IF(attempts>0, correct/attempts*100, 0), 1) AS accuracy
           FROM learning_progress WHERE user_id=%s
           ORDER BY last_practiced DESC''',
        (user_id,)
    )
    for p in progress:
        if p['last_practiced']:
            p['last_practiced'] = p['last_practiced'].isoformat()

    stats = query_db(
        '''SELECT COUNT(DISTINCT gesture_label) AS unique_gestures,
           SUM(attempts) AS total_attempts,
           SUM(correct) AS total_correct
           FROM learning_progress WHERE user_id=%s''',
        (user_id,), one=True
    )
    return jsonify({'progress': progress, 'stats': stats}), 200


@gesture_bp.route('/dataset', methods=['GET'])
def get_dataset():
    gestures = [
        {
            'label': k,
            'description': v,
            'category': 'ASL Alphabet' if len(k) == 1 else 'Common Gestures',
        }
        for k, v in ASL_GESTURES.items()
    ]
    return jsonify({
        'gestures': gestures,
        'total': len(gestures),
        'source': 'Kaggle ASL Gesture Dataset (built-in)',
    }), 200