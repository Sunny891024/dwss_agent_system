import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from openai import OpenAI
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dwss.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
ALGORITHM = "HS256"
AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").lower()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(100))
    company: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(String(100), default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(100))
    input_text: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class FormRecord(Base):
    __tablename__ = "form_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    form_code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(100), default="draft")
    current_assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    compliance_result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    company: str
    class Config:
        from_attributes = True

class ProjectIn(BaseModel):
    code: str
    name: str
    description: str = ""

class ProjectOut(ProjectIn):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class DocumentIn(BaseModel):
    project_id: int
    title: str
    content: str
    doc_type: str = "general"

class DocumentOut(DocumentIn):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class AgentRunIn(BaseModel):
    project_id: int
    document_id: Optional[int] = None
    agent_type: str
    input_text: str = ""

class AgentRunOut(BaseModel):
    id: int
    project_id: int
    document_id: Optional[int]
    agent_type: str
    input_text: str
    output_text: str
    created_at: datetime
    class Config:
        from_attributes = True

class FormIn(BaseModel):
    project_id: int
    form_code: str
    title: str
    current_assignee_id: Optional[int] = None
    payload: dict[str, Any] = {}

class FormUpdateIn(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    current_assignee_id: Optional[int] = None
    payload: Optional[dict[str, Any]] = None

class FormOut(BaseModel):
    id: int
    project_id: int
    form_code: str
    title: str
    status: str
    current_assignee_id: Optional[int]
    created_by_id: int
    payload_json: str
    compliance_result: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

app = FastAPI(title="DWSS AI Agent System", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_token(email: str, role: str) -> str:
    payload = {"sub": email, "role": role, "exp": datetime.utcnow() + timedelta(days=1)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(db_session)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    return user

def seed_data():
    db = SessionLocal()
    users = [
        ("admin@dwss.local", "Super Admin", "super_admin", "Platform"),
        ("form.a.filler@dwss.local", "Form A Filler", "form_filler", "Contractor"),
        ("form.a.signer@dwss.local", "Form A Signer", "form_signer", "Consultant"),
        ("safety.officer@dwss.local", "Safety Officer", "safety_officer", "Contractor"),
        ("qa.inspector@dwss.local", "QA Inspector", "qa_inspector", "Consultant"),
    ]
    for email, name, role, company in users:
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, name=name, role=role, company=company, password_hash=hash_password("test1234")))
    if not db.query(Project).filter(Project.code == "DWSS-DEMO").first():
        db.add(Project(code="DWSS-DEMO", name="DWSS Demo Project", description="Hong Kong Government Works DWSS demo project."))
    db.commit()
    db.close()

def run_mock_agent(agent_type: str, text: str) -> str:
    if agent_type == "document_parser":
        return """# 文件解析结果\n\n- 识别到 DWSS 工程监管场景。\n- 涉及表单、字段、审批角色、现场记录和合规要求。\n- 建议数据模型：Project、User、Document、AgentRun、FormRecord、AuditLog。\n- 风险点：复制历史表单可能导致当次现场事实缺失。"""
    if agent_type == "workflow":
        return """# Workflow 建议\n\n1. 创建表单。\n2. Filler 填写日期、时间、地点、责任人、检查内容、照片。\n3. Signer 审核签名。\n4. 系统合规检查。\n5. QA / Inspector 完成归档。"""
    if agent_type == "prd":
        return """# PRD 草案\n\n## 模块\n- 用户与角色\n- 项目管理\n- 文档管理\n- AI Agent\n- 表单填报\n- Workflow\n- 合规检查\n\n## 验收标准\n- 可登录。\n- 可创建项目。\n- 可录入文档。\n- 可运行 Agent。\n- 可创建表单并执行合规检查。"""
    if agent_type == "qa":
        return """# QA 测试计划\n\n## 正常流程\n登录 → 选择项目 → 新增文档 → 运行 Agent → 创建表单 → 合规检查。\n\n## 异常流程\n缺少日期、时间、地点、责任人、签名时应提示不合规。"""
    if agent_type == "compliance":
        required = ["date", "time", "location", "responsible_person", "signature"]
        missing = [k for k in required if k not in text.lower()]
        if missing:
            return "合规检查未通过，缺少字段：" + ", ".join(missing)
        return "合规检查通过。日期、时间、地点、责任人和签名字段已提供。"
    return "Agent 已完成处理。"

def run_agent(agent_type: str, text: str) -> str:
    if AI_PROVIDER == "openai" and os.getenv("OPENAI_API_KEY"):
        prompts = {
            "document_parser": "你是工程政府文件解析 Agent。提取表单、字段、角色、审批节点和合规要求。",
            "workflow": "你是 DWSS Workflow Agent。输出创建、填写、签名、指派、退回、完成流程。",
            "prd": "你是产品经理。整理可开发 PRD、模块、字段、权限、验收标准。",
            "qa": "你是 QA Agent。生成测试流程、异常流程、边界条件、验收标准。",
            "compliance": "你是工程记录合规检查 Agent。检查必填字段、照片、签名、责任人是否完整。",
        }
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": prompts.get(agent_type, "你是工程项目 AI Agent。")},
                {"role": "user", "content": text},
            ],
        )
        return resp.choices[0].message.content or ""
    return run_mock_agent(agent_type, text)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    seed_data()

