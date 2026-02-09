import os
import threading
import time
from datetime import datetime
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Import Flask & Database
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

# Import Login Management
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- ส่วนประกาศตัวแปร Shared Resource & Lock ---
email_counter = 0
counter_lock = threading.Lock()

# Thread Pool สำหรับงาน I/O (ส่งเมล)
executor = ThreadPoolExecutor(max_workers=5)

# Process Pool สำหรับงาน CPU (คำนวณหนักๆ)
cpu_executor = ProcessPoolExecutor(max_workers=os.cpu_count())

app = Flask(__name__)

# --- ส่วนตั้งค่า Database ---
db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'my_super_secret_key_123'

db = SQLAlchemy(app)

# --- ตั้งค่า Login Manager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ส่วนสร้างตาราง (Models) ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    # เชื่อมกับ PostUpdate เพื่อดูว่า User นี้เคยไปอัปเดตโพสต์ไหนบ้าง
    updates = db.relationship('PostUpdate', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    version = db.Column(db.Integer, default=1)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref=db.backref('posts', lazy=True))
    
    # --- [จุดที่แก้] ใส่ cascade เพื่อให้ลบลูกเมื่อลบแม่ ---
    updates = db.relationship('PostUpdate', backref='post', lazy=True, order_by="PostUpdate.updated_at", cascade="all, delete-orphan")

class PostUpdate(db.Model):
    __tablename__ = 'post_updates'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False) # ข้อความที่เพิ่มเข้ามา
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # เชื่อมกับ Post หลัก
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    
    # เชื่อมกับ User คนที่มาแก้ไข (อาจไม่ใช่เจ้าของโพสต์ก็ได้)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

# --- Routes (Login/Register) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('ชื่อผู้ใช้นี้ถูกใช้ไปแล้ว', 'error')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ! กรุณาล็อกอิน', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('ยินดีต้อนรับกลับครับ!', 'success')
            return redirect(url_for('index'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ออกจากระบบเรียบร้อยแล้ว', 'success')
    return redirect(url_for('login'))

# --- Routes (Main Logic) ---

@app.route('/')
def index():
    posts = Post.query.all()
    return render_template('index.html', posts=posts)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        # บันทึกคนสร้าง (author) เป็น current_user
        new_post = Post(title=title, content=content, author=current_user)
        db.session.add(new_post)
        db.session.commit()
        
        executor.submit(send_notification_email, title)
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    post_to_delete = Post.query.get_or_404(id)
    
    # [Security Check] อนุญาตเฉพาะเจ้าของโพสต์เท่านั้นถึงลบได้
    if post_to_delete.author != current_user:
        flash('คุณไม่มีสิทธิ์ลบโพสต์นี้!', 'error')
        return redirect(url_for('index'))

    db.session.delete(post_to_delete)
    # หมายเหตุ: เมื่อลบ Post, ตัว PostUpdate ที่ผูกอยู่จะถูกลบไปด้วย (ตาม Default behavior ของ DB)
    # หรือถ้าอยากให้ชัวร์อาจตั้ง cascade ใน Model เพิ่มเติมได้ แต่เบื้องต้นแค่นี้พอครับ
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST']) 
@login_required
def update(id):
    post = Post.query.get(id)
    
    if post is None:
        flash('ไม่สามารถบันทึกได้! โพสต์นี้ถูกลบไปแล้วโดยผู้ใช้อื่น', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            form_version = int(request.form.get('version'))
        except (TypeError, ValueError):
            form_version = post.version

        # --- Optimistic Locking Check ---
        if form_version != post.version:
            draft_content = request.form['content']
            flash(f'เกิดข้อผิดพลาด! มีคนอื่นอัปเดตโพสต์นี้ตัดหน้าคุณไปแล้ว (Version {post.version})', 'conflict')
            return render_template('edit.html', post=post, draft_content=draft_content, conflict=True)

        # --- Save Update Block ---
        new_content = request.form['content']
        
        # 1. สร้างประวัติเก็บไว้ในตาราง PostUpdate (เก็บว่าใครแก้ และแก้อะไร)
        new_update = PostUpdate(content=new_content, user=current_user, post=post)
        db.session.add(new_update)
        
        # 2. [แก้ไขตรงนี้] อัปเดตเนื้อหาหลักของโพสต์ให้เป็นของใหม่ล่าสุดด้วย
        post.content = new_content 
        
        # 3. อัปเดต Version
        post.version += 1
        
        db.session.commit()
        
        executor.submit(send_notification_email, f"UPDATED (v{post.version}): {post.title} by {current_user.username}")
        
        return redirect(url_for('index'))
        
    return render_template('edit.html', post=post)

# --- Parallel Processing Task ---
@app.route('/compute/<task_name>')
def compute(task_name):
    cpu_executor.submit(heavy_cpu_task, task_name)
    return f"สั่งงาน '{task_name}' เข้าคิวประมวลผลแล้ว!"

# --- Workers ---

def send_notification_email(post_title):
    global email_counter
    print(f"--- [Thread Start] กำลังเริ่มส่งอีเมล: {post_title} ---")
    time.sleep(5)
    with counter_lock:
        current_val = email_counter
        new_val = current_val + 1
        email_counter = new_val
        print(f"   [LOCKED] Updated Counter: {current_val} -> {new_val}")
    print(f"--- [Thread Finish] เสร็จสิ้น ---")

def heavy_cpu_task(task_name):
    pid = os.getpid()
    print(f"🔥🔥 [Parallel Start] Process ID: {pid} กำลังคำนวณงาน: {task_name}")
    result = 0
    for i in range(50_000_000): 
        result += i
    print(f"🔥🔥 [Parallel Finish] Process ID: {pid} คำนวณเสร็จแล้ว! ผลลัพธ์: {result}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)