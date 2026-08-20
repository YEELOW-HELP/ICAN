import { api, ApiError, getSession } from "./api.js";
import { collectProfileChanges, renderProfileBlocks, wireFieldEditEvents } from "./fields.js";
import { attachShellEvents, esc, fmtDate, shell, toast } from "./ui.js";

export const STATUS_META = {
  new: { label: "Новий клієнт", badge: "bg-slate-100 text-slate-600" },
  screening: { label: "Первинний скринінг", badge: "bg-blue-100 text-blue-700" },
  waiting_consultant: { label: "Очікує консультанта", badge: "bg-amber-100 text-amber-700" },
  career_consultation: { label: "Кар'єрна консультація", badge: "bg-purple-100 text-purple-700" },
  ready_for_matching: { label: "Готовий до підбору", badge: "bg-emerald-100 text-emerald-700" },
  in_work: { label: "У роботі", badge: "bg-cyan-100 text-cyan-700" },
  paused: { label: "Призупинено", badge: "bg-orange-100 text-orange-700" },
  closed: { label: "Закрито", badge: "bg-red-100 text-red-700" },
};

const PRIORITY_META = {
  normal: { label: "Normal", badge: "bg-slate-100 text-slate-600" },
  high: { label: "High", badge: "bg-amber-100 text-amber-700" },
  urgent: { label: "Urgent", badge: "bg-red-100 text-red-700" },
};

function statusBadge(s) {
  const m = STATUS_META[s] || { label: s, badge: "bg-slate-100" };
  return `<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${m.badge}">${m.label}</span>`;
}

function priorityBadge(p) {
  const m = PRIORITY_META[p] || PRIORITY_META.normal;
  return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${m.badge}">${m.label}</span>`;
}

let activeTab = "overview";

