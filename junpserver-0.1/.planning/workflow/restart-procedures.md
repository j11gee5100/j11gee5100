# 开发环境重启流程

**目的:** 标准化代码同步和服务重启流程，避免每次都需要手动提示

---

## 流程

### 方法1: 本地开发环境（当前使用）

```bash
# 1. 确认前端目录
cd F:/jingying/junpserver/junpserver/frontend

# 2. 重启 Vite 开发服务器（端口3000）
npm run dev -- --port 3000
```

**验证服务状态:**
```bash
curl -s http://localhost:3000 | head -1
# 应返回 <!doctype html>
```

### 方法2: 远程服务器部署

如果需要部署到远程服务器，请提供以下配置信息：
- 远程服务器地址（SSH host）
- 部署目录路径
- 重启命令（docker-compose / systemctl / npm）

---

## 快捷命令

在 GSD workflow 中，可以使用以下命令快速重启：

```bash
# 重启本地前端服务
/scripts/restart-frontend.sh

# 或手动执行
cd frontend && npm run dev -- --port 3000
```

---

## 注意事项

1. **端口保持3000** - 所有重启必须使用端口3000
2. **后台运行** - 使用 `&` 或 `run_in_background=true` 避免阻塞终端
3. **验证启动** - 重启后必须验证 `http://localhost:3000` 正常响应

---

## 部署检查清单

- [x] 代码已同步到本地仓库
- [x] 前端依赖已安装 (npm install)
- [x] TypeScript 类型检查通过
- [ ] 服务重启完成（端口3000）
- [ ] 浏览器刷新测试

---

*创建时间: 2026-04-08*
*最后更新: 2026-04-08*