# 后端启动指南

> 当前后端处于开发阶段，使用 `uvicorn --reload` 热重载启动。
> 依赖服务（PostgreSQL / Redis / MinIO）建议通过 Docker 运行。

---

## 一、环境要求

- Python ≥ 3.10
- Docker / Docker Desktop
- 数据库需要 **pgvector** 扩展（迁移会执行 `CREATE EXTENSION vector`），所以请使用 `pgvector/pgvector` 镜像，而不是官方 `postgres` 镜像

---

## 二、依赖服务（Docker）

```bash
# 1. PostgreSQL
docker run -d --name ppt-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=ppt_system \
  -p 5432:5432 \
  -v ppt-postgres-data:/var/lib/postgresql/data \
  pgvector/pgvector:pg16

# 2. Redis
docker run -d --name ppt-redis \
  -p 6379:6379 \
  -v ppt-redis-data:/data \
  redis:7-alpine \
  redis-server --requirepass 123456 --appendonly yes

# 3. MinIO
docker run -d --name ppt-minio \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  -p 9000:9000 -p 9001:9001 \
  -v ppt-minio-data:/data \
  minio/minio server /data --console-address ":9001"
```

### MinIO Bucket 初始化

首次启动后，需要创建 `.env` 中配置的 bucket `ppt-files`：

1. 浏览器打开 <http://localhost:9001>
2. 用 `minioadmin / minioadmin` 登录
3. **Buckets → Create Bucket**，名字填 `ppt-files`

或使用 `mc` 命令行：

```bash
docker run --rm --network host minio/mc \
  alias set local http://localhost:9000 minioadmin minioadmin && \
docker run --rm --network host minio/mc mb local/ppt-files
```

---

## 三、Python 环境

```bash
cd backend

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

# 安装依赖
pip install -r requirements.txt
```

---

## 四、配置 `.env`

`backend/.env` 已提供开发默认值，开箱即用。如需修改，请保证以下几项与 Docker 容器一致：

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ppt_system
REDIS_URL=redis://:123456@localhost:6379/0
OSS_ENDPOINT=http://localhost:9000
OSS_ACCESS_KEY=minioadmin
OSS_SECRET_KEY=minioadmin
OSS_BUCKET_NAME=ppt-files
```

---

## 五、数据库迁移

首次启动前执行 Alembic 迁移，建表并启用 pgvector：

```bash
cd backend
alembic upgrade head
```

---

## 六、启动后端

开发模式（热重载）：

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动成功后：

- API 根：<http://localhost:8000>
- Swagger 文档：<http://localhost:8000/docs>
- ReDoc 文档：<http://localhost:8000/redoc>

---
