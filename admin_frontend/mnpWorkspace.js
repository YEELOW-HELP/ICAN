// Stage 4A: MNP consultant workspace (Direction Intelligence Dashboard /
// Client Card). Consumes ONLY the existing Stage 3B/3.5 read model via
// api.mnp* -- no Direction/scoring logic is reconstructed here.
import { api, ApiError, getSession } from "./api.js";
import { attachShellEvents, esc, fmtDate, shell, toast } from "./ui.js";

const BAND_META = {
  high: { label: "HIGH", cls: "bg-emerald-100 text-emerald-700" },
  medium: { label: "MEDIUM", cls: "bg-amber-100 text-amber-700" },
  low: { label: "LOW", cls: "bg-red-100 text-red-700" },
};
const UNKNOWN_BAND = { label: "UNKNOWN", cls: "bg-slate-100 text-slate-500" };

function bandBadge(band) {
  const m = band ? (BAND_META[band] || UNKNOWN_BAND) : UNKNOWN_BAND;
  return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${m.cls}">${m.label}</span>`;
}

const PLACEMENT_META = {
  main: { label: "MAIN", cls: "bg-brand-100 text-brand-700" },
  alternative: { label: "ALTERNATIVE", cls: "bg-indigo-100 text-indigo-700" },
  blocked: { label: "BLOCKED", cls: "bg-red-100 text-red-700" },
  not_eligible: { label: "NOT ELIGIBLE", cls: "bg-slate-100 text-slate-500" },
  deduped: { label: "DEDUPED", cls: "bg-slate-100 text-slate-500" },
  unranked: { label: "UNRANKED", cls: "bg-slate-100 text-slate-500" },
};
function placementBadge(p) {
  const m = PLACEMENT_META[p] || { label: p, cls: "bg-slate-100 text-slate-500" };
  return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${m.cls}">${m.label}</span>`;
}

const REVIEW_META = {
  pending_review: { label: "Очікує перегляду", cls: "bg-amber-100 text-amber-700" },
  approved: { label: "Затверджено", cls: "bg-emerald-100 text-emerald-700" },
  changes_requested: { label: "Потрібні зміни", cls: "bg-orange-100 text-orange-700" },
  rejected: { label: "Відхилено", cls: "bg-red-100 text-red-700" },
};
function reviewBadge(status) {
  if (!status) return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-500">Немає рев'ю</span>`;
  const m = REVIEW_META[status] || { label: status, cls: "bg-slate-100 text-slate-600" };
  return `<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${m.cls}">${m.label}</span>`;
}

const RUN_STATUS_META = {
  ready: { label: "Готово", cls: "text-emerald-600" },
  generating: { label: "Генерується…", cls: "text-slate-500" },
  failed: { label: "Помилка", cls: "text-red-600" },
  insufficient_information: { label: "Недостатньо даних", cls: "text-amber-600" },
};

const REASON_CODES = [
  ["wrong_inference", "Неправильний висновок"],
  ["missing_inference", "Пропущений висновок"],
  ["wrong_dimension", "Неправильний вимір"],
  ["overconfidence", "Завищена впевненість"],
  ["underconfidence", "Занижена впевненість"],
  ["contradiction_missed", "Пропущена суперечність"],
  ["constraint_missed", "Пропущене обмеження"],
  ["unsupported_fact", "Непідтверджений факт"],
  ["wrong_direction_priority", "Неправильний пріоритет напряму"],
  ["career_knowledge_problem", "Проблема бази знань про кар'єри"],
  ["evidence_extraction_problem", "Проблема витягу доказів"],
  ["wording_only", "Лише формулювання"],
  ["other_with_comment", "Інше (з коментарем)"],
];

const DIMENSION_GROUPS = [
  { key: "attracts", title: "A. ЩО МЕНЕ ПРИВАБЛЮЄ", dims: ["interests", "values", "motivation"] },
  { key: "how", title: "B. ЯК Я ПРАЦЮЮ НАЙКРАЩЕ", dims: ["work_style", "work_environment"] },
  { key: "bring", title: "C. ЩО Я ПРИНОШУ", dims: ["strengths", "skills", "abilities_learning_potential", "experience"] },
  { key: "goals", title: "D. КУДИ Я ХОЧУ РУХАТИСЯ", dims: ["goals"] },
  { key: "consider", title: "E. ЩО ВРАХУВАТИ", dims: ["constraints", "career_adaptability"] },
];

