import { useEffect, useState } from "react"
import { NavLink, Outlet } from "react-router-dom"
import { Button } from "@/components/ui/button"

const NAV = [
  { to: "/", label: "Dashboard", icon: "◫" },
  { to: "/plan", label: "Plan", icon: "▤" },
  { to: "/schedule", label: "Schedule", icon: "▦" },
  { to: "/fuel", label: "Fuel", icon: "◒" },
  { to: "/coach", label: "Coach", icon: "◍" },
]

function useDarkMode() {
  const [dark, setDark] = useState(
    () =>
      localStorage.theme === "dark" ||
      (!("theme" in localStorage) &&
        window.matchMedia("(prefers-color-scheme: dark)").matches),
  )
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    localStorage.theme = dark ? "dark" : "light"
  }, [dark])
  return { dark, toggle: () => setDark((d) => !d) }
}

export default function Layout() {
  const { dark, toggle } = useDarkMode()
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-52 shrink-0 flex-col border-r bg-sidebar px-3 py-5 sm:flex">
        <div className="mb-6 px-2">
          <div className="text-sm font-semibold tracking-tight">garmin-coach</div>
          <div className="text-xs text-muted-foreground">Whistler · Sep 12</div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `rounded-md px-2 py-1.5 text-sm transition-colors ${
                  isActive
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                }`
              }
            >
              <span className="mr-2 opacity-60">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-2">
          <Button variant="ghost" size="sm" onClick={toggle} className="w-full justify-start">
            {dark ? "☀ Light mode" : "☾ Dark mode"}
          </Button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b px-4 py-2 sm:hidden">
          <span className="text-sm font-semibold">garmin-coach</span>
          <nav className="flex gap-3 text-sm">
            {NAV.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/"} className="text-muted-foreground [&.active]:text-foreground">
                {i.label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
