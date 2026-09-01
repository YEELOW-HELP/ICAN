// NAPRIAM — customer product frontend. Plain JS, hash router, no build step.
// Phase 1 scope: public shell (Home / How it works / About / Login-future /
// Opportunities-future), Person KB flows (person.js), Career KB explorer.
// Personalized Matching is Phase 2 — the old match/questionnaire screens are
// kept reachable by direct URL but are not surfaced in the product.

const App = (() => {
  const root = document.getElementById("app");
  const header = document.getElementById("site-header");

  const FEASIBILITY_LABELS = {
    ready_now: "Можете почати зараз", near_ready: "Майже готові", reachable: "Досяжно",
    long_transition: "Тривалий перехід", blocked: "Заблоковано",
  };
  const DISTANCE_LABELS = {
    d0_same_career: "Та сама професія", d1_progression: "Кар'єрне зростання", d2_adjacent: "Суміжний напрям",
    d3_transferable: "Перенесення навичок", d4_career_change: "Зміна професії", d5_fundamental_retraining: "Повне перенавчання",
  };
  const COMPONENT_LABELS = {
    skill_fit: "Навички", experience_transfer: "Досвід", knowledge_fit: "Знання", preference_fit: "Уподобання",
    values_fit: "Цінності", market_attractiveness: "Привабливість ринку", income_potential: "Потенціал доходу",
    transition_cost: "Вартість переходу",
  };

  function bandBadge(band) {
    const b = band || "insufficient";
    const label = { high: "Високо", medium: "Середньо", low: "Низько", insufficient: "Недостатньо даних" }[b];
    return `<span class="badge ${b}">${label}</span>`;
  }
  function feasibilityBadge(status) {
    return `<span class="badge feasibility-${status}">${FEASIBILITY_LABELS[status] || status}</span>`;
  }
  function setLoading() { root.innerHTML = `<div class="loading">Завантаження...</div>`; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }
  function showError(err) {
    root.innerHTML = `<div class="error-box">Сталася помилка: ${esc(err.message || err)}</div><a href="#/" class="btn">На головну</a>`;
  }

  function onClickSafely(button, handler) {
    button.addEventListener("click", async () => {
      let errorBox = button.parentElement.querySelector(".btn-error-box");
      if (errorBox) errorBox.remove();
      button.disabled = true;
      const originalText = button.textContent;
      button.textContent = "Зачекайте...";
      try { await handler(); }
      catch (e) {
        errorBox = document.createElement("div");
        errorBox.className = "error-box btn-error-box";
        errorBox.style.marginTop = "0.75rem";
        errorBox.textContent = `Не вдалося виконати дію: ${e.message || e}`;
        button.insertAdjacentElement("afterend", errorBox);
      } finally { button.disabled = false; button.textContent = originalText; }
    });
  }

  // --- Global product header ------------------------------------------
  // Hidden entirely on admin routes — admin is a separate internal tool.
  const NAV = [
    ["how", "Як це працює"],
    ["catalog", "Професії"],
    ["opportunities", "Можливості"],
    ["about", "Про нас"],
  ];

  function renderHeader() {
    const hash = location.hash || "#/";
    // Admin has its own (none) chrome; the post-profile workspace draws its
    // own sidebar + top bar and clears this header itself.
    if (hash.startsWith("#/admin") || hash.startsWith("#/app")) { header.innerHTML = ""; return; }
    const [, path] = hash.match(/^#\/([^/]*)/) || [null, ""];
    const hasSession = !!localStorage.getItem("mnp_session_token");
    header.innerHTML = `
      <a class="nv-brand" href="#/"><b>NAPRIAM</b><span>Кар'єрний навігатор</span></a>
      <nav class="nv-nav">
        ${NAV.map(([p, t]) => `<a href="#/${p}" class="${p === path ? "is-active" : ""}">${t}</a>`).join("")}
      </nav>
      <div class="nv-actions">
        <button class="btn ghost is-disabled" disabled title="Виробнича авторизація з'явиться пізніше">Увійти<span class="soon-tag">Незабаром</span></button>
        ${hasSession ? `<a class="btn secondary" href="#/app">Мій профіль</a>` : ""}
        <a class="btn" href="#/profile">Створити профіль</a>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Home
  // ===================================================================
  function screenHome() {
    root.innerHTML = `
      <section class="nv-hero">
        <div>
          <h1>Ким ви можете<br>працювати далі?</h1>
          <p class="lead">NAPRIAM перетворює ваш реальний досвід і навички на нові кар'єрні можливості та зрозумілий план переходу.</p>
          <div class="nv-drop" id="home-drop">
            <strong>Перетягніть сюди ваш CV</strong>
            <p>PDF, DOCX або TXT</p>
            <div style="margin-top:.8rem">
              <a class="btn btn-lg" href="#/profile/cv">Завантажити CV</a>
              <a class="btn secondary btn-lg" href="#/profile/build">Заповнити вручну</a>
            </div>
            <div style="margin-top:.6rem">
              <button class="btn ghost is-disabled" disabled>Імпортувати LinkedIn<span class="soon-tag">Незабаром</span></button>
            </div>
          </div>
        </div>
        <div class="nv-preview">
          <span class="demo-flag">Приклад результату</span>
          <p style="margin:.2rem 0 .8rem;font-weight:600">Так виглядатимуть ваші можливості</p>
          <div class="nv-preview-row"><b>Аналітик даних</b><span>суміжний напрям</span></div>
          <div class="nv-preview-row"><b>Керівник проєктів</b><span>кар'єрне зростання</span></div>
          <div class="nv-preview-row"><b>Продуктовий аналітик</b><span>перенесення навичок</span></div>
          <p class="nv-preview-note">Це ілюстрація майбутнього результату, а не розрахунок для вашого профілю. Персональний підбір з'явиться на наступному етапі.</p>
        </div>
      </section>

      <div class="nv-cards">
        <div class="nv-card"><div class="ico">🎯</div><h3>Знайдемо близькі професії</h3><p>Професії, куди реально перейти з вашим досвідом. З'явиться на наступному етапі.</p></div>
        <div class="nv-card"><div class="ico">🧩</div><h3>Покажемо skill gap</h3><p>Чого бракує для нової ролі та що вже підтверджено. З'явиться на наступному етапі.</p></div>
        <div class="nv-card"><div class="ico">🗺️</div><h3>Побудуємо маршрут переходу</h3><p>Зрозумілі кроки від поточної точки до цілі. З'явиться на наступному етапі.</p></div>
      </div>

      <section class="nv-panel">
        <h2 style="margin-top:0">Що вже працює зараз</h2>
        <p class="lead" style="font-size:1rem">Створіть кар'єрний профіль із CV або вручну, перевірте розпізнані факти — і одразу переглядайте каталог професій.</p>
        <a class="btn" href="#/profile">Створити профіль</a>
        <a class="btn secondary" href="#/catalog">Переглянути професії</a>
      </section>`;

    // drag & drop on the hero drop-zone -> hand off to the CV flow
    const drop = document.getElementById("home-drop");
    if (drop) {
      ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
      ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("drag")));
      drop.addEventListener("drop", (e) => {
        e.preventDefault();
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
          MnpPersonKB.stageCvFile(e.dataTransfer.files[0]);
          location.hash = "#/profile/cv";
        }
      });
    }
  }

  // ===================================================================
  // PUBLIC — How it works
  // ===================================================================
  function screenHowItWorks() {
    root.innerHTML = `
      <div class="nv-narrow">
        <h1>Як працює NAPRIAM</h1>
        <p class="lead">Чотири кроки від вашого досвіду до зрозумілого плану. Зараз працюють кроки 1–2; кроки 3–4 з'являться на наступних етапах.</p>
      </div>
      <div class="nv-steps-big">
        <div class="nv-step"><div class="num">1</div><h3>Завантажте CV або заповніть профіль</h3><p>PDF, DOCX, TXT — або крок за кроком вручну.</p></div>
        <div class="nv-step"><div class="num">2</div><h3>Підтвердіть ваші факти та навички</h3><p>Ви перевіряєте кожен запис — нічого не зберігається без підтвердження.</p></div>
        <div class="nv-step"><div class="num">3</div><h3>Отримайте близькі професії та skill gap</h3><p>Персональний підбір. <span class="soon-tag">Незабаром</span></p></div>
        <div class="nv-step"><div class="num">4</div><h3>Побудуйте маршрут переходу</h3><p>Кроки навчання й дій. <span class="soon-tag">Незабаром</span></p></div>
      </div>
      <div class="nv-narrow" style="text-align:center;margin-top:1.5rem">
        <a class="btn btn-lg" href="#/profile">Почати</a>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — About
  // ===================================================================
  function screenAbout() {
    root.innerHTML = `
      <div class="nv-narrow">
        <h1>Про нас</h1>
        <p class="lead">Наша місія — допомогти людям в Україні впевнено переходити між кар'єрними етапами та знаходити реалістичні професійні можливості.</p>
        <div class="nv-panel">
          <h2 style="margin-top:0">У що ми віримо</h2>
          <ul>
            <li>Рішення про кар'єру мають спиратися на реальні факти про людину, а не на здогади.</li>
            <li>Результат має бути зрозумілим і поясненним — без «чорної скриньки» та вигаданих відсотків.</li>
            <li>Ми не показуємо цифр (зарплат, попиту, статистики), доки не маємо перевіреного джерела.</li>
          </ul>
        </div>
        <div class="nv-panel">
          <h2 style="margin-top:0">Що вже є</h2>
          <p>Каталог професій із фактичними даними та кар'єрний профіль (Person KB), який ви наповнюєте з резюме або вручну. Персональний підбір професій, аналіз навичок і маршрут переходу — у розробці.</p>
        </div>
        <a class="btn" href="#/profile">Створити профіль</a>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Login (visual future state only)
  // ===================================================================
  function screenLogin() {
    root.innerHTML = `
      <div class="nv-narrow">
        <h1>Вхід</h1>
        <p class="lead">Вхід за email та паролем, а також через Google і LinkedIn з'явиться на наступному етапі. Зараз профіль створюється без реєстрації.</p>
        <div class="nv-panel">
          <div class="field"><label>Email</label><input type="email" disabled placeholder="you@example.com"></div>
          <div class="field"><label>Пароль</label><input type="password" disabled placeholder="••••••••"></div>
          <button class="btn is-disabled" disabled>Увійти<span class="soon-tag">Незабаром</span></button>
          <div style="margin-top:.75rem">
            <button class="btn secondary is-disabled" disabled>Продовжити з Google<span class="soon-tag">Незабаром</span></button>
            <button class="btn secondary is-disabled" disabled>Продовжити з LinkedIn<span class="soon-tag">Незабаром</span></button>
          </div>
        </div>
        <a class="btn" href="#/profile">Створити профіль без реєстрації</a>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Pricing (visual shell only; prices are placeholders, no checkout)
  // ===================================================================
  function screenPricing() {
    const plan = (name, chip, price, feats, future) => `
      <div class="nv-card ${future ? "future" : ""}">
        ${chip}
        <h3 style="margin:.5rem 0 .2rem">${name}</h3>
        <div style="font-size:1.4rem;font-weight:800">${price}</div>
        <ul style="padding-left:1.1rem;color:var(--muted);font-size:.9rem;margin:.6rem 0 0">
          ${feats.map((f) => `<li>${f}</li>`).join("")}
        </ul>
        <div style="margin-top:.8rem">
          ${future
            ? `<button class="btn secondary is-disabled" disabled>Обрати<span class="soon-tag">Незабаром</span></button>`
            : `<a class="btn" href="#/profile">Почати безкоштовно</a>`}
        </div>
      </div>`;
    root.innerHTML = `
      <div class="nv-narrow">
        <h1>Тарифи</h1>
        <p class="lead">Ціни на цій сторінці — орієнтовний макет, а не остаточне рішення. Оплата й оформлення підписки ще не підключені.</p>
      </div>
      <div class="nv-cards">
        ${plan("Free", `<span class="chip chip--green">Доступно</span>`, "0 ₴", ["Кар'єрний профіль (CV / вручну)", "Каталог професій", "Базовий огляд можливостей"], false)}
        ${plan("Premium", `<span class="chip chip--purple">Незабаром</span>`, "— ₴ / міс", ["Персональний підбір професій", "Skill gap і маршрут переходу", "План дій і прогрес", "Щотижневі апдейти"], true)}
        ${plan("Premium + Коуч", `<span class="chip chip--purple">Незабаром</span>`, "— ₴ / міс", ["Усе з Premium", "Персональний кар'єрний коуч", "Сесії та консультації"], true)}
      </div>
      <div class="nv-narrow"><p class="muted" style="font-size:.85rem">Оплата не реалізована. Значення цін — placeholder.</p></div>`;
  }

  // ===================================================================
  // PUBLIC — Opportunities (honest future state — Matching is Phase 2)
  // ===================================================================
  async function screenOpportunities() {
    setLoading();
    let hasProfile = false;
    try { const p = await MnpApi.request("/me/person"); hasProfile = !!(p && p.id); } catch (e) {}
    root.innerHTML = `
      <div class="nv-narrow">
        <h1>Можливості</h1>
        ${hasProfile
          ? `<p class="lead">Ваш профіль готовий.</p>
             <div class="nv-future">
               <div class="ico">🧭</div>
               <h2>Персональний підбір професій буде доступний на наступному етапі</h2>
               <p>Наступний крок — зіставити ваш досвід і навички з вимогами професій. Поки що ви можете переглянути повний каталог професій.</p>
               <a class="btn btn-lg" href="#/catalog">Переглянути професії</a>
             </div>`
          : `<div class="nv-future">
               <div class="ico">🧭</div>
               <h2>Спочатку створіть профіль</h2>
               <p>Персональні можливості будуються на основі вашого кар'єрного профілю. Персональний підбір з'явиться на наступному етапі; каталог професій доступний вже зараз.</p>
               <a class="btn btn-lg" href="#/profile">Створити профіль</a>
               <a class="btn secondary btn-lg" href="#/catalog">Переглянути професії</a>
             </div>`}
        <div class="nv-cards">
          <div class="nv-card future"><div class="ico">📊</div><h3>Skill gap</h3><p>Чого бракує для цільової ролі. <span class="soon-tag">Незабаром</span></p></div>
          <div class="nv-card future"><div class="ico">🗺️</div><h3>Маршрут переходу</h3><p>Покрокові дії та навчання. <span class="soon-tag">Незабаром</span></p></div>
          <div class="nv-card future"><div class="ico">🔀</div><h3>«Що зміниться, якщо…»</h3><p>Симуляція сценаріїв. <span class="soon-tag">Незабаром</span></p></div>
        </div>
      </div>`;
  }

  // ===================================================================
  // Legacy matching flow (kept reachable by URL, not surfaced in product)
  // ===================================================================
  function screenStart() { location.hash = "#/profile"; }
  function screenUpload() { location.hash = "#/profile/cv"; }

  async function screenQuestionnaireCapital() {
    setLoading();
    let missing;
    try { missing = await MnpApi.getMissingFields(); } catch (e) { showError(e); return; }
    root.innerHTML = `
      <h1>Ваш досвід</h1>
      <p class="lead">Заповнюємо лише те, чого ще не знаємо.</p>
      ${!missing.career_capital.includes("current_role") ? `<p class="limitation-label">Поточну роль вже визначено з резюме</p>` : `
      <div class="field"><label>Поточна або остання посада</label><input id="q-role" type="text"></div>
      <div class="field"><label>Досвід (років)</label><input id="q-years" type="number" step="0.5" min="0"></div>
      `}
      <div class="field"><label>Ключові навички та інструменти (через кому)</label><input id="q-skills" type="text" placeholder="Excel, CRM, Переговори"></div>
      <div class="field"><label>Освіта (рівень)</label>
        <select id="q-edu"><option value="">--</option><option value="bachelor">Бакалавр</option><option value="master">Магістр</option><option value="specialist">Спеціаліст</option></select>
      </div>
      <button class="btn" id="capital-next">Далі: цілі</button>
    `;
    onClickSafely(document.getElementById("capital-next"), async () => {
      const skills = document.getElementById("q-skills").value.split(",").map((s) => s.trim()).filter(Boolean);
      const roleInput = document.getElementById("q-role");
      const yearsInput = document.getElementById("q-years");
      await MnpApi.submitCareerCapital({
        current_role: roleInput ? roleInput.value || null : null,
        years_of_experience: yearsInput && yearsInput.value ? parseFloat(yearsInput.value) : null,
        skill_phrases: skills,
        education_level: document.getElementById("q-edu").value || null,
      });
      location.hash = "#/questionnaire/intent";
    });
  }

  function screenQuestionnaireIntent() {
    root.innerHTML = `
      <h1>Ваші цілі</h1>
      <div class="field"><label>Головна мета</label>
        <select id="q-goal">
          <option value="find_work">Знайти роботу</option>
          <option value="change_career">Змінити професію</option>
          <option value="increase_income">Заробляти більше</option>
          <option value="return_to_market">Повернутись на ринок праці</option>
          <option value="explore">Дослідити варіанти</option>
        </select>
      </div>
      <div class="field"><label>Бажаний дохід на місяць (грн, необов'язково)</label><input id="q-income" type="number"></div>
      <div class="field"><label>Формат роботи</label>
        <select id="q-format"><option value="">--</option><option value="onsite">Офіс</option><option value="hybrid">Гібрид</option><option value="remote">Віддалено</option></select>
      </div>
      <button class="btn" id="intent-submit">Отримати результат</button>
    `;
    onClickSafely(document.getElementById("intent-submit"), async () => {
      await MnpApi.submitCareerIntent({
        goal_type: document.getElementById("q-goal").value,
        target_income: document.getElementById("q-income").value ? parseFloat(document.getElementById("q-income").value) : null,
        work_format: document.getElementById("q-format").value || null,
      });
      location.hash = "#/processing";
    });
  }

  async function screenProcessing() {
    root.innerHTML = `<div class="loading">Обчислюємо ваші кар'єрні варіанти...</div>`;
    try {
      const { match_run_id } = await MnpApi.createMatchRun();
      localStorage.setItem("mnp_last_match_run", match_run_id);
      location.hash = `#/results/${match_run_id}`;
    } catch (e) { showError(e); }
  }

  function careerRow(entry, rankLabel) {
    const primaryComponent = entry.components.find((c) => c.component_type === "skill_fit");
    return `
      <div class="career-row" onclick="location.hash='#/career/${entry.career_match_id}'">
        <div><span class="rank">${rankLabel}</span><strong>${entry.career_name_uk}</strong></div>
        <div>${feasibilityBadge(entry.feasibility_status)} ${bandBadge(primaryComponent ? primaryComponent.band : null)}</div>
      </div>
    `;
  }

  async function screenResults(matchRunId) {
    setLoading();
    try {
      const results = await MnpApi.getMatchRunCareers(matchRunId);
      root.innerHTML = `
        <h1>Ваша карта кар'єрних варіантів</h1>
        ${results.featured.length ? `<h2>Рекомендовано для вас</h2>${results.featured.map((e, i) => careerRow(e, "#" + (i + 1))).join("")}` : `<p class="limitation-label">Даних поки недостатньо для впевнених рекомендацій -- перегляньте повний список нижче.</p>`}
        <h2>Усі варіанти (топ-10)</h2>
        ${results.ranked_top10.map((e) => careerRow(e, "")).join("")}
        ${results.blocked.length ? `<h2>Недоступно зараз</h2>${results.blocked.map((e) => careerRow(e, "")).join("")}` : ""}
        <a href="#/catalog" class="btn secondary">Переглянути весь каталог професій</a>
      `;
    } catch (e) { showError(e); }
  }

  async function screenCareerDetail(careerMatchId) {
    setLoading();
    try {
      const view = await MnpApi.getCareerMatchDetail(careerMatchId);
      root.innerHTML = `
        <h1>${view.career_name_uk}</h1>
        <p class="lead">${view.description_short_uk}</p>
        <div>${feasibilityBadge(view.feasibility_status)} <span class="badge insufficient">${DISTANCE_LABELS[view.transition_distance] || view.transition_distance}</span></div>
        ${view.market_data_limited ? `<p class="limitation-label">Дані про ринок праці для цієї професії поки обмежені</p>` : ""}
        <h2>Компоненти відповідності</h2>
        <div class="chips">
          ${view.components.map((c) => `<span class="chip">${COMPONENT_LABELS[c.component_type] || c.component_type}: ${c.status === "scored" ? bandBadge(c.band) : bandBadge(null)}</span>`).join("")}
        </div>
        ${view.matched_skill_labels.length ? `<h2>Що вже підтверджено</h2><div class="chips">${view.matched_skill_labels.map((s) => `<span class="chip">${s}</span>`).join("")}</div>` : ""}
        ${view.gaps.length ? `<h2>Над чим варто попрацювати</h2><ul class="gap-list">${view.gaps.map((g) => `<li><strong>${g.reference_label}</strong> -- ${g.action === "learn" ? "вивчити" : g.action === "practice" ? "попрактикувати" : "переформулювати досвід"}</li>`).join("")}</ul>` : ""}
        ${view.feasibility_findings.length ? `<h2>Вимоги професії</h2><ul class="gap-list">${view.feasibility_findings.map((f) => `<li>${f.requirement_description || f.finding_type} (${f.status})</li>`).join("")}</ul>` : ""}
        <a href="#/route/${careerMatchId}" class="btn">Переглянути маршрут</a>
        <a href="#/results/${localStorage.getItem('mnp_last_match_run')}" class="btn secondary">Назад до результатів</a>
      `;
    } catch (e) { showError(e); }
  }

  async function screenRoute(careerMatchId) {
    setLoading();
    try {
      const route = await MnpApi.getCareerMatchRoute(careerMatchId);
      const scenarioLabels = { safe: "Безпечний", growth: "Зростання", transform: "Трансформація" };
      root.innerHTML = `
        <h1>Ваш маршрут</h1>
        <p class="lead">Сценарій: ${scenarioLabels[route.route_type] || route.route_type}</p>
        <ul class="route-list">
          ${route.steps.map((s) => `<li><span class="step-num">${s.order}</span><strong>${s.title}</strong>${s.description ? `<div>${s.description}</div>` : ""}</li>`).join("")}
        </ul>
        <a href="#/career/${careerMatchId}" class="btn secondary">Назад до професії</a>
      `;
    } catch (e) { showError(e); }
  }

  // ===================================================================
  // Career Explorer (Career KB V1) — real customer-facing catalog
  // ===================================================================
  let _catalogCache = null;

  async function screenCatalog(selectedId) {
    setLoading();
    try {
      if (!_catalogCache) _catalogCache = await MnpApi.listCareers();
      const careers = _catalogCache;
      const isDesktop = window.matchMedia("(min-width: 761px)").matches;
      if (!selectedId && careers.length && isDesktop) {
        location.hash = `#/catalog/${careers[0].id}`;
        return;
      }
      const detail = selectedId ? await MnpApi.getCareerDetail(selectedId) : null;

      root.innerHTML = `
        <div class="explorer">
          <aside class="explorer-catalog" data-open="${detail ? "false" : "true"}">
            <h1>Професії</h1>
            <p class="muted" style="font-size:.88rem;margin:.2rem 0 .8rem">Каталог професій з фактичними даними. Персональний підбір — на наступному етапі.</p>
            <input id="career-search" class="career-search" type="text" placeholder="Пошук професії..." autocomplete="off">
            <div id="career-list">${renderCatalogList(careers, selectedId)}</div>
          </aside>
          <section class="explorer-detail">
            ${detail ? renderCareerKbDetail(detail) : `<p class="lead">Оберіть професію зі списку.</p>`}
          </section>
        </div>
      `;

      const search = document.getElementById("career-search");
      if (search) {
        search.addEventListener("input", () => {
          const q = search.value.trim().toLowerCase();
          const filtered = careers.filter((c) =>
            c.name_uk.toLowerCase().includes(q) ||
            (c.category_uk || "").toLowerCase().includes(q) ||
            (c.description_short_uk || "").toLowerCase().includes(q));
          document.getElementById("career-list").innerHTML =
            filtered.length ? renderCatalogList(filtered, selectedId)
                            : `<p class="limitation-label">Нічого не знайдено</p>`;
        });
      }
    } catch (e) { showError(e); }
  }

  function renderCatalogList(careers, selectedId) {
    return careers.map((c) => `
      <a class="catalog-item ${c.id === selectedId ? "is-selected" : ""}" href="#/catalog/${c.id}">
        <strong>${esc(c.name_uk)}</strong>
        <span class="catalog-item-cat">${esc(c.category_uk || "")}</span>
      </a>
    `).join("");
  }

  function renderReqSection(section) {
    if (!section) return "";
    const body = section.items.length
      ? `<ul class="kb-list">${section.items.map((it) => `
          <li>
            <span>${esc(it.title_uk)}</span>
            <span class="badge ${it.confirmed ? "high" : "insufficient"}">${esc(it.hardness_uk)}</span>
          </li>`).join("")}</ul>`
      : `<p class="limitation-label">${esc(section.empty_label_uk || "Немає підтверджених даних")}</p>`;
    return `<div class="kb-req-block"><h3>${esc(section.title_uk)}</h3>${body}</div>`;
  }

  function renderSkillTable(title, skills) {
    if (!skills || !skills.length) return "";
    return `
      <h3>${esc(title)}</h3>
      <table class="kb-skill-table">
        <thead><tr><th>Навичка</th><th>Потрібність</th><th>Рівень</th></tr></thead>
        <tbody>
          ${skills.map((s) => `
            <tr>
              <td>${esc(s.name_uk)}</td>
              <td><span class="badge ${skillReqClass(s.requirement_code)}">${esc(s.requirement_uk)}</span></td>
              <td>${esc(s.level_uk)}</td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  }
  function skillReqClass(code) {
    return { must_have: "high", high_value: "medium", differentiator: "insufficient", optional: "insufficient" }[code] || "insufficient";
  }

  function renderCareerKbDetail(d) {
    const reqOrder = ["education", "experience", "language", "credential", "legal", "other"];
    return `
      <div class="kb-detail">
        <a class="kb-back" href="#/catalog">← До списку професій</a>
        <h1>${esc(d.identity.name_uk)}</h1>
        <p class="kb-cat">${esc(d.identity.category_uk || "")}</p>
        <p class="lead">${esc(d.overview.short_description_uk)}</p>

        <div class="kb-kpis">
          <div class="kb-kpi"><span class="kb-kpi-label">Складність входу</span><span class="kb-kpi-value">${esc(d.entry.difficulty_uk)}</span></div>
          <div class="kb-kpi"><span class="kb-kpi-label">Старт без досвіду</span><span class="kb-kpi-value">${esc(d.entry.without_experience_uk)}</span></div>
          <div class="kb-kpi"><span class="kb-kpi-label">Ринок праці</span><span class="kb-kpi-value kb-kpi-muted">${esc(d.market.status_uk)}</span></div>
        </div>

        <h2>${esc(d.overview.title_uk)}</h2>
        ${d.overview.long_description_uk ? `<p>${esc(d.overview.long_description_uk)}</p>` : `<p class="limitation-label">Розгорнутий опис готується</p>`}

        <h2>Основні обов'язки</h2>
        <ul class="kb-list">
          ${d.responsibilities.map((r) => `<li><span><strong>${esc(r.title_uk)}</strong>${r.description_uk ? ` — ${esc(r.description_uk)}` : ""}</span></li>`).join("")}
        </ul>

        <h2>Навички</h2>
        ${renderSkillTable("Тверді навички", d.skills.hard)}
        ${renderSkillTable("М'які навички", d.skills.soft)}
        ${(!d.skills.hard.length && !d.skills.soft.length) ? `<p class="limitation-label">Навички готуються</p>` : ""}

        ${d.knowledge.length ? `<h2>Знання</h2><div class="chips">${d.knowledge.map((k) => `<span class="chip">${esc(k.name_uk)}</span>`).join("")}</div>` : ""}

        <h2>Вимоги та освіта</h2>
        ${reqOrder.map((k) => renderReqSection(d.requirements[k])).join("")}
        <p class="limitation-label">«Бажана» — перевага, а не обов'язкова умова. Відсутність підтверджених даних не означає, що вимоги немає.</p>

        <h2>Переваги та недоліки</h2>
        <p class="limitation-label">Редакційна оцінка NAPRIAM, а не статистика.</p>
        <div class="kb-proscons">
          <div class="kb-pros"><h3>Переваги</h3><ul class="kb-list">${d.pros_cons.advantages.map((t) => `<li><span>${esc(t)}</span></li>`).join("") || "<li>—</li>"}</ul></div>
          <div class="kb-cons"><h3>Недоліки</h3><ul class="kb-list">${d.pros_cons.disadvantages.map((t) => `<li><span>${esc(t)}</span></li>`).join("") || "<li>—</li>"}</ul></div>
        </div>

        <h2>${esc(d.career_path.label_uk)}</h2>
        <p class="limitation-label">Типовий маршрут, а не гарантований шлях просування.</p>
        <ol class="kb-path">
          ${d.career_path.steps.map((s) => `
            <li class="${s.is_current ? "is-current" : ""}">
              <div class="kb-path-name">${esc(s.name_uk)}${s.is_current ? ` <span class="badge insufficient">ця професія</span>` : ""}</div>
              ${s.typical_experience_uk ? `<div class="kb-path-exp">${esc(s.typical_experience_uk)}</div>` : ""}
              ${s.description_uk ? `<div class="kb-path-desc">${esc(s.description_uk)}</div>` : ""}
            </li>`).join("")}
        </ol>

        <h2>Попит і зарплата</h2>
        <p class="limitation-label">Дані ринку будуть додані пізніше. Ми не показуємо орієнтовних цифр, доки немає перевіреного джерела.</p>

        ${d.related_careers.length ? `
          <h2>Пов'язані професії</h2>
          <div class="kb-related">
            ${d.related_careers.map((r) => `
              <a class="kb-related-item" href="#/catalog/${relatedId(r.code)}">
                <strong>${esc(r.name_uk)}</strong>
                <span class="catalog-item-cat">${esc(r.relation_uk)}</span>
              </a>`).join("")}
          </div>` : ""}

        <div class="kb-cta">
          <h2>Чи підходить вам ця професія?</h2>
          <p>Персональний підбір і аналіз відповідності з'являться на наступному етапі. Зараз ви можете створити кар'єрний профіль, щоб бути готовими.</p>
          <a href="#/profile" class="btn">Створити профіль</a>
        </div>
      </div>
    `;
  }
  function relatedId(code) {
    const hit = (_catalogCache || []).find((c) => c.code === code);
    return hit ? hit.id : "";
  }

  // --- Router --------------------------------------------------------
  function render() {
    renderHeader();
    const hash = location.hash || "#/";
    const [, path, param] = hash.match(/^#\/([^/]*)(?:\/(.*))?$/) || [null, "", null];

    if (path === "") return screenHome();
    if (path === "how") return screenHowItWorks();
    if (path === "about") return screenAbout();
    if (path === "login") return screenLogin();
    if (path === "pricing") return screenPricing();
    if (path === "opportunities") return screenOpportunities();
    if (path === "catalog") return screenCatalog(param || null);

    // Post-profile career workspace (workspace.js) — visual product shell,
    // future modules are clearly non-live.
    if (path === "app") return MnpWorkspace.render(param || "");

    // Person KB customer flows (person.js)
    if (path === "profile" && !param) return MnpPersonKB.screenLanding();
    if (path === "profile" && param === "build") return MnpPersonKB.screenBuild();
    if (path === "profile" && param === "me") return MnpPersonKB.screenMyProfile();
    if (path === "profile" && param === "edit") return MnpPersonKB.screenEdit();
    if (path === "profile" && param === "cv") return MnpPersonKB.screenCv();
    if (path === "profile" && param === "confirmed") return MnpPersonKB.screenConfirmed();

    // Admin (separate internal interface)
    if (path === "admin" && param === "login") return MnpAdmin.screenLogin();
    if (path === "admin" && (param === "catalog" || !param)) return MnpAdmin.screenAdminCatalog();
    if (path === "admin" && param && param.startsWith("career/")) return MnpAdmin.screenEditor(param.slice("career/".length));
    if (path === "admin" && param === "persons") return MnpPersonKB.admScreenList();
    if (path === "admin" && param === "persons/new") return MnpPersonKB.admScreenCreate();
    if (path === "admin" && param && param.startsWith("persons/")) return MnpPersonKB.admScreenCard(param.slice("persons/".length));

    // Legacy matching flow — reachable by URL, not surfaced in the product
    if (path === "start") return screenStart();
    if (path === "upload") return screenUpload();
    if (path === "questionnaire" && param === "capital") return screenQuestionnaireCapital();
    if (path === "questionnaire" && param === "intent") return screenQuestionnaireIntent();
    if (path === "processing") return screenProcessing();
    if (path === "results") return screenResults(param || localStorage.getItem("mnp_last_match_run"));
    if (path === "career") return screenCareerDetail(param);
    if (path === "route") return screenRoute(param);
    if (path === "career-card") return (location.hash = "#/profile/me");

    return screenHome();
  }

  window.addEventListener("hashchange", render);
  window.addEventListener("DOMContentLoaded", render);
  window.addEventListener("unhandledrejection", (event) => {
    if (!root.querySelector(".error-box")) showError(event.reason || new Error("Невідома помилка"));
  });

  return { render };
})();
