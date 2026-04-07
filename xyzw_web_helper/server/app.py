import base64
import json
import secrets
import sqlite3
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = BASE_DIR / "users.db"
UPLOAD_ROOT = BASE_DIR / "uploads"


def _default_config():
    return {
        "secret_key": secrets.token_hex(32),
        "host": "0.0.0.0",
        "port": 5000,
        "default_admin": {
            "username": "admin",
            "password": "admin123",
        },
    }


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(_default_config(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


config = load_config()

app = Flask(__name__)
app.config["SECRET_KEY"] = config["secret_key"]
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


INDEX_TMPL = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>TokenURL 服务</title>
  <style>
    body { font-family: sans-serif; max-width: 980px; margin: 2rem auto; }
    .box { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
    input, button { margin: .25rem 0; padding: .4rem .6rem; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #eee; padding: .5rem; text-align: left; }
    code { word-break: break-all; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  </style>
</head>
<body>
  <h1>TokenURL 获取服务</h1>
  {% with msgs = get_flashed_messages() %}
    {% if msgs %}
      <div class="box">
        {% for m in msgs %}<div>{{ m }}</div>{% endfor %}
      </div>
    {% endif %}
  {% endwith %}

  {% if not user %}
    <div class="row">
      <form class="box" method="post" action="{{ url_for('login') }}">
        <h3>登录</h3>
        <input name="username" placeholder="用户名" required><br>
        <input name="password" type="password" placeholder="密码" required><br>
        <button type="submit">登录</button>
      </form>

      <form class="box" method="post" action="{{ url_for('register') }}">
        <h3>注册新账号</h3>
        <input name="username" placeholder="用户名" required><br>
        <input name="password" type="password" placeholder="密码" required><br>
        <button type="submit">注册</button>
      </form>
    </div>
    <p>默认管理员：<code>admin / admin123</code></p>
  {% else %}
    <div class="box">
      <div>当前用户：<b>{{ user['username'] }}</b>{% if user['is_admin'] %}（管理员）{% endif %}</div>
      <div>用户 Token：<code>{{ user['user_token'] }}</code></div>
      <div style="margin-top:.5rem;">
        <a href="{{ url_for('logout') }}">退出登录</a>
      </div>
    </div>

    <form class="box" method="post" action="{{ url_for('upload_bins') }}" enctype="multipart/form-data">
      <h3>上传 .bin 文件（支持多选）</h3>
      <input type="file" name="files" multiple required>
      <button type="submit">上传</button>
    </form>

    <form class="box" method="post" action="{{ url_for('change_password') }}">
      <h3>修改密码</h3>
      <input name="new_password" type="password" placeholder="新密码" required>
      <button type="submit">修改密码</button>
    </form>

    {% if not user['is_admin'] %}
    <form class="box" method="post" action="{{ url_for('delete_account') }}" onsubmit="return confirm('确定永久注销账号吗？')">
      <h3>注销账号（不可恢复）</h3>
      <button type="submit">注销账号</button>
    </form>
    {% endif %}

    <div class="box">
      <h3>我的 bin 文件</h3>
      <table>
        <thead>
          <tr><th>文件名</th><th>Token URL 示例</th><th>操作</th></tr>
        </thead>
        <tbody>
          {% for f in files %}
            <tr>
              <td>{{ f }}</td>
              <td>
                <code>{{ base_url }}/{{ user['user_token'] }}/{{ f }}/{{ sample_b64 }}</code>
              </td>
              <td>
                <form method="post" action="{{ url_for('delete_bin') }}" style="display:inline">
                  <input type="hidden" name="filename" value="{{ f }}">
                  <button type="submit">删除</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% endif %}
</body>
</html>
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_token TEXT UNIQUE NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    db.commit()

    admin = config["default_admin"]
    row = db.execute("SELECT id FROM users WHERE username = ?", (admin["username"],)).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO users(username, password_hash, user_token, is_admin) VALUES(?,?,?,1)",
            (
                admin["username"],
                generate_password_hash(admin["password"]),
                secrets.token_urlsafe(24),
            ),
        )
        db.commit()
    db.close()


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return get_db().execute(
        "SELECT id, username, user_token, is_admin FROM users WHERE id = ?", (uid,)
    ).fetchone()


def user_dir(username: str):
    path = UPLOAD_ROOT / username
    path.mkdir(parents=True, exist_ok=True)
    return path


@app.route("/")
def index():
    user = current_user()
    files = []
    if user:
        files = sorted(
            [p.name for p in user_dir(user["username"]).glob("*.bin") if p.is_file()]
        )
    return render_template_string(
        INDEX_TMPL,
        user=user,
        files=files,
        base_url=request.host_url.rstrip("/"),
        sample_b64=base64.urlsafe_b64encode(b"demo").decode(),
    )


@app.post("/register")
def register():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if not username or not password:
        flash("用户名和密码不能为空")
        return redirect(url_for("index"))

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users(username, password_hash, user_token, is_admin) VALUES(?,?,?,0)",
            (username, generate_password_hash(password), secrets.token_urlsafe(24)),
        )
        db.commit()
        flash("注册成功，请登录")
    except sqlite3.IntegrityError:
        flash("用户名已存在")
    return redirect(url_for("index"))


@app.post("/login")
def login():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    row = get_db().execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        session["uid"] = row["id"]
        flash("登录成功")
    else:
        flash("用户名或密码错误")
    return redirect(url_for("index"))


@app.get("/logout")
def logout():
    session.clear()
    flash("已退出登录")
    return redirect(url_for("index"))


@app.post("/upload")
def upload_bins():
    user = current_user()
    if not user:
        return redirect(url_for("index"))

    files = request.files.getlist("files")
    saved = 0
    target_dir = user_dir(user["username"])
    for f in files:
        if not f.filename:
            continue
        filename = secure_filename(f.filename)
        if not filename.endswith(".bin"):
            continue
        f.save(target_dir / filename)
        saved += 1

    flash(f"上传完成：{saved} 个文件")
    return redirect(url_for("index"))


@app.post("/delete-bin")
def delete_bin():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    filename = secure_filename(request.form.get("filename") or "")
    path = user_dir(user["username"]) / filename
    if path.exists() and path.is_file():
        path.unlink()
        flash("删除成功")
    else:
        flash("文件不存在")
    return redirect(url_for("index"))


@app.post("/change-password")
def change_password():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    new_password = request.form.get("new_password") or ""
    if len(new_password) < 4:
        flash("密码长度至少 4 位")
        return redirect(url_for("index"))

    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user["id"]),
    )
    db.commit()
    flash("密码修改成功")
    return redirect(url_for("index"))


