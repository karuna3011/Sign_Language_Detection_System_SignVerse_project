from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import query_db, execute_db
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = query_db('SELECT role FROM users WHERE id=%s', (user_id,), one=True)
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    # Total users
    total_users = query_db('SELECT COUNT(*) as cnt FROM users WHERE role="user"', one=True)
    
    # Users logged in today
    logged_today = query_db(
        'SELECT COUNT(DISTINCT user_id) as cnt FROM login_sessions WHERE DATE(login_time)=CURDATE()',
        one=True
    )
    
    # Active sessions (no logout)
    active_sessions = query_db(
        'SELECT COUNT(*) as cnt FROM login_sessions WHERE logout_time IS NULL AND login_time > DATE_SUB(NOW(), INTERVAL 8 HOUR)',
        one=True
    )
    
    # Total gestures detected today
    gestures_today = query_db(
        'SELECT COUNT(*) as cnt FROM gesture_logs WHERE DATE(detected_at)=CURDATE()',
        one=True
    )
    
    # Total gestures all time
    total_gestures = query_db('SELECT COUNT(*) as cnt FROM gesture_logs', one=True)
    
    # Most popular gestures
    popular_gestures = query_db(
        '''SELECT gesture_label, COUNT(*) as count 
           FROM gesture_logs GROUP BY gesture_label 
           ORDER BY count DESC LIMIT 10'''
    )
    
    # Recent user registrations (last 7 days)
    recent_registrations = query_db(
        '''SELECT DATE(created_at) as date, COUNT(*) as count 
           FROM users WHERE role="user" AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
           GROUP BY DATE(created_at) ORDER BY date DESC'''
    )
    for r in recent_registrations:
        if r['date']:
            r['date'] = r['date'].isoformat()
    
    # Gestures per day (last 7 days)
    gestures_per_day = query_db(
        '''SELECT DATE(detected_at) as date, COUNT(*) as count
           FROM gesture_logs WHERE detected_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
           GROUP BY DATE(detected_at) ORDER BY date ASC'''
    )
    for g in gestures_per_day:
        if g['date']:
            g['date'] = g['date'].isoformat()
    
    return jsonify({
        'stats': {
            'total_users': total_users['cnt'] if total_users else 0,
            'logged_today': logged_today['cnt'] if logged_today else 0,
            'active_sessions': active_sessions['cnt'] if active_sessions else 0,
            'gestures_today': gestures_today['cnt'] if gestures_today else 0,
            'total_gestures': total_gestures['cnt'] if total_gestures else 0,
        },
        'popular_gestures': popular_gestures,
        'recent_registrations': recent_registrations,
        'gestures_per_day': gestures_per_day
    }), 200


@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '')
    offset = (page - 1) * per_page
    
    if search:
        users = query_db(
            '''SELECT u.id, u.username, u.email, u.role, u.avatar_color, u.created_at, u.last_login, u.is_active,
               COUNT(DISTINCT gl.id) as total_gestures,
               COUNT(DISTINCT ls.id) as total_sessions
               FROM users u
               LEFT JOIN gesture_logs gl ON u.id=gl.user_id
               LEFT JOIN login_sessions ls ON u.id=ls.user_id
               WHERE (u.username LIKE %s OR u.email LIKE %s) AND u.role="user"
               GROUP BY u.id ORDER BY u.created_at DESC LIMIT %s OFFSET %s''',
            (f'%{search}%', f'%{search}%', per_page, offset)
        )
    else:
        users = query_db(
            '''SELECT u.id, u.username, u.email, u.role, u.avatar_color, u.created_at, u.last_login, u.is_active,
               COUNT(DISTINCT gl.id) as total_gestures,
               COUNT(DISTINCT ls.id) as total_sessions
               FROM users u
               LEFT JOIN gesture_logs gl ON u.id=gl.user_id
               LEFT JOIN login_sessions ls ON u.id=ls.user_id
               WHERE u.role="user"
               GROUP BY u.id ORDER BY u.created_at DESC LIMIT %s OFFSET %s''',
            (per_page, offset)
        )
    
    for u in users:
        for key in ['created_at', 'last_login']:
            if u[key]:
                u[key] = u[key].isoformat()
    
    total = query_db('SELECT COUNT(*) as cnt FROM users WHERE role="user"', one=True)
    return jsonify({'users': users, 'total': total['cnt'] if total else 0}), 200


@admin_bp.route('/users/<int:user_id>/activity', methods=['GET'])
@admin_required
def user_activity(user_id):
    gestures = query_db(
        '''SELECT gesture_label, confidence, source, detected_at 
           FROM gesture_logs WHERE user_id=%s ORDER BY detected_at DESC LIMIT 50''',
        (user_id,)
    )
    for g in gestures:
        if g['detected_at']:
            g['detected_at'] = g['detected_at'].isoformat()
    
    sessions = query_db(
        '''SELECT login_time, logout_time, ip_address FROM login_sessions 
           WHERE user_id=%s ORDER BY login_time DESC LIMIT 10''',
        (user_id,)
    )
    for s in sessions:
        for key in ['login_time', 'logout_time']:
            if s[key]:
                s[key] = s[key].isoformat()
    
    return jsonify({'gestures': gestures, 'sessions': sessions}), 200


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = query_db('SELECT is_active FROM users WHERE id=%s AND role="user"', (user_id,), one=True)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    new_status = 0 if user['is_active'] else 1
    execute_db('UPDATE users SET is_active=%s WHERE id=%s', (new_status, user_id))
    return jsonify({'message': 'Status updated', 'is_active': bool(new_status)}), 200


@admin_bp.route('/live-sessions', methods=['GET'])
@admin_required
def live_sessions():
    sessions = query_db(
        '''SELECT u.username, u.email, u.avatar_color, ls.login_time, ls.ip_address,
           COUNT(gl.id) as gestures_this_session
           FROM login_sessions ls
           JOIN users u ON ls.user_id=u.id
           LEFT JOIN gesture_logs gl ON gl.user_id=u.id AND gl.detected_at >= ls.login_time
           WHERE ls.logout_time IS NULL AND ls.login_time > DATE_SUB(NOW(), INTERVAL 8 HOUR)
           GROUP BY ls.id ORDER BY ls.login_time DESC'''
    )
    for s in sessions:
        if s['login_time']:
            s['login_time'] = s['login_time'].isoformat()
    return jsonify({'sessions': sessions}), 200
