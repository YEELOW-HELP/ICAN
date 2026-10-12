import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import ukraineMap from "@svg-maps/ukraine";
import { ConsoleGate, ConsoleLogin, ConsoleLayout, ConsolePersons, ConsoleCreate, ConsolePerson, ConsoleTeam } from "./Console";
import { adminRequest, personRequest, publicRequest, sessionStorageKeys } from "./api/client";
import { UserAnalysis, UserDashboard, UserProfileEditor, UserVacancies } from "./UserWorkspace";
import type { CareerListItem, Person, PersonCore, PersonListItem } from "./types";

const publicNav = [
  ["/", "Головна"], ["/how", "Як це працює"], ["/about", "Про МОЖУ"],
] as const;

const icons: Record<string, ReactNode> = {
  route: <><circle cx="5.5" cy="15" r="2"/><circle cx="14.5" cy="5" r="2"/><path d="M7.4 14.2c4-1 5-3 5-6M12.5 7h-3M12.5 7v2.5"/></>,
  briefcase: <><rect x="3" y="6.5" width="14" height="10" rx="1.6"/><path d="M7.5 6.5V5.2c0-.8.6-1.4 1.4-1.4h2.2c.8 0 1.4.6 1.4 1.4v1.3M3 10.5h14"/></>,
  target: <><circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="3.4"/><circle cx="10" cy="10" r=".6" fill="currentColor"/></>,
  compass: <><circle cx="10" cy="10" r="7.2"/><path d="M13.2 6.8 11.4 11l-4.2 1.8L9 8.6z"/></>,
  doc: <><path d="M6 3.5h5l3 3v10H6zM11 3.5v3h3M8 10h4M8 13h4"/></>,
  chart: <><path d="M4 4v12h12M7.5 13.5v-3M10.5 13.5V8M13.5 13.5V6"/></>,
  lightbulb: <><path d="M7 12.5a4.5 4.5 0 1 1 6 0c-.6.5-1 1.2-1 2h-4c0-.8-.4-1.5-1-2zM8.5 17.5h3"/></>,
  edit: <path d="M13.5 4.5 15.5 6.5 7 15l-3 .8.8-3z"/>,
  checklist: <><path d="M8 5.5h9M8 10h9M8 14.5h9M3.2 5l1.1 1.1L6.3 4M3.2 9.6l1.1 1.1L6.3 8.5M3.2 14.1l1.1 1.1 2-2.2"/></>,
  arrow: <path d="M4 10h11M11 6l4 4-4 4"/>,
  check: <path d="m4.5 10.5 3.5 3.5 7.5-8"/>,
  sparkles: <><path d="M10 3.5 11.4 8 16 9.4 11.4 10.8 10 15.5 8.6 10.8 4 9.4 8.6 8z"/><path d="M15 4v3M16.5 5.5h-3"/></>,
};
function Icon({name}:{name:string}){return <svg className="nv-i" viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{icons[name]||icons.doc}</svg>}
function LogoMark(){return <svg className="nv-logo-mark" viewBox="0 0 32 32" width="32" height="32" aria-hidden><rect width="32" height="32" rx="9" fill="#ffc72c"/><path d="M11 9l5 7 5-7M16 16v7" stroke="#18140f" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none"/></svg>}
function Brand() {
  return <Link className="brand" to="/"><LogoMark/><span className="brand-copy"><strong>Yellow Hub</strong><small>Кар'єрний центр</small></span></Link>;
}

function PublicLayout() {
  const [mobileMenuOpen,setMobileMenuOpen]=useState(false);
  const hasStaffSession=Boolean(localStorage.getItem(sessionStorageKeys.admin));
  const hasUserSession=Boolean(localStorage.getItem(sessionStorageKeys.session)&&localStorage.getItem(sessionStorageKeys.account));
  const accountTarget=hasStaffSession?"/admin/persons":hasUserSession?"/app":"/login";
  return <div className="site">
    <header className="topbar"><Brand/><nav className={mobileMenuOpen?"mobile-open":""}>{publicNav.map(([to, label]) => <NavLink onClick={()=>setMobileMenuOpen(false)} end={to==="/"} key={to} to={to}>{label}</NavLink>)}<NavLink onClick={()=>setMobileMenuOpen(false)} to="/market">Ринок праці</NavLink><Link onClick={()=>setMobileMenuOpen(false)} className="mobile-account-link" to={accountTarget}>{hasStaffSession?"Відкрити консоль":hasUserSession?"Відкрити кабінет":"Увійти в кабінет"}</Link></nav>
      <div className="top-actions"><Link className="button ghost" to={accountTarget}>{hasStaffSession?"Консоль":hasUserSession?"Мій кабінет":"Увійти"}</Link><Link className="button small" to="/profile"><span className="desktop-label">Створити профіль</span><span className="mobile-label">Створити</span></Link></div>
      <button type="button" className={`mobile-menu-toggle ${mobileMenuOpen?"open":""}`} aria-label={mobileMenuOpen?"Закрити меню":"Відкрити меню"} aria-expanded={mobileMenuOpen} onClick={()=>setMobileMenuOpen(!mobileMenuOpen)}><span/><span/><span/></button>
    </header>
    <main className="page"><Outlet/></main>
    <footer><Brand/><nav><Link to="/about">Про МОЖУ</Link><Link to="/how">Як це працює</Link><Link to="/market">Ринок праці</Link></nav><span>© 2026 Yellow Hub</span></footer>
  </div>;
}

function useMobileLanding(){
  const query="(max-width: 700px)";
  const [mobile,setMobile]=useState(()=>typeof window!=="undefined"&&"matchMedia" in window?window.matchMedia(query).matches:false);
  useEffect(()=>{if(typeof window==="undefined"||!("matchMedia" in window))return;const media=window.matchMedia(query);const update=()=>setMobile(media.matches);update();media.addEventListener("change",update);return()=>media.removeEventListener("change",update)},[]);
  return mobile;
}

function MobileHome(){
  const audiences=[["route","Змінюю професію"],["briefcase","Шукаю роботу"],["target","Повертаюсь на ринок"],["compass","Не знаю, куди далі"]];
  return <div className="mobile-home">
    <section className="mobile-home-hero">
      <div className="mobile-home-kicker"><i/><span>Кар'єрний навігатор</span><b>Безкоштовно</b></div>
      <h1>Знайдіть свій наступний <em>професійний крок</em></h1>
      <p>Заповніть профіль один раз — отримайте аналіз сильних сторін, реальні напрями та вакансії у вашому регіоні.</p>
      <div className="mobile-home-actions"><Link className="button" to="/profile">Почати безкоштовно <Icon name="arrow"/></Link><Link to="/how">Подивитись, як це працює</Link></div>
      <div className="mobile-home-proof"><div><strong>10–15</strong><span>хвилин</span></div><div><strong>3</strong><span>кроки до результату</span></div><div><strong>0 ₴</strong><span>вартість</span></div></div>
      <div className="mobile-home-preview"><div className="mobile-home-preview-bar"><span><LogoMark/>Мій кар'єрний профіль</span><i>82%</i></div><div className="mobile-home-preview-person"><span>ЛБ</span><div><b>Ваші сильні сторони</b><small>Досвід, навички та цілі — в одному місці</small></div></div><div className="mobile-home-preview-tags"><span>Комунікація</span><span>Аналітика</span><span>Організація</span></div><div className="mobile-home-preview-result"><Icon name="sparkles"/><div><small>Ваш результат</small><b>3 реалістичні напрями</b></div><Icon name="arrow"/></div></div>
      <div className="mobile-home-trust"><span><Icon name="check"/>Без реєстрації на старті</span><span><Icon name="check"/>Офіційні дані ринку</span></div>
    </section>

    <Region embedded/>

    <section className="mobile-home-results">
      <div className="mobile-section-heading"><span>Що ви отримаєте</span><h2>Не просто тест.<br/>Ваш план дій.</h2><p>Від повної картини про себе до конкретного наступного кроку.</p></div>
      <div className="mobile-result-bento">
        <article className="mobile-result-main"><span><Icon name="doc"/></span><div><small>Ваш профіль</small><h3>Усе важливе про вас — структуровано</h3><p>Досвід, навички, цілі й умови роботи в одному місці.</p></div><b>01</b></article>
        <article><span><Icon name="chart"/></span><small>Напрями</small><h3>Професії, які вам підходять</h3><b>02</b></article>
        <article className="accent"><span><Icon name="lightbulb"/></span><small>Пояснення</small><h3>Чому саме цей вибір</h3><b>03</b></article>
        <article className="mobile-result-wide"><span><Icon name="target"/></span><div><small>Наступний крок</small><h3>Що робити вже зараз</h3></div><Icon name="arrow"/></article>
      </div>
    </section>

    <section className="mobile-home-audience">
      <div className="mobile-section-heading light"><span>Для кого</span><h2>Коли потрібна ясність</h2><p>Оберіть ситуацію, яка найближча до вашої.</p></div>
      <div className="mobile-audience-grid">{audiences.map(([icon,title],index)=><Link to="/profile" key={title}><span><Icon name={icon}/></span><b>{title}</b><i>{String(index+1).padStart(2,"0")}</i></Link>)}</div>
    </section>

    <section className="mobile-home-process">
      <div className="mobile-section-heading"><span>Як це працює</span><h2>Три кроки — і є з чого почати</h2></div>
      <div className="mobile-process-track"><article><i>1</i><div><b>Заповніть профіль</b><p>Розкажіть про досвід, навички та цілі.</p></div></article><article><i>2</i><div><b>Отримайте аналіз</b><p>Побачите сильні сторони й реальні напрями.</p></div></article><article><i>3</i><div><b>Перейдіть до дій</b><p>Оберіть фокус і почніть пошук вакансій.</p></div></article></div>
      <Link className="mobile-process-link" to="/how">Детально про процес <Icon name="arrow"/></Link>
    </section>

    <section className="mobile-home-faq">
      <div className="mobile-section-heading"><span>Коротко про важливе</span><h2>Перед початком</h2></div>
      <div className="mobile-faq-list"><details><summary>Це справді безкоштовно?<i>+</i></summary><p>Так. Створення профілю, базовий аналіз і перегляд напрямів не потребують оплати.</p></details><details><summary>Потрібно вже мати резюме?<i>+</i></summary><p>Ні. Дані можна заповнити поступово, навіть якщо готового резюме ще немає.</p></details><details><summary>Що буде з моїми даними?<i>+</i></summary><p>Профіль зберігається у вашому кабінеті та використовується для персональних рекомендацій.</p></details></div>
    </section>

    <section className="mobile-home-final"><span><Icon name="sparkles"/></span><small>Ваш наступний крок</small><h2>Почніть із профілю.<br/>Решту підкажемо.</h2><p>Ваші дані зберігаються, і ви зможете повернутися до них у будь-який момент.</p><Link className="button" to="/profile">Почати безкоштовно <Icon name="arrow"/></Link></section>
  </div>;
}

function Home() {
  const mobile=useMobileLanding();
  if(mobile)return <MobileHome/>;
  return <>
    <section className="hero-split home-hero">
      <div className="hero-copy"><span className="eyebrow">Кар'єрний навігатор</span><h1>Знайдіть напрям, у якому <em>хочеться рухатись</em></h1>
        <p className="lead">Створіть кар'єрний профіль і побачите реалістичні професійні напрями, що вам підходять зараз.</p>
        <div className="hero-actions"><Link className="button large" to="/profile">Створити кар'єрний профіль →</Link><Link className="button secondary large" to="/how">Як це працює</Link></div>
        <div className="check-row">{["Безкоштовно","10–15 хвилин","Профіль зберігається"].map(x=><span key={x}><i><Icon name="check"/></i>{x}</span>)}</div>
      </div>
      <div className="illus-wrap hero-visual"><div className="illus-frame"><PersonIllustration/></div><div className="visual-caption"><span><Icon name="sparkles"/></span><div><small>Ваш результат</small><strong>Зрозумілий кар'єрний план</strong></div></div>
      </div>
    </section>
    <Region embedded/>
    <section className="home-section audience"><div className="section-intro"><span>Для кого це</span><h2>Коли потрібен зрозумілий наступний крок</h2></div><div className="tile-nav-grid">{[["route","Хочу змінити професію"],["briefcase","Втратив(-ла) роботу"],["target","Повертаюсь на ринок праці"],["compass","Шукаю свій напрям"]].map(([i,t])=><Link className="tile-nav" to="/profile" key={t}><span className="tn-ico"><Icon name={i}/></span><b>{t}</b></Link>)}</div></section>
    <section className="home-section benefits"><div className="section-intro"><span>Результат</span><h2>Усе необхідне для впевненого рішення</h2><p>Не просто список професій, а зрозумілий профіль і послідовний план дій.</p></div><div className="tile-feat-grid">{[["doc","Кар'єрний профіль","Ваші сильні сторони та інтереси"],["chart","Реалістичні напрями","Професії, що вам підходять зараз"],["lightbulb","Зрозумілі пояснення","Чому саме ці професії і що це означає"],["target","Наступні кроки","З чого почати і як розвиватися"]].map(([i,t,d])=><article className="tile-feat" key={t}><span className="tn-ico"><Icon name={i}/></span><div><h3>{t}</h3><p>{d}</p></div></article>)}</div></section>
    <section className="home-section process"><div className="section-intro"><span>Простий процес</span><h2>Від профілю до наступного кроку</h2></div><FlowSteps/></section>
    <CtaBand title="Почніть із першого кроку" text="Створіть кар'єрний профіль і відкрийте нові можливості для себе."/>
  </>;
}

function PersonIllustration(){return <svg viewBox="0 0 520 390" role="img" aria-label="Приклад кар'єрного профілю">
  <defs><linearGradient id="profileBg" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fff8df"/><stop offset="1" stopColor="#f6e9b9"/></linearGradient><filter id="cardShadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="10" stdDeviation="12" floodColor="#594b1f" floodOpacity=".12"/></filter></defs>
  <rect width="520" height="390" rx="30" fill="url(#profileBg)"/>
  <circle cx="454" cy="55" r="76" fill="#ffc72c" opacity=".26"/><circle cx="36" cy="342" r="92" fill="#fff" opacity=".55"/>
  <g filter="url(#cardShadow)"><rect x="58" y="42" width="404" height="306" rx="24" fill="#fff"/></g>
  <rect x="58" y="42" width="404" height="62" rx="24" fill="#18140f"/><rect x="58" y="82" width="404" height="22" fill="#18140f"/>
  <circle cx="92" cy="73" r="13" fill="#ffc72c"/><path d="M87 68l5 6 5-6M92 74v6" stroke="#18140f" strokeWidth="2" strokeLinecap="round" fill="none"/>
  <text x="116" y="78" fill="#fff" fontSize="15" fontFamily="Manrope, sans-serif" fontWeight="700">Мій кар'єрний профіль</text><circle cx="428" cy="73" r="5" fill="#ffc72c"/>
  <circle cx="113" cy="148" r="25" fill="#ffe58f"/><circle cx="113" cy="141" r="8" fill="#18140f"/><path d="M97 169c2-13 9-20 16-20s14 7 16 20" fill="#18140f"/>
  <rect x="152" y="128" width="116" height="11" rx="5.5" fill="#18140f"/><rect x="152" y="148" width="78" height="8" rx="4" fill="#ddd8ca"/><rect x="152" y="166" width="98" height="8" rx="4" fill="#eeeae0"/>
  <rect x="314" y="124" width="112" height="47" rx="14" fill="#fff5cd"/><text x="329" y="144" fill="#7f6814" fontSize="9" fontFamily="Manrope, sans-serif" fontWeight="700">ПРОФІЛЬ ГОТОВИЙ</text><text x="329" y="160" fill="#18140f" fontSize="15" fontFamily="Manrope, sans-serif" fontWeight="800">82%</text>
  <text x="88" y="213" fill="#8b826d" fontSize="9" fontFamily="Manrope, sans-serif" fontWeight="700">ВАШІ СИЛЬНІ СТОРОНИ</text>
  <rect x="88" y="226" width="106" height="30" rx="15" fill="#fff2bd"/><text x="108" y="245" fill="#18140f" fontSize="10" fontFamily="Manrope, sans-serif" fontWeight="700">Комунікація</text><rect x="202" y="226" width="104" height="30" rx="15" fill="#f3f1eb"/><text x="224" y="245" fill="#18140f" fontSize="10" fontFamily="Manrope, sans-serif" fontWeight="700">Аналітика</text><rect x="314" y="226" width="104" height="30" rx="15" fill="#f3f1eb"/><text x="333" y="245" fill="#18140f" fontSize="10" fontFamily="Manrope, sans-serif" fontWeight="700">Креативність</text>
  <rect x="88" y="279" width="330" height="43" rx="13" fill="#f8f7f3"/><circle cx="111" cy="300" r="11" fill="#ffc72c"/><path d="m106 300 3 3 6-7" stroke="#18140f" strokeWidth="2" fill="none"/><text x="132" y="297" fill="#18140f" fontSize="10" fontFamily="Manrope, sans-serif" fontWeight="700">3 професійні напрями вже підібрано</text><text x="132" y="311" fill="#8b826d" fontSize="8" fontFamily="Manrope, sans-serif">На основі вашого досвіду та інтересів</text>
</svg>}
function FlowSteps(){return <div className="step-flow">{[["edit","Створіть профіль","Дайте відповіді на прості запитання"],["checklist","Отримайте напрями","Сервіс підбере професії, що вам підходять"],["target","Оберіть свій фокус","Дослідіть професії та можливості"],["chart","Рухайтесь далі","Отримайте наступні кроки для вашої мети"]].map(([i,t,d],n)=><div className="flow-group" key={t}><article className="sf-item"><div className="sf-row"><span className="sf-n">{n+1}</span><span className="sf-ico"><Icon name={i}/></span></div><h3>{t}</h3><p>{d}</p></article>{n<3&&<span className="sf-arrow"><Icon name="arrow"/></span>}</div>)}</div>}
function CtaBand({title,text}:{title:string;text:string}){return <div className="cta-band"><span className="cb-ico"><Icon name="sparkles"/></span><div><h2>{title}</h2><p>{text}</p></div><Link className="button large" to="/profile">Створити кар'єрний профіль →</Link><span className="cb-doodle">Ти можеш! ♥</span></div>}

function StaticPage({ title, intro, children }: { title: string; intro: string; children?: ReactNode }) {
  return <section className="narrow"><span className="eyebrow">YELLOW HUB · МОЖУ</span><h1>{title}</h1><p className="lead">{intro}</p>{children}</section>;
}

function How() { return <><section className="hero-split compact-hero"><div><span className="eyebrow">Ваш наступний крок — можливий</span><h1>Як це працює</h1><p className="lead">Ми зробили процес простим і зрозумілим, щоб ви могли отримати персональні рекомендації та обрати реалістичний наступний крок.</p></div><div className="illus-frame"><PersonIllustration/></div></section><FlowSteps/><CtaBand title="Готові зробити перший крок?" text="Створіть кар'єрний профіль і відкрийте нові можливості для себе."/></>; }
function About() { return <><StaticPage title="Про МОЖУ" intro="Соціальна програма в межах Yellow Hub, яка допомагає людям у складних життєвих ситуаціях знайти свій професійний шлях і повернутися до активного життя."/><div className="tile-feat-grid about-grid">{[["briefcase","Для тих, хто потребує підтримки"],["checklist","Безкоштовний доступ"],["edit","Експертна підтримка"],["lightbulb","Реальні можливості"]].map(([i,t])=><article className="tile-feat" key={t}><span className="tn-ico"><Icon name={i}/></span><h3>{t}</h3><p>Людська підтримка та зрозумілий наступний крок.</p></article>)}</div><CtaBand title="МОЖУ" text="Люди. Підтримка. Нові можливості."/></>; }
function Opportunities() { return <StaticPage title="Можливості" intro="Кар'єрні сценарії, вакансії та навчальні ресурси відкриватимуться поступово."><EmptyState title="Розділ готується" text="Ми не показуємо вигаданих вакансій або ринкових даних."/></StaticPage>; }
type MarketItem = {career_id:string;career_code:string;name:string;family?:string|null;vacancy_count:number;trend?:"up"|"flat"|"down"|null;salary_median?:number|null;salary_p25?:number|null;salary_p75?:number|null};
type RegionSummary = {region:string;vacancy_count:number;salary_average?:number|null};
type MarketOverview = {available:boolean;message?:string;snapshot_date?:string;selected_region?:string|null;total_vacancies?:number;source:string;source_url:string;methodology_note?:string;regions:string[];region_summaries?:RegionSummary[];items:MarketItem[]};
const MARKET_CACHE_TTL=5*60*1000;
const marketOverviewCache=new Map<string,{data:MarketOverview;expiresAt:number}>();
const marketOverviewRequests=new Map<string,Promise<MarketOverview>>();
const marketCacheKey=(region="")=>region.trim().toLocaleLowerCase("uk-UA");
function cachedMarketOverview(region=""){
  const key=marketCacheKey(region),cached=marketOverviewCache.get(key);
  if(!cached||cached.expiresAt<=Date.now()){marketOverviewCache.delete(key);return null}
  return cached.data;
}
function loadMarketOverview(region="",force=false){
  const key=marketCacheKey(region);
  if(force){marketOverviewCache.delete(key);marketOverviewRequests.delete(key)}
  const cached=cachedMarketOverview(region);if(cached)return Promise.resolve(cached);
  const pending=marketOverviewRequests.get(key);if(pending)return pending;
  const request=publicRequest<MarketOverview>(`/market/overview${region?`?region=${encodeURIComponent(region)}`:""}`).then(data=>{marketOverviewCache.set(key,{data,expiresAt:Date.now()+MARKET_CACHE_TTL});return data}).finally(()=>marketOverviewRequests.delete(key));
  marketOverviewRequests.set(key,request);return request;
}
function clearMarketOverviewCache(){marketOverviewCache.clear();marketOverviewRequests.clear()}
function Market(){
  const [data,setData]=useState<MarketOverview|null>(()=>cachedMarketOverview());const [region,setRegion]=useState("");const [sortBy,setSortBy]=useState("vacancies-desc");const [error,setError]=useState("");const [loading,setLoading]=useState(()=>!cachedMarketOverview());const [refreshing,setRefreshing]=useState(false);
  const load=async(selected=region,force=false)=>{const cached=!force&&cachedMarketOverview(selected);if(cached){setData(cached);setLoading(false);setError("");return}setLoading(true);setData(null);setError("");try{setData(await loadMarketOverview(selected,force))}catch(e){setError(e instanceof Error?e.message:"Не вдалося завантажити дані")}finally{setLoading(false)}};
  useEffect(()=>{void load(region)},[region]);
  const refresh=async()=>{setRefreshing(true);setError("");try{await adminRequest("/admin/market/refresh",{method:"POST"});clearMarketOverviewCache();await load(region,true)}catch(e){setError(e instanceof Error?e.message:"Не вдалося оновити дані")}finally{setRefreshing(false)}};
  const money=(value?:number|null)=>value?`${new Intl.NumberFormat("uk-UA",{maximumFractionDigits:0}).format(value)} ₴`:"Немає даних";
  const sortedItems=useMemo(()=>[...(data?.items??[])].sort((a,b)=>{
    if(sortBy==="vacancies-asc")return a.vacancy_count-b.vacancy_count;
    if(sortBy==="salary-desc")return (b.salary_median??-1)-(a.salary_median??-1);
    if(sortBy==="salary-asc")return (a.salary_median??Number.MAX_SAFE_INTEGER)-(b.salary_median??Number.MAX_SAFE_INTEGER);
    return b.vacancy_count-a.vacancy_count;
  }),[data?.items,sortBy]);
  const maxCount=Math.max(1,...(data?.items.map(item=>item.vacancy_count)??[]));
  const canRefresh=Boolean(localStorage.getItem(sessionStorageKeys.admin));
  return <section className="market-page">
    <div className="market-heading"><div><span className="eyebrow">Офіційні відкриті дані</span><h1>Ринок праці в Україні</h1><p className="lead">Дивіться, які професії зараз найбільш затребувані в Україні та окремих регіонах.</p></div><div className="market-orbit"><span><Icon name="chart"/></span><b>Дані без припущень</b><small>На основі актуальних вакансій Державної служби зайнятості</small></div></div>
    <div className="market-toolbar"><label><span>Регіон</span><select value={region} onChange={e=>setRegion(e.target.value)}><option value="">Уся Україна</option>{data?.regions.map(item=><option key={item} value={item}>{item}</option>)}</select></label><div className="market-source"><span>{data?.snapshot_date?`Оновлено ${new Date(`${data.snapshot_date}T12:00:00`).toLocaleDateString("uk-UA")}`:"Очікуємо перше оновлення"}</span><a href={data?.source_url||"https://data.gov.ua/dataset/a95174b2-ff4b-43f8-bee2-a89d3a258215"} target="_blank" rel="noreferrer">Джерело даних ↗</a><a className="button secondary small market-export" href="/v1/mnp/market/export.xlsx" download><Icon name="doc"/>Завантажити всі дані</a>{canRefresh&&<button className="button secondary small" onClick={()=>void refresh()} disabled={refreshing}>{refreshing?"Оновлюємо…":"Оновити зараз"}</button>}</div></div>
    {error&&<ErrorBox message={error}/>} {loading&&!data?<Loading/>:data?.available?<>
      <div className="market-stats"><article className="primary"><span className="stat-icon"><Icon name="briefcase"/></span><div><span>Вакансій у зрізі</span><strong>{new Intl.NumberFormat("uk-UA").format(data.total_vacancies||0)}</strong><small>{region||"Уся Україна"}</small></div></article><article><span className="stat-icon"><Icon name="chart"/></span><div><span>Професій у рейтингу</span><strong>{data.items.length}</strong><small>Найвищий попит зараз</small></div></article><article><span className="stat-icon"><Icon name="checklist"/></span><div><span>Дата зрізу</span><strong>{data.snapshot_date?new Date(`${data.snapshot_date}T12:00:00`).toLocaleDateString("uk-UA",{day:"2-digit",month:"short"}):"—"}</strong><small>Перевірені відкриті дані</small></div></article></div>
      <div className="market-results"><div className="market-results-head"><div><span>Огляд попиту</span><h2>Популярні професії</h2></div><div className="market-results-tools"><p>{data.methodology_note}</p><label><span>Сортувати</span><select value={sortBy} onChange={e=>setSortBy(e.target.value)}><option value="vacancies-desc">Вакансії: найбільше</option><option value="vacancies-asc">Вакансії: найменше</option><option value="salary-desc">Зарплата: найвища</option><option value="salary-asc">Зарплата: найнижча</option></select></label></div></div><div className="demand-columns"><span>№</span><span>Професія</span><span>Вакансії</span><span>Медіана зарплати</span><span>Дія</span></div><div className="demand-list">{sortedItems.map((item,index)=><Link className="demand-row" to={`/profile?career=${encodeURIComponent(item.career_id)}`} key={item.career_id}><span className="demand-rank">{index+1}</span><div className="demand-main"><div><strong>{item.name}</strong>{item.family&&<small>{item.family}</small>}</div><div className="demand-bar"><i style={{width:`${Math.max(6,item.vacancy_count/maxCount*100)}%`}}/></div></div><div className="demand-count"><strong>{new Intl.NumberFormat("uk-UA").format(item.vacancy_count)}</strong><small>позицій</small></div><div className="demand-salary"><strong>{money(item.salary_median)}</strong><small>на місяць</small></div><span className="demand-register">Обрати <b>→</b></span></Link>)}</div></div>
    </>:<div className="market-empty"><span className="tn-ico"><Icon name="chart"/></span><h2>Завантажуємо перший зріз ринку</h2><p>{data?.message||"Дані ще не синхронізовано."} Після першого імпорту тут з’являться професії, зарплати та регіональна статистика.</p><button className="button secondary" onClick={()=>void load(region)}>Перевірити ще раз</button></div>}
    <p className="market-attribution">Джерело: <a href={data?.source_url||"https://data.gov.ua/dataset/a95174b2-ff4b-43f8-bee2-a89d3a258215"} target="_blank" rel="noreferrer">Державна служба зайнятості України / Data.gov.ua</a>. Дані використовуються за ліцензією CC BY 4.0.</p>
  </section>
}
const REGION_BY_MAP_ID:Record<string,string>={
  "cherkasy":"Черкаська область","chernihiv":"Чернігівська область","chernivtsi":"Чернівецька область","crimea":"Автономна Республіка Крим","dnipropetrovsk":"Дніпропетровська область","donetsk":"Донецька область","ivano-frankivsk":"Івано-Франківська область","kharkiv":"Харківська область","kherson":"Херсонська область","khmelnytskyi":"Хмельницька область","kirovohrad":"Кіровоградська область","kyiv":"Київська область","kyiv-city":"м. Київ","luhansk":"Луганська область","lviv":"Львівська область","mykolaiv":"Миколаївська область","odessa":"Одеська область","poltava":"Полтавська область","rivne":"Рівненська область","sumy":"Сумська область","ternopil":"Тернопільська область","vinnytsia":"Вінницька область","volyn":"Волинська область","zakarpattia":"Закарпатська область","zaporizhia":"Запорізька область","zhytomyr":"Житомирська область"
};
function Region({embedded=false}:{embedded?:boolean}){
  const [overview,setOverview]=useState<MarketOverview|null>(()=>cachedMarketOverview());const [details,setDetails]=useState<MarketOverview|null>(null);const [selected,setSelected]=useState("");const [hovered,setHovered]=useState<{region:string;summary?:RegionSummary;x:number;y:number}|null>(null);const [loading,setLoading]=useState(()=>!cachedMarketOverview());const [error,setError]=useState("");
  useEffect(()=>{loadMarketOverview().then(setOverview).catch(e=>setError(e instanceof Error?e.message:"Не вдалося завантажити дані")).finally(()=>setLoading(false))},[]);
  const summaries=useMemo(()=>new Map((overview?.region_summaries??[]).map(item=>[item.region,item])),[overview?.region_summaries]);
  const rankedRegions=useMemo(()=>[...(overview?.region_summaries??[])].sort((a,b)=>b.vacancy_count-a.vacancy_count),[overview?.region_summaries]);
  const maxVacancies=Math.max(1,...rankedRegions.map(item=>item.vacancy_count));
  const selectRegion=async(region:string)=>{setSelected(region);setDetails(cachedMarketOverview(region));setError("");if(!region)return;if(!overview?.regions.includes(region)){setDetails({available:false,message:"Для цього регіону у поточному зрізі немає зіставлених вакансій.",source:overview?.source??"",source_url:overview?.source_url??"",regions:overview?.regions??[],items:[]});return}if(cachedMarketOverview(region))return;try{setDetails(await loadMarketOverview(region))}catch(e){setError(e instanceof Error?e.message:"Не вдалося завантажити регіон")}};
  const money=(value?:number|null)=>value?`${new Intl.NumberFormat("uk-UA",{maximumFractionDigits:0}).format(value)} ₴`:"—";
  if(loading)return <Loading/>;
  if(error&&!overview)return <ErrorBox message={error}/>;
  return <section className={embedded?"region-page home-region-section":"region-page"}>
    <div className="region-heading"><div><span className="eyebrow">Регіональна аналітика</span>{embedded?<h2>Подивіться, де зараз шукають фахівців</h2>:<h1>Професії у вашому регіоні</h1>}<p className="lead">Оберіть область на карті та перегляньте актуальний попит, зарплати й професії з найбільшою кількістю вакансій.</p></div><label><span>Швидкий вибір</span><select value={selected} onChange={e=>void selectRegion(e.target.value)}><option value="">Оберіть область</option>{overview?.regions.map(region=><option value={region} key={region}>{region}</option>)}</select></label></div>
    {error&&<ErrorBox message={error}/>}<div className="region-dashboard">
      <article className="ukraine-map-card"><div className="map-card-head"><div><span>Карта попиту</span><h2>Україна</h2></div><p>Чим насиченіший колір, тим більше відкритих позицій</p></div>
        <svg className="ukraine-map" viewBox={ukraineMap.viewBox} role="img" aria-label="Інтерактивна карта областей України">{ukraineMap.locations.map((location:{id:string;name:string;path:string})=>{const region=REGION_BY_MAP_ID[location.id]||location.name;const summary=summaries.get(region);const level=summary?Math.max(1,Math.ceil(summary.vacancy_count/maxVacancies*5)):0;return <path key={location.id} d={location.path} className={`${summary?`heat-${level}`:"no-data"} ${selected===region?"selected":""}`} onMouseMove={event=>{const card=event.currentTarget.closest(".ukraine-map-card")?.getBoundingClientRect();if(card)setHovered({region,summary,x:event.clientX-card.left,y:event.clientY-card.top})}} onMouseLeave={()=>setHovered(null)} onClick={()=>void selectRegion(region)} onKeyDown={event=>{if(event.key==="Enter"||event.key===" ")void selectRegion(region)}} role="button" tabIndex={0} aria-label={`${region}${summary?`: ${summary.vacancy_count} вакансій`:": даних немає"}`}/>})}</svg>
        {hovered&&<div className="map-tooltip" style={{left:hovered.x,top:hovered.y}}><strong>{hovered.region}</strong>{hovered.summary?<><span>{new Intl.NumberFormat("uk-UA").format(hovered.summary.vacancy_count)} вакансій</span><small>Середня зарплата: {money(hovered.summary.salary_average)}</small></>:<span>У поточному зрізі даних немає</span>}</div>}
        <div className="map-legend"><span>Менше</span>{[1,2,3,4,5].map(level=><i className={`heat-${level}`} key={level}/>)}<span>Більше вакансій</span></div><small className="map-hint">Натисніть на область, щоб побачити деталі</small>
      </article>
      <aside className="region-panel">{selected?<><div className="region-panel-title"><span>Обраний регіон</span><h2>{selected}</h2></div>{details?details.available?<><div className="region-kpis"><div><strong>{new Intl.NumberFormat("uk-UA").format(details.total_vacancies??0)}</strong><span>вакансій</span></div><div><strong>{details.items.length}</strong><span>професій у рейтингу</span></div></div><h3>Найбільший попит</h3><div className="region-jobs">{details.items.slice(0,6).map((item,index)=><Link to={`/profile?career=${encodeURIComponent(item.career_id)}`} key={item.career_id}><i>{index+1}</i><span><b>{item.name}</b><small>{item.vacancy_count} вакансій · {money(item.salary_median)}</small></span><Icon name="arrow"/></Link>)}</div></>:<div className="region-no-data"><span className="tn-ico"><Icon name="chart"/></span><h3>Даних поки немає</h3><p>{details.message}</p><button className="button secondary" onClick={()=>setSelected("")}>Повернутися до огляду</button></div>:<Loading/>}</>:<><div className="region-panel-title"><span>Огляд областей</span><h2>Оберіть регіон</h2><p>Наведіть для швидкої інформації або клікніть для детальної статистики.</p></div><h3>Найбільше вакансій</h3><div className="region-leaders">{rankedRegions.slice(0,5).map((item,index)=><button onClick={()=>void selectRegion(item.region)} key={item.region}><i>{index+1}</i><span><b>{item.region.replace(" область","")}</b><small>{new Intl.NumberFormat("uk-UA").format(item.vacancy_count)} вакансій</small></span></button>)}</div></>}</aside>
    </div>
    <div className="region-mobile-explorer">
      <section className="region-mobile-map-shell">
        <div className="region-mobile-intro"><span>Регіональна аналітика</span><h2>Де зараз є робота</h2><p>Торкніться області на карті — покажемо попит і зарплати.</p></div>
        <label className="region-mobile-select"><span>Швидкий вибір</span><select value={selected} onChange={e=>void selectRegion(e.target.value)}><option value="">Уся Україна</option>{overview?.regions.map(region=><option value={region} key={region}>{region}</option>)}</select></label>
        <div className="region-mobile-map-title"><strong>Україна</strong><small>Натисніть на область</small></div>
        <svg className="ukraine-map region-mobile-map" viewBox={ukraineMap.viewBox} role="img" aria-label="Інтерактивна карта областей України">{ukraineMap.locations.map((location:{id:string;name:string;path:string})=>{const region=REGION_BY_MAP_ID[location.id]||location.name;const summary=summaries.get(region);const level=summary?Math.max(1,Math.ceil(summary.vacancy_count/maxVacancies*5)):0;return <path key={location.id} d={location.path} className={`${summary?`heat-${level}`:"no-data"} ${selected===region?"selected":""}`} onClick={()=>void selectRegion(region)} onKeyDown={event=>{if(event.key==="Enter"||event.key===" ")void selectRegion(region)}} role="button" tabIndex={0} aria-label={`${region}${summary?`: ${summary.vacancy_count} вакансій`:": даних немає"}`}/>})}</svg>
        <div className="region-mobile-legend"><span>Менше</span>{[1,2,3,4,5].map(level=><i className={`heat-${level}`} key={level}/>)}<span>Більше</span></div>
      </section>
      {selected?<section className="region-mobile-detail">
        <div className="region-mobile-detail-head"><div><span>Обраний регіон</span><h3>{selected}</h3></div><button type="button" onClick={()=>void selectRegion("")} aria-label="Скинути вибір">×</button></div>
        {details?details.available?<><div className="region-mobile-kpis"><div><strong>{new Intl.NumberFormat("uk-UA").format(details.total_vacancies??0)}</strong><span>вакансій</span></div><div><strong>{details.items.length}</strong><span>професій</span></div></div><div className="region-mobile-jobs-head"><span>Найбільший попит</span><small>Обрати напрям →</small></div><div className="region-mobile-jobs">{details.items.slice(0,4).map((item,index)=><Link to={`/profile?career=${encodeURIComponent(item.career_id)}`} key={item.career_id}><i>{index+1}</i><span><b>{item.name}</b><small>{item.vacancy_count} вакансій · {money(item.salary_median)}</small></span><Icon name="arrow"/></Link>)}</div></>:<div className="region-mobile-empty"><h3>Даних поки немає</h3><p>{details.message}</p></div>:<Loading/>}
      </section>:<section className="region-mobile-popular">
        <div className="region-mobile-popular-head"><div><span>Топ регіонів</span><h3>Найбільше вакансій</h3></div><small>Гортайте →</small></div>
        <div className="region-mobile-region-rail">{rankedRegions.slice(0,5).map((item,index)=><button type="button" onClick={()=>void selectRegion(item.region)} key={item.region}><i>{String(index+1).padStart(2,"0")}</i><span><b>{item.region.replace(" область","")}</b><small>{new Intl.NumberFormat("uk-UA").format(item.vacancy_count)} вакансій</small></span><Icon name="arrow"/></button>)}</div>
      </section>}
    </div>
    <p className="market-attribution">Дані вакансій: <a href={overview?.source_url} target="_blank" rel="noreferrer">Державна служба зайнятості України</a>. SVG-карта: <a href="https://github.com/VictorCazanave/svg-maps/tree/master/packages/ukraine" target="_blank" rel="noreferrer">@svg-maps/ukraine, CC BY 4.0</a>.</p>
  </section>
}
function EmptyState({ title, text }: { title: string; text: string }) { return <div className="empty"><span>✦</span><h3>{title}</h3><p>{text}</p></div>; }
function Loading() { return <div className="loading loading-indicator" role="status" aria-live="polite"><span className="loading-spinner" aria-hidden="true"/><strong>Завантажуємо дані</strong><small>Будь ласка, зачекайте кілька секунд</small></div>; }
function ErrorBox({ message }: { message: string }) { return <div className="error">{message}</div>; }

function CareerCatalog() {
  const {id}=useParams(); const [items, setItems] = useState<CareerListItem[]>([]); const [error, setError] = useState(""); const [query, setQuery] = useState(""); const [category,setCategory]=useState("Усі");
  useEffect(() => { publicRequest<CareerListItem[]>("/careers").then(setItems).catch(e => setError(e.message)); }, []);
  if(id)return <CareerDetailPage id={id} items={items}/>;
  const categories=["Усі",...Array.from(new Set(items.map(x=>x.category_uk).filter((x):x is string=>!!x)))];
  const filtered = items.filter(x => (category==="Усі"||x.category_uk===category)&&`${x.name_uk} ${x.category_uk ?? ""} ${x.short_description_uk??""}`.toLowerCase().includes(query.toLowerCase()));
  return <section><div className="hero-split catalog-hero"><div><span className="eyebrow">Досліджуйте. Обирайте. Розвивайтесь</span><h1>Професії</h1><p className="lead">Досліджуйте світ професій, дізнавайтеся, чим вони займаються, та відкривайте нові можливості для свого майбутнього.</p><input className="search" placeholder="Пошук професії, навички або сфери діяльності" value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="illus-wrap"><div className="illus-frame"><PersonIllustration/></div><div className="doodle"><span>↘</span> Відкривайте нові можливості</div></div></div>
    <div className="pill-row">{categories.map(x=><button className={category===x?"active":""} onClick={()=>setCategory(x)} key={x}>{x}</button>)}</div>{error && <ErrorBox message={error}/>} {!items.length && !error ? <Loading/> : filtered.length?<div className="pcard-grid">{filtered.map((x,i)=><Link className="pcard" to={`/catalog/${x.id}`} key={x.id}><div className={`pcard-illus tone-${i%3}`}><PersonIllustration/></div><div className="pcard-body"><h3>{x.name_uk}</h3><p>{x.short_description_uk || x.category_uk || "Перегляньте опис професії та ключові вимоги."}</p><span><Icon name="arrow"/></span></div></Link>)}</div>:<EmptyState title="Нічого не знайдено" text="Спробуйте інший запит або категорію."/>}<CtaBand title="Не знайшли потрібну професію?" text="Каталог поповнюється. Спробуйте інший запит або перегляньте всі категорії."/>
  </section>;
}
function CareerDetailPage({id,items}:{id:string;items:CareerListItem[]}){const [data,setData]=useState<Record<string,any>|null>(null);const [error,setError]=useState("");const [tab,setTab]=useState("about");useEffect(()=>{publicRequest<Record<string,any>>(`/careers/${id}`).then(setData).catch(e=>setError(e.message))},[id]);if(error)return <ErrorBox message={error}/>;if(!data)return <Loading/>;const identity=data.identity||{},overview=data.overview||{},responsibilities=data.responsibilities||[],skills=data.skills||{hard:[],soft:[]};return <section><div className="crumb"><Link to="/">Головна</Link><span>›</span><Link to="/catalog">Професії</Link><span>›</span><b>{identity.name_uk}</b></div><div className="hero-split detail-hero"><div><h1>{identity.name_uk}</h1><p className="lead">{overview.short_description_uk}</p></div><div className="illus-frame"><PersonIllustration/></div></div><div className="detail-tabs">{[["about","Про професію"],["skills","Навички"],["education","Освіта і розвиток"],["market","Ринок праці"],["related","Схожі професії"]].map(([k,t])=><button className={tab===k?"active":""} onClick={()=>setTab(k)} key={k}>{t}</button>)}</div>{tab==="about"&&<div className="detail-grid"><article className="panel"><h2>Про професію</h2><p>{overview.long_description_uk||"Розгорнутий опис готується."}</p></article><article className="panel"><h2>Що ви робитимете</h2><ul>{responsibilities.slice(0,4).map((r:Record<string,unknown>,i:number)=><li key={i}>{String(r.title_uk||"")}</li>)}</ul><Link className="button" to="/profile">Перевірити, чи підходить мені →</Link></article></div>}{tab==="skills"&&<div className="panel"><h2>Навички</h2><div className="skill-chips">{[...(skills.hard||[]),...(skills.soft||[])].map((s:Record<string,unknown>,i:number)=><span key={i}>{String(s.name_uk||"")}</span>)}</div></div>}{tab==="education"&&<EmptyState title="Освіта і розвиток" text="Перегляньте вимоги та типовий шлях входу у професію."/>}{tab==="market"&&<EmptyState title="Дані ринку будуть додані пізніше" text="Ми не показуємо орієнтовних цифр без перевіреного джерела."/>}{tab==="related"&&<div className="pcard-grid">{items.filter(x=>x.id!==id).slice(0,3).map(x=><Link className="pcard" to={`/catalog/${x.id}`} key={x.id}><div className="pcard-body"><h3>{x.name_uk}</h3><p>{x.category_uk}</p></div></Link>)}</div>}</section>}

function ProfileStart() { return <StaticPage title="Створити кар'єрний профіль" intro="Оберіть зручний спосіб, і ми допоможемо вам зробити перший крок до нових можливостей."><div className="choice-grid"><Link className="choice featured" to="/profile/edit"><span className="recommend"><Icon name="sparkles"/> Рекомендовано</span><span className="tn-ico"><Icon name="edit"/></span><b>Заповнити самостійно</b><span>Підійде, якщо готові пройти профіль за 10–15 хвилин.</span></Link><Link className="choice" to="/profile/cv"><span className="tn-ico"><Icon name="doc"/></span><b>Завантажити резюме</b><span>Ми проаналізуємо ваш досвід і допоможемо швидше заповнити профіль.</span></Link><div className="choice disabled"><span className="tn-ico"><Icon name="briefcase"/></span><b>Профіль створює консультант <small className="soon-tag">Незабаром</small></b><span>Отримайте особисту підтримку від нашого фахівця.</span></div></div></StaticPage>; }

const wizardSteps=["Основне","Досвід","Освіта","Навички","Мови","Сертифікати","Активності","Мобільність","Перевірка"];
function ProfileWizard(){const nav=useNavigate();const [step,setStep]=useState(0);const [person,setPerson]=useState<Person|null>(null);const [core,setCore]=useState<Partial<PersonCore>>({first_name:""});const [error,setError]=useState("");useEffect(()=>{personRequest<Person>("/me/person").then(p=>{setPerson(p);setCore(p.core)}).catch(e=>{if(e.status!==404)setError(e.message)})},[]);const saveCore=async()=>{const p=await personRequest<Person>("/me/person",{method:"POST",body:JSON.stringify(core)});setPerson(p);setCore(p.core)};const next=async()=>{try{setError("");if(step===0)await saveCore();if(step===wizardSteps.length-1){await personRequest("/me/person/activate",{method:"POST"});nav("/profile/confirmed");return}setStep(x=>x+1)}catch(e){setError((e as Error).message)}};const lists:Record<number,[string,unknown[]]|undefined>={1:["Досвід роботи",person?.experiences||[]],2:["Освіта",person?.educations||[]],3:["Навички та інструменти",person?.skills||[]],4:["Мови",person?.languages||[]],5:["Сертифікати",person?.credentials||[]],6:["Проєкти та активності",person?.activities||[]],7:["Мобільність",person?[person.mobility]:[]]};return <section className="wizard-wrap"><div className="wizard-top"><span>Створення кар'єрного профілю</span><b>Крок {step+1} з {wizardSteps.length}</b></div><div className="wizard-track"><i style={{width:`${((step+1)/wizardSteps.length)*100}%`}}/></div><h1>{wizardSteps[step]}</h1>{step===0&&<div className="wizard-card"><div className="avatar">{`${core.first_name?.[0]||""}${core.last_name?.[0]||""}`.toUpperCase()||"?"}</div><div className="form form-grid">{[["first_name","Ім'я *"],["last_name","Прізвище"],["phone","Телефон"],["email","Email"],["telegram_username","Telegram (@username)"],["city","Місто"],["region","Область"]].map(([key,label])=><label key={key}><span>{label}</span><input required={key==="first_name"} value={String(core[key as keyof PersonCore]??"")} onChange={e=>setCore({...core,[key]:e.target.value})}/></label>)}</div></div>}{lists[step]&&<WizardFacts title={lists[step]![0]} rows={lists[step]![1]}/>} {step===8&&<div className="wizard-card review-card"><span className="review-check"><Icon name="check"/></span><h2>Чудово! Основна інформація готова</h2><p>Ви заповнили ключові розділи профілю. Далі ми дізнаємось більше про ваші сильні сторони, інтереси та цілі.</p>{wizardSteps.slice(0,5).map((x,i)=><div className="review-row" key={x}><Icon name={i===0||((lists[i]?.[1].length||0)>0)?"check":"doc"}/>{x}</div>)}</div>}{error&&<ErrorBox message={error}/>}<div className="wizard-nav">{step>0&&<button className="button secondary" onClick={()=>setStep(x=>x-1)}>Назад</button>}<button className="button" onClick={()=>void next()}>{step===8?"Зберегти профіль":"Продовжити →"}</button></div></section>}
function WizardFacts({title,rows}:{title:string;rows:unknown[]}){return <div className="wizard-card"><p className="muted">{rows.length?`Додано записів: ${rows.length}`:"Поки що порожньо. Це нормально — розділ можна заповнити пізніше."}</p>{rows.map((row,i)=><div className="wizard-fact" key={i}><span className="tn-ico"><Icon name="doc"/></span><b>{String((row as Record<string,unknown>).raw_job_title||(row as Record<string,unknown>).institution_name||(row as Record<string,unknown>).raw_input||(row as Record<string,unknown>).language||(row as Record<string,unknown>).title||title)}</b></div>)}</div>}

function ProfileEdit() {
  const [person, setPerson] = useState<Person | null>(null); const [core, setCore] = useState<Partial<PersonCore>>({ first_name: "" }); const [error,setError]=useState(""); const [saved,setSaved]=useState(false);
  useEffect(()=>{personRequest<Person>("/me/person").then(p=>{setPerson(p);setCore(p.core)}).catch(e=>{if(e.status!==404)setError(e.message)});},[]);
  const save=async(e:FormEvent)=>{e.preventDefault();setError("");setSaved(false);try{const p=await personRequest<Person>("/me/person",{method:"POST",body:JSON.stringify(core)});setPerson(p);setCore(p.core);setSaved(true);}catch(err){setError((err as Error).message)}};
  return <StaticPage title="Основна інформація" intro="Почніть з контактів. Інші блоки можна доповнювати поступово."><form className="panel form" onSubmit={save}><div className="form-grid">{[["first_name","Ім'я *"],["last_name","Прізвище"],["phone","Телефон"],["email","Email"],["telegram_username","Telegram"],["city","Місто"],["region","Область"],["country","Країна"]].map(([key,label])=><label key={key}><span>{label}</span><input required={key==="first_name"} value={String(core[key as keyof PersonCore]??"")} onChange={e=>setCore({...core,[key]:e.target.value})}/></label>)}</div><label><span>Нотатки</span><textarea rows={4} value={core.notes??""} onChange={e=>setCore({...core,notes:e.target.value})}/></label>{error&&<ErrorBox message={error}/>} {saved&&<div className="success">Дані збережено</div>}<button className="button" type="submit">Зберегти профіль</button>{person&&<Link className="button secondary" to="/profile/me">Переглянути профіль</Link>}</form></StaticPage>;
}

function MyProfile() {
  const [person,setPerson]=useState<Person|null>(null);const [error,setError]=useState("");useEffect(()=>{personRequest<Person>("/me/person").then(setPerson).catch(e=>setError(e.message));},[]);
  if(error)return <ErrorBox message={error}/>; if(!person)return <Loading/>; const c=person.core;
  return <section><div className="page-title"><div><span className="eyebrow">DIGITAL CAREER PROFILE</span><h1>{c.first_name} {c.last_name}</h1><p>{c.city||"Місто не вказано"} · {c.status_uk||"Чернетка"}</p></div><Link className="button" to="/profile/edit">Редагувати</Link></div><div className="profile-grid"><FactCard title="Контакти" rows={[c.phone,c.email,c.telegram_username]}/><FactCard title="Досвід" rows={person.experiences.map(x=>String(x.raw_job_title||"Досвід"))}/><FactCard title="Освіта" rows={person.educations.map(x=>String(x.institution_name||x.education_level_uk||"Освіта"))}/><FactCard title="Навички" rows={person.skills.map(x=>String(x.raw_input||x.proficiency_uk||"Навичка"))}/><FactCard title="Мови" rows={person.languages.map(x=>`${x.language||""} · ${x.level_uk||""}`)}/><FactCard title="Документи" rows={person.documents.map(x=>String(x.filename||"Документ"))}/></div></section>;
}
function FactCard({title,rows}:{title:string;rows:(unknown|null|undefined)[]}){const clean=rows.filter(Boolean);return <article className="card"><h3>{title}</h3>{clean.length?<ul>{clean.map((r,i)=><li key={i}>{String(r)}</li>)}</ul>:<p className="muted">Поки немає даних</p>}</article>}

function CvUpload(){const [state,setState]=useState("");const upload=async(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();const input=e.currentTarget.elements.namedItem("cv") as HTMLInputElement;if(!input.files?.[0])return;const body=new FormData();body.append("file",input.files[0]);setState("Обробляємо файл…");try{await personRequest("/me/person/cv",{method:"POST",body});setState("Файл завантажено. Наступним кроком буде перевірка знайдених даних.")}catch(err){setState((err as Error).message)}};return <StaticPage title="Завантажте ваше резюме" intro="Підтримуються PDF, DOC і DOCX до 10 МБ."><form className="upload" onSubmit={upload}><input name="cv" type="file" accept=".pdf,.doc,.docx" required/><button className="button">Обробити резюме</button>{state&&<p>{state}</p>}</form></StaticPage>}

const workspaceItems=[["/app","Огляд"],["/app/profile","Мій профіль"],["/app/analysis","Мій аналіз"],["/app/vacancies","Пошук вакансій"]] as const;
function WorkspaceLayout(){const nav=useNavigate(),[expired,setExpired]=useState(false);useEffect(()=>{const onExpired=()=>setExpired(true);window.addEventListener("user-session-expired",onExpired);return()=>window.removeEventListener("user-session-expired",onExpired)},[]);const authenticated=Boolean(localStorage.getItem(sessionStorageKeys.session)&&localStorage.getItem(sessionStorageKeys.account));const logout=()=>{localStorage.removeItem(sessionStorageKeys.session);localStorage.removeItem(sessionStorageKeys.user);localStorage.removeItem(sessionStorageKeys.account);nav("/")};if(!authenticated||expired)return <Navigate to="/login" replace/>;return <div className="workspace"><aside><Brand/><nav>{workspaceItems.map(([to,l])=><NavLink end={to==="/app"} key={to} to={to}>{l}</NavLink>)}</nav><Link to="/">← На головну</Link><button className="link-button" onClick={logout}>Вийти з облікового запису</button></aside><main><Outlet/></main></div>}
function Future({name}:{name:string}){return <section><h1>{name}</h1><EmptyState title="Незабаром" text="Функціональність ще не підключена до реальних даних."/></section>}

function AdminCatalog(){const [items,setItems]=useState<CareerListItem[]>([]);const [error,setError]=useState("");useEffect(()=>{adminRequest<CareerListItem[]>("/admin/careers").then(setItems).catch(e=>setError(e.message));},[]);return <section><div className="page-title"><div><span className="eyebrow">CAREER KB</span><h1>База професій</h1><p>Канонічні професії ICAN. Дані не дублюються.</p></div></div>{error&&<ErrorBox message={error}/>}<div className="cards careers">{items.slice(0,150).map(x=><article className="card" key={x.id}><span className={`status ${x.status}`}>{x.status||"draft"}</span><h3>{x.name_uk}</h3><p>{x.category_uk||x.code}</p></article>)}</div></section>}

export function App(){return <ConsoleGate><Routes><Route element={<PublicLayout/>}><Route index element={<Home/>}/><Route path="how" element={<How/>}/><Route path="about" element={<About/>}/><Route path="opportunities" element={<Opportunities/>}/><Route path="market" element={<Market/>}/><Route path="region" element={<Region/>}/><Route path="catalog" element={<CareerCatalog/>}/><Route path="catalog/:id" element={<CareerCatalog/>}/><Route path="profile" element={<ProfileStart/>}/><Route path="profile/build" element={<ProfileWizard/>}/><Route path="profile/edit" element={<UserProfileEditor/>}/><Route path="profile/me" element={<MyProfile/>}/><Route path="profile/cv" element={<CvUpload/>}/><Route path="profile/confirmed" element={<MyProfile/>}/></Route><Route path="login" element={<ConsoleLogin/>}/><Route path="app" element={<WorkspaceLayout/>}><Route index element={<UserDashboard/>}/><Route path="profile" element={<UserProfileEditor/>}/><Route path="profile/edit" element={<UserProfileEditor/>}/><Route path="analysis" element={<UserAnalysis/>}/><Route path="vacancies" element={<UserVacancies/>}/><Route path=":module" element={<Future name="Розділ у розробці"/>}/></Route><Route path="admin/login" element={<ConsoleLogin/>}/><Route element={<Outlet/>}><Route path="admin" element={<ConsoleLayout/>}><Route index element={<Navigate to="persons" replace/>}/><Route path="persons" element={<ConsolePersons/>}/><Route path="persons/new" element={<ConsoleCreate/>}/><Route path="persons/:id" element={<ConsolePerson/>}/><Route path="team" element={<ConsoleTeam/>}/><Route path="catalog" element={<AdminCatalog/>}/></Route></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes></ConsoleGate>}
