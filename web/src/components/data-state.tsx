import { useEffect, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api"

export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    fetcher().then(
      (d) => !cancelled && setData(d),
      (e) => !cancelled && setError(e),
    )
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, error, loading: data === null && error === null }
}

export function ErrorNote({ error }: { error: Error }) {
  const isAuth = error instanceof ApiError && error.status === 401
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
      <div className="mb-1 font-medium">{isAuth ? "Garmin session expired" : "Could not load data"}</div>
      <div className="text-muted-foreground">{error.message}</div>
    </div>
  )
}

export function ChartSkeleton({ height = 190 }: { height?: number }) {
  return <Skeleton className="w-full" style={{ height }} />
}
