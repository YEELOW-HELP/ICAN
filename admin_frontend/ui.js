import { clearSession, getSession } from "./api.js";

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function toast(message, kind = "success") {
  const el = document.createElement("div");
  el.className = `fixed bottom-6 right-6 ${kind === "success" ? "bg-emerald-600" : "bg-red-600"} text-white px-4 py-3 rounded-lg shadow-lg text-sm z-50`;
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 2800);
}

let debounceTimer;
export function debounce(fn, delay = 350) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fn, delay);
}

const ROLE_LABELS = { admin: "ADMIN", manager: "MANAGER", career_consultant: "CAREER CONSULTANT" };

export function shell(activeNav, contentHtml) {
  const session = getSession();
  const isAdmin = session?.role === "admin";
  return `
    <div class="min-h-screen flex">
      <aside class="w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div class="h-16 flex items-center gap-2 px-5 border-b border-slate-200">
          <span class="text-xl">🧭</span>
          <span class="font-semibold text-slate-900">ICAN CRM</span>
        </div>
        <nav class="flex-1 px-3 py-4 space-y-1">
          <a href="#/clients" class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${activeNav === "clients" ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}">
            <span>👥</span> Клієнти
          </a>
          <a href="#/mnp" class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${activeNav === "mnp" ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}">
            <span>🧭</span> Напрями (MNP)
          </a>
          ${isAdmin ? `
          <a href="#/staff" class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${activeNav === "staff" ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}">
            <span>🧑‍💼</span> Персонал
          </a>` : ""}
        </nav>
        <div class="p-4 border-t border-slate-200">
          <div class="text-sm font-medium text-slate-800 truncate">${esc(session?.email || "")}</div>
          <div class="text-xs text-slate-500 uppercase tracking-wide">${ROLE_LABELS[session?.role] || ""}</div>
          <button id="logout-btn" class="mt-3 w-full text-sm text-slate-600 hover:text-red-600 border border-slate-200 rounded-lg py-1.5 transition-colors">Вийти</button>
        </div>
      </aside>
      <main class="flex-1 min-w-0">${contentHtml}</main>
    </div>`;
}

export function attachShellEvents() {
  document.getElementById("logout-btn")?.addEventListener("click", () => {
    clearSession();
    window.location.hash = "#/login";
  });
}

export { ROLE_LABELS };
