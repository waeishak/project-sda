# ใช้ Python เวอร์ชันเบาๆ (Slim)
FROM python:3.9-slim

# ตั้งค่าโฟลเดอร์ทำงานใน Container
WORKDIR /app

# Copy ไฟล์ requirements และติดตั้ง Library ก่อน (เพื่อใช้ cache ของ Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy โค้ดทั้งหมดในโปรเจกต์เข้าไป
COPY . .

# เปิด Port 5000
EXPOSE 5000

# คำสั่งรันแอป
CMD ["python", "app.py"]