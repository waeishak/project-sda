COMPOSE=docker-compose

.PHONY: help up down restart logs clean shell

help:
	@echo "Usage:"
	@echo "  make up       Start the app (build if needed)"
	@echo "  make down     Stop the app"
	@echo "  make restart  Restart only the Flask app (fast update)"
	@echo "  make logs     View logs (follow mode)"
	@echo "  make clean    Stop and REMOVE DATABASE (Reset everything)"
	@echo "  make shell    Enter the web container shell"

# รันโปรแกรม (เทียบเท่า docker-compose up --build)
up:
	$(COMPOSE) up --build

# ปิดโปรแกรม
down:
	$(COMPOSE) down

# รีสตาร์ทเฉพาะเว็บ (ใช้บ่อยเวลาแก้โค้ด Python)
restart:
	$(COMPOSE) restart web

# ดู Log แบบ real-time
logs:
	$(COMPOSE) logs -f

# ล้างทุกอย่างรวมถึงข้อมูลใน Database (ระวัง!)
clean:
	$(COMPOSE) down -v

# เข้าไปพิมพ์คำสั่งใน container (เผื่อ debug)
shell:
	$(COMPOSE) exec web bash