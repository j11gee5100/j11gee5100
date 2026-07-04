# OpsPaw 推理环境交付平台容器运行

## 运行形态

- MySQL 8.4：业务数据库。
- Redis 7：缓存/后台任务依赖。
- API：uWSGI 启动，8 worker 进程，监听容器内 8000。
- Nginx：服务前端静态文件，并反向代理 `/api`、`/mcp`、`/healthz` 到 API。

## 启动

```bash
cp .env.example .env
# 修改 .env 中 MYSQL_PASSWORD / MYSQL_ROOT_PASSWORD / AUTH_TOKEN_SECRET
docker compose up -d --build
```

访问：

- 前端：http://127.0.0.1:18081/
- 后端：http://127.0.0.1:18080/healthz
- MCP：http://127.0.0.1:18080/mcp

## 关键配置

```env
DATABASE_URL=mysql+pymysql://opspaw:opspaw@mysql:3306/opspaw?charset=utf8mb4
DELIVERY_BUNDLE_ARTIFACT_ROOT=/data/delivery-bundles
MCP_ALLOWED_PACKAGE_ROOTS=/data/env-packages,/mnt/env-packages,/nas/inference-packages
```

## uWSGI

配置文件：`docker/api/uwsgi.ini`。

核心参数：

```ini
processes = 8
http-socket = 0.0.0.0:8000
module = app.api.wsgi:application
```
