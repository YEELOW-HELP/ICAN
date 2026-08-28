import { api, ApiError, getSession, isLoggedIn, setSession } from "./api.js";
import { renderClientDetail, STATUS_META } from "./clientDetail.js";
import { renderMnpClientCard, renderMnpList } from "./mnpWorkspace.js";
import { attachShellEvents, debounce, esc, fmtDate, shell, toast } from "./ui.js";

const root = document.getElementById("app");

function statusBadge(s) {
  const m = STATUS_META[s] || { label: s, badge: "bg-slate-100 text-slate-600" };
  return `<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${m.badge}">${m.label}</span>`;
}

const ROLE_LABELS = { admin: "ADMIN", manager: "MANAGER", career_consultant: "CAREER CONSULTANT" };

// ---------------- Login ----------------

function renderLogin(error) {
  root.innerHTML = `
    <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-700 via-brand-600 to-indigo-800 px-4">
      <div class="w-full max-w-sm bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-6">
          <div class="text-3xl mb-2">🧭</div>
          <h1 class="text-xl font-semibold text-slate-900">ICAN CRM</h1>
          <p class="text-sm text-slate-500 mt-1">Увійдіть, щоб керувати клієнтами</p>
        </div>
        <form id="login-form" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input name="email" type="email" required autocomplete="username"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Пароль</label>
            <input name="password" type="password" required autocomplete="current-password"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          ${error ? `<div class="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">${esc(error)}</div>` : ""}
          <button type="submit" class="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium rounded-lg py-2.5 text-sm transition-colors">
            Увійти
          </button>
        </form>
      </div>
    </div>`;

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const res = await api.login(fd.get("email"), fd.get("password"));
      setSession(res.access_token, res.email, res.role);
      navigate("#/clients");
    } catch (err) {
      renderLogin(err instanceof ApiError ? err.message : "Не вдалося увійти");
    }
  });
}

// ---------------- Clients list ----------------

let clientsState = {
  page: 1, page_size: 25, search: "", status: "", city: "",
  sort_by: "created_at", sort_dir: "desc",
};

const QUICK_FILTERS = {
  admin: [
    ["", "Усі"], ["new", "Нові"], ["waiting_consultant", "Очікують консультанта"], ["ready_for_matching", "Готові до підбору"],
  ],
  manager: [
    ["", "Усі"], ["new", "Нові клієнти"], ["screening", "Скринінг у процесі"],
  ],
  career_consultant: [
    ["", "Усі мої"], ["career_consultation", "Очікують консультацію"], ["ready_for_matching", "Готові"],
  ],
};