const DIM_LABELS = {
  interests: "Інтереси", values: "Цінності", motivation: "Мотивація", work_style: "Стиль роботи",
  work_environment: "Середовище роботи", strengths: "Сильні сторони", skills: "Навички",
  abilities_learning_potential: "Здібності / потенціал навчання", experience: "Досвід", goals: "Цілі",
  constraints: "Обмеження", career_adaptability: "Кар'єрна адаптивність",
};

let mnpListState = { filter: "" };

const LIST_FILTERS = [
  ["", "Усі"], ["needs_review", "Потребують перегляду"], ["blockers", "Є блокери"],
  ["changes_requested", "Потрібні зміни"], ["approved", "Затверджено"],
  ["insufficient_information", "Недостатньо даних"], ["no_directions_yet", "Ще без напрямів"],
];

export async function renderMnpList(root, navigate) {
  root.innerHTML = shell("mnp", `<div class="p-8 text-slate-400">Завантаження…</div>`);
  let items;
  try {
    items = await api.mnpListClients(mnpListState.filter || null);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return;
    root.innerHTML = shell("mnp", `<div class="p-8 text-red-600">Помилка: ${esc(err.message)}</div>`);
    return;
  }

  root.innerHTML = shell("mnp", `
    <div class="p-8 max-w-6xl mx-auto">
      <h1 class="text-2xl font-semibold text-slate-900 mb-1">Напрями (MNP)</h1>
      <p class="text-sm text-slate-500 mb-6">Консультантський воркспейс Direction Intelligence.</p>

      <div class="flex flex-wrap gap-2 mb-4">
        ${LIST_FILTERS.map(([value, label]) => `
          <button data-filter="${value}" class="text-xs px-3 py-1.5 rounded-full border ${mnpListState.filter === value ? "bg-brand-600 text-white border-brand-600" : "border-slate-200 text-slate-600 hover:bg-slate-50"}">${label}</button>`).join("")}
      </div>

      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
            <tr>
              <th class="text-left px-4 py-3 font-medium">User ID</th>
              <th class="text-left px-4 py-3 font-medium">Профіль</th>
              <th class="text-left px-4 py-3 font-medium">DirectionRun</th>
              <th class="text-left px-4 py-3 font-medium">Рев'ю</th>
              <th class="text-left px-4 py-3 font-medium">Блокери</th>
              <th class="text-left px-4 py-3 font-medium">Попередження</th>
              <th class="text-left px-4 py-3 font-medium">Оновлено</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            ${items.length === 0 ? `<tr><td colspan="7" class="text-center text-slate-400 py-10">Нічого не знайдено</td></tr>` : ""}
            ${items.map((c) => `
              <tr class="hover:bg-slate-50 cursor-pointer transition-colors" data-id="${c.user_id}">
                <td class="px-4 py-3 font-mono text-xs text-slate-700">${esc(c.user_id.slice(0, 8))}…</td>
                <td class="px-4 py-3 text-slate-600">${esc(c.profile_status || "—")} ${c.profile_version ? `v${c.profile_version}` : ""}</td>
                <td class="px-4 py-3 text-slate-600">
                  ${c.direction_run_id ? `<span class="${(RUN_STATUS_META[c.direction_run_status] || {}).cls || ""}">${(RUN_STATUS_META[c.direction_run_status] || {}).label || esc(c.direction_run_status)}</span> v${c.direction_run_version}` : `<span class="text-slate-400">немає</span>`}
                </td>
                <td class="px-4 py-3">${reviewBadge(c.review_status)}</td>
                <td class="px-4 py-3">${c.blocker_count > 0 ? `<span class="text-red-600 font-semibold">${c.blocker_count}</span>` : "0"}</td>
                <td class="px-4 py-3">${c.warning_count > 0 ? `<span class="text-amber-600 font-semibold">${c.warning_count}</span>` : "0"}</td>
                <td class="px-4 py-3 text-slate-400 text-xs">${fmtDate(c.last_updated)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
        </div>
      </div>
    </div>`);

  attachShellEvents();
  root.querySelectorAll("tbody tr[data-id]").forEach((row) => {
    row.addEventListener("click", () => navigate(`#/mnp/${row.dataset.id}`));
  });
  root.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => { mnpListState.filter = btn.dataset.filter; renderMnpList(root, navigate); });
  });
}

