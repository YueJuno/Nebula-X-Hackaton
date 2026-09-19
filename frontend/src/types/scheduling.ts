export interface Summary {
  lines: number; stations: number; locations: number; contracts: number;
  activities: number; total_accesses: number; horizon_start: string; horizon_weeks: number;
}
export interface Dataset { id: string; name: string; summary: Summary; created_at: string }
export interface Activity {
  activity_id: string; contract_number: string; activity_type: string; start_location_id: string;
  end_location_id: string; total_accesses: number; planned_start_date: string; activity_priority: number;
}
export interface Instance {
  activities: Activity[];
  stations: { station_id: string; line_code: string; seq: number; is_interchange: boolean }[];
  lines: { line_code: string; line_name: string }[];
  locations: { location_id: string; supply_capacity: number; line_code: string; bound: string }[];
  horizon_weeks: number;
}
export interface Footprint {
  activity_id: string; occupied: string[]; buffers: string[]; mirrored: string[];
  cross_line: string[]; affected_lines: string[];
}
export interface SoftScores {
  scenario?: string; overrun_days_total?: number; contracts_overrunning?: number;
  earliness_days_total?: number; excess_access_nights_total?: number;
  eclo_nights_total?: number; priority_overrun?: Record<string, number>;
  priority_weighted_score?: number; objective_score?: number; formula_version?: string;
}
export interface Validation {
  status: string;
  validator?: string;
  feasible: boolean | null;
  hard_violations?: { rule: string; severity?: string; detail: string }[];
  soft_scores?: SoftScores;
  detail?: {
    closure_granularity?: string;
    hard_violations_total?: number;
    violations_by_rule?: Record<string, number>;
    nights_scheduled?: number;
    eclo_nights?: number;
  };
}
export interface DelayExplanation {
  activity_id: string; contract_number: string; activity_type: string;
  contract_priority: number; activity_priority: number;
  completion_week: number; deadline_week: number; overrun_days: number;
  weighted_cost: number; earliest_week: number; window_weeks: number;
  nights_required: number; window_shortfall: number; shortfall_with_eclo: number;
  missed_weeks: number[]; blocking_factors: Record<string, number>;
  primary_factor: string; hotspots: { location_id: string; weeks: number[] }[];
  summary: string;
}
export interface Explanation {
  scenario: string; objective_score: number; delayed_activities: number;
  explanations: DelayExplanation[];
}
export interface PreparationReport {
  missing_constraints: string[]; model_stats: string; footprints: Record<string, Footprint>;
  notice: string;
  solution?: {
    solver_status: string; objective_score: number; nights_scheduled: number;
    eclo_nights_total: number; excess_access_nights_total: number;
    contracts_overrunning: number; overrun_days_total: number;
    priority_weighted_overrun: number;
  };
  explanation?: Explanation;
  validation?: Validation;
  external_validation?: Validation;
}
export interface Schedule {
  accesses: { activity_id: string; week: number; eclo: number; access_night: number; groups: Record<string, string> }[];
  objective_score: number; solver_status: string;
}
export interface Run {
  id: string; dataset_id: string; scenario: string; buffer_granularity?: string; status: string; created_at: string;
  message: string | null; report: PreparationReport | null; schedule: Schedule | null;
}
export interface Capabilities { can_schedule: boolean; can_prepare: boolean; missing_constraints: string[]; required_files: string[] }
