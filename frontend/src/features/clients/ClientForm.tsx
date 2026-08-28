import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../api/http";
import { clientsApi } from "./api";
import type { ClientInput, RiskProfile } from "./types";

const EMPTY: ClientInput = {
  name: "",
  email: "",
  phone: "",
  risk_profile: "moderate",
  notes: "",
};

const RISK_OPTIONS: RiskProfile[] = ["conservative", "moderate", "aggressive"];

export function ClientForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState<ClientInput>(EMPTY);

  const create = useMutation({
    mutationFn: clientsApi.create,
    onSuccess: () => {
      setForm(EMPTY);
      onCreated();
    },
  });

  const fieldErrors =
    create.error instanceof ApiError && create.error.detail && typeof create.error.detail === "object"
      ? (create.error.detail as Record<string, string[]>)
      : {};

  function update<K extends keyof ClientInput>(key: K, value: ClientInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(form);
      }}
    >
      <label>
        Name
        <input
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
          required
        />
        {fieldErrors.name && <span className="error">{fieldErrors.name[0]}</span>}
      </label>

      <label>
        Email
        <input
          type="email"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          required
        />
        {fieldErrors.email && <span className="error">{fieldErrors.email[0]}</span>}
      </label>

      <label>
        Phone
        <input value={form.phone} onChange={(e) => update("phone", e.target.value)} />
      </label>

      <label>
        Risk profile
        <select
          value={form.risk_profile}
          onChange={(e) => update("risk_profile", e.target.value as RiskProfile)}
        >
          {RISK_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <button type="submit" disabled={create.isPending}>
        {create.isPending ? "Saving…" : "Create client"}
      </button>

      {create.isError && Object.keys(fieldErrors).length === 0 && (
        <p className="error">Could not create client.</p>
      )}
    </form>
  );
}
