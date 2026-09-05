// Yellow Hub — customer product frontend. Plain JS, hash router, no build step.
// Phase 1 scope: public shell (Home / How it works / About / Login-future /
// Opportunities-future), Person KB flows (person.js), Career KB explorer.
// Personalized Matching is Phase 2 — the old match/questionnaire screens are
// kept reachable by direct URL but are not surfaced in the product.

const App = (() => {
  const root = document.getElementById("app");
  const header = document.getElementById("site-header");

  const LOGO_MARK = NvUI.logoMark();

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
    ["catalog", "Професії"],
    ["how", "Як це працює"],
    ["about", "Про МОЖУ"],
  ];

  function renderHeader() {
    const hash = location.hash || "#/";
    renderFooter(hash);
    // Admin gets its own dark internal nav; the post-profile workspace draws
    // its own sidebar + top bar and clears this header itself.
    if (hash.startsWith("#/admin")) { renderAdminNav(hash); return; }
    if (hash.startsWith("#/app")) { header.innerHTML = ""; return; }
    const [, path] = hash.match(/^#\/([^/]*)/) || [null, ""];
    const hasProfile = !!localStorage.getItem("mnp_has_profile");
    // "Увійти" is a staff entry point (consultant / admin), not a client
    // login -- clients never need an account in PILOT-30. See #/login.
    header.innerHTML = `
      <div class="nv-header">
        <a class="nv-brand" href="#/">${LOGO_MARK}<b>Yellow Hub</b><span>Кар'єрний центр</span></a>
        <nav class="nv-nav">
          ${NAV.map(([p, t]) => `<a href="#/${p}" class="${p === path ? "is-active" : ""}">${t}</a>`).join("")}
          <a href="#/market" class="${path === "market" ? "is-active" : ""}">Ринок праці<span class="soon-tag" style="margin-left:.35rem">Незабаром</span></a>
        </nav>
        <div class="nv-actions">
          <a href="#/login" class="btn ghost">Увійти</a>
          ${hasProfile
            ? `<a class="btn secondary" href="#/app">Мій профіль</a>`
            : `<a class="btn" href="#/profile">Створити профіль</a>`}
        </div>
      </div>`;
  }

  function renderAdminNav(hash) {
    if (hash === "#/admin/login" || !MnpApi.isAdmin()) { header.innerHTML = ""; return; }
    const p = (hash.match(/^#\/admin\/([^/]*)/) || [])[1] || "";
    const item = (slug, label) =>
      `<a href="#/admin/${slug}" class="${p.startsWith(slug.split("/")[0]) ? "is-active" : ""}">${label}</a>`;
    header.innerHTML = `
      <div class="adm-nav">
        <b>YELLOW HUB · ADMIN</b>
        ${item("persons", "Люди")}
        ${item("catalog", "Професії")}
        <span class="spacer"></span>
        <a href="#" id="adm-logout">Вийти</a>
      </div>`;
    const lo = document.getElementById("adm-logout");
    if (lo) lo.addEventListener("click", (e) => { e.preventDefault(); MnpApi.adminLogout(); location.hash = "#/admin/login"; });
  }

  function renderFooter(hash) {
    const f = document.getElementById("site-footer");
    if (!f) return;
    if (hash.startsWith("#/admin") || hash.startsWith("#/app")) { f.innerHTML = ""; f.style.display = "none"; return; }
    f.style.display = "";
    f.innerHTML = `
      <div class="site-footer-inner">
        <div class="fbrand">${LOGO_MARK}<span><b>Yellow Hub</b><span>Професійні можливості для кожного</span></span></div>
        <nav>
          <a href="#/about">Про МОЖУ</a>
          <a href="#/catalog">Професії</a>
          <a href="#/how">Як це працює</a>
          <a href="#/market">Ринок праці</a>
          <a href="#/privacy">Конфіденційність</a>
          <a href="#/terms">Умови використання</a>
        </nav>
        <span class="fcopy">© 2026 Yellow Hub</span>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Home
  // ===================================================================
  function screenHome() {
    const I = (n) => NvUI.icon(n);
    root.innerHTML = `
      <section class="hero-split">
        <div>
          <span class="eyebrow">Ваш наступний крок — можливий</span>
          <h1>Не знаєте, куди рухатися в кар'єрі?</h1>
          <p class="lead">Створіть кар'єрний профіль і побачите реалістичні професійні напрями, що вам підходять зараз.</p>
          <div class="hero-actions">
            <a class="btn btn-lg" href="#/profile">Створити кар'єрний профіль →</a>
            <a class="btn secondary btn-lg" href="#/catalog">Переглянути професії</a>
          </div>
          <div class="check-row">
            <span><span class="ck">${I("check")}</span>Безкоштовно</span>
            <span><span class="ck">${I("check")}</span>Зрозуміло та просто</span>
            <span><span class="ck">${I("check")}</span>Для кожного</span>
          </div>
        </div>
        <div class="illus-wrap">
          <div class="illus-frame">${NvUI.illustration("person")}</div>
          <div class="doodle d-tl">${NvUI.doodleIcon("arrow")}<span class="txt">Нові можливості починаються з розуміння себе</span></div>
          <div class="sticky-note">Краще майбутнє починається сьогодні ${NvUI.doodleIcon("heart")}</div>
        </div>
      </section>

      <h2>Для кого це</h2>
      <div class="tile-nav-grid">
        <a class="tile-nav" href="#/profile"><span class="tn-ico">${I("route")}</span><span class="tn-lbl">Хочу змінити професію</span><span class="tn-chev">${I("arrow")}</span></a>
        <a class="tile-nav" href="#/profile"><span class="tn-ico">${I("briefcase")}</span><span class="tn-lbl">Втратили роботу</span><span class="tn-chev">${I("arrow")}</span></a>
        <a class="tile-nav" href="#/profile"><span class="tn-ico">${I("target")}</span><span class="tn-lbl">Повертаюсь на ринок праці</span><span class="tn-chev">${I("arrow")}</span></a>
        <a class="tile-nav" href="#/profile"><span class="tn-ico">${I("compass")}</span><span class="tn-lbl">Шукаю свій напрям</span><span class="tn-chev">${I("arrow")}</span></a>
      </div>

      <h2>Що ви отримаєте</h2>
      <div class="tile-feat-grid">
        <div class="tile-feat"><span class="tn-ico">${I("doc")}</span><h3>Кар'єрний профіль</h3><p>Ваші сильні сторони та інтереси</p></div>
        <div class="tile-feat"><span class="tn-ico">${I("chart")}</span><h3>Реалістичні напрями</h3><p>Професії, що вам підходять зараз</p></div>
        <div class="tile-feat"><span class="tn-ico">${I("lightbulb")}</span><h3>Пояснення рекомендацій</h3><p>Чому саме ці професії і що це означає</p></div>
        <div class="tile-feat"><span class="tn-ico">${I("target")}</span><h3>Наступні кроки</h3><p>З чого почати і як розвиватися</p></div>
      </div>

      <h2>Як це працює</h2>
      <div class="step-flow">
        <div class="sf-item"><div class="sf-row"><span class="sf-n">1</span><span class="sf-ico">${I("edit")}</span></div><h3>Створіть профіль</h3><p>Дайте відповіді на прості запитання</p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">2</span><span class="sf-ico">${I("checklist")}</span></div><h3>Отримайте напрями</h3><p>Сервіс підбере професії, що вам підходять</p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">3</span><span class="sf-ico">${I("target")}</span></div><h3>Оберіть свій фокус</h3><p>Дослідіть професії та можливості</p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">4</span><span class="sf-ico">${I("chart")}</span></div><h3>Рухайтесь далі</h3><p>Отримайте наступні кроки для вашої мети</p></div>
      </div>

      <div class="cta-band">
        <div style="display:flex;align-items:center;gap:1rem">
          <span class="cb-ico">${I("sparkles")}</span>
          <div><h2>Почніть із першого кроку</h2><p>Створіть кар'єрний профіль і відкрийте нові можливості для себе.</p></div>
        </div>
        <a class="btn btn-lg" href="#/profile">Створити кар'єрний профіль →</a>
        <span class="cb-doodle">Ти можеш! ${NvUI.doodleIcon("heart")}</span>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — How it works
  // ===================================================================
  function screenHowItWorks() {
    const I = (n) => NvUI.icon(n);
    root.innerHTML = `
      <div class="crumb"><a href="#/">Головна</a><span class="sep">›</span><span class="cur">Як це працює</span></div>
      <section class="hero-split">
        <div>
          <span class="eyebrow">Ваш наступний крок — можливий</span>
          <h1>Як це працює</h1>
          <p class="lead">Ми зробили процес простим і зрозумілим, щоб ви могли отримати персональні рекомендації та обрати реалістичний наступний крок.</p>
        </div>
        <div class="illus-wrap">
          <div class="illus-frame">${NvUI.illustration("person")}</div>
          <div class="doodle d-tl">${NvUI.doodleIcon("arrow")}<span class="txt">Крок за кроком до бажаного майбутнього</span></div>
        </div>
      </section>

      <div class="step-flow" style="grid-template-columns:repeat(5,1fr)">
        <div class="sf-item"><div class="sf-row"><span class="sf-n">1</span><span class="sf-ico">${I("edit")}</span></div><h3>Створіть кар'єрний профіль</h3><p>Розкажіть про себе: освіту, досвід, інтереси. Це займе близько 10–15 хвилин.</p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">2</span><span class="sf-ico">${I("checklist")}</span></div><h3>Отримайте професійні напрями</h3><p>Сервіс проаналізує ваші дані та запропонує реалістичні напрями, які відповідають вашому досвіду.</p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">3</span><span class="sf-ico">${I("chat")}</span></div><h3>Перегляньте рекомендації</h3><p>Побачите, що у вас вже є, які навички можна перенести та що ще важливо врахувати. <span class="soon-tag">Незабаром</span></p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">4</span><span class="sf-ico">${I("target")}</span></div><h3>Оберіть свій напрям</h3><p>Разом із консультантом оберіть найбільш близький і зрозумілий для себе варіант. <span class="soon-tag">Незабаром</span></p></div>
        <span class="sf-arrow">${I("arrow")}</span>
        <div class="sf-item"><div class="sf-row"><span class="sf-n">5</span><span class="sf-ico">${I("route")}</span></div><h3>Отримайте наступні кроки</h3><p>Ви отримаєте план дій: з чого почати, що дослідити і куди рухатися далі. <span class="soon-tag">Незабаром</span></p></div>
      </div>

      <div class="cta-band">
        <div style="display:flex;align-items:center;gap:1rem">
          <span class="cb-ico">${I("route")}</span>
          <div><h2>Готові зробити перший крок?</h2><p>Створіть кар'єрний профіль і відкрийте нові можливості для себе.</p></div>
        </div>
        <a class="btn btn-lg" href="#/profile">Почати зараз →</a>
        <div class="check-row" style="color:rgba(24,20,15,.75)">
          <span><span class="ck" style="background:rgba(24,20,15,.1);color:var(--brand-ink)">${I("check")}</span>Безкоштовно</span>
          <span><span class="ck" style="background:rgba(24,20,15,.1);color:var(--brand-ink)">${I("check")}</span>Зрозуміло та просто</span>
          <span><span class="ck" style="background:rgba(24,20,15,.1);color:var(--brand-ink)">${I("check")}</span>Для кожного</span>
        </div>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — About
  // ===================================================================
  function screenAbout() {
    const I = (n) => NvUI.icon(n);
    root.innerHTML = `
      <div class="crumb"><a href="#/">Головна</a><span class="sep">›</span><span class="cur">Про МОЖУ</span></div>
      <div class="nv-narrow" style="max-width:760px;margin:0 0 1.5rem">
        <span class="eyebrow">Соціальна програма</span>
        <h1 style="font-size:clamp(2rem,3vw,2.6rem);font-weight:800;letter-spacing:-.01em">Про МОЖУ</h1>
        <p class="lead">Соціальна програма в межах Yellow Hub, яка допомагає людям у складних життєвих ситуаціях знайти свій професійний шлях і повернутися до активного життя.</p>
      </div>
      <div class="hero-split" style="margin-top:0">
        <div class="illus-wrap">
          <div class="illus-frame">${NvUI.illustration("consult")}</div>
          <div class="sticky-note" style="left:-1.2rem;right:auto;bottom:-1.2rem;transform:rotate(-3deg)">Поруч, коли важливо ${NvUI.doodleIcon("heart")}</div>
        </div>
        <div class="tile-feat-grid" style="grid-template-columns:1fr 1fr;margin:0">
          <div class="tile-feat"><span class="tn-ico">${I("user")}</span><h3>Для тих, хто потребує підтримки</h3><p>Для людей, які втратили роботу або хочуть змінити професійний напрям.</p></div>
          <div class="tile-feat"><span class="tn-ico">${I("gauge")}</span><h3>Безкоштовний доступ</h3><p>Участь у програмі не потребує оплати.</p></div>
          <div class="tile-feat"><span class="tn-ico">${I("edit")}</span><h3>Експертна підтримка</h3><p>Консультації від фахівців, які допомагають розібратися в можливостях.</p></div>
          <div class="tile-feat"><span class="tn-ico">${I("lightbulb")}</span><h3>Реальні можливості</h3><p>Допомагаємо не лише зрозуміти себе, а й рухатися далі.</p></div>
        </div>
      </div>

      <div class="cta-band">
        <div style="display:flex;align-items:center;gap:1rem">
          <span class="cb-ico">${I("compass")}</span>
          <div><h2>МОЖУ</h2><p>Люди. Підтримка. Нові можливості.</p></div>
        </div>
        <a class="btn btn-lg" href="#/profile">Дізнатися більше →</a>
      </div>

      <div class="nv-narrow" style="max-width:760px">
        <h2>У що ми віримо</h2>
        <ul>
          <li>Рішення про кар'єру мають спиратися на реальні факти про людину, а не на здогади.</li>
          <li>Результат має бути зрозумілим і поясненним — без «чорної скриньки» та вигаданих відсотків.</li>
          <li>Технологія без живої людини недостатня: кожен напрям перевіряє кар'єрний консультант.</li>
          <li>Ми не показуємо цифр (зарплат, попиту, статистики), доки не маємо перевіреного джерела.</li>
        </ul>
        <p class="muted">Ми запускаємо продукт разом із першими учасниками у Харкові. Каталог професій і кар'єрний профіль (з CV або вручну) вже працюють. Персональні рекомендації, перевірка консультантом і маршрут наступного кроку запускаються поступово, у межах пілотної програми.</p>
        <a class="btn" href="#/profile">Створити кар'єрний профіль</a>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Ринок праці (future -- honest empty state, no fabricated data)
  // ===================================================================
  function screenMarket() {
    const I = (n) => NvUI.icon(n);
    root.innerHTML = `
      <div class="crumb"><a href="#/">Головна</a><span class="sep">›</span><span class="cur">Ринок праці</span></div>
      <div class="nv-narrow" style="max-width:760px;margin:0 0 1.5rem">
        <h1 style="font-size:clamp(2rem,3vw,2.6rem);font-weight:800;letter-spacing:-.01em">Ринок праці в Україні</h1>
        <p class="lead">Актуальна інформація про тенденції, затребувані професії та навички на українському ринку праці.</p>
      </div>
      <div class="future-hero">
        <div class="future-illus">${NvUI.illustration("chart")}
          <div class="future-card"><h3>Незабаром</h3><p>Ми готуємо для вас цей розділ</p></div>
        </div>
      </div>
      <div class="tile-feat-grid">
        <div class="tile-feat future"><span class="tn-ico">${I("chart")}</span><h3>Тенденції</h3><p><span class="soon-tag">Незабаром</span></p></div>
        <div class="tile-feat future"><span class="tn-ico">${I("briefcase")}</span><h3>Затребувані професії</h3><p><span class="soon-tag">Незабаром</span></p></div>
        <div class="tile-feat future"><span class="tn-ico">${I("layers")}</span><h3>Рівень зарплат</h3><p><span class="soon-tag">Незабаром</span></p></div>
        <div class="tile-feat future"><span class="tn-ico">${I("book")}</span><h3>Навички майбутнього</h3><p><span class="soon-tag">Незабаром</span></p></div>
      </div>
      <div class="nv-narrow" style="text-align:center;margin-top:1.5rem">
        <button class="btn secondary notify-btn" disabled title="Розсилка сповіщень ще не підключена">${I("chat")} Повідомити, коли буде готово →</button>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Регіон (future -- honest empty state, no fabricated data)
  // ===================================================================
  function screenRegion() {
    const I = (n) => NvUI.icon(n);
    root.innerHTML = `
      <div class="crumb"><a href="#/">Головна</a><span class="sep">›</span><a href="#/region">Регіон</a><span class="sep">›</span><span class="cur">Професії у вашому регіоні</span></div>
      <div class="nv-narrow" style="max-width:760px;margin:0 0 1.5rem">
        <h1 style="font-size:clamp(2rem,3vw,2.6rem);font-weight:800;letter-spacing:-.01em">Професії у вашому регіоні</h1>
        <p class="lead">Дізнайтеся, які професії найбільш затребувані у вашому регіоні, і які є можливості для працевлаштування та розвитку.</p>
      </div>
      <div class="future-hero">
        <div class="future-illus">${NvUI.illustration("map")}
          <div class="future-card"><h3>Незабаром</h3><p>Ми готуємо для вас цей розділ</p></div>
        </div>
      </div>
      <div class="tile-feat-grid">
        <div class="tile-feat future"><span class="tn-ico">${I("chart")}</span><h3>Популярні професії</h3><p><span class="soon-tag">Незабаром</span></p></div>
        <div class="tile-feat future"><span class="tn-ico">${I("map")}</span><h3>Можливості в регіоні</h3><p><span class="soon-tag">Незабаром</span></p></div>
        <div class="tile-feat future"><span class="tn-ico">${I("book")}</span><h3>Освітні програми</h3><p><span class="soon-tag">Незабаром</span></p></div>
        <div class="tile-feat future"><span class="tn-ico">${I("user")}</span><h3>Історії успіху</h3><p><span class="soon-tag">Незабаром</span></p></div>
      </div>
      <div class="nv-narrow" style="text-align:center;margin-top:1.5rem">
        <button class="btn secondary notify-btn" disabled title="Розсилка сповіщень ще не підключена">${I("chat")} Повідомити, коли буде готово →</button>
      </div>`;
  }

  // ===================================================================
  // PUBLIC — Login hub (staff entry point: admin real, consultant future)
  // ===================================================================
  function screenLoginHub() {
    const I = (n) => NvUI.icon(n);
    root.innerHTML = `
      <div class="nv-narrow">
        <h1>Увійти</h1>
        <p class="lead">Клієнти не потребують акаунта — кар'єрний профіль створюється без реєстрації. Цей вхід — для консультантів та адміністраторів Yellow Hub.</p>
        <div class="login-split">
          <div class="login-role-card">
            <span class="tn-ico">${I("user")}</span>
            <h3>Я консультант</h3>
            <p>Перегляд клієнтів, рекомендацій і статусів консультацій.</p>
            <button class="btn is-disabled" disabled>Увійти<span class="soon-tag">Незабаром</span></button>
          </div>
          <div class="login-role-card">
            <span class="tn-ico">${I("checklist")}</span>
            <h3>Я адміністратор</h3>
            <p>Каталог професій, людей та повний доступ до налаштувань.</p>
            <a class="btn" href="#/admin/login">Увійти</a>
          </div>
        </div>
        <p class="muted" style="margin-top:1.25rem;font-size:.85rem">Шукаєте свій кар'єрний профіль? <a href="#/profile">Створити або відкрити профіль →</a></p>
      </div>`;
  }

  function screenPrivacy() {
    root.innerHTML = `<div class="nv-narrow"><h1>Конфіденційність</h1>
      <p class="lead">Політика конфіденційності зараз готується разом із запуском пілотної програми.</p>
      <p class="muted">Ми не показуємо цей текст, доки він не узгоджений — щоб не публікувати недостовірну інформацію про обробку даних. Питання щодо ваших даних — на пошту нижче.</p>
      <a class="btn secondary" href="#/">На головну</a></div>`;
  }
  function screenTerms() {
    root.innerHTML = `<div class="nv-narrow"><h1>Умови використання</h1>
      <p class="lead">Умови використання зараз готуються разом із запуском пілотної програми.</p>
      <a class="btn secondary" href="#/">На головну</a></div>`;
  }

  // ===================================================================
  // PUBLIC — Login (visual future state only)
  // ===================================================================
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
        ${plan("Premium", `<span class="chip chip--purple">Незабаром</span>`, "— ₴ / міс", ["Персональний підбір професій", "Аналіз навичок і маршрут переходу", "План дій і прогрес", "Щотижневі апдейти"], true)}
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
          <div class="nv-card future"><div class="ico">📊</div><h3>Потрібні навички</h3><p>Чого бракує для цільової ролі. <span class="soon-tag">Незабаром</span></p></div>
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
  let _catFilter = "Усі", _catQuery = "";
  const CARD_ILLUS = ["person", "consult", "chart"];

  async function screenCatalog(selectedId) {
    setLoading();
    try {
      if (!_catalogCache) _catalogCache = await MnpApi.listCareers();
      if (selectedId) { await screenCareerDetailPage(selectedId); return; }
      renderCatalogGrid();
    } catch (e) { showError(e); }
  }

  function renderCatalogGrid() {
    const I = (n) => NvUI.icon(n);
    const careers = _catalogCache;
    const cats = ["Усі", ...Array.from(new Set(careers.map((c) => c.category_uk).filter(Boolean)))];
    root.innerHTML = `
      <div class="hero-split" style="margin-bottom:1.5rem">
        <div>
          <span class="eyebrow">Досліджуйте. Обирайте. Розвивайтесь</span>
          <h1>Професії</h1>
          <p class="lead">Досліджуйте світ професій, дізнавайтеся, чим вони займаються, та відкривайте нові можливості для свого майбутнього.</p>
          <input id="career-search" class="career-search" type="text" placeholder="Пошук професії, навички або сфери діяльності" autocomplete="off" style="max-width:420px">
        </div>
        <div class="illus-wrap">
          <div class="illus-frame">${NvUI.illustration("person")}</div>
          <div class="doodle d-tl">${NvUI.doodleIcon("arrow")}<span class="txt">Відкривайте нові можливості</span></div>
        </div>
      </div>
      <div class="pill-row" id="cat-pills">
        ${cats.map((c) => `<button data-cat="${esc(c)}" class="${c === _catFilter ? "is-active" : ""}">${esc(c)}</button>`).join("")}
      </div>
      <div id="pcard-list"></div>
      <div class="cta-band">
        <div style="display:flex;align-items:center;gap:1rem">
          <span class="cb-ico">${I("compass")}</span>
          <div><h2>Не знайшли потрібну професію?</h2><p>Каталог поповнюється. Спробуйте інший запит або перегляньте всі категорії.</p></div>
        </div>
        <button class="btn btn-lg" id="cat-reset">Спробувати ще раз →</button>
      </div>`;
    renderPcardList();
    document.querySelectorAll("#cat-pills button").forEach((b) => b.onclick = () => { _catFilter = b.dataset.cat; renderCatalogGrid(); });
    const search = document.getElementById("career-search");
    search.value = _catQuery;
    search.addEventListener("input", () => { _catQuery = search.value; renderPcardList(); });
    document.getElementById("cat-reset").onclick = () => { _catFilter = "Усі"; _catQuery = ""; renderCatalogGrid(); };
  }

  function renderPcardList() {
    const q = _catQuery.trim().toLowerCase();
    const filtered = _catalogCache.filter((c) =>
      (_catFilter === "Усі" || c.category_uk === _catFilter) &&
      (!q || c.name_uk.toLowerCase().includes(q) || (c.category_uk || "").toLowerCase().includes(q) || (c.description_short_uk || "").toLowerCase().includes(q)));
    const list = document.getElementById("pcard-list");
    list.innerHTML = filtered.length ? `<div class="pcard-grid">${filtered.map((c, i) => renderPcard(c, i)).join("")}</div>`
      : `<p class="limitation-label">Нічого не знайдено. Спробуйте інший запит.</p>`;
  }

  function renderPcard(c, i) {
    const I = (n) => NvUI.icon(n);
    return `<a class="pcard" href="#/catalog/${c.id}">
      <div class="pcard-illus">${NvUI.illustration(CARD_ILLUS[i % CARD_ILLUS.length])}</div>
      <div class="pcard-body">
        <h3>${esc(c.name_uk)}</h3>
        <p>${esc(c.description_short_uk || c.category_uk || "")}</p>
        <span class="pcard-go">${I("arrow")}</span>
      </div>
    </a>`;
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

  const DETAIL_TABS = [["about", "Про професію"], ["skills", "Навички"], ["education", "Освіта і розвиток"], ["market", "Ринок праці"], ["related", "Схожі професії"]];
  let _dTab = "about", _dData = null, _dIllusIdx = 0;

  async function screenCareerDetailPage(id) {
    setLoading();
    try {
      _dData = await MnpApi.getCareerDetail(id);
      _dTab = "about";
      _dIllusIdx = (_catalogCache || []).findIndex((c) => c.id === id);
      renderDetailPage();
    } catch (e) { showError(e); }
  }

  function renderDetailPage() {
    const d = _dData;
    root.innerHTML = `
      <div class="crumb"><a href="#/">Головна</a><span class="sep">›</span><a href="#/catalog">Професії</a><span class="sep">›</span><span class="cur">${esc(d.identity.name_uk)}</span></div>
      <div class="hero-split" style="margin-bottom:0">
        <div>
          <h1 style="font-size:clamp(1.9rem,3vw,2.5rem)">${esc(d.identity.name_uk)}</h1>
          <p class="lead">${esc(d.overview.short_description_uk)}</p>
        </div>
        <div class="illus-wrap">
          <div class="illus-frame">${NvUI.illustration(CARD_ILLUS[Math.max(_dIllusIdx, 0) % CARD_ILLUS.length])}</div>
        </div>
      </div>
      <div class="tabs-row" id="d-tabs">
        ${DETAIL_TABS.map(([k, t]) => `<a href="#" data-tab="${k}" class="${k === _dTab ? "is-active" : ""}">${t}</a>`).join("")}
      </div>
      <div id="d-body"></div>
      <h2 style="margin-top:2.5rem">Інші професії, які можуть вас зацікавити</h2>
      <div class="pcard-grid" style="grid-template-columns:repeat(3,1fr)">
        ${(_catalogCache || []).filter((c) => c.id !== d.identity.id).slice(0, 3).map((c, i) => renderPcard(c, i + 1)).join("")}
      </div>`;
    document.querySelectorAll("#d-tabs a").forEach((a) => a.onclick = (e) => { e.preventDefault(); _dTab = a.dataset.tab; renderDetailBody(); document.querySelectorAll("#d-tabs a").forEach((x) => x.classList.toggle("is-active", x === a)); });
    renderDetailBody();
  }

  function renderDetailBody() {
    const d = _dData;
    const body = document.getElementById("d-body");
    if (_dTab === "about") {
      body.innerHTML = `
        <div class="hero-split" style="grid-template-columns:1.3fr 1fr;margin:1.5rem 0">
          <div class="nv-panel" style="margin:0">
            <h2 style="margin-top:0">Про професію</h2>
            ${d.overview.long_description_uk ? `<p>${esc(d.overview.long_description_uk)}</p>` : `<p class="limitation-label">Розгорнутий опис готується</p>`}
            ${d.pros_cons.advantages[0] ? `<div class="example-card" style="box-shadow:none;background:var(--bg-soft);padding:1.1rem 1.3rem;margin:1rem 0 0">«${esc(d.pros_cons.advantages[0])}»</div>` : ""}
          </div>
          <div class="nv-panel" style="margin:0">
            <h2 style="margin-top:0">Що ви робитимете</h2>
            <ul class="kb-list">
              ${d.responsibilities.slice(0, 4).map((r) => `<li><span>${esc(r.title_uk)}</span></li>`).join("") || `<li><span class="muted">Дані готуються</span></li>`}
            </ul>
            <a class="btn btn-lg" href="#/profile" style="margin-top:.5rem">Перевірити, чи підходить мені →</a>
          </div>
        </div>
        <div class="kb-kpis">
          <div class="kb-kpi"><span class="kb-kpi-label">Складність входу</span><span class="kb-kpi-value">${esc(d.entry.difficulty_uk)}</span></div>
          <div class="kb-kpi"><span class="kb-kpi-label">Старт без досвіду</span><span class="kb-kpi-value">${esc(d.entry.without_experience_uk)}</span></div>
          <div class="kb-kpi"><span class="kb-kpi-label">Ринок праці</span><span class="kb-kpi-value kb-kpi-muted">${esc(d.market.status_uk)}</span></div>
        </div>`;
    } else if (_dTab === "skills") {
      body.innerHTML = `
        ${renderSkillTable("Тверді навички", d.skills.hard)}
        ${renderSkillTable("М'які навички", d.skills.soft)}
        ${(!d.skills.hard.length && !d.skills.soft.length) ? `<p class="limitation-label">Навички готуються</p>` : ""}
        ${d.knowledge.length ? `<h2>Знання</h2><div class="chips">${d.knowledge.map((k) => `<span class="chip">${esc(k.name_uk)}</span>`).join("")}</div>` : ""}`;
    } else if (_dTab === "education") {
      const reqOrder = ["education", "experience", "language", "credential", "legal", "other"];
      body.innerHTML = `
        <h2 style="margin-top:0">Вимоги та освіта</h2>
        ${reqOrder.map((k) => renderReqSection(d.requirements[k])).join("")}
        <p class="limitation-label">«Бажана» — перевага, а не обов'язкова умова. Відсутність підтверджених даних не означає, що вимоги немає.</p>
        <h2>${esc(d.career_path.label_uk)}</h2>
        <p class="limitation-label">Типовий маршрут, а не гарантований шлях просування.</p>
        <ol class="kb-path">
          ${d.career_path.steps.map((s) => `
            <li class="${s.is_current ? "is-current" : ""}">
              <div class="kb-path-name">${esc(s.name_uk)}${s.is_current ? ` <span class="badge insufficient">ця професія</span>` : ""}</div>
              ${s.typical_experience_uk ? `<div class="kb-path-exp">${esc(s.typical_experience_uk)}</div>` : ""}
              ${s.description_uk ? `<div class="kb-path-desc">${esc(s.description_uk)}</div>` : ""}
            </li>`).join("")}
        </ol>`;
    } else if (_dTab === "market") {
      body.innerHTML = `
        <h2 style="margin-top:0">Попит і зарплата</h2>
        <p class="limitation-label">Дані ринку будуть додані пізніше. Ми не показуємо орієнтовних цифр, доки немає перевіреного джерела.</p>
        <h2>Переваги та недоліки</h2>
        <p class="limitation-label">Редакційна оцінка Yellow Hub, а не статистика.</p>
        <div class="kb-proscons">
          <div class="kb-pros"><h3>Переваги</h3><ul class="kb-list">${d.pros_cons.advantages.map((t) => `<li><span>${esc(t)}</span></li>`).join("") || "<li>—</li>"}</ul></div>
          <div class="kb-cons"><h3>Недоліки</h3><ul class="kb-list">${d.pros_cons.disadvantages.map((t) => `<li><span>${esc(t)}</span></li>`).join("") || "<li>—</li>"}</ul></div>
        </div>`;
    } else if (_dTab === "related") {
      body.innerHTML = d.related_careers.length ? `
        <div class="kb-related">
          ${d.related_careers.map((r) => `
            <a class="kb-related-item" href="#/catalog/${relatedId(r.code)}">
              <strong>${esc(r.name_uk)}</strong>
              <span class="catalog-item-cat">${esc(r.relation_uk)}</span>
            </a>`).join("")}
        </div>` : `<p class="limitation-label">Пов'язані професії ще не додані.</p>`;
    }
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
    if (path === "market") return screenMarket();
    if (path === "region") return screenRegion();
    if (path === "login") return screenLoginHub();
    if (path === "privacy") return screenPrivacy();
    if (path === "terms") return screenTerms();
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
