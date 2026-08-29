// MNP V1 minimal functional frontend. Plain JS, hash router, no build
// step -- matches admin_frontend's own vanilla convention. Not pixel-
// perfect marketing design; the goal is that a user can go from landing
// to a real, explainable result without a developer in the loop.

const App = (() => {
  const root = document.getElementById("app");

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

  function setLoading() {
    root.innerHTML = `<div class="loading">Завантаження...</div>`;
  }

  function showError(err) {
    root.innerHTML = `<div class="error-box">Сталася помилка: ${err.message || err}</div><a href="#/" class="btn">На головну</a>`;
  }

  // --- Screens ---------------------------------------------------------

  function screenLanding() {
    root.innerHTML = `
      <h1>МОЖУ: Мій Напрям</h1>
      <p class="lead">Перетворюємо ваш досвід, навички та цілі на реалістичну карту кар'єрних переходів -- без "процентів збігу" і вигаданих даних.</p>
      <a href="#/start" class="btn">Знайти свій напрям</a>
      <a href="#/catalog" class="btn secondary">Переглянути професії</a>
    `;
  }

  function screenStart() {
    root.innerHTML = `
      <h1>Почнемо</h1>
      <p class="lead">Оберіть, як зручніше зібрати вашу кар'єрну карту.</p>
      <div class="choice-grid">
        <div class="choice-card" onclick="location.hash='#/upload'">
          <h3>Завантажити резюме</h3>
          <p>PDF, DOCX або TXT. Ми одразу структуруємо ваш досвід -- без додаткового підтвердження.</p>
        </div>
        <div class="choice-card" onclick="location.hash='#/questionnaire/capital'">
          <h3>Пройти без резюме</h3>
          <p>Коротка анкета: досвід, навички, освіта, а потім -- цілі.</p>
        </div>
      </div>
    `;
  }

  function screenUpload() {
    root.innerHTML = `
      <h1>Завантажте резюме</h1>
      <p class="lead">Підтримуються PDF (з текстовим шаром), DOCX, TXT.</p>
      <div class="field"><input type="file" id="cv-file" accept=".pdf,.docx,.txt"></div>
      <button class="btn" id="upload-btn">Завантажити</button>
      <div id="upload-status"></div>
    `;
    document.getElementById("upload-btn").addEventListener("click", async () => {
      const fileInput = document.getElementById("cv-file");
      const statusEl = document.getElementById("upload-status");
      if (!fileInput.files.length) { statusEl.textContent = "Оберіть файл спочатку."; return; }
      statusEl.textContent = "Обробка...";
      try {
        const result = await MnpApi.uploadDocument(fileInput.files[0]);
        if (result.extraction_status === "extracted" || result.extraction_status === "parse_partial") {
          location.hash = "#/questionnaire/capital";
        } else {
          statusEl.innerHTML = `<div class="error-box">Не вдалося розпізнати файл (${result.extraction_status}). Спробуйте пройти анкету без резюме.</div><a href="#/questionnaire/capital" class="btn">Заповнити анкету</a>`;
        }
      } catch (e) {
        statusEl.innerHTML = `<div class="error-box">${e.message}</div>`;
      }
    });
  }

  async function screenQuestionnaireCapital() {
    setLoading();
    const missing = await MnpApi.getMissingFields();
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
    document.getElementById("capital-next").addEventListener("click", async () => {
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
    document.getElementById("intent-submit").addEventListener("click", async () => {
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
    } catch (e) {
      showError(e);
    }
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
    } catch (e) {
      showError(e);
    }
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
    } catch (e) {
      showError(e);
    }
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
    } catch (e) {
      showError(e);
    }
  }

  async function screenCatalog() {
    setLoading();
    try {
      const careers = await MnpApi.listCareers();
      root.innerHTML = `
        <h1>Каталог професій</h1>
        ${careers.map((c) => `<div class="career-row" style="cursor:default"><div><strong>${c.name_uk}</strong><div class="limitation-label" style="margin-top:0.3rem">${c.description_short_uk}</div></div></div>`).join("")}
      `;
    } catch (e) {
      showError(e);
    }
  }

  async function screenCareerCard() {
    setLoading();
    try {
      const card = await MnpApi.getCareerCard();
      if (!card) {
        root.innerHTML = `<h1>Кар'єрна карта</h1><p class="lead">Картки ще немає.</p><a href="#/start" class="btn">Почати</a>`;
        return;
      }
      root.innerHTML = `
        <h1>Кар'єрна карта</h1>
        <p class="lead">Версія ${card.version}</p>
        <h2>Досвід</h2>
        ${card.experiences.map((e) => `<div class="card"><strong>${e.raw_job_title}</strong>${e.company_name ? ` -- ${e.company_name}` : ""}</div>`).join("") || "<p>Немає даних</p>"}
        <h2>Навички</h2>
        <div class="chips">${card.person_skills.map((s) => `<span class="chip">${s.proficiency_level}</span>`).join("") || "Немає даних"}</div>
        <h2>Освіта</h2>
        ${card.educations.map((e) => `<div class="card">${e.level}${e.graduation_year ? `, ${e.graduation_year}` : ""}</div>`).join("") || "<p>Немає даних</p>"}
        <p class="limitation-label">Редагування картки в інтерфейсі -- у розробці; наразі повторно пройдіть анкету, щоб оновити дані.</p>
        <a href="#/questionnaire/capital" class="btn">Оновити дані</a>
      `;
    } catch (e) {
      showError(e);
    }
  }

  // --- Router ------------------------------------------------------------

  function render() {
    const hash = location.hash || "#/";
    const [, path, param] = hash.match(/^#\/([^/]*)(?:\/(.*))?$/) || [null, "", null];

    if (path === "" ) return screenLanding();
    if (path === "start") return screenStart();
    if (path === "upload") return screenUpload();
    if (path === "questionnaire" && param === "capital") return screenQuestionnaireCapital();
    if (path === "questionnaire" && param === "intent") return screenQuestionnaireIntent();
    if (path === "processing") return screenProcessing();
    if (path === "results") return screenResults(param || localStorage.getItem("mnp_last_match_run"));
    if (path === "career") return screenCareerDetail(param);
    if (path === "route") return screenRoute(param);
    if (path === "catalog") return screenCatalog();
    if (path === "career-card") return screenCareerCard();
    return screenLanding();
  }

  window.addEventListener("hashchange", render);
  window.addEventListener("DOMContentLoaded", render);

  return { render };
})();
