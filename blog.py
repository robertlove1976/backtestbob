from flask import Blueprint, render_template, request, current_app, url_for, redirect
from models import db, BlogPost, Comment

blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

@blog_bp.route('/')
def list_posts():
    q = request.args.get('q','')
    posts = BlogPost.query.filter(
        BlogPost.title.ilike(f'%{q}%') | BlogPost.body.ilike(f'%{q}%')
    ).order_by(BlogPost.published_at.desc()).all()
    return render_template('blog_list.html', posts=posts, q=q)

@blog_bp.route('/<slug>/', methods=['GET','POST'])
def show_post(slug):
    post = BlogPost.query.filter_by(slug=slug).first_or_404()
    if request.method=='POST':
        author = request.form['author']
        body = request.form['body']
        comment = Comment(post=post, author=author, body=body)
        db.session.add(comment); db.session.commit()
        return redirect(url_for('blog.show_post', slug=slug))
    return render_template('blog_post.html', post=post)