@app.get("/")
def root():
    return {"status": "ok", "name": "DWSS AI Agent System"}

@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(db_session)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=create_token(user.email, user.role))

@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(db_session), user: User = Depends(current_user)):
    return db.query(User).order_by(User.id.asc()).all()

@app.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(db_session), user: User = Depends(current_user)):
    return db.query(Project).order_by(Project.id.desc()).all()

@app.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectIn, db: Session = Depends(db_session), user: User = Depends(current_user)):
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@app.get("/documents/project/{project_id}", response_model=list[DocumentOut])
def list_documents(project_id: int, db: Session = Depends(db_session), user: User = Depends(current_user)):
    return db.query(Document).filter(Document.project_id == project_id).order_by(Document.id.desc()).all()

@app.post("/documents", response_model=DocumentOut)
def create_document(payload: DocumentIn, db: Session = Depends(db_session), user: User = Depends(current_user)):
    doc = Document(**payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@app.post("/agents/run", response_model=AgentRunOut)
def create_agent_run(payload: AgentRunIn, db: Session = Depends(db_session), user: User = Depends(current_user)):
    text = payload.input_text or ""
    if payload.document_id:
        doc = db.query(Document).filter(Document.id == payload.document_id).first()
        if doc:
            text = f"文档标题：{doc.title}\n\n文档内容：\n{doc.content}\n\n用户补充：\n{text}"
    output = run_agent(payload.agent_type, text)
    run = AgentRun(project_id=payload.project_id, document_id=payload.document_id, agent_type=payload.agent_type, input_text=text, output_text=output)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

@app.get("/agents/project/{project_id}", response_model=list[AgentRunOut])
def list_agent_runs(project_id: int, db: Session = Depends(db_session), user: User = Depends(current_user)):
    return db.query(AgentRun).filter(AgentRun.project_id == project_id).order_by(AgentRun.id.desc()).all()

@app.get("/forms/project/{project_id}", response_model=list[FormOut])
def list_forms(project_id: int, db: Session = Depends(db_session), user: User = Depends(current_user)):
    return db.query(FormRecord).filter(FormRecord.project_id == project_id).order_by(FormRecord.id.desc()).all()

@app.post("/forms", response_model=FormOut)
def create_form(payload: FormIn, db: Session = Depends(db_session), user: User = Depends(current_user)):
    form = FormRecord(project_id=payload.project_id, form_code=payload.form_code, title=payload.title, current_assignee_id=payload.current_assignee_id, created_by_id=user.id, payload_json=json.dumps(payload.payload, ensure_ascii=False))
    db.add(form)
    db.commit()
    db.refresh(form)
    return form

@app.patch("/forms/{form_id}", response_model=FormOut)
def update_form(form_id: int, payload: FormUpdateIn, db: Session = Depends(db_session), user: User = Depends(current_user)):
    form = db.query(FormRecord).filter(FormRecord.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    if payload.title is not None:
        form.title = payload.title
    if payload.status is not None:
        form.status = payload.status
    if payload.current_assignee_id is not None:
        form.current_assignee_id = payload.current_assignee_id
    if payload.payload is not None:
        form.payload_json = json.dumps(payload.payload, ensure_ascii=False)
    form.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(form)
    return form

@app.post("/forms/{form_id}/compliance", response_model=FormOut)
def check_compliance(form_id: int, db: Session = Depends(db_session), user: User = Depends(current_user)):
    form = db.query(FormRecord).filter(FormRecord.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    form.compliance_result = run_agent("compliance", form.payload_json)
    form.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(form)
    return form
