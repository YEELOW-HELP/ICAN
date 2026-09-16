import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { adminBootstrapStatus, adminDownload, adminLogin, adminRequest, ApiError, bootstrapSuperAdmin } from "./api/client";
import { useAppDispatch, useAppSelector } from "./app/hooks";
import { signedIn, signedOut, staffVerified } from "./app/store";
import type { Person, PersonCore, PersonListItem, FactRow } from "./types";

const roles: Record<string,string> = {super_admin:"Суперадміністратор", admin:"Адміністратор", manager:"Менеджер"};
type Staff = {id:number; email:string; full_name:string|null; role:string; is_active:boolean; is_creator?:boolean};
const errText = (e:unknown) => e instanceof Error ? e.message : "Не вдалося виконати дію";
function Notice({error}:{error:string}) { return error ? <div className="error" role="alert">{error}</div> : null }
function ConsoleBrand(){return <div className="console-brand"><span>Y</span><div>Yellow Hub<small>Робочий простір</small></div></div>}

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
  const [items,setItems]=useState<PersonListItem[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true),[query,setQuery]=useState(""),[status,setStatus]=useState("");
  const load=()=>{setLoading(true);setError("");adminRequest<PersonListItem[]>("/admin/persons").then(setItems).catch(e=>setError(errText(e))).finally(()=>setLoading(false))};
  useEffect(load,[]);
  const filtered=items.filter(p=>(!status||p.status===status)&&`${p.name} ${p.phone??""} ${p.email??""} ${p.city??""}`.toLowerCase().includes(query.toLowerCase()));
  return <section><div className="page-title"><div><span className="console-kicker">РОБОТА З ЛЮДЬМИ</span><h1>{role==="manager"?"Мої клієнти":"Усі клієнти"}</h1><p>{role==="manager"?"Створені вами та доступні вам профілі.":"Єдина база клієнтів вашої команди."}</p></div><Link className="button" to="/admin/persons/new">+ Додати клієнта</Link></div><div className="console-metrics">{[["Доступних клієнтів",items.length],["Активних",items.filter(p=>p.status==="active").length],["Чернеток",items.filter(p=>p.status==="draft").length]].map(([label,value])=><article key={label}><span>{label}</span><strong>{loading?"—":value}</strong></article>)}</div><div className="console-list-panel"><div className="console-filters"><input aria-label="Пошук клієнтів" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ім’я, телефон, email або місто"/><select aria-label="Статус" value={status} onChange={e=>setStatus(e.target.value)}><option value="">Усі статуси</option><option value="draft">Чернетки</option><option value="active">Активні</option><option value="archived">В архіві</option></select><button className="button secondary" onClick={load} disabled={loading}>Оновити</button></div><Notice error={error}/><div className="table-wrap"><table><thead><tr><th>Клієнт</th><th>Контакти</th><th>Місто</th><th>Статус</th><th>Оновлено</th><th/></tr></thead><tbody>{!loading&&filtered.map(p=><tr key={p.id}><td><Link className="console-person-link" to={`/admin/persons/${p.id}`}><span className="console-avatar">{p.name?.[0]||"?"}</span><b>{p.name||"Без імені"}</b></Link></td><td>{p.phone||"—"}<small>{p.email}</small></td><td>{p.city||"—"}</td><td><span className={`status ${p.status}`}>{p.status_uk}</span></td><td>{p.updated_at?new Date(p.updated_at).toLocaleDateString("uk-UA"):"—"}</td><td><Link className="button secondary small" to={`/admin/persons/${p.id}`}>Відкрити →</Link></td></tr>)}</tbody></table>{loading?<p className="loading">Завантажуємо клієнтів…</p>:!filtered.length&&<div className="console-empty"><h2>{query||status?"Нічого не знайдено":"Тут будуть ваші клієнти"}</h2><p>{query||status?"Змініть пошук або фільтр.":"Додайте першого клієнта, щоб почати роботу."}</p></div>}</div><div className="console-list-footer">Показано {filtered.length} із {items.length}</div></div></section>
}