@app.post("/delete-account")
def delete_account():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    if user["is_admin"]:
        flash("管理员账号不可注销")
        return redirect(url_for("index"))

    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    db.commit()

    root = user_dir(user["username"])
    for p in root.glob("*"):
        if p.is_file():
            p.unlink()
    root.rmdir()

    session.clear()
    flash("账号已注销")
    return redirect(url_for("index"))


@app.get("/<user_token>/<path:filename>/<encoded>")
def get_token_url(user_token: str, filename: str, encoded: str):
    user = get_db().execute(
        "SELECT username FROM users WHERE user_token = ?", (user_token,)
    ).fetchone()
    if not user:
        return jsonify({"error": "invalid user token"}), 404

    safe_name = secure_filename(filename)
    path = user_dir(user["username"]) / safe_name
    if not path.exists():
        return jsonify({"error": "file not found"}), 404

    try:
        decoded = base64.urlsafe_b64decode(encoded + "==").decode("utf-8", errors="ignore")
    except Exception:
        decoded = ""

    response = send_from_directory(path.parent, safe_name, as_attachment=False)
    response.headers["X-Token-Payload"] = decoded
    return response


if __name__ == "__main__":
    init_db()
    app.run(host=config.get("host", "0.0.0.0"), port=int(config.get("port", 5000)))
