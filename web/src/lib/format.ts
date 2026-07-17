export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "–"
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.round((total % 3600) / 60)
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–"
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "–"
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  })
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v == null) return "–"
  return v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function titleCase(phrase: string | null | undefined): string {
  if (!phrase) return "–"
  return phrase
    .replace(/_\d+$/, "")
    .split("_")
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(" ")
}