const coreFields=[['first_name',"Ім’я",'text'],['last_name','Прізвище','text'],['phone','Телефон','tel'],['email','Email','email'],['city','Місто','text'],['region','Область','text'],['country','Країна','text'],['date_of_birth','Дата народження','date'],['telegram_username','Telegram','text']];
function CoreFields({value,onChange}:{value:Partial<PersonCore>;onChange:(v:Partial<PersonCore>)=>void}){return <div className="form-grid">{coreFields.map(([key,label,type])=><label key={key}><span>{label}{key==="first_name"?" *":""}</span><input type={type} required={key==="first_name"} value={String(value[key as keyof PersonCore]??"")} onChange={e=>onChange({...value,[key]:e.target.value})}/></label>)}</div>}
export function ConsoleCreate(){const nav=useNavigate();const [core,setCore]=useState<Partial<PersonCore>>({first_name:""}),[error,setError]=useState(""),[busy,setBusy]=useState(false);const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");try{const p=await adminRequest<Person>("/admin/persons",{method:"POST",body:JSON.stringify(core)});nav(`/admin/persons/${p.id}`)}catch(e){setError(errText(e))}finally{setBusy(false)}};return <section><Link className="back" to="/admin/persons">← До клієнтів</Link><div className="page-title"><div><h1>Новий клієнт</h1><p>Для початку достатньо імені. Решту можна доповнити пізніше.</p></div></div><form className="panel form console-editor" onSubmit={submit}><CoreFields value={core} onChange={setCore}/><Notice error={error}/><div className="console-form-actions"><Link className="button secondary" to="/admin/persons">Скасувати</Link><button disabled={busy} className="button">{busy?"Створюємо…":"Створити профіль →"}</button></div></form></section>}

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
  return <div className="panel console-editor"><div className="page-title compact"><h2>{block.title}</h2><button className="button secondary" onClick={()=>{setEditing("new");setValues({});setError("")}}>+ Додати запис</button></div><Notice error={error}/>{editing&&<form className="form console-fact-form" onSubmit={submit}><div className="form-grid">{block.fields.map(([key,label,type])=><label key={key}><span>{label}</span>{type==="textarea"?<textarea value={values[key]||""} onChange={e=>setValues({...values,[key]:e.target.value})}/>:type==="level"?<select value={values[key]||"unknown"} onChange={e=>setValues({...values,[key]:e.target.value})}>{["unknown","native","a1","a2","b1","b2","c1","c2"].map(x=><option key={x} value={x}>{x==="unknown"?"Не вказано":x==="native"?"Рідна":x.toUpperCase()}</option>)}</select>:<input type={type||"text"} required={label.includes("*")} value={values[key]||""} onChange={e=>setValues({...values,[key]:e.target.value})}/>}</label>)}</div><div className="console-form-actions"><button type="button" className="button secondary" onClick={()=>setEditing(null)}>Скасувати</button><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти запис"}</button></div></form>}<div className="console-facts">{rows.map(row=><article key={row.id}><div>{block.fields.filter(([key])=>row[key]!=null&&row[key]!=="").map(([key,label])=><div key={key}><small>{label.replace(" *","")}</small><p>{String(row[key])}</p></div>)}{block.key==="skills"&&row.evidence_state==="system_detected"&&<small>Знайдено ШІ · потребує підтвердження{row.evidence_excerpt?` · «${String(row.evidence_excerpt)}»`:""}</small>}</div><button className="button secondary small" onClick={()=>{setEditing(row.id);setValues(Object.fromEntries(block.fields.map(([key])=>[key,String(row[key]??"")])));setError("")}}>Редагувати</button></article>)}</div>{!rows.length&&!editing&&<div className="console-empty"><p>Записів ще немає. Додайте інформацію зі слів клієнта.</p></div>}</div>
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
  new_tags_count:number;
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
      if(analysis.new_tags_count)onSaved(await adminRequest<Person>(`/admin/persons/${person.id}`));
    }catch(e){setError(errText(e))}finally{setBusy(false)}
  };
  return <div className="panel console-editor">
    <h2>Проаналізувати клієнта</h2>
    <p className="muted">Оберіть джерело даних для ШІ. Навички, знайдені в наявному довіднику та підтверджені текстом, додадуться до профілю як непідтверджені теги. Інші пропозиції залишаться чернеткою.</p>
    <div className="console-row-actions"><button type="button" className={`button ${source==="cv"?"":"secondary"}`} onClick={()=>choose("cv")}>CV</button><button type="button" className={`button ${source==="questionnaire"?"":"secondary"}`} onClick={()=>choose("questionnaire")}>Анкету</button></div>
    {source==="cv"&&(cvs.length?<label><span>Прикріплений CV</span><select value={cvs.some(row=>row.id===selectedCv)?selectedCv:cvs[0].id} onChange={e=>setSelectedCv(e.target.value)}>{cvs.map(row=><option key={row.id} value={row.id}>{String(row.filename||"CV")}</option>)}</select></label>:<p className="muted">Немає PDF або DOCX. Прикріпіть файл у вкладці «Документи».</p>)}
    {source==="questionnaire"&&<p className="muted">Буде використано збережені дані анкети: досвід, освіту, навички, мови та побажання щодо роботи. Контакти, дата народження й нотатки працівника не надсилаються.</p>}
    {source&&<><p className="muted">Дані вибраного джерела надсилаються сервісу OpenAI для аналізу.</p><label><input type="checkbox" checked={permissionConfirmed} onChange={e=>setPermissionConfirmed(e.target.checked)}/> Підтверджую, що маю дозвіл на AI-обробку даних клієнта.</label><div className="console-form-actions"><button className="button" disabled={busy||!permissionConfirmed||(source==="cv"&&!cvs.length)} onClick={()=>void run()}>{busy?"Аналізуємо…":"Надіслати на аналіз"}</button></div></>}
    <Notice error={error}/>
    {result&&<div className="console-fact-form"><h3>Результат аналізу {result.cached&&<small>· із кешу</small>}</h3><p><b>Основна посада:</b> {result.proposal.primary_role||"Не визначено"}</p>{result.proposal.alternative_roles.length>0&&<p><b>Суміжні посади:</b> {result.proposal.alternative_roles.join(", ")}</p>}{result.detected_tags.length>0&&<p><b>Теги з довідника:</b> {result.detected_tags.map(t=>t.name).join(", ")} · нових: {result.new_tags_count}. Перегляньте їх у вкладці «Навички».</p>}{result.proposal.skills.some(s=>!s.canonical_skill_id)&&<p><b>Потребують звірки:</b> {result.proposal.skills.filter(s=>!s.canonical_skill_id).map(s=>s.name).join(", ")}</p>}{result.proposal.search_queries.length>0&&<p><b>Запити для пошуку:</b> {result.proposal.search_queries.join("; ")}</p>}{result.proposal.work_format&&<p><b>Формат:</b> {result.proposal.work_format}</p>}{result.proposal.summary&&<p>{result.proposal.summary}</p>}<small>Теги ШІ не є підтвердженими фактами. Інші пропозиції не записуються в профіль. Токени: {result.input_tokens} вхідних / {result.output_tokens} вихідних.</small></div>}
  </div>;
}

