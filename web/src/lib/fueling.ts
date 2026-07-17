// Fueling plan engine.
//
// Guidelines encoded here (sources in README/architecture doc):
// - Carbs: <1h rides need ~0-30 g/h; 1-2h → 30-60; 2-3h → 60-90; 3h+ → 90+.
//   Above ~60 g/h requires dual-source carbs (glucose+fructose); above ~90 g/h
//   requires a trained gut. Practical ceiling 120 g/h.
// - Fluids: anchor to sweat rate; plan ~80% replacement, never exceed sweat loss.
// - Sodium: sweat sodium concentration typically 230-1600 mg/L (default ~950).

export type Intensity = "endurance" | "tempo" | "race"
export type ProductKind = "drink" | "gel" | "chew" | "food"

export interface Product {
  id: string
  name: string
  kind: ProductKind
  carbs_g: number
  sodium_mg: number
  /** serving description, e.g. "500 ml bottle" or "1 gel" */
  serving: string
  /** ml of fluid per serving (drinks only) */
  fluid_ml: number
  /** glucose:fructose style ratio label, if known */
  ratio?: string
  dual_source: boolean
  est_cost_usd?: number
  custom?: boolean
}

// Nutrition values are approximate, from public product pages.
export const PRODUCTS: Product[] = [
  { id: "maurten160", name: "Maurten Drink Mix 160", kind: "drink", carbs_g: 40, sodium_mg: 160, serving: "500 ml bottle", fluid_ml: 500, ratio: "1:0.8", dual_source: true, est_cost_usd: 3.5 },
  { id: "maurten320", name: "Maurten Drink Mix 320", kind: "drink", carbs_g: 80, sodium_mg: 200, serving: "500 ml bottle", fluid_ml: 500, ratio: "1:0.8", dual_source: true, est_cost_usd: 5.5 },
  { id: "betafuel80", name: "SiS Beta Fuel 80", kind: "drink", carbs_g: 80, sodium_mg: 220, serving: "500 ml bottle", fluid_ml: 500, ratio: "1:0.8", dual_source: true, est_cost_usd: 4.0 },
  { id: "skratch", name: "Skratch Sport Hydration", kind: "drink", carbs_g: 21, sodium_mg: 380, serving: "500 ml bottle", fluid_ml: 500, dual_source: false, est_cost_usd: 1.8 },
  {
    id: "homemade",
    name: "Homemade mix (malto + fructose + salt)",
    kind: "drink",
    carbs_g: 60,
    sodium_mg: 400,
    serving: "500 ml bottle (~50g malto + 25g fructose + 1g salt)",
    fluid_ml: 500,
    ratio: "2:1",
    dual_source: true,
    est_cost_usd: 0.7,
  },
  { id: "maurtengel", name: "Maurten Gel 100", kind: "gel", carbs_g: 25, sodium_mg: 20, serving: "1 gel", fluid_ml: 0, ratio: "1:0.8", dual_source: true, est_cost_usd: 4.0 },
  { id: "betafuelgel", name: "SiS Beta Fuel Gel", kind: "gel", carbs_g: 40, sodium_mg: 10, serving: "1 gel", fluid_ml: 0, ratio: "1:0.8", dual_source: true, est_cost_usd: 3.0 },
  { id: "gugel", name: "GU Energy Gel", kind: "gel", carbs_g: 22, sodium_mg: 60, serving: "1 gel", fluid_ml: 0, dual_source: false, est_cost_usd: 1.8 },
  { id: "clifbloks", name: "Clif Bloks (3 pieces)", kind: "chew", carbs_g: 24, sodium_mg: 50, serving: "3 bloks", fluid_ml: 0, dual_source: false, est_cost_usd: 1.5 },
  { id: "banana", name: "Banana", kind: "food", carbs_g: 27, sodium_mg: 1, serving: "1 medium", fluid_ml: 0, dual_source: true, est_cost_usd: 0.4 },
  { id: "ricecake", name: "Rice cake (homemade)", kind: "food", carbs_g: 35, sodium_mg: 100, serving: "1 cake", fluid_ml: 0, dual_source: false, est_cost_usd: 0.5 },
]

export interface FuelingInputs {
  duration_min: number
  intensity: Intensity
  carbs_per_h: number
  sweat_rate_l_h: number
  sodium_loss_mg_l: number
  drink_id: string
  solid_id: string | null
  interval_min: number
  custom_products: Product[]
}

export interface ScheduleRow {
  time_min: number // -1 = pre-start
  label: string
  items: string[]
  carbs_g: number
  fluid_ml: number
  sodium_mg: number
}

export interface Warning {
  level: "info" | "warn"
  text: string
}