export async function renderClientDetail(root, clientId, navigate) {
  root.innerHTML = `<div class="p-8 text-slate-400">Завантаження…</div>`;

  let clientData, files, tasks;
  try {
    [clientData, files, tasks] = await Promise.all([
      api.getClient(clientId),
      api.listFiles(clientId),
      api.listTasks(clientId),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return;
    root.innerHTML = `<div class="p-8 text-red-600">Помилка: ${esc(err.message)}</div>`;
    return;
  }

  const session = getSession();
  const fullName = [clientData.first_name, clientData.last_name].filter(Boolean).join(" ") || "Без імені";
  const pendingTask = tasks.find((t) => t.status === "pending");

  root.innerHTML = shell("clients", `
    <div class="max-w-6xl mx-auto p-6">
      <a href="#/clients" class="text-sm text-slate-500 hover:text-brand-600">← До списку клієнтів</a>

      <div class="bg-white rounded-xl border border-slate-200 p-6 mt-3 mb-5 sticky top-4 z-10 shadow-sm">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-xl font-semibold text-slate-900">${esc(fullName)}</h1>
              ${statusBadge(clientData.status)}
              ${priorityBadge(clientData.priority)}
            </div>
            <div class="flex flex-wrap items-center gap-3 mt-2 text-sm text-slate-500">
              ${clientData.phone ? `<button data-copy="${esc(clientData.phone)}" class="copy-btn hover:text-brand-600">📱 ${esc(clientData.phone)}</button>` : ""}
              ${clientData.telegram_username ? `<button data-copy="@${esc(clientData.telegram_username)}" class="copy-btn hover:text-brand-600">✈ @${esc(clientData.telegram_username)}</button>` : ""}
              <span>Manager: ${esc(clientData.manager_name || "не призначено")}</span>
              <span>Consultant: ${esc(clientData.consultant_name || "не призначено")}</span>
            </div>
            ${pendingTask ? `<div class="mt-2 text-xs text-amber-700 bg-amber-50 inline-block px-2 py-1 rounded-lg">Наступна дія: ${esc(pendingTask.task_type)}${pendingTask.due_at ? " — " + fmtDate(pendingTask.due_at) : ""}</div>` : ""}
          </div>
          <div class="flex flex-col items-end gap-2">
            <div class="flex gap-2">
              <button id="btn-log-call" class="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">📞 Записати дзвінок</button>
              <button id="btn-actions" class="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">⋯ Дії</button>
            </div>
            <div id="actions-menu" class="hidden bg-white border border-slate-200 rounded-lg shadow-lg text-sm overflow-hidden w-56"></div>
          </div>
        </div>
        <div class="mt-4">
          <div class="flex items-center gap-2 text-xs text-slate-500 mb-1">
            <span>Заповнення профілю</span><span class="font-medium text-slate-700">${clientData.profile_completion}%</span>
          </div>
          <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden"><div class="h-full bg-brand-500" style="width:${clientData.profile_completion}%"></div></div>
        </div>
      </div>

      <div class="border-b border-slate-200 mb-5">
        <nav class="flex gap-6 text-sm overflow-x-auto">
          ${tabBtn("overview", "Огляд")}
          ${tabBtn("profile", "Профіль")}
          ${tabBtn("screening", "Скринінг / консультація")}
          ${tabBtn("calls", "Дзвінки")}
          ${tabBtn("files", "Файли")}
          ${tabBtn("history", "Історія")}
        </nav>
      </div>

      <div id="tab-content"></div>
    </div>`);

  attachShellEvents();

  // Copy buttons
  root.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      navigator.clipboard?.writeText(btn.dataset.copy);
      toast("Скопійовано");
    });
  });

  // Actions menu
  const actionsBtn = document.getElementById("btn-actions");
  const actionsMenu = document.getElementById("actions-menu");
  actionsMenu.innerHTML = await buildActionsMenu(clientData, session);
  actionsBtn.addEventListener("click", () => actionsMenu.classList.toggle("hidden"));
  wireActionsMenu(actionsMenu, clientId, clientData, () => renderClientDetail(root, clientId, navigate));

  document.getElementById("btn-log-call").addEventListener("click", () => {
    activeTab = "calls";
    renderClientDetail(root, clientId, navigate);
  });

  root.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => { activeTab = btn.dataset.tab; renderClientDetail(root, clientId, navigate); });
  });

  const tabContent = document.getElementById("tab-content");
  if (activeTab === "overview") tabContent.innerHTML = overviewTabHtml(clientData, tasks);
  else if (activeTab === "profile") { tabContent.innerHTML = await profileTabHtml(clientData); wireProfileTab(tabContent, clientId, () => renderClientDetail(root, clientId, navigate)); }
  else if (activeTab === "screening") { tabContent.innerHTML = await screeningTabHtml(clientId, clientData); wireScreeningTab(tabContent, clientId, () => renderClientDetail(root, clientId, navigate)); }
  else if (activeTab === "calls") { tabContent.innerHTML = await callsTabHtml(clientId); wireCallsTab(tabContent, clientId, () => renderClientDetail(root, clientId, navigate)); }
  else if (activeTab === "files") { tabContent.innerHTML = filesTabHtml(files); wireFilesTab(tabContent, clientId, () => renderClientDetail(root, clientId, navigate)); }
  else if (activeTab === "history") tabContent.innerHTML = await historyTabHtml(clientId);
}

function tabBtn(key, label) {
  const active = activeTab === key;
  return `<button data-tab="${key}" class="tab-btn pb-3 border-b-2 font-medium whitespace-nowrap transition-colors ${active ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700"}">${label}</button>`;
}

// ---------------- Actions menu ----------------