let activeMnpTab = "profile";

export async function renderMnpClientCard(root, userId, navigate) {
  root.innerHTML = `<div class="p-8 text-slate-400">Завантаження…</div>`;
  let card;
  try {
    card = await api.mnpClientCard(userId);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return;
    if (err instanceof ApiError && err.status === 404) {
      root.innerHTML = shell("mnp", `
        <div class="p-8 max-w-3xl mx-auto text-center">
          <p class="text-slate-500 mb-4">У цього клієнта ще немає жодного DirectionRun.</p>
          <button id="gen-first" class="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg">Згенерувати напрями</button>
        </div>`);
      attachShellEvents();
      document.getElementById("gen-first").addEventListener("click", async () => {
        try { await api.mnpGenerateDirections(userId); renderMnpClientCard(root, userId, navigate); }
        catch (e) { toast(e.message, "error"); }
      });
      return;
    }
    root.innerHTML = shell("mnp", `<div class="p-8 text-red-600">Помилка: ${esc(err.message)}</div>`);
    return;
  }

  const session = getSession();
  const canReview = ["admin", "career_consultant"].includes(session?.role); // super_admin has no separate frontend role today
  const runId = card.client.direction_run_id;

  root.innerHTML = shell("mnp", `
    <div class="max-w-6xl mx-auto p-6">
      <a href="#/mnp" class="text-sm text-slate-500 hover:text-brand-600">← До списку</a>

      <div class="bg-white rounded-xl border border-slate-200 p-6 mt-3 mb-5 sticky top-4 z-10 shadow-sm">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-lg font-mono font-semibold text-slate-900">${esc(card.client.user_id)}</h1>
              ${reviewBadge(card.client.review_status)}
            </div>
            <div class="flex flex-wrap items-center gap-3 mt-2 text-sm text-slate-500">
              <span>Профіль: ${esc(card.client.profile_id)} v${card.client.profile_version}</span>
              <span>Run: v${card.client.direction_run_version}</span>
              <span>Блокери: <b class="${card.critic_summary.blocker_count > 0 ? "text-red-600" : "text-emerald-600"}">${card.critic_summary.blocker_count}</b></span>
              <span>Попередження: <b class="text-amber-600">${card.critic_summary.warning_count}</b></span>
            </div>
          </div>
          <div class="flex flex-wrap gap-2 justify-end">
            <button id="act-generate" class="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">🔄 Перегенерувати</button>
            <button id="act-critic" class="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">🔍 Запустити Critic</button>
            <button id="act-narrative" class="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50">✍ Згенерувати наратив</button>
            ${canReview ? `
            <button id="act-approve" class="text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white">✔ Затвердити</button>
            <button id="act-changes" class="text-xs px-3 py-1.5 rounded-lg border border-amber-300 text-amber-700 hover:bg-amber-50">✎ Потрібні зміни</button>
            <button id="act-reject" class="text-xs px-3 py-1.5 rounded-lg border border-red-300 text-red-700 hover:bg-red-50">✖ Відхилити</button>` : ""}
          </div>
        </div>
      </div>

      <div class="border-b border-slate-200 mb-5">
        <nav class="flex gap-6 text-sm overflow-x-auto">
          ${tabBtn("profile", "Профіль")}
          ${tabBtn("directions", "Напрями")}
          ${tabBtn("critic", "Critic")}
          ${tabBtn("publish", "Публікація")}
        </nav>
      </div>

      <div id="tab-content"></div>
    </div>`);

  attachShellEvents();

  const rerender = () => renderMnpClientCard(root, userId, navigate);

  document.getElementById("act-generate").addEventListener("click", async () => {
    try { await api.mnpGenerateDirections(userId); toast("Нова генерація запущена"); rerender(); }
    catch (e) { toast(e.message, "error"); }
  });
  document.getElementById("act-critic").addEventListener("click", async () => {
    try { const r = await api.mnpRunCritic(runId); toast(`Critic: ${r.blocker_count} блокерів, ${r.warning_count} попереджень`); rerender(); }
    catch (e) { toast(e.message, "error"); }
  });
  document.getElementById("act-narrative").addEventListener("click", async () => {
    try { const r = await api.mnpGenerateNarrative(runId); toast(`Наратив згенеровано для ${r.narrated_count} напрямів`); rerender(); }
    catch (e) { toast(e.message, "error"); }
  });
  if (canReview) {
    document.getElementById("act-approve").addEventListener("click", async () => {
      if (!confirm("Затвердити цей результат?")) return;
      try { await api.mnpApprove(runId, null); toast("Затверджено"); rerender(); }
      catch (e) { toast(e.message, "error"); }
    });
    document.getElementById("act-changes").addEventListener("click", async () => {
      const comment = prompt("Коментар (обов'язково):");
      if (!comment) return;
      try { await api.mnpRequestChanges(runId, comment); toast("Позначено як 'потрібні зміни'"); rerender(); }
      catch (e) { toast(e.message, "error"); }
    });
    document.getElementById("act-reject").addEventListener("click", async () => {
      const comment = prompt("Причина відхилення (обов'язково):");
      if (!comment) return;
      try { await api.mnpReject(runId, comment); toast("Відхилено"); rerender(); }
      catch (e) { toast(e.message, "error"); }
    });
  }

  root.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => { activeMnpTab = btn.dataset.tab; rerender(); });
  });

  const tabContent = document.getElementById("tab-content");
  if (activeMnpTab === "profile") tabContent.innerHTML = profileTabHtml(card);
  else if (activeMnpTab === "directions") { tabContent.innerHTML = directionsTabHtml(card); wireDirectionsTab(tabContent, runId, rerender); }
  else if (activeMnpTab === "critic") tabContent.innerHTML = criticTabHtml(card);
  else if (activeMnpTab === "publish") await renderPublishTab(tabContent, userId);
}

