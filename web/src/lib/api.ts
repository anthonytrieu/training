export class ApiError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(path)
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`
    try {
      const body = await resp.json()
      if (body.detail) detail = body.detail
    } catch {
      /* keep default */
    }
    throw new ApiError(resp.status, detail)
  }
  return resp.json()
}

export interface RideSummary {
  activity_id: number
  name: string
  activity_type: string
  start_time_local: string | null
  duration_s: number | null
  moving_duration_s: number | null
  distance_km: number | null
  elevation_gain_m: number | null
  avg_speed_kmh: number | null
  avg_hr_bpm: number | null
  max_hr_bpm: number | null
  avg_power_w: number | null
  max_power_w: number | null
  normalized_power_w: number | null
  avg_cadence_rpm: number | null
  calories_kcal: number | null
  training_load: number | null
  power_note: string | null
}

export interface WeekSummary {
  week_start: string
  week_end: string
  ride_count: number
  total_duration_h: number
  total_moving_h: number
  total_distance_km: number | null
  total_elevation_gain_m: number | null
  total_training_load: number | null
  hardest_ride: {
    activity_id: number
    name: string
    date: string | null
    training_load: number | null
  } | null
}

export interface ZoneBucket {
  zone: number
  time_s: number
  share_pct: number
  low_boundary_w?: number
  low_boundary_bpm?: number
}

export interface RideDetailResponse {
  summary: Record<string, number | string | null>
  power_zones: { zones: ZoneBucket[]; total_time_s: number }
  hr_zones: { zones: ZoneBucket[]; total_time_s: number }
  splits: { lap_count: number; laps: Record<string, number | string | null>[] }
  series: {
    point_count: number
    points: {
      offset_s: number | null
      distance_m: number | null
      power_w: number | null
      hr_bpm: number | null
      cadence_rpm: number | null
      speed_kmh: number | null
      elevation_m: number | null
    }[]
  }
}

export interface WellnessResponse {
  sleep: { nights: SleepNight[]; missing_dates: string[] }
  hrv: { days: HrvDay[]; missing_dates: string[] }
  resting_hr: { days: RhrDay[]; missing_dates: string[] }
}

export interface SleepNight {
  date: string
  total_sleep_s: number | null
  deep_s: number | null
  light_s: number | null
  rem_s: number | null
  sleep_score: number | null
  sleep_score_qualifier: string | null
  avg_overnight_hrv_ms: number | null
  resting_hr_bpm: number | null
}

export interface HrvDay {
  date: string
  last_night_avg_ms: number | null
  weekly_avg_ms: number | null
  status: string | null
}

export interface RhrDay {
  date: string
  resting_hr_bpm: number | null
}

export interface StatusResponse {
  training_status: {
    training_status_phrase: string | null
    acute_load: number | null
    chronic_load: number | null
    acwr_ratio: number | null
    acwr_status: string | null
    load_balance_phrase: string | null
    vo2max_cycling: number | null
  }
  ftp: { ftp_w: number | null; set_on: string | null; is_stale: boolean | null }
  vo2max: { vo2max_cycling: number | null; fitness_age: number | null }
  fitness_age: Record<string, number | string | null>
}

export const api = {
  rides: (limit = 10) => apiGet<RideSummary[]>(`/api/rides?limit=${limit}`),
  rideDetail: (id: number) => apiGet<RideDetailResponse>(`/api/rides/${id}`),
  weekly: (weeks = 8) =>
    apiGet<{ weeks: WeekSummary[] }>(`/api/weekly?weeks=${weeks}`),
  wellness: (days = 7) => apiGet<WellnessResponse>(`/api/wellness?days=${days}`),
  status: () => apiGet<StatusResponse>(`/api/status`),
  plan: () => apiGet<{ name: string; markdown: string }>(`/api/plan`),
}
