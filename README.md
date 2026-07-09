# 📧 令牌取件系统 - 微软令牌网页取件

一个基于 Flask 的 Outlook 邮箱令牌管理与邮件收取系统，支持多账号管理、分组管理、邮件查看，以及 AI Agent 自动化调用。

## ✨ 功能特性

- 📥 **导入令牌账号** - 支持文本输入和 TXT 文件上传
- 📂 **分组管理** - 新建分组、删除分组、移动账号
- 📧 **收取邮件** - 通过 Microsoft Graph API 获取邮件
- 📬 **最新邮件** - 一键查看最新一封邮件
- 📖 **邮件详情** - 查看完整邮件内容（支持 HTML 格式）
- ✅ **多账号管理** - 全选、批量删除、导出账密
- 📋 **导出原数据** - 导出完整令牌数据
- 🔄 **自动刷新 Token** - Token 失效时自动刷新
- 🔍 **搜索邮箱账号** - 按邮箱地址过滤账号
- 🤖 **AI Agent 接口** - 供其他 AI Agent 调用获取邮件

## 🛠️ 技术栈

- **后端**: Python + Flask
- **前端**: 原生 HTML / CSS / JavaScript
- **存储**: JSON 文件
- **邮件 API**: Microsoft Graph API + OAuth2

## 📦 安装与运行

### 1. 克隆项目

```bash
git clone https://github.com/a137460387/email-token-post.git
cd email-token-post
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
python app.py
```

### 4. 访问页面

打开浏览器访问：http://localhost:5000

## 📝 账号格式

导入账号时使用以下格式（每行一个）：

```
email----password----client_id----refresh_token
```

示例：
```
user@outlook.com----password----9e5f94bc-e8a4-4e73-b8be-63364c29d753----M.C555_BAY.0.xxx...
```

## 📁 项目结构

```
email-token-post/
├── app.py              # Flask 后端主程序
├── requirements.txt    # Python 依赖
├── .gitignore         # Git 忽略文件
├── data.json          # 账号数据存储（自动生成，已忽略）
├── static/
│   ├── style.css      # 样式文件
│   └── app.js         # 前端 JavaScript
└── templates/
    └── index.html     # 主页面模板
```

## 🔌 API 接口

### 分组管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/groups` | 获取所有分组 |
| POST | `/api/groups` | 创建新分组 |
| DELETE | `/api/groups/<id>` | 删除分组 |
| POST | `/api/groups/move` | 移动账号到指定分组 |

### 账号管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/accounts/import` | 批量导入账号 |
| DELETE | `/api/accounts/<id>` | 删除单个账号 |
| DELETE | `/api/accounts/batch` | 批量删除账号 |
| POST | `/api/accounts/export` | 导出账密 |
| POST | `/api/accounts/raw` | 导出原始数据 |

### 邮件操作

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/emails/<account_id>` | 获取邮件列表 |
| GET | `/api/emails/<account_id>/latest` | 获取最新邮件 |
| GET | `/api/emails/<account_id>/<message_id>` | 获取邮件详情 |
| POST | `/api/emails/<account_id>/<message_id>/read` | 标记邮件已读 |

### 🤖 AI Agent 专用接口

供其他 AI Agent 程序调用，自动处理 Token 刷新。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agent/accounts` | 获取所有账号列表 |
| GET | `/api/agent/emails` | 获取指定邮箱的邮件 |

#### 获取账号列表

```bash
curl "http://localhost:5000/api/agent/accounts"
```

响应：
```json
{
  "success": true,
  "accounts": [
    {"email": "user@outlook.com", "status": "有效"}
  ],
  "count": 1
}
```

#### 获取邮件

```bash
# 获取最新一封邮件
curl "http://localhost:5000/api/agent/emails?email=user@outlook.com&latest=1"

# 获取最新 5 封邮件
curl "http://localhost:5000/api/agent/emails?email=user@outlook.com&top=5"

# 搜索包含关键词的邮件
curl "http://localhost:5000/api/agent/emails?email=user@outlook.com&keyword=验证码"
```

**参数说明：**

| 参数 | 必须 | 说明 |
|------|------|------|
| `email` | 是 | 邮箱地址 |
| `latest` | 否 | 设为 `1` 只获取最新一封 |
| `keyword` | 否 | 搜索关键词 |
| `top` | 否 | 获取数量，默认 20 |

**响应示例（latest=1）：**

```json
{
  "success": true,
  "email": "user@outlook.com",
  "message": {
    "id": "AQMkAD...",
    "subject": "Your verification code",
    "from": {"emailAddress": {"address": "noreply@example.com", "name": "Example"}},
    "receivedDateTime": "2026-07-09T12:00:00Z",
    "bodyPreview": "Your code is 123456",
    "body": {"contentType": "html", "content": "<html>...</html>"},
    "isRead": false
  }
}
```

**响应示例（列表）：**

```json
{
  "success": true,
  "email": "user@outlook.com",
  "messages": [...],
  "count": 5
}
```

## 📸 界面预览

三栏布局：
- **左侧**: 分组管理面板
- **中间**: 账号列表（可搜索、勾选、批量操作）
- **右侧**: 邮件列表 / 邮件详情

## ⚠️ 注意事项

- `data.json` 包含敏感信息（账号密码和 Token），已加入 `.gitignore`
- 首次运行会自动创建 `data.json` 文件
- Token 刷新使用 Microsoft OAuth2 `.default` scope
- Token 有效期约 1 小时，过期自动刷新
- 本地使用建议绑定 `127.0.0.1`，避免暴露到网络

## 📄 License

MIT License
