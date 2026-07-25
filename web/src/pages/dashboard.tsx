import { Link } from "react-router-dom"
import { BalanceTrend, Sparkline, WeeklyBars } from "@/components/charts"
import { ChartSkeleton, ErrorNote, useApi } from "@/components/data-state"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { fmtDateTime, fmtDuration, fmtNum, titleCase } from "@/lib/format"

function StatTile({
  label,
  value,
  unit,
  sub,
  spark,
  sparkColor,
}: {
  label: string
  value: string
  unit?: string
  sub?: string
  spark?: { x: string; y: number | null }[]
  sparkColor?: string
}) {
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-semibold tracking-tight">{value}</span>
          {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
        </div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
        {spark && sparkColor && <Sparkline points={spark} color={sparkColor} />}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const status = useApi(() => api.status())
  const weekly = useApi(() => api.weekly(8))
  const wellness = useApi(() => api.wellness(7))
  const rides = useApi(() => api.rides(30))
  const forecast = useApi(() => api.weather(5))

  const anyAuthError = [status, weekly, wellness, rides].find(
    (q) => q.error,
  )?.error

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Training dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Live from Garmin Connect · power values from a single-sided meter
        </p>
      </div>

      {anyAuthError && <ErrorNote error={anyAuthError} />}

      {/* Stat tiles */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {status.loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : status.data ? (
          <>
            <StatTile
              label="FTP"
              value={fmtNum(status.data.ftp.ftp_w)}
              unit="W"
              sub={status.data.ftp.is_stale ? "stale — retest soon" : "current"}
            />
            <StatTile
              label="VO2 max (cycling)"
              value={fmtNum(status.data.vo2max.vo2max_cycling, 1)}
              sub={
                status.data.vo2max.fitness_age != null
                  ? `fitness age ${fmtNum(status.data.vo2max.fitness_age)}`
                  : undefined
              }
            />
            <StatTile
              label="Training status"
              value={titleCase(status.data.training_status.training_status_phrase)}
              sub={`ACWR ${fmtNum(status.data.training_status.acwr_ratio, 2)} · ${(
                status.data.training_status.acwr_status ?? "–"
              ).toLowerCase()}`}
            />
            <StatTile
              label="Load (acute / chronic)"
              value={`${fmtNum(status.data.training_status.acute_load)} / ${fmtNum(
                status.data.training_status.chronic_load,
              )}`}
              sub={titleCase(status.data.training_status.load_balance_phrase)}
            />
          </>
        ) : null}
      </div>

      {/* Weekly charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Weekly volume — moving hours</CardTitle>
          </CardHeader>
          <CardContent>
            {weekly.data ? (
              <WeeklyBars
                weeks={weekly.data.weeks}
                metric={(w) => w.total_moving_h}
                color="var(--viz-volume)"
                unit="hours"
              />
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Weekly training load (Garmin)</CardTitle>
          </CardHeader>
          <CardContent>
            {weekly.data ? (
              <WeeklyBars
                weeks={weekly.data.weeks}
                metric={(w) => w.total_training_load}
                color="var(--viz-load)"
                unit="load"
                format={(v) => fmtNum(v, 0)}
              />
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Week ahead weather */}
      {forecast.data && (
        <Card className="py-4">
          <CardContent className="px-4">
            <div className="mb-2 text-xs font-medium text-muted-foreground">
              Week ahead — {forecast.data.location}
            </div>
            <div className="grid grid-cols-5 gap-2">
              {forecast.data.daily.map((d) => (
                <div key={d.date} className="rounded-md border p-2 text-center">
                  <div className="text-xs font-medium">
                    {new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short" })}
                  </div>
                  <div className="text-sm font-semibold tabular-nums">
                    {Math.round(d.temp_max_c ?? 0)}°
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      {Math.round(d.temp_min_c ?? 0)}°
                    </span>
                  </div>
                  <div className="truncate text-[11px] text-muted-foreground">{d.conditions ?? "–"}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {d.precip_probability_pct ?? 0}% ☂ · {Math.round(d.wind_max_kmh ?? 0)} km/h
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Wellness tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {wellness.loading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32" />)
        ) : wellness.data ? (
          <>
            <StatTile
              label="Sleep score (last night)"
              value={fmtNum(wellness.data.sleep.nights.at(-1)?.sleep_score)}
              sub={`${fmtDuration(wellness.data.sleep.nights.at(-1)?.total_sleep_s)} sleep`}
              spark={wellness.data.sleep.nights.map((n) => ({ x: n.date, y: n.sleep_score }))}
              sparkColor="var(--viz-sleep)"
            />
            <StatTile
              label="Overnight HRV"
              value={fmtNum(wellness.data.hrv.days.at(-1)?.last_night_avg_ms)}
              unit="ms"
              sub={`7-day avg ${fmtNum(wellness.data.hrv.days.at(-1)?.weekly_avg_ms)} ms`}
              spark={wellness.data.hrv.days.map((d) => ({ x: d.date, y: d.last_night_avg_ms }))}
              sparkColor="var(--viz-hrv)"
            />
            <StatTile
              label="Resting heart rate"
              value={fmtNum(wellness.data.resting_hr.days.at(-1)?.resting_hr_bpm)}
              unit="bpm"
              spark={wellness.data.resting_hr.days.map((d) => ({
                x: d.date,
                y: d.resting_hr_bpm,
              }))}
              sparkColor="var(--viz-rhr)"
            />
          </>
        ) : null}
      </div>

      {/* L/R balance trend (dual-sided rides only) */}
      {rides.data && rides.data.filter((r) => r.left_balance_pct != null).length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Left-leg share of power — dual-sided rides
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BalanceTrend rides={rides.data} />
            <p className="mt-1 text-xs text-muted-foreground">
              Shaded band = normal 48–52%. Day-to-day wobble is noise; only a persistent
              drift outside the band is worth a look.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Recent rides */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent rides</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {rides.data ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ride</TableHead>
                  <TableHead className="text-right">Distance</TableHead>
                  <TableHead className="text-right">Moving</TableHead>
                  <TableHead className="text-right">Climb</TableHead>
                  <TableHead className="text-right">NP*</TableHead>
                  <TableHead className="text-right">Avg HR</TableHead>
                  <TableHead className="text-right">Load</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rides.data.slice(0, 8).map((r) => (
                  <TableRow key={r.activity_id}>
                    <TableCell>
                      <Link
                        to={`/rides/${r.activity_id}`}
                        className="font-medium hover:underline"
                      >
                        {fmtDateTime(r.start_time_local)}
                      </Link>
                      <div className="text-xs text-muted-foreground">{r.name}</div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(r.distance_km, 1)} km
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtDuration(r.moving_duration_s)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(r.elevation_gain_m)} m
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.normalized_power_w != null ? `${fmtNum(r.normalized_power_w)} W` : "–"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(r.avg_hr_bpm)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="secondary" className="tabular-nums">
                        {fmtNum(r.training_load)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <ChartSkeleton height={240} />
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            *NP is Garmin-reported. Power is from a dual-sided Rally meter since Jul 24,
            2026; earlier rides used a single-sided meter (left-leg doubled).
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
