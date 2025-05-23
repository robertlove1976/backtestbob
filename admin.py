# admin.py

import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, current_app, send_from_directory
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, BlogPost, AdminUser

admin_bp = Blueprint(
    'admin',
    __name__,
    url_prefix='/admin',
    template_folder='templates'
)

# This LoginManager is passed back to backtestbob_server.py and initialized there:
login_manager = LoginManager()
login_manager.login_view = 'admin.login'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

# — NO before_app_first_request or before_app_request here —
# The default‐admin seeding is now in backtestbob_server.py

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))


@admin_bp.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = AdminUser.query.filter_by(
            username=request.form['username']
        ).first()
        if user and check_password_hash(
            user.password_hash, request.form['password']
        ):
            login_user(user)
            return redirect(url_for('admin.list_posts'))
        flash('Invalid username or password', 'danger')
    return render_template('admin_login.html')


@admin_bp.route('/logout/')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@admin_bp.route('/')
@login_required
def list_posts():
    posts = BlogPost.query.order_by(BlogPost.published_at.desc()).all()
    return render_template('admin_list.html', posts=posts)


@admin_bp.route('/edit/<int:post_id>/', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id) if post_id else BlogPost()

    if request.method == 'POST':
        # Text fields
        post.title = request.form['title']
        post.slug  = request.form['slug']
        post.body  = request.form['body']

        # Parse & validate published_at date
        pub_str = request.form.get('published_at')
        if pub_str:
            try:
                post.published_at = datetime.strptime(pub_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid date format for “Published At” (use YYYY-MM-DD)', 'danger')

        # Handle image upload
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))
            post.image = f'uploads/{filename}'

        # Save to DB
        db.session.add(post)
        db.session.commit()
        flash('Post saved successfully.', 'success')
        return redirect(url_for('blog.show_post', slug=post.slug))

    return render_template('admin_edit.html', post=post)


# Optional: serve uploaded images
@admin_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(
        os.path.join(current_app.static_folder, 'uploads'),
        filename
    )
