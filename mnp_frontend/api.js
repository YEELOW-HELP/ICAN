// Thin fetch wrapper for the MNP V1 API (MNP_API_CONTRACTS_V1). No
// framework -- matches admin_frontend's own plain-JS convention.

const MnpApi = (() => {
  const BASE = "/v1/mnp";

  function getUserId() {
    return localStorage.getItem("mnp_user_id");
  }
  function getToken() {
    return localStorage.getItem("mnp_session_token");
  }

  async function ensureSession() {
    if (getToken()) return getUserId();
    return createNewSession();
  }

  async function createNewSession() {
    const res = await fetch(`${BASE}/session`, { method: "POST" });
    const data = await res.json();
    localStorage.setItem("mnp_user_id", data.user_id);
    // secure bearer token -- authenticates private user routes; never
    // derivable from user_id. Person KB routes accept ONLY this.
    if (data.session_token) localStorage.setItem("mnp_session_token", data.session_token);
    return data.user_id;
  }

  async function doFetch(path, method, headers, payload) {
    const token = getToken();
    const auth = token ? { Authorization: `Bearer ${token}` } : {};
    return fetch(`${BASE}${path}`, { method, headers: { ...headers, ...auth }, body: payload });
  }

  async function request(path, { method = "GET", body, isForm = false } = {}) {
    await ensureSession();
    const headers = {};
    let payload = body;
    if (body && !isForm) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let res = await doFetch(path, method, headers, payload);

    if (res.status === 401 || res.status === 404) {
      // session token no longer valid on the server (e.g. a local dev DB
      // was reset) -> start a fresh session and retry once. A normal 404
      // like "no Career Card yet" is re-raised to the caller below.
      let detail = "";
      try { detail = (await res.clone().json()).detail || ""; } catch (e) {}
      if (res.status === 401 || detail.includes("Unknown session") || detail.includes("сесі")) {
        localStorage.removeItem("mnp_session_token");
        await createNewSession();
        res = await doFetch(path, method, headers, payload);
      }
    }

    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) {}
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    return res.status === 204 ? null : res.json();
  }

  return {
    getUserId, ensureSession,
    // generic user-scoped request (Bearer session token auto-attached). Used by
    // the Person KB user flows. `isForm: true` for multipart uploads.
    request,
    uploadDocument: (file) => {
      const form = new FormData();
      form.append("file", file);
      return request("/documents", { method: "POST", body: form, isForm: true });
    },
    getCareerCard: () => request("/career-card").catch((e) => (e.status === 404 ? null : Promise.reject(e))),
    // No Career Card yet (404) means EVERYTHING is still missing, not
    // nothing -- the opposite fallback would silently hide every
    // "already known" question a brand-new user actually still needs.
    getMissingFields: () => request("/questionnaire/missing").catch((e) => (e.status === 404 ? { career_capital: ["current_role", "education", "languages"], career_intent: ["goal", "income_target", "preference_profile", "learning_capacity"] } : Promise.reject(e))),
    submitCareerCapital: (answers) => request("/questionnaire/career-capital", { method: "POST", body: answers }),
    submitCareerIntent: (answers) => request("/questionnaire/career-intent", { method: "POST", body: answers }),
    createMatchRun: (rankingMode) => request("/match-runs", { method: "POST", body: { ranking_mode: rankingMode || "best_for_me" } }),
    getMatchRunCareers: (matchRunId) => request(`/match-runs/${matchRunId}/careers`),
    getCareerMatchDetail: (careerMatchId) => request(`/career-matches/${careerMatchId}`),
    getCareerMatchRoute: (careerMatchId) => request(`/career-matches/${careerMatchId}/route`),
    listCareers: () => request("/careers"),
    getCareerDetail: (careerId) => request(`/careers/${careerId}`),

    // --- Career KB Editor (admin only) -------------------------------
    getAdminToken: () => localStorage.getItem("mnp_admin_token"),
    isAdmin: () => !!localStorage.getItem("mnp_admin_token"),
    adminLogout: () => localStorage.removeItem("mnp_admin_token"),
    async adminLogin(email, password) {
      const res = await fetch("/admin/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        let d = "Невірний email або пароль";
        try { d = (await res.json()).detail || d; } catch (e) {}
        throw new Error(d);
      }
      const data = await res.json();
      localStorage.setItem("mnp_admin_token", data.access_token);
      return data;
    },
    async admin(path, { method = "GET", body } = {}) {
      const token = localStorage.getItem("mnp_admin_token");
      if (!token) throw new Error("Потрібен вхід адміністратора");
      const headers = { Authorization: `Bearer ${token}` };
      if (body) headers["Content-Type"] = "application/json";
      const res = await fetch(`${BASE}${path}`, {
        method, headers, body: body ? JSON.stringify(body) : undefined,
      });
      if (res.status === 401) {
        localStorage.removeItem("mnp_admin_token");
        throw new Error("Сесію адміністратора завершено — увійдіть знову");
      }
      if (!res.ok) {
        let d = res.statusText;
        try { d = (await res.json()).detail || d; } catch (e) {}
        const err = new Error(typeof d === "string" ? d : JSON.stringify(d));
        err.status = res.status;
        throw err;
      }
      return res.status === 204 ? null : res.json();
    },
  };
})();
