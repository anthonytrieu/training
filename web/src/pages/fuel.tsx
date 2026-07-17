import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  PRODUCTS,
  computePlan,
  estimateSweatRate,
  fmtClock,
  planSummaryForCoach,
  recommendedCarbsPerHour,
  type FuelingInputs,
  type Intensity,
} from "@/lib/fueling"
import { fmtNum } from "@/lib/format"

const STORAGE_KEY = "garmin-coach-fuel-plans"

const DEFAULTS: FuelingInputs = {
  duration_min: 180,
  intensity: "tempo",
  carbs_per_h: recommendedCarbsPerHour(180, "tempo"),
  sweat_rate_l_h: 1.0,
  sodium_loss_mg_l: 950,
  drink_id: "maurten160",
  solid_id: "maurtengel",
  interval_min: 20,
  custom_products: [],
}

// From training/whistler-gran-fondo-plan.md: ~122 km, 4.5-5 h at tempo effort.
const WHISTLER: Partial<FuelingInputs> = {
  duration_min: 285,
  intensity: "tempo",
  carbs_per_h: 80,
  drink_id: "maurten160",
  solid_id: "maurtengel",
}

interface SavedPlan {
  name: string
  inputs: FuelingInputs
}

function loadSaved(): SavedPlan[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]")
  } catch {
    return []
  }
}

