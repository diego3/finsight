export type RiskProfile = "conservative" | "moderate" | "aggressive";

export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  risk_profile: RiskProfile;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ClientInput {
  name: string;
  email: string;
  phone?: string;
  risk_profile: RiskProfile;
  notes?: string;
}
