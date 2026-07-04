@echo off
chcp 65001 >nul
echo ========================================
echo   JumpServer 服务停止脚本
echo ========================================
echo 时间：%date% %time%
echo.

REM 切换到项目目录
cd /d "%~dp0.."

REM 停止 Docker Compose 服务
echo 停止所有 Docker 服务...
docker-compose down

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
