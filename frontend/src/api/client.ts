const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
const API_ROOT = `${API_ORIGIN}/v1/mnp`;

export const apiUrl = (path: string) => `${API_ORIGIN}${path}`;

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = response.statusText || "Помилка запиту";
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch { /* keep HTTP message */ }
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? (null as T) : response.json() as Promise<T>;
}

async function fetchJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, init);
  return decode<T>(response);
}

const jsonHeaders = { "Content-Type": "application/json" };

export const sessionStorageKeys = {
  user: "mnp_user_id",
  session: "mnp_session_token",
  account: "mnp_user_account",
  admin: "mnp_admin_token",
};

export async function ensurePersonSession(): Promise<string> {
  const existing = localStorage.getItem(sessionStorageKeys.session);
  if (existing) return existing;
  const data = await fetchJson<{ user_id: string; session_token: string }>(`${API_ROOT}/session`, { method: "POST" });
  localStorage.setItem(sessionStorageKeys.user, data.user_id);
  localStorage.setItem(sessionStorageKeys.session, data.session_token);
  return data.session_token;
}

export async function personRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let token = await ensurePersonSession();
  const execute = () => fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { ...(init.body instanceof FormData ? {} : jsonHeaders), ...init.headers, Authorization: `Bearer ${token}` },
  });
  let response = await execute();
  if (response.status === 401) {
    if (localStorage.getItem(sessionStorageKeys.account)) {
      localStorage.removeItem(sessionStorageKeys.session);
      localStorage.removeItem(sessionStorageKeys.user);
      localStorage.removeItem(sessionStorageKeys.account);
      window.dispatchEvent(new Event("user-session-expired"));
      return decode<T>(response);
    }
    localStorage.removeItem(sessionStorageKeys.session);
    token = await ensurePersonSession();
    response = await execute();
  }
  return decode<T>(response);
}

export async function adminLogin(email: string, password: string) {
  const data = await fetchJson<{ access_token: string; email: string; role: string }>(apiUrl("/admin/auth/login"), {
    method: "POST", headers: jsonHeaders, body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(sessionStorageKeys.admin, data.access_token);
  return data;
}

export type UnifiedAuthResponse = {
  account_type: "user" | "staff";
  email: string;
  role: string;
  access_token?: string;
  session_token?: string;
  user_id?: string;
};

export async function unifiedLogin(email: string, password: string) {
  return fetchJson<UnifiedAuthResponse>(`${API_ROOT}/auth/login`, {
    method: "POST", headers: jsonHeaders, body: JSON.stringify({ email, password }),
  });
}

export async function registerUser(email: string, password: string) {
  const existingSession = localStorage.getItem(sessionStorageKeys.session);
  return fetchJson<UnifiedAuthResponse>(`${API_ROOT}/auth/register`, {
    method: "POST",
    headers: { ...jsonHeaders, ...(existingSession ? { Authorization: `Bearer ${existingSession}` } : {}) },
    body: JSON.stringify({ email, password }),
  });
}

export async function adminBootstrapStatus() {
  return fetchJson<{ registration_open: boolean }>(apiUrl("/admin/auth/bootstrap/status"));
}

export async function bootstrapSuperAdmin(full_name: string, email: string, password: string) {
  return fetchJson<{ id: number; email: string }>(apiUrl("/admin/auth/bootstrap"), {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ full_name, email, password, role: "super_admin" }),
  });
}

export async function adminRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(sessionStorageKeys.admin);
  if (!token) throw new ApiError("Потрібен вхід консультанта", 401);
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { ...(init.body instanceof FormData ? {} : jsonHeaders), ...init.headers, Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) {
    localStorage.removeItem(sessionStorageKeys.admin);
    window.dispatchEvent(new Event("console-session-expired"));
  }
  return decode<T>(response);
}

export async function adminDownload(path: string): Promise<Blob> {
  const token = localStorage.getItem(sessionStorageKeys.admin);
  if (!token) throw new ApiError("Потрібен вхід консультанта", 401);
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) {
    localStorage.removeItem(sessionStorageKeys.admin);
    window.dispatchEvent(new Event("console-session-expired"));
  }
  if (!response.ok) await decode<never>(response);
  return response.blob();
}

export const publicRequest = <T,>(path: string) => fetchJson<T>(`${API_ROOT}${path}`);
