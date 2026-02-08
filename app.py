import os
import threading
import time
from datetime import datetime
from multiprocessing import Process
from flask import Flask, render_template, request, redirect, url_for, flash # <--- [แก้ไข] เพิ่ม flash ตรงนี้
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor# <--- [เพิ่ม]
from flask_sqlalchemy import SQLAlchemy

# --- ส่วนประกาศตัวแปร Shared Resource & Lock ---
email_counter = 0
counter_lock = threading.Lock()

# [เพิ่ม] สร้าง Thread Pool ไว้ใช้งาน (จำกัดแค่ 5 Thread)
# แปลว่าส่งเมลพร้อมกันได้สูงสุด 5 งาน ที่เหลือต้องต่อคิว
executor = ThreadPoolExecutor(max_workers=5)

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

# --- ส่วนสร้างตาราง (Model) ---
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    version = db.Column(db.Integer, default=1)

with app.app_context():
    db.create_all()

# --- Routes ---

@app.route('/')
def index():
    posts = Post.query.all()
    return render_template('index.html', posts=posts)

@app.route('/add', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        new_post = Post(title=title, content=content)
        db.session.add(new_post)
        db.session.commit()
        
        executor.submit(send_notification_email, title)
        
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/delete/<int:id>')
def delete(id):
    post_to_delete = Post.query.get_or_404(id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST']) 
def update(id):
    post = Post.query.get(id)
    
    if post is None:
        # ถ้าหาไม่เจอ (แสดงว่าโดนลบไปแล้ว) ให้แจ้งเตือนแล้วดีดกลับหน้าแรก
        flash('ไม่สามารถบันทึกได้! โพสต์นี้ถูกลบไปแล้วโดยผู้ใช้อื่น', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            form_version = int(request.form.get('version'))
        except (TypeError, ValueError):
            form_version = post.version

        if form_version != post.version:
            # แทนที่จะดีดกลับ เราจะดึงข้อมูลที่ User เพิ่งพิมพ์เก็บไว้ก่อน
            draft_title = request.form['title']
            draft_content = request.form['content']
            
            # แจ้งเตือน พร้อมส่งข้อมูลทั้ง "ของเก่า" และ "ของใหม่" ไปที่หน้าเว็บ
            flash(f'เกิดข้อผิดพลาด! มีคนแก้ไขตัดหน้า (Version {post.version})', 'conflict')
            
            # Render หน้าเดิม แต่ส่งตัวแปรเพิ่มไปบอกว่า "มี Conflict นะ"
            return render_template('edit.html', 
                                   post=post,               # ข้อมูลล่าสุดใน DB (ของคนอื่น)
                                   draft_title=draft_title, # ข้อมูลที่ User พิมพ์ค้างไว้
                                   draft_content=draft_content,
                                   conflict=True)           # ตัวบอกสถานะ

        post.title = request.form['title']
        post.content = request.form['content']
        post.version = post.version + 1
        
        db.session.commit()
        
        executor.submit(send_notification_email, f"EDITED (v{post.version}): {post.title}")
        
        return redirect(url_for('index'))
        
    return render_template('edit.html', post=post)

# Route สำหรับทดสอบ Parallel Processing
@app.route('/compute/<task_name>')
def compute(task_name):
    # [2. เปลี่ยนจาก Process() เป็น executor.submit()]
    # p = Process(target=heavy_cpu_task, args=(task_name,))
    # p.start()

    cpu_executor.submit(heavy_cpu_task, task_name)

    return f"สั่งงาน '{task_name}' เข้าคิวประมวลผลแล้ว! (Server จะไม่ล่มแม้คนกดรัวๆ)"

# --- Functions (Worker) ---

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