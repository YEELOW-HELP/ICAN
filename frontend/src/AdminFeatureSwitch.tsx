import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { App } from "./App";
import { ConsoleCreate, ConsoleGate, ConsoleLogin, ConsolePerson, ConsolePersons, ConsoleTeam } from "./Console";
import { AdminCareerEditor, AdminCareers, AdminMatch } from "./AdminMatch";
import { useAppDispatch, useAppSelector } from "./app/hooks";
import { signedOut } from "./app/store";

const roles:Record<string,string>={super_admin:"Суперадміністратор",admin:"Адміністратор",manager:"Менеджер"};

function FeatureBrand(){return <div className="console-brand"><span>Y</span><div>Yellow Hub<small>Робочий простір</small></div></div>}

function MatchConsoleLayout(){
  const auth=useAppSelector(s=>s.auth),dispatch=useAppDispatch();
  return <div className="admin-shell console-shell"><aside><FeatureBrand/><span className="side-label">КОНСОЛЬ</span><nav><NavLink end to="/admin/persons">Люди</NavLink><NavLink to="/admin/persons/new">Додати клієнта</NavLink>{auth.role!=="manager"&&<NavLink to="/admin/catalog">Професії</NavLink>}<NavLink to="/admin/match">Метч</NavLink>{auth.role!=="manager"&&<NavLink to="/admin/team">Команда</NavLink>}{auth.role==="super_admin"&&<Link to="/">Переглянути сайт ↗</Link>}</nav><div className="console-account"><span className="console-avatar">{auth.adminEmail?.[0]?.toUpperCase()}</span><div><strong>{roles[auth.role||""]}</strong><small>{auth.adminEmail}</small></div></div><button className="button secondary" onClick={()=>dispatch(signedOut())}>Вийти з облікового запису</button></aside><main><div className="console-topline"><span>NAPRIAM / Адміністративна панель</span><span className="status active">{roles[auth.role||""]}</span></div><Outlet/></main></div>;
}

function FeatureAdminRoutes(){
  const role=useAppSelector(s=>s.auth.role);
  return <ConsoleGate><Routes><Route path="/admin/login" element={<ConsoleLogin/>}/><Route path="/admin" element={<MatchConsoleLayout/>}><Route index element={<Navigate to="persons" replace/>}/><Route path="persons" element={<ConsolePersons/>}/><Route path="persons/new" element={<ConsoleCreate/>}/><Route path="persons/:id" element={<ConsolePerson/>}/><Route path="match" element={<AdminMatch/>}/><Route path="catalog" element={role==="manager"?<Navigate to="/admin/match" replace/>:<AdminCareers/>}/><Route path="catalog/:id" element={role==="manager"?<Navigate to="/admin/match" replace/>:<AdminCareerEditor/>}/><Route path="team" element={role==="manager"?<Navigate to="/admin/persons" replace/>:<ConsoleTeam/>}/></Route><Route path="*" element={<Navigate to="/admin/persons" replace/>}/></Routes></ConsoleGate>;
}

export function AdminFeatureSwitch(){
  const {pathname}=useLocation();
  return pathname.startsWith("/admin")?<FeatureAdminRoutes/>:<App/>;
}
