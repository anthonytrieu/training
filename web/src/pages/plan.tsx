import ReactMarkdown from "react-markdown"
import { ChartSkeleton, ErrorNote, useApi } from "@/components/data-state"
import { api } from "@/lib/api"

export default function Plan() {
  const plan = useApi(() => api.plan())
  return (
    <div className="mx-auto max-w-3xl p-6">
      {plan.error && <ErrorNote error={plan.error} />}
      {plan.loading && <ChartSkeleton height={480} />}
      {plan.data && (
        <article className="prose prose-sm dark:prose-invert max-w-none prose-table:text-xs prose-headings:tracking-tight">
          <ReactMarkdown>{plan.data.markdown}</ReactMarkdown>
        </article>
      )}
    </div>
  )
}