async function buildActionsMenu(clientData, session) {
  const items = [];
  if (session.role === "admin") {
    items.push(`<button data-action="assign-manager" class="w-full text-left px-4 py-2 hover:bg-slate-50">Призначити Manager</button>`);
    items.push(`<button data-action="assign-consultant" class="w-full text-left px-4 py-2 hover:bg-slate-50">Призначити Career Consultant</button>`);
  }
  items.push(`<button data-action="add-task" class="w-full text-left px-4 py-2 hover:bg-slate-50">Додати задачу (Next Action)</button>`);
  if (session.role === "admin") {
    items.push(`<div class="border-t border-slate-100"></div>`);
    for (const s of ["paused", "closed", "in_work"]) {
      items.push(`<button data-action="status" data-status="${s}" class="w-full text-left px-4 py-2 hover:bg-slate-50">Статус: ${STATUS_META[s].label}</button>`);
    }
  }
  return items.join("");
}

function wireActionsMenu(menu, clientId, clientData, reload) {
  menu.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      menu.classList.add("hidden");
      const action = btn.dataset.action;
      try {
        if (action === "assign-manager" || action === "assign-consultant") {
          const role = action === "assign-manager" ? "manager" : "career_consultant";
          const staff = await api.assignableStaff(role);
          if (!staff.length) return toast(`Немає активних ${role}`, "error");
          const choice = prompt(`Оберіть ${role === "manager" ? "менеджера" : "консультанта"}:\n` + staff.map((s, i) => `${i + 1}. ${s.full_name || s.email}`).join("\n"));
          const idx = parseInt(choice, 10) - 1;
          if (Number.isNaN(idx) || !staff[idx]) return;
          if (action === "assign-manager") await api.assignManager(clientId, staff[idx].id);
          else await api.assignConsultant(clientId, staff[idx].id);
          toast("Призначено");
          reload();
        } else if (action === "status") {
          await api.setStatus(clientId, btn.dataset.status);
          toast("Статус змінено");
          reload();
        } else if (action === "add-task") {
          const note = prompt("Опис задачі (наступна дія):");
          if (note === null) return;
          await api.createTask(clientId, { task_type: "other", note });
          toast("Задачу додано");
          reload();
        }
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });
}

// ---------------- Overview ----------------

function overviewTabHtml(c, tasks) {
  const p = c.profile;
  const pending = tasks.filter((t) => t.status === "pending");
  return `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="font-medium text-slate-800 mb-3">Ключовий профіль</h3>
        <dl class="space-y-2 text-sm">
          ${row("Цільова професія", p.primary_target)}
          ${row("Навички", "дивись вкладку Профіль")}
          ${row("Зарплата", p.min_salary ? `${p.min_salary}${p.salary_currency ? " " + p.salary_currency : ""}` : null)}
          ${row("Формат / графік", [p.work_formats?.join(", "), p.schedules?.join(", ")].filter(Boolean).join(" / "))}
          ${row("Географія", (p.work_cities || []).join(", "))}
        </dl>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="font-medium text-slate-800 mb-3">Поточна ситуація</h3>
        <dl class="space-y-2 text-sm">
          ${row("Працює зараз", p.currently_employed === null ? null : (p.currently_employed ? "Так" : "Ні"))}
          ${row("Поточна посада", p.current_position)}
          ${row("Причина пошуку", (p.search_reasons || []).join(", "))}
          ${row("Готовність вийти", p.readiness_to_start)}
        </dl>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5 md:col-span-2">
        <h3 class="font-medium text-slate-800 mb-3">Незавершені задачі (${pending.length})</h3>
        ${pending.length ? `<ul class="space-y-1.5 text-sm">${pending.map((t) => `<li>• ${esc(t.task_type)}${t.note ? " — " + esc(t.note) : ""}${t.due_at ? ` <span class="text-slate-400">(${fmtDate(t.due_at)})</span>` : ""}</li>`).join("")}</ul>` : `<div class="text-sm text-slate-400">Немає</div>`}
      </div>
    </div>`;
}

