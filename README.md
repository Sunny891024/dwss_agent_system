# DWSS AI Agent System MVP

这是一个可运行的完整 MVP 系统代码，用于 DWSS / 工程监管 AI Agent 项目。

## 包含功能

- 登录认证
- 用户角色
- 项目管理
- 文档录入
- AI Agent：文件解析、Workflow、PRD、QA、合规检查
- 表单记录
- 表单合规检查
- SQLite 数据库
- React 前端
- OpenAI API 接入预留
- Mock Agent：没有 API Key 也能跑通

## 后端启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

打开 API 文档：

```bash
http://localhost:8000/docs
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

打开：

```bash
http://localhost:5173
```

## 测试账号

```text
admin@dwss.local / test1234
form.a.filler@dwss.local / test1234
form.a.signer@dwss.local / test1234
safety.officer@dwss.local / test1234
qa.inspector@dwss.local / test1234
```

## 使用真实 OpenAI

编辑 `backend/.env`：

```env
AI_PROVIDER=openai
OPENAI_API_KEY=你的key
OPENAI_MODEL=gpt-4.1-mini
```

默认是：

```env
AI_PROVIDER=mock
```
