# backtestbob_server.py

import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from models import db, AdminUser
from blog import blog_bp
from admin import admin_bp, login_manager as admin_login_manager
from compound_interest_calculator import create_dash_app as ci_factory
from pension_drawdown_calculator import create_dash_app as pd_factory
from werkzeug.security import generate_password_hash

# ── ENV & CONFIG ─────────────────────────────────────────────────────────
load_dotenv()
DB_FILE = os.getenv('DB_FILE', 'stocks.db')

# Flask application setup
app = Flask(__name__, static_folder='static', template_folder='templates')

# Expose current_year() in Jinja templates
app.jinja_env.globals['current_year'] = lambda: datetime.utcnow().year

app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'change_me'),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_FILE}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

# ── EXTENSIONS INITIALIZATION ─────────────────────────────────────────────
db.init_app(app)
Migrate(app, db)

admin_login_manager.init_app(app)
admin_login_manager.login_view = 'admin.login'

# ── REGISTER BLUEPRINTS ───────────────────────────────────────────────────
app.register_blueprint(blog_bp)   # Public blog routes
app.register_blueprint(admin_bp)  # Admin routes (protected via @login_required)

# ── PUBLIC ROUTES ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculators')
def calculators():
    return render_template('calculators.html')

# ── DATABASE SETUP & DEFAULT ADMIN SEEDING ─────────────────────────────────
def ensure_default_admin():
    """Create a default admin user if none exists."""
    if AdminUser.query.count() == 0:
        pwd_hash = generate_password_hash('changeme')
        admin = AdminUser(username='admin', password_hash=pwd_hash)
        db.session.add(admin)
        db.session.commit()

with app.app_context():
    # Create tables and seed admin
    db.create_all()
    ensure_default_admin()

# ── MOUNT DASH APPS ────────────────────────────────────────────────────────
# These remain publicly accessible
ci_factory(server=app, url_base_pathname='/dash/compound-interest/')
pd_factory(server=app, url_base_pathname='/dash/pension-drawdown/')

# ── RUN SERVER ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
