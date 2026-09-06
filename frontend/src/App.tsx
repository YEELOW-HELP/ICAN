import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { adminLogin, adminRequest, personRequest, publicRequest, sessionStorageKeys } from "./api/client";
import { useAppDispatch, useAppSelector } from "./app/hooks";
import { signedIn, signedOut } from "./app/store";
import type { CareerListItem, Person, PersonCore, PersonListItem } from "./types";

const publicNav = [
  ["/how", "Як це працює"], ["/catalog", "Професії"],
  ["/opportunities", "Можливості"], ["/about", "Про нас"],
] as const;

function Brand() {
  return <Link className="brand" to="/"><strong>YELLOW HUB</strong><span>Кар'єрний центр</span></Link>;
}

function PublicLayout() {
  return <div className="site">
    <header className="topbar"><Brand/><nav>{publicNav.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}</nav>
      <div className="top-actions"><Link className="text-link" to="/login">Увійти</Link><Link className="button small" to="/profile">Створити кар'єрний профіль</Link></div>
    </header>
    <main className="page"><Outlet/></main>
    <footer><Brand/><span>Ваш досвід має цінність. Ми допомагаємо побачити більше можливостей.</span></footer>
  </div>;
}

function Home() {
  return <>
    <section className="hero">
      <div><span className="eyebrow">ВАШ НАСТУПНИЙ КРОК — МОЖЛИВИЙ</span><h1>Не знаєте, куди рухатися в кар'єрі?</h1>
        <p className="lead">Створіть кар'єрний профіль і отримайте зрозумілий огляд досвіду, навичок та можливих напрямів.</p>
        <div className="actions"><Link className="button" to="/profile">Створити кар'єрний профіль</Link><Link className="button secondary" to="/catalog">Переглянути професії</Link></div>
      </div>
      <div className="hero-card"><span className="demo">ПРИКЛАД ПРОФІЛЮ</span><h3>Ваш цифровий кар'єрний профіль</h3>
        {[["Досвід і освіта","Зібрано в одному місці"],["Навички","Зрозуміло й структуровано"],["Кар'єрні цілі","Ваш наступний напрям"]].map(([a,b]) => <div className="preview-row" key={a}><b>{a}</b><span>{b}</span></div>)}
      </div>
    </section>
    <section><div className="section-heading"><span className="eyebrow">ДЛЯ КОГО ЦЕ</span><h2>Кар'єрна опора для різних ситуацій</h2></div>
      <div className="cards">{[["Шукаю роботу","Підготуйте профіль і побачте релевантні напрями."],["Змінюю професію","Зрозумійте, що вже можна використати в новій сфері."],["Повертаюся на ринок","Зберіть актуальний досвід без втрати важливих деталей."],["Шукаю свій шлях","Рухайтеся від фактів про себе до наступних кроків."]].map(([t,d],i)=><article className="card" key={t}><span className="card-num">0{i+1}</span><h3>{t}</h3><p>{d}</p></article>)}</div>
    </section>
  </>;
}

function StaticPage({ title, intro, children }: { title: string; intro: string; children?: ReactNode }) {
  return <section className="narrow"><span className="eyebrow">YELLOW HUB · МОЖУ</span><h1>{title}</h1><p className="lead">{intro}</p>{children}</section>;
}

function How() { return <StaticPage title="Як це працює" intro="Від вашого досвіду до зрозумілого кар'єрного напряму."><div className="steps">{["Створіть кар'єрний профіль","Отримайте професійні напрями","Перевірте рекомендації з консультантом","Оберіть наступний крок"].map((x,i)=><article className="card" key={x}><span className="step-number">{i+1}</span><h3>{x}</h3><p>Рухайтеся послідовно, без необхідності заповнювати все одразу.</p></article>)}</div></StaticPage>; }
function About() { return <StaticPage title="Про МОЖУ" intro="Соціальна програма Yellow Hub, що допомагає людям зробити обґрунтований професійний крок."><div className="panel"><h2>Місія</h2><p>Допомогти людині побачити цінність власного досвіду та перетворити її на реальний план дій.</p></div></StaticPage>; }
function Opportunities() { return <StaticPage title="Можливості" intro="Кар'єрні сценарії, вакансії та навчальні ресурси відкриватимуться поступово."><EmptyState title="Розділ готується" text="Ми не показуємо вигаданих вакансій або ринкових даних."/></StaticPage>; }
function LoginInfo() { return <StaticPage title="Вхід до профілю" intro="Особистий профіль працює через захищену сесію цього браузера."><Link className="button" to="/app">Перейти до мого простору</Link></StaticPage>; }

