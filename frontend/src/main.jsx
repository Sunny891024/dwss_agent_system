import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Bot, ClipboardCheck, FileText, GitBranch, LogOut, Play, Plus } from "lucide-react";
import "./styles.css";
import { api, getToken, logout, setToken } from "./api";

function Login({ onLogin }) {
  const [email, setEmail] = useState("admin@dwss.local");
  const [password, setPassword] = useState("test1234");
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const result = await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setToken(result.access_token);
      onLogin();
    } catch {
      setError("登录失败，请检查账号密码");
    }
  }
  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form onSubmit={submit} className="bg-white rounded-2xl shadow p-8 w-full max-w-md space-y-5">
        <div>
          <h1 className="text-2xl font-bold">DWSS AI Agent System</h1>
          <p className="text-gray-500 mt-1">工程监管智能工作流系统</p>
        </div>
        <input className="w-full border rounded-xl px-4 py-3" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
        <input className="w-full border rounded-xl px-4 py-3" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button className="w-full bg-black text-white rounded-xl py-3 font-medium">登录</button>
        <div className="text-xs text-gray-500">测试账号：admin@dwss.local / test1234</div>
      </form>
    </div>
  );
}

function Card({ title, icon, children }) {
  const Icon = icon;
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={20} />}
        <h2 className="font-semibold text-lg">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function App() {
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState(null);
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [agentRuns, setAgentRuns] = useState([]);
  const [forms, setForms] = useState([]);
  const [users, setUsers] = useState([]);
  const [docTitle, setDocTitle] = useState("DWSS Requirement Notes");
  const [docContent, setDocContent] = useState("Weekly Safety Walk should record date, time, location, responsible_person, site photos, non-compliance, remedial works and signature.");
  const [agentType, setAgentType] = useState("document_parser");
  const [loading, setLoading] = useState(false);

  async function load() {
    const meRes = await api("/auth/me");
    const usersRes = await api("/users");
    const projectsRes = await api("/projects");
    setMe(meRes);
    setUsers(usersRes);
    setProjects(projectsRes);
    const first = projectsRes[0]?.id;
    if (first) setProjectId(first);
    setReady(true);
  }
  async function loadProjectData(id) {
    if (!id) return;
    const [docs, runs, fs] = await Promise.all([
      api(`/documents/project/${id}`), api(`/agents/project/${id}`), api(`/forms/project/${id}`),
    ]);
    setDocuments(docs); setAgentRuns(runs); setForms(fs);
  }
  useEffect(() => {
    if (!getToken()) { setReady(true); return; }
    load().catch(() => { localStorage.removeItem("token"); setReady(true); });
  }, []);
  useEffect(() => { loadProjectData(projectId).catch(console.error); }, [projectId]);

  async function createProject() {
    const code = prompt("项目编号", "DWSS-" + Date.now().toString().slice(-4));
    if (!code) return;
    await api("/projects", { method: "POST", body: JSON.stringify({ code, name: code + " Project", description: "AI Agent DWSS Project" }) });
    await load();
  }
  async function createDocument() {
    await api("/documents", { method: "POST", body: JSON.stringify({ project_id: projectId, title: docTitle, content: docContent, doc_type: "requirement" }) });
    await loadProjectData(projectId);
  }
  async function runAgent(documentId = null) {
    setLoading(true);
    try {
      await api("/agents/run", { method: "POST", body: JSON.stringify({ project_id: projectId, document_id: documentId, agent_type: agentType, input_text: documentId ? "" : docContent }) });
      await loadProjectData(projectId);
    } finally { setLoading(false); }
  }
  async function createForm() {
    const assignee = users.find(u => u.role === "safety_officer") || users[0];
    await api("/forms", { method: "POST", body: JSON.stringify({ project_id: projectId, form_code: "WSW", title: "Weekly Safety Walk - Demo", current_assignee_id: assignee?.id, payload: { date: "2026-05-02", time: "10:00", location: "Site Area A", responsible_person: "Safety Officer", description: "Weekly inspection record", signature: "Form A Signer" } }) });
    await loadProjectData(projectId);
  }
  async function checkCompliance(formId) {
    await api(`/forms/${formId}/compliance`, { method: "POST" });
    await loadProjectData(projectId);
  }

  if (!ready) return <div className="p-10">Loading...</div>;
  if (!getToken()) return <Login onLogin={load} />;

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div><h1 className="font-bold text-xl">DWSS AI Agent System</h1><p className="text-sm text-gray-500">Digital Workflow and Supervision System</p></div>
          <div className="flex items-center gap-4"><span className="text-sm text-gray-600">{me?.name} · {me?.role}</span><button onClick={logout} className="flex items-center gap-1 text-sm border rounded-xl px-3 py-2"><LogOut size={16} /> 退出</button></div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-1 space-y-6">
          <Card title="项目" icon={GitBranch}>
            <div className="space-y-3"><select className="w-full border rounded-xl px-3 py-2" value={projectId || ""} onChange={e => setProjectId(Number(e.target.value))}>{projects.map(p => <option key={p.id} value={p.id}>{p.code} - {p.name}</option>)}</select><button onClick={createProject} className="flex items-center justify-center gap-2 w-full border rounded-xl py-2"><Plus size={16} /> 新建项目</button></div>
          </Card>
          <Card title="文档录入" icon={FileText}>
            <div className="space-y-3"><input className="w-full border rounded-xl px-3 py-2" value={docTitle} onChange={e => setDocTitle(e.target.value)} /><textarea className="w-full border rounded-xl px-3 py-2 h-40" value={docContent} onChange={e => setDocContent(e.target.value)} /><button onClick={createDocument} className="w-full bg-black text-white rounded-xl py-2">保存文档</button></div>
          </Card>
          <Card title="AI Agent" icon={Bot}>
            <div className="space-y-3"><select className="w-full border rounded-xl px-3 py-2" value={agentType} onChange={e => setAgentType(e.target.value)}><option value="document_parser">文件解析 Agent</option><option value="workflow">Workflow Agent</option><option value="prd">PRD Agent</option><option value="qa">QA Agent</option><option value="compliance">合规检查 Agent</option></select><button disabled={loading} onClick={() => runAgent()} className="flex items-center justify-center gap-2 w-full bg-black text-white rounded-xl py-2 disabled:opacity-50"><Play size={16} /> {loading ? "运行中..." : "运行 Agent"}</button></div>
          </Card>
        </section>
        <section className="lg:col-span-2 space-y-6">
          <Card title="项目文档" icon={FileText}>
            <div className="space-y-3">{documents.length === 0 && <p className="text-gray-500">暂无文档</p>}{documents.map(doc => <div key={doc.id} className="border rounded-xl p-4"><div className="flex justify-between gap-4"><div><h3 className="font-medium">{doc.title}</h3><p className="text-sm text-gray-500 line-clamp-2">{doc.content}</p></div><button onClick={() => runAgent(doc.id)} className="shrink-0 border rounded-xl px-3 py-2 text-sm">解析</button></div></div>)}</div>
          </Card>
          <Card title="表单记录" icon={ClipboardCheck}>
            <div className="space-y-3"><button onClick={createForm} className="border rounded-xl px-4 py-2 text-sm">创建 Weekly Safety Walk 示例表单</button>{forms.map(form => <div key={form.id} className="border rounded-xl p-4 space-y-2"><div className="flex justify-between"><div><h3 className="font-medium">{form.form_code} · {form.title}</h3><p className="text-sm text-gray-500">状态：{form.status}</p></div><button onClick={() => checkCompliance(form.id)} className="border rounded-xl px-3 py-2 text-sm">合规检查</button></div><pre className="bg-gray-50 rounded-xl p-3 text-xs overflow-auto">{form.payload_json}</pre>{form.compliance_result && <div className="bg-green-50 border border-green-100 rounded-xl p-3 text-sm">{form.compliance_result}</div>}</div>)}</div>
          </Card>
          <Card title="Agent 输出记录" icon={Bot}>
            <div className="space-y-4">{agentRuns.length === 0 && <p className="text-gray-500">暂无 Agent 运行记录</p>}{agentRuns.map(run => <div key={run.id} className="border rounded-xl p-4"><div className="flex justify-between mb-2"><h3 className="font-medium">{run.agent_type}</h3><span className="text-xs text-gray-400">{new Date(run.created_at).toLocaleString()}</span></div><pre className="whitespace-pre-wrap text-sm bg-gray-50 rounded-xl p-4 overflow-auto">{run.output_text}</pre></div>)}</div>
          </Card>
        </section>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
