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
  updated_at?: string | null;
};

export type FactRow = Record<string, unknown> & { id: string };

export type Person = {
  id: string;
  identity_user_id?: string | null;
  core: PersonCore;
  mobility: Record<string, unknown>;
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

export type CareerListItem = {
  id: string;
  code: string;
  name_uk: string;
  category_uk?: string | null;
  status?: string;
  profile_version?: number;
  short_description_uk?: string;
};
