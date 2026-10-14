MEMORYHUB - LAM TU DAU

CHAY TREN MAY:
1. Giai nen va mo thu muc nay bang VS Code.
2. Mo Terminal trong thu muc du an:
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
3. Dat mat khau admin (PowerShell):
   $env:ADMIN_PASSWORD = "DatMatKhauManhCuaBan"
   $env:SESSION_SECRET = "ThayBangChuoiBiMatNgauNhienDaiHon32KyTu"
4. Chay:
   .\.venv\Scripts\python.exe -m uvicorn main:app --reload
5. Trang xem: http://127.0.0.1:8000
   Admin: http://127.0.0.1:8000/admin/login

DUA LEN INTERNET:
- Du an co render.yaml de deploy len Render tu GitHub.
- Sau khi day source len GitHub, tao Web Service tren Render va dat bien moi truong ADMIN_PASSWORD, SESSION_SECRET (chuoi ngau nhien dai), COOKIE_HTTPS_ONLY=true.
- Build: pip install -r requirements.txt
- Start: uvicorn main:app --host 0.0.0.0 --port $PORT
- Render free co the ngu khi khong dung va file SQLite/video tren o dia local co the mat khi instance duoc thay the. Ban nay la ban khoi dau de hoc/chay thu; de luu video lau dai tren Internet, can them kho luu tru ben ngoai va database ben ngoai (vi du object storage + PostgreSQL). Khong commit mat khau vao GitHub.
- Chi tai len video ban co quyen chia se va co su dong y cua nguoi xuat hien trong video.
