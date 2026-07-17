import type { ReactNode } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { WeekSummary, ZoneBucket } from "@/lib/api"
import { fmtDate, fmtDuration, fmtNum } from "@/lib/format"

const AXIS = { fontSize: 11, fill: "var(--viz-axis)" }
const GRID = "var(--viz-grid)"

function VizTooltip({
  active,
  label,
  rows,
}: {
  active?: boolean
  label?: ReactNode
  rows: { name: string; value: string; color?: string }[]
}) {
  if (!active || rows.length === 0) return null
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      {label != null && <div className="mb-1 font-medium text-popover-foreground">{label}</div>}
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2 text-muted-foreground">
          {r.color && (
            <span className="inline-block size-2 rounded-full" style={{ background: r.color }} />
          )}
          <span>{r.name}</span>
          <span className="ml-auto pl-3 font-medium text-popover-foreground">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

export function WeeklyBars({
  weeks,
  metric,
  color,
  unit,
  format = (v) => fmtNum(v, 1),
}: {
  weeks: WeekSummary[]
  metric: (w: WeekSummary) => number | null
  color: string
  unit: string
  format?: (v: number) => string
}) {
  const data = [...weeks]
    .reverse()
    .map((w) => ({ week: fmtDate(w.week_start), value: metric(w) ?? 0, rides: w.ride_count }))
  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -8, bottom: 0 }} barCategoryGap="28%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="week" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} />
        <Tooltip
          cursor={{ fill: "var(--viz-grid)", opacity: 0.35 }}
          content={({ active, payload, label }) => (
            <VizTooltip
              active={active}
              label={`Week of ${label}`}
              rows={
                payload?.length
                  ? [
                      { name: unit, value: format(payload[0].payload.value), color },
                      { name: "rides", value: String(payload[0].payload.rides) },
                    ]
                  : []
              }
            />
          )}
        />
        <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} maxBarSize={38} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ZoneBars({
  zones,
  color,
  boundaryKey,
  boundaryUnit,
}: {
  zones: ZoneBucket[]
  color: string
  boundaryKey: "low_boundary_w" | "low_boundary_bpm"
  boundaryUnit: string
}) {
  return (
    <div className="flex flex-col gap-2">
      {zones.map((z) => (
        <div
          key={z.zone}
          className="group flex items-center gap-2"
          title={`Z${z.zone} · from ${fmtNum(z[boundaryKey])} ${boundaryUnit} · ${fmtDuration(z.time_s)}`}
        >
          <span className="w-7 text-xs text-muted-foreground">Z{z.zone}</span>
          <div className="h-4 flex-1 overflow-hidden rounded-r-[4px] bg-transparent">
            <div
              className="h-full rounded-r-[4px] transition-opacity group-hover:opacity-80"
              style={{ width: `${Math.max(z.share_pct, 0.5)}%`, background: color }}
            />
          </div>
          <span className="w-12 text-right text-xs tabular-nums text-muted-foreground">
            {fmtNum(z.share_pct, 0)}%
          </span>
        </div>
      ))}
      <div className="mt-1 text-xs text-muted-foreground">
        Zone boundaries from your Garmin settings ({boundaryUnit}) · hover for time in zone
      </div>
    </div>
  )
}

export function Sparkline({
  points,
  color,
}: {
  points: { x: string; y: number | null }[]
  color: string
}) {
  const data = points.filter((p) => p.y != null)
  if (data.length < 2) return <div className="h-10" />
  return (
    <ResponsiveContainer width="100%" height={40}>
      <LineChart data={data} margin={{ top: 4, right: 2, left: 2, bottom: 2 }}>
        <Tooltip
          content={({ active, payload }) => (
            <VizTooltip
              active={active}
              rows={
                payload?.length
                  ? [{ name: payload[0].payload.x, value: fmtNum(payload[0].payload.y as number, 0), color }]
                  : []
              }
            />
          )}
        />
        <Line type="monotone" dataKey="y" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

interface SeriesPoint {
  offset_s: number | null
  power_w: number | null
  hr_bpm: number | null
  elevation_m: number | null
}

export function RideStreams({ points }: { points: SeriesPoint[] }) {
  const data = points
    .filter((p) => p.offset_s != null)
    .map((p) => ({ ...p, t: Math.round((p.offset_s as number) / 60) }))

  const panels: {
    key: "power_w" | "hr_bpm" | "elevation_m"
    label: string
    unit: string
    color: string
    area: boolean
  }[] = [
    { key: "power_w", label: "Power", unit: "W", color: "var(--viz-power)", area: false },
    { key: "hr_bpm", label: "Heart rate", unit: "bpm", color: "var(--viz-hr)", area: false },
    { key: "elevation_m", label: "Elevation", unit: "m", color: "var(--viz-elev)", area: true },
  ]

  return (
    <div className="flex flex-col gap-1">
      {panels.map((panel) =>
        data.some((d) => d[panel.key] != null) ? (
          <div key={panel.key}>
            <div className="mb-0.5 flex items-baseline gap-2 pl-1">
              <span className="inline-block size-2 rounded-full" style={{ background: panel.color }} />
              <span className="text-xs font-medium">{panel.label}</span>
              <span className="text-xs text-muted-foreground">{panel.unit}</span>
            </div>
            <ResponsiveContainer width="100%" height={110}>
              <AreaChart data={data} syncId="ride" margin={{ top: 2, right: 4, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis
                  dataKey="t"
                  tick={AXIS}
                  axisLine={{ stroke: GRID }}
                  tickLine={false}
                  tickFormatter={(v) => `${v}m`}
                  minTickGap={40}
                />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} domain={["auto", "auto"]} />
                <Tooltip
                  content={({ active, payload }) => (
                    <VizTooltip
                      active={active}
                      label={payload?.length ? `${payload[0].payload.t} min` : undefined}
                      rows={
                        payload?.length && payload[0].payload[panel.key] != null
                          ? [
                              {
                                name: panel.label,
                                value: `${fmtNum(payload[0].payload[panel.key] as number)} ${panel.unit}`,
                                color: panel.color,
                              },
                            ]
                          : []
                      }
                    />
                  )}
                />
                <Area
                  type="monotone"
                  dataKey={panel.key}
                  stroke={panel.color}
                  strokeWidth={2}
                  fill={panel.color}
                  fillOpacity={panel.area ? 0.35 : 0.06}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : null,
      )}
    </div>
  )
}
