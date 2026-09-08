# ICAN frontend

Актуальний UI: React + Vite + TypeScript + Redux Toolkit у `src/`.

- `npm run dev` — розробка на порту 5173, API proxy на backend:8099.
- `npm run build` — перевірка TypeScript і збірка в `dist/`.
- Бекенд запускається окремо через `../backend/run.py`.
- У терміналі цієї папки виконайте `npm run dev` і відкрийте адресу Vite.
- Якщо залежності ще не встановлені, один раз виконайте `npm install`.
- `Ctrl+C` тут зупиняє лише frontend; backend має власний термінал.

`legacy/admin/` і `legacy/mnp/` — збережені попередні інтерфейси.
Нові UI-функції розробляються в `src/`, не дублюються в legacy.
`dist/` та `node_modules/` генеруються автоматично і не комітяться.
