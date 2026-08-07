export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  advisorData?: AdvisorResponse["data"];
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export interface DeveloperMatch {
  user_id: number;
  display_name: string;
  profile_picture: string | null;
  skills: string;
  rating: number | null;
  matched_tech: string[];
  gig_count: number;
  score: number;
  match_evidence: Record<string, string[]>;
  requested_tech_count: number;
  coverage_percent: number;
  advertised_price_low: number | null;
  advertised_price_high: number | null;
  price_currency: string;
  compensation_label: string | null;
  annual_compensation_inr: number | null;
  daily_rate_inr: number | null;
  hourly_rate_inr: number | null;
  experience: string | null;
  location: string | null;
  current_company: string | null;
}

export interface Estimate {
  low: number;
  median: number;
  high: number;
  sample_size: number;
  confidence: string;
  unit: string;
}

export interface AdvisorResponse {
  chat_id: string;
  response: string;
  intents: string[];
  data: {
    developers: DeveloperMatch[];
    cost: Estimate | null;
    time: Estimate | null;
    technology_used: string[];
    search_terms: string[];
    total_matches: number | null;
  };
}
