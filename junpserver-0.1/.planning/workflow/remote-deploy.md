# 远程服务器部署流程

**目的:** 标准化代码同步和远程服务重启流程

**重要:** 
- Claude 使用 SSH 密钥认证自动同步代码和重启服务
- SSH 密钥位于: `~/.ssh/id_rsa`
- 无需密码输入，自动化执行

---

## 服务器配置

```yaml
SSH连接: jykj@172.24.26.12
认证方式: SSH 密钥认证（无密码）
部署路径: /home/jykj/opspaw
服务端口: 3000
```

---

## 标准部署流程（自动执行）

### 步骤 1: 同步代码到远程服务器

```bash
# 使用 SSH 密钥同步前端源码（自动执行，无需密码）
scp -r -o StrictHostKeyChecking=no \
  F:/jingying/junpserver/junpserver/frontend/src \
  jykj@172.24.26.12:/home/jykj/opspaw/frontend/
```

### 步骤 2: 重启远程服务

```bash
# SSH 连接到远程服务器重启服务
ssh -o StrictHostKeyChecking=no jykj@172.24.26.12 << 'EOF'
  cd /home/jykj/opspaw

  # Kill 3000 端口占用
  lsof -ti:3000 | xargs kill -9 2>/dev/null || true

  # 启动前端服务（后台运行）
  cd frontend && nohup npm run dev -- --port 3000 > /tmp/frontend.log 2>&1 &

  # 验证服务启动
  sleep 3
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 && echo " - 服务正常"
EOF
```

### 步骤 3: 验证部署

```bash
# 检查远程服务状态
curl -s http://172.24.26.12:3000 | head -5
```

---

## 快速部署命令（一键执行）

```bash
# 完整部署流程
scp -r -o StrictHostKeyChecking=no \
  F:/jingying/junpserver/junpserver/frontend/src \
  jykj@172.24.26.12:/home/jykj/opspaw/frontend/ && \
ssh -o StrictHostKeyChecking=no jykj@172.24.26.12 \
  'cd /home/jykj/opspaw && lsof -ti:3000 | xargs kill -9 2>/dev/null; cd frontend && nohup npm run dev -- --port 3000 > /tmp/frontend.log 2>&1 &'
```

---

## SSH 密钥配置说明

**当前位置:** `~/.ssh/id_rsa`

**SSH 密钥认证优势:**
- ✅ 无需密码输入，完全自动化
- ✅ 安全可靠，支持免密登录
- ✅ 适用于 scp、ssh 等所有 SSH 操作

**首次配置（如果需要）:**
```bash
# 生成 SSH 密钥对（如果不存在）
ssh-keygen -t rsa -b 4096

# 将公钥复制到远程服务器
ssh-copy-id jykj@172.24.26.12

# 测试免密登录
ssh jykj@172.24.26.12 'echo "认证成功"'
```

### 步骤 3: 验证部署

```bash
# 检查远程服务状态
curl -s http://172.24.26.12:3000 | head -5
```

---

## 快速部署命令（一键执行）

```bash
# 完整部署流程
rsync -avz --exclude 'node_modules' --exclude '.git' --exclude '.planning' \
  F:/jingying/junpserver/junpserver/ \
  jykj@172.24.26.12:/home/jykj/opspaw/ && \
ssh jykj@172.24.26.12 'cd /home/jykj/opspaw && lsof -ti:3000 | xargs kill -9 2>/dev/null; cd frontend && nohup npm run dev -- --port 3000 > /tmp/frontend.log 2>&1 &'
```

---

## 注意事项

1. **首次部署**: 需要在远程服务器执行 `cd frontend && npm install`
2. **端口冲突**: 部署前自动 kill 3000 端口占用
3. **日志查看**: `ssh jykj@172.24.26.12 'tail -f /tmp/frontend.log'`
4. **服务验证**: 访问 `http://172.24.26.12:3000` 确认部署成功

---

## 故障排查

| 问题 | 解决方案 |
|------|---------|
| 无法连接 SSH | 检查网络和 SSH 服务状态 |
| rsync 失败 | 确认目标目录有写权限 |
| 端口被占用 | `lsof -ti:3000 \| xargs kill -9` |
| npm install 失败 | 检查 Node.js 版本和 npm 源配置 |

---

*创建时间: 2026-04-08*
*最后更新: 2026-04-08*