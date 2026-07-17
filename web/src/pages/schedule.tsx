import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ErrorNote, useApi } from "@/components/data-state"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type RideSummary } from "@/lib/api"
import { fmtDuration, fmtNum } from "@/lib/format"

interface SessionDef {
  id: string
  title: string
  kind: "intervals" | "tempo" | "long" | "easy" | "race"
  duration_min: number
  target: string
  detail: string
  alt?: string
  fixed_date?: string
}

const STORAGE_KEY = "garmin-coach-schedule"
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

const KIND_STYLE: Record<SessionDef["kind"], string> = {
  intervals: "border-l-[var(--viz-hr)]",
  tempo: "border-l-[var(--viz-load)]",
  long: "border-l-[var(--viz-power)]",
  easy: "border-l-[var(--viz-elev)]",
  race: "border-l-[var(--viz-sleep)]",
}

// session id -> ISO date it is scheduled on
type Assignments = Record<string, string>

function loadAssignments(): Assignments {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}")
  } catch {
    return {}
  }
}

function isoAddDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function SessionCard({
  session,
  compact,
  onUnassign,
  assignable,
  onAssign,
  days,
}: {
  session: SessionDef
  compact?: boolean
  onUnassign?: () => void
  assignable?: boolean
  onAssign?: (dayIdx: number) => void
  days?: string[]
}) {
  const locked = Boolean(session.fixed_date)
  return (
    <div
      draggable={!locked}
      onDragStart={(e) => e.dataTransfer.setData("text/session", session.id)}
      className={`group rounded-md border border-l-4 bg-card p-2 text-left shadow-xs ${KIND_STYLE[session.kind]} ${
        locked ? "opacity-90" : "cursor-grab active:cursor-grabbing"
      }`}
      title={`${session.detail}${session.alt ? `\nEasier alternative: ${session.alt}` : ""}`}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="text-xs font-medium leading-tight">{session.title}</div>
        {onUnassign && !locked && (
          <button
            onClick={onUnassign}
            className="hidden text-xs text-muted-foreground hover:text-foreground group-hover:block"
            aria-label="Unassign"
          >
            ✕
          </button>
        )}
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">
        {fmtDuration(session.duration_min * 60)} · {session.target}
      </div>
      {!compact && assignable && onAssign && days && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {DAY_NAMES.map((name, i) => (
            <button
              key={name}
              onClick={() => onAssign(i)}
              className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-accent hover:text-foreground"
              title={days[i]}
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Schedule() {
  const navigate = useNavigate()
  const plan = useApi(() => api.sessions())
  const rides = useApi(() => api.rides(30))
  const [assignments, setAssignments] = useState<Assignments>(loadAssignments)
  const [weekIdx, setWeekIdx] = useState<number | null>(null)

  // Default to the current week once the plan loads.
  useEffect(() => {
    if (plan.data && weekIdx === null) {
      const today = todayIso()
      const idx = plan.data.weeks.findIndex(
        (w) => today >= w.start && today <= isoAddDays(w.start, 6),
      )
      setWeekIdx(idx >= 0 ? idx : today < plan.data.weeks[0].start ? 0 : plan.data.weeks.length - 1)
    }
  }, [plan.data, weekIdx])

  const week = plan.data && weekIdx !== null ? plan.data.weeks[weekIdx] : null
  const days = useMemo(
    () => (week ? Array.from({ length: 7 }, (_, i) => isoAddDays(week.start, i)) : []),
    [week],
  )

  const ridesByDay = useMemo(() => {
    const map: Record<string, RideSummary[]> = {}
    for (const r of rides.data ?? []) {
      const day = r.start_time_local?.slice(0, 10)
      if (day) (map[day] ??= []).push(r)
    }
    return map
  }, [rides.data])

  function assign(sessionId: string, date: string | null) {
    setAssignments((prev) => {
      const next = { ...prev }
      if (date) next[sessionId] = date
      else delete next[sessionId]
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }

  if (plan.error) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <ErrorNote error={plan.error} />
      </div>
    )
  }
  if (!plan.data || !week) {
    return (
      <div className="mx-auto max-w-6xl p-6">
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  const sessionDate = (s: SessionDef): string | undefined =>
    s.fixed_date ?? assignments[s.id]
  const pool = week.sessions.filter((s) => !sessionDate(s))
  const scheduled = week.sessions.filter((s) => {
    const d = sessionDate(s)
    return d && days.includes(d)
  })

  const summary = scheduled
    .map((s) => `${DAY_NAMES[days.indexOf(sessionDate(s)!)]}: ${s.title}`)
    .join("; ")

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Weekly schedule</h1>
          <p className="text-sm text-muted-foreground">{plan.data.note}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={scheduled.length === 0}
          onClick={() =>
            navigate("/coach", {
              state: {
                prefill: `Here's how I've scheduled week ${week.week} (${week.focus}): ${summary}. Any concerns with this arrangement given my recent training and recovery?`,
              },
            })
          }
        >
          Review week with coach
        </Button>
      </div>

      {/* Week navigation */}
      <div className="flex items-center justify-between rounded-lg border bg-card px-4 py-3">
        <Button
          variant="ghost"
          size="sm"
          disabled={weekIdx === 0}
          onClick={() => setWeekIdx((i) => (i ?? 0) - 1)}
        >
          ‹ Week {week.week - 1 || ""}
        </Button>
        <div className="text-center">
          <div className="text-sm font-semibold">
            Week {week.week} of 8 · {week.start} → {isoAddDays(week.start, 6)}
          </div>
          <div className="text-xs text-muted-foreground">{week.focus}</div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          disabled={weekIdx === plan.data.weeks.length - 1}
          onClick={() => setWeekIdx((i) => (i ?? 0) + 1)}
        >
          Week {week.week + 1 <= 8 ? week.week + 1 : ""} ›
        </Button>
      </div>

      {/* Unscheduled pool */}
      <Card
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          const id = e.dataTransfer.getData("text/session")
          if (id) assign(id, null)
        }}
      >
        <CardContent className="pt-4">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-sm font-medium">
              To schedule ({pool.length} session{pool.length === 1 ? "" : "s"})
            </span>
            <span className="text-xs text-muted-foreground">
              Drag onto a day, or tap a day button · drop back here to unschedule
            </span>
          </div>
          {pool.length === 0 ? (
            <p className="py-2 text-sm text-muted-foreground">
              All sessions placed — nice. Drag any card back here to rethink.
            </p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {pool.map((s) => (
                <SessionCard
                  key={s.id}
                  session={s}
                  assignable
                  days={days}
                  onAssign={(i) => assign(s.id, days[i])}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Day board */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {days.map((date, i) => {
          const isToday = date === todayIso()
          const daySessions = week.sessions.filter((s) => sessionDate(s) === date)
          const dayRides = ridesByDay[date] ?? []
          return (
            <div
              key={date}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                const id = e.dataTransfer.getData("text/session")
                const session = week.sessions.find((s) => s.id === id)
                if (id && session && !session.fixed_date) assign(id, date)
              }}
              className={`flex min-h-36 flex-col gap-1.5 rounded-lg border p-2 ${
                isToday ? "border-primary/50 bg-accent/40" : "bg-card/50"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <span className={`text-xs font-semibold ${isToday ? "" : "text-muted-foreground"}`}>
                  {DAY_NAMES[i]}
                </span>
                <span className="text-[10px] text-muted-foreground">{date.slice(5)}</span>
              </div>
              {daySessions.map((s) => (
                <SessionCard key={s.id} session={s} compact onUnassign={() => assign(s.id, null)} />
              ))}
              {dayRides.map((r) => (
                <div
                  key={r.activity_id}
                  className="rounded-md border border-dashed px-2 py-1 text-[10px] text-muted-foreground"
                  title={r.name}
                >
                  ✓ rode {fmtNum(r.distance_km, 1)} km · load {fmtNum(r.training_load)}
                </div>
              ))}
            </div>
          )
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        Guidance: keep an easy day between the interval and tempo sessions, and protect the
        long ride — if life intervenes, drop anything but that one. Dashed entries are rides
        already recorded on Garmin. The race is locked to Sep 12.
      </p>
    </div>
  )
}
