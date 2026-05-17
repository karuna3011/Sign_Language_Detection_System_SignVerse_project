import pymysql
import pymysql.cursors
from flask import current_app, g


def get_db():
    """Get database connection, creating one if needed for this request."""
    if 'db' not in g:
        g.db = pymysql.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password='Palneha@77',
            database=current_app.config['MYSQL_DB'],
            port=current_app.config['MYSQL_PORT'],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            charset='utf8mb4'
        )
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False, commit=False):
    """Execute a query and return results."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, args)
    if commit:
        db.commit()
    rv = cursor.fetchall()
    cursor.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute an INSERT/UPDATE/DELETE and return lastrowid."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, args)
    db.commit()
    lastid = cursor.lastrowid
    cursor.close()
    return lastid


def init_db_schema():
    """Initialize the database schema."""
    import os
    db = get_db()
    cursor = db.cursor()
    
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        sql = f.read()
    
    # Execute each statement
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    for statement in statements:
        if statement:
            cursor.execute(statement)
    
    db.commit()
    cursor.close()
    print("Database schema initialized!")