function tabBtn(key, label) {
  const active = activeMnpTab === key;
  return `<button data-tab="${key}" class="tab-btn pb-3 border-b-2 font-medium whitespace-nowrap transition-colors ${active ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700"}">${label}</button>`;
}

// ---------------- Profile tab ----------------

function profileTabHtml(card) {
  const claimsByDim = {};
  for (const claim of card.profile_claims) {
    const key = claim.canonical_dimension || "_unmapped";
    (claimsByDim[key] = claimsByDim[key] || []).push(claim);
  }

  const groupsHtml = DIMENSION_GROUPS.map((group) => {
    const claims = group.dims.flatMap((d) => claimsByDim[d] || []);
    return `
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <h3 class="text-sm font-semibold text-slate-800 mb-3">${group.title}</h3>
        ${claims.length === 0
          ? `<p class="text-xs text-slate-400">Немає підтверджених тверджень у цьому блоці.</p>`
          : `<div class="space-y-2">${claims.map(claimCardHtml).join("")}</div>`}
      </div>`;
  }).join("");

  const unmapped = claimsByDim["_unmapped"] || [];
  const unmappedHtml = unmapped.length ? `
    <details class="bg-white rounded-xl border border-slate-200 p-5">
      <summary class="text-sm font-semibold text-slate-600 cursor-pointer">Потребує уточнення методології (${unmapped.length})</summary>
      <div class="space-y-2 mt-3">${unmapped.map(claimCardHtml).join("")}</div>
    </details>` : "";

  return `
    <div class="mb-4 bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap gap-4 text-sm text-slate-600">
      <span>Підтверджених тверджень: <b>${card.profile_summary.supported_claim_count}</b></span>
      <span>Виміри охоплено: <b>${card.profile_summary.canonical_dimensions_covered.length}/12</b></span>
      <span>Суперечності: <b class="${card.profile_summary.contradiction_count > 0 ? "text-red-600" : ""}">${card.profile_summary.contradiction_count}</b></span>
      <span>Впевненість: ${bandBadge(card.profile_summary.confidence_band)}</span>
    </div>
    <div class="grid md:grid-cols-2 gap-4">${groupsHtml}</div>
    <div class="mt-4">${unmappedHtml}</div>`;
}

