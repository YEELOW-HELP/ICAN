// Generic, schema-driven field renderer implementing ТЗ §9/§22: standard
// controls (dropdown/radio/checkbox) instead of free text wherever there's
// a closed set of options, and an "Інше" escape hatch on every such field
// that reveals a manual text input when chosen.

export const OTHER_VALUE = "__other__";

const T = {
  TEXT: "text",
  TEXTAREA: "textarea",
  NUMBER: "number",
  DATE: "date",
  RADIO: "radio",
  SELECT: "select",
  MULTISELECT: "multiselect",
  TAGLIST: "taglist",
  CURRENCY: "currency",
};
export { T as FIELD_TYPE };

const CURRENCIES = ["UAH", "USD", "EUR"];
const FIELDS_OPTIONS = ["Фінанси", "Retail", "Manufacturing", "IT", "Освіта", "Медицина", "Логістика", "Будівництво"];

export const PROFILE_BLOCKS = [
  {
    title: "Поточна ситуація",
    fields: [
      { key: "currently_employed", label: "Працює зараз", type: T.RADIO, options: ["Так", "Ні"], bool: true },
      { key: "current_position", label: "Поточна посада", type: T.TEXT },
      { key: "current_fields", label: "Поточна сфера", type: T.MULTISELECT, options: FIELDS_OPTIONS },
      { key: "current_income", label: "Поточний дохід", type: T.CURRENCY, currencyKey: "current_income_currency" },
      { key: "search_reasons", label: "Причина пошуку", type: T.MULTISELECT, options: ["Без роботи", "Більший дохід", "Зміна професії", "Переїзд", "Незручний графік", "Конфлікт на роботі"] },
      { key: "readiness_to_start", label: "Готовність вийти", type: T.SELECT, options: ["Одразу", "2 тижні", "1 місяць"] },
      { key: "readiness_date", label: "Конкретна дата", type: T.DATE },
      { key: "urgency", label: "Терміновість пошуку", type: T.RADIO, options: ["Терміново", "До 1 місяця", "Розглядає варіанти"] },
      { key: "consultation_consent", label: "Згода на консультацію", type: T.RADIO, options: ["Так", "Ні"], bool: true },
      { key: "nonstandard_info", label: "Нестандартна інформація", type: T.TEXTAREA },
    ],
  },
  {
    title: "Освіта та кваліфікація",
    fields: [
      { key: "education_level", label: "Рівень освіти", type: T.SELECT, options: ["Середня", "Професійна", "Bachelor", "Master", "PhD"] },
      { key: "specialty", label: "Спеціальність", type: T.TEXT },
      { key: "institution", label: "Навчальний заклад", type: T.TEXT },
      { key: "graduation_year", label: "Рік закінчення", type: T.NUMBER },
      { key: "courses", label: "Курси", type: T.TAGLIST },
      { key: "driver_licenses", label: "Водійські права", type: T.MULTISELECT, options: ["B", "C", "D", "BE", "CE"] },
      { key: "other_qualification", label: "Інша кваліфікація", type: T.TEXT },
    ],
  },
  {
    title: "Career Target",
    fields: [
      { key: "primary_target", label: "Primary Career Target", type: T.TEXT },
      { key: "alternative_targets", label: "Alternative Targets", type: T.TAGLIST },
      { key: "interesting_fields", label: "Цікаві сфери", type: T.MULTISELECT, options: FIELDS_OPTIONS },
      { key: "avoid_fields", label: "Не пропонувати", type: T.MULTISELECT, options: FIELDS_OPTIONS },
      { key: "open_to_career_change", label: "Готовий змінити професію", type: T.RADIO, options: ["Так", "Ні", "Розглядаю"] },
    ],
  },
  {
    title: "Умови роботи",
    fields: [
      { key: "min_salary", label: "Мінімальна зарплата", type: T.CURRENCY, currencyKey: "salary_currency" },
      { key: "desired_salary", label: "Бажана зарплата", type: T.CURRENCY, currencyKey: "salary_currency" },
      { key: "employment_types", label: "Тип зайнятості", type: T.MULTISELECT, options: ["Full-time", "Part-time", "Contract", "Freelance"] },
      { key: "work_formats", label: "Формат", type: T.MULTISELECT, options: ["Office", "Remote", "Hybrid", "Flexible"] },
      { key: "schedules", label: "Графік", type: T.MULTISELECT, options: ["Стандартний", "Змінний", "Гнучкий"] },
      { key: "work_cities", label: "Місто роботи", type: T.TAGLIST },
      { key: "commute_limit", label: "Радіус / дорога", type: T.TEXT },
      { key: "relocation_ready", label: "Готовність до переїзду", type: T.RADIO, options: ["Так", "Ні", "За умов"] },
      { key: "relocation_cities", label: "Куди готовий переїхати", type: T.TAGLIST },
      { key: "business_trips_ok", label: "Командировки", type: T.RADIO, options: ["Так", "Ні", "Іноді"] },
      { key: "start_date", label: "Дата виходу", type: T.TEXT },
    ],
  },
  {
    title: "Практичні обмеження",
    fields: [
      { key: "constraints", label: "Обмеження", type: T.MULTISELECT, options: ["Без нічних змін", "Remote only", "Не піднімати тяжке", "До 6 год"] },
      { key: "critical_constraint", label: "Критичне для відсіву", type: T.RADIO, options: ["Так", "Ні"], bool: true },
      { key: "constraints_comment", label: "Коментар", type: T.TEXTAREA },
    ],
  },
];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function displayValue(field, value) {
  if (value === null || value === undefined || value === "") return null;
  if (field.type === T.RADIO && field.bool) return value ? "Так" : "Ні";
  if (Array.isArray(value)) return value.length ? value.join(", ") : null;
  if (field.type === T.CURRENCY) return value;
  return String(value);
}

