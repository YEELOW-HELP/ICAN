import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import "./profile.css";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { adminBootstrapStatus, adminDownload, adminLogin, adminRequest, ApiError, bootstrapSuperAdmin } from "./api/client";
import { useAppDispatch, useAppSelector } from "./app/hooks";
import { signedIn, signedOut, staffVerified } from "./app/store";
import type { Person, PersonCore, PersonListItem, FactRow, StaffSummary, SuperAdminAiRecommendation } from "./types";

const personStatuses = [["case","КЕЙС"],["draft","Чернетка"],["active","Активний"],["archived","В архіві"]];
const workflowStages = [["new_request","Нова заявка"],["needs_contact","Потрібно зв’язатися"],["in_contact","В контакті"],["consultation_scheduled","Консультація запланована"],["consultation_completed","Консультація проведена"],["in_progress","У роботі"],["employed","Працевлаштований"],["closed","Закритий"]];
const closureReasons = [["no_response","Не відповідає"],["refused","Відмовився"],["not_relevant","Неактуально"],["other","Інше"]];
const referralSources = [["instagram","Instagram"],["telegram","Telegram"],["workshop","Воркшоп"],["phone","Телефонний дзвінок"],["work_ua","Work.ua"],["recommendation","За рекомендацією"],["other","Інше"]];
function referralLabel(core:Partial<PersonCore>){
  const label=referralSources.find(([key])=>key===core.referral_source)?.[1]||"Не вказано";
  return core.referral_source==="other"&&core.referral_details?`${label}: ${core.referral_details}`:label;
}
function ReferralFields({value,onChange}:{value:Partial<PersonCore>;onChange:(value:Partial<PersonCore>)=>void}){
  return <div className="form-grid referral-fields"><label><span>Звідки дізнався про нас</span><select aria-label="Звідки дізнався про нас" value={value.referral_source||""} onChange={e=>onChange({...value,referral_source:e.target.value||null,referral_details:null})}><option value="">Не вказано</option>{referralSources.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>{value.referral_source==="other"&&<label><span>Уточніть джерело *</span><input required maxLength={300} value={value.referral_details||""} placeholder="Наприклад, оголошення в громаді" onChange={e=>onChange({...value,referral_details:e.target.value})}/></label>}</div>;
}
const roles: Record<string,string> = {super_admin:"Суперадміністратор", admin:"Адміністратор", manager:"Менеджер"};
type Staff = StaffSummary & {is_creator?:boolean};
type DuplicateMatch={id:string|null;name:string;phone?:string|null;email?:string|null;match_reasons:("phone"|"email")[];has_access:boolean};
const errText = (e:unknown) => e instanceof Error ? e.message : "Не вдалося виконати дію";
function Notice({error}:{error:string}) { return error ? <div className="error" role="alert">{error}</div> : null }
function ConsoleBrand(){return <div className="console-brand"><span>Y</span><div>Yellow Hub<small>Робочий простір</small></div></div>}
function normalizePhoneInput(value:string){
  let digits=value.replace(/\D/g,"");if(digits.startsWith("00"))digits=digits.slice(2);
  if(digits.length===9)digits="380"+digits;else if(digits.length===10&&digits.startsWith("0"))digits="38"+digits;else if(digits.length===11&&digits.startsWith("80"))digits="3"+digits;
  return digits.length>=8&&digits.length<=15?"+"+digits:value.trim();
}
function DuplicateWarning({phone,email,excludeId}:{phone?:string|null;email?:string|null;excludeId?:string}){
  const [matches,setMatches]=useState<DuplicateMatch[]>([]);
  useEffect(()=>{const phoneReady=(phone||"").replace(/\D/g,"").length>=9,emailReady=(email||"").includes("@");if(!phoneReady&&!emailReady){setMatches([]);return}const timeout=window.setTimeout(()=>{const query=new URLSearchParams();if(phoneReady)query.set("phone",phone||"");if(emailReady)query.set("email",email||"");if(excludeId)query.set("exclude_person_id",excludeId);adminRequest<DuplicateMatch[]>(`/admin/persons/duplicates?${query}`).then(setMatches).catch(()=>setMatches([]))},450);return()=>window.clearTimeout(timeout)},[phone,email,excludeId]);
  if(!matches.length)return null;
  return <div className="duplicate-warning" role="status"><b>Можливо, цей клієнт уже є в базі</b>{matches.map(match=><div key={`${match.id||match.name}-${match.match_reasons.join("-")}`}><span><strong>{match.name}</strong><small>Збіг: {match.match_reasons.map(reason=>reason==="phone"?"телефон":"email").join(" та ")}</small></span>{match.has_access&&match.id?<Link className="button secondary small" to={`/admin/persons/${match.id}`}>Відкрити профіль</Link>:<small>Зверніться до адміністратора, щоб отримати доступ.</small>}</div>)}</div>;
}

export function ConsoleGate({children}:{children:ReactNode}) {
  const auth=useAppSelector(s=>s.auth), dispatch=useAppDispatch(), location=useLocation();
  const [verified,setVerified]=useState<string|null>(null),[error,setError]=useState("");
  useEffect(()=>{
    let current=true;
    const verify=async()=>{
      if(!auth.adminToken)return;
      try { const me=await adminRequest<Staff>("/admin/me"); if(current){dispatch(staffVerified(me));setVerified(auth.adminToken);setError("")} }
      catch(e){if(current){if(e instanceof ApiError && e.status===401){dispatch(signedOut());setVerified(null)}else setError(errText(e))}}
    };
    void verify(); window.addEventListener("focus",verify);
    const expired=()=>{dispatch(signedOut());setVerified(null)};
    window.addEventListener("console-session-expired",expired);
    return ()=>{current=false;window.removeEventListener("focus",verify);window.removeEventListener("console-session-expired",expired)};
  },[auth.adminToken,dispatch,location.pathname]);
  if(!auth.adminToken)return <ConsoleLogin/>;
  if(error)return <div className="console-auth"><div className="console-login"><Notice error={error}/><button className="button" onClick={()=>window.location.reload()}>Спробувати ще раз</button></div></div>;
  if(verified!==auth.adminToken || !auth.role)return <div className="loading">Перевіряємо доступ…</div>;
  if(!roles[auth.role])return <div className="console-auth"><div className="console-login"><Notice error="Цей обліковий запис не має доступу до консолі"/><button className="button" onClick={()=>dispatch(signedOut())}>Вийти</button></div></div>;
  if(location.pathname==="/admin/login" || location.pathname==="/login")return <Navigate to="/admin/persons" replace/>;
  if(auth.role!=="super_admin" && !location.pathname.startsWith("/admin"))return <Navigate to="/admin/persons" replace/>;
  if(auth.role==="manager" && (location.pathname.startsWith("/admin/team") || location.pathname.startsWith("/admin/catalog")))return <Navigate to="/admin/persons" replace/>;
  return <>{auth.role==="super_admin"&&!location.pathname.startsWith("/admin")&&<Link className="console-return" to="/admin/persons">← Консоль</Link>}{children}</>;
}

export function ConsoleLogin(){
  const dispatch=useAppDispatch(),nav=useNavigate();
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[show,setShow]=useState(false),[bootstrap,setBootstrap]=useState(false),[checking,setChecking]=useState(true);
  useEffect(()=>{adminBootstrapStatus().then(x=>setBootstrap(x.registration_open)).catch(e=>setError(errText(e))).finally(()=>setChecking(false))},[]);
  const submit=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();const form=new FormData(e.currentTarget);setBusy(true);setError("");
    try {const email=String(form.get("email")).trim(),password=String(form.get("password"));if(bootstrap)await bootstrapSuperAdmin(String(form.get("full_name")||"").trim(),email,password);const data=await adminLogin(email,password);dispatch(signedIn({token:data.access_token,email:data.email}));nav("/admin/persons")}
    catch(e){setError(e instanceof ApiError&&e.status===401?"Невірний email або пароль, або обліковий запис вимкнено.":errText(e))}finally{setBusy(false)}
  };
  return <div className="console-auth"><section className="console-auth-story"><ConsoleBrand/><div><span className="console-kicker">ЛЮДИ. МОЖЛИВОСТІ. РЕЗУЛЬТАТ.</span><h1>Кожна зміна<br/>починається<br/><em>з людини.</em></h1><p>Клієнти, профілі та робота команди — в одному просторі.</p></div><small>Yellow Hub · МОЖУ</small></section><main className="console-auth-form"><div className="console-login"><span className="console-kicker">{bootstrap?"ПЕРШИЙ ЗАПУСК":"РАДІ БАЧИТИ ВАС"}</span><h1>{bootstrap?"Створення власника":"Вхід у консоль"}</h1><p>{bootstrap?"Створіть перший обліковий запис. Він автоматично отримає роль суперадміністратора.":"Використайте робочий обліковий запис, щоб продовжити."}</p>{checking?<p>Перевіряємо систему…</p>:<form onSubmit={submit} className="form">{bootstrap&&<label><span>Ваше ім’я</span><input name="full_name" required autoFocus/></label>}<label><span>Робочий email</span><input name="email" type="email" autoComplete="username" placeholder="name@example.com" required autoFocus={!bootstrap}/></label><label><span>Пароль (від 8 символів)</span><div className="password-field"><input name="password" minLength={8} type={show?"text":"password"} autoComplete={bootstrap?"new-password":"current-password"} required/><button type="button" onClick={()=>setShow(!show)} aria-label={show?"Приховати пароль":"Показати пароль"}>{show?"Сховати":"Показати"}</button></div></label><Notice error={error}/><button disabled={busy} className="button wide">{busy?"Зберігаємо…":bootstrap?"Створити суперадміна →":"Увійти →"}</button></form>}{!bootstrap&&!checking&&<p className="console-login-help">Для отримання доступу зверніться до адміністратора команди.</p>}</div></main></div>
}

