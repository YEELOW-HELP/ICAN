/* NAPRIAM shared UI helpers — a tiny inline-SVG icon set so the product
 * stops relying on OS emoji for primary interface icons. No framework, no
 * external library. All icons: 20x20 viewBox, stroke = currentColor. */
const NvUI = (() => {
  const P = {
    grid: '<rect x="3" y="3" width="6.5" height="6.5" rx="1.4"/><rect x="10.5" y="3" width="6.5" height="6.5" rx="1.4"/><rect x="3" y="10.5" width="6.5" height="6.5" rx="1.4"/><rect x="10.5" y="10.5" width="6.5" height="6.5" rx="1.4"/>',
    user: '<circle cx="10" cy="6.6" r="3.1"/><path d="M4 16.5c1.4-2.9 4-4 6-4s4.6 1.1 6 4"/>',
    briefcase: '<rect x="3" y="6.5" width="14" height="10" rx="1.6"/><path d="M7.5 6.5V5.2c0-.8.6-1.4 1.4-1.4h2.2c.8 0 1.4.6 1.4 1.4v1.3"/><path d="M3 10.5h14"/>',
    compass: '<circle cx="10" cy="10" r="7.2"/><path d="M13.2 6.8 11.4 11l-4.2 1.8L9 8.6z"/>',
    target: '<circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="3.4"/><circle cx="10" cy="10" r=".6" fill="currentColor"/>',
    layers: '<path d="m10 3 7 3.8-7 3.8L3 6.8z"/><path d="m3.5 10 6.5 3.6L16.5 10"/><path d="m3.5 13.4 6.5 3.6 6.5-3.6"/>',
    route: '<circle cx="5.5" cy="15" r="2"/><circle cx="14.5" cy="5" r="2"/><path d="M7.4 14.2c4-1 5-3 5-6M12.5 7h-3M12.5 7v2.5"/>',
    checklist: '<path d="M8 5.5h9M8 10h9M8 14.5h9"/><path d="m3.2 5 1.1 1.1L6.3 4M3.2 9.6l1.1 1.1L6.3 8.5M3.2 14.1l1.1 1.1 2-2.2"/>',
    chart: '<path d="M4 4v12h12"/><path d="M7.5 13.5v-3M10.5 13.5V8M13.5 13.5V6"/>',
    lightbulb: '<path d="M7 12.5a4.5 4.5 0 1 1 6 0c-.6.5-1 1.2-1 2h-4c0-.8-.4-1.5-1-2z"/><path d="M8.5 17.5h3"/>',
    book: '<path d="M4 4.5C4 3.7 4.7 3 5.5 3H16v12.5H5.5c-.8 0-1.5.7-1.5 1.5z"/><path d="M4 17c0-.8.7-1.5 1.5-1.5H16V17H5.5C4.7 17 4 16.3 4 15.5z"/>',
    chat: '<path d="M4 5.5C4 4.7 4.7 4 5.5 4h9C15.3 4 16 4.7 16 5.5v6c0 .8-.7 1.5-1.5 1.5H8l-3.5 3z"/>',
    calendar: '<rect x="3.5" y="4.5" width="13" height="12" rx="1.6"/><path d="M3.5 8h13M7 3v3M13 3v3"/>',
    tag: '<path d="M4 4h5.5l6.5 6.5-5.5 5.5L4 9.5z"/><circle cx="7.5" cy="7.5" r="1.1"/>',
    upload: '<path d="M10 13V4.5M6.5 8 10 4.5 13.5 8"/><path d="M4.5 13v2.5c0 .6.4 1 1 1h9c.6 0 1-.4 1-1V13"/>',
    edit: '<path d="M13.5 4.5 15.5 6.5 7 15l-3 .8.8-3z"/>',
    check: '<path d="m4.5 10.5 3.5 3.5 7.5-8"/>',
    sparkles: '<path d="M10 3.5 11.4 8 16 9.4 11.4 10.8 10 15.5 8.6 10.8 4 9.4 8.6 8z"/><path d="M15 4v3M16.5 5.5h-3"/>',
    "map": '<path d="M7.5 4 3.5 5.6v10.4L7.5 14.5l5 1.5 4-1.6V4l-4 1.6z"/><path d="M7.5 4v10.5M12.5 5.5V16"/>',
    arrow: '<path d="M4 10h11M11 6l4 4-4 4"/>',
    plus: '<path d="M10 4.5v11M4.5 10h11"/>',
    doc: '<path d="M6 3.5h5l3 3v10H6z"/><path d="M11 3.5v3h3M8 10h4M8 13h4"/>',
    gauge: '<path d="M4 14a6 6 0 1 1 12 0"/><path d="m10 14 3-4"/><circle cx="10" cy="14" r=".7" fill="currentColor"/>',
    home: '<path d="m3.5 9.5 6.5-5.5 6.5 5.5"/><path d="M5 8.5v7.5h10V8.5"/>',
    trash: '<path d="M4.5 6h11M8 6V4.3c0-.5.4-.8.8-.8h2.4c.4 0 .8.3.8.8V6M6 6l.6 9.4c0 .6.5 1 1 1h4.8c.5 0 1-.4 1-1L14 6"/><path d="M8.3 9v4.5M11.7 9v4.5"/>',
    close: '<path d="m5 5 10 10M15 5 5 15"/>',
  };
  function icon(name, cls) {
    const body = P[name] || P.grid;
    return `<svg class="nv-i ${cls || ""}" viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"
      fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  }
  function greeting() {
    const h = new Date().getHours();
    if (h < 5) return "Доброї ночі";
    if (h < 12) return "Доброго ранку";
    if (h < 18) return "Добрий день";
    return "Добрий вечір";
  }

  /* ---- flat illustration system (own art, on-brand palette) -------------
   * Never a photo of a real or stock person -- nothing here can be mistaken
   * for a real MOЖУ participant or staff member. Simple geometric figures,
   * consistent yellow / ink / cream palette, reused across hero + future
   * pages + catalog cards. */
  // Clean avatar silhouette: circular head + rounded shoulder arc, single
  // tone. Deliberately abstract (no face/skin detail) -- reads as "a
  // person" without implying any specific individual's likeness.
  const person = (cx, cy, s, tone) => {
    const headR = s * 0.24, headCy = cy - s * 0.34;
    return `
    <path d="M${cx - s * 0.5} ${cy + s * 0.5} a${s * 0.5} ${s * 0.42} 0 0 1 ${s} 0 Z" fill="${tone}"/>
    <circle cx="${cx}" cy="${headCy}" r="${headR}" fill="${tone}"/>`;
  };
  const ILL = {
    person: `<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="400" height="300" fill="#fdf3d8"/>
      <circle cx="205" cy="155" r="112" fill="#ffe38c"/>
      <circle cx="335" cy="55" r="20" fill="#fff" opacity=".55"/>
      <circle cx="52" cy="230" r="14" fill="#18140f" opacity=".08"/>
      <rect x="90" y="262" width="230" height="13" rx="6.5" fill="#18140f" opacity=".08"/>
      <circle cx="205" cy="155" r="70" fill="none" stroke="#ffc72c" stroke-width="3" opacity=".5"/>
      ${person(205, 190, 150, "#18140f")}
      <path d="M172 108c6-20 22-32 38-32" stroke="#ffc72c" stroke-width="5" fill="none" stroke-linecap="round"/>
    </svg>`,
    consult: `<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="400" height="300" fill="#fdf3d8"/>
      <ellipse cx="200" cy="262" rx="165" ry="16" fill="#18140f" opacity=".06"/>
      <rect x="55" y="55" width="290" height="170" rx="20" fill="#fff" opacity=".65"/>
      <circle cx="135" cy="150" r="72" fill="#ffe9ac"/>
      <circle cx="275" cy="155" r="76" fill="#fff3c9"/>
      ${person(135, 195, 128, "#18140f")}
      ${person(275, 200, 132, "#4c4638")}
      <path d="M170 140c18-16 46-16 66 2" stroke="#18140f" stroke-width="4" fill="none" stroke-linecap="round" opacity=".22"/>
    </svg>`,
    map: `<svg viewBox="0 0 400 220" xmlns="http://www.w3.org/2000/svg">
      <rect width="400" height="220" fill="#fdf3d8"/>
      <path d="M90 40 L230 30 L300 60 L320 110 L280 170 L190 190 L110 160 L70 100 Z" fill="#fff" stroke="#ece4d0" stroke-width="2"/>
      <path d="M150 70 L260 70 M140 100 L270 110 M160 140 L250 150" stroke="#ece4d0" stroke-width="2"/>
      <circle cx="215" cy="95" r="13" fill="#18140f"/>
      <path d="M215 108 L215 60 Q215 45 230 45 Q245 45 245 60 Q245 75 215 108Z" fill="#ffc72c" stroke="#18140f" stroke-width="2"/>
    </svg>`,
    chart: `<svg viewBox="0 0 400 240" xmlns="http://www.w3.org/2000/svg">
      <rect width="400" height="240" fill="#fdf3d8"/>
      <ellipse cx="200" cy="218" rx="165" ry="13" fill="#18140f" opacity=".06"/>
      <circle cx="118" cy="150" r="66" fill="#ffe9ac"/>
      ${person(118, 178, 108, "#18140f")}
      <rect x="60" y="150" width="110" height="70" rx="10" fill="#fff"/>
      <rect x="75" y="185" width="14" height="25" fill="#ffc72c"/>
      <rect x="98" y="170" width="14" height="40" fill="#18140f" opacity=".7"/>
      <rect x="121" y="195" width="14" height="15" fill="#ffc72c"/>
      <circle cx="295" cy="155" r="70" fill="#fff3c9"/>
      ${person(295, 185, 100, "#4c4638")}
      <rect x="255" y="120" width="80" height="55" rx="8" fill="#fff"/>
      <path d="M265 155 L280 140 L295 150 L320 128" stroke="#18140f" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity=".55"/>
    </svg>`,
  };
  function illustration(name) { return ILL[name] || ILL.person; }

  const DOODLE = {
    arrow: `<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 10c8 2 20 8 26 22M22 28l10 4 2-11"/></svg>`,
    heart: `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 17s-6.5-4.1-8.4-8C.4 6 2 3 5.2 3c1.9 0 3.3 1 4.8 3 1.5-2 2.9-3 4.8-3 3.2 0 4.8 3 3.6 6-1.9 3.9-8.4 8-8.4 8z"/></svg>`,
  };
  function doodleIcon(name) { return DOODLE[name] || ""; }

  function logoMark() {
    return `<svg class="nv-logo-mark" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#ffc72c"/>
      <path d="M11 9l5 7 5-7M16 16v7" stroke="#18140f" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </svg>`;
  }

  return { icon, greeting, illustration, doodleIcon, logoMark };
})();