async function renderClientsList() {
  root.innerHTML = shell("clients", `<div class="p-8 text-slate-400">Завантаження…</div>`);
  const session = getSession();

  let summary, data;
  try {
    [summary, data] = await Promise.all([api.dashboard(), api.listClients(cleanParams(clientsState))]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return;
    root.innerHTML = shell("clients", `<div class="p-8 text-red-600">Помилка: ${esc(err.message)}</div>`);
    return;
  }

  const kpis = [
    ["Всього клієнтів", summary.total_clients],
    ["Нові сьогодні", summary.new_today],
    ["На скринінгу", summary.in_screening],
    ["Очікують консультанта", summary.waiting_consultant],
    ["На консультації", summary.in_career_consultation],
    ["Готові до підбору", summary.ready_for_matching],
  ];

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const quickFilters = QUICK_FILTERS[session.role] || QUICK_FILTERS.admin;

  root.innerHTML = shell(
    "clients",
    `
    <div class="p-8 max-w-7xl mx-auto">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-semibold text-slate-900">Клієнти</h1>
        <button id="new-client-btn" class="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg">+ Новий клієнт</button>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        ${kpis.map(([label, value]) => `
          <div class="bg-white rounded-xl border border-slate-200 p-4">
            <div class="text-2xl font-semibold text-slate-900">${value}</div>
            <div class="text-xs text-slate-500 mt-1">${label}</div>
          </div>`).join("")}
      </div>

      <div class="flex flex-wrap gap-2 mb-4">
        ${quickFilters.map(([value, label]) => `
          <button data-quick-filter="${value}" class="text-xs px-3 py-1.5 rounded-full border ${clientsState.status === value ? "bg-brand-600 text-white border-brand-600" : "border-slate-200 text-slate-600 hover:bg-slate-50"}">${label}</button>`).join("")}
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-4 mb-4">
        <div class="flex flex-wrap gap-3 items-end">
          <div class="flex-1 min-w-[220px]">
            <label class="block text-xs font-medium text-slate-500 mb-1">Пошук (ПІБ, телефон, Telegram, email, ID)</label>
            <input id="f-search" value="${esc(clientsState.search)}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Місто</label>
            <input id="f-city" value="${esc(clientsState.city)}" class="rounded-lg border border-slate-300 px-3 py-2 text-sm w-36" />
          </div>
          <button id="f-clear" class="text-sm text-slate-600 hover:text-red-600 border border-slate-200 rounded-lg px-3 py-2">Очистити</button>
        </div>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
            <tr>
              <th class="text-left px-4 py-3 font-medium">Клієнт</th>
              <th class="text-left px-4 py-3 font-medium">Телефон</th>
              <th class="text-left px-4 py-3 font-medium">Місто</th>
              <th class="text-left px-4 py-3 font-medium">Ціль</th>
              <th class="text-left px-4 py-3 font-medium">Статус</th>
              <th class="text-left px-4 py-3 font-medium">Профіль</th>
              <th class="text-left px-4 py-3 font-medium">Manager</th>
              <th class="text-left px-4 py-3 font-medium">Consultant</th>
              <th class="text-left px-4 py-3 font-medium">Next action</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            ${data.items.length === 0 ? `<tr><td colspan="9" class="text-center text-slate-400 py-10">Нічого не знайдено</td></tr>` : ""}
            ${data.items.map((c) => `
              <tr class="hover:bg-slate-50 cursor-pointer transition-colors" data-id="${c.id}">
                <td class="px-4 py-3 font-medium text-slate-800">${esc([c.first_name, c.last_name].filter(Boolean).join(" ") || "Без імені")} <span class="text-slate-400 text-xs">#${c.id}</span></td>
                <td class="px-4 py-3 text-slate-500">${esc(c.phone || "—")}</td>
                <td class="px-4 py-3 text-slate-500">${esc(c.city || "—")}</td>
                <td class="px-4 py-3 text-slate-500">${esc(c.primary_target || "—")}</td>
                <td class="px-4 py-3">${statusBadge(c.status)}</td>
                <td class="px-4 py-3 w-28">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden"><div class="h-full bg-brand-500" style="width:${c.profile_completion}%"></div></div>
                    <span class="text-xs text-slate-500">${c.profile_completion}%</span>
                  </div>
                </td>
                <td class="px-4 py-3 text-slate-500">${esc(c.manager_name || "—")}</td>
                <td class="px-4 py-3 text-slate-500">${esc(c.consultant_name || "—")}</td>
                <td class="px-4 py-3 text-slate-500 text-xs">${c.next_action_type ? esc(c.next_action_type) + (c.next_action_due_at ? " · " + fmtDate(c.next_action_due_at) : "") : "—"}</td>
              </tr>`).join("")}
          </tbody>
        </table>
        </div>
        <div class="flex items-center justify-between px-4 py-3 border-t border-slate-200 text-sm text-slate-500">
          <div>Всього: ${data.total}</div>
          <div class="flex items-center gap-2">
            <button id="page-prev" ${data.page <= 1 ? "disabled" : ""} class="px-3 py-1.5 rounded-lg border border-slate-200 disabled:opacity-40">←</button>
            <span>Сторінка ${data.page} з ${totalPages}</span>
            <button id="page-next" ${data.page >= totalPages ? "disabled" : ""} class="px-3 py-1.5 rounded-lg border border-slate-200 disabled:opacity-40">→</button>
          </div>
        </div>
      </div>
    </div>`
  );

  attachShellEvents();

  root.querySelectorAll("tbody tr[data-id]").forEach((row) => {
    row.addEventListener("click", () => navigate(`#/clients/${row.dataset.id}`));
  });

  root.querySelectorAll("[data-quick-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      clientsState.status = btn.dataset.quickFilter;
      clientsState.page = 1;
      renderClientsList();
    });
  });

  document.getElementById("f-search").addEventListener("input", (e) => {
    clientsState.search = e.target.value; clientsState.page = 1; debounce(renderClientsList);
  });
  document.getElementById("f-city").addEventListener("input", (e) => {
    clientsState.city = e.target.value; clientsState.page = 1; debounce(renderClientsList);
  });
  document.getElementById("f-clear").addEventListener("click", () => {
    clientsState = { page: 1, page_size: 25, search: "", status: "", city: "", sort_by: "created_at", sort_dir: "desc" };
    renderClientsList();
  });
  document.getElementById("page-prev").addEventListener("click", () => { clientsState.page--; renderClientsList(); });
  document.getElementById("page-next").addEventListener("click", () => { clientsState.page++; renderClientsList(); });

  document.getElementById("new-client-btn").addEventListener("click", () => openNewClientModal());
}

