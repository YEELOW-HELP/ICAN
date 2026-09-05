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

  // Founder-approved workspace navigation. slug, label, icon, [badge].
  // Future modules keep a sidebar entry (they open a real explainer/
  // future-state screen) but carry a "Незабаром" pill.
  const I = (n) => NvUI.icon(n);
  const SIDE = [
    { items: [
      ["", "Огляд", "grid"],
      ["profile", "Мій профіль", "user"],
    ]},
    { items: [
      ["scenarios", "Мої сценарії", "layers", "Незабаром"],
      ["what-if", "Що зміниться, якщо…", "sparkles", "Незабаром"],
      ["route", "Мій маршрут", "route", "Незабаром"],
      ["plan", "План дій", "checklist", "Незабаром"],
      ["progress", "Прогрес", "chart", "Незабаром"],
      ["insights", "Інсайти", "lightbulb", "Незабаром"],
      ["vacancies", "Вакансії", "briefcase", "Незабаром"],
      ["resources", "Ресурси", "book", "Незабаром"],
    ]},
    { divider: true, items: [
      ["coach", "AI Коуч", "chat", "Premium"],
      ["consultation", "Консультація", "calendar", "Незабаром"],
      ["pricing", "Тарифи", "tag"],
    ]},
  ];

  // Any module that is not wired to a real engine renders through this.
  function futureState(title, text) {
    return `<div class="future-state"><div class="nv-ico-box soft" style="margin:0 auto .5rem">${I("compass")}</div>
      <h3>${esc(title)}</h3><p>${esc(text)}</p>
      <span class="soon-tag">Незабаром</span></div>`;
  }
  function demoNote() {
    return `<p class="muted" style="font-size:.8rem;margin-top:.5rem">Приклади нижче — ілюстрація майбутнього інтерфейсу, а не розрахунок для вашого профілю.</p>`;
  }
  function exampleFlag() {
    return `<span class="demo-flag" style="background:var(--st-orange-bg);color:var(--st-orange)">Приклад результату</span>`;
  }

  /* Digital Career Profile completeness — DETERMINISTIC, qualitative
   * (no fabricated %). Rules documented in NAPRIAM_PRODUCT_UI_V1.md.
   *   I CAN  : count of non-empty factual Person KB sections
   *            (experience / education / skills / languages / activities /
   *             credentials) -> >=3 filled / 1-2 partial / 0 empty
   *   I AM   : assessment layer not built -> always "empty" for now
   *   I WANT : canonical want-fields set on MnpPerson
   *            (work_format / willing_to_relocate / work_geography) */
  const STATE_UK = { filled: "Заповнено", partial: "Частково", empty: "Не заповнено" };
  const STATE_CHIP = { filled: "chip--green", partial: "chip--orange", empty: "chip--red" };
  function stateChip(s) { return `<span class="chip ${STATE_CHIP[s]}">${STATE_UK[s]}</span>`; }

  function iCanState(p) {
    const filled = [p.experiences, p.educations, p.skills, p.languages, p.activities, p.credentials]
      .filter((a) => (a || []).length > 0).length;
    return filled >= 3 ? "filled" : filled >= 1 ? "partial" : "empty";
  }
  function iWantState(p) {
    const m = p.mobility || {};
    const set = [m.work_format && m.work_format !== "unknown",
                 m.willing_to_relocate && m.willing_to_relocate !== "unknown",
                 (m.work_geography || []).length > 0].filter(Boolean).length;
    return set >= 2 ? "filled" : set >= 1 ? "partial" : "empty";
  }
  function iAmState() { return "empty"; }

  async function render(page) {
    header().innerHTML = "";
    await MnpApi.ensureSession();
    const p = await MnpApi.request("/me/person").catch(() => null);
    if (!p || !p.id) { location.hash = "#/profile"; return; }
    try { localStorage.setItem("mnp_has_profile", "1"); } catch (e) {}
    const initials = (p.core.first_name || "?").trim().charAt(0) + (p.core.last_name || "").trim().charAt(0);

    const href = (slug) => slug === "pricing" ? "#/pricing" : `#/app${slug ? "/" + slug : ""}`;
    const navHtml = SIDE.map((s) => `
      ${s.divider ? `<div class="ws-divider"></div>` : ""}
      ${s.items.map(([slug, label, ico, badge]) =>
        `<a href="${href(slug)}" class="${slug === page ? "is-active" : ""}">${I(ico)}<span class="lbl">${esc(label)}</span>${badge ? `<span class="soon">${esc(badge)}</span>` : ""}</a>`).join("")}
    `).join("");

    const cur = SIDE.flatMap((s) => s.items).find(([slug]) => slug === page);

    root().innerHTML = `
      <div class="ws">
        <aside class="ws-side">
          <a class="ws-brand" href="#/"><b>NAPRIAM</b><span>Кар'єрний навігатор</span></a>
          <nav class="ws-nav">${navHtml}</nav>
          <div class="ws-side-foot">
            <a href="#/how">${I("book")}<span class="lbl">Довідка</span></a>
            <a href="#/profile/edit">${I("edit")}<span class="lbl">Редагувати профіль</span></a>
          </div>
        </aside>
        <div class="ws-main">
          <div class="ws-top">
            <div class="ws-top-title">${esc(cur ? cur[1] : "Огляд")}</div>
            <div class="ws-top-actions">
              <span class="ws-bell" title="Сповіщення — незабаром">${I("lightbulb")}</span>
              <a href="#/profile/me" class="ws-avatar" title="${esc(p.core.first_name || "")}">${esc(initials.toUpperCase() || "N")}</a>
            </div>
          </div>
          <div class="ws-body" id="ws-content"></div>
        </div>
      </div>`;

    (PAGES[page] || PAGES[""])(p);
  }

  const dimRow = (label, hint, state, href) => `
    <a href="${href}" class="dim-row">
      <span class="dim-label">${esc(label)} <span class="muted">· ${esc(hint)}</span></span>
      ${stateChip(state)}
      ${I("arrow")}
    </a>`;

  // "next step" is chosen ONLY from real current state — no engine.
  function nextStep(p, can, want) {
    if (can !== "filled") return ["Доповніть ваш профіль", "Додайте досвід, освіту чи навички — так підбір буде точнішим.", "#/profile/edit", "Відкрити профіль"];
    if (want === "empty") return ["Вкажіть кар'єрні цілі", "Формат роботи та готовність до переїзду — 1 хвилина.", "#/app/goals", "Вказати цілі"];
    return ["Перегляньте каталог професій", "Ознайомтеся з професіями, поки готується персональний підбір.", "#/catalog", "Відкрити каталог"];
  }

  const PAGES = {
    ""(p) {
      const can = iCanState(p), am = iAmState(p), want = iWantState(p);
      const [nsTitle, nsText, nsHref, nsCta] = nextStep(p, can, want);
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>${esc(NvUI.greeting())}${p.core.first_name && p.core.first_name !== "—" ? ", " + esc(p.core.first_name) : ""}</h1>
          <p>Ваш профіль збережено. Ось що варто зробити далі.</p>
        </div>

        <div class="nv-panel">
          <div class="panel-head">
            <div class="nv-ico-box">${I("target")}</div>
            <div><h3 style="margin:0">Ваш цифровий кар'єрний профіль</h3>
              <p class="muted" style="margin:.15rem 0 0;font-size:.88rem">Один профіль — три погляди на вас</p></div>
          </div>
          <div class="dim-list">
            ${dimRow("Я можу", "що я вже вмію", can, "#/profile/me")}
            ${dimRow("Я є", "хто я", am, "#/app/strengths")}
            ${dimRow("Я хочу", "чого я хочу", want, "#/app/goals")}
          </div>
          <a class="btn secondary" href="#/app/profile">Відкрити профіль</a>
        </div>

        <div class="ws-hero next">
          <span class="chip chip--blue">Наступний крок</span>
          <h2 style="margin:.5rem 0 .3rem">${esc(nsTitle)}</h2>
          <p class="muted">${esc(nsText)}</p>
          <a class="btn" href="${nsHref}">${esc(nsCta)}</a>
        </div>

        <div class="nv-panel">
          <div class="panel-head">
            <div class="nv-ico-box purple">${I("layers")}</div>
            <div><h3 style="margin:0">Персональні сценарії</h3>
              <p class="muted" style="margin:.15rem 0 0;font-size:.88rem">NAPRIAM змоделює варіанти вашого професійного майбутнього</p></div>
          </div>
          <p class="muted" style="font-size:.92rem">На основі «Я можу», «Я є» та «Я хочу» ви побачите кілька напрямів переходу з кроками до кожного.</p>
          <span class="soon-tag">Незабаром</span>
        </div>`;
    },

    // Digital Career Profile home — I CAN + I AM + I WANT, one Person model.
    profile(p) {
      const can = iCanState(p), am = iAmState(p), want = iWantState(p);
      const factCounts = [
        ["досвід", (p.experiences || []).length], ["освіта", (p.educations || []).length],
        ["навички", (p.skills || []).length], ["мови", (p.languages || []).length],
        ["проєкти", (p.activities || []).length], ["сертифікати", (p.credentials || []).length],
      ].filter(([, n]) => n > 0).map(([l, n]) => `${l} ${n}`).join(" · ") || "ще не заповнено";
      const combined = [can, am, want].every((s) => s === "filled") ? "filled"
        : [can, am, want].some((s) => s !== "empty") ? "partial" : "empty";
      const c = (title, hint, ico, box, state, sub, href, cta) => `
        <div class="nv-card">
          <div class="nv-ico-box ${box}">${I(ico)}</div>
          <h3 style="margin:.7rem 0 .1rem">${title}</h3>
          <div class="muted" style="font-size:.8rem;margin-bottom:.5rem">${hint}</div>
          <div style="margin-bottom:.5rem">${stateChip(state)}</div>
          <p style="color:var(--muted);font-size:.9rem;margin:0 0 .9rem;flex:1">${sub}</p>
          <a class="btn secondary" href="${href}">${cta}</a>
        </div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>Ваш цифровий кар'єрний профіль</h1>
          <p>Один профіль — три погляди. Разом вони дають точніші кар'єрні сценарії.</p>
        </div>

        <div class="nv-cards">
          ${c("Я можу", "Що я вже вмію", "briefcase", "", can, `Досвід, освіта, навички, мови${factCounts !== "ще не заповнено" ? " · " + esc(factCounts) : ""}.`, "#/profile/me", "Відкрити")}
          ${c("Я є", "Хто я", "compass", "purple", am, "Сильні сторони, стиль роботи, мотивація, цінності.", "#/app/strengths", "Дізнатися більше")}
          ${c("Я хочу", "Чого я хочу", "target", "green", want, "Формат роботи, географія, готовність до переїзду, цілі.", "#/app/goals", "Відкрити")}
        </div>

        <div class="nv-panel" style="text-align:center">
          <p style="font-size:1.05rem;margin:.2rem 0"><b>Я можу</b> &nbsp;+&nbsp; <b>Я є</b> &nbsp;+&nbsp; <b>Я хочу</b> &nbsp;→&nbsp; <span class="chip chip--purple">Точніші кар'єрні сценарії</span></p>
          <p class="muted" style="font-size:.85rem;margin:.3rem 0 .8rem">Готовність профілю: ${stateChip(combined)}</p>
          ${combined !== "filled"
            ? `<a class="btn" href="${want === "empty" ? "#/app/goals" : "#/profile/edit"}">Покращити профіль</a>`
            : `<a class="btn secondary" href="#/app">На головну</a>`}
        </div>`;
    },

    skills(p) {
      const rows = p.skills || [];
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Мої навички</h1><p>Навички та інструменти з вашого профілю. Аналіз того, яких навичок бракує для нової ролі — на наступному етапі.</p></div>
        <div class="nv-panel">
          <h3 style="margin-top:0">Підтверджені навички (${rows.length})</h3>
          <div class="chips">
            ${rows.length ? rows.map((s) => `<span class="chip chip--green">${esc(s.raw_input || "навичка")}</span>`).join("")
                          : '<p class="muted">Ще не додано. <a href="#/profile/edit">Додати навички</a></p>'}
          </div>
        </div>
        <div class="nv-panel">
          <h3 style="margin-top:0">Відсутні навички для цільової професії</h3>
          ${futureState("Яких навичок бракує", "Порівняння ваших навичок з вимогами професій запрацює після підключення персонального підбору.")}
        </div>`;
    },

    // ---- I AM : strengths / work style (VISUAL / FUTURE) ----
    strengths() {
      const block = (t, items, chipCls) => `
        <div class="nv-panel">
          <h3 style="margin-top:0">${esc(t)} <span class="demo-flag" style="background:var(--st-orange-bg);color:var(--st-orange);margin:0">Приклад</span></h3>
          <div class="chips">${items.map((x) => `<span class="chip ${chipCls}">${esc(x)}</span>`).join("")}</div>
        </div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>Дізнайтесь свої сильні сторони</h1>
          <p>Погляд «Я є»: інтереси, сильні сторони, стиль роботи та цінності — щоб точніше підбирати напрями.</p>
        </div>
        <div class="nv-panel">
          <div class="panel-head">
            <div class="nv-ico-box purple">${I("compass")}</div>
            <div><h3 style="margin:0">Коротка оцінка (~7 хвилин)</h3>
              <p class="muted" style="margin:.15rem 0 0;font-size:.88rem">Прості візуальні питання про інтереси й підхід до роботи</p></div>
          </div>
          <button class="btn is-disabled" disabled title="Функція з'явиться пізніше">Пройти тест<span class="soon-tag">Незабаром</span></button>
        </div>
        <p class="muted" style="font-size:.85rem">Нижче — приклад того, як виглядатиме ваш результат. Це не аналіз вашого профілю.</p>
        ${block("Сильні сторони", ["Аналітичне мислення", "Комунікація", "Увага до деталей"], "chip--green")}
        ${block("Стиль роботи", ["Структурований", "Командний", "Орієнтований на результат"], "chip--blue")}
        ${block("Що мотивує", ["Складні задачі", "Визнання", "Автономія"], "chip--purple")}
        ${block("Що може виснажувати", ["Рутина без сенсу", "Постійні перемикання"], "chip--orange")}
        <div class="nv-panel">
          <h3 style="margin-top:0">Ваші кар'єрні суперсили</h3>
          <p class="muted" style="font-size:.9rem">Цей блок поєднає результати тесту з фактами вашого профілю — досвідом і підтвердженими навичками.</p>
          <span class="soon-tag">Незабаром</span>
        </div>`;
    },

    // legacy route — the assessment is not built; land on the strengths screen.
    assessment(p) { location.hash = "#/app/strengths"; },

    // ---- I AM : interests & values (VISUAL / FUTURE) ----
    values() {
      const grp = (t, items) => `<div class="nv-panel"><h3 style="margin-top:0">${esc(t)}</h3>
        <div class="chips">${items.map((x) => `<span class="chip">${esc(x)}</span>`).join("")}</div></div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Інтереси та цінності</h1><p>Погляд «Я є»: що вам цікаво і що для вас важливо в роботі.</p></div>
        ${grp("Інтереси", ["Аналітика", "Робота з людьми", "Технології", "Творчість", "Організація"])}
        ${grp("Цінності", ["Стабільність", "Розвиток", "Вплив", "Баланс", "Незалежність"])}
        ${grp("Мотивація", ["Складні задачі", "Визнання", "Дохід", "Місія"])}
        ${grp("Робочі уподобання", ["Темп", "Рівень структурованості", "Командність"])}
        ${futureState("Оцінка інтересів і цінностей", "Ви зможете відзначити те, що вам відгукується, і побачити свій профіль.")}`;
    },

    // ---- I WANT : goals (PARTIAL — canonical want-fields are functional) ----
    async goals(p) {
      const m = p.mobility || {};
      const WF = [["unknown", "Не вказано"], ["onsite", "В офісі"], ["remote", "Віддалено"], ["hybrid", "Гібрид"], ["any", "Будь-який"]];
      const TRI = [["unknown", "Не вказано"], ["yes", "Так"], ["no", "Ні"]];
      const GEO = [["own_city", "Своє місто"], ["region", "Область"], ["ukraine", "Україна"], ["remote", "Віддалено"], ["other", "Інше"]];
      const opt = (list, cur) => list.map(([v, t]) => `<option value="${v}" ${v === cur ? "selected" : ""}>${esc(t)}</option>`).join("");
      const geoNow = m.work_geography || [];
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Уточніть ваші кар'єрні цілі</h1><p>Погляд «Я хочу». Частина полів уже працює й зберігається у ваш профіль.</p></div>

        <div class="nv-panel">
          <h3 style="margin-top:0">Робочі уподобання <span class="chip chip--green">Працює</span></h3>
          <div class="field"><label>Формат роботи</label><select id="g-wf">${opt(WF, m.work_format || "unknown")}</select></div>
          <div class="field"><label>Готовність до переїзду</label><select id="g-relo">${opt(TRI, m.willing_to_relocate || "unknown")}</select></div>
          <div class="field"><label>Географія роботи</label>
            <div class="chips">${GEO.map(([v, t]) => `<label class="pk-chk" style="display:inline-flex;gap:.3rem;align-items:center">
              <input type="checkbox" value="${v}" ${geoNow.includes(v) ? "checked" : ""} class="g-geo"> ${esc(t)}</label>`).join(" ")}</div>
          </div>
          <button class="btn" id="g-save">Зберегти цілі</button>
        </div>

        <div class="nv-panel">
          <h3 style="margin-top:0">Ще уточнимо пізніше <span class="soon-tag">Незабаром</span></h3>
          <div class="field"><label>Бажаний дохід (ваша ціль, не ринкова медіана)</label><input disabled placeholder="напр. 40 000 ₴/міс"></div>
          <div class="field"><label>Бажаний темп переходу</label><select disabled><option>Комфортний</option></select></div>
          <div class="field"><label>Напрями кар'єрного розвитку</label><input disabled placeholder="оберете зі списку професій"></div>
          <div class="field"><label>Пріоритети</label>
            <div class="chips">${["Швидкість переходу", "Дохід", "Стабільність", "Гнучкість", "Довгострокове зростання"].map((x) => `<span class="chip is-disabled">${x}</span>`).join("")}</div>
          </div>
          <p class="muted" style="font-size:.8rem">Ці поля з'являться, коли підключимо персональні сценарії. Ми не показуємо ринкових зарплат без перевіреного джерела.</p>
        </div>`;
      const btn = document.getElementById("g-save");
      btn.onclick = async () => {
        btn.disabled = true; btn.textContent = "Збереження…";
        try {
          const geo = [...document.querySelectorAll(".g-geo:checked")].map((c) => c.value);
          await MnpApi.request("/me/person", { method: "POST", body: {
            work_format: document.getElementById("g-wf").value,
            willing_to_relocate: document.getElementById("g-relo").value,
            work_geography: geo,
          }});
          btn.textContent = "Збережено ✓";
          setTimeout(() => { btn.disabled = false; btn.textContent = "Зберегти цілі"; }, 1500);
        } catch (e) {
          btn.disabled = false; btn.textContent = "Зберегти цілі";
          alert("Не вдалося зберегти: " + (e.message || e));
        }
      };
    },

    scenarios() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Сценарії переходу</h1><p>Три типи сценарію — залежно від того, що для вас важливіше.</p></div>
        <div class="nv-cards">
          <div class="nv-card"><span class="chip chip--blue">Найшвидший</span><p style="margin:.6rem 0 0;color:var(--muted);font-size:.9rem">Мінімум кроків до нової ролі</p></div>
          <div class="nv-card"><span class="chip chip--green">Приріст доходу</span><p style="margin:.6rem 0 0;color:var(--muted);font-size:.9rem">Найбільша зміна доходу</p></div>
          <div class="nv-card"><span class="chip chip--purple">Довгострокове зростання</span><p style="margin:.6rem 0 0;color:var(--muted);font-size:.9rem">Найкраща траєкторія на роки</p></div>
        </div>
        ${futureState("Порівняння сценаріїв", "Тут з'являться сценарії, професії, терміни та кроки — після підключення персональних рекомендацій.")}
        <div class="nv-panel">
          <span class="chip chip--purple">Оцінка кар'єрної мобільності</span>
          <h3 style="margin:.5rem 0 .3rem">Наскільки легко вам змінити напрям</h3>
          <p class="muted" style="font-size:.9rem">Один зрозумілий показник. З'явиться пізніше.</p>
          <span class="soon-tag">Незабаром</span>
        </div>`;
    },

    "what-if"(p) { PAGES.whatif(p); },
    whatif() {
      const q = (t) => `<div class="wi-q">${I("sparkles")}<span>${esc(t)}</span></div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Що зміниться, якщо…</h1><p>Перевірте, як нова навичка чи умова вплине на ваші кар'єрні можливості.</p></div>
        <div class="nv-panel">
          ${q("Що зміниться, якщо я вивчу нову навичку?")}
          ${q("Що зміниться, якщо я готовий працювати дистанційно?")}
          ${q("Що зміниться, якщо я готовий переїхати?")}
          ${q("Що зміниться, якщо я зміню професію?")}
          <div class="pk-nav" style="margin-top:1rem">
            <button class="btn is-disabled" disabled title="Функція з'явиться пізніше">Перерахувати можливості<span class="soon-tag">Незабаром</span></button>
          </div>
          <p class="muted" style="font-size:.8rem;margin-top:.6rem">Розрахунок з'явиться після підключення персональних сценаріїв. Жодних вигаданих +% чи нових професій зараз.</p>
        </div>`;
    },

    route() {
      const step = (t, now) => `<li class="${now ? "now" : ""}"><div class="t-title">${esc(t)}</div></li>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Мій маршрут</h1><p>Покроковий план від сьогодні до цілі.</p></div>
        <div class="nv-panel">
          <ul class="timeline">
            ${step("Сьогодні", true)}${step("Навички")}${step("Навчання")}${step("Практика")}${step("Перші кроки")}${step("Ціль")}
          </ul>
          <div class="empty-state" style="margin:.5rem 0 0">
            <div class="nv-ico-box soft" style="margin:0 auto .5rem">${I("route")}</div>
            <h3>Маршрут з'явиться після вибору кар'єрного сценарію</h3>
            <span class="soon-tag">Незабаром</span>
          </div>
        </div>`;
    },

    plan() {
      const col = (t) => `<div class="plan-col"><div class="plan-col-h">${esc(t)}</div>
        <div class="plan-col-b">Завдання з'являться після побудови маршруту</div></div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>План дій</h1><p>Ваш трекер кроків переходу — від сьогоднішніх дій до довгострокових.</p></div>
        <div class="plan-board">
          ${col("Сьогодні")}${col("Цього тижня")}${col("Цього місяця")}${col("Пізніше")}
        </div>
        ${futureState("Трекер завдань", "Завдання, дедлайни, пріоритети та нагадування запрацюють разом із маршрутом переходу.")}`;
    },

    progress() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Прогрес</h1><p>Виконання маршруту, серії та покращені навички.</p></div>
        <div class="nv-panel" style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap">
          <div class="progress-ring" style="--p:0" data-label="0%"></div>
          <div><h3 style="margin:0">Виконання маршруту</h3>
            <p class="muted" style="font-size:.9rem;margin:.2rem 0 0">Почнеться після побудови плану дій</p></div>
        </div>
        ${futureState("Графіки прогресу", "Тижнева динаміка, серії, віхи та покращені навички з'являться, коли ви почнете виконувати кроки.")}`;
    },

    insights() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Інсайти</h1><p>Нові можливості, прогрес за навичками та поради тижня.</p></div>
        <div class="empty-state">
          <div class="nv-ico-box soft" style="margin:0 auto .5rem">${I("lightbulb")}</div>
          <h3>Поки що тут нічого немає</h3>
          <p>Апдейти з'являться, коли ви почнете виконувати кроки плану.</p></div>`;
    },

    vacancies() {
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Вакансії</h1><p>Підбір вакансій під ваш кар'єрний профіль.</p></div>
        ${futureState("Підбір вакансій", "З'явиться разом із даними ринку праці. Жодних вигаданих вакансій чи роботодавців зараз.")}`;
    },

    resources() {
      const card = (t, ico) => `<div class="nv-card">
        <div class="nv-ico-box soft">${I(ico)}</div>
        <h3 style="margin:.6rem 0 .2rem">${esc(t)}</h3>
        <div class="card-tag"><span class="soon-tag" style="margin:0">Незабаром</span></div></div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Ресурси</h1><p>Курси, статті, шаблони та тести для розвитку навичок.</p></div>
        <div class="nv-cards" style="grid-template-columns:repeat(4,1fr)">
          ${card("Курси", "book")}${card("Статті", "doc")}${card("Шаблони", "checklist")}${card("Тести", "target")}
        </div>
        ${futureState("Бібліотека ресурсів", "Добірки навчальних матеріалів з'являться разом із маршрутами переходу.")}`;
    },

    coach() {
      const msg = (who, txt) => `<div class="chat-msg ${who}"><div class="chat-bubble">${esc(txt)}</div></div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Кар'єрний AI Коуч <span class="chip chip--purple">Premium</span></h1>
          <p>Коуч використовуватиме ваш цифровий профіль, обраний сценарій, маршрут та прогрес, щоб допомагати рухатися до цілі.</p></div>
        <div class="nv-panel chat-panel">
          <div class="chat-log">
            ${msg("bot", "Вітаю! Коли модуль запрацює, ми разом розберемо ваші сильні сторони та складемо план переходу.")}
            ${msg("bot", "Розкажіть, яка професія вас цікавить — і я підкажу, з чого почати.")}
          </div>
          <div class="chat-input">
            <input placeholder="Напишіть повідомлення…" disabled>
            <button class="btn is-disabled" disabled title="Функція з'явиться пізніше">${I("arrow")}</button>
          </div>
        </div>
        <p class="muted" style="font-size:.85rem"><span class="soon-tag" style="margin:0">Premium · Незабаром</span> — чат, бронювання сесій та нотатки.</p>`;
    },

    consultation() {
      const slot = (t) => `<button class="cons-slot" disabled>${esc(t)}</button>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header"><h1>Консультація</h1><p>Жива розмова з кар'єрним консультантом: дата, час, формат.</p></div>
        <div class="ws-grid2">
          <div class="nv-panel">
            <h3 style="margin-top:0">Оберіть час</h3>
            <div class="cons-grid">${["Пн 10:00", "Пн 14:00", "Вт 11:00", "Вт 16:00", "Ср 12:00", "Чт 15:00"].map(slot).join("")}</div>
          </div>
          <div class="nv-panel">
            <h3 style="margin-top:0">Деталі</h3>
            <div class="field"><label>Формат</label><select disabled><option>Відео-дзвінок (45 хв)</option></select></div>
            <div class="field"><label>Консультант</label><select disabled><option>Буде призначено</option></select></div>
            <button class="btn is-disabled" disabled title="Функція з'явиться пізніше">Підтвердити запис<span class="soon-tag">Незабаром</span></button>
          </div>
        </div>`;
    },
  };

  return { render };
})();
