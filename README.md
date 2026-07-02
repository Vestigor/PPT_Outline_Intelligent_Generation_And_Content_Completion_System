# PPT 大纲智能生成与内容补全系统

面向 PPT 内容创作的智能系统，支持引导式生成、报告式生成、对话修改、知识库检索增强、联网搜索、模型配置及后台管理。

## 项目组成

| 组件 | 技术栈 | 本地地址 |
| --- | --- | --- |
| 用户端 | React + TypeScript + Vite | <http://localhost:3001> |
| 管理端 | React + TypeScript + Vite | <http://localhost:3000/admin/> |
| 后端 API | FastAPI + SQLAlchemy | <http://localhost:8000/api/docs> |
| PostgreSQL | PostgreSQL 16 + pgvector | `localhost:5432` |
| Redis | Redis 7 | `localhost:6379` |
| 对象存储 | MinIO | <http://localhost:9001> |

## 本地开发

### 1. 环境要求

- Python 3.11
- Node.js 20 或更高版本、npm
- Docker 与 Docker Compose

### 2. 启动基础设施

在项目根目录执行：

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
```

该配置会启动 PostgreSQL、Redis 和 MinIO，并自动创建 `ppt-files` bucket。开发数据存放在独立的 Docker volumes 中，不会与生产部署混用。

### 3. 启动后端

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

迁移会创建 pgvector 扩展及初始超级管理员：

- 用户名：`admin`
- 初始密码：`PPTAdmin@2026`

首次登录后请立即修改密码。后端健康检查地址为 <http://localhost:8000/health>。

### 4. 启动用户端

另开终端：

```bash
cd user_frontend
npm ci
npm run dev
```

访问 <http://localhost:3001>。

### 5. 启动管理端

另开终端：

```bash
cd admin_frontend
npm ci
npm run dev
```

访问 <http://localhost:3000/admin/>。

## 配置文件

- `backend/.env.dev`：可提交的本地开发默认配置，使用 `localhost` 连接开发基础设施。
- `backend/.env`：个人私有配置，不会被 Git 跟踪；存在时会覆盖 `.env.dev` 中的同名配置。
- `backend/.env.example`：生产环境模板，使用 Docker Compose 服务名连接容器。

需要测试邮件验证码、向量化或其他外部服务时，在 `backend/.env` 中填写相应密钥。例如：

```dotenv
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_smtp_app_password
DASHSCOPE_API_KEY=your_dashscope_api_key
```

不要把真实密码、API Key、SMTP 授权码或生产环境 `SECRET_KEY` 写入 `.env.dev` 或提交到 Git。

## 常用命令

```bash
# 后端测试
cd backend
pytest

# 前端检查与构建（分别在两个前端目录执行）
npm run lint
npm run build

# 停止本地基础设施（保留数据）
docker compose -f docker-compose.dev.yml down

# 停止并清空本地开发数据（不可恢复）
docker compose -f docker-compose.dev.yml down -v
```

## 文档

- [用户手册](<docs/User Manual.pdf>)
- [生产部署说明](DEPLOYMENT.md)
- [技术验证报告](docs/Technical_Validation_Report.md)
- [Likert 人工评价标准](docs/Likert_Human_Evaluation_Criteria.md)

生产环境请使用根目录的 `docker-compose.yml` 和 `backend/.env`，不要直接复用开发配置。