export function renderFieldView(field, values) {
  const value = values[field.key];
  const display = displayValue(field, value);
  const suffix = field.type === T.CURRENCY && values[field.currencyKey] ? ` ${values[field.currencyKey]}` : "";
  return `<div class="text-sm text-slate-800 ${display ? "" : "text-slate-400"}">${display ? esc(display) + esc(suffix) : "Не вказано"}</div>`;
}

export function renderFieldEdit(field, values) {
  const value = values[field.key];
  const base = `data-field="${field.key}" data-type="${field.type}"`;

  if (field.type === T.TEXT) {
    return `<input ${base} value="${esc(value ?? "")}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />`;
  }
  if (field.type === T.TEXTAREA) {
    return `<textarea ${base} rows="2" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">${esc(value ?? "")}</textarea>`;
  }
  if (field.type === T.NUMBER) {
    return `<input ${base} type="number" value="${esc(value ?? "")}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />`;
  }
  if (field.type === T.DATE) {
    return `<input ${base} type="date" value="${esc(value ?? "")}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />`;
  }
  if (field.type === T.TAGLIST) {
    const joined = Array.isArray(value) ? value.join(", ") : "";
    return `<input ${base} value="${esc(joined)}" placeholder="через кому" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />`;
  }
  if (field.type === T.CURRENCY) {
    const cur = values[field.currencyKey] || "";
    return `
      <div class="flex gap-2">
        <input ${base} type="number" value="${esc(value ?? "")}" class="w-2/3 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select data-field="${field.currencyKey}" data-type="select-plain" class="w-1/3 rounded-lg border border-slate-300 px-2 py-2 text-sm">
          <option value="">—</option>
          ${CURRENCIES.map((c) => `<option value="${c}" ${cur === c ? "selected" : ""}>${c}</option>`).join("")}
        </select>
      </div>`;
  }
  if (field.type === T.RADIO) {
    const current = field.bool ? (value === true ? field.options[0] : value === false ? field.options[1] : null) : value;
    return `
      <div class="flex gap-4" ${base}>
        ${field.options.map((opt) => `
          <label class="flex items-center gap-1.5 text-sm">
            <input type="radio" name="radio-${field.key}" value="${esc(opt)}" ${current === opt ? "checked" : ""} />
            ${esc(opt)}
          </label>`).join("")}
      </div>`;
  }
  if (field.type === T.SELECT) {
    const isOther = value && !field.options.includes(value);
    return `
      <div ${base}>
        <select data-role="select" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="">—</option>
          ${field.options.map((opt) => `<option value="${esc(opt)}" ${value === opt ? "selected" : ""}>${esc(opt)}</option>`).join("")}
          <option value="${OTHER_VALUE}" ${isOther ? "selected" : ""}>Інше…</option>
        </select>
        <input data-role="other" value="${esc(isOther ? value : "")}" placeholder="Вкажіть свій варіант"
          class="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm ${isOther ? "" : "hidden"}" />
      </div>`;
  }
  if (field.type === T.MULTISELECT) {
    const selected = Array.isArray(value) ? value : [];
    const extra = selected.filter((v) => !field.options.includes(v));
    return `
      <div ${base}>
        <div class="flex flex-wrap gap-x-4 gap-y-1.5">
          ${field.options.map((opt) => `
            <label class="flex items-center gap-1.5 text-sm">
              <input type="checkbox" data-role="option" value="${esc(opt)}" ${selected.includes(opt) ? "checked" : ""} />
              ${esc(opt)}
            </label>`).join("")}
          <label class="flex items-center gap-1.5 text-sm">
            <input type="checkbox" data-role="other-toggle" ${extra.length ? "checked" : ""} />
            Інше
          </label>
        </div>
        <input data-role="other" value="${esc(extra.join(", "))}" placeholder="через кому"
          class="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm ${extra.length ? "" : "hidden"}" />
      </div>`;
  }
  return `<input ${base} value="${esc(value ?? "")}" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />`;
}