export function ConsoleLayout(){
  const auth=useAppSelector(s=>s.auth),dispatch=useAppDispatch();
  return <div className="admin-shell console-shell"><aside><ConsoleBrand/><span className="side-label">КОНСОЛЬ</span><nav><NavLink end to="/admin/persons">Клієнти <span>↗</span></NavLink><NavLink to="/admin/persons/new">Додати клієнта <span>+</span></NavLink>{auth.role!=="manager"&&<><NavLink to="/admin/team">Команда</NavLink><NavLink to="/admin/catalog">База професій</NavLink></>}{auth.role==="super_admin"&&<Link to="/">Переглянути сайт ↗</Link>}</nav><div className="console-account"><span className="console-avatar">{auth.adminEmail?.[0]?.toUpperCase()}</span><div><strong>{roles[auth.role||""]}</strong><small>{auth.adminEmail}</small></div></div><button className="button secondary" onClick={()=>dispatch(signedOut())}>Вийти з облікового запису</button></aside><main><div className="console-topline"><span>Yellow Hub / Консоль</span><span className="status active">{roles[auth.role||""]}</span></div><Outlet/></main></div>
}

export function ConsolePersons(){
  const role=useAppSelector(s=>s.auth.role);
  const [items,setItems]=useState<PersonListItem[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true),[query,setQuery]=useState(""),[status,setStatus]=useState(""),[quickFilter,setQuickFilter]=useState("");
  const load=()=>{setLoading(true);setError("");adminRequest<PersonListItem[]>("/admin/persons").then(setItems).catch(e=>setError(errText(e))).finally(()=>setLoading(false))};
  useEffect(load,[]);
  const filterMatches=(person:PersonListItem)=>quickFilter==="needs-contact"?person.needs_contact:quickFilter==="without-responsible"?!person.responsible:quickFilter==="without-next-action"?!person.has_next_action:true;
  const filtered=items.filter(p=>(!status||p.status===status)&&filterMatches(p)&&`${p.name} ${p.phone??""} ${p.email??""} ${p.city??""} ${p.responsible?.full_name??""}`.toLowerCase().includes(query.toLowerCase()));
  const quickFilters:[[string,string,number],[string,string,number],[string,string,number]]=[
    ["needs-contact","Потребують контакту",items.filter(p=>p.needs_contact).length],
    ["without-responsible","Без відповідального",items.filter(p=>!p.responsible).length],
    ["without-next-action","Без наступної дії",items.filter(p=>!p.has_next_action).length],
  ];
  return <section><div className="page-title"><div><span className="console-kicker">РОБОТА З ЛЮДЬМИ</span><h1>{role==="manager"?"Мої клієнти":"Усі клієнти"}</h1><p>{role==="manager"?"Створені вами та доступні вам профілі.":"Єдина база клієнтів вашої команди."}</p></div><Link className="button" to="/admin/persons/new">+ Додати клієнта</Link></div><div className="console-metrics console-person-metrics">{[["Доступних клієнтів",items.length],["Кейсів",items.filter(p=>p.status==="case").length],["Активних",items.filter(p=>p.status==="active").length],["Чернеток",items.filter(p=>p.status==="draft").length]].map(([label,value])=><article key={label}><span>{label}</span><strong>{loading?"—":value}</strong></article>)}</div><div className="console-list-panel"><div className="workflow-quick-filters" aria-label="Швидкі фільтри">{quickFilters.map(([value,label,count])=><button type="button" key={value} className={quickFilter===value?"active":""} aria-pressed={quickFilter===value} onClick={()=>setQuickFilter(quickFilter===value?"":value)}><span>{label}</span><b>{loading?"—":count}</b></button>)}</div><div className="console-filters"><input aria-label="Пошук клієнтів" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ім’я, телефон, email, місто або консультант"/><select aria-label="Статус" value={status} onChange={e=>setStatus(e.target.value)}><option value="">Усі статуси</option>{personStatuses.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select><button className="button secondary" onClick={load} disabled={loading}>Оновити</button></div><Notice error={error}/><div className="table-wrap"><table><thead><tr><th>Клієнт</th><th>Контакти</th><th>Місто</th><th>Супровід</th><th>Статус</th><th/></tr></thead><tbody>{!loading&&filtered.map(p=><tr key={p.id}><td><Link className="console-person-link" to={`/admin/persons/${p.id}`}><span className="console-avatar">{p.name?.[0]||"?"}</span><b>{p.name||"Без імені"}</b></Link></td><td>{p.phone||"—"}<small>{p.email}</small></td><td>{p.city||"—"}</td><td><div className="workflow-table-cell"><b>{p.responsible?.full_name||p.responsible?.email||"Без відповідального"}</b><span className="workflow-stage-label">{p.workflow_stage_uk||"Нова заявка"}</span>{p.needs_contact?<small className="needs-contact-label">Потрібно зв’язатися</small>:p.next_action_at?<small>Наступна дія: {new Date(p.next_action_at).toLocaleString("uk-UA",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}</small>:<small>Наступної дії немає</small>}</div></td><td><span className={`status ${p.status}`}>{p.status_uk}</span></td><td><Link className="button secondary small" to={`/admin/persons/${p.id}`}>Відкрити →</Link></td></tr>)}</tbody></table>{loading?<p className="loading">Завантажуємо клієнтів…</p>:!filtered.length&&<div className="console-empty"><h2>{query||status||quickFilter?"Нічого не знайдено":"Тут будуть ваші клієнти"}</h2><p>{query||status||quickFilter?"Змініть пошук або фільтр.":"Додайте першого клієнта, щоб почати роботу."}</p></div>}</div><div className="console-list-footer">Показано {filtered.length} із {items.length}</div></div></section>
}