export interface FuelingPlan {
  rows: ScheduleRow[]
  totals: { carbs_g: number; fluid_ml: number; sodium_mg: number; est_cost_usd: number }
  perHour: { carbs_g: number; fluid_ml: number; sodium_mg: number }
  targets: { carbs_g: number; fluid_ml: number; sodium_mg: number; sweat_loss_ml: number }
  prep: string[]
  warnings: Warning[]
  bottles: number
  solid_servings: number
}

export function recommendedCarbsPerHour(duration_min: number, intensity: Intensity): number {
  const h = duration_min / 60
  let base: number
  if (h < 1) base = 25
  else if (h < 2) base = 50
  else if (h < 3) base = 70
  else base = 90
  if (intensity === "race") base += 15
  if (intensity === "endurance") base -= 10
  return Math.max(20, Math.min(120, Math.round(base / 5) * 5))
}

export function estimateSweatRate(temp: "cool" | "mild" | "warm" | "hot", intensity: Intensity): number {
  const byTemp = { cool: 0.6, mild: 0.9, warm: 1.2, hot: 1.6 }[temp]
  const bump = intensity === "race" ? 0.2 : intensity === "tempo" ? 0.1 : 0
  return Math.round((byTemp + bump) * 10) / 10
}

function findProduct(id: string, custom: Product[]): Product | undefined {
  return [...PRODUCTS, ...custom].find((p) => p.id === id)
}

