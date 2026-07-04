#!/bin/bash
#
# OpsPaw 生产环境部署脚本
# 用途：一键部署 OpsPaw 到产线环境
#
# 使用方式：
#   ./scripts/deploy-prod.sh
#
# 前置条件：
#   - Docker 20.x+ 已安装
#   - docker-compose 已安装
#   - .env 文件已配置（包含 JumpServer 连接信息）
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 步骤 1: 环境检查
log_info "=== 步骤 1: 环境检查 ==="

# 检查 docker 是否安装
if ! command -v docker &> /dev/null; then
    log_error "Docker 未安装，请先安装 Docker 20.x+"
    exit 1
fi
log_info "Docker 版本：$(docker --version)"

# 检查 docker-compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose 未安装，请先安装 docker-compose"
    exit 1
fi
log_info "docker-compose 版本：$(docker-compose --version)"

# 检查 .env 文件是否存在
if [ ! -f .env ]; then
    log_error ".env 文件不存在，请复制 .env.example 并配置"
    log_warn "参考命令：cp .env.example .env"
    exit 1
fi
log_info ".env 文件存在"

# 步骤 2: 依赖准备
log_info "=== 步骤 2: 依赖准备 ==="

# 拉取最新代码
log_info "拉取最新代码..."
git pull origin main || log_warn "git pull 失败，请检查网络连接"

# 构建镜像
log_info "构建 Docker 镜像（首次构建可能需要几分钟）..."
docker-compose build --no-cache

# 步骤 3: 执行数据库迁移
log_info "=== 步骤 3: 执行数据库迁移 ==="
docker-compose up db-migrate

# 步骤 4: 启动服务
log_info "=== 步骤 4: 启动服务 ==="
docker-compose up -d nginx api orchestrator-worker sync-worker callback-worker scheduler

# 步骤 5: 健康检查
log_info "=== 步骤 5: 健康检查 ==="
log_info "等待服务启动（最多等待 60 秒）..."

HEALTH_CHECK_MAX_RETRIES=12
HEALTH_CHECK_INTERVAL=5
HEALTH_CHECK_COUNT=0

while [ $HEALTH_CHECK_COUNT -lt $HEALTH_CHECK_MAX_RETRIES ]; do
    sleep $HEALTH_CHECK_INTERVAL
    HEALTH_CHECK_COUNT=$((HEALTH_CHECK_COUNT + 1))

    # 尝试访问健康检查端点
    if curl -s -f http://localhost/health > /dev/null 2>&1; then
        log_info "健康检查通过！"
        break
    fi

    if [ $HEALTH_CHECK_COUNT -eq $HEALTH_CHECK_MAX_RETRIES ]; then
        log_error "健康检查失败：服务未能在预期时间内启动"
        log_warn "请查看日志：docker-compose logs api"
        exit 1
    fi

    log_info "等待服务启动... ($HEALTH_CHECK_COUNT/$HEALTH_CHECK_MAX_RETRIES)"
done

# 输出服务状态
log_info "=== 服务状态 ==="
docker-compose ps

# 验证 API 响应
log_info "=== 验证 API 响应 ==="
if curl -s -f http://localhost/api/v1/dashboard/overview > /dev/null 2>&1; then
    log_info "API 响应正常"
else
    log_warn "API 响应异常，请查看日志：docker-compose logs api"
fi

log_info "=== 部署完成 ==="
log_info "访问地址：http://localhost/"
log_info "API 文档：http://localhost/docs"
log_info ""
log_warn "回滚命令参考："
log_warn "  docker-compose down"
log_warn "  git revert HEAD"
log_warn "  docker-compose up -d"
