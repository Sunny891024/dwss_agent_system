const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export function getToken() { return localStorage.getItem("token"); }
export function setToken(token) { localStorage.setItem("token", token); }
export function logout() { localStorage.removeItem("token"); window.location.reload(); }
export async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