export function computePlan(inputs: FuelingInputs): FuelingPlan {
  const warnings: Warning[] = []
  const drink = findProduct(inputs.drink_id, inputs.custom_products)
  const solid = inputs.solid_id ? findProduct(inputs.solid_id, inputs.custom_products) : undefined

  const durH = inputs.duration_min / 60
  const targetCarbs = Math.round(inputs.carbs_per_h * durH)
  const sweatLoss = Math.round(inputs.sweat_rate_l_h * durH * 1000)
  // Plan ~80% sweat replacement, capped at 1 L/h of practical intake.
  const targetFluid = Math.round(Math.min(sweatLoss * 0.8, durH * 1000))
  const targetSodium = Math.round((sweatLoss / 1000) * inputs.sodium_loss_mg_l)

  // --- Fluids: bottles of the chosen drink spread across the ride ---
  const bottleMl = drink?.fluid_ml || 500
  const bottles = drink ? Math.max(1, Math.round(targetFluid / bottleMl)) : 0
  const fluidPlanned = bottles * bottleMl
  const drinkCarbs = drink ? bottles * drink.carbs_g : 0
  const drinkSodium = drink ? bottles * drink.sodium_mg : 0

  // --- Remaining carbs from the solid/gel choice ---
  const carbsRemaining = Math.max(0, targetCarbs - drinkCarbs)
  const solidServings = solid && carbsRemaining > 0 ? Math.round(carbsRemaining / solid.carbs_g) : 0
  const solidCarbs = solid ? solidServings * solid.carbs_g : 0
  const solidSodium = solid ? solidServings * solid.sodium_mg : 0

  const totalCarbs = drinkCarbs + solidCarbs
  const totalSodium = drinkSodium + solidSodium

  // --- Timeline ---
  const rows: ScheduleRow[] = []
  const interval = inputs.interval_min
  const slots: number[] = []
  for (let t = interval; t < inputs.duration_min - interval / 2; t += interval) slots.push(t)

  const drinkPerSlot = slots.length > 0 ? Math.round(fluidPlanned / (slots.length + 1) / 10) * 10 : 0
  const drinkConcentration = drink && drink.fluid_ml > 0 ? drink.carbs_g / drink.fluid_ml : 0

  // Spread solid servings evenly across the ride.
  const solidAt = new Set<number>()
  if (solidServings > 0 && slots.length > 0) {
    for (let i = 0; i < solidServings; i++) {
      const idx = Math.min(slots.length - 1, Math.round(((i + 0.5) / solidServings) * slots.length))
      solidAt.add(slots[idx])
    }
  }

  if (drink) {
    rows.push({
      time_min: -1,
      label: "Pre-start",
      items: [`Drink ~${drinkPerSlot} ml of ${drink.name} in the last 15 min`],
      carbs_g: Math.round(drinkPerSlot * drinkConcentration),
      fluid_ml: drinkPerSlot,
      sodium_mg: Math.round((drinkPerSlot / (drink.fluid_ml || 500)) * drink.sodium_mg),
    })
  }

  let solidCount = 0
  for (const t of slots) {
    const items: string[] = []
    let carbs = 0
    let fluid = 0
    let sodium = 0
    if (drink && drinkPerSlot > 0) {
      items.push(`Drink ~${drinkPerSlot} ml of ${drink.name}`)
      carbs += drinkPerSlot * drinkConcentration
      fluid += drinkPerSlot
      sodium += (drinkPerSlot / (drink.fluid_ml || 500)) * drink.sodium_mg
    }
    if (solid && solidAt.has(t)) {
      solidCount += 1
      items.push(`Take ${solid.serving} of ${solid.name}`)
      carbs += solid.carbs_g
      sodium += solid.sodium_mg
    }
    rows.push({
      time_min: t,
      label: fmtClock(t),
      items,
      carbs_g: Math.round(carbs),
      fluid_ml: Math.round(fluid),
      sodium_mg: Math.round(sodium),
    })
  }

  // --- Prep + cost ---
  const cost =
    (drink?.est_cost_usd ?? 0) * bottles + (solid?.est_cost_usd ?? 0) * solidServings
  const prep: string[] = []
  if (drink) {
    prep.push(
      `Prepare ${bottles} × ${drink.serving} of ${drink.name} (${bottles * bottleMl} ml, ${drinkCarbs} g carbs).`,
    )
    if (drink.ratio) {
      prep.push(
        `${drink.name} uses a ${drink.ratio} glucose:fructose-style blend — dual transporters (SGLT1 + GLUT5) let you absorb well beyond the ~60 g/h single-source ceiling.`,
      )
    }
  }
  if (solid && solidServings > 0) {
    prep.push(`Pack ${solidServings} × ${solid.name} (${solidCarbs} g carbs).`)
  }
  prep.push(`Eat/drink every ${interval} minutes — set a timer on the Edge.`)

  // --- Warnings ---
  if (inputs.carbs_per_h > 90) {
    warnings.push({
      level: "warn",
      text: `${inputs.carbs_per_h} g/h is elite-level intake. Only race with this after progressive gut training — start at 60-70 g/h and build up over weeks.`,
    })
  } else if (inputs.carbs_per_h > 60 && drink && !drink.dual_source && !solid?.dual_source) {
    warnings.push({
      level: "warn",
      text: "Above ~60 g/h you need dual-source carbs (glucose + fructose). Your selected products are single-source — expect GI trouble at this intake.",
    })
  }
  if (fluidPlanned > sweatLoss && sweatLoss > 0) {
    warnings.push({
      level: "warn",
      text: `Planned fluid (${fluidPlanned} ml) exceeds estimated sweat loss (${sweatLoss} ml). Over-drinking risks hyponatremia — cut a bottle or reduce per-slot volume.`,
    })
  }
  const sodiumShortfall = targetSodium - totalSodium
  if (sodiumShortfall > 500) {
    warnings.push({
      level: "info",
      text: `Sodium is ~${Math.round(sodiumShortfall)} mg short of estimated losses (${targetSodium} mg). For rides over ~3 h in heat, consider electrolyte capsules or a saltier mix.`,
    })
  }
  if (drinkConcentration > 0.12) {
    warnings.push({
      level: "info",
      text: `Your drink is ~${Math.round(drinkConcentration * 100)}% carbohydrate — concentrated mixes empty slower from the stomach; chase gels/mix with plain sips if available.`,
    })
  }
  if (Math.abs(totalCarbs - targetCarbs) > targetCarbs * 0.15 && targetCarbs > 0) {
    warnings.push({
      level: "info",
      text: `Plan delivers ${totalCarbs} g vs the ${targetCarbs} g target — adjust bottle count, product, or add/remove a serving.`,
    })
  }

  return {
    rows,
    totals: {
      carbs_g: totalCarbs,
      fluid_ml: fluidPlanned,
      sodium_mg: Math.round(totalSodium),
      est_cost_usd: Math.round(cost * 100) / 100,
    },
    perHour: {
      carbs_g: Math.round(totalCarbs / durH),
      fluid_ml: Math.round(fluidPlanned / durH),
      sodium_mg: Math.round(totalSodium / durH),
    },
    targets: { carbs_g: targetCarbs, fluid_ml: targetFluid, sodium_mg: targetSodium, sweat_loss_ml: sweatLoss },
    prep,
    warnings,
    bottles,
    solid_servings: solidCount,
  }
}

export function fmtClock(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return `${h}:${String(m).padStart(2, "0")}`
}

export function planSummaryForCoach(inputs: FuelingInputs, plan: FuelingPlan): string {
  const drink = findProduct(inputs.drink_id, inputs.custom_products)
  const solid = inputs.solid_id ? findProduct(inputs.solid_id, inputs.custom_products) : undefined
  return (
    `Please review this fueling plan for a ${fmtClock(inputs.duration_min)} ${inputs.intensity} ride: ` +
    `${inputs.carbs_per_h} g/h carbs target via ${plan.bottles}× ${drink?.name ?? "no drink"}` +
    (solid && plan.solid_servings > 0 ? ` + ${plan.solid_servings}× ${solid.name}` : "") +
    `, total ${plan.totals.carbs_g} g carbs / ${plan.totals.fluid_ml} ml fluid / ${plan.totals.sodium_mg} mg sodium ` +
    `(sweat rate ${inputs.sweat_rate_l_h} L/h, sodium loss ${inputs.sodium_loss_mg_l} mg/L). ` +
    `Does this fit my training and the Whistler plan, and would you change anything?`
  )
}