function cleanParams(state) {
  const out = {};
  for (const [k, v] of Object.entries(state)) if (v !== "" && v !== null && v !== undefined) out[k] = v;
  return out;
}

function openNewClientModal() {
  const overlay = document.createElement("div");
  overlay.className = "fixed inset-0 bg-black/40 flex items-center justify-center z-50";
  overlay.innerHTML = `
    <div class="bg-white rounded-xl p-6 w-full max-w-md">
      <h2 class="text-lg font-semibold text-slate-900 mb-4">Новий клієнт</h2>
      <div class="space-y-3">
        <input id="nc-first" placeholder="Ім'я" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input id="nc-last" placeholder="Прізвище" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input id="nc-phone" placeholder="Телефон" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input id="nc-city" placeholder="Місто" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select id="nc-source" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="phone">Телефонний дзвінок</option>
          <option value="manager">Вручну (менеджер)</option>
          <option value="website">Сайт</option>
          <option value="app">Застосунок</option>
        </select>
      </div>
      <div class="flex justify-end gap-2 mt-5">
        <button id="nc-cancel" class="text-sm border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50">Скасувати</button>
        <button id="nc-save" class="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg">Створити</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector("#nc-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#nc-save").addEventListener("click", async () => {
    const payload = {
      first_name: overlay.querySelector("#nc-first").value.trim() || null,
      last_name: overlay.querySelector("#nc-last").value.trim() || null,
      phone: overlay.querySelector("#nc-phone").value.trim() || null,
      city: overlay.querySelector("#nc-city").value.trim() || null,
      source_channel: overlay.querySelector("#nc-source").value,
    };
    try {
      const client = await api.createClient(payload);
      overlay.remove();
      navigate(`#/clients/${client.id}`);
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

// ---------------- Staff (ADMIN only) ----------------

async function renderStaff() {
  root.innerHTML = shell("staff", `<div class="p-8 text-slate-400">Завантаження…</div>`);
  let staff;
  try {
    staff = await api.listStaff();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return;
    root.innerHTML = shell("staff", `<div class="p-8 text-red-600">Помилка: ${esc(err.message)}</div>`);
    return;
  }

  root.innerHTML = shell(
    "staff",
    `
    <div class="p-8 max-w-4xl mx-auto">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-semibold text-slate-900">Персонал</h1>
        <button id="new-staff-btn" class="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg">+ Новий акаунт</button>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-500 text-xs uppercase">
            <tr><th class="text-left px-4 py-3">Ім'я</th><th class="text-left px-4 py-3">Email</th><th class="text-left px-4 py-3">Роль</th><th class="text-left px-4 py-3">Статус</th><th class="px-4 py-3"></th></tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            ${staff.map((s) => `
              <tr>
                <td class="px-4 py-3 text-slate-800">${esc(s.full_name || "—")}</td>
                <td class="px-4 py-3 text-slate-500">${esc(s.email)}</td>
                <td class="px-4 py-3 text-slate-500">${ROLE_LABELS[s.role] || s.role}</td>
                <td class="px-4 py-3">${s.is_active ? '<span class="text-emerald-600 text-xs">Активний</span>' : '<span class="text-red-500 text-xs">Деактивовано</span>'}</td>
                <td class="px-4 py-3 text-right">
                  <button data-toggle-staff="${s.id}" data-active="${s.is_active}" class="text-xs text-brand-600 hover:underline">${s.is_active ? "Деактивувати" : "Активувати"}</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>`
  );

  attachShellEvents();

  document.getElementById("new-staff-btn").addEventListener("click", () => openNewStaffModal());
  root.querySelectorAll("[data-toggle-staff]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api.updateStaff(btn.dataset.toggleStaff, { is_active: btn.dataset.active !== "true" });
        renderStaff();
      } catch (err) { toast(err.message, "error"); }
    });
  });
}

function openNewStaffModal() {
  const overlay = document.createElement("div");
  overlay.className = "fixed inset-0 bg-black/40 flex items-center justify-center z-50";
  overlay.innerHTML = `
    <div class="bg-white rounded-xl p-6 w-full max-w-md">
      <h2 class="text-lg font-semibold text-slate-900 mb-4">Новий акаунт</h2>
      <div class="space-y-3">
        <input id="ns-name" placeholder="Ім'я" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input id="ns-email" type="email" placeholder="Email" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input id="ns-password" type="password" placeholder="Пароль" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select id="ns-role" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="manager">MANAGER</option>
          <option value="career_consultant">CAREER CONSULTANT</option>
          <option value="admin">ADMIN</option>
        </select>
      </div>
      <div class="flex justify-end gap-2 mt-5">
        <button id="ns-cancel" class="text-sm border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50">Скасувати</button>
        <button id="ns-save" class="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg">Створити</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector("#ns-cancel").addEventListener("click", () => overlay.remove());
  overlay.querySelector("#ns-save").addEventListener("click", async () => {
    try {
      await api.createStaff({
        full_name: overlay.querySelector("#ns-name").value.trim() || null,
        email: overlay.querySelector("#ns-email").value.trim(),
        password: overlay.querySelector("#ns-password").value,
        role: overlay.querySelector("#ns-role").value,
      });
      overlay.remove();
      renderStaff();
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

// ---------------- Router ----------------

function navigate(hash) {
  window.location.hash = hash;
}

function route() {
  const hash = window.location.hash || "#/login";

  if (!isLoggedIn() && hash !== "#/login") {
    navigate("#/login");
    return;
  }

  if (hash === "#/login") {
    if (isLoggedIn()) { navigate("#/clients"); return; }
    renderLogin();
    return;
  }

  const detailMatch = hash.match(/^#\/clients\/(\d+)$/);
  if (detailMatch) {
    renderClientDetail(root, detailMatch[1], navigate);
    return;
  }

  const mnpDetailMatch = hash.match(/^#\/mnp\/([0-9a-fA-F-]{36})$/);
  if (mnpDetailMatch) {
    renderMnpClientCard(root, mnpDetailMatch[1], navigate);
    return;
  }

  if (hash === "#/mnp" || hash.startsWith("#/mnp?")) {
    renderMnpList(root, navigate);
    return;
  }

  if (hash === "#/staff") {
    if (getSession()?.role !== "admin") { navigate("#/clients"); return; }
    renderStaff();
    return;
  }

  if (hash.startsWith("#/clients")) {
    renderClientsList();
    return;
  }

  navigate("#/clients");
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);
