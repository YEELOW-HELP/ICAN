/* PERSON KB BASE V1 -- user profile flows + admin Person KB.
 * Plain JS, Ukrainian-first, functionality over polish. One canonical
 * Person KB behind both. */
const MnpPersonKB = (() => {
  const root = () => document.getElementById("app");
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const val = (id) => { const e = document.getElementById(id); return e ? (e.type === "checkbox" ? e.checked : e.value) : undefined; };
  const admin = (p, o) => MnpApi.admin(p, o);
  const me = (p, o) => MnpApi.request(p, o);

  function toast(msg, ok = true) {
    let n = document.getElementById("pk-toast");
    if (!n) { n = document.createElement("div"); n.id = "pk-toast"; document.body.appendChild(n); }
    n.textContent = msg;
    n.style.cssText = "position:fixed;bottom:16px;left:50%;transform:translateX(-50%);padding:10px 16px;border-radius:8px;z-index:99;color:#fff;background:" + (ok ? "#123d1e" : "#4a1220");
    clearTimeout(n._t); n._t = setTimeout(() => n.remove(), 3500);
  }
  async function act(fn) { try { await fn(); } catch (e) { toast(e.message || String(e), false); } }

  // A file dropped on the public Home hero is stashed here and picked up
  // by screenCv() after the route changes to #/profile/cv.
  let _stagedCv = null;
  function stageCvFile(file) { _stagedCv = file; }

  // Customer-facing evidence labels — never the raw enum. `self_reported`
  // (the default for anything typed by hand) shows nothing: a chip on
  // every manual row is noise, not information.
  const EV_LABEL = {
    system_detected: ["Знайдено у CV", "cv"],
    cv_import: ["Знайдено у CV", "cv"],
    user_confirmed: ["Підтверджено", "ok"],
    document_supported: ["Підтверджено документом", "ok"],
  };
  function evChip(state) {
    const hit = EV_LABEL[state];
    if (!hit) return "";
    return ` <span class="nv-ev ${hit[1]}">${hit[0]}</span>`;
  }
  // Friendly note for a skill the person typed that is not in the shared
  // catalogue yet — no "taxonomy" wording in customer UI.
  function skillNote(s) {
    return s && s.custom_status === "pending_review"
      ? ` <span class="nv-ev check">нова навичка</span>` : "";
  }
  // Header uses this flag to show "Мій профіль" instead of "Створити профіль".
  function markProfile(exists) {
    try {
      if (exists) localStorage.setItem("mnp_has_profile", "1");
      else localStorage.removeItem("mnp_has_profile");
    } catch (e) {}
  }

  const TRI = [["unknown", "Немає даних"], ["yes", "Так"], ["no", "Ні"]];
  const EDU_LEVEL = [["unknown", "Немає даних"], ["secondary", "Середня"], ["vocational", "Професійно-технічна"], ["incomplete_higher", "Неповна вища"], ["bachelor", "Бакалавр"], ["specialist", "Спеціаліст"], ["master", "Магістр"], ["phd", "PhD"], ["other", "Інше"]];
  const EDU_STATUS = [["unknown", "Немає даних"], ["completed", "Завершено"], ["ongoing", "Триває"], ["incomplete", "Незавершено"]];
  const CRED_TYPE = [["course", "Курс"], ["certificate", "Сертифікат"], ["license", "Ліцензія"], ["professional_credential", "Проф. кваліфікація"], ["other", "Інше"]];
  const ACT_TYPE = [["project", "Проєкт"], ["academic_project", "Навчальний проєкт"], ["practice", "Практика"], ["internship", "Стажування"], ["volunteering", "Волонтерство"], ["student_activity", "Студентська активність"], ["student_government", "Студентське самоврядування"], ["event_organization", "Організація подій"], ["pet_project", "Власний проєкт"], ["other", "Інше"]];
  const LANG_LEVEL = [["unknown", "Немає даних"], ["a1", "A1"], ["a2", "A2"], ["b1", "B1"], ["b2", "B2"], ["c1", "C1"], ["c2", "C2"], ["native", "Рідна"], ["other", "Інше"]];
  const PROF = [["", "Немає даних"], ["basic", "Базовий"], ["working", "Впевнений"], ["strong", "Високий"]];
  const WFORMAT = [["unknown", "Немає даних"], ["onsite", "В офісі"], ["remote", "Віддалено"], ["hybrid", "Гібрид"], ["any", "Будь-який"]];

  const opts = (list, cur) => list.map(([v, t]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(t)}</option>`).join("");
  const F = (id, label, v, attrs = "") => `<label class="pk-f"><span>${esc(label)}</span><input id="${id}" value="${esc(v || "")}" ${attrs}></label>`;
  const A = (id, label, v) => `<label class="pk-f"><span>${esc(label)}</span><textarea id="${id}" rows="3">${esc(v || "")}</textarea></label>`;
  const S = (id, label, list, cur) => `<label class="pk-f"><span>${esc(label)}</span><select id="${id}">${opts(list, cur)}</select></label>`;

  // ================= USER =================
  async function screenLanding() {
    await MnpApi.ensureSession();
    const cur = await me("/me/person").catch(() => ({ person: null }));
    const has = cur && cur.id;
    markProfile(has);
    const I = (n) => NvUI.icon(n);
    root().innerHTML = `
      <div class="pk-wrap">
        <span class="eyebrow">Ваш наступний крок — можливий</span>
        <h1>Створити кар'єрний профіль</h1>
        <p class="lead">Оберіть зручний спосіб, і ми допоможемо вам зробити перший крок до нових можливостей.</p>
        ${has ? `<div class="pk-card"><p>У вас уже є профіль (${esc(cur.core.status_uk)}).</p>
           <a class="btn" href="#/app">Відкрити робочий простір</a>
           <a class="btn secondary" href="#/profile/me">Мій профіль</a></div>` : ""}
        <div class="pk-choices">
          <div class="choice-card is-reco" onclick="location.hash='#/profile/build'">
            <span class="badge-reco">${I("sparkles")} Рекомендовано</span>
            <div class="choice-ico nv-ico-box">${I("edit")}</div>
            <h3>Заповнити самостійно</h3>
            <p>Підійде, якщо готові пройти профіль за 10–15 хвилин.</p>
          </div>
          <div class="choice-card" onclick="location.hash='#/profile/cv'">
            <div class="choice-ico nv-ico-box">${I("upload")}</div>
            <h3>Завантажити резюме</h3>
            <p>Ми проаналізуємо ваш досвід і допоможемо швидше заповнити профіль.</p>
          </div>
          <div class="choice-card future" aria-disabled="true">
            <div class="choice-ico nv-ico-box soft">${I("user")}</div>
            <h3>Профіль створює консультант <span class="soon-tag">Незабаром</span></h3>
            <p>Отримайте особисту підтримку від нашого фахівця.</p>
          </div>
        </div>
      </div>`;
  }

  const STEPS = ["about", "experience", "education", "skills", "languages", "credentials", "activities", "mobility", "review"];
  const STEP_TITLE = { about: "Основне", experience: "Досвід", education: "Освіта", skills: "Навички", languages: "Мови", credentials: "Сертифікати", activities: "Активності", mobility: "Мобільність", review: "Перевірка" };
  let _p = null, _step = 0;

  async function screenBuild() {
    await MnpApi.ensureSession();
    _p = await me("/me/person").catch(() => ({ person: null }));
    if (!_p || !_p.id) _p = null;
    _step = 0;
    renderStep();
  }
  async function reload() { _p = await me("/me/person"); renderStep(); }

  function wizBar(cur, total, label) {
    return `<div class="wiz-bar-wrap">
      <div class="wiz-bar-top"><span>${esc(label)}</span><b>Крок ${cur} з ${total}</b></div>
      <div class="wiz-bar"><div class="wiz-bar-fill" style="width:${Math.round((cur / total) * 100)}%"></div></div>
    </div>`;
  }

  function renderStep() {
    const step = STEPS[_step];
    root().innerHTML = `
      <div class="pk-wrap">
        ${wizBar(_step + 1, STEPS.length, "Створення кар'єрного профілю")}
        <h1>${esc(STEP_TITLE[step])}</h1>
        <div id="pk-body"></div>
        <div class="pk-nav">
          ${_step > 0 ? `<button class="btn secondary" id="pk-prev">Назад</button>` : ""}
          ${_step < STEPS.length - 1 ? `<button class="btn" id="pk-next">Продовжити →</button>` : `<button class="btn" id="pk-finish">Зберегти профіль</button>`}
        </div>
      </div>`;
    const prev = document.getElementById("pk-prev"); if (prev) prev.onclick = () => { _step--; renderStep(); };
    const next = document.getElementById("pk-next"); if (next) next.onclick = () => act(async () => { await saveStep(step); _step++; renderStep(); });
    const fin = document.getElementById("pk-finish"); if (fin) fin.onclick = () => act(async () => {
      await me("/me/person/activate", { method: "POST" });
      markProfile(true);
      toast("Профіль збережено"); location.hash = "#/profile/confirmed";
    });
    (BODY[step] || (() => {}))();
  }

  const BODY = {
    about() {
      const c = (_p && _p.core) || {};
      const fn = c.first_name === "—" ? "" : (c.first_name || "");
      const initials = ((fn[0] || "") + (c.last_name ? c.last_name[0] : "")).toUpperCase() || "?";
      document.getElementById("pk-body").innerHTML = `
        <div class="avatar-circle" id="f-avatar">${initials}</div>
        ${F("f-fn", "Ім'я *", fn)}
        ${F("f-ln", "Прізвище", c.last_name)}
        ${F("f-phone", "Телефон", c.phone)}
        ${F("f-email", "Email", c.email, "type=email")}
        ${F("f-tg", "Telegram (@username)", c.telegram_username)}
        ${F("f-city", "Місто", c.city)}
        ${F("f-region", "Область", c.region)}`;
      const upd = () => {
        const i = (((val("f-fn") || "")[0] || "") + ((val("f-ln") || "")[0] || "")).toUpperCase() || "?";
        document.getElementById("f-avatar").textContent = i;
      };
      document.getElementById("f-fn").addEventListener("input", upd);
      document.getElementById("f-ln").addEventListener("input", upd);
    },
    education() { listBlock("educations", eduForm, (e) => `${esc(e.education_level_uk)} — ${esc(e.institution_name || "—")}${e.end_year ? " (" + e.end_year + ")" : ""}`); },
    experience() {
      const empty = !((_p && _p.experiences) || []).length;
      document.getElementById("pk-body").innerHTML =
        (empty ? `<p class="muted">Ще немає досвіду роботи? Це нормально — просто натисніть «Продовжити».</p>` : "")
        + blockHtml("experiences", (x) => `${esc(x.raw_job_title)} — ${esc(x.company_name || "—")}`);
      wireBlock("experiences", expForm);
    },
    activities() { listBlock("activities", actForm, (a) => `${esc(a.activity_type_uk)}: ${esc(a.title)}`); },
    skills() { skillsBody(); },
    credentials() { listBlock("credentials", credForm, (c) => `${esc(c.credential_type_uk)}: ${esc(c.title || "—")}`); },
    languages() { listBlock("languages", langForm, (l) => `${esc(l.language)} — ${esc(l.level_uk)}`); },
    mobility() {
      const m = (_p && _p.mobility) || {};
      document.getElementById("pk-body").innerHTML = `
        ${S("f-dl", "Посвідчення водія", TRI, m.has_driver_license || "unknown")}
        ${F("f-dlc", "Категорії (напр. B, C1)", m.driver_license_categories)}
        ${S("f-car", "Автомобіль", TRI, m.has_car || "unknown")}
        ${S("f-relo", "Готовність до переїзду", TRI, m.willing_to_relocate || "unknown")}
        ${S("f-wf", "Формат роботи", WFORMAT, m.work_format || "unknown")}`;
    },
    review() {
      const v = _p || {};
      const sections = [
        ["Особиста інформація", true],
        ["Досвід роботи", (v.experiences || []).length > 0],
        ["Освіта", (v.educations || []).length > 0],
        ["Навички та інструменти", (v.skills || []).length > 0],
        ["Мови", (v.languages || []).length > 0],
      ];
      document.getElementById("pk-body").innerHTML = `
        <div class="pk-card" style="text-align:center;padding:2rem 1.5rem">
          <div class="nv-ico-box" style="margin:0 auto .8rem;width:48px;height:48px;background:var(--st-green-bg);color:var(--st-green)">${NvUI.icon("check")}</div>
          <h2 style="margin:.2rem 0 .4rem">Чудово! Основна інформація готова</h2>
          <p class="muted" style="max-width:44ch;margin:0 auto 1.1rem">Ви заповнили ключові розділи профілю. Далі ми дізнаємось більше про ваші сильні сторони, інтереси та цілі.</p>
          <div style="display:inline-block;text-align:left">
            ${sections.map(([t, done]) => `<div class="wi-q" style="${done ? "color:var(--st-green)" : ""}">${NvUI.icon(done ? "check" : "close")}${esc(t)}</div>`).join("")}
          </div>
        </div>
        <p class="muted" style="margin-top:1rem">Освіта: ${(v.educations || []).length} · Досвід: ${(v.experiences || []).length} · Активності: ${(v.activities || []).length} · Навички: ${(v.skills || []).length} · Мови: ${(v.languages || []).length}</p>`;
    },
  };

  async function saveStep(step) {
    if (step === "about") {
      const body = { first_name: val("f-fn").trim() || "—", last_name: val("f-ln"), phone: val("f-phone"), email: val("f-email"), telegram_username: val("f-tg"), city: val("f-city"), region: val("f-region") };
      _p = await me("/me/person", { method: "POST", body });
    } else if (step === "mobility") {
      _p = await me("/me/person", { method: "POST", body: { has_driver_license: val("f-dl"), driver_license_categories: val("f-dlc"), has_car: val("f-car"), willing_to_relocate: val("f-relo"), work_format: val("f-wf") } });
    }
  }

  // ---- reusable nested-collection block ----
  function blockHtml(coll, label) {
    const rows = (_p && _p[coll]) || [];
    return `<div class="pk-list" id="pk-${coll}">
      ${rows.map((r) => `<div class="pk-row-card"><span class="pk-row-txt">${label(r)}</span>
        <button class="mini-ic" data-edit="${r.id}" type="button" title="Редагувати">${NvUI.icon("edit")}</button>
        <button class="mini-ic danger" data-del="${r.id}" type="button" title="Видалити">${NvUI.icon("trash")}</button></div>`).join("") || `<p class="muted">Поки що порожньо.</p>`}
      <div id="pk-form-${coll}"></div>
      <button class="btn secondary" id="pk-add-${coll}">+ Додати</button>
    </div>`;
  }
  function listBlock(coll, formFn, label) {
    document.getElementById("pk-body").innerHTML = blockHtml(coll, label);
    wireBlock(coll, formFn);
  }
  function wireBlock(coll, formFn) {
    const add = document.getElementById(`pk-add-${coll}`);
    if (add) add.onclick = () => renderForm(coll, formFn, null);
    document.querySelectorAll(`#pk-${coll} [data-edit]`).forEach((b) => b.onclick = () => {
      const row = (_p[coll] || []).find((r) => r.id === b.dataset.edit);
      renderForm(coll, formFn, row);
    });
    document.querySelectorAll(`#pk-${coll} [data-del]`).forEach((b) => b.onclick = () => act(async () => {
      _p = await me(`/me/person/${coll}/${b.dataset.del}`, { method: "DELETE" });
      renderStep();
    }));
  }
  function renderForm(coll, formFn, row) {
    document.getElementById(`pk-form-${coll}`).innerHTML = `<div class="pk-card">${formFn(row || {})}
      <button class="btn" id="pk-save-${coll}">${row ? "Зберегти" : "Додати"}</button>
      <button class="btn secondary" id="pk-cancel-${coll}">Скасувати</button></div>`;
    document.getElementById(`pk-cancel-${coll}`).onclick = () => renderStep();
    document.getElementById(`pk-save-${coll}`).onclick = () => act(async () => {
      const body = COLLECT[coll]();
      _p = row
        ? await me(`/me/person/${coll}/${row.id}`, { method: "PATCH", body })
        : await me(`/me/person/${coll}`, { method: "POST", body });
      toast("Збережено"); renderStep();
    });
  }

  const eduForm = (e) => `${S("e-lvl", "Рівень", EDU_LEVEL, e.education_level)}${F("e-inst", "Заклад", e.institution_name)}${F("e-spec", "Спеціальність / кваліфікація", e.specialty_or_qualification)}${F("e-sy", "Рік початку", e.start_year, "type=number")}${F("e-ey", "Рік завершення", e.end_year, "type=number")}${S("e-st", "Статус", EDU_STATUS, e.status)}${A("e-desc", "Опис", e.description)}`;
  const expForm = (x) => `${F("x-title", "Посада (як у вас) *", x.raw_job_title)}${F("x-co", "Компанія", x.company_name)}${F("x-sd", "Дата початку", x.start_date, "type=date")}${F("x-ed", "Дата завершення", x.end_date, "type=date")}${S("x-cur", "Зараз тут працюю", TRI, x.is_current)}${A("x-resp", "Обов'язки", x.responsibilities_description)}${A("x-ach", "Досягнення", x.achievements)}${F("x-tools", "Інструменти", x.tools_used)}`;
  const actForm = (a) => `${S("a-type", "Тип", ACT_TYPE, a.activity_type)}${F("a-title", "Назва *", a.title)}${F("a-org", "Організація", a.organization)}${F("a-role", "Роль", a.role)}${F("a-sd", "Початок", a.start_date, "type=date")}${F("a-ed", "Завершення", a.end_date, "type=date")}${A("a-desc", "Опис", a.description)}${A("a-res", "Результат / досягнення", a.result_or_achievement)}`;
  const langForm = (l) => `${F("l-lang", "Мова *", l.language)}${S("l-lvl", "Рівень", LANG_LEVEL, l.level)}${F("l-cert", "Сертифікат", l.certificate)}`;

  const credForm = (c) => `${S("cr-type", "Тип", CRED_TYPE, c.credential_type)}${F("cr-title", "Назва *", c.title)}${F("cr-prov", "Провайдер", c.provider)}${F("cr-issue", "Дата видачі", c.issue_date, "type=date")}${F("cr-exp", "Дійсний до", c.expiry_date, "type=date")}${F("cr-num", "Номер", c.credential_number)}${A("cr-desc", "Опис", c.description)}`;

  const COLLECT = {
    educations: () => ({ education_level: val("e-lvl"), institution_name: val("e-inst"), specialty_or_qualification: val("e-spec"), start_year: val("e-sy") || null, end_year: val("e-ey") || null, status: val("e-st"), description: val("e-desc") }),
    experiences: () => ({ raw_job_title: val("x-title"), company_name: val("x-co"), start_date: val("x-sd") || null, end_date: val("x-ed") || null, is_current: val("x-cur"), responsibilities_description: val("x-resp"), achievements: val("x-ach"), tools_used: val("x-tools") }),
    activities: () => ({ activity_type: val("a-type"), title: val("a-title"), organization: val("a-org"), role: val("a-role"), start_date: val("a-sd") || null, end_date: val("a-ed") || null, description: val("a-desc"), result_or_achievement: val("a-res") }),
    languages: () => ({ language: val("l-lang"), level: val("l-lvl"), certificate: val("l-cert") }),
    credentials: () => ({ credential_type: val("cr-type"), title: val("cr-title"), provider: val("cr-prov"), issue_date: val("cr-issue") || null, expiry_date: val("cr-exp") || null, credential_number: val("cr-num"), description: val("cr-desc") }),
  };

  // ---- skills (chip-tag picker, mirrors C08) ----
  const POPULAR_SKILLS = ["Комунікація", "Excel", "Організація роботи", "Клієнтський сервіс", "Управління проєктами", "Англійська мова", "Продажі", "Маркетинг", "Креативність", "Робота в команді"];
  function skillsBody() {
    const rows = (_p && _p.skills) || [];
    const already = new Set(rows.map((s) => (s.raw_input || "").toLowerCase()));
    document.getElementById("pk-body").innerHTML = `
      <div class="pk-card">
        <label class="pk-f"><span>Які у вас навички?</span><input id="sk-search" placeholder="почніть вводити або оберіть із підказок нижче"></label>
        <div id="sk-results" class="chips-row" style="margin:.3rem 0"></div>
        <p class="muted" style="font-size:.82rem;margin:.7rem 0 .4rem">Популярні навички</p>
        <div class="chips-row">
          ${POPULAR_SKILLS.filter((s) => !already.has(s.toLowerCase())).map((s) => `<button class="chip" data-quick="${esc(s)}" type="button">+ ${esc(s)}</button>`).join("")}
        </div>
      </div>
      <p class="muted" style="font-size:.82rem;margin:1rem 0 .4rem">Ваші навички (${rows.length})</p>
      <div class="chips-row">
        ${rows.map((s) => `<span class="chip" style="display:inline-flex;align-items:center;gap:.4rem">${esc(s.raw_input || "")}${skillNote(s)}${s.proficiency ? ` · ${esc(s.proficiency_uk)}` : ""}<button class="chip-x" data-del="${s.id}" type="button" aria-label="Видалити">×</button></span>`).join("") || `<p class="muted">Поки що порожньо.</p>`}
      </div>`;
    document.querySelectorAll(".chip-x").forEach((b) => b.onclick = () => act(async () => {
      _p = await me(`/me/person/skills/${b.dataset.del}`, { method: "DELETE" }); renderStep();
    }));
    document.querySelectorAll("[data-quick]").forEach((b) => b.onclick = () => act(async () => {
      _p = await me("/me/person/skills", { method: "POST", body: { raw_input: b.dataset.quick } });
      toast("Додано"); renderStep();
    }));
    const search = document.getElementById("sk-search");
    search.oninput = async () => {
      const q = search.value.trim();
      if (q.length < 2) { document.getElementById("sk-results").innerHTML = ""; return; }
      const res = await me(`/me/person/skills/search?q=${encodeURIComponent(q)}`);
      document.getElementById("sk-results").innerHTML = res.map((s) => `<button class="chip" data-skid="${s.id}" type="button">+ ${esc(s.name_uk)}</button>`).join(" ")
        || `<button class="chip" data-quick="${esc(q)}" type="button">+ Додати «${esc(q)}» як свою навичку</button>`;
      document.querySelectorAll("#sk-results [data-skid]").forEach((b) => b.onclick = () => act(async () => {
        _p = await me("/me/person/skills", { method: "POST", body: { canonical_skill_id: b.dataset.skid } });
        toast("Додано"); renderStep();
      }));
      document.querySelectorAll("#sk-results [data-quick]").forEach((b) => b.onclick = () => act(async () => {
        _p = await me("/me/person/skills", { method: "POST", body: { raw_input: b.dataset.quick } });
        toast("Додано"); renderStep();
      }));
    };
  }

  // ---- edit existing profile ----
  async function screenEdit() {
    await MnpApi.ensureSession();
    _p = await me("/me/person").catch(() => null);
    if (!_p || !_p.id) { markProfile(false); location.hash = "#/profile"; return; }
    markProfile(true);
    _step = 0;
    root().innerHTML = `<div class="pk-wrap">
      <a class="kb-back" href="#/profile/me" style="display:inline-block">← Мій профіль</a>
      <h1>Редагувати профіль <span class="badge ${_p.core.status === "active" ? "high" : "insufficient"}">${esc(_p.core.status_uk)}</span></h1>
      <p class="muted">Зміни в списках (досвід, навички, освіта тощо) зберігаються одразу. Для розділів «Про мене» та «Мобільність» натисніть «Зберегти».</p>
      <div class="pk-steps" id="pk-tabs">${STEPS.slice(0, STEPS.length - 1).map((s, i) => `<span data-s="${i}" class="${i === 0 ? "on" : ""}">${esc(STEP_TITLE[s])}</span>`).join("")}</div>
      <div id="pk-body"></div>
      <div class="pk-nav"><button class="btn" id="pk-save-all">Зберегти</button><a class="btn secondary" href="#/profile/me">Готово</a></div></div>`;
    document.querySelectorAll("#pk-tabs span").forEach((t) => t.onclick = () => {
      document.querySelectorAll("#pk-tabs span").forEach((x) => x.classList.remove("on"));
      t.classList.add("on"); _step = +t.dataset.s;
      (BODY[STEPS[_step]] || (() => {}))();
    });
    document.getElementById("pk-save-all").onclick = () => act(async () => {
      const step = STEPS[_step];
      if (step === "about" || step === "mobility") { await saveStep(step); toast("Збережено"); }
      else toast("Зміни в цьому розділі зберігаються одразу");
    });
    BODY.about();
  }

  // ---- CV upload + review ----
  let _cv = null;
  const CV_STAGE_LABEL = ["Завантаження резюме", "Перевірка знайдених даних", "Підтвердження профілю", "Профіль готовий"];
  function cvSteps(active) { return wizBar(active + 1, CV_STAGE_LABEL.length, CV_STAGE_LABEL[active]); }
  async function screenCv() {
    await MnpApi.ensureSession();
    const staged = _stagedCv; _stagedCv = null;
    root().innerHTML = `
      <div class="pk-wrap"><h1>Завантажити CV</h1>
        ${cvSteps(0)}
        <p class="lead">Ми знайдемо факти у вашому резюме. Ви перевірите та підтвердите їх — нічого не зберігається без вашого підтвердження.</p>
        <div class="nv-drop" id="cv-drop">
          <div class="nv-ico-box soft" style="margin:0 auto .5rem">${NvUI.icon("upload")}</div>
          <strong>Перетягніть файл сюди або оберіть</strong>
          <p>PDF, DOCX або TXT · до 15 МБ</p>
          <input type="file" id="cv-file" accept=".pdf,.docx,.txt">
          <div id="cv-name" class="muted" style="margin-top:.4rem"></div>
        </div>
        <button class="btn" id="cv-up">Розпізнати</button>
        <a class="btn secondary" href="#/profile/build">Заповнити вручну</a>
        <div id="cv-out"></div>
      </div>`;
    const input = document.getElementById("cv-file");
    const nameEl = document.getElementById("cv-name");
    const showName = () => { nameEl.textContent = input.files[0] ? `Обрано: ${input.files[0].name}` : ""; };
    input.onchange = showName;
    if (staged) {
      const dt = new DataTransfer(); dt.items.add(staged); input.files = dt.files; showName();
    }
    const drop = document.getElementById("cv-drop");
    ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("drag")));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; showName(); }
    });
    document.getElementById("cv-up").onclick = () => act(async () => {
      const f = input.files[0];
      if (!f) { toast("Оберіть файл", false); return; }
      showProcessing();
      const form = new FormData(); form.append("file", f);
      const res = await MnpApi.request("/me/person/cv", { method: "POST", body: form, isForm: true });
      if (!res.parsed) {
        document.getElementById("cv-out").innerHTML = `<div class="error-box">${esc(res.fallback || res.message)}</div>
          <p class="muted">Файл збережено. Ви можете заповнити профіль вручну — уже введені дані не втратяться.</p>
          <a class="btn" href="#/profile/build">Заповнити вручну</a>
          <button class="btn secondary" id="cv-retry">Спробувати інший файл</button>`;
        const r = document.getElementById("cv-retry"); if (r) r.onclick = () => screenCv();
        return;
      }
      _cv = res.candidates; renderCvReview();
    });
  }
  // Decorative pacing over a real async CV-parse call -- ticks visually,
  // never blocks or fakes a result; the real request runs in parallel.
  function showProcessing() {
    const stages = ["Читаємо файл", "Визначаємо досвід", "Знаходимо навички", "Аналізуємо освіту", "Готуємо попередні дані"];
    const out = document.getElementById("cv-out");
    out.innerHTML = `${cvSteps(1)}<div class="pk-card" style="text-align:center;padding:2rem 1.5rem">
      <div class="nv-ico-box soft" style="margin:0 auto .8rem;width:48px;height:48px">${NvUI.icon("checklist")}</div>
      <h2 style="margin:.2rem 0 1rem">Аналізуємо ваше резюме</h2>
      <div id="cv-proc-list" style="display:inline-block;text-align:left">
        ${stages.map((s, i) => `<div class="wi-q" data-i="${i}" style="opacity:${i === 0 ? 1 : .4}">${NvUI.icon("gauge")}${esc(s)}</div>`).join("")}
      </div></div>`;
    let i = 0;
    const rows = out.querySelectorAll("#cv-proc-list .wi-q");
    const t = setInterval(() => {
      if (i >= rows.length) { clearInterval(t); return; }
      rows[i].style.opacity = 1;
      rows[i].style.color = "var(--st-green)";
      rows[i].innerHTML = NvUI.icon("check") + esc(stages[i]);
      i++;
    }, 420);
  }

  function renderCvReview() {
    const c = _cv;
    const sec = (title, arr, render) => `<h3>${esc(title)}</h3>${arr.length ? arr.map((r, i) => `<label class="pk-chk"><input type="checkbox" checked data-sec="${title}" data-i="${i}"> ${render(r)}</label>`).join("") : `<p class="muted">Не знайдено.</p>`}`;
    document.getElementById("cv-out").innerHTML = `
      ${cvSteps(1)}
      <div class="pk-card">
        <h2 style="margin-top:0">Попередній перегляд витягнутих даних</h2>
        <p class="muted">Ми знайшли ці записи у вашому резюме. Зніміть галочку, щоб не додавати запис. Редагувати можна після збереження.</p>
        ${sec("Досвід роботи", c.experiences, (e) => `${esc(e.raw_job_title)} — ${esc(e.company_name || "—")}`)}
        ${sec("Освіта", c.educations, (e) => `${esc(e.specialty_or_qualification || "—")}`)}
        ${sec("Навички", c.skills, (s) => esc(s.raw_input))}
        ${sec("Мови", c.languages, (l) => `${esc(l.language)} — ${esc(l.level)}`)}
        ${sec("Сертифікати", c.credentials, (x) => esc(x.title))}
        <div class="pk-nav">
          <button class="btn" id="cv-confirm">Перевірити та продовжити</button>
          <a class="btn secondary" href="#/profile/build">Редагувати вручну</a>
        </div>
      </div>`;
    document.getElementById("cv-confirm").onclick = () => act(async () => {
      const pick = (title, arr) => arr.filter((_, i) => {
        const el = document.querySelector(`[data-sec="${title}"][data-i="${i}"]`); return el && el.checked;
      });
      const confirmed = {
        experiences: pick("Досвід роботи", c.experiences), educations: pick("Освіта", c.educations),
        skills: pick("Навички", c.skills), languages: pick("Мови", c.languages),
        credentials: pick("Сертифікати", c.credentials),
      };
      await MnpApi.request("/me/person/cv/confirm", { method: "POST", body: { document_id: c.document_id, confirmed } });
      await me("/me/person/activate", { method: "POST" }).catch(() => {});
      markProfile(true);
      toast("Збережено в профіль"); location.hash = "#/profile/confirmed";
    });
  }

  // ---- confirmation screen ("Ми проаналізували ваш досвід") ----
  async function screenConfirmed() {
    await MnpApi.ensureSession();
    const p = await me("/me/person").catch(() => null);
    if (!p || !p.id) { markProfile(false); location.hash = "#/profile"; return; }
    markProfile(true);
    const count = (a) => (p[a] || []).length;
    const needName = !p.core.first_name || p.core.first_name === "—";
    root().innerHTML = `
      <div class="pk-wrap">
        ${cvSteps(2)}
        <span class="demo-flag" style="background:#e6f6ef;color:var(--green)">Профіль збережено</span>
        <h1>Ми проаналізували ваш досвід</h1>
        <p class="lead">Перевірте, чи ми правильно зрозуміли ваш профіль. Ви можете відредагувати будь-який розділ.</p>
        ${needName ? `<div class="pk-card"><label class="pk-f"><span>Як вас звати?</span>
          <input id="cf-name" placeholder="Ім'я"></label>
          <button class="btn secondary" id="cf-name-save">Зберегти ім'я</button></div>` : ""}
        <div class="nv-prof-grid">
          ${profCard("Особистий профіль", [
            row("Ім'я", `${esc(p.core.first_name || "")} ${esc(p.core.last_name || "")}`),
            row("Місто", esc(p.core.city || "—")),
            row("Контакти", [p.core.phone, p.core.email, p.core.telegram_username].filter(Boolean).map(esc).join(" · ") || "—"),
          ])}
          ${profCard("Досвід роботи", (p.experiences || []).map((x) => row(esc(x.raw_job_title), esc(x.company_name || "—") + evChip(x.evidence_state))))}
          ${profCard("Ключові навички", (p.skills || []).map((s) => row(esc(s.raw_input || "навичка") + skillNote(s), evChip(s.evidence_state) || "&nbsp;")))}
          ${profCard("Освіта та мови", [
            ...(p.educations || []).map((e) => row(esc(e.education_level_uk), esc(e.institution_name || "—"))),
            ...(p.languages || []).map((l) => row(esc(l.language), esc(l.level_uk))),
          ])}
        </div>
        <div class="pk-nav">
          <a class="btn btn-lg" href="#/app/profile">Підтвердити профіль</a>
          <a class="btn secondary" href="#/profile/edit">Редагувати</a>
        </div>
        <p class="muted" style="margin-top:.6rem">Знайдено записів: досвід ${count("experiences")} · освіта ${count("educations")} · навички ${count("skills")} · мови ${count("languages")} · сертифікати ${count("credentials")}.</p>
      </div>`;
    const nb = document.getElementById("cf-name-save");
    if (nb) nb.onclick = () => act(async () => {
      const v = (val("cf-name") || "").trim();
      if (!v) { toast("Вкажіть ім'я", false); return; }
      await me("/me/person", { method: "POST", body: { first_name: v } });
      toast("Збережено"); screenConfirmed();
    });
  }
  const row = (k, v) => `<li><span class="k">${k}</span><br>${v || "—"}</li>`;
  const profCard = (title, rows) => `<div class="nv-prof-card"><h3>${esc(title)}</h3><ul>${rows.length ? rows.join("") : "<li class=\"muted\">Немає даних</li>"}</ul></div>`;

  // ---- My Profile (read-only, human-readable canonical MnpPerson) ----
  async function screenMyProfile() {
    await MnpApi.ensureSession();
    const p = await me("/me/person").catch(() => null);
    if (!p || !p.id) { markProfile(false); location.hash = "#/profile"; return; }
    markProfile(true);
    const m = p.mobility || {};
    root().innerHTML = `
      <div class="pk-wrap">
        <h1>Мій профіль <span class="badge ${p.core.status === "active" ? "high" : "insufficient"}">${esc(p.core.status_uk)}</span></h1>
        <div class="pk-nav" style="margin-top:.4rem">
          <a class="btn" href="#/app">Робочий простір</a>
          <a class="btn secondary" href="#/profile/edit">Редагувати профіль</a>
          <a class="btn secondary" href="#/profile/cv">Оновити з CV</a>
          <a class="btn secondary" href="#/catalog">Переглянути професії</a>
        </div>
        <div class="nv-prof-grid">
          ${profCard("Особистий профіль", [
            row("Ім'я", `${esc(p.core.first_name || "")} ${esc(p.core.last_name || "")}`),
            row("Місто / регіон", [p.core.city, p.core.region, p.core.country].filter(Boolean).map(esc).join(", ") || "—"),
          ])}
          ${profCard("Контакти", [
            row("Телефон", esc(p.core.phone || "—")),
            row("Email", esc(p.core.email || "—")),
            row("Telegram", esc(p.core.telegram_username || "—")),
          ])}
          ${profCard("Досвід роботи", (p.experiences || []).map((x) =>
            row(esc(x.raw_job_title) + evChip(x.evidence_state),
              `${esc(x.company_name || "—")}${x.start_date ? " · " + esc(x.start_date) : ""}${x.end_date ? " – " + esc(x.end_date) : (x.is_current === "yes" ? " · зараз" : "")}`)))}
          ${profCard("Навички та інструменти", (p.skills || []).map((s) =>
            row(esc(s.raw_input || "навичка") + skillNote(s) + evChip(s.evidence_state),
              s.proficiency ? esc(s.proficiency_uk) : "")))}
          ${profCard("Освіта", (p.educations || []).map((e) =>
            row(esc(e.education_level_uk) + evChip(e.evidence_state),
              `${esc(e.institution_name || "—")}${e.end_year ? " · " + e.end_year : ""}`)))}
          ${profCard("Мови", (p.languages || []).map((l) => row(esc(l.language), esc(l.level_uk))))}
          ${profCard("Сертифікати", (p.credentials || []).map((c) =>
            row(esc(c.title) + evChip(c.evidence_state), esc(c.credential_type_uk))))}
          ${profCard("Проєкти та активності", (p.activities || []).map((a) =>
            row(esc(a.title) + evChip(a.evidence_state), esc(a.activity_type_uk))))}
          ${profCard("Мобільність / формат роботи", [
            row("Формат роботи", esc(m.work_format_uk || "—")),
            row("Посвідчення водія", esc(m.has_driver_license_uk || "—") + (m.driver_license_categories ? " (" + esc(m.driver_license_categories) + ")" : "")),
            row("Автомобіль", esc(m.has_car_uk || "—")),
            row("Готовність до переїзду", esc(m.willing_to_relocate_uk || "—")),
          ])}
        </div>
      </div>`;
  }

  // ================= ADMIN =================
  async function admScreenList() {
    if (!MnpApi.isAdmin()) { location.hash = "#/admin/login"; return; }
    const rows = await admin("/admin/persons");
    root().innerHTML = `
      <div class="adm-actions"><h1 style="flex:1">Люди (${rows.length})</h1>
        <a href="#/admin/persons/new" class="btn">+ Створити профіль</a></div>
      <input id="pk-q" class="career-search" placeholder="Пошук за ім'ям / містом / статусом">
      <table class="kb-table"><thead><tr><th>Ім'я</th><th>Телефон</th><th>Email</th><th>Telegram</th><th>Місто</th><th>Статус</th><th>Оновлено</th><th></th></tr></thead>
      <tbody id="pk-rows">${rows.map(prow).join("")}</tbody></table>`;
    const q = document.getElementById("pk-q");
    q.oninput = () => {
      const t = q.value.toLowerCase();
      document.getElementById("pk-rows").innerHTML = rows.filter((r) =>
        (r.name || "").toLowerCase().includes(t) || (r.city || "").toLowerCase().includes(t) || (r.status_uk || "").toLowerCase().includes(t)).map(prow).join("");
    };
  }
  const prow = (r) => `<tr><td><a href="#/admin/persons/${r.id}">${esc(r.name || "—")}</a></td><td>${esc(r.phone || "")}</td><td>${esc(r.email || "")}</td><td>${esc(r.telegram_username || "")}</td><td>${esc(r.city || "")}</td><td><span class="badge ${r.status === "active" ? "high" : "insufficient"}">${esc(r.status_uk)}</span></td><td>${esc((r.updated_at || "").slice(0, 16).replace("T", " "))}</td><td><a class="mini" href="#/admin/persons/${r.id}">Відкрити</a></td></tr>`;

  async function admScreenCreate() {
    if (!MnpApi.isAdmin()) { location.hash = "#/admin/login"; return; }
    root().innerHTML = `<div class="pk-wrap"><a class="kb-back" href="#/admin/persons">← Люди</a><h1>Новий профіль</h1>
      ${F("n-fn", "Ім'я *", "")}${F("n-ln", "Прізвище", "")}${F("n-phone", "Телефон", "")}${F("n-email", "Email", "", "type=email")}${F("n-tg", "Telegram", "")}${F("n-city", "Місто", "")}
      <button class="btn" id="n-save">Створити (DRAFT)</button></div>`;
    document.getElementById("n-save").onclick = () => act(async () => {
      if (!val("n-fn").trim()) { toast("Вкажіть ім'я", false); return; }
      const p = await admin("/admin/persons", { method: "POST", body: { first_name: val("n-fn"), last_name: val("n-ln"), phone: val("n-phone"), email: val("n-email"), telegram_username: val("n-tg"), city: val("n-city") } });
      location.hash = `#/admin/persons/${p.id}`;
    });
  }

  const ADM_TABS = [["core", "Основне"], ["educations", "Освіта"], ["experiences", "Досвід"], ["activities", "Проєкти та активності"], ["skills", "Навички та інструменти"], ["languages", "Мови"], ["credentials", "Сертифікати / Кваліфікації"], ["documents", "Документи"], ["mobility", "Мобільність"]];
  let _ap = null, _atab = "core";

  async function admScreenCard(id) {
    if (!MnpApi.isAdmin()) { location.hash = "#/admin/login"; return; }
    _ap = await admin(`/admin/persons/${id}`);
    _atab = "core";
    admRender();
  }
  async function admReload() { _ap = await admin(`/admin/persons/${_ap.id}`); admRender(); }

  function admRender() {
    const c = _ap.core;
    root().innerHTML = `
      <div class="adm-head"><a class="kb-back" href="#/admin/persons">← Люди</a>
        <h1>${esc(c.first_name)} ${esc(c.last_name || "")} <span class="badge ${c.status === "active" ? "high" : "insufficient"}">${esc(c.status_uk)}</span></h1>
        <p class="kb-cat">${esc(_ap.id)} · джерело: ${esc(c.source_uk)} · версія ${c.profile_version}</p>
        <div class="adm-actions">
          ${c.status !== "active" ? `<button class="btn" id="ap-activate">Активувати</button>` : ""}
          ${c.status !== "archived" ? `<button class="btn secondary" id="ap-archive">Архівувати</button>` : `<button class="btn secondary" id="ap-unarchive">Повернути з архіву</button>`}
        </div></div>
      <div class="adm-tabs">${ADM_TABS.map(([k, t]) => `<button class="adm-tab ${k === _atab ? "is-active" : ""}" data-t="${k}">${esc(t)}</button>`).join("")}</div>
      <div id="ap-body"></div>`;
    root().querySelectorAll(".adm-tab").forEach((b) => b.onclick = () => { _atab = b.dataset.t; admRender(); });
    const a = document.getElementById("ap-activate"); if (a) a.onclick = () => act(async () => { await admin(`/admin/persons/${_ap.id}/activate`, { method: "POST" }); await admReload(); });
    const ar = document.getElementById("ap-archive"); if (ar) ar.onclick = () => act(async () => { await admin(`/admin/persons/${_ap.id}/archive`, { method: "POST" }); await admReload(); });
    const un = document.getElementById("ap-unarchive"); if (un) un.onclick = () => act(async () => { await admin(`/admin/persons/${_ap.id}/unarchive`, { method: "POST" }); await admReload(); });
    admTab();
  }

  function admTab() {
    const body = document.getElementById("ap-body");
    if (_atab === "core") {
      const c = _ap.core;
      body.innerHTML = `${F("c-fn", "Ім'я", c.first_name)}${F("c-ln", "Прізвище", c.last_name)}${F("c-phone", "Телефон", c.phone)}${F("c-email", "Email", c.email, "type=email")}${F("c-tg", "Telegram", c.telegram_username)}${F("c-city", "Місто", c.city)}${F("c-region", "Область", c.region)}${F("c-country", "Країна", c.country)}${F("c-dob", "Дата народження", c.date_of_birth, "type=date")}${A("c-notes", "Нотатки", c.notes)}
        <button class="btn" id="c-save">Зберегти</button>`;
      document.getElementById("c-save").onclick = () => act(async () => {
        _ap = await admin(`/admin/persons/${_ap.id}`, { method: "PATCH", body: { first_name: val("c-fn"), last_name: val("c-ln"), phone: val("c-phone"), email: val("c-email"), telegram_username: val("c-tg"), city: val("c-city"), region: val("c-region"), country: val("c-country"), date_of_birth: val("c-dob") || null, notes: val("c-notes") } });
        toast("Збережено"); admRender();
      });
    } else if (_atab === "mobility") {
      const m = _ap.mobility;
      body.innerHTML = `${S("m-dl", "Посвідчення водія", TRI, m.has_driver_license)}${F("m-dlc", "Категорії", m.driver_license_categories)}${S("m-car", "Автомобіль", TRI, m.has_car)}${S("m-relo", "Готовність до переїзду", TRI, m.willing_to_relocate)}${S("m-wf", "Формат роботи", WFORMAT, m.work_format)}
        <button class="btn" id="m-save">Зберегти</button>`;
      document.getElementById("m-save").onclick = () => act(async () => {
        _ap = await admin(`/admin/persons/${_ap.id}`, { method: "PATCH", body: { has_driver_license: val("m-dl"), driver_license_categories: val("m-dlc"), has_car: val("m-car"), willing_to_relocate: val("m-relo"), work_format: val("m-wf") } });
        toast("Збережено"); admRender();
      });
    } else if (_atab === "documents") {
      body.innerHTML = (_ap.documents || []).map((d) => `<div class="pk-row"><span>${esc(d.document_type_uk)}: ${esc(d.filename)}</span></div>`).join("") || `<p class="muted">Документів немає.</p>`;
    } else if (_atab === "skills") {
      admSkills();
    } else {
      admCollection(_atab);
    }
  }

  function admCollection(coll) {
    const rows = _ap[coll] || [];
    const labelFor = {
      educations: (e) => `${esc(e.education_level_uk)} — ${esc(e.institution_name || "—")} ${e.end_year || ""} · ${esc(e.evidence_state_uk)}`,
      experiences: (x) => `${esc(x.raw_job_title)} — ${esc(x.company_name || "—")} · ${esc(x.evidence_state_uk)}`,
      activities: (a) => `${esc(a.activity_type_uk)}: ${esc(a.title)} · ${esc(a.evidence_state_uk)}`,
      languages: (l) => `${esc(l.language)} — ${esc(l.level_uk)} · ${esc(l.evidence_state_uk)}`,
      credentials: (c) => `${esc(c.credential_type_uk)}: ${esc(c.title)} · ${esc(c.evidence_state_uk)}`,
    }[coll];
    const formFn = { educations: eduForm, experiences: expForm, activities: actForm, languages: langForm, credentials: credForm }[coll];
    document.getElementById("ap-body").innerHTML = `
      <div class="pk-list" id="ap-${coll}">
        ${rows.map((r) => `<div class="pk-row"><span>${labelFor(r)}</span><button class="mini" data-e="${r.id}">Ред.</button><button class="mini" data-d="${r.id}">×</button></div>`).join("") || `<p class="muted">Порожньо.</p>`}
        <div id="ap-form-${coll}"></div>
        <button class="btn secondary" id="ap-add-${coll}">+ Додати</button>
      </div>`;
    document.getElementById(`ap-add-${coll}`).onclick = () => admForm(coll, formFn, null);
    document.querySelectorAll(`#ap-${coll} [data-e]`).forEach((b) => b.onclick = () => admForm(coll, formFn, rows.find((r) => r.id === b.dataset.e)));
    document.querySelectorAll(`#ap-${coll} [data-d]`).forEach((b) => b.onclick = () => act(async () => {
      _ap = await admin(`/admin/persons/${_ap.id}/${coll}/${b.dataset.d}`, { method: "DELETE" }); admRender();
    }));
  }
  function admForm(coll, formFn, row) {
    document.getElementById(`ap-form-${coll}`).innerHTML = `<div class="pk-card">${formFn(row || {})}<button class="btn" id="ap-s">${row ? "Зберегти" : "Додати"}</button><button class="btn secondary" id="ap-c">Скасувати</button></div>`;
    document.getElementById("ap-c").onclick = () => admRender();
    document.getElementById("ap-s").onclick = () => act(async () => {
      const body = ADM_COLLECT[coll]();
      _ap = row
        ? await admin(`/admin/persons/${_ap.id}/${coll}/${row.id}`, { method: "PATCH", body })
        : await admin(`/admin/persons/${_ap.id}/${coll}`, { method: "POST", body });
      toast("Збережено"); admRender();
    });
  }
  const ADM_COLLECT = { ...COLLECT };
  // admin form ids differ from user (e- vs different prefixes) -- reuse user COLLECT which reads e-/x-/a-/l-
  ADM_COLLECT.educations = COLLECT.educations;
  ADM_COLLECT.experiences = COLLECT.experiences;
  ADM_COLLECT.activities = COLLECT.activities;
  ADM_COLLECT.languages = COLLECT.languages;

  function admSkills() {
    const rows = _ap.skills || [];
    document.getElementById("ap-body").innerHTML = `
      <div class="pk-list">${rows.map((s) => `<div class="pk-row"><span>${esc(s.raw_input || "")} <em>(${esc(s.custom_status_uk)}${s.proficiency ? ", " + esc(s.proficiency_uk) : ""}, ${esc(s.evidence_state_uk)})</em></span><button class="mini" data-d="${s.id}">×</button></div>`).join("") || `<p class="muted">Порожньо.</p>`}</div>
      <div class="pk-card"><label class="pk-f"><span>Пошук у каталозі навичок</span><input id="ap-sk-q" placeholder="вводьте..."></label><div id="ap-sk-res"></div>
      <label class="pk-f"><span>або своя навичка</span><input id="ap-sk-raw"></label>${S("ap-sk-prof", "Рівень", PROF, "")}<button class="btn" id="ap-sk-add">+ Додати</button></div>`;
    document.querySelectorAll(".pk-list [data-d]").forEach((b) => b.onclick = () => act(async () => { _ap = await admin(`/admin/persons/${_ap.id}/skills/${b.dataset.d}`, { method: "DELETE" }); admRender(); }));
    const q = document.getElementById("ap-sk-q");
    q.oninput = async () => {
      if (q.value.trim().length < 2) { document.getElementById("ap-sk-res").innerHTML = ""; return; }
      const res = await admin(`/admin/persons/skills/search?q=${encodeURIComponent(q.value.trim())}`);
      document.getElementById("ap-sk-res").innerHTML = res.map((s) => `<button class="mini" data-id="${s.id}">${esc(s.name_uk)}</button>`).join(" ");
      document.querySelectorAll("#ap-sk-res [data-id]").forEach((b) => b.onclick = () => act(async () => {
        _ap = await admin(`/admin/persons/${_ap.id}/skills`, { method: "POST", body: { canonical_skill_id: b.dataset.id, proficiency: val("ap-sk-prof") || null } });
        toast("Додано"); admRender();
      }));
    };
    document.getElementById("ap-sk-add").onclick = () => act(async () => {
      if (!val("ap-sk-raw").trim()) return;
      _ap = await admin(`/admin/persons/${_ap.id}/skills`, { method: "POST", body: { raw_input: val("ap-sk-raw").trim(), proficiency: val("ap-sk-prof") || null } });
      toast("Додано"); admRender();
    });
  }

  return {
    screenLanding, screenBuild, screenEdit, screenCv,
    screenMyProfile, screenConfirmed, stageCvFile, evChip, skillNote,
    admScreenList, admScreenCreate, admScreenCard,
  };
})();
