import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- ส่วนตั้งค่า Database ---
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- ส่วนสร้างตาราง (Model) ---
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

# --- Routes ---

@app.route('/')
def index():
    posts = Post.query.all()
    return render_template('index.html', posts=posts)

# แก้ไขจุดที่ 1: ใช้ route /add และเรียกไฟล์ add.html
@app.route('/add', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        new_post = Post(title=title, content=content)
        db.session.add(new_post)
        db.session.commit()
        
        return redirect(url_for('index'))
    return render_template('add.html')  # แก้เป็น add.html ตามโครงสร้างจริง

# ลบโพสต์
@app.route('/delete/<int:id>')
def delete(id):
    post_to_delete = Post.query.get_or_404(id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('index'))

# แก้ไขจุดที่ 2: เรียกไฟล์ edit.html (เผื่อคุณใช้ฟีเจอร์นี้ต่อ)
@app.route('/edit/<int:id>', methods=['GET', 'POST']) 
def update(id):
    post = Post.query.get_or_404(id)
    
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        db.session.commit()
        return redirect(url_for('index'))
        
    return render_template('edit.html', post=post)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)