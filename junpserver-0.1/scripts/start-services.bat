@echo off
chcp 65001 >nul
echo ========================================
echo   JumpServer 服务启动脚本
echo ========================================
echo 时间：%date% %time%
echo.

REM 切换到项目目录
cd /d "%~dp0.."

REM 检查 Docker 是否可用
echo [1/3] 检查 Docker 环境...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未安装或未启动
    pause
    exit /b 1
)
echo [完成] Docker 环境正常

REM 检查 .env 文件
echo [2/3] 检查配置文件...
if not exist ".env" (
    echo [警告] .env 文件不存在，请从 .env.example 复制并配置
    pause
    exit /b 1
)
echo [完成] 配置文件存在

REM 启动 Docker Compose 服务
echo [3/3] 启动 Docker 服务...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [错误] 服务启动失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   所有服务已成功启动！
echo ========================================
echo.
echo 服务列表:
docker-compose ps
echo.
echo 日志查看：docker-compose logs -f [服务名]
echo 停止服务：docker-compose down
echo.

REM 等待 3 秒后最小化或退出
timeout /t 3 >nul