function EmptyState({ title, text }: { title: string; text: string }) { return <div className="empty"><span>✦</span><h3>{title}</h3><p>{text}</p></div>; }
function Loading() { return <div className="loading">Завантаження…</div>; }
function ErrorBox({ message }: { message: string }) { return <div className="error">{message}</div>; }

function CareerCatalog() {
  const [items, setItems] = useState<CareerListItem[]>([]); const [error, setError] = useState(""); const [query, setQuery] = useState("");
  useEffect(() => { publicRequest<CareerListItem[]>("/careers").then(setItems).catch(e => setError(e.message)); }, []);
  const filtered = items.filter(x => `${x.name_uk} ${x.category_uk ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  return <section><div className="page-title"><div><span className="eyebrow">КАР'ЄРНА БАЗА</span><h1>Професії</h1><p>Досліджуйте професії, обов'язки та вимоги.</p></div></div>
    <input className="search" placeholder="Пошук за професією або категорією" value={query} onChange={e=>setQuery(e.target.value)}/>{error && <ErrorBox message={error}/>} {!items.length && !error ? <Loading/> : <div className="cards careers">{filtered.map(x=><article className="card" key={x.id}><span className="pill">{x.category_uk || "Професія"}</span><h3>{x.name_uk}</h3><p>{x.short_description_uk || "Перегляньте опис професії та ключові вимоги."}</p><Link className="arrow-link" to={`/catalog/${x.id}`}>Переглянути →</Link></article>)}</div>}
  </section>;
}

function ProfileStart() { return <StaticPage title="Як ви хочете створити свій кар'єрний профіль?" intro="Оберіть зручний спосіб. Дані можна доповнити пізніше."><div className="choice-grid"><Link className="choice featured" to="/profile/cv"><b>Завантажити резюме (CV)</b><span>Ми автоматично заповнимо основну інформацію.</span></Link><Link className="choice" to="/profile/edit"><b>Заповнити самостійно</b><span>Крок за кроком, у зручному темпі.</span></Link><div className="choice disabled"><b>Профіль створює консультант</b><span>Зверніться до кар'єрного консультанта.</span></div></div></StaticPage>; }

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

const workspaceItems=[["/app","Огляд"],["/app/profile","Кар'єрний профіль"],["/app/scenarios","Сценарії"],["/app/route","Маршрут"],["/app/vacancies","Вакансії"],["/app/progress","Прогрес"]] as const;
function WorkspaceLayout(){return <div className="workspace"><aside><Brand/><nav>{workspaceItems.map(([to,l])=><NavLink end={to==="/app"} key={to} to={to}>{l}{!["/app","/app/profile"].includes(to)&&<small>Незабаром</small>}</NavLink>)}</nav><Link to="/">← На головну</Link></aside><main><Outlet/></main></div>}
function WorkspaceHome(){return <section><span className="eyebrow">МІЙ ПРОСТІР</span><h1>Ваш наступний крок</h1><div className="panel"><h2>Завершіть кар'єрний профіль</h2><p>Додайте факти про досвід, освіту та навички — вони стануть основою майбутніх рекомендацій.</p><Link className="button" to="/profile/edit">Доповнити профіль</Link></div></section>}
function Future({name}:{name:string}){return <section><h1>{name}</h1><EmptyState title="Незабаром" text="Функціональність ще не підключена до реальних даних."/></section>}

function RequireAdmin(){const token=useAppSelector(s=>s.auth.adminToken);return token?<Outlet/>:<Navigate to="/admin/login" replace/>}
function AdminLogin(){const dispatch=useAppDispatch();const nav=useNavigate();const [error,setError]=useState("");const submit=async(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{const data=await adminLogin(String(fd.get("email")),String(fd.get("password")));dispatch(signedIn({token:data.access_token,email:data.email}));nav("/admin/persons");}catch(err){setError((err as Error).message)}};return <div className="login-page"><div className="login-card"><Brand/><span className="eyebrow">CONSULTANT WORKSPACE</span><h1>Вхід консультанта</h1><p>Увійдіть, щоб працювати з клієнтами та їхніми профілями.</p><form onSubmit={submit}><label><span>Email</span><input name="email" type="email" defaultValue="admin@mnp.local" required/></label><label><span>Пароль</span><input name="password" type="password" required/></label>{error&&<ErrorBox message={error}/>}<button className="button wide">Увійти</button></form><Link to="/">← Повернутися на сайт</Link></div></div>}

function AdminLayout(){const dispatch=useAppDispatch();const nav=useNavigate();return <div className="admin-shell"><aside><Brand/><span className="side-label">CONSULTANT WORKSPACE</span><nav><NavLink to="/admin/persons">Мої клієнти</NavLink><NavLink to="/admin/persons/new">Створити клієнта</NavLink><NavLink to="/admin/catalog">Career KB</NavLink></nav><button className="link-button" onClick={()=>{dispatch(signedOut());nav("/admin/login")}}>Вийти</button></aside><main><Outlet/></main></div>}

function PersonList(){const [items,setItems]=useState<PersonListItem[]>([]);const [error,setError]=useState("");const [query,setQuery]=useState("");useEffect(()=>{adminRequest<PersonListItem[]>("/admin/persons").then(setItems).catch(e=>setError(e.message));},[]);const filtered=useMemo(()=>items.filter(x=>`${x.name} ${x.phone} ${x.email} ${x.city}`.toLowerCase().includes(query.toLowerCase())),[items,query]);return <section><div className="page-title"><div><span className="eyebrow">PERSON KB</span><h1>Мої клієнти</h1><p>Єдина база профілів для роботи консультанта.</p></div><Link className="button" to="/admin/persons/new">+ Створити клієнта</Link></div><input className="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Пошук за ім'ям, телефоном, email або містом"/>{error&&<ErrorBox message={error}/>}<div className="table-wrap"><table><thead><tr><th>Клієнт</th><th>Телефон</th><th>Email</th><th>Місто</th><th>Статус</th><th>Оновлено</th><th/></tr></thead><tbody>{filtered.map(p=><tr key={p.id}><td><b>{p.name||"Без імені"}</b><small>{p.telegram_username}</small></td><td>{p.phone||"—"}</td><td>{p.email||"—"}</td><td>{p.city||"—"}</td><td><span className={`status ${p.status}`}>{p.status_uk}</span></td><td>{p.updated_at?.slice(0,10)||"—"}</td><td><Link className="button secondary small" to={`/admin/persons/${p.id}`}>Відкрити</Link></td></tr>)}</tbody></table>{!filtered.length&&!error&&<EmptyState title="Клієнтів не знайдено" text="Змініть пошук або створіть нового клієнта."/>}</div></section>}

function PersonCreate(){const nav=useNavigate();const [error,setError]=useState("");const submit=async(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();const fd=new FormData(e.currentTarget);try{const p=await adminRequest<Person>("/admin/persons",{method:"POST",body:JSON.stringify({first_name:String(fd.get("first_name")),last_name:String(fd.get("last_name")||"")})});nav(`/admin/persons/${p.id}`)}catch(err){setError((err as Error).message)}};return <section className="narrow"><span className="eyebrow">НОВИЙ КЛІЄНТ</span><h1>Створити профіль</h1><form className="panel form" onSubmit={submit}><label><span>Ім'я *</span><input name="first_name" required autoFocus/></label><label><span>Прізвище</span><input name="last_name"/></label>{error&&<ErrorBox message={error}/>}<button className="button">Створити та відкрити</button></form></section>}

const detailTabs=["Основне","Освіта","Досвід","Активності","Навички","Мови","Документи","Мобільність"];
function PersonDetail(){const {id}=useParams();const [person,setPerson]=useState<Person|null>(null);const [core,setCore]=useState<Partial<PersonCore>>({first_name:""});const [tab,setTab]=useState("Основне");const [error,setError]=useState("");const [saved,setSaved]=useState(false);const load=()=>adminRequest<Person>(`/admin/persons/${id}`).then(p=>{setPerson(p);setCore(p.core)}).catch(e=>setError(e.message));useEffect(()=>{void load()},[id]);const save=async(e:FormEvent)=>{e.preventDefault();setSaved(false);try{const p=await adminRequest<Person>(`/admin/persons/${id}`,{method:"PATCH",body:JSON.stringify(core)});setPerson(p);setCore(p.core);setSaved(true)}catch(err){setError((err as Error).message)}};if(error&&!person)return <ErrorBox message={error}/>;if(!person)return <Loading/>;const collections:Record<string,[string,unknown[]]>={"Освіта":["educations",person.educations],"Досвід":["experiences",person.experiences],"Активності":["activities",person.activities],"Навички":["skills",person.skills],"Мови":["languages",person.languages],"Документи":["documents",person.documents]};return <section><div className="page-title"><div><Link className="back" to="/admin/persons">← Мої клієнти</Link><h1>{person.core.first_name} {person.core.last_name}</h1><p>ID: {person.id}</p></div><span className={`status ${person.core.status}`}>{person.core.status_uk}</span></div><div className="tabs">{detailTabs.map(x=><button className={tab===x?"active":""} onClick={()=>setTab(x)} key={x}>{x}</button>)}</div>{tab==="Основне"&&<form className="panel form" onSubmit={save}><div className="form-grid">{[["first_name","Ім'я *"],["last_name","Прізвище"],["phone","Телефон"],["email","Email"],["telegram_username","Telegram"],["city","Місто"],["region","Область"],["country","Країна"],["date_of_birth","Дата народження"]].map(([key,label])=><label key={key}><span>{label}</span><input type={key==="date_of_birth"?"date":"text"} required={key==="first_name"} value={String(core[key as keyof PersonCore]??"")} onChange={e=>setCore({...core,[key]:e.target.value})}/></label>)}</div><label><span>Нотатки консультанта</span><textarea rows={5} value={core.notes??""} onChange={e=>setCore({...core,notes:e.target.value})}/></label>{saved&&<div className="success">Зміни збережено. Дані залишаться після перезавантаження.</div>}<button className="button">Зберегти</button><button className="button secondary" type="button" onClick={()=>void load()}>Перезавантажити</button></form>}{collections[tab]&&<CollectionView title={tab} rows={collections[tab][1]}/>} {tab==="Мобільність"&&<CollectionView title="Мобільність і формат роботи" rows={[person.mobility]}/>}</section>}
function CollectionView({title,rows}:{title:string;rows:unknown[]}){return <div className="panel"><div className="page-title compact"><div><h2>{title}</h2><p>Факти з канонічного профілю MnpPerson.</p></div></div>{rows.length?<div className="fact-list">{rows.map((row,i)=><pre key={i}>{JSON.stringify(row,null,2)}</pre>)}</div>:<EmptyState title="Даних поки немає" text="Редагування цього блоку буде перенесене в наступній ітерації."/>}</div>}

function AdminCatalog(){const [items,setItems]=useState<CareerListItem[]>([]);const [error,setError]=useState("");useEffect(()=>{adminRequest<CareerListItem[]>("/admin/careers").then(setItems).catch(e=>setError(e.message));},[]);return <section><div className="page-title"><div><span className="eyebrow">CAREER KB</span><h1>База професій</h1><p>Канонічні професії ICAN. Дані не дублюються.</p></div></div>{error&&<ErrorBox message={error}/>}<div className="cards careers">{items.slice(0,150).map(x=><article className="card" key={x.id}><span className={`status ${x.status}`}>{x.status||"draft"}</span><h3>{x.name_uk}</h3><p>{x.category_uk||x.code}</p></article>)}</div></section>}

export function App(){return <Routes><Route element={<PublicLayout/>}><Route index element={<Home/>}/><Route path="how" element={<How/>}/><Route path="about" element={<About/>}/><Route path="opportunities" element={<Opportunities/>}/><Route path="login" element={<LoginInfo/>}/><Route path="catalog" element={<CareerCatalog/>}/><Route path="catalog/:id" element={<CareerCatalog/>}/><Route path="profile" element={<ProfileStart/>}/><Route path="profile/build" element={<ProfileEdit/>}/><Route path="profile/edit" element={<ProfileEdit/>}/><Route path="profile/me" element={<MyProfile/>}/><Route path="profile/cv" element={<CvUpload/>}/><Route path="profile/confirmed" element={<MyProfile/>}/></Route><Route path="app" element={<WorkspaceLayout/>}><Route index element={<WorkspaceHome/>}/><Route path="profile" element={<MyProfile/>}/><Route path=":module" element={<Future name="Розділ у розробці"/>}/></Route><Route path="admin/login" element={<AdminLogin/>}/><Route element={<RequireAdmin/>}><Route path="admin" element={<AdminLayout/>}><Route index element={<Navigate to="persons" replace/>}/><Route path="persons" element={<PersonList/>}/><Route path="persons/new" element={<PersonCreate/>}/><Route path="persons/:id" element={<PersonDetail/>}/><Route path="catalog" element={<AdminCatalog/>}/></Route></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}