export function wireFieldEditEvents(container) {
  container.querySelectorAll('[data-type="select"] select[data-role="select"]').forEach((select) => {
    select.addEventListener("change", () => {
      const otherInput = select.parentElement.querySelector('[data-role="other"]');
      otherInput.classList.toggle("hidden", select.value !== OTHER_VALUE);
    });
  });
  container.querySelectorAll('[data-type="multiselect"] input[data-role="other-toggle"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const otherInput = cb.closest("[data-field]").querySelector('[data-role="other"]');
      otherInput.classList.toggle("hidden", !cb.checked);
    });
  });
}

export function renderProfileBlocks(values, editing) {
  return PROFILE_BLOCKS.map((block, blockIdx) => `
    <details class="bg-white rounded-xl border border-slate-200 overflow-hidden" ${blockIdx === 0 ? "open" : ""}>
      <summary class="cursor-pointer select-none px-5 py-3 font-medium text-slate-800 bg-slate-50 hover:bg-slate-100">${block.title}</summary>
      <div class="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        ${block.fields.map((field) => `
          <div>
            <label class="block text-xs font-medium text-slate-500 mb-1">${field.label}</label>
            ${editing ? renderFieldEdit(field, values) : renderFieldView(field, values)}
          </div>`).join("")}
      </div>
    </details>`).join("");
}

export function collectProfileChanges(container) {
  const changes = {};
  for (const block of PROFILE_BLOCKS) {
    for (const field of block.fields) {
      const wrapper = container.querySelector(`[data-field="${field.key}"]`);
      if (!wrapper) continue;
      changes[field.key] = collectFieldValue(field, wrapper);
      if (field.currencyKey) {
        const curEl = container.querySelector(`[data-field="${field.currencyKey}"]`);
        if (curEl) changes[field.currencyKey] = curEl.value || null;
      }
    }
  }
  return changes;
}

export function collectFieldValue(field, wrapper) {
  if (field.type === T.TEXT || field.type === T.TEXTAREA) {
    return wrapper.value.trim() || null;
  }
  if (field.type === T.NUMBER) {
    return wrapper.value.trim() || null;
  }
  if (field.type === T.DATE) {
    return wrapper.value || null;
  }
  if (field.type === T.TAGLIST) {
    const raw = wrapper.value.trim();
    return raw ? raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
  }
  if (field.type === T.RADIO) {
    const checked = wrapper.querySelector("input[type=radio]:checked");
    if (!checked) return null;
    if (field.bool) return checked.value === field.options[0];
    return checked.value;
  }
  if (field.type === T.SELECT) {
    const select = wrapper.querySelector('[data-role="select"]');
    const other = wrapper.querySelector('[data-role="other"]');
    if (select.value === OTHER_VALUE) return other.value.trim() || null;
    return select.value || null;
  }
  if (field.type === T.MULTISELECT) {
    const checked = [...wrapper.querySelectorAll('input[data-role="option"]:checked')].map((el) => el.value);
    const otherToggle = wrapper.querySelector('[data-role="other-toggle"]');
    if (otherToggle?.checked) {
      const extra = wrapper.querySelector('[data-role="other"]').value.trim();
      if (extra) checked.push(...extra.split(",").map((s) => s.trim()).filter(Boolean));
    }
    return checked;
  }
  return wrapper.value?.trim() || null;
}
