/* NAPRIAM — post-profile career workspace shell (Founder Visual Architecture
 * Addendum). ONE design system with the public site, but its own chrome
 * (left sidebar + slim top bar). Dashboard is a visual "what next" summary;
 * every development module (Scenarios / What-if / Route / Action plan /
 * Progress / Insights / Vacancies / Resources / Coach / Consultation) is a
 * VISUAL / FUTURE state — clearly non-live, no fabricated numbers, no
 * backend logic. Functional data shown here is only the real canonical
 * MnpPerson (profile + skills). */
const MnpWorkspace = (() => {
  const root = () => document.getElementById("app");
  const header = () => document.getElementById("site-header");
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const SIDE = [
    { grp: "" , items: [
      ["", "Головна", "🏠"],
      ["profile", "Профіль", "👤"],
      ["skills", "Мої навички", "🧩"],
    ]},
    { grp: "Розвиток кар'єри", items: [
      ["scenarios", "Сценарії", "🗂️"],
      ["plan", "План дій", "📋"],
      ["progress", "Прогрес", "📈"],
      ["vacancies", "Вакансії для мене", "💼"],
      ["insights", "Інсайти", "✨"],
    ]},
  ];
  const TOP = [["scenarios", "Можливості"], ["resources", "Ресурси"], ["route", "Маршрути"], ["coach", "Підтримка"]];

  // Any module that is not wired to a real engine renders through this.
  function futureState(title, text) {
    return `<div class="future-state"><div class="ico">🧭</div>
      <h3>${esc(title)}</h3><p>${esc(text)}</p>
      <span class="soon-tag">Незабаром</span></div>`;
  }
  function demoNote() {
    return `<p class="muted" style="font-size:.8rem;margin-top:.5rem">Приклади нижче — ілюстрація майбутнього інтерфейсу, а не розрахунок для вашого профілю.</p>`;
  }

  async function render(page) {
    header().innerHTML = "";
    await MnpApi.ensureSession();
    const p = await MnpApi.request("/me/person").catch(() => null);
    if (!p || !p.id) { location.hash = "#/profile"; return; }
    const initials = (p.core.first_name || "?").trim().charAt(0) + (p.core.last_name || "").trim().charAt(0);

    const navHtml = SIDE.map((s) => `
      ${s.grp ? `<div class="grp">${esc(s.grp)}</div>` : ""}
      ${s.items.map(([slug, label, ico]) =>
        `<a href="#/app${slug ? "/" + slug : ""}" class="${slug === page ? "is-active" : ""}"><span class="ico">${ico}</span>${esc(label)}</a>`).join("")}
    `).join("");

    root().innerHTML = `
      <div class="ws">
        <aside class="ws-side">
          <a class="ws-brand" href="#/"><b>NAPRIAM</b><span>Кар'єрний навігатор</span></a>
          <nav class="ws-nav">${navHtml}</nav>
          <div class="ws-side-foot">
            <a href="#/pricing" class="premium">NAPRIAM Premium</a>
            <a href="#/app/coach">Коуч поруч</a>
            <a href="#/how">Допомога</a>
            <a href="#/profile/edit">Налаштування профілю</a>
          </div>
        </aside>
        <div class="ws-main">
          <div class="ws-top">
            <div class="ws-top-nav">${TOP.map(([s, t]) => `<a href="#/app/${s}">${esc(t)}</a>`).join("")}</div>
            <div class="ws-top-actions">
              <span title="Сповіщення — незабаром">🔔</span>
              <a href="#/profile/me" class="ws-avatar" title="${esc(p.core.first_name || "")}">${esc(initials.toUpperCase() || "🙂")}</a>
            </div>
          </div>
          <div class="ws-body" id="ws-content"></div>
        </div>
      </div>`;

    (PAGES[page] || PAGES[""])(p);
  }

  const PAGES = {
    ""(p) {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>Вітаємо, ${esc(p.core.first_name || "")}</h1>
          <p>Ваш профіль збережено. Ось що варто зробити далі.</p>
        </div>

        <div class="ws-hero next">
          <span class="chip chip--blue">Наступна найкраща дія</span>
          <h2 style="margin:.5rem 0 .3rem">Персональна рекомендація з'явиться після підключення підбору</h2>
          <p class="muted">Коли запрацює персональний підбір професій, тут буде конкретний крок: урок, навичка або дія — з очікуваним ефектом і часом.</p>
          <span class="soon-tag">Незабаром</span>
        </div>

        <div class="ws-grid2">
          <div class="nv-panel">
            <h3 style="margin-top:0">Карта сценаріїв</h3>
            <p class="muted" style="font-size:.9rem">Ваш профіль → можливі цільові професії.</p>
            ${futureState("Карта переходів", "Побудується після підключення персонального підбору.")}
          </div>
          <div class="nv-panel">
            <h3 style="margin-top:0">Активний маршрут</h3>
            ${futureState("Маршрут переходу", "З'явиться, коли ви оберете цільову професію та сценарій.")}
          </div>
          <div class="nv-panel">
            <h3 style="margin-top:0">Щотижневий апдейт</h3>
            <div class="empty-state"><div class="ico">📭</div><h3>Поки що порожньо</h3><p>Апдейти з'являться, коли ви почнете виконувати кроки плану.</p></div>
          </div>
          <div class="nv-panel">
            <h3 style="margin-top:0">Ваш прогрес</h3>
            <div style="display:flex;align-items:center;gap:1rem">
              <div class="progress-ring" style="--p:0" data-label="0%"></div>
              <p class="muted" style="font-size:.9rem;margin:0">Виконання маршруту почнеться після побудови плану дій.</p>
            </div>
          </div>
        </div>

        <div class="nv-panel">
          <span class="chip chip--purple">Premium</span>
          <h3 style="margin:.5rem 0 .3rem">Коуч поруч</h3>
          <p class="muted" style="font-size:.9rem">Персональний кар'єрний коуч, сесії та нотатки.</p>
          <a class="btn secondary is-disabled" aria-disabled="true">Дізнатися більше<span class="soon-tag">Незабаром</span></a>
        </div>`;
    },

    profile(p) {
      const m = p.mobility || {};
      // callers pass already-escaped text (+ trusted chip HTML) — do not re-escape here
      const rowL = (k, v) => `<li><span class="k">${k}</span><br>${v || "—"}</li>`;
      const card = (t, rows) => `<div class="nv-prof-card"><h3>${esc(t)}</h3><ul>${rows.length ? rows.join("") : '<li class="muted">Немає даних</li>'}</ul></div>`;
      const ev = (s) => (MnpPersonKB.evChip ? MnpPersonKB.evChip(s) : "");
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Профіль</h1><p>Людиночитане подання вашого кар'єрного профілю.</p></div>
        <div class="pk-nav" style="margin:0 0 1rem">
          <a class="btn" href="#/profile/edit">Редагувати</a>
          <a class="btn secondary" href="#/profile/cv">Оновити з CV</a>
        </div>
        <div class="nv-prof-grid">
          ${card("Особисте", [
            rowL("Ім'я", `${esc(p.core.first_name || "")} ${esc(p.core.last_name || "")}`),
            rowL("Місто", [p.core.city, p.core.region, p.core.country].filter(Boolean).map(esc).join(", ") || "—"),
            rowL("Контакти", [p.core.phone, p.core.email, p.core.telegram_username].filter(Boolean).map(esc).join(" · ") || "—"),
          ])}
          ${card("Досвід роботи", (p.experiences || []).map((x) => rowL(esc(x.raw_job_title) + ev(x.evidence_state), esc(x.company_name || "—"))))}
          ${card("Освіта", (p.educations || []).map((e) => rowL(esc(e.education_level_uk), esc(e.institution_name || "—") + (e.end_year ? " · " + e.end_year : ""))))}
          ${card("Мови", (p.languages || []).map((l) => rowL(esc(l.language), esc(l.level_uk))))}
          ${card("Сертифікати", (p.credentials || []).map((c) => rowL(esc(c.title), esc(c.credential_type_uk))))}
          ${card("Проєкти та активності", (p.activities || []).map((a) => rowL(esc(a.title), esc(a.activity_type_uk))))}
          ${card("Мобільність", [
            rowL("Формат роботи", esc(m.work_format_uk || "—")),
            rowL("Посвідчення водія", esc(m.has_driver_license_uk || "—")),
            rowL("Готовність до переїзду", esc(m.willing_to_relocate_uk || "—")),
          ])}
        </div>`;
    },

    skills(p) {
      const rows = p.skills || [];
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Мої навички</h1><p>Навички та інструменти з вашого профілю. Аналіз відсутніх навичок (skill gap) — на наступному етапі.</p></div>
        <div class="nv-panel">
          <h3 style="margin-top:0">Підтверджені навички (${rows.length})</h3>
          <div class="chips">
            ${rows.length ? rows.map((s) => `<span class="chip chip--green">${esc(s.raw_input || "навичка")}</span>`).join("")
                          : '<p class="muted">Ще не додано. <a href="#/profile/edit">Додати навички</a></p>'}
          </div>
        </div>
        <div class="nv-panel">
          <h3 style="margin-top:0">Відсутні навички для цільової професії</h3>
          ${futureState("Skill gap", "Порівняння ваших навичок з вимогами професій запрацює після підключення персонального підбору.")}
        </div>`;
    },

    scenarios() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Сценарії переходу</h1><p>Оберіть свій сценарій — від найшвидшого до найбільшого довгострокового потенціалу.</p></div>
        <div class="metric-grid" style="grid-template-columns:repeat(3,1fr)">
          <div class="metric-card"><span class="chip chip--blue">Найшвидший</span><div class="sub" style="margin-top:.6rem">Мінімум кроків до нової ролі</div></div>
          <div class="metric-card"><span class="chip chip--green">Найкращий приріст доходу</span><div class="sub" style="margin-top:.6rem">Максимальна зміна доходу</div></div>
          <div class="metric-card"><span class="chip chip--purple">Довгостроковий потенціал</span><div class="sub" style="margin-top:.6rem">Найкраща траєкторія на роки</div></div>
        </div>
        ${futureState("Порівняння сценаріїв", "Сценарії, професії, терміни та кроки з'являться після підключення персонального підбору та маршрутів.")}
        <div class="nv-panel">
          <span class="chip chip--purple">Career Mobility Score</span>
          <h3 style="margin:.5rem 0 .3rem">Оцінка кар'єрної мобільності</h3>
          <p class="muted" style="font-size:.9rem">Єдиний показник того, наскільки легко вам змінити напрям. Методологію затвердить окреме рішення Founder.</p>
          <span class="soon-tag">Незабаром</span>
        </div>`;
    },

    whatif() {
      const chip = (t) => `<button class="chip is-disabled" disabled style="cursor:not-allowed">+ ${esc(t)}</button>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Що, якщо?</h1><p>Подивіться, як нова навичка чи умова змінює ваші можливості.</p></div>
        <div class="nv-panel">
          <p class="muted" style="font-size:.9rem;margin-top:0">Оберіть зміни (демо):</p>
          <div class="chips">${["SQL", "Англійська B2", "Power BI", "Переїзд", "Сертифікат"].map(chip).join("")}</div>
          ${futureState("Результат симуляції", "Двигун «Що, якщо?» порахує ефект після підключення персонального підбору. Жодних вигаданих +% чи нових професій зараз.")}
        </div>`;
    },

    route() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Маршрут переходу</h1><p>Покроковий план від поточної точки до цільової професії.</p></div>
        ${futureState("Конструктор маршруту", "З'явиться після того, як ви оберете цільову професію та сценарій.")}`;
    },

    plan() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Ваш план дій</h1><p>Тижневий roadmap з кроками навчання та дій.</p></div>
        <div class="metric-grid">
          <div class="metric-card"><span class="label">Загальний прогрес</span><div class="value">0%</div></div>
          <div class="metric-card"><span class="label">Орієнтовна тривалість</span><div class="value">—</div></div>
          <div class="metric-card"><span class="label">Темп</span><div class="value">—</div></div>
          <div class="metric-card"><span class="label">Наступний крок</span><div class="value">—</div></div>
        </div>
        <ul class="timeline">
          <li class="now"><div class="t-title">Тиждень 1–2</div><div class="t-meta">Кроки з'являться після побудови маршруту</div></li>
          <li><div class="t-title">Тиждень 3–4</div><div class="t-meta">—</div></li>
          <li><div class="t-title">Тиждень 5–6</div><div class="t-meta">—</div></li>
        </ul>
        ${futureState("Завдання плану", "Завдання, дедлайни, пріоритети, календар і нагадування запрацюють разом із маршрутом переходу.")}`;
    },

    progress() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Ваш прогрес</h1><p>Виконання маршруту, серії та покращені навички.</p></div>
        <div class="ws-grid2">
          <div class="nv-panel" style="display:flex;align-items:center;gap:1.25rem">
            <div class="progress-ring" style="--p:0" data-label="0%"></div>
            <div><h3 style="margin:0">Маршрут</h3><p class="muted" style="font-size:.9rem;margin:.2rem 0 0">Почнеться після побудови плану дій</p></div>
          </div>
          <div class="nv-panel">
            <div class="metric-grid" style="grid-template-columns:1fr 1fr;margin:0">
              <div class="metric-card"><span class="label">Серія</span><div class="value">0</div><div class="sub">днів поспіль</div></div>
              <div class="metric-card"><span class="label">Виконано завдань</span><div class="value">0</div></div>
            </div>
          </div>
        </div>
        ${futureState("Графіки прогресу", "Тижнева динаміка, віхи та покращені навички з'являться, коли ви почнете виконувати кроки.")}`;
    },

    insights() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Щотижневий апдейт</h1><p>Нові можливості, зменшений skill gap та поради тижня.</p></div>
        <div class="empty-state"><div class="ico">📭</div><h3>Апдейтів поки немає</h3>
          <p>Персональні події з'являться, коли запрацює підбір і ви почнете виконувати план. Ми не показуємо вигаданих подій.</p></div>`;
    },

    vacancies() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Вакансії для мене</h1><p>Підбір вакансій під ваш профіль.</p></div>
        ${futureState("Підбір вакансій", "Модуль ринку праці (Market KB) ще не підключено. Жодних вигаданих вакансій чи роботодавців.")}`;
    },

    resources() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Ресурси</h1><p>Курси, статті, шаблони та тести для розвитку навичок.</p></div>
        <div class="metric-grid">
          ${["Курси", "Статті", "Шаблони", "Тести"].map((t) => `<div class="metric-card"><div class="value" style="font-size:1.1rem">${t}</div><div class="sub">Незабаром</div></div>`).join("")}
        </div>
        ${futureState("Бібліотека ресурсів", "Добірки навчальних матеріалів з'являться разом із маршрутами переходу.")}`;
    },

    coach() {
      const tab = (t, on) => `<button class="adm-tab ${on ? "is-active" : ""}" disabled style="cursor:not-allowed">${esc(t)}</button>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Коуч поруч <span class="chip chip--purple">Premium</span></h1><p>Персональний кар'єрний коуч, сесії та нотатки.</p></div>
        <div class="adm-tabs">${tab("Чат", true)}${tab("Сесії")}${tab("Нотатки")}${tab("Питання")}</div>
        ${futureState("Коуч-модуль", "Чат з коучем, бронювання сесій та рекомендації — у складі NAPRIAM Premium. Backend коуча ще не підключено.")}
        <a class="btn secondary is-disabled" aria-disabled="true" href="#/app/consultation">Запланувати консультацію<span class="soon-tag">Незабаром</span></a>`;
    },

    consultation() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Заплануйте консультацію</h1><p>Оберіть дату, час, коуча та формат.</p></div>
        <div class="ws-grid2">
          <div class="nv-panel"><h3 style="margin-top:0">Календар</h3><div class="empty-state"><div class="ico">📅</div><p>Вибір дати з'явиться після підключення розкладу коучів.</p></div></div>
          <div class="nv-panel"><h3 style="margin-top:0">Деталі</h3>
            <div class="field"><label>Формат</label><select disabled><option>Відео-дзвінок</option></select></div>
            <div class="field"><label>Коуч</label><select disabled><option>—</option></select></div>
            <button class="btn is-disabled" disabled>Підтвердити<span class="soon-tag">Незабаром</span></button>
          </div>
        </div>`;
    },
  };

  return { render };
})();