export function ConsolePerson(){
  const {id}=useParams(),role=useAppSelector(s=>s.auth.role);
  const [person,setPerson]=useState<Person|null>(null),[core,setCore]=useState<Partial<PersonCore>>({}),[tab,setTab]=useState("core"),[error,setError]=useState(""),[saved,setSaved]=useState(false),[busy,setBusy]=useState(false);
  const accept=(p:Person)=>{setPerson(p);setCore(p.core);setSaved(true);setError("")};
  useEffect(()=>{setPerson(null);setError("");adminRequest<Person>(`/admin/persons/${id}`).then(p=>{setPerson(p);setCore(p.core)}).catch(e=>setError(errText(e)))},[id]);
  const save=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setSaved(false);setError("");try{const payload=Object.fromEntries(coreFields.map(([key])=>[key,core[key as keyof PersonCore]??null]));accept(await adminRequest<Person>(`/admin/persons/${id}`,{method:"PATCH",body:JSON.stringify({...payload,notes:core.notes})}))}catch(e){setError(errText(e))}finally{setBusy(false)}};
  if(!person)return error?<Notice error={error}/>:<p className="loading">Відкриваємо профіль…</p>;
  const tabs=[["core","Основне"],...blocks.map(b=>[b.key,b.title]),["mobility","Мобільність"],["documents","Документи"],["analysis","Проаналізувати"],...(role!=="manager"?[["access","Доступ"]]:[])];const block=blocks.find(b=>b.key===tab);
  return <section><Link className="back" to="/admin/persons">← До клієнтів</Link><div className="page-title console-profile-title"><div className="console-person-link"><span className="console-avatar large">{person.core.first_name[0]}</span><div><h1>{person.core.first_name} {person.core.last_name}</h1><p>{person.core.city||"Місто не вказано"} · {person.core.phone||"Телефон не вказано"}</p></div></div><span className={`status ${person.core.status}`}>{person.core.status_uk}</span></div><div className="tabs">{tabs.map(([key,label])=><button key={key} className={tab===key?"active":""} onClick={()=>{setTab(key);setSaved(false);setError("")}}>{label}</button>)}</div><Notice error={error}/>{saved&&<div className="success" role="status">Зміни збережено</div>}{tab==="core"&&<form className="panel form console-editor" onSubmit={save}><h2>Контактна інформація</h2><CoreFields value={core} onChange={setCore}/><label><span>Нотатки</span><textarea rows={5} value={core.notes||""} onChange={e=>setCore({...core,notes:e.target.value})}/></label><div className="console-form-actions"><button className="button" disabled={busy}>{busy?"Зберігаємо…":"Зберегти зміни"}</button></div></form>}{block&&<FactsEditor key={block.key} person={person} block={block} onSaved={accept}/>} {tab==="mobility"&&<MobilityEditor person={person} onSaved={accept}/>} {tab==="access"&&<AccessPanel personId={person.id}/>} {tab==="documents"&&<DocumentsPanel person={person} onSaved={accept}/>} {tab==="analysis"&&<AnalysisPanel key={person.id} person={person} onSaved={accept}/>}</section>
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
