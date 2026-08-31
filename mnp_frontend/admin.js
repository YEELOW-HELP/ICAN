// MNP Career KB Editor V1 -- admin-only authoring UI.
// Plain JS, same style as the rest of mnp_frontend. Every write goes to
// /v1/mnp/admin/* with the admin bearer token; the public site reads the
// same Career KB DB, so a save is visible on the public card immediately.

const MnpAdmin = (() => {
  const root = () => document.getElementById("app");
  let ev = null;   // current editor view (whole career)
  let tab = "core";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // --- Ukrainian labels for the internal enum codes --------------------
  const UK = {
    importance: { low: "Низька", medium: "Середня", high: "Висока", critical: "Критична" },
    requirement_type: { must_have: "Обов'язкова", high_value: "Дуже бажана", differentiator: "Перевага", optional: "Додатково" },
    proficiency: { basic: "Базовий", working: "Впевнений", strong: "Високий" },
    difficulty: { easy: "Низька", moderate: "Середня", challenging: "Висока", hard: "Дуже висока" },
    entry_without_experience: { yes: "Так", limited: "Частково", no: "Ні", unknown: "Немає підтверджених даних" },
    requirement_category: { education: "Освіта", experience: "Досвід", language: "Мова", credential: "Сертифікація", legal: "Ліцензія та дозволи", other: "Інші" },
    hardness: { soft: "Бажана", hard: "Обов'язкова (підтверджено)" },
    path_step_type: { entry: "Старт", junior: "Початковий", core: "Основний", senior: "Досвідчений", lead: "Керівний", executive: "Топ-рівень" },
    procon_type: { advantage: "Перевага", disadvantage: "Недолік" },
    relation_type: { progression: "Наступний крок", adjacent: "Суміжна професія", related: "Пов'язана професія", same_family: "Та сама сфера", common_transition: "Частий перехід" },
    external_system: { esco: "ESCO", onet: "O*NET", isco: "ISCO", ua_classifier: "Класифікатор професій України" },
    mapping_type: { exact: "Точна", close: "Близька", broad: "Ширша", narrow: "Вужча" },
    skill_type: { technical: "Технічна", tool: "Інструмент", functional: "Функціональна", management: "Менеджмент", communication: "Комунікація", digital: "Цифрова" },
    source_type: { mnp_editorial_v1: "MNP редакція", expert_review: "Експертний огляд", official_ua: "Офіційне джерело (UA)", esco: "ESCO", onet: "O*NET", other: "Інше" },
    review_status: { editorial: "Редакція", expert_reviewed: "Перевірено експертом", needs_review: "Потребує огляду", approved: "Затверджено", rejected: "Відхилено", candidate: "Кандидат", confirmed: "Підтверджено" },
    status: { draft: "Чернетка", validated: "Перевірено", active: "Опубліковано", review_due: "Потребує перегляду", archived: "В архіві" },
  };
  const lbl = (group, code) => (UK[group] && UK[group][code]) || code || "—";

  // --- tiny form helpers ---------------------------------------------
  function opt(list, group, cur) {
    return list.map((c) => `<option value="${esc(c)}" ${c === cur ? "selected" : ""}>${esc(lbl(group, c))}</option>`).join("");
  }
  const field = (id, label, val, attrs = "") =>
    `<div class="field"><label>${esc(label)}</label><input id="${id}" value="${esc(val || "")}" ${attrs}></div>`;
  const area = (id, label, val) =>
    `<div class="field"><label>${esc(label)}</label><textarea id="${id}" rows="3">${esc(val || "")}</textarea></div>`;
  const sel = (id, label, list, group, cur) =>
    `<div class="field"><label>${esc(label)}</label><select id="${id}">${opt(list, group, cur)}</select></div>`;
  const check = (id, label, on) =>
    `<div class="field"><label><input type="checkbox" id="${id}" ${on ? "checked" : ""}> ${esc(label)}</label></div>`;

  function sourceBlock(prefix, row) {
    row = row || {};
    const v = ev.vocab;
    return `
      <div class="src-block">
        <span class="src-title">Джерело</span>
        ${sel(prefix + "_st", "Тип джерела", v.source_types, "source_type", row.source_type || "mnp_editorial_v1")}
        ${field(prefix + "_sr", "Посилання на джерело", row.source_reference, "placeholder=\"обов'язково для ESCO / O*NET / офіційних джерел\"")}
        ${sel(prefix + "_rs", "Статус огляду", v.review_states, "review_status", row.review_status || "editorial")}
      </div>`;
  }
  const srcPayload = (prefix) => ({
    source_type: val(prefix + "_st"), source_reference: val(prefix + "_sr"), review_status: val(prefix + "_rs"),
  });

  const val = (id) => { const e = document.getElementById(id); return e ? (e.type === "checkbox" ? e.checked : e.value) : undefined; };

  function notify(msg, ok = true) {
    let n = document.getElementById("admin-notify");
    if (!n) { n = document.createElement("div"); n.id = "admin-notify"; document.body.appendChild(n); }
    n.textContent = msg;
    n.className = ok ? "admin-notify ok" : "admin-notify err";
    n.style.display = "block";
    clearTimeout(n._t);
    n._t = setTimeout(() => { n.style.display = "none"; }, 3500);
  }

  async function act(fn) {
    try { await fn(); }
    catch (e) { notify(e.message || String(e), false); }
  }

  // ===================================================================
  // LOGIN
  // ===================================================================
  function screenLogin() {
    root().innerHTML = `
      <h1>Вхід для редагування</h1>
      <p class="lead">Career KB Editor — лише для адміністраторів.</p>
      ${field("adm-email", "Email", "", "type=email autocomplete=username")}
      ${field("adm-pass", "Пароль", "", "type=password autocomplete=current-password")}
      <button class="btn" id="adm-login-btn">Увійти</button>
      <a href="#/catalog" class="btn secondary">Назад до каталогу</a>
    `;
    document.getElementById("adm-login-btn").addEventListener("click", () => act(async () => {
      await MnpApi.adminLogin(val("adm-email").trim(), val("adm-pass"));
      notify("Вхід виконано");
      location.hash = "#/catalog";
    }));
  }

  // ===================================================================
  // ADMIN CATALOG  (all careers, every status)
  // ===================================================================
  let _admCache = null;

  async function screenAdminCatalog() {
    if (!MnpApi.isAdmin()) { location.hash = "#/admin/login"; return; }
    root().innerHTML = `<div class="loading">Завантаження каталогу…</div>`;
    _admCache = await MnpApi.admin("/admin/careers");
    const counts = _admCache.reduce((a, c) => (a[c.status] = (a[c.status] || 0) + 1, a), {});
    root().innerHTML = `
      <div class="admin-bar">
        <span>Режим редактора</span>
        <a href="#/admin/career/new" class="btn">+ Створити професію</a>
        <a href="#/catalog" class="admin-logout" style="color:var(--muted)">публічний сайт</a>
        <a href="#" class="admin-logout">вийти</a>
      </div>
      <h1>Career KB — усі професії (${_admCache.length})</h1>
      <p class="lead">Опубліковано: ${counts.active || 0} · Чернетки: ${counts.draft || 0} · В архіві: ${counts.archived || 0}.
         Публічно показуються лише опубліковані.</p>
      <input id="adm-cat-search" class="career-search" type="text" placeholder="Пошук професії або категорії...">
      <div id="adm-cat-list">${renderAdmCatalog(_admCache)}</div>
    `;
    root().querySelector(".admin-logout:last-child").addEventListener("click", (e) => {
      e.preventDefault(); MnpApi.adminLogout(); location.hash = "#/catalog";
    });
    const s = document.getElementById("adm-cat-search");
    s.addEventListener("input", () => {
      const q = s.value.trim().toLowerCase();
      const f = _admCache.filter((c) => c.name_uk.toLowerCase().includes(q) ||
        (c.category_uk || "").toLowerCase().includes(q) || c.code.includes(q) || c.status.includes(q));
      document.getElementById("adm-cat-list").innerHTML = renderAdmCatalog(f);
    });
  }

  function renderAdmCatalog(rows) {
    const badge = { active: "high", draft: "insufficient", archived: "low",
                    validated: "medium", review_due: "medium" };
    return `<table class="adm-table"><thead><tr><th>Професія</th><th>Категорія</th><th>Статус</th><th>Версія</th><th></th></tr></thead>
      <tbody>${rows.map((c) => `<tr>
        <td><strong>${esc(c.name_uk)}</strong><br><span class="muted">${esc(c.code)}</span></td>
        <td>${esc(c.category_uk || "—")}</td>
        <td><span class="badge ${badge[c.status] || "insufficient"}">${esc(lbl("status", c.status))}</span></td>
        <td>${c.profile_version}</td>
        <td><a class="mini" href="#/admin/career/${c.id}">Відкрити</a></td>
      </tr>`).join("")}</tbody></table>`;
  }

  // ===================================================================
  // CREATE
  // ===================================================================
  function screenCreate() {
    if (!MnpApi.isAdmin()) { location.hash = "#/admin/login"; return; }
    root().innerHTML = `
      <a class="kb-back" href="#/admin/catalog" style="display:inline-block">← До каталогу професій</a>
      <h1>Нова професія</h1>
      <p class="lead">Створюється у статусі <strong>Чернетка</strong>. Опублікувати можна після заповнення мінімуму.</p>
      ${field("nc-code", "Код професії (career_code, латиниця, знак підкреслення)", "", "placeholder=\"напр. data_analyst\"")}
      ${field("nc-name-uk", "Назва (укр)", "")}
      ${field("nc-name-en", "Назва (en, необов'язково)", "")}
      ${field("nc-cat", "Категорія (укр)", "")}
      ${area("nc-short", "Короткий опис (укр)", "")}
      ${area("nc-long", "Повний опис (укр)", "")}
      <button class="btn" id="nc-save">Створити чернетку</button>
      <a href="#/catalog" class="btn secondary">Скасувати</a>
    `;
    document.getElementById("nc-save").addEventListener("click", () => act(async () => {
      const created = await MnpApi.admin("/admin/careers", {
        method: "POST",
        body: {
          career_code: val("nc-code").trim(), name_uk: val("nc-name-uk").trim(),
          name_en: val("nc-name-en").trim() || undefined, category_uk: val("nc-cat").trim() || "Інше",
          short_description_uk: val("nc-short").trim(), long_description_uk: val("nc-long").trim() || undefined,
        },
      });
      notify("Чернетку створено");
      location.hash = `#/admin/career/${created.id}`;
    }));
  }

  // ===================================================================
  // EDITOR SHELL
  // ===================================================================
  const TABS = [
    ["core", "Основне"], ["responsibilities", "Обов'язки"], ["skills", "Навички"],
    ["knowledge", "Знання"], ["requirements", "Вимоги"], ["career_path", "Кар'єрний шлях"],
    ["pros_cons", "Переваги та недоліки"], ["related_careers", "Пов'язані професії"],
    ["external_references", "Зовнішні відповідники"], ["history", "Джерела / Історія"],
  ];

  async function screenEditor(careerId) {
    if (!MnpApi.isAdmin()) { location.hash = "#/admin/login"; return; }
    if (careerId === "new") return screenCreate();
    root().innerHTML = `<div class="loading">Завантаження редактора…</div>`;
    try {
      ev = await MnpApi.admin(`/admin/careers/${careerId}`);
    } catch (e) {
      root().innerHTML = `<div class="error-box">${esc(e.message)}</div><a href="#/catalog" class="btn">Каталог</a>`;
      return;
    }
    renderShell();
  }

  function renderShell() {
    const c = ev.core;
    root().innerHTML = `
      <div class="adm-head">
        <a class="kb-back" href="#/admin/catalog" style="display:inline-block">← До каталогу професій</a>
        <h1>${esc(c.name_uk)} <span class="badge ${c.status === "active" ? "high" : "insufficient"}">${esc(lbl("status", c.status))}</span></h1>
        <p class="kb-cat">${esc(c.career_code)} · версія профілю ${c.profile_version}</p>
        <div class="adm-actions">
          ${c.status === "active"
            ? `<button class="btn secondary" id="adm-archive">Архівувати</button>`
            : `<button class="btn" id="adm-publish">Опублікувати</button>`}
          ${c.status === "archived" ? `<button class="btn secondary" id="adm-unarchive">Повернути з архіву</button>` : ""}
          ${c.status === "active" ? `<a class="btn secondary" href="#/catalog/${ev.id}">Публічна картка</a>` : ""}
        </div>
      </div>
      <div class="adm-tabs">
        ${TABS.map(([k, t]) => `<button class="adm-tab ${k === tab ? "is-active" : ""}" data-tab="${k}">${esc(t)}</button>`).join("")}
      </div>
      <div id="adm-tabbody"></div>
    `;
    root().querySelectorAll(".adm-tab").forEach((b) =>
      b.addEventListener("click", () => { tab = b.dataset.tab; renderShell(); }));
    const pub = document.getElementById("adm-publish");
    if (pub) pub.addEventListener("click", () => act(async () => {
      await MnpApi.admin(`/admin/careers/${ev.id}/publish`, { method: "POST" });
      notify("Професію опубліковано"); await refresh();
    }));
    const arc = document.getElementById("adm-archive");
    if (arc) arc.addEventListener("click", () => act(async () => {
      if (!confirm("Професія буде прибрана з публічного каталогу. Історія та дані збережуться.")) return;
      await MnpApi.admin(`/admin/careers/${ev.id}/archive`, { method: "POST" });
      notify("Професію заархівовано"); await refresh();
    }));
    const un = document.getElementById("adm-unarchive");
    if (un) un.addEventListener("click", () => act(async () => {
      await MnpApi.admin(`/admin/careers/${ev.id}/unarchive`, { method: "POST" });
      notify("Повернено з архіву як чернетку"); await refresh();
    }));
    renderTab();
  }

  async function refresh() {
    ev = await MnpApi.admin(`/admin/careers/${ev.id}`);
    renderShell();
  }
  function applyView(v) { ev = v; renderShell(); }

  function renderTab() {
    const body = document.getElementById("adm-tabbody");
    const fns = {
      core: tabCore, responsibilities: tabResponsibilities, skills: tabSkills, knowledge: tabKnowledge,
      requirements: tabRequirements, career_path: tabPath, pros_cons: tabProsCons,
      related_careers: tabRelated, external_references: tabExternal, history: tabHistory,
    };
    (fns[tab] || tabCore)(body);
  }

  // ---- helper: render a collection table ---------------------------
  function collectionTable(rows, cols, actions) {
    return `<table class="adm-table"><thead><tr>${cols.map((c) => `<th>${esc(c.h)}</th>`).join("")}<th></th></tr></thead>
      <tbody>${rows.map((r) => `<tr>
        ${cols.map((c) => `<td>${c.render(r)}</td>`).join("")}
        <td class="adm-row-actions">${actions(r)}</td>
      </tr>`).join("") || `<tr><td colspan="${cols.length + 1}" class="muted">Немає записів</td></tr>`}</tbody></table>`;
  }

  function rowActions(coll, r, { move = false } = {}) {
    return `
      ${move ? `<button class="mini" data-a="up" data-id="${r.id}">↑</button><button class="mini" data-a="down" data-id="${r.id}">↓</button>` : ""}
      <button class="mini" data-a="edit" data-id="${r.id}">Ред.</button>
      <button class="mini danger" data-a="del" data-id="${r.id}">×</button>`;
  }

  function wireRows(coll, editForm, { move = false } = {}) {
    document.querySelectorAll(`#adm-tabbody [data-a]`).forEach((b) => {
      b.addEventListener("click", () => act(async () => {
        const id = b.dataset.id, a = b.dataset.a;
        if (a === "del") {
          if (!confirm("Видалити цей запис?")) return;
          applyView(await MnpApi.admin(`/admin/careers/${ev.id}/${coll}/${id}`, { method: "DELETE" }));
          notify("Видалено");
        } else if (a === "up" || a === "down") {
          applyView(await MnpApi.admin(`/admin/careers/${ev.id}/${coll}/${id}/move`, { method: "POST", body: { direction: a } }));
        } else if (a === "edit") {
          editForm(id);
        }
      }));
    });
  }

  // ===================================================================
  // TAB: CORE
  // ===================================================================
  function tabCore(body) {
    const c = ev.core, v = ev.vocab;
    body.innerHTML = `
      <div class="card">
        ${field("c-code", "Код професії (career_code)", c.career_code, c.status !== "draft" ? "disabled title=\"код не змінюється після створення\"" : "")}
        ${field("c-name-uk", "Назва (укр)", c.name_uk)}
        ${field("c-name-en", "Назва (en)", c.name_en)}
        ${field("c-cat", "Категорія (укр)", c.category_uk)}
        ${area("c-short", "Короткий опис (укр)", c.short_description_uk)}
        ${area("c-long", "Повний опис (укр)", c.long_description_uk)}
        ${sel("c-diff", "Складність входу", ["", ...v.difficulty], "difficulty", c.difficulty_level || "")}
        ${sel("c-ewe", "Старт без досвіду", v.entry_without_experience, "entry_without_experience", c.entry_without_experience || "unknown")}
        ${area("c-route", "Типовий вхід (укр)", c.typical_entry_route_uk)}
        <button class="btn" id="c-save">Зберегти</button>
      </div>`;
    document.getElementById("c-save").addEventListener("click", () => act(async () => {
      const b = {
        name_uk: val("c-name-uk").trim(), name_en: val("c-name-en").trim(),
        category_uk: val("c-cat").trim(), short_description_uk: val("c-short").trim(),
        long_description_uk: val("c-long").trim(), difficulty_level: val("c-diff") || null,
        entry_without_experience: val("c-ewe"), typical_entry_route_uk: val("c-route").trim(),
      };
      applyView(await MnpApi.admin(`/admin/careers/${ev.id}`, { method: "PATCH", body: b }));
      notify("Зміни збережено");
    }));
  }

  // ===================================================================
  // TAB: RESPONSIBILITIES
  // ===================================================================
  function tabResponsibilities(body) {
    const rows = ev.responsibilities;
    body.innerHTML = `
      ${collectionTable(rows, [
        { h: "Обов'язок (укр)", render: (r) => esc(r.title_uk) },
        { h: "Опис (укр)", render: (r) => esc(r.description_uk || "") },
        { h: "Важливість", render: (r) => esc(lbl("importance", r.importance)) },
        { h: "Огляд", render: (r) => esc(lbl("review_status", r.review_status)) },
      ], (r) => rowActions("responsibilities", r, { move: true }))}
      <button class="btn" id="add-resp">+ Додати обов'язок</button>
      <div id="resp-form"></div>`;
    wireRows("responsibilities", (id) => respForm(rows.find((r) => r.id === id)), { move: true });
    document.getElementById("add-resp").addEventListener("click", () => respForm(null));
  }
  function respForm(r) {
    const box = document.getElementById("resp-form");
    box.innerHTML = `<div class="card">
      <h3>${r ? "Редагувати обов'язок" : "Новий обов'язок"}</h3>
      ${field("rf-title", "Обов'язок (укр)", r && r.title_uk)}
      ${area("rf-desc", "Опис (укр)", r && r.description_uk)}
      ${sel("rf-imp", "Важливість", ev.vocab.importance, "importance", (r && r.importance) || "medium")}
      ${field("rf-freq", "Частота (необов'язково)", r && r.frequency)}
      ${sourceBlock("rf", r)}
      <button class="btn" id="rf-save">Зберегти</button>
      <button class="btn secondary" id="rf-cancel">Скасувати</button>
    </div>`;
    document.getElementById("rf-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    document.getElementById("rf-save").addEventListener("click", () => act(async () => {
      const b = { title_uk: val("rf-title").trim(), description_uk: val("rf-desc").trim(),
                  importance: val("rf-imp"), frequency: val("rf-freq").trim(), ...srcPayload("rf") };
      const path = `/admin/careers/${ev.id}/responsibilities` + (r ? `/${r.id}` : "");
      applyView(await MnpApi.admin(path, { method: r ? "PATCH" : "POST", body: b }));
      notify("Збережено");
    }));
  }

  // ===================================================================
  // TAB: SKILLS
  // ===================================================================
  function tabSkills(body) {
    const hard = ev.skills.filter((s) => !s.is_soft);
    const soft = ev.skills.filter((s) => s.is_soft);
    const skillCols = [
      { h: "Навичка (укр)", render: (s) => esc(s.name_uk) },
      { h: "Потрібність", render: (s) => esc(lbl("requirement_type", s.requirement_type)) },
      { h: "Рівень", render: (s) => esc(lbl("proficiency", s.required_level)) },
      { h: "Важливість", render: (s) => esc(lbl("importance", s.importance)) },
      { h: "Огляд", render: (s) => esc(lbl("review_status", s.review_status)) },
    ];
    body.innerHTML = `
      <h3>Тверді навички</h3>
      ${collectionTable(hard, skillCols, (r) => rowActions("skills", r))}
      <h3>М'які навички</h3>
      ${collectionTable(soft, skillCols, (r) => rowActions("skills", r))}
      <button class="btn" id="add-skill">+ Додати навичку</button>
      <div id="skill-form"></div>`;
    wireRows("skills", (id) => skillEditForm(ev.skills.find((s) => s.id === id)));
    document.getElementById("add-skill").addEventListener("click", () => skillAddForm());
  }
  function skillEditForm(s) {
    const box = document.getElementById("skill-form");
    box.innerHTML = `<div class="card">
      <h3>Редагувати: ${esc(s.name_uk)}</h3>
      ${sel("se-imp", "Важливість", ev.vocab.importance, "importance", s.importance)}
      ${sel("se-lvl", "Потрібний рівень", ev.vocab.proficiency, "proficiency", s.required_level)}
      ${sel("se-rt", "Потрібність", ev.vocab.requirement_type, "requirement_type", s.requirement_type)}
      ${sourceBlock("se", s)}
      <button class="btn" id="se-save">Зберегти</button>
      <button class="btn secondary" id="se-cancel">Скасувати</button>
    </div>`;
    document.getElementById("se-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    document.getElementById("se-save").addEventListener("click", () => act(async () => {
      applyView(await MnpApi.admin(`/admin/careers/${ev.id}/skills/${s.id}`, {
        method: "PATCH",
        body: { importance: val("se-imp"), required_level: val("se-lvl"), requirement_type: val("se-rt"), ...srcPayload("se") },
      }));
      notify("Збережено");
    }));
  }
  function skillAddForm() {
    const box = document.getElementById("skill-form");
    box.innerHTML = `<div class="card">
      <h3>Додати навичку</h3>
      <p class="muted">Спочатку знайдіть наявну навичку. Створюйте нову лише якщо такої ще немає.</p>
      <div class="field"><label>Пошук навички</label><input id="sa-q" placeholder="почніть вводити…"></div>
      <div id="sa-results" class="adm-search-results"></div>
      <div id="sa-attach"></div>
      <details><summary>Створити нову канонічну навичку</summary>
        ${field("sa-nu", "Назва (укр)", "")}
        ${field("sa-ne", "Назва (en)", "")}
        ${sel("sa-nt", "Тип навички", ev.vocab.skill_type, "skill_type", "technical")}
        <button class="btn secondary" id="sa-create">Створити навичку</button>
      </details>
      <button class="btn secondary" id="sa-cancel">Закрити</button>
    </div>`;
    document.getElementById("sa-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    let picked = null;
    const doSearch = async () => {
      const q = val("sa-q").trim();
      const res = await MnpApi.admin(`/admin/skills/search?q=${encodeURIComponent(q)}`);
      document.getElementById("sa-results").innerHTML = res.map((s) =>
        `<button class="chip pick" data-id="${s.id}" data-name="${esc(s.name_uk)}">${esc(s.name_uk)} <span class="muted">(${esc(lbl("skill_type", s.skill_type))})</span></button>`).join("") || "<span class='muted'>нічого не знайдено</span>";
      document.querySelectorAll("#sa-results .pick").forEach((b) => b.addEventListener("click", () => {
        picked = { id: b.dataset.id, name: b.dataset.name };
        renderAttach();
      }));
    };
    const renderAttach = () => {
      document.getElementById("sa-attach").innerHTML = `<div class="card">
        <strong>${esc(picked.name)}</strong>
        ${sel("sa-imp", "Важливість", ev.vocab.importance, "importance", "medium")}
        ${sel("sa-lvl", "Потрібний рівень", ev.vocab.proficiency, "proficiency", "working")}
        ${sel("sa-rt", "Потрібність", ev.vocab.requirement_type, "requirement_type", "high_value")}
        ${sourceBlock("saa", null)}
        <button class="btn" id="sa-do">Додати до професії</button>
      </div>`;
      document.getElementById("sa-do").addEventListener("click", () => act(async () => {
        applyView(await MnpApi.admin(`/admin/careers/${ev.id}/skills`, {
          method: "POST",
          body: { skill_id: picked.id, importance: val("sa-imp"), required_level: val("sa-lvl"),
                  requirement_type: val("sa-rt"), ...srcPayload("saa") },
        }));
        notify("Навичку додано");
      }));
    };
    document.getElementById("sa-q").addEventListener("input", () => act(doSearch));
    document.getElementById("sa-create").addEventListener("click", () => act(async () => {
      const s = await MnpApi.admin("/admin/skills", {
        method: "POST",
        body: { name_uk: val("sa-nu").trim(), name_en: val("sa-ne").trim(), skill_type: val("sa-nt") },
      });
      picked = { id: s.id, name: s.name_uk };
      notify("Навичку створено"); renderAttach();
    }));
    act(doSearch);
  }

  // ===================================================================
  // TAB: KNOWLEDGE
  // ===================================================================
  function tabKnowledge(body) {
    body.innerHTML = `
      ${collectionTable(ev.knowledge, [
        { h: "Знання (укр)", render: (r) => esc(r.name_uk) },
        { h: "Важливість", render: (r) => esc(lbl("importance", r.importance)) },
        { h: "Огляд", render: (r) => esc(lbl("review_status", r.review_status)) },
      ], (r) => rowActions("knowledge", r))}
      <button class="btn" id="add-kn">+ Додати знання</button>
      <div id="kn-form"></div>`;
    wireRows("knowledge", (id) => knEditForm(ev.knowledge.find((k) => k.id === id)));
    document.getElementById("add-kn").addEventListener("click", () => knAddForm());
  }
  function knEditForm(k) {
    const box = document.getElementById("kn-form");
    box.innerHTML = `<div class="card"><h3>Редагувати: ${esc(k.name_uk)}</h3>
      ${sel("ke-imp", "Важливість", ev.vocab.importance, "importance", k.importance)}
      ${sourceBlock("ke", k)}
      <button class="btn" id="ke-save">Зберегти</button>
      <button class="btn secondary" id="ke-cancel">Скасувати</button></div>`;
    document.getElementById("ke-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    document.getElementById("ke-save").addEventListener("click", () => act(async () => {
      applyView(await MnpApi.admin(`/admin/careers/${ev.id}/knowledge/${k.id}`, {
        method: "PATCH", body: { importance: val("ke-imp"), ...srcPayload("ke") },
      }));
      notify("Збережено");
    }));
  }
  function knAddForm() {
    const box = document.getElementById("kn-form");
    box.innerHTML = `<div class="card"><h3>Додати знання</h3>
      <div class="field"><label>Пошук знання</label><input id="kn-q"></div>
      <div id="kn-results" class="adm-search-results"></div>
      <div id="kn-attach"></div>
      <details><summary>Створити нове знання</summary>
        ${field("kn-nu", "Назва (укр)", "")}${field("kn-ne", "Назва (en)", "")}
        <button class="btn secondary" id="kn-create">Створити</button></details>
      <button class="btn secondary" id="kn-cancel">Закрити</button></div>`;
    document.getElementById("kn-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    let picked = null;
    const search = async () => {
      const res = await MnpApi.admin(`/admin/knowledge/search?q=${encodeURIComponent(val("kn-q").trim())}`);
      document.getElementById("kn-results").innerHTML = res.map((k) =>
        `<button class="chip pick" data-id="${k.id}" data-name="${esc(k.name_uk)}">${esc(k.name_uk)}</button>`).join("") || "<span class='muted'>нічого не знайдено</span>";
      document.querySelectorAll("#kn-results .pick").forEach((b) => b.addEventListener("click", () => {
        picked = { id: b.dataset.id, name: b.dataset.name };
        document.getElementById("kn-attach").innerHTML = `<div class="card"><strong>${esc(picked.name)}</strong>
          ${sel("kn-imp", "Важливість", ev.vocab.importance, "importance", "medium")}
          ${sourceBlock("kna", null)}
          <button class="btn" id="kn-do">Додати</button></div>`;
        document.getElementById("kn-do").addEventListener("click", () => act(async () => {
          applyView(await MnpApi.admin(`/admin/careers/${ev.id}/knowledge`, {
            method: "POST", body: { knowledge_id: picked.id, importance: val("kn-imp"), ...srcPayload("kna") },
          }));
          notify("Знання додано");
        }));
      }));
    };
    document.getElementById("kn-q").addEventListener("input", () => act(search));
    document.getElementById("kn-create").addEventListener("click", () => act(async () => {
      const k = await MnpApi.admin("/admin/knowledge", { method: "POST", body: { name_uk: val("kn-nu").trim(), name_en: val("kn-ne").trim() } });
      picked = { id: k.id, name: k.name_uk };
      notify("Створено");
      document.getElementById("kn-attach").innerHTML = `<div class="card"><strong>${esc(k.name_uk)}</strong>
        ${sel("kn-imp", "Важливість", ev.vocab.importance, "importance", "medium")}${sourceBlock("kna", null)}
        <button class="btn" id="kn-do">Додати</button></div>`;
      document.getElementById("kn-do").addEventListener("click", () => act(async () => {
        applyView(await MnpApi.admin(`/admin/careers/${ev.id}/knowledge`, {
          method: "POST", body: { knowledge_id: picked.id, importance: val("kn-imp"), ...srcPayload("kna") },
        }));
        notify("Знання додано");
      }));
    }));
    act(search);
  }

  // ===================================================================
  // TAB: REQUIREMENTS
  // ===================================================================
  function tabRequirements(body) {
    body.innerHTML = `
      <p class="limitation-label">Порожня категорія = «Немає підтверджених даних», а НЕ «вимоги немає».</p>
      ${collectionTable(ev.requirements, [
        { h: "Категорія", render: (r) => esc(lbl("requirement_category", r.category)) },
        { h: "Вимога (укр)", render: (r) => esc(r.description_uk) },
        { h: "Значення", render: (r) => esc(r.value || "") },
        { h: "Обов'язковість", render: (r) => esc(lbl("hardness", r.hardness)) },
        { h: "Огляд", render: (r) => esc(lbl("review_status", r.review_status)) },
      ], (r) => rowActions("requirements", r))}
      <button class="btn" id="add-req">+ Додати вимогу</button>
      <div id="req-form"></div>`;
    wireRows("requirements", (id) => reqForm(ev.requirements.find((r) => r.id === id)));
    document.getElementById("add-req").addEventListener("click", () => reqForm(null));
  }
  function reqForm(r) {
    const box = document.getElementById("req-form");
    box.innerHTML = `<div class="card">
      <h3>${r ? "Редагувати вимогу" : "Нова вимога"}</h3>
      ${sel("qf-cat", "Категорія", ev.vocab.requirement_category, "requirement_category", (r && r.category) || "education")}
      ${field("qf-desc", "Вимога (укр)", r && r.description_uk)}
      ${field("qf-val", "Значення (напр. bachelor, 1_year, uk:b2)", r && r.value)}
      ${sel("qf-hard", "Обов'язковість", ev.vocab.hardness, "hardness", (r && r.hardness) || "soft")}
      ${field("qf-country", "Країна", (r && r.country) || "UA")}
      <p class="muted">Жорстка (HARD) вимога має спиратися на офіційне джерело, а не на редакційну оцінку.</p>
      ${sourceBlock("qf", r)}
      <button class="btn" id="qf-save">Зберегти</button>
      <button class="btn secondary" id="qf-cancel">Скасувати</button></div>`;
    document.getElementById("qf-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    document.getElementById("qf-save").addEventListener("click", () => act(async () => {
      const b = { category: val("qf-cat"), description_uk: val("qf-desc").trim(), value: val("qf-val").trim(),
                  hardness: val("qf-hard"), country: val("qf-country").trim(), ...srcPayload("qf") };
      const path = `/admin/careers/${ev.id}/requirements` + (r ? `/${r.id}` : "");
      applyView(await MnpApi.admin(path, { method: r ? "PATCH" : "POST", body: b }));
      notify("Збережено");
    }));
  }

  // ===================================================================
  // TAB: CAREER PATH
  // ===================================================================
  function tabPath(body) {
    body.innerHTML = `
      <p class="limitation-label">Типовий маршрут, а не гарантований шлях просування.</p>
      ${collectionTable(ev.career_path, [
        { h: "№", render: (r) => r.step_order },
        { h: "Крок (укр)", render: (r) => esc(r.step_name_uk) + (r.is_current_career_step ? " <span class='badge insufficient'>ця професія</span>" : "") },
        { h: "Рівень", render: (r) => esc(lbl("path_step_type", r.step_type)) },
        { h: "Досвід", render: (r) => esc(r.typical_experience_text_uk || "") },
      ], (r) => rowActions("career-path", r, { move: true }))}
      <button class="btn" id="add-step">+ Додати крок</button>
      <div id="step-form"></div>`;
    wireRows("career-path", (id) => stepForm(ev.career_path.find((s) => s.id === id)), { move: true });
    document.getElementById("add-step").addEventListener("click", () => stepForm(null));
  }
  function stepForm(s) {
    const box = document.getElementById("step-form");
    box.innerHTML = `<div class="card"><h3>${s ? "Редагувати крок" : "Новий крок"}</h3>
      ${field("sf-name", "Назва кроку (укр)", s && s.step_name_uk)}
      ${sel("sf-type", "Рівень", ev.vocab.path_step_type, "path_step_type", (s && s.step_type) || "core")}
      ${area("sf-desc", "Опис (укр)", s && s.description_uk)}
      ${field("sf-exp", "Типовий досвід (укр)", s && s.typical_experience_text_uk)}
      ${check("sf-cur", "Це рівень самої професії", s && s.is_current_career_step)}
      ${sourceBlock("sf", s)}
      <button class="btn" id="sf-save">Зберегти</button>
      <button class="btn secondary" id="sf-cancel">Скасувати</button></div>`;
    document.getElementById("sf-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    document.getElementById("sf-save").addEventListener("click", () => act(async () => {
      const b = { step_name_uk: val("sf-name").trim(), step_type: val("sf-type"),
                  description_uk: val("sf-desc").trim(), typical_experience_text_uk: val("sf-exp").trim(),
                  is_current_career_step: val("sf-cur"), ...srcPayload("sf") };
      const path = `/admin/careers/${ev.id}/career-path` + (s ? `/${s.id}` : "");
      applyView(await MnpApi.admin(path, { method: s ? "PATCH" : "POST", body: b }));
      notify("Збережено");
    }));
  }

  // ===================================================================
  // TAB: PROS / CONS
  // ===================================================================
  function tabProsCons(body) {
    const pros = ev.pros_cons.filter((p) => p.type === "advantage");
    const cons = ev.pros_cons.filter((p) => p.type === "disadvantage");
    const cols = [
      { h: "Твердження (укр)", render: (r) => esc(r.text_uk) },
      { h: "Джерело", render: (r) => esc(lbl("source_type", r.source_type)) },
      { h: "Огляд", render: (r) => esc(lbl("review_status", r.review_status)) },
    ];
    body.innerHTML = `
      <p class="limitation-label">Редакційна оцінка MNP, а не статистика. За замовчуванням джерело — MNP редакція.</p>
      <h3>Переваги</h3>
      ${collectionTable(pros, cols, (r) => rowActions("pros-cons", r, { move: true }))}
      <h3>Недоліки</h3>
      ${collectionTable(cons, cols, (r) => rowActions("pros-cons", r, { move: true }))}
      <button class="btn" id="add-pc">+ Додати</button>
      <div id="pc-form"></div>`;
    wireRows("pros-cons", (id) => pcForm(ev.pros_cons.find((p) => p.id === id)), { move: true });
    document.getElementById("add-pc").addEventListener("click", () => pcForm(null));
  }
  function pcForm(p) {
    const box = document.getElementById("pc-form");
    box.innerHTML = `<div class="card"><h3>${p ? "Редагувати" : "Нове твердження"}</h3>
      ${sel("pcf-type", "Тип", ev.vocab.procon_type, "procon_type", (p && p.type) || "advantage")}
      ${area("pcf-text", "Твердження (укр)", p && p.text_uk)}
      ${sourceBlock("pcf", p)}
      <button class="btn" id="pcf-save">Зберегти</button>
      <button class="btn secondary" id="pcf-cancel">Скасувати</button></div>`;
    document.getElementById("pcf-cancel").addEventListener("click", () => { box.innerHTML = ""; });
    document.getElementById("pcf-save").addEventListener("click", () => act(async () => {
      const b = { type: val("pcf-type"), text_uk: val("pcf-text").trim(), ...srcPayload("pcf") };
      const path = `/admin/careers/${ev.id}/pros-cons` + (p ? `/${p.id}` : "");
      applyView(await MnpApi.admin(path, { method: p ? "PATCH" : "POST", body: b }));
      notify("Збережено");
    }));
  }

  // ===================================================================
  // TAB: RELATED CAREERS
  // ===================================================================
  async function tabRelated(body) {
    const all = await MnpApi.admin("/admin/careers");
    const options = all.filter((c) => c.id !== ev.id);
    body.innerHTML = `
      ${collectionTable(ev.related_careers, [
        { h: "Професія", render: (r) => esc(r.to_career_name_uk || r.to_career_code) },
        { h: "Тип зв'язку", render: (r) => esc(lbl("relation_type", r.relation_type)) },
        { h: "Огляд", render: (r) => esc(lbl("review_status", r.review_status)) },
      ], (r) => rowActions("relations", r))}
      <div class="card"><h3>Додати зв'язок</h3>
        <div class="field"><label>Пов'язана професія</label>
          <select id="rl-to">${options.map((c) => `<option value="${c.id}">${esc(c.name_uk)} (${esc(lbl("status", c.status))})</option>`).join("")}</select></div>
        ${sel("rl-type", "Тип зв'язку", ev.vocab.relation_type, "relation_type", "related")}
        ${sourceBlock("rl", null)}
        <button class="btn" id="rl-add">Додати</button>
      </div>`;
    wireRows("relations", () => {});
    document.getElementById("rl-add").addEventListener("click", () => act(async () => {
      applyView(await MnpApi.admin(`/admin/careers/${ev.id}/relations`, {
        method: "POST", body: { to_career_id: val("rl-to"), relation_type: val("rl-type"), ...srcPayload("rl") },
      }));
      notify("Зв'язок додано");
    }));
  }

  // ===================================================================
  // TAB: EXTERNAL REFERENCES
  // ===================================================================
  function tabExternal(body) {
    body.innerHTML = `
      <p class="limitation-label">Довідкові відповідники (ESCO / O*NET / класифікатор). Ніколи не підтверджуються автоматично.</p>
      ${collectionTable(ev.external_references, [
        { h: "Система", render: (r) => esc(lbl("external_system", r.external_system)) },
        { h: "Ідентифікатор", render: (r) => esc(r.external_id) },
        { h: "Мітка", render: (r) => esc(r.external_label || "") },
        { h: "Тип", render: (r) => esc(lbl("mapping_type", r.mapping_type)) },
        { h: "Статус", render: (r) => esc(lbl("review_status", r.review_status)) },
      ], (r) => rowActions("external-references", r))}
      <div class="card"><h3>Додати відповідник</h3>
        ${sel("xr-sys", "Зовнішня система", ev.vocab.external_system, "external_system", "esco")}
        ${field("xr-id", "Зовнішній ідентифікатор", "")}
        ${field("xr-label", "Мітка (назва в зовнішній системі)", "")}
        ${sel("xr-map", "Тип відповідності", ev.vocab.mapping_type, "mapping_type", "close")}
        ${field("xr-ref", "Посилання на джерело", "")}
        ${area("xr-note", "Примітка", "")}
        <button class="btn" id="xr-add">Додати</button>
      </div>`;
    wireRows("external-references", (id) => xrEdit(ev.external_references.find((x) => x.id === id)));
    document.getElementById("xr-add").addEventListener("click", () => act(async () => {
      applyView(await MnpApi.admin(`/admin/careers/${ev.id}/external-references`, {
        method: "POST",
        body: { external_system: val("xr-sys"), external_id: val("xr-id").trim(),
                external_label: val("xr-label").trim(), mapping_type: val("xr-map"),
                source_reference: val("xr-ref").trim(), note: val("xr-note").trim() },
      }));
      notify("Відповідник додано");
    }));
  }
  function xrEdit(x) {
    const box = document.getElementById("adm-tabbody");
    const holder = document.createElement("div");
    holder.innerHTML = `<div class="card"><h3>Редагувати відповідник</h3>
      ${field("xe-label", "Мітка", x.external_label)}
      ${sel("xe-map", "Тип відповідності", ev.vocab.mapping_type, "mapping_type", x.mapping_type)}
      ${sel("xe-rs", "Статус", ev.vocab.ext_review_states, "review_status", x.review_status)}
      ${field("xe-ref", "Посилання", x.source_reference)}
      ${area("xe-note", "Примітка", x.note)}
      <button class="btn" id="xe-save">Зберегти</button>
      <button class="btn secondary" id="xe-cancel">Скасувати</button></div>`;
    box.appendChild(holder);
    document.getElementById("xe-cancel").addEventListener("click", () => holder.remove());
    document.getElementById("xe-save").addEventListener("click", () => act(async () => {
      applyView(await MnpApi.admin(`/admin/careers/${ev.id}/external-references/${x.id}`, {
        method: "PATCH",
        body: { external_label: val("xe-label").trim(), mapping_type: val("xe-map"),
                review_status: val("xe-rs"), source_reference: val("xe-ref").trim(), note: val("xe-note").trim() },
      }));
      notify("Збережено");
    }));
  }

  // ===================================================================
  // TAB: HISTORY
  // ===================================================================
  async function tabHistory(body) {
    body.innerHTML = `<div class="loading">Завантаження історії…</div>`;
    const { history } = await MnpApi.admin(`/admin/careers/${ev.id}/history`);
    body.innerHTML = `
      <p class="muted">Кожна зміна фіксується: хто, коли, старе та нове значення. Джерело кожного значення — у відповідних формах (поле «Джерело»).</p>
      <table class="adm-table"><thead><tr><th>Коли</th><th>Що</th><th>Дія</th><th>Адмін</th><th>Було → Стало</th></tr></thead>
      <tbody>${history.map((h) => `<tr>
        <td>${esc((h.changed_at || "").replace("T", " ").slice(0, 16))}</td>
        <td>${esc(h.entity_type.replace("mnp_career_", "").replace("mnp_career", "професія").replace("mnp_external_mapping", "зовн. відповідник"))}</td>
        <td>${esc(h.action)}</td>
        <td>#${esc(h.changed_by_admin_id ?? "—")}</td>
        <td class="hist-diff">${esc(JSON.stringify(h.old_value || {}))} <br>→ ${esc(JSON.stringify(h.new_value || {}))}</td>
      </tr>`).join("") || `<tr><td colspan="5" class="muted">Історія порожня</td></tr>`}</tbody></table>`;
  }

  return { screenLogin, screenEditor, screenCreate, screenAdminCatalog };
})();
