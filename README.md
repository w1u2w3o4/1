# XYZW Web Helper

## 本地预览（Cloudflare Pages）
为了在本地模拟 Cloudflare Pages 环境（包括 `worker.js` 的代理功能），请使用 Wrangler：

1. 安装 Wrangler（推荐作为项目依赖，避免全局环境差异）：
   ```bash
   cd xyzw_web_helper
   pnpm add -D wrangler
   ```

2. 安装前端依赖：
   ```bash
   cd xyzw_web_helper
   pnpm install
   ```

3. 构建项目并注入 Worker：
   ```bash
   pnpm run build:pages
   ```

4. 启动 Cloudflare Pages 本地预览：
   ```bash
   pnpm run preview:pages
   ```

5. 访问地址：
   - http://localhost:8787

### 说明
- `pnpm run preview` 仅提供静态文件预览，无法执行 `worker.js` 中的代理逻辑。
- `pnpm run preview:pages` 会先构建，再通过 `wrangler pages dev dist` 启动全功能预览（含代理逻辑）。
- 如果你使用 `npm install` 遇到 `Unsupported URL Type "workspace:"`，请改用 `pnpm install`（本项目使用 pnpm workspace）。

---


## 一键启动前后端（开发）
如果你希望同时运行前端和 Python TokenURL 服务，可使用：

```bash
cd xyzw_web_helper
pnpm run dev:all
```

默认地址：
- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:5000`

也可以分别启动：

```bash
cd xyzw_web_helper
pnpm run dev:frontend
# 或
pnpm run dev:backend
```

---

## 部署 TokenURL 获取服务（Python）
本项目提供了一个基于 Python Flask 的配套后端服务，用于管理游戏 bin 文件并提供 Token 获取接口。

主要功能：
- 多用户管理：支持用户注册、登录、注销，每个用户拥有独立的文件存储空间。
- Web 管理界面：可视化管理 bin 文件，支持批量上传、删除。
- 安全认证：内置登录认证机制，保护接口安全。
- 专属 Token：为每个用户生成唯一的 Token，用于构建安全访问链接。

### 1. 环境准备
确保服务器安装了 Python 3.x，并安装依赖：

```bash
cd xyzw_web_helper/server
pip install -r requirements.txt
```

### 2. 配置
服务启动时会自动检查 `server/config.json`，如果不存在则创建默认配置（包含默认管理员账号）。

> 注意：默认管理员账号为 `admin`，密码为 `admin123`。建议首次登录后修改密码或创建新账号。

### 3. 启动服务
```bash
cd xyzw_web_helper/server
python app.py
```

服务默认启动在 `0.0.0.0:5000`。

### 4. 使用方式
- 注册/登录：访问 `http://<你的服务器IP>:5000`。
- 默认管理员：`admin / admin123`
- 普通用户：点击“注册新账号”创建自己的账号。
- 上传 bin 文件：登录后，点击“上传”按钮，选择一个或多个 `.bin` 文件进行上传。文件将存储在用户专属目录下。
- 获取 Token URL：上传成功后，列表中会显示每个文件的 Token URL。

URL 格式示例（包含用户专属 Token）：

```text
http://<你的服务器IP>:5000/<UserToken>/<bin文件名>/<base64编码>
```

账号管理：
- 修改密码：点击“修改密码”按钮，输入新密码。
- 注销账号：普通用户可注销并永久删除账号及数据；管理员账号不可注销。
