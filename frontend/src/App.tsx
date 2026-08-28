import { NavLink, Route, Routes } from "react-router-dom";

import { ClientsPage } from "./features/clients/ClientsPage";

export function App() {
  return (
    <div className="app">
      <header className="app__header">
        <span className="app__brand">FinSight</span>
        <nav>
          <NavLink to="/clients">Clients</NavLink>
        </nav>
      </header>
      <main className="app__main">
        <Routes>
          <Route path="/" element={<ClientsPage />} />
          <Route path="/clients" element={<ClientsPage />} />
        </Routes>
      </main>
    </div>
  );
}
