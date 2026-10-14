import os
import sqlite3
import secrets
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware


# =========================
# CẤU HÌNH
# =========================

ROOT = Path(__file__).resolve().parent

UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)

DB = ROOT / "memoryhub.db"

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "local-only-change-this"
)

app = FastAPI(title="MemoryHub")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=os.getenv(
        "COOKIE_HTTPS_ONLY", "false"
    ).lower() == "true"
)

app.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "static")),
    name="static"
)

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOADS)),
    name="uploads"
)

templates = Jinja2Templates(
    directory=str(ROOT / "templates")
)


# =========================
# CƠ SỞ DỮ LIỆU
# =========================

def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


with db() as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            url TEXT NOT NULL,
            thumbnail TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)


# =========================
# HÀM HỖ TRỢ
# =========================

def is_admin(request: Request):
    return request.session.get("admin") is True


def get_videos(q: str = ""):
    with db() as connection:
        if q.strip():
            keyword = "%" + q.strip() + "%"

            data = connection.execute(
                """
                SELECT id, title, description, url,
                       thumbnail, created_at
                FROM videos
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY id DESC
                """,
                (keyword, keyword)
            ).fetchall()

        else:
            data = connection.execute(
                """
                SELECT id, title, description, url,
                       thumbnail, created_at
                FROM videos
                ORDER BY id DESC
                """
            ).fetchall()

    return [
        {
            "id": video["id"],
            "title": video["title"],
            "description": video["description"],
            "url": video["url"],
            "thumbnail": video["thumbnail"],
            "uploaded_at": video["created_at"]
        }
        for video in data
    ]


def render_template(
    request: Request,
    name: str,
    context: dict | None = None,
    status_code: int = 200
):
    if context is None:
        context = {}

    return templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code
    )


# =========================
# TRANG CHỦ
# =========================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render_template(
        request,
        "index.html"
    )


# =========================
# API LẤY DANH SÁCH VIDEO
# =========================

@app.get("/api/videos")
def api_videos(q: str = ""):
    return get_videos(q)


# =========================
# TRANG ĐĂNG NHẬP ADMIN
# =========================

@app.get("/login", response_class=HTMLResponse)
@app.get("/admin/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_admin(request):
        return RedirectResponse(
            "/admin",
            status_code=303
        )

    return render_template(
        request,
        "login.html",
        {"error": None}
    )


@app.post("/admin/login", response_class=HTMLResponse)
def login(
    request: Request,
    password: str = Form(...)
):
    if not ADMIN_PASSWORD:
        return render_template(
            request,
            "login.html",
            {
                "error": (
                    "Chưa đặt ADMIN_PASSWORD. "
                    "Hãy cấu hình mật khẩu admin trước."
                )
            },
            status_code=500
        )

    if not secrets.compare_digest(
        password,
        ADMIN_PASSWORD
    ):
        return render_template(
            request,
            "login.html",
            {"error": "Mật khẩu không đúng."},
            status_code=401
        )

    request.session["admin"] = True

    return RedirectResponse(
        "/admin",
        status_code=303
    )


# =========================
# TRANG QUẢN LÝ VIDEO
# =========================

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    if not is_admin(request):
        return RedirectResponse(
            "/login",
            status_code=303
        )

    return render_template(
        request,
        "admin.html",
        {"videos": get_videos()}
    )


# =========================
# ĐĂNG XUẤT ADMIN
# =========================

@app.post("/admin/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        "/",
        status_code=303
    )


# =========================
# TẢI VIDEO LÊN
# =========================

@app.post("/admin/upload")
async def upload(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    video: UploadFile = File(...),
    thumbnail: UploadFile | None = File(None)
):
    if not is_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền quản trị."
        )

    title = title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Cần nhập tên video."
        )

    video_ext = Path(
        video.filename or ""
    ).suffix.lower()

    allowed_video_exts = {
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
        ".ogv"
    }

    if video_ext not in allowed_video_exts:
        raise HTTPException(
            status_code=400,
            detail=(
                "Chỉ nhận MP4, WebM, MOV, "
                "M4V hoặc OGV."
            )
        )

    max_bytes = (
        int(os.getenv("MAX_UPLOAD_MB", "500"))
        * 1024
        * 1024
    )

    data = await video.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail="Video quá dung lượng cho phép."
        )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="File video rỗng."
        )

    video_name = secrets.token_hex(16) + video_ext
    video_path = UPLOADS / video_name
    video_path.write_bytes(data)

    video_url = "/uploads/" + video_name
    thumbnail_url = ""

    # Xử lý ảnh bìa nếu có
    if thumbnail and thumbnail.filename:
        thumbnail_ext = Path(
            thumbnail.filename
        ).suffix.lower()

        allowed_image_exts = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        }

        if thumbnail_ext not in allowed_image_exts:
            video_path.unlink(missing_ok=True)

            raise HTTPException(
                status_code=400,
                detail="Ảnh bìa phải là JPG, PNG hoặc WebP."
            )

        thumbnail_data = await thumbnail.read(
            8 * 1024 * 1024 + 1
        )

        if len(thumbnail_data) > 8 * 1024 * 1024:
            video_path.unlink(missing_ok=True)

            raise HTTPException(
                status_code=413,
                detail="Ảnh bìa tối đa 8 MB."
            )

        thumbnail_name = (
            secrets.token_hex(16) + thumbnail_ext
        )

        thumbnail_path = UPLOADS / thumbnail_name
        thumbnail_path.write_bytes(thumbnail_data)

        thumbnail_url = "/uploads/" + thumbnail_name

    with db() as connection:
        connection.execute(
            """
            INSERT INTO videos (
                title,
                description,
                url,
                thumbnail,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                description.strip(),
                video_url,
                thumbnail_url,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M"
                )
            )
        )

    return RedirectResponse(
        "/admin?uploaded=1",
        status_code=303
    )


# =========================
# XÓA VIDEO
# =========================

@app.post("/admin/delete/{vid}")
def delete_video(
    request: Request,
    vid: int
):
    if not is_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền quản trị."
        )

    with db() as connection:
        video = connection.execute(
            """
            SELECT url, thumbnail
            FROM videos
            WHERE id = ?
            """,
            (vid,)
        ).fetchone()

        if not video:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy video."
            )

        # Xóa file video và ảnh bìa
        for value in (
            video["url"],
            video["thumbnail"]
        ):
            if value and value.startswith("/uploads/"):
                file_path = UPLOADS / Path(value).name

                if file_path.exists():
                    file_path.unlink()

        connection.execute(
            "DELETE FROM videos WHERE id = ?",
            (vid,)
        )

    return RedirectResponse(
        "/admin?deleted=1",
        status_code=303
    )


# =========================
# KIỂM TRA SERVER
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}