// Thin fetch wrapper for the MNP V1 API (MNP_API_CONTRACTS_V1). No
// framework -- matches admin_frontend's own plain-JS convention.

const MnpApi = (() => {
  const BASE = "/v1/mnp";

  function getUserId() {
    return localStorage.getItem("mnp_user_id");
  }

  function setUserId(id) {
    localStorage.setItem("mnp_user_id", id);
  }

  async function ensureSession() {
    if (getUserId()) return getUserId();
    const res = await fetch(`${BASE}/session`, { method: "POST" });
    const data = await res.json();
    setUserId(data.user_id);
    return data.user_id;
  }

  async function request(path, { method = "GET", body, isForm = false } = {}) {
    const userId = await ensureSession();
    const headers = { "X-Mnp-User-Id": userId };
    let payload = body;
    if (body && !isForm) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
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
  };
})();
