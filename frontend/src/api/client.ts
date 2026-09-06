const API_ROOT = "/v1/mnp";

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
    localStorage.removeItem(sessionStorageKeys.session);
    token = await ensurePersonSession();
    response = await execute();
  }
  return decode<T>(response);
}

export async function adminLogin(email: string, password: string) {
  const data = await fetchJson<{ access_token: string; email: string; role: string }>("/admin/auth/login", {
    method: "POST", headers: jsonHeaders, body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(sessionStorageKeys.admin, data.access_token);
  return data;
}

export async function adminRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(sessionStorageKeys.admin);
  if (!token) throw new ApiError("Потрібен вхід консультанта", 401);
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { ...jsonHeaders, ...init.headers, Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) localStorage.removeItem(sessionStorageKeys.admin);
  return decode<T>(response);
}

export const publicRequest = <T,>(path: string) => fetchJson<T>(`${API_ROOT}${path}`);
