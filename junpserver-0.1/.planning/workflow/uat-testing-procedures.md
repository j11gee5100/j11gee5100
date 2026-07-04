# GSD UAT 测试流程规范

**重要原则:**

1. **代码同步由 Claude 自动执行** - 测试过程中发现问题时，Claude 自动同步修复代码到远程服务器
2. **服务重启由 Claude 自动执行** - 修复完成后自动重启远程服务
3. **用户只负责验证** - 用户只需测试功能并反馈结果
4. **使用 SSH 密钥认证** - 自动化执行，无需密码输入

---

## 标准测试流程

### 步骤 1: 发现问题
用户测试功能 → 报告问题（直接描述，无需其他操作）

### 步骤 2: Claude 自动处理
```
Claude 执行:
1. 诊断问题 → 定位代码
2. 修复代码
3. 同步代码到远程服务器（自动执行，SSH 密钥认证）
4. 重启远程服务（自动执行）
5. 提示用户重新测试
```

### 步骤 3: 用户验证
用户刷新页面 → 重新测试 → 反馈结果

---

## 远程部署配置

详细配置见: `.planning/workflow/remote-deploy.md`

**关键配置:**
```yaml
SSH连接: jykj@172.24.26.12
认证方式: SSH 密钥认证（位于 ~/.ssh/id_rsa）
部署路径: /home/jykj/opspaw
服务端口: 3000
```

**自动同步命令:**
```bash
scp -r -o StrictHostKeyChecking=no \
  F:/jingying/junpserver/junpserver/frontend/src \
  jykj@172.24.26.12:/home/jykj/opspaw/frontend/
```

**自动重启命令:**
```bash
ssh -o StrictHostKeyChecking=no jykj@172.24.26.12 \
  'cd /home/jykj/opspaw && lsof -ti:3000 | xargs kill -9 2>/dev/null; cd frontend && nohup npm run dev -- --port 3000 > /tmp/frontend.log 2>&1 &'
```

---

## 测试流程示例

**用户:** "模板中心创建了一个本应该拦截的命令，但是成功了"

**Claude 自动执行:**
1. ✅ 诊断问题：模板创建时没有检查策略评估结果
2. ✅ 修复代码：添加 `evalResult` 状态，禁用提交按钮
3. ✅ 同步代码：使用 `scp` 同步到远程服务器
4. ✅ 重启服务：SSH 连接重启前端服务
5. ✅ 提示用户："请刷新页面重新测试"

**用户:** 刷新页面 → 重新测试 → 反馈结果

---

## 注意事项

- ❌ 不要让用户手动同步代码
- ❌ 不要让用户手动重启服务
- ✅ Claude 负责所有代码同步和服务重启操作
- ✅ 使用 SSH 密钥认证，自动化执行
- ✅ 用户只需测试功能并反馈结果

---

*创建时间: 2026-04-08*
*最后更新: 2026-04-08*