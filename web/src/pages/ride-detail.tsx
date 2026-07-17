import { Link, useParams } from "react-router-dom"
import { RideStreams, ZoneBars } from "@/components/charts"
import { ChartSkeleton, ErrorNote, useApi } from "@/components/data-state"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { fmtDateTime, fmtDuration, fmtNum } from "@/lib/format"

function Fact({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tracking-tight">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-muted-foreground">{unit}</span>}
      </div>
    </div>
  )
}

export default function RideDetail() {
  const { id } = useParams()
  const detail = useApi(() => api.rideDetail(Number(id)), [id])

  if (detail.error) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <ErrorNote error={detail.error} />
      </div>
    )
  }

  const s = detail.data?.summary as Record<string, never> | undefined
  const num = (key: string) => (s?.[key] != null ? Number(s[key]) : null)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <div>
        <Link to="/" className="text-xs text-muted-foreground hover:underline">
          ← Dashboard
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">
          {s ? String(s["name"] ?? "Ride") : "Ride"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {s ? fmtDateTime(String(s["start_time_local"])) : ""}
          {s?.["location"] ? ` · ${s["location"]}` : ""}
        </p>
      </div>

      <Card>
        <CardContent>
          {s ? (
            <div className="grid grid-cols-3 gap-x-4 gap-y-5 sm:grid-cols-5">
              <Fact label="Distance" value={fmtNum(num("distance_km"), 1)} unit="km" />
              <Fact label="Moving time" value={fmtDuration(num("moving_duration_s"))} />
              <Fact label="Climbing" value={fmtNum(num("elevation_gain_m"))} unit="m" />
              <Fact label="Avg power" value={fmtNum(num("avg_power_w"))} unit="W" />
              <Fact label="NP (Garmin)" value={fmtNum(num("normalized_power_w"))} unit="W" />
              <Fact label="Intensity factor" value={fmtNum(num("intensity_factor"), 2)} />
              <Fact label="TSS (Garmin)" value={fmtNum(num("training_stress_score"))} />
              <Fact label="Avg HR" value={fmtNum(num("avg_hr_bpm"))} unit="bpm" />
              <Fact label="Max HR" value={fmtNum(num("max_hr_bpm"))} unit="bpm" />
              <Fact label="Load" value={fmtNum(num("training_load"))} />
            </div>
          ) : (
            <ChartSkeleton height={90} />
          )}
          {s?.["garmin_reported_note"] != null && (
            <p className="mt-4 text-xs text-muted-foreground">{String(s["garmin_reported_note"])}.</p>
          )}
          {s?.["power_note"] != null && (
            <p className="text-xs text-muted-foreground">Power: {String(s["power_note"])}.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Ride streams</CardTitle>
        </CardHeader>
        <CardContent>
          {detail.data ? <RideStreams points={detail.data.series.points} /> : <ChartSkeleton height={340} />}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Time in power zones</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.data ? (
              <ZoneBars
                zones={detail.data.power_zones.zones}
                color="var(--viz-power)"
                boundaryKey="low_boundary_w"
                boundaryUnit="W"
              />
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Time in heart-rate zones</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.data ? (
              <ZoneBars
                zones={detail.data.hr_zones.zones}
                color="var(--viz-hr)"
                boundaryKey="low_boundary_bpm"
                boundaryUnit="bpm"
              />
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Laps</CardTitle>
        </CardHeader>
        <CardContent>
          {detail.data ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Lap</TableHead>
                  <TableHead className="text-right">Distance</TableHead>
                  <TableHead className="text-right">Moving</TableHead>
                  <TableHead className="text-right">Climb</TableHead>
                  <TableHead className="text-right">Avg W</TableHead>
                  <TableHead className="text-right">NP</TableHead>
                  <TableHead className="text-right">Avg HR</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detail.data.splits.laps.map((lap) => (
                  <TableRow key={String(lap["lap_index"])}>
                    <TableCell className="font-medium">{String(lap["lap_index"])}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(lap["distance_km"] as number, 1)} km
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtDuration(lap["moving_duration_s"] as number)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(lap["elevation_gain_m"] as number)} m
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(lap["avg_power_w"] as number)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(lap["normalized_power_w"] as number)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {fmtNum(lap["avg_hr_bpm"] as number)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <ChartSkeleton height={160} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