function claimCardHtml(claim) {
  const statusColor = claim.is_contradicted ? "text-red-600" : claim.status === "supported" ? "text-emerald-600" : "text-slate-500";
  return `
    <details class="border border-slate-100 rounded-lg p-3">
      <summary class="cursor-pointer flex items-center justify-between gap-2">
        <span class="text-sm text-slate-800">${esc(claim.label)}</span>
        <span class="flex items-center gap-2 shrink-0">
          ${claim.is_contradicted ? `<span class="text-[11px] text-red-600 font-semibold">⚠ суперечність</span>` : ""}
          <span class="text-[11px] ${statusColor} uppercase font-medium">${esc(claim.status)}</span>
        </span>
      </summary>
      <div class="mt-2 text-xs text-slate-500 space-y-1">
        <div>${esc(claim.normalized_value)}</div>
        <div>Впевненість: ${(claim.confidence * 100).toFixed(0)}% · Вимір: ${esc(claim.canonical_dimension ? DIM_LABELS[claim.canonical_dimension] || claim.canonical_dimension : "не визначено")}${claim.canonical_subdimension ? ` / ${esc(claim.canonical_subdimension)}` : ""}</div>
        <div>Доказів: ${claim.evidence.length}${claim.evidence.length ? " (" + claim.evidence.map((e) => esc(e.source_type)).join(", ") + ")" : ""}</div>
      </div>
    </details>`;
}

// ---------------- Directions tab ----------------

function directionsTabHtml(card) {
  const main = card.directions.filter((d) => d.effective_placement === "main");
  const alt = card.directions.filter((d) => d.effective_placement === "alternative");
  const technical = card.directions.filter((d) => !["main", "alternative"].includes(d.effective_placement));

  return `
    <div class="space-y-6">
      <div>
        <h3 class="text-sm font-semibold text-slate-700 mb-2">MAIN</h3>
        ${main.length === 0 ? `<p class="text-xs text-slate-400">Немає.</p>` : `<div class="grid md:grid-cols-2 gap-3">${main.map(directionCardHtml).join("")}</div>`}
      </div>
      <div>
        <h3 class="text-sm font-semibold text-slate-700 mb-2">ALTERNATIVE</h3>
        ${alt.length === 0 ? `<p class="text-xs text-slate-400">Немає.</p>` : `<div class="grid md:grid-cols-2 gap-3">${alt.map(directionCardHtml).join("")}</div>`}
      </div>
      <details class="bg-slate-50 rounded-xl border border-slate-200 p-4">
        <summary class="text-xs font-semibold text-slate-500 cursor-pointer uppercase">Технічна секція: DEDUPED / BLOCKED / NOT_ELIGIBLE (${technical.length})</summary>
        <div class="grid md:grid-cols-2 gap-3 mt-3">${technical.map(directionCardHtml).join("")}</div>
      </details>
    </div>`;
}

