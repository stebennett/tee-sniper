export type WantedKind = 'one_shot' | 'recurring';
export type WantedStatus = 'pending' | 'booked' | 'expired' | 'disabled';
export type Outcome =
  | 'booked' | 'no_slots' | 'auth_failed' | 'upstream_error' | 'booking_failed';

export interface Notify { to: string; from?: string }

export interface Attempt {
  ts: string;
  target_date: string;
  outcome: Outcome;
  booking_id?: string | null;
  error?: string | null;
}

export interface WantedResponse {
  id: string;
  kind: WantedKind;
  target_date: string | null;
  day_of_week: number | null;
  end_date: string | null;
  start_time: string;
  end_time: string;
  num_slots: number;
  partners: string[];
  has_credentials: boolean;
  notify: Notify | null;
  status: WantedStatus;
  attempts: Attempt[];
  created_at: string;
  updated_at: string;
}

export interface LoginRequest { credentials: string }
export interface LoginResponse { access_token: string; expires_at: string }

export interface EncryptRequest { username: string; pin: string }
export interface EncryptResponse { credentials: string }

export interface CreateOneShotRequest {
  target_date: string;          // YYYY-MM-DD
  start_time: string;           // HH:MM
  end_time: string;             // HH:MM
  num_slots: number;
  partners: string[];
  credentials: string;
  notify?: Notify | null;
}

export interface CreateRecurringRequest {
  day_of_week: number;          // 0=Mon ... 6=Sun (matches Python weekday())
  end_date?: string | null;
  start_time: string;
  end_time: string;
  num_slots: number;
  partners: string[];
  credentials: string;
  notify?: Notify | null;
}

export interface PatchWantedRequest {
  start_time?: string;
  end_time?: string;
  num_slots?: number;
  partners?: string[];
  notify?: Notify | null;
  disabled?: boolean;
  credentials?: string;
}

export interface Partner { id: string; name: string }
export interface PartnerListResponse { partners: Partner[] }
