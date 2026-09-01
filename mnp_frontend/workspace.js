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
    { grp: "Цифровий профіль", items: [
      ["strengths", "Сильні сторони", "💪"],
      ["values", "Інтереси та цінності", "🎯"],
      ["goals", "Цілі", "🧭"],
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
      const can = iCanState(p), am = iAmState(p), want = iWantState(p);
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>Вітаємо, ${esc(p.core.first_name || "")}</h1>
          <p>Ваш профіль збережено. Ось що варто зробити далі.</p>
        </div>

        <div class="nv-panel">
          <h3 style="margin-top:0">Ваш цифровий кар'єрний профіль</h3>
          <div class="chips">
            <a href="#/profile/me" class="chip ${STATE_CHIP[can]}" style="text-decoration:none">Я можу — ${STATE_UK[can]}</a>
            <a href="#/app/strengths" class="chip ${STATE_CHIP[am]}" style="text-decoration:none">Я є — ${STATE_UK[am]}</a>
            <a href="#/app/goals" class="chip ${STATE_CHIP[want]}" style="text-decoration:none">Я хочу — ${STATE_UK[want]}</a>
          </div>
          <a class="btn secondary" href="#/app/profile" style="margin-top:.7rem">Відкрити цифровий профіль</a>
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
            <div class="empty-state"><div class="ico">📭</div><h3>Поки що тут нічого немає</h3><p>Апдейти з'являться, коли ви почнете виконувати кроки плану.</p></div>
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
          <button class="btn secondary is-disabled" disabled>Дізнатися більше<span class="soon-tag">Незабаром</span></button>
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
      const c = (title, hint, ico, state, sub, href, cta) => `
        <div class="nv-card">
          <div class="ico">${ico}</div>
          <h3 style="margin:.5rem 0 .1rem">${title}</h3>
          <div class="muted" style="font-size:.8rem;margin-bottom:.4rem">${hint}</div>
          <div style="margin-bottom:.5rem">${stateChip(state)}</div>
          <p style="color:var(--muted);font-size:.9rem;margin:0 0 .8rem">${sub}</p>
          <a class="btn secondary" href="${href}">${cta}</a>
        </div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>Ваш цифровий кар'єрний профіль</h1>
          <p>Один профіль — три погляди. Разом вони дають точніші кар'єрні сценарії.</p>
        </div>

        <div class="nv-cards">
          ${c("Я можу", "Що я вже вмію", "🛠️", can, `Факти: ${esc(factCounts)}.`, "#/profile/me", "Відкрити")}
          ${c("Я є", "Що мені підходить", "🧭", am, "Сильні сторони, стиль роботи, мотивація.", "#/app/strengths", "Дізнатися більше")}
          ${c("Я хочу", "Чого я хочу", "🎯", want, "Формат роботи, готовність до переїзду, цілі.", "#/app/goals", "Відкрити")}
        </div>

        <div class="nv-panel" style="text-align:center">
          <p style="font-size:1.05rem;margin:.2rem 0"><b>Я можу</b> &nbsp;+&nbsp; <b>Я є</b> &nbsp;+&nbsp; <b>Я хочу</b> &nbsp;→&nbsp; <span class="chip chip--purple">Точніші кар'єрні сценарії</span></p>
          <p class="muted" style="font-size:.85rem;margin:.3rem 0 .8rem">Готовність профілю: ${stateChip(combined)}</p>
          ${combined !== "filled"
            ? `<a class="btn" href="${want === "empty" ? "#/app/goals" : "#/profile/edit"}">Покращити профіль</a>`
            : `<a class="btn secondary" href="#/app">На головну</a>`}
        </div>

        <div class="nv-panel">
          <h3 style="margin-top:0">Ваші персональні сценарії</h3>
          <div class="future-state" style="margin:0">
            <div class="ico">🗺️</div>
            <p>Після заповнення профілю тут з'являться ваші персональні кар'єрні сценарії.</p>
            <span class="soon-tag">Незабаром</span>
          </div>
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
    strengths(p) {
      const started = sessionStorage.getItem("mnp_demo_assessment") === "done";
      const block = (t, items, chipCls) => `
        <div class="nv-panel">
          <h3 style="margin-top:0">${esc(t)}</h3>
          <div class="chips">${items.map((i) => `<span class="chip ${chipCls}">${esc(i)}</span>`).join("")}</div>
        </div>`;
      document.getElementById("ws-content").innerHTML = `
        <div class="page-header">
          <h1>Ваші сильні сторони та стиль роботи</h1>
          <p>Погляд «Я є»: який тип роботи вам підходить. Ґрунтовна оцінка — попереду.</p>
        </div>
        <div class="nv-panel">
          <span class="chip chip--blue">Тест сильних сторін та інтересів</span>
          <h3 style="margin:.5rem 0 .3rem">Пройдіть коротку оцінку (~7 хвилин)</h3>
          <p class="muted" style="font-size:.9rem">Прості візуальні питання. Результат допоможе точніше підбирати напрями.</p>
          <a class="btn" href="#/app/assessment">${started ? "Пройти ще раз" : "Почати"}</a>
        </div>
        ${started ? exampleFlag() : ""}
        ${started ? `
          ${block("Ваші сильні сторони", ["Аналітичне мислення", "Комунікація", "Увага до деталей"], "chip--green")}
          ${block("Ваш стиль роботи", ["Структурований", "Командний", "Орієнтований на результат"], "chip--blue")}
          ${block("Що вас мотивує", ["Складні задачі", "Визнання", "Автономія"], "chip--purple")}
          ${block("Що може виснажувати", ["Рутина без сенсу", "Постійні перемикання"], "chip--orange")}
          <div class="nv-panel">
            <h3 style="margin-top:0">Ваші кар'єрні суперсили</h3>
            <p class="muted" style="font-size:.9rem">Цей блок поєднає результати тесту з фактами вашого профілю — досвідом і підтвердженими навичками.</p>
            <div class="chips"><span class="chip chip--purple">Переконувати та домовлятися</span><span class="chip chip--purple">Розбиратися в даних</span></div>
            <span class="soon-tag">Незабаром</span>
          </div>
          <p class="muted" style="font-size:.8rem">Це приклад того, як виглядатиме результат. Демо-відповіді не зберігаються у профіль.</p>
        ` : futureState("Результат оцінки", "Тут з'являться ваші сильні сторони, стиль роботи та мотивація після проходження тесту.")}`;
    },

    // ---- I AM : the assessment itself (frontend-only demo, nothing persisted) ----
    assessment() {
      const QS = [
        ["Що вам більше подобається робити?",
          "Розібратися в цифрах і знайти закономірність",
          "Поговорити з людиною і допомогти вирішити проблему"],
        ["Як ви радше працюєте над задачею?",
          "За чітким планом і покроково",
          "Гнучко, підлаштовуючись під ситуацію"],
        ["Що приносить більше задоволення?",
          "Довести справу до бездоганного результату",
          "Швидко запустити і покращувати на ходу"],
      ];
      let i = 0;
      const el = document.getElementById("ws-content");
      const step = () => {
        if (i >= QS.length) {
          sessionStorage.setItem("mnp_demo_assessment", "done");
          el.innerHTML = `
            <div class="page-header"><h1>Дякуємо!</h1><p>Це демо-версія тесту. Результати не зберігаються у ваш профіль.</p></div>
            ${exampleFlag()}
            <div class="nv-panel"><p>Перегляньте приклад того, як виглядатиме результат.</p>
              <a class="btn" href="#/app/strengths">Переглянути приклад результату</a></div>`;
          return;
        }
        const [q, a, b] = QS[i];
        el.innerHTML = `
          <div class="page-header"><h1>Тест сильних сторін</h1><p>Питання ${i + 1} з ${QS.length} · ~7 хвилин · демо</p></div>
          <div class="nv-panel">
            <h3 style="margin-top:0">${esc(q)}</h3>
            <div class="pk-nav" style="flex-direction:column;align-items:stretch">
              <button class="btn secondary" data-a>A. ${esc(a)}</button>
              <button class="btn secondary" data-b>B. ${esc(b)}</button>
            </div>
          </div>
          <p class="muted" style="font-size:.8rem">Демонстрація UX. Відповіді нікуди не надсилаються, бали не рахуються.</p>`;
        el.querySelector("[data-a]").onclick = () => { i++; step(); };
        el.querySelector("[data-b]").onclick = () => { i++; step(); };
      };
      step();
    },

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
        <div class="page-header"><h1>Щотижневий апдейт</h1><p>Нові можливості, прогрес за навичками та поради тижня.</p></div>
        <div class="empty-state"><div class="ico">📭</div><h3>Поки що тут нічого немає</h3>
          <p>Апдейти з'являться, коли ви почнете виконувати кроки плану.</p></div>`;
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
        <a class="btn secondary" href="#/app/consultation">Як працюватимуть консультації</a>`;
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