export default function Fuel() {
  const navigate = useNavigate()
  const [inputs, setInputs] = useState<FuelingInputs>(DEFAULTS)
  const [carbsTouched, setCarbsTouched] = useState(false)
  const [saved, setSaved] = useState<SavedPlan[]>(loadSaved)
  const [planName, setPlanName] = useState("")

  const set = <K extends keyof FuelingInputs>(key: K, value: FuelingInputs[K]) =>
    setInputs((s) => ({ ...s, [key]: value }))

  // Track the recommendation until the user overrides the carb slider.
  useEffect(() => {
    if (!carbsTouched) {
      set("carbs_per_h", recommendedCarbsPerHour(inputs.duration_min, inputs.intensity))
    }
  }, [inputs.duration_min, inputs.intensity, carbsTouched])

  const plan = useMemo(() => computePlan(inputs), [inputs])
  const drinks = PRODUCTS.filter((p) => p.kind === "drink")
  const solids = PRODUCTS.filter((p) => p.kind !== "drink")

  function savePlan() {
    const name = planName.trim() || `${fmtClock(inputs.duration_min)} ${inputs.intensity}`
    const next = [...saved.filter((p) => p.name !== name), { name, inputs }]
    setSaved(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setPlanName("")
  }

  const hours = Math.floor(inputs.duration_min / 60)
  const mins = inputs.duration_min % 60

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Fueling planner</h1>
          <p className="text-sm text-muted-foreground">
            Carbs, fluids and sodium on a timer — product numbers are approximate,
            practice the plan in training before racing it.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setCarbsTouched(true)
            setInputs((s) => ({ ...s, ...WHISTLER }))
          }}
        >
          ⛰ Whistler Gran Fondo preset
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* Inputs */}
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Ride</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="mb-1.5 text-xs">Hours</Label>
                  <Input
                    type="number"
                    min={0}
                    max={12}
                    value={hours}
                    onChange={(e) =>
                      set("duration_min", Math.max(20, Number(e.target.value) * 60 + mins))
                    }
                  />
                </div>
                <div>
                  <Label className="mb-1.5 text-xs">Minutes</Label>
                  <Input
                    type="number"
                    min={0}
                    max={59}
                    step={5}
                    value={mins}
                    onChange={(e) =>
                      set("duration_min", Math.max(20, hours * 60 + Number(e.target.value)))
                    }
                  />
                </div>
              </div>
              <div>
                <Label className="mb-1.5 text-xs">Intensity</Label>
                <Select
                  value={inputs.intensity}
                  onValueChange={(v) => v && set("intensity", v as Intensity)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue>
                      {{ endurance: "Endurance (Z2)", tempo: "Tempo / fondo pace (Z3)", race: "Race / hard" }[inputs.intensity]}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="endurance">Endurance (Z2)</SelectItem>
                    <SelectItem value="tempo">Tempo / fondo pace (Z3)</SelectItem>
                    <SelectItem value="race">Race / hard</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <Label className="text-xs">Carb target</Label>
                  <span className="text-sm font-semibold tabular-nums">
                    {inputs.carbs_per_h} g/h
                  </span>
                </div>
                <Slider
                  value={[inputs.carbs_per_h]}
                  min={20}
                  max={120}
                  step={5}
                  onValueChange={(v) => {
                    setCarbsTouched(true)
                    set("carbs_per_h", Array.isArray(v) ? v[0] : v)
                  }}
                />
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Recommended for this ride:{" "}
                  {recommendedCarbsPerHour(inputs.duration_min, inputs.intensity)} g/h
                  {inputs.carbs_per_h > 90 && " · >90 needs gut training"}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Sweat & sodium</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <Label className="text-xs">Sweat rate</Label>
                  <span className="text-sm font-semibold tabular-nums">
                    {inputs.sweat_rate_l_h.toFixed(1)} L/h
                  </span>
                </div>
                <Slider
                  value={[inputs.sweat_rate_l_h]}
                  min={0.3}
                  max={2.5}
                  step={0.1}
                  onValueChange={(v) => set("sweat_rate_l_h", Array.isArray(v) ? v[0] : v)}
                />
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(["cool", "mild", "warm", "hot"] as const).map((t) => (
                    <Button
                      key={t}
                      variant="outline"
                      size="sm"
                      className="h-7 px-2 text-xs capitalize"
                      onClick={() => set("sweat_rate_l_h", estimateSweatRate(t, inputs.intensity))}
                    >
                      {t}
                    </Button>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Best measured: weigh yourself before/after a 1 h ride without drinking —
                  1 kg lost ≈ 1 L/h.
                </p>
              </div>
              <div>
                <Label className="mb-1.5 text-xs">Sodium loss (mg/L of sweat)</Label>
                <Input
                  type="number"
                  min={200}
                  max={1800}
                  step={50}
                  value={inputs.sodium_loss_mg_l}
                  onChange={(e) => set("sodium_loss_mg_l", Number(e.target.value))}
                />
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Typical range 230–1600; salty-sweater signs (white kit stains, cramps) → 1200+.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Products</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div>
                <Label className="mb-1.5 text-xs">Drink mix</Label>
                <Select value={inputs.drink_id} onValueChange={(v) => v && set("drink_id", v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue>{drinks.find((p) => p.id === inputs.drink_id)?.name}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {drinks.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name} ({p.carbs_g}g C / {p.sodium_mg}mg Na per bottle)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="mb-1.5 text-xs">Gels / solids (tops up carbs)</Label>
                <Select
                  value={inputs.solid_id ?? "none"}
                  onValueChange={(v) => v != null && set("solid_id", v === "none" ? null : v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue>
                      {inputs.solid_id
                        ? solids.find((p) => p.id === inputs.solid_id)?.name
                        : "None — drink only"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None — drink only</SelectItem>
                    {solids.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name} ({p.carbs_g}g C)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="mb-1.5 text-xs">Reminder interval</Label>
                <Select
                  value={String(inputs.interval_min)}
                  onValueChange={(v) => v && set("interval_min", Number(v))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue>{`Every ${inputs.interval_min} min`}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">Every 15 min</SelectItem>
                    <SelectItem value="20">Every 20 min</SelectItem>
                    <SelectItem value="30">Every 30 min</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Saved plans</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Plan name…"
                  value={planName}
                  onChange={(e) => setPlanName(e.target.value)}
                />
                <Button onClick={savePlan}>Save</Button>
              </div>
              {saved.length > 0 && (
                <div className="flex flex-col gap-1">
                  {saved.map((p) => (
                    <div key={p.name} className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 flex-1 justify-start px-2 text-xs"
                        onClick={() => {
                          setCarbsTouched(true)
                          setInputs(p.inputs)
                        }}
                      >
                        {p.name}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-muted-foreground"
                        onClick={() => {
                          const next = saved.filter((s) => s.name !== p.name)
                          setSaved(next)
                          localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
                        }}
                      >
                        ✕
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Plans are saved in this browser only.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Output */}
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Carbs / h", value: `${plan.perHour.carbs_g} g`, target: `${inputs.carbs_per_h} g` },
              { label: "Fluid / h", value: `${plan.perHour.fluid_ml} ml`, target: `${Math.round(plan.targets.fluid_ml / (inputs.duration_min / 60))} ml` },
              { label: "Sodium / h", value: `${plan.perHour.sodium_mg} mg`, target: `${Math.round(plan.targets.sodium_mg / (inputs.duration_min / 60))} mg` },
              { label: "Est. cost", value: `$${fmtNum(plan.totals.est_cost_usd, 2)}`, target: null },
            ].map((tile) => (
              <Card key={tile.label} className="gap-1 py-3">
                <CardContent className="px-4">
                  <div className="text-xs text-muted-foreground">{tile.label}</div>
                  <div className="text-lg font-semibold tracking-tight">{tile.value}</div>
                  {tile.target && (
                    <div className="text-xs text-muted-foreground">target {tile.target}</div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-sm">Fueling schedule</CardTitle>
              <div className="flex gap-2 print:hidden">
                <Button variant="outline" size="sm" onClick={() => window.print()}>
                  Print / PDF
                </Button>
                <Button
                  size="sm"
                  onClick={() =>
                    navigate("/coach", { state: { prefill: planSummaryForCoach(inputs, plan) } })
                  }
                >
                  Review with coach
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20">Time</TableHead>
                    <TableHead>Fuel</TableHead>
                    <TableHead className="text-right">Carbs (g)</TableHead>
                    <TableHead className="text-right">Fluid (ml)</TableHead>
                    <TableHead className="text-right">Sodium (mg)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {plan.rows.map((row) => (
                    <TableRow key={row.time_min}>
                      <TableCell className="font-medium tabular-nums">
                        {row.time_min < 0 ? "Pre-start" : row.label}
                      </TableCell>
                      <TableCell className="whitespace-normal text-sm">
                        {row.items.join(" · ")}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{row.carbs_g}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.fluid_ml}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.sodium_mg}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="font-medium">
                    <TableCell>Total</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {plan.bottles} bottles
                      {plan.solid_servings > 0 && ` · ${plan.solid_servings} gels/solids`}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{plan.totals.carbs_g}</TableCell>
                    <TableCell className="text-right tabular-nums">{plan.totals.fluid_ml}</TableCell>
                    <TableCell className="text-right tabular-nums">{plan.totals.sodium_mg}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Playbook</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {plan.prep.map((p, i) => (
                <div key={i} className="flex gap-2 text-sm">
                  <span className="text-muted-foreground">⚡</span>
                  <span>{p}</span>
                </div>
              ))}
              {plan.warnings.map((w, i) => (
                <div key={i} className="flex gap-2 text-sm">
                  <Badge
                    variant={w.level === "warn" ? "destructive" : "secondary"}
                    className="mt-0.5 h-fit shrink-0"
                  >
                    {w.level === "warn" ? "Warning" : "Note"}
                  </Badge>
                  <span className={w.level === "warn" ? "" : "text-muted-foreground"}>
                    {w.text}
                  </span>
                </div>
              ))}
              <p className="mt-2 text-xs text-muted-foreground">
                Estimated sweat loss for this ride: {fmtNum(plan.targets.sweat_loss_ml)} ml.
                Guidelines: 30–60 g/h under 2 h, 60–90 g/h for 2–3 h, 90+ g/h beyond 3 h with
                dual-source carbs. This is planning guidance, not medical advice.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
