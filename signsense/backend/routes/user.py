from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import query_db, execute_db

user_bp = Blueprint('user', __name__)


@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = query_db(
        'SELECT id, username, email, role, avatar_color, created_at, last_login FROM users WHERE id=%s',
        (user_id,), one=True
    )
    if not user:
        return jsonify({'error': 'Not found'}), 404
    for key in ['created_at', 'last_login']:
        if user[key]:
            user[key] = user[key].isoformat()
    return jsonify(user), 200


@user_bp.route('/stats', methods=['GET'])
@jwt_required()
def stats():
    user_id = get_jwt_identity()
    
    total_gestures = query_db(
        'SELECT COUNT(*) as cnt FROM gesture_logs WHERE user_id=%s', (user_id,), one=True
    )
    
    unique_gestures = query_db(
        'SELECT COUNT(DISTINCT gesture_label) as cnt FROM gesture_logs WHERE user_id=%s', (user_id,), one=True
    )
    
    today_gestures = query_db(
        'SELECT COUNT(*) as cnt FROM gesture_logs WHERE user_id=%s AND DATE(detected_at)=CURDATE()',
        (user_id,), one=True
    )
    
    recent = query_db(
        '''SELECT gesture_label, confidence, detected_at FROM gesture_logs 
           WHERE user_id=%s ORDER BY detected_at DESC LIMIT 10''',
        (user_id,)
    )
    for r in recent:
        if r['detected_at']:
            r['detected_at'] = r['detected_at'].isoformat()
    
    top_gestures = query_db(
        '''SELECT gesture_label, COUNT(*) as count FROM gesture_logs 
           WHERE user_id=%s GROUP BY gesture_label ORDER BY count DESC LIMIT 5''',
        (user_id,)
    )
    
    streak = query_db(
        '''SELECT COUNT(DISTINCT DATE(detected_at)) as days FROM gesture_logs 
           WHERE user_id=%s AND detected_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)''',
        (user_id,), one=True
    )
    
    return jsonify({
        'total_gestures': total_gestures['cnt'] if total_gestures else 0,
        'unique_gestures': unique_gestures['cnt'] if unique_gestures else 0,
        'today_gestures': today_gestures['cnt'] if today_gestures else 0,
        'streak_days': streak['days'] if streak else 0,
        'recent': recent,
        'top_gestures': top_gestures
    }), 200


@user_bp.route('/leaderboard', methods=['GET'])
@jwt_required()
def leaderboard():
    top = query_db(
        '''SELECT u.username, u.avatar_color, COUNT(gl.id) as total,
           COUNT(DISTINCT gl.gesture_label) as unique_g
           FROM users u
           LEFT JOIN gesture_logs gl ON u.id=gl.user_id
           WHERE u.role="user"
           GROUP BY u.id ORDER BY total DESC LIMIT 10'''
    )
    return jsonify({'leaderboard': top}), 200
