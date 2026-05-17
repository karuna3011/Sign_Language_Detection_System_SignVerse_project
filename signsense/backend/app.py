import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta


def create_app():
    app = Flask(__name__, static_folder='../frontend', static_url_path='')

    # ── Config ────────────────────────────────────────────────────────────────
    app.config['SECRET_KEY']         = os.environ.get('SECRET_KEY',     'signverse-secret-2024')
    app.config['JWT_SECRET_KEY']     = os.environ.get('JWT_SECRET_KEY', 'signverse-jwt-2024')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)

    # MySQL — edit these or set env vars
    app.config['MYSQL_HOST']     = os.environ.get('MYSQL_HOST',     'localhost')
    app.config['MYSQL_USER']     = os.environ.get('MYSQL_USER',     'root')
    app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
    app.config['MYSQL_DB']       = os.environ.get('MYSQL_DB',       'signlang_db')
    app.config['MYSQL_PORT']     = int(os.environ.get('MYSQL_PORT', 3306))

    CORS(app, resources={r'/api/*': {'origins': '*'}})
    JWTManager(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.auth    import auth_bp
    from routes.gesture import gesture_bp
    from routes.admin   import admin_bp
    from routes.user    import user_bp

    app.register_blueprint(auth_bp,    url_prefix='/api/auth')
    app.register_blueprint(gesture_bp, url_prefix='/api/gesture')
    app.register_blueprint(admin_bp,   url_prefix='/api/admin')
    app.register_blueprint(user_bp,    url_prefix='/api/user')

    # ── Frontend routes ───────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return send_from_directory('../frontend', 'index.html')

    @app.route('/admin')
    def admin_page():
        return send_from_directory('../frontend', 'admin.html')

    @app.errorhandler(404)
    def not_found(e):
        return send_from_directory('../frontend', 'index.html')

    return app


if __name__ == '__main__':
    app = create_app()
    print('\n🤟  SignVerse is running!')
    print('   User App  → http://localhost:5000')
    print('   Admin     → http://localhost:5000/admin')
    print('   Admin login: admin / Admin@123\n')
    app.run(debug=True, port=5000, host='0.0.0.0')
