const TOKEN_KEY = "ican_admin_token";
const SESSION_KEY = "ican_admin_session";

export function getSession() {
  const raw = localStorage.getItem(SESSION_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSession(token, email, role) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(SESSION_KEY, JSON.stringify({ email, role }));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(SESSION_KEY);
}

export function isLoggedIn() {
  return Boolean(localStorage.getItem(TOKEN_KEY));
}

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth) {
    clearSession();
    window.location.hash = "#/login";
    throw new ApiError(401, "Сесія закінчилась, увійдіть знову");
  }

  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

async function upload(path, formData) {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(path, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

async function download(path) {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  return { blob, filename: match ? match[1] : "file" };
}

export const api = {
  login: (email, password) => request("/admin/auth/login", { method: "POST", body: { email, password }, auth: false }),

  // Legacy simple dashboard (still used for raw bot conversation view)
  legacySummary: () => request("/admin/dashboard/summary"),
  legacyListUsers: (params) => request(`/admin/users?${new URLSearchParams(params)}`),
  legacyGetUser: (id) => request(`/admin/users/${id}`),
  legacyGetMessages: (id) => request(`/admin/users/${id}/messages`),

  // CRM
  me: () => request("/crm/me"),
  dashboard: () => request("/crm/dashboard"),
  listClients: (params) => request(`/crm/clients?${new URLSearchParams(params)}`),
  createClient: (data) => request("/crm/clients", { method: "POST", body: data }),
  getClient: (id) => request(`/crm/clients/${id}`),
  updateClient: (id, changes) => request(`/crm/clients/${id}`, { method: "PATCH", body: changes }),
  updateClientProfile: (id, changes) => request(`/crm/clients/${id}/profile`, { method: "PATCH", body: changes }),

  addWorkExperience: (id, data) => request(`/crm/clients/${id}/work-experience`, { method: "POST", body: data }),
  updateWorkExperience: (id, weId, data) => request(`/crm/clients/${id}/work-experience/${weId}`, { method: "PATCH", body: data }),
  deleteWorkExperience: (id, weId) => request(`/crm/clients/${id}/work-experience/${weId}`, { method: "DELETE" }),

  addSkill: (id, data) => request(`/crm/clients/${id}/skills`, { method: "POST", body: data }),
  deleteSkill: (id, skillId) => request(`/crm/clients/${id}/skills/${skillId}`, { method: "DELETE" }),

  addLanguage: (id, data) => request(`/crm/clients/${id}/languages`, { method: "POST", body: data }),
  deleteLanguage: (id, langId) => request(`/crm/clients/${id}/languages/${langId}`, { method: "DELETE" }),

  assignConsultant: (id, staffId) => request(`/crm/clients/${id}/assign-consultant`, { method: "POST", body: { staff_id: staffId } }),
  assignManager: (id, staffId) => request(`/crm/clients/${id}/assign-manager`, { method: "POST", body: { staff_id: staffId } }),
  setStatus: (id, statusValue) => request(`/crm/clients/${id}/status`, { method: "POST", body: { status: statusValue } }),
  completeScreening: (id) => request(`/crm/clients/${id}/screening/complete`, { method: "POST" }),
  readyForMatching: (id) => request(`/crm/clients/${id}/ready-for-matching`, { method: "POST" }),

  getConsultation: (id) => request(`/crm/clients/${id}/career-consultation`),
  saveConsultationDraft: (id, data) => request(`/crm/clients/${id}/career-consultation`, { method: "PATCH", body: data }),
  completeConsultation: (id, conclusion) => request(`/crm/clients/${id}/career-consultation/complete`, { method: "POST", body: { conclusion } }),

  listCalls: (id) => request(`/crm/clients/${id}/calls`),
  logCall: (id, data) => request(`/crm/clients/${id}/calls`, { method: "POST", body: data }),

  listTasks: (id) => request(`/crm/clients/${id}/tasks`),
  createTask: (id, data) => request(`/crm/clients/${id}/tasks`, { method: "POST", body: data }),
  completeTask: (taskId) => request(`/crm/tasks/${taskId}/complete`, { method: "POST" }),
  cancelTask: (taskId) => request(`/crm/tasks/${taskId}/cancel`, { method: "POST" }),

  getTimeline: (id) => request(`/crm/clients/${id}/timeline`),

  listFiles: (id) => request(`/crm/clients/${id}/files`),
  uploadFile: (id, fileType, otherDescription, file) => {
    const fd = new FormData();
    fd.append("file_type", fileType);
    if (otherDescription) fd.append("other_description", otherDescription);
    fd.append("upload", file);
    return upload(`/crm/clients/${id}/files`, fd);
  },
  downloadFile: (id, fileId) => download(`/crm/clients/${id}/files/${fileId}/download`),
  markCurrentCv: (id, fileId) => request(`/crm/clients/${id}/files/${fileId}/current-cv`, { method: "PATCH" }),
  deleteFile: (id, fileId) => request(`/crm/clients/${id}/files/${fileId}`, { method: "DELETE" }),

  assignableStaff: (role) => request(`/crm/users/assignable?role=${role}`),
  listStaff: () => request("/crm/users"),
  createStaff: (data) => request("/crm/users", { method: "POST", body: data }),
  updateStaff: (id, data) => request(`/crm/users/${id}`, { method: "PATCH", body: data }),

  // MNP Direction Intelligence consultant workspace (Stage 4A)
  mnpListClients: (filter) => request(`/direction/clients${filter ? `?filter=${filter}` : ""}`),
  mnpClientCard: (userId) => request(`/direction/clients/${userId}/card`),
  mnpGenerateDirections: (userId) => request(`/direction/clients/${userId}/generate`, { method: "POST", body: {} }),
  mnpRunCritic: (runId) => request(`/direction/runs/${runId}/critic`, { method: "POST" }),
  mnpGenerateNarrative: (runId) => request(`/direction/runs/${runId}/narrative`, { method: "POST" }),
  mnpCreateCorrection: (runId, data) => request(`/direction/runs/${runId}/corrections`, { method: "POST", body: data }),
  mnpApprove: (runId, comment) => request(`/direction/runs/${runId}/approve`, { method: "POST", body: { comment } }),
  mnpRequestChanges: (runId, comment) => request(`/direction/runs/${runId}/request-changes`, { method: "POST", body: { comment } }),
  mnpReject: (runId, comment) => request(`/direction/runs/${runId}/reject`, { method: "POST", body: { comment } }),
  mnpPublishablePreview: (userId) => request(`/direction/clients/${userId}/publishable`),
};

export { ApiError };
