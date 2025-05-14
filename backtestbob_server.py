# backtestbob_server.py
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from models import db
from blog import blog_bp
from admin import admin_bp, login_manager as admin_login_manager
from compound_interest_calculator import create_dash_app as ci_factory
from pension_drawdown_calculator import create_dash_app as pd_factory

# ── ENV & CONFIG ─────────────────────────────────────────────────────────
load_dotenv()
DB_FILE = os.getenv('DB_FILE', 'stocks.db')

# Flask application setup
app = Flask(__name__)
# current_year() helper for footer
app.jinja_env.globals['current_year'] = lambda: datetime.utcnow().year
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'change_me'),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_FILE}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
# file uploads
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

# ── EXTENSIONS INITIALIZATION ─────────────────────────────────────────────
# SQLAlchemy + migrations
db.init_app(app)
Migrate(app, db)
# Admin login
admin_login_manager.init_app(app)
admin_login_manager.login_view = 'admin.login'

# ── REGISTER BLUEPRINTS ───────────────────────────────────────────────────
app.register_blueprint(blog_bp)
app.register_blueprint(admin_bp)

# ── CORE ROUTES ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculators')
def calculators():
    return render_template('calculators.html')

# ── DATABASE SETUP ─────────────────────────────────────────────────────────
# Create all tables (for development; production should use migrations)
with app.app_context():
    db.create_all()

# ── MOUNT DASH APPS ────────────────────────────────────────────────────────
ci_factory(server=app, url_base_pathname='/dash/compound-interest/')
pd_factory(server=app, url_base_pathname='/dash/pension-drawdown/')

# ── RUN SERVER ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)