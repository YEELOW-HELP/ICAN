export type PersonCore = {
  first_name: string;
  last_name?: string | null;
  phone?: string | null;
  email?: string | null;
  telegram_username?: string | null;
  city?: string | null;
  region?: string | null;
  country?: string | null;
  date_of_birth?: string | null;
  status?: string;
  status_uk?: string;
  source?: string;
  source_uk?: string;
  referral_source?: string | null;
  referral_details?: string | null;
  notes?: string | null;
};

export type PersonListItem = {
  id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  telegram_username?: string | null;
  city?: string | null;
  status: string;
  status_uk: string;
  source?: string;
  created_at?: string | null;
  updated_at?: string | null;
  work_format?: string | null;
  employment_type?: string | null;
  responsible?: StaffSummary | null;
  workflow_stage?: string;
  workflow_stage_uk?: string;
  workflow_closure_reason_uk?: string | null;
  needs_contact?: boolean;
  has_next_action?: boolean;
  next_action_text?: string | null;
  next_action_at?: string | null;
};

export type StaffSummary = {
  id: number;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
};

export type FactRow = Record<string, unknown> & { id: string };

export type Person = {
  id: string;
  identity_user_id?: string | null;
  core: PersonCore;
  mobility: Record<string, unknown>;
  employment?: {
    stage_id?: string | null;
    stage_name?: string | null;
    stage_active?: boolean | null;
    offer_text?: string | null;
  };
  workflow?: {
    stage: string;
    stage_uk: string;
    closure_reason?: string | null;
    closure_reason_uk?: string | null;
    closure_note?: string | null;
    client_requests: {id:string; name:string; is_active:boolean}[];
    responsible?: StaffSummary | null;
    needs_contact: boolean;
    next_action_text?: string | null;
    next_action_at?: string | null;
  };
  tags: {skill_id:string; name:string; skill_type?:string|null}[];
  educations: FactRow[];
  credentials: FactRow[];
  experiences: FactRow[];
  activities: FactRow[];
  skills: FactRow[];
  languages: FactRow[];
  documents: FactRow[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type AiRecommendationStep = {
  title: string;
  action: string;
};

export type SuperAdminAiRecommendation = {
  recommendation: {
    summary: string;
    steps: AiRecommendationStep[];
    platform_offers: string[];
    questions_to_clarify: string[];
    suggested_workflow_stage: string;
  } | null;
  vacancy_search?: {
    location?: string | null;
    work_format?: string | null;
    professions: {
      career_id: string;
      name: string;
      matched_tags: string[];
      match_count: number;
      score: number;
    }[];
    queries: string[];
  } | null;
  generated_at?: string | null;
  profile_updated_at?: string | null;
  is_outdated?: boolean;
  model?: string | null;
  input_tokens?: number;
  output_tokens?: number;
};

export type CareerListItem = {
  id: string;
  code: string;
  name_uk: string;
  category_uk?: string | null;
  status?: string;
  profile_version?: number;
  short_description_uk?: string;
};