function row(label, value) {
  return `<div class="flex justify-between gap-4"><dt class="text-slate-500">${label}</dt><dd class="text-slate-800 text-right">${value ? esc(value) : '<span class="text-slate-400">Не вказано</span>'}</dd></div>`;
}

// ---------------- Profile tab ----------------

async function profileTabHtml(c) {
  const contactFields = [
    ["first_name", "Ім'я"], ["last_name", "Прізвище"], ["phone", "Телефон"], ["telegram_username", "Telegram"],
    ["email", "Email"], ["birth_date", "Дата народження"], ["country", "Країна"], ["city", "Місто"],
  ];
  return `
    <div class="space-y-5">
      <details class="bg-white rounded-xl border border-slate-200 overflow-hidden" open>
        <summary class="cursor-pointer select-none px-5 py-3 font-medium text-slate-800 bg-slate-50 hover:bg-slate-100">Контакти</summary>
        <div class="p-5 grid grid-cols-1 md:grid-cols-2 gap-4" id="contact-grid">
          ${contactFields.map(([key, label]) => `
            <div>
              <label class="block text-xs font-medium text-slate-500 mb-1">${label}</label>
              <input data-contact-field="${key}" value="${esc(c[key] ?? "")}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            </div>`).join("")}
        </div>
      </details>

      ${renderProfileBlocks(c.profile, true)}

      <div class="flex justify-end">
        <button id="save-profile-btn" class="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg">Зберегти профіль</button>
      </div>

      ${repeatableSection("Досвід роботи (${count})".replace("${count}", c.work_experiences.length), "work-exp-list", c.work_experiences.map(workExpRow).join("") || emptyRow(), "add-work-exp", "+ Додати місце роботи")}
      ${repeatableSection(`Навички (${c.skills.length})`, "skills-list", c.skills.map(skillRow).join("") || emptyRow(), "add-skill", "+ Додати навичку")}
      ${repeatableSection(`Мови (${c.languages.length})`, "langs-list", c.languages.map(langRow).join("") || emptyRow(), "add-lang", "+ Додати мову")}
    </div>`;
}

function emptyRow() {
  return `<div class="text-sm text-slate-400 px-5 py-3">Немає записів</div>`;
}

function repeatableSection(title, listId, rowsHtml, addBtnId, addLabel) {
  return `
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div class="flex items-center justify-between px-5 py-3 bg-slate-50">
        <h3 class="font-medium text-slate-800">${title}</h3>
        <button id="${addBtnId}" class="text-xs text-brand-600 hover:underline">${addLabel}</button>
      </div>
      <div id="${listId}" class="divide-y divide-slate-100">${rowsHtml}</div>
    </div>`;
}

function workExpRow(w) {
  return `
    <div class="px-5 py-3 flex items-start justify-between gap-3" data-we-id="${w.id}">
      <div class="text-sm">
        <div class="font-medium text-slate-800">${esc(w.position || "(без посади)")} ${w.company ? "— " + esc(w.company) : ""}</div>
        <div class="text-slate-500 text-xs">${esc(w.start_month_year || "?")} – ${esc(w.end_month_year || "дотепер")}</div>
        ${w.responsibilities ? `<div class="text-slate-600 text-xs mt-1">${esc(w.responsibilities)}</div>` : ""}
      </div>
      <button data-del-we="${w.id}" class="text-xs text-red-500 hover:underline shrink-0">Видалити</button>
    </div>`;
}

function skillRow(s) {
  return `
    <div class="px-5 py-2.5 flex items-center justify-between gap-3" data-skill-id="${s.id}">
      <div class="text-sm text-slate-800">${esc(s.skill_name)} ${s.level ? `<span class="text-xs text-slate-400">(${esc(s.level)})</span>` : ""}</div>
      <button data-del-skill="${s.id}" class="text-xs text-red-500 hover:underline">Видалити</button>
    </div>`;
}

function langRow(l) {
  return `
    <div class="px-5 py-2.5 flex items-center justify-between gap-3" data-lang-id="${l.id}">
      <div class="text-sm text-slate-800">${esc(l.language)} ${l.level ? `<span class="text-xs text-slate-400">(${esc(l.level)})</span>` : ""}</div>
      <button data-del-lang="${l.id}" class="text-xs text-red-500 hover:underline">Видалити</button>
    </div>`;
}

function wireProfileTab(container, clientId, reload) {
  wireFieldEditEvents(container);

  document.getElementById("save-profile-btn").addEventListener("click", async () => {
    try {
      const contactChanges = {};
      container.querySelectorAll("[data-contact-field]").forEach((el) => {
        contactChanges[el.dataset.contactField] = el.value.trim() || null;
      });
      const profileChanges = collectProfileChanges(container);
      await api.updateClient(clientId, contactChanges);
      await api.updateClientProfile(clientId, profileChanges);
      toast("Профіль збережено");
      reload();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  document.getElementById("add-work-exp").addEventListener("click", async () => {
    const position = prompt("Посада:");
    if (!position) return;
    const company = prompt("Компанія (необов'язково):") || null;
    try {
      await api.addWorkExperience(clientId, { position, company });
      toast("Додано");
      reload();
    } catch (err) { toast(err.message, "error"); }
  });
  container.querySelectorAll("[data-del-we]").forEach((btn) => btn.addEventListener("click", async () => {
    try { await api.deleteWorkExperience(clientId, btn.dataset.delWe); reload(); } catch (err) { toast(err.message, "error"); }
  }));

  document.getElementById("add-skill").addEventListener("click", async () => {
    const skill_name = prompt("Назва навички:");
    if (!skill_name) return;
    try { await api.addSkill(clientId, { skill_name }); toast("Додано"); reload(); } catch (err) { toast(err.message, "error"); }
  });
  container.querySelectorAll("[data-del-skill]").forEach((btn) => btn.addEventListener("click", async () => {
    try { await api.deleteSkill(clientId, btn.dataset.delSkill); reload(); } catch (err) { toast(err.message, "error"); }
  }));

  document.getElementById("add-lang").addEventListener("click", async () => {
    const language = prompt("Мова:");
    if (!language) return;
    const level = prompt("Рівень (A1-C2 / Native / Не знаю):") || null;
    try { await api.addLanguage(clientId, { language, level }); toast("Додано"); reload(); } catch (err) { toast(err.message, "error"); }
  });
  container.querySelectorAll("[data-del-lang]").forEach((btn) => btn.addEventListener("click", async () => {
    try { await api.deleteLanguage(clientId, btn.dataset.delLang); reload(); } catch (err) { toast(err.message, "error"); }
  }));
}

// ---------------- Screening / consultation tab ----------------

async function screeningTabHtml(clientId, c) {
  const consultation = await api.getConsultation(clientId);
  return `
    <div class="space-y-5">
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-medium text-slate-800">Первинний скринінг</h3>
          <button id="complete-screening-btn" class="text-sm bg-slate-800 hover:bg-slate-900 text-white px-3 py-1.5 rounded-lg">Завершити скринінг</button>
        </div>
        <p class="text-sm text-slate-500">Переносить клієнта на етап «Очікує консультанта», якщо всі обов'язкові поля скринінгу заповнені.</p>
        <div id="screening-result" class="mt-3 text-sm"></div>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="font-medium text-slate-800 mb-3">Кар'єрна консультація</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4" id="consultation-grid">
          <div class="md:col-span-2">
            <label class="block text-xs font-medium text-slate-500 mb-1">Primary Career Target</label>
            <input data-c-field="primary_target" value="${esc(consultation.primary_target ?? "")}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Alternative Targets (через кому)</label>
            <input data-c-field="alternative_targets" data-c-type="taglist" value="${esc((consultation.alternative_targets || []).join(", "))}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Сильні сторони (через кому)</label>
            <input data-c-field="strengths" data-c-type="taglist" value="${esc((consultation.strengths || []).join(", "))}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Skills gaps (через кому)</label>
            <input data-c-field="skills_gaps" data-c-type="taglist" value="${esc((consultation.skills_gaps || []).join(", "))}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">Реалістичність очікувань</label>
            <select data-c-field="expectations_realistic" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="">—</option>
              <option value="Реалістичні" ${consultation.expectations_realistic === "Реалістичні" ? "selected" : ""}>Реалістичні</option>
              <option value="Потребують корекції" ${consultation.expectations_realistic === "Потребують корекції" ? "selected" : ""}>Потребують корекції</option>
            </select>
          </div>
          <div class="md:col-span-2">
            <label class="block text-xs font-medium text-slate-500 mb-1">Search Strategy</label>
            <textarea data-c-field="search_strategy" rows="2" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">${esc(consultation.search_strategy ?? "")}</textarea>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-3">
          <button id="save-consultation-draft" class="text-sm border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50">Зберегти чернетку</button>
        </div>

        <div class="border-t border-slate-100 mt-4 pt-4">
          <label class="block text-xs font-medium text-slate-500 mb-1">Career Consultant Conclusion ${consultation.completed_at ? "✅" : ""}</label>
          <textarea id="conclusion-input" rows="3" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Фінальний професійний висновок...">${esc(consultation.conclusion ?? "")}</textarea>
          <div class="flex justify-end mt-2">
            <button id="complete-consultation-btn" class="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg">Завершити консультацію</button>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <div class="flex items-center justify-between">
          <h3 class="font-medium text-slate-800">Готовність до підбору</h3>
          <button id="ready-for-matching-btn" class="text-sm bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-lg">✅ Готовий до підбору</button>
        </div>
        <div id="ready-result" class="mt-3 text-sm"></div>
      </div>
    </div>`;
}

function wireScreeningTab(container, clientId, reload) {
  document.getElementById("complete-screening-btn").addEventListener("click", async () => {
    try {
      const res = await api.completeScreening(clientId);
      renderReadiness(document.getElementById("screening-result"), res);
      if (res.ready) { toast("Скринінг завершено"); reload(); }
    } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("save-consultation-draft").addEventListener("click", async () => {
    const data = {};
    container.querySelectorAll("[data-c-field]").forEach((el) => {
      if (el.dataset.cType === "taglist") {
        data[el.dataset.cField] = el.value.trim() ? el.value.split(",").map((s) => s.trim()).filter(Boolean) : [];
      } else {
        data[el.dataset.cField] = el.value.trim() || null;
      }
    });
    try { await api.saveConsultationDraft(clientId, data); toast("Чернетку збережено"); } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("complete-consultation-btn").addEventListener("click", async () => {
    const conclusion = document.getElementById("conclusion-input").value.trim();
    if (!conclusion) return toast("Заповніть висновок", "error");
    try { await api.completeConsultation(clientId, conclusion); toast("Консультацію завершено"); reload(); } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("ready-for-matching-btn").addEventListener("click", async () => {
    try {
      const res = await api.readyForMatching(clientId);
      renderReadiness(document.getElementById("ready-result"), res);
      if (res.ready) { toast("Клієнт готовий до підбору! 🎉"); reload(); }
    } catch (err) { toast(err.message, "error"); }
  });
}

function renderReadiness(el, res) {
  if (res.ready) {
    el.innerHTML = `<div class="text-emerald-600">Готово ✅</div>`;
  } else {
    el.innerHTML = `<div class="text-amber-700">Бракує: ${res.missing.map(esc).join(", ")}</div>`;
  }
}

// ---------------- Calls tab ----------------

async function callsTabHtml(clientId) {
  const calls = await api.listCalls(clientId);
  return `
    <div class="bg-white rounded-xl border border-slate-200 p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-medium text-slate-800">Дзвінки (${calls.length})</h3>
        <button id="log-call-btn" class="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg">+ Записати дзвінок</button>
      </div>
      <div id="call-form" class="hidden bg-slate-50 rounded-lg p-4 mb-4 grid grid-cols-2 gap-3">
        <select id="call-direction" class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="outgoing">Вихідний</option>
          <option value="incoming">Вхідний</option>
          <option value="missed">Пропущений</option>
        </select>
        <select id="call-status" class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="answered">Відповів</option>
          <option value="missed">Пропущено</option>
          <option value="failed">Не вдалося</option>
        </select>
        <input id="call-duration" type="number" placeholder="Тривалість (сек)" class="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select id="call-contact-type" class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="">Тип контакту —</option>
          <option value="Screening">Screening</option>
          <option value="Career Consultation">Career Consultation</option>
          <option value="Follow-up">Follow-up</option>
        </select>
        <textarea id="call-note" placeholder="Нотатка" class="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"></textarea>
        <div class="col-span-2 flex justify-end">
          <button id="save-call-btn" class="text-sm bg-slate-800 hover:bg-slate-900 text-white px-3 py-1.5 rounded-lg">Зберегти</button>
        </div>
      </div>
      <div class="divide-y divide-slate-100">
        ${calls.length ? calls.map((c) => `
          <div class="py-3 flex items-start justify-between gap-3">
            <div class="text-sm">
              <div class="font-medium text-slate-800">${esc(c.direction)} · ${esc(c.status)} ${c.duration_seconds ? `· ${c.duration_seconds}с` : ""}</div>
              <div class="text-slate-500 text-xs">${esc(c.employee_name || "")} ${c.contact_type ? "· " + esc(c.contact_type) : ""} · ${fmtDate(c.started_at)}</div>
              ${c.note ? `<div class="text-slate-600 text-xs mt-1">${esc(c.note)}</div>` : ""}
              ${c.recording_url ? `<a href="${esc(c.recording_url)}" target="_blank" class="text-xs text-brand-600 hover:underline">▶ Прослухати</a>` : ""}
            </div>
          </div>`).join("") : `<div class="text-sm text-slate-400 py-4">Дзвінків ще не було</div>`}
      </div>
    </div>`;
}

function wireCallsTab(container, clientId, reload) {
  const form = document.getElementById("call-form");
  document.getElementById("log-call-btn").addEventListener("click", () => form.classList.toggle("hidden"));
  document.getElementById("save-call-btn").addEventListener("click", async () => {
    const data = {
      direction: document.getElementById("call-direction").value,
      status: document.getElementById("call-status").value,
      duration_seconds: document.getElementById("call-duration").value ? Number(document.getElementById("call-duration").value) : null,
      contact_type: document.getElementById("call-contact-type").value || null,
      note: document.getElementById("call-note").value.trim() || null,
    };
    try { await api.logCall(clientId, data); toast("Дзвінок записано"); reload(); } catch (err) { toast(err.message, "error"); }
  });
}

// ---------------- Files tab ----------------

function filesTabHtml(files) {
  return `
    <div class="bg-white rounded-xl border border-slate-200 p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-medium text-slate-800">Файли (${files.length})</h3>
      </div>
      <div class="bg-slate-50 rounded-lg p-4 mb-4 flex flex-wrap gap-3 items-end">
        <select id="file-type" class="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="cv">CV</option>
          <option value="cover_letter">Cover Letter</option>
          <option value="certificate">Certificate</option>
          <option value="diploma">Diploma</option>
          <option value="portfolio">Portfolio</option>
          <option value="other">Other</option>
        </select>
        <input id="file-desc" placeholder="Опис (для Other)" class="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input id="file-input" type="file" class="text-sm" />
        <button id="upload-file-btn" class="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg">Завантажити</button>
      </div>
      <div class="divide-y divide-slate-100">
        ${files.length ? files.map((f) => `
          <div class="py-3 flex items-center justify-between gap-3" data-file-id="${f.id}">
            <div class="text-sm">
              <div class="font-medium text-slate-800">${esc(f.filename)} ${f.is_current_cv ? '<span class="text-xs text-emerald-600">(Current CV)</span>' : ""}</div>
              <div class="text-slate-500 text-xs">${esc(f.file_type)}${f.other_description ? " — " + esc(f.other_description) : ""} · ${((f.size_bytes || 0) / 1024).toFixed(0)} KB · ${esc(f.uploaded_by_name || "")} · ${fmtDate(f.uploaded_at)}</div>
            </div>
            <div class="flex gap-3 text-xs shrink-0">
              <button data-dl="${f.id}" class="text-brand-600 hover:underline">Завантажити</button>
              ${f.file_type === "cv" && !f.is_current_cv ? `<button data-cv="${f.id}" class="text-slate-500 hover:underline">Current CV</button>` : ""}
              <button data-del-file="${f.id}" class="text-red-500 hover:underline">Видалити</button>
            </div>
          </div>`).join("") : `<div class="text-sm text-slate-400 py-4">Файлів ще немає</div>`}
      </div>
    </div>`;
}

function wireFilesTab(container, clientId, reload) {
  document.getElementById("upload-file-btn").addEventListener("click", async () => {
    const input = document.getElementById("file-input");
    if (!input.files.length) return toast("Оберіть файл", "error");
    try {
      await api.uploadFile(clientId, document.getElementById("file-type").value, document.getElementById("file-desc").value.trim() || null, input.files[0]);
      toast("Файл завантажено");
      reload();
    } catch (err) { toast(err.message, "error"); }
  });

  container.querySelectorAll("[data-dl]").forEach((btn) => btn.addEventListener("click", async () => {
    try {
      const { blob, filename } = await api.downloadFile(clientId, btn.dataset.dl);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { toast(err.message, "error"); }
  }));
  container.querySelectorAll("[data-cv]").forEach((btn) => btn.addEventListener("click", async () => {
    try { await api.markCurrentCv(clientId, btn.dataset.cv); reload(); } catch (err) { toast(err.message, "error"); }
  }));
  container.querySelectorAll("[data-del-file]").forEach((btn) => btn.addEventListener("click", async () => {
    try { await api.deleteFile(clientId, btn.dataset.delFile); reload(); } catch (err) { toast(err.message, "error"); }
  }));
}

// ---------------- History tab ----------------

const EVENT_ICONS = {
  created: "🆕", status_changed: "🔄", assigned: "👤", call: "📞", file_uploaded: "📎",
  file_deleted: "🗑", profile_field_changed: "✏️", screening_completed: "✅",
  consultation_completed: "🎓", ready_for_matching: "🎯", note: "📝",
};

async function historyTabHtml(clientId) {
  const events = await api.getTimeline(clientId);
  return `
    <div class="bg-white rounded-xl border border-slate-200 p-5">
      <h3 class="font-medium text-slate-800 mb-4">Історія (${events.length})</h3>
      <div class="space-y-3">
        ${events.length ? events.map((e) => `
          <div class="flex gap-3 text-sm">
            <div class="text-lg leading-none">${EVENT_ICONS[e.event_type] || "•"}</div>
            <div class="flex-1">
              <div class="text-slate-800">${esc(e.description)}</div>
              ${e.before_value || e.after_value ? `<div class="text-xs text-slate-500 mt-0.5">${esc(e.before_value || "—")} → ${esc(e.after_value || "—")}</div>` : ""}
              <div class="text-xs text-slate-400 mt-0.5">${esc(e.actor_name)} · ${fmtDate(e.created_at)}</div>
            </div>
          </div>`).join("") : `<div class="text-sm text-slate-400">Подій ще немає</div>`}
      </div>
    </div>`;
}