function directionCardHtml(d) {
  const systemVsEffective = d.system_placement !== d.effective_placement ? `
    <div class="mt-2 text-[11px] bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5">
      <div>SYSTEM: ${placementBadge(d.system_placement)}</div>
      <div class="mt-1">CONSULTANT: ${placementBadge(d.effective_placement)}</div>
    </div>` : "";

  const narrative = d.effective_narrative;
  const outputs = d.outputs;

  return `
    <div class="border border-slate-200 rounded-xl p-4 bg-white">
      <div class="flex items-center justify-between gap-2 mb-2">
        <div class="font-medium text-slate-800 text-sm">${esc(d.career_title || d.career_code)}</div>
        ${placementBadge(d.effective_placement)}
      </div>
      ${systemVsEffective}
      <div class="grid grid-cols-2 gap-2 my-3 text-xs">
        <div class="flex items-center justify-between bg-slate-50 rounded-lg px-2 py-1.5"><span>Potential Fit</span>${bandBadge(outputs.potential_fit_band)}</div>
        <div class="flex items-center justify-between bg-slate-50 rounded-lg px-2 py-1.5"><span>Goal Alignment</span>${bandBadge(outputs.goal_alignment_band)}</div>
        <div class="flex items-center justify-between bg-slate-50 rounded-lg px-2 py-1.5"><span>Transition Feasibility</span>${bandBadge(outputs.transition_feasibility_band)}</div>
        <div class="flex items-center justify-between bg-slate-50 rounded-lg px-2 py-1.5"><span>Evidence Confidence</span>${bandBadge(outputs.evidence_confidence_band)}</div>
      </div>

      ${narrative ? `<p class="text-xs text-slate-600 mb-2">${esc(narrative.summary)}</p>` : ""}
      ${d.trade_off_notes ? `<div class="text-[11px] text-amber-700 bg-amber-50 rounded-lg px-2 py-1 mb-2">⚠ ${esc(d.trade_off_notes)}</div>` : ""}
      ${d.skills_to_verify.length ? `<div class="text-[11px] text-slate-500 mb-2">Перевірити навички: ${d.skills_to_verify.map(esc).join(", ")}</div>` : ""}

      <details class="text-xs">
        <summary class="cursor-pointer text-brand-600">Деталі / EXPERIMENTAL / Provenance</summary>
        <div class="mt-2 space-y-2 text-slate-500">
          ${explanationSectionHtml("WHY FIT", d.explanation_bundle?.why_fit?.strongest_supported_factors)}
          ${explanationSectionHtml("WHY NOW", d.explanation_bundle?.why_now?.goal_alignment_factors)}
          <div>TRANSITION: ${d.explanation_bundle?.transition?.confirmed_gaps?.length ? "прогалини: " + d.explanation_bundle.transition.confirmed_gaps.map(esc).join(", ") : "без підтверджених прогалин"}</div>
          <div>CONFIDENCE: ${esc(d.explanation_bundle?.confidence?.coverage_note || "—")}</div>
          <div class="border-t border-slate-100 pt-2">
            <div class="text-[10px] uppercase text-slate-400 mb-1">EXPERIMENTAL raw values</div>
            <div>PF=${outputs.potential_fit_raw ?? "—"} · GA=${outputs.goal_alignment_raw ?? "—"} · TF=${outputs.transition_feasibility_raw ?? "—"} · EC=${outputs.evidence_confidence_raw ?? "—"}</div>
          </div>
          <div class="text-[10px] text-slate-400">career_id: ${esc(d.career_id)}</div>
        </div>
      </details>

      ${(d.critic_findings || []).length ? `
        <div class="mt-2 space-y-1">
          ${d.critic_findings.map((f) => `<div class="text-[11px] ${f.severity === "blocker" ? "text-red-600" : "text-amber-600"}">${f.severity === "blocker" ? "🛑" : "⚠"} ${esc(f.code)}: ${esc(f.message)}</div>`).join("")}
        </div>` : ""}

      <div class="mt-3 flex gap-2">
        <button data-correct-placement="${d.direction_id}" data-current="${esc(d.effective_placement)}" class="text-[11px] text-brand-600 hover:underline">Виправити розміщення</button>
        <button data-correct-narrative="${d.direction_id}" class="text-[11px] text-brand-600 hover:underline">Виправити текст</button>
      </div>
      ${(d.applied_corrections || []).length ? `<div class="mt-1 text-[10px] text-slate-400">Корекцій застосовано: ${d.applied_corrections.length}</div>` : ""}
    </div>`;
}

function explanationSectionHtml(title, factors) {
  if (!factors || !factors.length) return `<div>${title}: немає структурованих даних.</div>`;
  return `<div>${title}: ${factors.map((f) => `${esc(f.component_key)} (${(f.raw_score_experimental * 100).toFixed(0)}%)`).join(", ")}</div>`;
}