const coreFields=[['first_name',"Ім’я",'text'],['last_name','Прізвище','text'],['phone','Телефон','tel'],['email','Email','email'],['city','Місто','text'],['region','Область','text'],['country','Країна','text'],['date_of_birth','Дата народження','date'],['telegram_username','Telegram','text']];
function CoreFields({value,onChange,only}:{only?:string[];value:Partial<PersonCore>;onChange:(v:Partial<PersonCore>)=>void}){return <div className="form-grid">{coreFields.filter(([key])=>!only||only.includes(key)).map(([key,label,type])=><label key={key}><span>{label}{key==="first_name"?" *":""}</span><input type={type} required={key==="first_name"} value={String(value[key as keyof PersonCore]??"")} onChange={e=>onChange({...value,[key]:e.target.value})} onBlur={key==="phone"?()=>onChange({...value,phone:normalizePhoneInput(String(value.phone||""))}):undefined}/></label>)}</div>}
export function ConsoleCreate(){
  const nav=useNavigate();
  const [core,setCore]=useState<Partial<PersonCore>>({first_name:"",status:"case"}),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const submit=async(e:FormEvent)=>{
    e.preventDefault();if(busy)return;setBusy(true);setError("");
    try{const p=await adminRequest<Person>("/admin/persons",{method:"POST",body:JSON.stringify(core)});nav("/admin/persons/"+p.id)}
    catch(e){setError(errText(e))}finally{setBusy(false)}
  };
  return <section className="client-profile client-create">
    <div className="profile-breadcrumb"><Link className="back" to="/admin/persons"><span className="back-icon" aria-hidden="true">←</span><span>Клієнти</span></Link><span>/</span><span>Новий клієнт</span></div>
    <header className="profile-header">
      <div className="profile-identity"><span className="profile-avatar create-avatar"><ProfileIcon name="user"/></span><div className="profile-heading"><span className="console-kicker">НОВЕ ЗНАЙОМСТВО</span><h1>Додати клієнта</h1><p className="create-intro">Перший крок до нових можливостей.</p></div></div>
      <span className="create-required-hint"><span aria-hidden="true">*</span> Лише ім’я обов’язкове</span>
    </header>
    <div className="profile-overview create-overview">
      <form className="panel form profile-contact-card" onSubmit={submit} aria-label="Новий клієнт">
        <div className="profile-card-heading"><span className="profile-section-icon"><ProfileIcon name="user"/></span><div><h2>Основна інформація</h2><p>Заповніть те, що вже знаєте про людину</p></div></div>
        <label className="create-status-field"><span>Статус клієнта</span><select aria-label="Статус клієнта" value={core.status||"case"} disabled={busy} onChange={e=>setCore({...core,status:e.target.value})}>{personStatuses.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        <fieldset disabled={busy}><legend><span className="create-section-number">01</span> Особисті дані</legend><CoreFields only={["first_name","last_name","date_of_birth"]} value={core} onChange={setCore}/></fieldset>
        <fieldset disabled={busy}><legend><span className="create-section-number">02</span> Як зв’язатися</legend><CoreFields only={["phone","email","telegram_username"]} value={core} onChange={setCore}/><DuplicateWarning phone={core.phone} email={core.email}/></fieldset>
        <fieldset disabled={busy}><legend><span className="create-section-number">03</span> Місце проживання</legend><CoreFields only={["city","region","country"]} value={core} onChange={setCore}/></fieldset>
        <fieldset disabled={busy}><legend><span className="create-section-number">04</span> Знайомство з нами</legend><ReferralFields value={core} onChange={setCore}/></fieldset>
        <Notice error={error}/>
        <div className="console-form-actions profile-form-footer create-form-footer"><Link className="create-cancel" to="/admin/persons">Скасувати</Link><button type="submit" disabled={busy} className="button">{busy?"Створюємо…":"Створити профіль"}{!busy&&<ProfileIcon name="arrow"/>}</button></div>
      </form>
      <aside className="profile-sidebar create-sidebar">
        <section className="create-guide">
          <span className="create-guide-icon"><ProfileIcon name="spark"/></span>
          <h2>Почніть з імені</h2><p>Не потрібно знати все одразу. Контакти, досвід та інші деталі можна додати в будь-який момент.</p>
          <div className="create-guide-divider"/>
          <h3>Що далі?</h3>
          <ol className="create-next-steps">
            <li><span className="profile-section-icon"><ProfileIcon name="user"/></span><div><b>Уточніть запит</b><p>Після створення виберіть потреби клієнта та наступну дію.</p></div></li>
            <li><span className="profile-section-icon"><ProfileIcon name="file"/></span><div><b>Прикріпіть CV</b><p>Якщо є резюме, збережіть його в картці клієнта.</p></div></li>
            <li><span className="profile-section-icon"><ProfileIcon name="tag"/></span><div><b>Визначте теги</b><p>Аналіз анкети або CV допоможе підготувати профіль до пошуку вакансій.</p></div></li>
          </ol>
        </section>
      </aside>
    </div>
  </section>;
}

type Block={key:string;title:string;fields:[string,string,string?][]};
const blocks:Block[]=[
  {key:"educations",title:"Освіта",fields:[["institution_name","Навчальний заклад"],["specialty_or_qualification","Спеціальність"],["start_year","Рік початку","number"],["end_year","Рік завершення","number"],["description","Опис","textarea"]]},
  {key:"experiences",title:"Досвід",fields:[["raw_job_title","Посада *"],["company_name","Компанія"],["start_date","Початок","date"],["end_date","Завершення","date"],["responsibilities_description","Обов’язки","textarea"],["achievements","Досягнення","textarea"],["tools_used","Інструменти"]]},
  {key:"credentials",title:"Сертифікати",fields:[["title","Назва *"],["provider","Організація"],["issue_date","Дата видачі","date"],["expiry_date","Діє до","date"],["description","Опис","textarea"]]},
  {key:"skills",title:"Навички",fields:[["raw_input","Навичка *"],["years_used","Років досвіду","number"],["notes","Нотатки","textarea"]]},
  {key:"languages",title:"Мови",fields:[["language","Мова *"],["level","Рівень","level"],["certificate","Сертифікат"]]},
  {key:"activities",title:"Активності",fields:[["title","Назва *"],["organization","Організація"],["role","Роль"],["description","Опис","textarea"]]},
];
function FactsEditor({person,block,onSaved}:{person:Person;block:Block;onSaved:(p:Person)=>void}){
  const [editing,setEditing]=useState<string|null>(null),[values,setValues]=useState<Record<string,string>>({}),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const rows=(person as unknown as Record<string,FactRow[]>)[block.key]||[];
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");const payload:Record<string,unknown>={};for(const [key,,type]of block.fields)if(key in values)payload[key]=values[key]===""?null:type==="number"?Number(values[key]):values[key];try{onSaved(await adminRequest<Person>(`/admin/persons/${person.id}/${block.key}${editing&&editing!=="new"?`/${editing}`:""}`,{method:editing==="new"?"POST":"PATCH",body:JSON.stringify(payload)}));setEditing(null)}catch(e){setError(errText(e))}finally{setBusy(false)}};
  return <div className="panel console-editor"><div className="page-title compact"><h2>{block.title}</h2><button className="button secondary" onClick={()=>{setEditing("new");setValues({});setError("")}}>+ Додати запис</button></div><Notice error={error}/>{block.key==="skills"&&<PersonTags person={person}/>}{editing&&<form className="form console-fact-form" onSubmit={submit}><div className="form-grid">{block.fields.map(([key,label,type])=><label key={key}><span>{label}</span>{type==="textarea"?<textarea value={values[key]||""} onChange={e=>setValues({...values,[key]:e.target.value})}/>:type==="level"?<select value={values[key]||"unknown"} onChange={e=>setValues({...values,[key]:e.target.value})}>{["unknown","native","a1","a2","b1","b2","c1","c2"].map(x=><option key={x} value={x}>{x==="unknown"?"Не вказано":x==="native"?"Рідна":x.toUpperCase()}</option>)}</select>:<input type={type||"text"} required={label.includes("*")} value={values[key]||""} onChange={e=>setValues({...values,[key]:e.target.value})}/>}</label>)}</div><div className="console-form-actions"><button type="button" className="button secondary" onClick={()=>setEditing(null)}>Скасувати</button><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти запис"}</button></div></form>}<div className="console-facts">{rows.map(row=><article key={row.id}><div>{block.fields.filter(([key])=>row[key]!=null&&row[key]!=="").map(([key,label])=><div key={key}><small>{label.replace(" *","")}</small><p>{String(row[key])}</p></div>)}{block.key==="skills"&&row.evidence_state==="system_detected"&&<small>Знайдено ШІ · потребує підтвердження{row.evidence_excerpt?` · «${String(row.evidence_excerpt)}»`:""}</small>}</div><button className="button secondary small" onClick={()=>{setEditing(row.id);setValues(Object.fromEntries(block.fields.map(([key])=>[key,String(row[key]??"")])));setError("")}}>Редагувати</button></article>)}</div>{!rows.length&&!editing&&<div className="console-empty"><p>Записів ще немає. Додайте інформацію зі слів клієнта.</p></div>}</div>
}

function AccessPanel({personId}:{personId:string}){
  const [staff,setStaff]=useState<Staff[]>([]),[grants,setGrants]=useState<Staff[]>([]),[error,setError]=useState(""),[busy,setBusy]=useState(false),[selected,setSelected]=useState("");
  const load=async()=>{const [s,g]=await Promise.all([adminRequest<Staff[]>("/admin/staff"),adminRequest<Staff[]>(`/admin/persons/${personId}/access`)]);setStaff(s);setGrants(g)};
  useEffect(()=>{load().catch(e=>setError(errText(e)))},[personId]);
  const change=async(id:number,method:string)=>{setBusy(true);setError("");try{await adminRequest(`/admin/persons/${personId}/access/${id}`,{method});await load();setSelected("")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  return <section className="panel console-editor"><h2>Доступ до клієнта</h2><p className="muted">Адміністратори бачать усіх клієнтів. Надайте менеджеру доступ до перегляду та редагування цього профілю.</p><Notice error={error}/><div className="console-filters"><select aria-label="Менеджер" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Оберіть менеджера</option>{staff.filter(s=>s.role==="manager"&&s.is_active&&!grants.some(g=>g.id===s.id)).map(s=><option key={s.id} value={s.id}>{s.full_name||s.email}</option>)}</select><button disabled={!selected||busy} className="button" onClick={()=>void change(Number(selected),"PUT")}>Надати доступ</button></div>{grants.map(g=><div className="console-access-row" key={g.id}><div><b>{g.full_name||g.email}</b><small>{g.email} · {g.is_creator?"Створив клієнта":"Доступ надано"}</small></div>{!g.is_creator&&<button className="button secondary small" disabled={busy} onClick={()=>void change(g.id,"DELETE")}>Забрати доступ</button>}</div>)}</section>
}

function MobilityEditor({person,onSaved}:{person:Person;onSaved:(p:Person)=>void}){
  const [values,setValues]=useState(person.mobility),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const save=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");try{const keys=["has_driver_license","driver_license_categories","has_car","willing_to_relocate","work_format","work_geography"];onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`,{method:"PATCH",body:JSON.stringify(Object.fromEntries(keys.filter(k=>k in values).map(k=>[k,values[k]])))}))}catch(e){setError(errText(e))}finally{setBusy(false)}};
  return <form className="panel form console-editor" onSubmit={save}><h2>Формат роботи та мобільність</h2><div className="form-grid">{[["has_driver_license","Посвідчення водія"],["has_car","Власне авто"],["willing_to_relocate","Готовність до переїзду"]].map(([key,label])=><label key={key}><span>{label}</span><select value={String(values[key]||"unknown")} onChange={e=>setValues({...values,[key]:e.target.value})}><option value="unknown">Не вказано</option><option value="yes">Так</option><option value="no">Ні</option></select></label>)}<label><span>Категорії водійського посвідчення</span><input value={String(values.driver_license_categories||"")} onChange={e=>setValues({...values,driver_license_categories:e.target.value})}/></label><label><span>Формат роботи</span><select value={String(values.work_format||"unknown")} onChange={e=>setValues({...values,work_format:e.target.value})}>{[["unknown","Не вказано"],["onsite","На місці / в офісі"],["remote","Віддалено"],["hybrid","Гібрид"],["any","Будь-який"]].map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div><Notice error={error}/><div className="console-form-actions"><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти зміни"}</button></div></form>
}

type CvAnalysisResult = {
  cached:boolean;
  input_tokens:number;
  output_tokens:number;
  detected_tags:{id:string;name:string}[];
  inferred_tags:{id:string;name:string}[];
  person_tags:{skill_id:string;name:string;skill_type?:string|null}[];
  new_tags_count:number;
  tagging:{minimum:number;total:number;complete:boolean;career:{id:string;name:string}|null};
  proposal:{
    primary_role:string;alternative_roles:string[];
    skills:{name:string;evidence:string;canonical_skill_id:string|null}[];
    search_queries:string[];work_format:string;employment_type:string;
    languages:string[];summary:string;
  };
};

function DocumentsPanel({person,onSaved}:{person:Person;onSaved:(p:Person)=>void}){
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[downloading,setDownloading]=useState<string|null>(null);
  const upload=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();const form=e.currentTarget,input=form.elements.namedItem("cv") as HTMLInputElement;
    const file=input.files?.[0];if(!file)return;
    setError("");setBusy(true);
    try{
      const body=new FormData();body.append("file",file);
      onSaved(await adminRequest<Person>(`/admin/persons/${person.id}/documents/cv`,{method:"POST",body}));
      form.reset();
    }catch(e){setError(errText(e))}finally{setBusy(false)}
  };
  const download=async(row:FactRow)=>{
    setError("");setDownloading(row.id);
    try{
      const blob=await adminDownload(`/admin/persons/${person.id}/documents/${row.id}/download`);
      const url=URL.createObjectURL(blob),link=document.createElement("a");
      link.href=url;link.download=String(row.filename||"cv");document.body.appendChild(link);link.click();link.remove();
      window.setTimeout(()=>URL.revokeObjectURL(url),60000);
    }catch(e){setError(errText(e))}finally{setDownloading(null)}
  };
  return <div className="panel console-editor">
    <h2>Документи клієнта</h2>
    <p className="muted">Прикріпіть CV у форматі PDF, DOC або DOCX до 15 МБ. Файл зберігатиметься приватно в Dropbox. Для AI-аналізу потрібен PDF із текстом або DOCX.</p>
    <Notice error={error}/>
    <form className="form" onSubmit={upload}><label><span>Файл CV</span><input name="cv" type="file" accept=".pdf,.doc,.docx" required/></label><div className="console-form-actions"><button className="button" disabled={busy}>{busy?"Завантажуємо…":"Прикріпити CV"}</button></div></form>
    <div className="console-facts">{person.documents.map(row=><div className="console-access-row" key={row.id}><b>{String(row.filename||"Документ")}</b><button className="button secondary small" disabled={downloading===row.id} onClick={()=>void download(row)}>{downloading===row.id?"Готуємо…":"Завантажити"}</button></div>)}</div>
    {!person.documents.length&&<p className="muted">Збережених документів поки немає.</p>}
  </div>;
}

function AnalysisPanel({person,onSaved}:{person:Person;onSaved:(p:Person)=>void}){
  const [source,setSource]=useState<"cv"|"questionnaire"|null>(null);
  const [selectedCv,setSelectedCv]=useState("");
  const [permissionConfirmed,setPermissionConfirmed]=useState(false);
  const [result,setResult]=useState<CvAnalysisResult|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const cvs=person.documents.filter(row=>row.document_type==="cv"&&!String(row.filename||"").toLowerCase().endsWith(".doc"));
  const choose=(value:"cv"|"questionnaire")=>{setSource(value);setResult(null);setError("")};
  const run=async()=>{
    if(!source||!permissionConfirmed)return;
    const documentId=cvs.some(row=>row.id===selectedCv)?selectedCv:cvs[0]?.id;
    if(source==="cv"&&!documentId){setError("Спочатку прикріпіть PDF або DOCX у вкладці «Документи»");return}
    setBusy(true);setError("");setResult(null);
    try{
      const path=source==="cv"?`/admin/persons/${person.id}/documents/${documentId}/analyze`:`/admin/persons/${person.id}/analysis/questionnaire`;
      const analysis=await adminRequest<CvAnalysisResult>(path,{method:"POST",body:JSON.stringify({permission_confirmed:true})});
      setResult(analysis);
      onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`));
    }catch(e){setError(errText(e))}finally{setBusy(false)}
  };
  return <div className="panel console-editor">
    <h2>Проаналізувати клієнта</h2>
    <p className="muted">Оберіть джерело даних для ШІ. Система збере щонайменше 5 канонічних тегів із довідника: спочатку підтверджені текстом навички, а якщо їх недостатньо — найважливіші вимоги найближчої професії.</p>
    <div className="profile-analysis-choices"><button type="button" className={source==="questionnaire"?"selected":""} aria-pressed={source==="questionnaire"} disabled={busy} onClick={()=>choose("questionnaire")}><ProfileIcon name="user"/><b>Анкета</b><span>Збережений досвід, освіта й навички</span></button><button type="button" className={source==="cv"?"selected":""} aria-pressed={source==="cv"} disabled={busy} onClick={()=>choose("cv")}><ProfileIcon name="file"/><b>Резюме / CV</b><span>Один із прикріплених документів</span></button></div>
    {source==="cv"&&(cvs.length?<label><span>Прикріплений CV</span><select value={cvs.some(row=>row.id===selectedCv)?selectedCv:cvs[0].id} onChange={e=>setSelectedCv(e.target.value)}>{cvs.map(row=><option key={row.id} value={row.id}>{String(row.filename||"CV")}</option>)}</select></label>:<p className="muted">Немає PDF або DOCX. Прикріпіть файл у вкладці «Документи».</p>)}
    {source==="questionnaire"&&<p className="muted">Буде використано збережені дані анкети: досвід, освіту, навички, мови та побажання щодо роботи. Контакти, дата народження й нотатки працівника не надсилаються.</p>}
    {source&&<><p className="muted">Дані вибраного джерела надсилаються сервісу OpenAI для аналізу.</p><label className="profile-analysis-consent"><input type="checkbox" checked={permissionConfirmed} onChange={e=>setPermissionConfirmed(e.target.checked)}/> Підтверджую, що маю дозвіл на AI-обробку даних клієнта.</label><div className="console-form-actions"><button className="button" disabled={busy||!permissionConfirmed||(source==="cv"&&!cvs.length)} onClick={()=>void run()}>{busy?"Аналізуємо…":"Надіслати на аналіз"}</button></div></>}
    <Notice error={error}/>
    {result&&<div className="console-fact-form"><h3>Результат аналізу {result.cached&&<small>· із кешу</small>}</h3><p><b>Основна посада:</b> {result.proposal.primary_role||"Не визначено"}</p>{result.proposal.alternative_roles.length>0&&<p><b>Суміжні посади:</b> {result.proposal.alternative_roles.join(", ")}</p>}{result.person_tags.length>0&&<p><b>Теги людини ({result.tagging.total}):</b> {result.person_tags.map(t=>t.name).join(", ")} · нових: {result.new_tags_count}.</p>}{result.inferred_tags.length>0&&<p><b>Добрано з вимог професії{result.tagging.career?` «${result.tagging.career.name}»`:""}:</b> {result.inferred_tags.map(t=>t.name).join(", ")}</p>}{!result.tagging.complete&&<p className="error"><b>Недостатньо тегів:</b> знайдено {result.tagging.total} із мінімальних {result.tagging.minimum}. Перевірте назву професії та наповнення її вимог у базі.</p>}{result.proposal.skills.some(s=>!s.canonical_skill_id)&&<p><b>Потребують звірки:</b> {result.proposal.skills.filter(s=>!s.canonical_skill_id).map(s=>s.name).join(", ")}</p>}{result.proposal.search_queries.length>0&&<p><b>Запити для пошуку:</b> {result.proposal.search_queries.join("; ")}</p>}{result.proposal.work_format&&<p><b>Формат:</b> {result.proposal.work_format}</p>}{result.proposal.summary&&<p>{result.proposal.summary}</p>}<small>Усі теги взяті з канонічного довідника. Теги, добрані з вимог професії, є припущеннями та потребують перевірки. Токени: {result.input_tokens} вхідних / {result.output_tokens} вихідних.</small></div>}
  </div>;
}

function ProfileIcon({name}:{name:"spark"|"user"|"pin"|"file"|"tag"|"arrow"}){
  const paths={
    spark:"m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z",
    user:"M20 21v-2a7 7 0 0 0-14 0v2M13 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
    pin:"M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0ZM12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
    file:"M14 2H5v20h14V7l-5-5ZM14 2v6h5M8 12h8M8 16h6",
    tag:"M3 3h8l10 10-8 8L3 11V3ZM7 7h.01",
    arrow:"M5 12h14m-5-5 5 5-5 5",
  };
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

function PersonTags({person}:{person:Person}){
  const tags=person.tags||[];
  return <section className="console-person-tags">
    <div className="profile-card-heading"><span className="profile-section-icon"><ProfileIcon name="tag"/></span><h3>Теги для пошуку</h3><span className="profile-count">{tags.length}</span></div>
    <p>Навички та орієнтири для підбору вакансій.</p>
    {tags.length?<div className="console-tag-list">{tags.map(tag=><span key={tag.skill_id}>{tag.name}</span>)}</div>:<p className="console-no-tags">Проаналізуйте анкету або CV, щоб додати теги до профілю.</p>}
    {!!tags.length&&<div className="profile-tag-footnote">Добрані за професією теги потребують перевірки.</div>}
  </section>;
}

function AnalysisModal({person,onSaved,onClose}:{person:Person;onSaved:(p:Person)=>void;onClose:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const element=dialog.current;element?.showModal();return()=>element?.close()},[]);
  return <dialog ref={dialog} className="console-modal profile-analysis-modal" aria-labelledby="analysis-title" onCancel={onClose} onClick={event=>{if(event.target===event.currentTarget){const rect=event.currentTarget.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)onClose()}}}>
    <div className="console-modal-head"><div><span className="console-kicker">ПРОФІЛЬ КЛІЄНТА</span><h2 id="analysis-title">Аналіз анкети або CV</h2></div><button type="button" className="console-modal-close" onClick={onClose} aria-label="Закрити вікно аналізу">×</button></div>
    <AnalysisPanel key={person.id} person={person} onSaved={onSaved}/>
  </dialog>;
}

function ProfileFold({title,hint,children}:{title:string;hint:string;children:ReactNode}){
  return <details className="profile-fold"><summary><span><b>{title}</b><small>{hint}</small></span><span className="profile-fold-toggle" aria-hidden="true">+</span></summary><div className="profile-fold-body">{children}</div></details>;
}

type EmploymentStage={id:string;name:string;is_active:boolean};
function SuperAdminAiRecommendations({personId}:{personId:string}){
  const [data,setData]=useState<SuperAdminAiRecommendation|null>(null),[loading,setLoading]=useState(true),[generating,setGenerating]=useState(false),[error,setError]=useState("");
  useEffect(()=>{let active=true;setLoading(true);setError("");adminRequest<SuperAdminAiRecommendation>(`/admin/persons/${personId}/ai-recommendations`).then(value=>{if(active)setData(value)}).catch(e=>{if(active)setError(errText(e))}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[personId]);
  const generate=async()=>{setGenerating(true);setError("");try{setData(await adminRequest<SuperAdminAiRecommendation>(`/admin/persons/${personId}/ai-recommendations`,{method:"POST"}))}catch(e){setError(errText(e))}finally{setGenerating(false)}};
  const plan=data?.recommendation;
  const vacancy=data?.vacancy_search;
  const suggestedStage=workflowStages.find(([value])=>value===plan?.suggested_workflow_stage)?.[1];
  return <section className="panel superadmin-ai-card" aria-label="AI-рекомендації для суперадміністратора">
    <div className="superadmin-ai-head"><div className="profile-card-heading"><span className="profile-section-icon"><ProfileIcon name="spark"/></span><div><span className="ai-private-badge">ЛИШЕ ДЛЯ СУПЕРАДМІНА</span><h2>AI-рекомендації</h2><p>Короткий план дій на основі даних картки клієнта</p></div></div></div>
    <Notice error={error}/>
    {loading?<p className="ai-recommendation-empty">Завантажуємо збережені рекомендації…</p>:!plan?<div className="ai-recommendation-empty"><b>Рекомендацій ще немає</b><span>ШІ перегляне професійні дані, запит, поточний етап і складе короткий покроковий план.</span></div>:<div className="ai-recommendation-content">
      {data?.is_outdated&&<div className="ai-outdated">Картку змінено після останнього аналізу. Оновіть рекомендації.</div>}
      <p className="ai-summary">{plan.summary}</p>
      <div className="ai-recommendation-section ai-vacancy-search"><div className="ai-section-title"><h3>Пошук вакансій за тегами</h3>{vacancy?.location&&<span>{vacancy.location}</span>}</div>
        {vacancy?.professions.length?<><div className="ai-career-matches">{vacancy.professions.map(career=><article key={career.career_id}><div><b>{career.name}</b><small>{career.match_count} {career.match_count===1?"тег-збіг":"теги-збіги"}</small></div><div>{career.matched_tags.map(tag=><span key={tag}>{tag}</span>)}</div></article>)}</div><div className="ai-search-queries"><b>Готові пошукові запити</b>{vacancy.queries.map(query=><code key={query}>{query}</code>)}</div></>:<p className="ai-no-careers">За поточними тегами ще немає достатнього збігу з професіями у довіднику. Перевірте теги або доповніть профіль.</p>}
      </div>
      <div className="ai-recommendation-section"><h3>Що робити далі</h3><ol>{plan.steps.map((step,index)=><li key={`${step.title}-${index}`}><span>{index+1}</span><div><b>{step.title}</b><p>{step.action}</p></div></li>)}</ol></div>
      {!!plan.platform_offers.length&&<div className="ai-recommendation-section"><h3>Що може запропонувати Yellow Hub</h3><div className="ai-offer-list">{plan.platform_offers.map(offer=><span key={offer}>{offer}</span>)}</div></div>}
      {!!plan.questions_to_clarify.length&&<div className="ai-recommendation-section ai-clarify"><h3>Що уточнити</h3><ul>{plan.questions_to_clarify.map(question=><li key={question}>{question}</li>)}</ul></div>}
      <div className="ai-recommendation-meta"><span>Рекомендований етап: <b>{suggestedStage||plan.suggested_workflow_stage}</b></span>{data.generated_at&&<span>Сформовано {new Date(data.generated_at).toLocaleString("uk-UA",{day:"2-digit",month:"long",year:"numeric",hour:"2-digit",minute:"2-digit"})}</span>}</div>
    </div>}
    <div className="superadmin-ai-actions"><small>Рекомендації не змінюють картку автоматично — рішення залишається за суперадміністратором.</small><button type="button" className="button" disabled={loading||generating} onClick={()=>void generate()}>{generating?"Формуємо…":plan?"Оновити AI-рекомендації":"Сформувати AI-рекомендації"}</button></div>
  </section>;
}
function EmploymentPanel({person,role,onSaved}:{person:Person;role:string|null;onSaved:(person:Person)=>void}){
  const current=person.employment||{};
  const [stages,setStages]=useState<EmploymentStage[]>([]),[stageId,setStageId]=useState(current.stage_id||""),[offer,setOffer]=useState(current.offer_text||"");
  const [newName,setNewName]=useState(""),[editingId,setEditingId]=useState<string|null>(null),[editingName,setEditingName]=useState("");
  const [error,setError]=useState(""),[success,setSuccess]=useState(""),[busy,setBusy]=useState(false);
  const canManage=role==="admin"||role==="super_admin";
  const load=async()=>setStages(await adminRequest<EmploymentStage[]>("/admin/employment-stages"));
  useEffect(()=>{load().catch(e=>setError(errText(e)))},[]);
  useEffect(()=>{setStageId(current.stage_id||"");setOffer(current.offer_text||"")},[current.stage_id,current.offer_text]);
  const save=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");setSuccess("");try{const payload:Record<string,unknown>={offer_text:offer};if(stageId!==(current.stage_id||""))payload.stage_id=stageId||null;onSaved(await adminRequest<Person>(`/admin/persons/${person.id}/employment`,{method:"PATCH",body:JSON.stringify(payload)}));setSuccess("Результат і рекомендації збережено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const createStage=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");setSuccess("");try{const created=await adminRequest<EmploymentStage>("/admin/employment-stages",{method:"POST",body:JSON.stringify({name:newName})});setNewName("");await load();setStageId(created.id);setSuccess("Новий етап додано до списку")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const renameStage=async(id:string)=>{setBusy(true);setError("");setSuccess("");try{await adminRequest(`/admin/employment-stages/${id}`,{method:"PATCH",body:JSON.stringify({name:editingName})});setEditingId(null);await load();if(current.stage_id===id)onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`));setSuccess("Назву етапу оновлено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const removeStage=async(stage:EmploymentStage)=>{if(!window.confirm(`Прибрати етап «${stage.name}» зі списку?`))return;setBusy(true);setError("");setSuccess("");try{const result=await adminRequest<{archived:boolean}>(`/admin/employment-stages/${stage.id}`,{method:"DELETE"});if(stageId===stage.id)setStageId(current.stage_id||"");await load();if(current.stage_id===stage.id)onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`));setSuccess(result.archived?"Етап прибрано з вибору. У старих картках його збережено.":"Етап видалено") }catch(e){setError(errText(e))}finally{setBusy(false)}};
  const selectable=stages.filter(stage=>stage.is_active||stage.id===current.stage_id);
  if(current.stage_id&&current.stage_name&&!selectable.some(stage=>stage.id===current.stage_id))selectable.push({id:current.stage_id,name:current.stage_name,is_active:false});
  return <div className="employment-layout">
    <div className="employment-main-stack"><form className="panel form employment-card" onSubmit={save}>
      <div className="profile-card-heading"><span className="profile-section-icon"><ProfileIcon name="spark"/></span><div><h2>Результат і рекомендації</h2><p>Поточний етап та рекомендації команди Yellow Hub для клієнта</p></div></div>
      <label><span>Етап працевлаштування</span><select aria-label="Етап працевлаштування" value={stageId} disabled={busy} onChange={e=>setStageId(e.target.value)}><option value="">Не вказано</option>{selectable.map(stage=><option key={stage.id} value={stage.id} disabled={!stage.is_active}>{stage.name}{!stage.is_active?" (прибрано зі списку)":""}</option>)}</select></label>
      {!selectable.length&&<p className="employment-empty">{canManage?"Спочатку додайте хоча б один етап у правому блоці.":"Адміністратор ще не створив варіанти етапів."}</p>}
      <label><span>Рекомендації від платформи</span><textarea aria-label="Рекомендації від платформи" rows={8} maxLength={5000} disabled={busy} value={offer} placeholder="Наприклад: розглянути вакансії адміністратора з денним графіком; оновити резюме; пройти курс Excel; підготуватися до співбесіди…" onChange={e=>setOffer(e.target.value)}/><small className="field-counter">{offer.length} / 5000</small></label>
      <Notice error={error}/>{success&&<div className="success" role="status">{success}</div>}
      <div className="console-form-actions"><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти"}</button></div>
    </form>{role==="super_admin"&&<SuperAdminAiRecommendations personId={person.id}/>}</div>
    <aside className="employment-stage-card">
      <span className="console-kicker">СПІЛЬНИЙ ДОВІДНИК</span><h3>Етапи працевлаштування</h3>
      <p>{canManage?"Створені тут варіанти зможуть вибирати всі менеджери.":"Виберіть короткий етап зі списку, налаштованого адміністратором."}</p>
      {canManage&&<form className="employment-stage-create" onSubmit={createStage}><label><span>Новий етап</span><input aria-label="Новий етап" maxLength={80} required value={newName} placeholder="Наприклад, проходить співбесіду" onChange={e=>setNewName(e.target.value)}/></label><button className="button secondary" disabled={busy||!newName.trim()}>Додати</button></form>}
      <div className="employment-stage-list">{stages.map(stage=><div key={stage.id} className={!stage.is_active?"inactive":""}>{editingId===stage.id?<><input aria-label={`Нова назва для ${stage.name}`} maxLength={80} value={editingName} onChange={e=>setEditingName(e.target.value)}/><div><button type="button" className="button small" disabled={busy||!editingName.trim()} onClick={()=>void renameStage(stage.id)}>Зберегти</button><button type="button" className="button secondary small" onClick={()=>setEditingId(null)}>Скасувати</button></div></>:<><span><b>{stage.name}</b>{!stage.is_active&&<small>Прибрано зі списку</small>}</span>{canManage&&stage.is_active&&<div><button type="button" className="button secondary small" onClick={()=>{setEditingId(stage.id);setEditingName(stage.name)}}>Редагувати</button><button type="button" className="button secondary small employment-delete" onClick={()=>void removeStage(stage)}>Видалити</button></div>}</>}</div>)}</div>
    </aside>
  </div>;
}

type ClientRequestType={id:string;name:string;is_active:boolean};
function localDateTimeValue(value?:string|null){if(!value)return "";const date=new Date(value);if(Number.isNaN(date.getTime()))return "";return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16)}
function SupportPanel({person,role,staffId,onSaved}:{person:Person;role:string|null;staffId:number|null;onSaved:(person:Person)=>void}){
  const current=person.workflow||{stage:"new_request",stage_uk:"Нова заявка",closure_reason:null,closure_reason_uk:null,closure_note:null,client_requests:[],responsible:null,needs_contact:false,next_action_text:null,next_action_at:null};
  const [requestTypes,setRequestTypes]=useState<ClientRequestType[]>([]),[consultants,setConsultants]=useState<Staff[]>([]);
  const [selectedRequests,setSelectedRequests]=useState<string[]>(current.client_requests.map(item=>item.id)),[workflowStage,setWorkflowStage]=useState(current.stage||"new_request"),[responsibleId,setResponsibleId]=useState(current.responsible?.id?String(current.responsible.id):"");
  const [closureReason,setClosureReason]=useState(current.closure_reason||""),[closureNote,setClosureNote]=useState(current.closure_note||"");
  const [nextAt,setNextAt]=useState(localDateTimeValue(current.next_action_at)),[notes,setNotes]=useState(person.core.notes||"");
  const [newName,setNewName]=useState(""),[editingId,setEditingId]=useState<string|null>(null),[editingName,setEditingName]=useState("");
  const [error,setError]=useState(""),[success,setSuccess]=useState(""),[busy,setBusy]=useState(false);
  const canManage=role==="admin"||role==="super_admin";
  const load=async()=>{const [types,staff]=await Promise.all([adminRequest<ClientRequestType[]>("/admin/client-request-types"),adminRequest<Staff[]>("/admin/consultants")]);setRequestTypes(types);setConsultants(staff)};
  useEffect(()=>{load().catch(e=>setError(errText(e)))},[]);
  useEffect(()=>{setSelectedRequests(current.client_requests.map(item=>item.id));setWorkflowStage(current.stage||"new_request");setClosureReason(current.closure_reason||"");setClosureNote(current.closure_note||"");setResponsibleId(current.responsible?.id?String(current.responsible.id):"");setNextAt(localDateTimeValue(current.next_action_at));setNotes(person.core.notes||"")},[person.id,current.stage,current.closure_reason,current.closure_note,current.responsible?.id,current.next_action_at,person.core.notes]);
  const toggleRequest=(id:string)=>setSelectedRequests(values=>values.includes(id)?values.filter(value=>value!==id):[...values,id]);
  const save=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");setSuccess("");if(workflowStage==="closed"&&!closureReason){setError("Оберіть причину закриття клієнта");setBusy(false);return}if(workflowStage==="closed"&&closureReason==="other"&&!closureNote.trim()){setError("Уточніть іншу причину закриття");setBusy(false);return}try{const stageLabel=workflowStages.find(([value])=>value===workflowStage)?.[1]||workflowStage;const payload={client_request_ids:selectedRequests,workflow_stage:workflowStage,closure_reason:workflowStage==="closed"?closureReason:null,closure_note:workflowStage==="closed"?closureNote.trim()||null:null,responsible_staff_id:responsibleId?Number(responsibleId):null,next_action_text:nextAt?stageLabel:null,next_action_at:nextAt?new Date(nextAt).toISOString():null,notes:notes.trim()||null};onSaved(await adminRequest<Person>(`/admin/persons/${person.id}/workflow`,{method:"PATCH",body:JSON.stringify(payload)}));setSuccess("Супровід клієнта оновлено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const createType=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");setSuccess("");try{const created=await adminRequest<ClientRequestType>("/admin/client-request-types",{method:"POST",body:JSON.stringify({name:newName})});setNewName("");await load();setSelectedRequests(values=>[...values,created.id]);setSuccess("Новий варіант додано до довідника")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const renameType=async(id:string)=>{setBusy(true);setError("");setSuccess("");try{await adminRequest(`/admin/client-request-types/${id}`,{method:"PATCH",body:JSON.stringify({name:editingName})});setEditingId(null);await load();if(selectedRequests.includes(id))onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`));setSuccess("Назву запиту оновлено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const removeType=async(item:ClientRequestType)=>{if(!window.confirm(`Прибрати «${item.name}» зі списку запитів?`))return;setBusy(true);setError("");setSuccess("");try{const result=await adminRequest<{archived:boolean}>(`/admin/client-request-types/${item.id}`,{method:"DELETE"});if(!result.archived)setSelectedRequests(values=>values.filter(value=>value!==item.id));await load();if(selectedRequests.includes(item.id))onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`));setSuccess(result.archived?"Варіант прибрано з вибору. У старих картках його збережено.":"Варіант видалено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const selectable=[...requestTypes.filter(item=>item.is_active)];for(const item of current.client_requests)if(!selectable.some(option=>option.id===item.id))selectable.push(item);
  const consultantOptions=[...consultants];if(current.responsible&&!consultantOptions.some(member=>member.id===current.responsible!.id))consultantOptions.push(current.responsible as Staff);
  const managerCanTake=role==="manager"&&staffId&&responsibleId!==String(staffId);
  return <div className="support-layout">
    <form className="panel form support-card" onSubmit={save}>
      <div className="profile-card-heading"><span className="profile-section-icon"><ProfileIcon name="user"/></span><div><h2>Супровід клієнта</h2><p>Запит людини, відповідальний консультант і конкретний наступний крок</p></div></div>
      <section className="support-form-section"><div className="support-section-heading"><div><span className="support-step">01</span><h3>Запит клієнта</h3></div><small>Можна вибрати декілька · обрано {selectedRequests.length}</small></div>
        {selectable.length?<div className="request-choice-grid">{selectable.map(item=><label key={item.id} className={selectedRequests.includes(item.id)?"selected":""}><input type="checkbox" checked={selectedRequests.includes(item.id)} disabled={busy||!item.is_active} onChange={()=>toggleRequest(item.id)}/><span>{item.name}{!item.is_active&&<small>Більше не використовується</small>}</span></label>)}</div>:<p className="muted">{canManage?"Додайте перший варіант у довіднику праворуч.":"Адміністратор ще не налаштував варіанти запиту."}</p>}
      </section>
      <section className="support-form-section"><div className="support-section-heading"><div><span className="support-step">02</span><h3>Хто і коли діє далі</h3></div></div>
        <div className="support-owner-grid support-owner-single"><label><span>Відповідальний консультант</span>{canManage?<select value={responsibleId} disabled={busy} onChange={e=>setResponsibleId(e.target.value)}><option value="">Не призначено</option>{consultantOptions.map(member=><option key={member.id} value={member.id} disabled={!member.is_active}>{member.full_name||member.email} · {roles[member.role]||member.role}{!member.is_active?" (вимкнений)":""}</option>)}</select>:<div className="responsible-readonly"><b>{current.responsible?.full_name||current.responsible?.email||"Не призначено"}</b>{managerCanTake&&<button type="button" className="button secondary small" onClick={()=>setResponsibleId(String(staffId))}>Взяти на себе</button>}{responsibleId===String(staffId)&&current.responsible?.id!==staffId&&<small>Буде призначено після збереження</small>}</div>}</label></div>
        <div className="next-action-grid"><label><span>Наступна дія</span><select value={workflowStage} disabled={busy} onChange={e=>{setWorkflowStage(e.target.value);if(e.target.value!=="closed"){setClosureReason("");setClosureNote("")}}}>{workflowStages.map(([value,label],index)=><option key={value} value={value}>{index+1}. {label}</option>)}</select></label><label><span>Дата і час</span><input type="datetime-local" value={nextAt} disabled={busy} onChange={e=>setNextAt(e.target.value)}/></label></div>
        {workflowStage==="closed"&&<div className="closure-reason-grid"><label><span>Причина закриття *</span><select required value={closureReason} disabled={busy} onChange={e=>setClosureReason(e.target.value)}><option value="">Оберіть причину</option>{closureReasons.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>{closureReason==="other"&&<label><span>Уточніть причину *</span><input required maxLength={500} value={closureNote} disabled={busy} placeholder="Коротко вкажіть причину" onChange={e=>setClosureNote(e.target.value)}/></label>}</div>}
      </section>
      <section className="support-form-section"><div className="support-section-heading"><div><span className="support-step">03</span><h3>Робочі нотатки</h3></div><small>Не надсилаються на AI-аналіз</small></div><label><span>Домовленості, обмеження та важливий контекст</span><textarea rows={7} maxLength={10000} value={notes} disabled={busy} placeholder="Що важливо врахувати, про що домовилися, посилання та коментарі консультанта…" onChange={e=>setNotes(e.target.value)}/></label></section>
      <Notice error={error}/>{success&&<div className="success" role="status">{success}</div>}<div className="console-form-actions support-save"><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти супровід"}</button></div>
    </form>
    <aside className="request-type-card"><span className="console-kicker">СПІЛЬНИЙ ДОВІДНИК</span><h3>Варіанти запиту</h3><p>{canManage?"Створені тут варіанти зможуть обирати всі менеджери.":"Оберіть один або декілька варіантів, налаштованих адміністратором."}</p>
      {canManage&&<form className="employment-stage-create" onSubmit={createType}><label><span>Новий варіант</span><input maxLength={100} required value={newName} placeholder="Наприклад, допомога з резюме" onChange={e=>setNewName(e.target.value)}/></label><button className="button secondary" disabled={busy||!newName.trim()}>Додати</button></form>}
      <div className="employment-stage-list">{requestTypes.map(item=><div key={item.id} className={!item.is_active?"inactive":""}>{editingId===item.id?<><input maxLength={100} value={editingName} onChange={e=>setEditingName(e.target.value)}/><div><button type="button" className="button small" disabled={busy||!editingName.trim()} onClick={()=>void renameType(item.id)}>Зберегти</button><button type="button" className="button secondary small" onClick={()=>setEditingId(null)}>Скасувати</button></div></>:<><span><b>{item.name}</b>{!item.is_active&&<small>Прибрано зі списку</small>}</span>{canManage&&item.is_active&&<div><button type="button" className="button secondary small" onClick={()=>{setEditingId(item.id);setEditingName(item.name)}}>Редагувати</button><button type="button" className="button secondary small employment-delete" onClick={()=>void removeType(item)}>Видалити</button></div>}</>}</div>)}</div>
    </aside>
  </div>;
}

function QuickWorkflowCard({person,role,staffId,onSaved}:{person:Person;role:string|null;staffId:number|null;onSaved:(person:Person)=>void}){
  const current=person.workflow||{stage:"new_request",stage_uk:"Нова заявка",closure_reason:null,closure_note:null,responsible:null,next_action_at:null};
  const canManage=role==="admin"||role==="super_admin";
  const [consultants,setConsultants]=useState<Staff[]>([]),[workflowStage,setWorkflowStage]=useState(current.stage||"new_request"),[responsibleId,setResponsibleId]=useState(current.responsible?.id?String(current.responsible.id):"");
  const [closureReason,setClosureReason]=useState(current.closure_reason||""),[closureNote,setClosureNote]=useState(current.closure_note||""),[nextAt,setNextAt]=useState(localDateTimeValue(current.next_action_at));
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{if(canManage)adminRequest<Staff[]>("/admin/consultants").then(setConsultants).catch(e=>setError(errText(e)))},[canManage]);
  useEffect(()=>{setWorkflowStage(current.stage||"new_request");setResponsibleId(current.responsible?.id?String(current.responsible.id):"");setClosureReason(current.closure_reason||"");setClosureNote(current.closure_note||"");setNextAt(localDateTimeValue(current.next_action_at))},[person.id,current.stage,current.responsible?.id,current.closure_reason,current.closure_note,current.next_action_at]);
  const consultantOptions=[...consultants];if(current.responsible&&!consultantOptions.some(member=>member.id===current.responsible!.id))consultantOptions.push(current.responsible as Staff);
  const managerCanTake=role==="manager"&&staffId&&responsibleId!==String(staffId);
  const save=async(e:FormEvent)=>{e.preventDefault();if(busy)return;setError("");if(workflowStage==="closed"&&!closureReason){setError("Оберіть причину закриття клієнта");return}if(workflowStage==="closed"&&closureReason==="other"&&!closureNote.trim()){setError("Уточніть іншу причину закриття");return}setBusy(true);try{const stageLabel=workflowStages.find(([value])=>value===workflowStage)?.[1]||workflowStage;onSaved(await adminRequest<Person>(`/admin/persons/${person.id}/workflow`,{method:"PATCH",body:JSON.stringify({workflow_stage:workflowStage,closure_reason:workflowStage==="closed"?closureReason:null,closure_note:workflowStage==="closed"?closureNote.trim()||null:null,responsible_staff_id:responsibleId?Number(responsibleId):null,next_action_text:nextAt?stageLabel:null,next_action_at:nextAt?new Date(nextAt).toISOString():null})}))}catch(e){setError(errText(e))}finally{setBusy(false)}};
  return <form className="profile-section-surface profile-workflow-quick-card" onSubmit={save}>
    <div className="profile-card-heading"><span className="profile-step-number">01</span><div><h2>Хто і коли діє далі</h2><p>Відповідальний консультант, наступний етап і запланована дата</p></div><span className="profile-workflow-stage">{current.stage_uk||"Нова заявка"}</span></div>
    <div className="support-owner-grid support-owner-single"><label><span>Відповідальний консультант</span>{canManage?<select value={responsibleId} disabled={busy} onChange={e=>setResponsibleId(e.target.value)}><option value="">Не призначено</option>{consultantOptions.map(member=><option key={member.id} value={member.id} disabled={!member.is_active}>{member.full_name||member.email} · {roles[member.role]||member.role}{!member.is_active?" (вимкнений)":""}</option>)}</select>:<div className="responsible-readonly"><b>{current.responsible?.full_name||current.responsible?.email||"Не призначено"}</b>{managerCanTake&&<button type="button" className="button secondary small" onClick={()=>setResponsibleId(String(staffId))}>Взяти на себе</button>}{responsibleId===String(staffId)&&current.responsible?.id!==staffId&&<small>Буде призначено після збереження</small>}</div>}</label></div>
    <div className="next-action-grid"><label><span>Наступна дія</span><select value={workflowStage} disabled={busy} onChange={e=>{setWorkflowStage(e.target.value);if(e.target.value!=="closed"){setClosureReason("");setClosureNote("")}}}>{workflowStages.map(([value,label],index)=><option key={value} value={value}>{index+1}. {label}</option>)}</select></label><label><span>Дата і час</span><input type="datetime-local" value={nextAt} disabled={busy} onChange={e=>setNextAt(e.target.value)}/></label></div>
    {workflowStage==="closed"&&<div className="closure-reason-grid"><label><span>Причина закриття *</span><select required value={closureReason} disabled={busy} onChange={e=>setClosureReason(e.target.value)}><option value="">Оберіть причину</option>{closureReasons.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>{closureReason==="other"&&<label><span>Уточніть причину *</span><input required maxLength={500} value={closureNote} disabled={busy} placeholder="Коротко вкажіть причину" onChange={e=>setClosureNote(e.target.value)}/></label>}</div>}
    <Notice error={error}/><div className="quick-workflow-actions"><small>Зміни також відобразяться у вкладці «Супровід».</small><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти"}</button></div>
  </form>;
}

const profileGroups = [
  {title:"Освіта та кваліфікація",keys:["educations","credentials"],hint:"Спеціальність, навчальні заклади та сертифікати"},
  {title:"Досвід роботи",keys:["experiences","activities"],hint:"Місця роботи, посади та основні обов’язки"},
  {title:"Навички та мови",keys:["skills","languages"],hint:"Професійні навички та рівень володіння мовами"},
];
function profileFactSummary(row:FactRow,key:string){
  const fields:Record<string,string[]>={educations:["specialty_or_qualification","institution_name"],credentials:["title","provider"],experiences:["raw_job_title","company_name"],activities:["title","organization"],skills:["raw_input"],languages:["language","level"]};
  return (fields[key]||[]).map(field=>row[field]).filter(value=>value&&value!=="unknown").join(" · ");
}

export function ConsolePerson(){
  const {id}=useParams(),auth=useAppSelector(s=>s.auth),role=auth.role;
  const [person,setPerson]=useState<Person|null>(null),[core,setCore]=useState<Partial<PersonCore>>({}),[tab,setTab]=useState("core"),[error,setError]=useState(""),[saved,setSaved]=useState(false),[busy,setBusy]=useState(false),[contactBusy,setContactBusy]=useState(false),[analysisOpen,setAnalysisOpen]=useState(false);
  const [editingContacts,setEditingContacts]=useState(false);
  const accept=(p:Person)=>{setPerson(p);setSaved(true);setError("")};
  const acceptAnalysis=(p:Person)=>{setPerson(p);setSaved(true);setError("")};
  const editCore=(value:Partial<PersonCore>)=>{setCore(value);setSaved(false)};
  useEffect(()=>{if(!saved)return;const timeout=window.setTimeout(()=>setSaved(false),4000);return()=>window.clearTimeout(timeout)},[saved]);
  useEffect(()=>{setPerson(null);setError("");setAnalysisOpen(false);setEditingContacts(false);setTab("core");adminRequest<Person>("/admin/persons/"+id).then(p=>{setPerson(p);setCore(p.core)}).catch(e=>setError(errText(e)))},[id]);
  const save=async(e:FormEvent,notesOnly=false)=>{e.preventDefault();if(busy)return;setBusy(true);setSaved(false);setError("");try{const payload=notesOnly?{notes:core.notes??null}:{...Object.fromEntries(coreFields.map(([key])=>[key,core[key as keyof PersonCore]??null])),referral_source:core.referral_source??null,referral_details:core.referral_source==="other"?core.referral_details:null};const p=await adminRequest<Person>("/admin/persons/"+id,{method:"PATCH",body:JSON.stringify(payload)});accept(p);if(notesOnly)setCore(current=>({...current,notes:p.core.notes}));else{setCore(current=>({...p.core,notes:current.notes}));setEditingContacts(false)}}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const toggleNeedsContact=async()=>{if(!person||contactBusy)return;setContactBusy(true);setSaved(false);setError("");try{accept(await adminRequest<Person>(`/admin/persons/${person.id}/workflow`,{method:"PATCH",body:JSON.stringify({needs_contact:!person.workflow?.needs_contact})}))}catch(e){setError(errText(e))}finally{setContactBusy(false)}};
  if(!person)return error?<Notice error={error}/>:<p className="loading">Відкриваємо профіль…</p>;
  const tabs=[["core","Картка клієнта"],["support","Супровід"],["employment","Результат"],["documents","Документи"]];
  const documents=person.documents||[];
  return <section className="client-profile simplified-profile">
    <div className="profile-breadcrumb"><Link className="back" to="/admin/persons"><span className="back-icon" aria-hidden="true">←</span><span>Клієнти</span></Link><span>/</span><span>Картка клієнта</span></div>
    <header className="profile-header">
      <div className="profile-identity">
        <span className="profile-avatar">{person.core.first_name?.[0]}{person.core.last_name?.[0]}</span>
        <div className="profile-heading"><div className="profile-heading-label"><span className="console-kicker">КАРТКА КЛІЄНТА</span>{person.core.status&&<span className={"status "+person.core.status}>{person.core.status_uk||personStatuses.find(([value])=>value===person.core.status)?.[1]||person.core.status}</span>}</div><h1>{person.core.first_name} {person.core.last_name}</h1><div className="profile-meta"><span><ProfileIcon name="pin"/>{person.core.city||"Місто не вказано"}</span>{person.core.phone&&<a href={"tel:"+person.core.phone.replace(/[^\d+]/g,"")}>{person.core.phone}</a>}</div></div>
      </div>
      <div className="profile-header-action"><div className="profile-header-buttons"><button className="button profile-analyze-button" type="button" onClick={()=>setAnalysisOpen(true)}><ProfileIcon name="spark"/>Проаналізувати</button><button type="button" className={`profile-contact-priority ${person.workflow?.needs_contact?"active":""}`} aria-pressed={Boolean(person.workflow?.needs_contact)} disabled={contactBusy} onClick={()=>void toggleNeedsContact()}><span className="profile-contact-check" aria-hidden="true">{person.workflow?.needs_contact?"✓":""}</span><span><b>{contactBusy?"Зберігаємо…":person.workflow?.needs_contact?"Потрібно зв’язатися":"Позначити для контакту"}</b><small>{person.workflow?.needs_contact?"У швидкому фільтрі":"Додати до швидкого фільтра"}</small></span></button></div><small className="profile-header-hint">Аналізуйте профіль або позначте наступну пріоритетну дію</small></div>
    </header>
    <div className="profile-navigation"><nav className="tabs profile-tabs" aria-label="Розділи профілю">{tabs.map(([key,label])=><button type="button" key={key} aria-current={tab===key?"page":undefined} className={tab===key?"active":""} onClick={()=>{setTab(key);setSaved(false);setError("")}}>{label}{key==="documents"&&documents.length>0&&<span className="profile-tab-count">{documents.length}</span>}</button>)}</nav>{role!=="manager"&&<button type="button" className="profile-access-button" aria-pressed={tab==="access"} onClick={()=>setTab(tab==="access"?"core":"access")}>Налаштувати доступ</button>}</div>
    <Notice error={error}/>
    <div className="profile-save-notice" role="status">{saved&&<span>✓ Зміни збережено</span>}</div>
    <div hidden={tab!=="core"}><div className="profile-overview">
      <div className="profile-main-column">
      <QuickWorkflowCard person={person} role={role} staffId={auth.staffId} onSaved={accept}/>
      <section className="panel profile-contact-card profile-contact-summary">
        <div className="profile-card-heading"><span className="profile-step-number">02</span><div><h2>Особисті дані</h2><p>Контакти та місце проживання</p></div>{!editingContacts&&<button className="profile-edit-link" type="button" onClick={()=>setEditingContacts(true)}>Редагувати</button>}</div>
        {!editingContacts?<dl className="profile-contact-values">{coreFields.filter(([key])=>!["first_name","last_name","city","region","country"].includes(key)).filter(([key])=>["phone","email"].includes(key)||person.core[key as keyof PersonCore]).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{String(person.core[key as keyof PersonCore]||"Не вказано")}</dd></div>)}<div className="profile-location-value"><dt>Місце проживання</dt><dd>{[person.core.city,person.core.region,person.core.country].filter(Boolean).join(", ")||"Не вказано"}</dd></div></dl>:<form className="form" onSubmit={save}>
        <fieldset disabled={busy}>
        <legend>Про людину</legend><CoreFields only={["first_name","last_name","date_of_birth"]} value={core} onChange={editCore}/>
        </fieldset>
        <fieldset disabled={busy}><legend>Контакти</legend><CoreFields only={["phone","email","telegram_username"]} value={core} onChange={editCore}/><DuplicateWarning phone={core.phone} email={core.email} excludeId={person.id}/></fieldset>
        <fieldset disabled={busy}><legend>Місце проживання</legend><CoreFields only={["city","region","country"]} value={core} onChange={editCore}/></fieldset>
        <fieldset disabled={busy}><legend>Знайомство з нами</legend><ReferralFields value={core} onChange={editCore}/></fieldset>
        <div className="console-form-actions profile-form-footer"><button className="button secondary" type="button" disabled={busy} onClick={()=>{setCore(current=>({...person.core,notes:current.notes}));setEditingContacts(false);setError("")}}>Скасувати</button><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти контакти"}</button></div>
      </form>}
      {!editingContacts&&<div className="profile-referral-summary"><span>Звідки дізнався про нас</span><strong>{referralLabel(person.core)}</strong></div>}
      </section>
      <section className="profile-ability-section profile-section-surface"><div className="profile-card-heading"><span className="profile-step-number">03</span><div><h2>Професійний профіль</h2><p>Освіта, досвід роботи та навички</p></div></div>
        <div className="profile-grouped-facts">{profileGroups.map(group=>{const facts=person as unknown as Record<string,FactRow[]>;const previews=group.keys.flatMap(key=>(facts[key]||[]).map(row=>profileFactSummary(row,key))).filter(Boolean);return <ProfileFold key={group.title} title={group.title} hint={previews.length?previews.slice(0,2).join(" / "):group.hint}><div className="profile-related-editors">{group.keys.map(key=><FactsEditor key={key} person={person} block={blocks.find(block=>block.key===key)!} onSaved={accept}/>)}</div></ProfileFold>})}</div>
      </section>
      <section className="profile-section-surface"><div className="profile-card-heading"><span className="profile-step-number">04</span><div><h2>Яка робота підходить</h2><p>Практичні умови для підбору вакансій</p></div></div><ProfileFold title="Умови роботи та мобільність" hint="Формат роботи, готовність до переїзду, права й авто"><MobilityEditor person={person} onSaved={accept}/></ProfileFold></section>
      </div>
      <aside className="profile-sidebar">
        <section className="profile-result-card"><span className="console-kicker">ПОТОЧНИЙ РЕЗУЛЬТАТ</span><h3>{person.employment?.stage_name||"Етап не вказано"}</h3><p className={person.employment?.offer_text?"profile-note-preview":""}>{person.employment?.offer_text||"Додайте етап працевлаштування та рекомендації від платформи."}</p><button type="button" className="profile-text-action" onClick={()=>setTab("employment")}>{person.employment?.stage_id||person.employment?.offer_text?"Відкрити результат":"Додати результат"}<ProfileIcon name="arrow"/></button></section>
        <section className="profile-followup-card"><span className="console-kicker">РОБОТА З КЛІЄНТОМ</span><span className="profile-workflow-stage">{person.workflow?.stage_uk||"Нова заявка"}{person.workflow?.stage==="closed"&&person.workflow.closure_reason_uk?` · ${person.workflow.closure_reason_uk}`:""}</span><h3>{person.workflow?.client_requests.length?person.workflow.client_requests.map(item=>item.name).join(" · "):"Запит ще не визначено"}</h3><p>{person.workflow?.responsible?<><b>{person.workflow.responsible.full_name||person.workflow.responsible.email}</b><br/></>:"Без відповідального консультанта. "}{person.workflow?.next_action_at?`Дата наступної дії: ${new Date(person.workflow.next_action_at).toLocaleString("uk-UA",{day:"2-digit",month:"long",hour:"2-digit",minute:"2-digit"})}`:"Дату наступної дії не заплановано."}</p><button type="button" className="profile-text-action" onClick={()=>setTab("support")}>{person.workflow?.client_requests.length||person.workflow?.responsible?"Відкрити супровід":"Налаштувати супровід"}<ProfileIcon name="arrow"/></button></section>
        <PersonTags person={person}/>
        <section className="profile-doc-card">
          <div className="profile-card-heading"><span className="profile-section-icon"><ProfileIcon name="file"/></span><h3>CV та документи</h3><span className="profile-count">{documents.length}</span></div>
          <p>{documents.length?"Файли, прикріплені до профілю клієнта.":"Додайте резюме, щоб мати досвід клієнта під рукою."}</p>
          {documents.length>0&&<ul>{documents.slice(0,3).map(doc=><li key={doc.id}><ProfileIcon name="file"/><span>{String(doc.filename||"Документ")}</span></li>)}</ul>}
          <button className="profile-text-action" type="button" onClick={()=>setTab("documents")}>{documents.length?"Переглянути документи":"Прикріпити CV"}<ProfileIcon name="arrow"/></button>
        </section>
      </aside>
    </div></div>
    {tab==="support"&&<SupportPanel person={person} role={role} staffId={auth.staffId} onSaved={accept}/>}
    {tab==="employment"&&<EmploymentPanel person={person} role={role} onSaved={accept}/>}
    {tab==="access"&&<AccessPanel personId={person.id}/>}
    {tab==="documents"&&<DocumentsPanel person={person} onSaved={accept}/>}
    {analysisOpen&&<AnalysisModal person={person} onSaved={acceptAnalysis} onClose={()=>setAnalysisOpen(false)}/>}
  </section>;
}

export function ConsoleTeam(){
  const auth=useAppSelector(s=>s.auth),dispatch=useAppDispatch(),nav=useNavigate();
  const [items,setItems]=useState<Staff[]>([]),[error,setError]=useState(""),[success,setSuccess]=useState(""),[busy,setBusy]=useState(false),[show,setShow]=useState(false),[passwordTarget,setPasswordTarget]=useState<Staff|null>(null),[showPassword,setShowPassword]=useState(false);
  const load=async()=>setItems(await adminRequest<Staff[]>("/admin/staff"));
  useEffect(()=>{load().catch(e=>setError(errText(e)))},[]);
  const create=async(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();const form=e.currentTarget;const data=Object.fromEntries(new FormData(form));setBusy(true);setError("");setSuccess("");try{await adminRequest("/admin/staff",{method:"POST",body:JSON.stringify(data)});await load();form.reset();setShow(false);setSuccess("Обліковий запис створено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const update=async(id:number,payload:Record<string,unknown>)=>{setBusy(true);setError("");setSuccess("");try{await adminRequest(`/admin/staff/${id}`,{method:"PATCH",body:JSON.stringify(payload)});await load();setSuccess("Дані працівника оновлено")}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const resetPassword=async(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();if(!passwordTarget)return;const form=e.currentTarget,data=new FormData(form),password=String(data.get("new_password")||""),confirmation=String(data.get("confirm_password")||"");setError("");setSuccess("");if(password!==confirmation){setError("Паролі не збігаються");return}setBusy(true);try{await adminRequest(`/admin/staff/${passwordTarget.id}/password`,{method:"PUT",body:JSON.stringify({new_password:password})});if(passwordTarget.id===auth.staffId){dispatch(signedOut());nav("/admin/login");return}setPasswordTarget(null);setShowPassword(false);setSuccess(`Пароль для ${passwordTarget.full_name||passwordTarget.email} змінено`)}catch(e){setError(errText(e))}finally{setBusy(false)}};
  const canEdit=(s:Staff)=>s.id!==auth.staffId&&(auth.role==="super_admin"||s.role==="manager");
  return <section>
    <div className="page-title"><div><span className="console-kicker">СПІЛЬНА РОБОТА</span><h1>Команда</h1><p>Працівники, ролі та доступ до робочого простору.</p></div><button className="button" onClick={()=>setShow(!show)}>{show?"Закрити форму":"+ Додати працівника"}</button></div>
    <Notice error={error}/>{success&&<div className="success" role="status">{success}</div>}
    {show&&<form className="panel form console-editor" onSubmit={create}><h2>Новий працівник</h2><div className="form-grid"><label><span>Ім’я та прізвище</span><input name="full_name" required/></label><label><span>Email</span><input name="email" type="email" required/></label><label><span>Початковий пароль · від 8 символів</span><input name="password" type="password" autoComplete="new-password" minLength={8} maxLength={72} required/></label><label><span>Роль</span><select name="role" defaultValue="manager">{Object.entries(roles).filter(([key])=>auth.role==="super_admin"||key==="manager").map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div><button disabled={busy} className="button">{busy?"Створюємо…":"Створити обліковий запис"}</button></form>}
    {passwordTarget&&<form className="panel form console-editor console-password-reset" onSubmit={resetPassword}><div className="console-password-heading"><div><span className="console-kicker">БЕЗПЕКА ОБЛІКОВОГО ЗАПИСУ</span><h2>Новий пароль</h2><p>{passwordTarget.full_name||passwordTarget.email}{passwordTarget.id===auth.staffId?" · ваш обліковий запис":""}</p></div><button type="button" className="button secondary small" onClick={()=>{setPasswordTarget(null);setShowPassword(false);setError("")}}>Закрити</button></div><div className="form-grid"><label><span>Новий пароль · від 8 символів</span><div className="password-field"><input name="new_password" type={showPassword?"text":"password"} autoComplete="new-password" minLength={8} maxLength={72} required autoFocus/><button type="button" onClick={()=>setShowPassword(!showPassword)}>{showPassword?"Сховати":"Показати"}</button></div></label><label><span>Повторіть новий пароль</span><input name="confirm_password" type={showPassword?"text":"password"} autoComplete="new-password" minLength={8} maxLength={72} required/></label></div><div className="console-password-warning">Після збереження усі попередні сесії цього користувача завершаться.</div><button disabled={busy} className="button">{busy?"Змінюємо…":"Зберегти новий пароль"}</button></form>}
    <div className="console-list-panel table-wrap"><table><thead><tr><th>Працівник</th><th>Роль</th><th>Стан</th><th/></tr></thead><tbody>{items.map(s=><tr key={s.id}><td><b>{s.full_name||s.email}{s.id===auth.staffId?" · Ви":""}</b><small>{s.email}</small></td><td>{canEdit(s)&&s.role!=="super_admin"&&auth.role==="super_admin"?<select aria-label={`Роль ${s.email}`} value={s.role} disabled={busy} onChange={e=>void update(s.id,{role:e.target.value})}>{Object.entries(roles).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>:roles[s.role]||s.role}</td><td><span className={`status ${s.is_active?"active":"archived"}`}>{s.is_active?"Активний":"Вимкнений"}</span></td><td><div className="console-row-actions">{auth.role==="super_admin"&&<button className="button secondary small" disabled={busy} onClick={()=>{setPasswordTarget(s);setShowPassword(false);setError("");setSuccess("")}}>Змінити пароль</button>}{canEdit(s)&&s.role!=="super_admin"&&<button className="button secondary small" disabled={busy} onClick={()=>void update(s.id,{is_active:!s.is_active})}>{s.is_active?"Вимкнути доступ":"Увімкнути доступ"}</button>}</div></td></tr>)}</tbody></table></div>
  </section>
}
