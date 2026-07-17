import { BrowserRouter, Route, Routes } from "react-router-dom"
import Layout from "@/components/layout"
import Coach from "@/pages/coach"
import Dashboard from "@/pages/dashboard"
import Plan from "@/pages/plan"
import RideDetail from "@/pages/ride-detail"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/rides/:id" element={<RideDetail />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/coach" element={<Coach />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