function wireDirectionsTab(container, runId, rerender) {
  container.querySelectorAll("[data-correct-placement]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const options = ["main", "alternative", "not_eligible", "blocked"];
      const value = prompt(`Нове ефективне розміщення (${options.join(" / ")}):`, btn.dataset.current);
      if (!value || !options.includes(value)) return;
      const reason = await pickReasonCode();
      if (!reason) return;
      try {
        await api.mnpCreateCorrection(runId, {
          artifact_type: "direction_placement", direction_id: btn.dataset.correctPlacement,
          corrected_placement: value, reason_code: reason.code, comment: reason.comment,
        });
        toast("Корекцію збережено");
        rerender();
      } catch (e) { toast(e.message, "error"); }
    });
  });
  container.querySelectorAll("[data-correct-narrative]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = prompt("Новий текст (summary):");
      if (!text) return;
      try {
        await api.mnpCreateCorrection(runId, {
          artifact_type: "narrative", direction_id: btn.dataset.correctNarrative, corrected_text: text,
          narrative_field: "summary", reason_code: "wording_only", comment: "consultant wording correction",
        });
        toast("Текст виправлено");
        rerender();
      } catch (e) { toast(e.message, "error"); }
    });
  });
}

function pickReasonCode() {
  const list = REASON_CODES.map(([code, label], i) => `${i + 1}. ${label}`).join("\n");
  const choice = prompt(`Оберіть код причини (1-${REASON_CODES.length}):\n${list}`);
  const idx = parseInt(choice, 10) - 1;
  if (isNaN(idx) || !REASON_CODES[idx]) return null;
  const comment = prompt("Коментар:") || "";
  return { code: REASON_CODES[idx][0], comment };
}

// ---------------- Critic tab ----------------

function criticTabHtml(card) {
  const all = card.directions.flatMap((d) => (d.critic_findings || []).map((f) => ({ ...f, career: d.career_title || d.career_code })));
  const blockers = all.filter((f) => f.severity === "blocker");
  const warnings = all.filter((f) => f.severity === "warning");
  const info = all.filter((f) => f.severity === "info");

  const section = (title, items, colorCls) => `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="text-sm font-semibold ${colorCls} mb-2">${title} (${items.length})</h3>
      ${items.length === 0 ? `<p class="text-xs text-slate-400">Немає.</p>` : `
      <div class="space-y-2">
        ${items.map((f) => `
          <div class="text-xs border border-slate-100 rounded-lg p-2">
            <div class="font-mono text-[11px] text-slate-500">${esc(f.code)}</div>
            <div class="text-slate-700">${esc(f.message)}</div>
            <div class="text-[10px] text-slate-400 mt-1">Напрям: ${esc(f.career)}</div>
          </div>`).join("")}
      </div>`}
    </div>`;

  return `
    <div class="space-y-4">
      ${blockers.length > 0 ? `<div class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">🛑 Затвердження неможливе, поки не вирішено ${blockers.length} блокер(и).</div>` : ""}
      ${section("BLOCKERS", blockers, "text-red-700")}
      ${section("WARNINGS", warnings, "text-amber-700")}
      ${section("INFO", info, "text-slate-500")}
    </div>`;
}

// ---------------- Publishable preview tab ----------------

async function renderPublishTab(container, userId) {
  container.innerHTML = `<div class="text-slate-400 text-sm">Завантаження…</div>`;
  let preview;
  try {
    preview = await api.mnpPublishablePreview(userId);
  } catch (err) {
    container.innerHTML = `<div class="text-red-600 text-sm">Помилка: ${esc(err.message)}</div>`;
    return;
  }

  if (!preview.publishable) {
    container.innerHTML = `
      <div class="bg-slate-50 border border-slate-200 rounded-xl p-6 text-center">
        <div class="text-lg font-semibold text-slate-500 mb-2">НЕ ГОТОВО ДО ПУБЛІКАЦІЇ</div>
        <p class="text-sm text-slate-500">${esc(preview.reason || "")}</p>
      </div>`;
    return;
  }

  const result = preview.result;
  container.innerHTML = `
    <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4 text-sm text-emerald-800">
      ✔ Готово до публікації — це результат, який побачить майбутній клієнтський звіт (ефективна версія, з урахуванням корекцій).
    </div>
    <div class="grid md:grid-cols-2 gap-3">
      ${result.directions.filter((d) => ["main", "alternative"].includes(d.effective_placement)).map(directionCardHtml).join("")}
    </div>`;
}
