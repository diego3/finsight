import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../api/http";
import { clientsApi } from "./api";
import { ClientForm } from "./ClientForm";
import type { Client } from "./types";

const RISK_LABELS: Record<Client["risk_profile"], string> = {
  conservative: "Conservative",
  moderate: "Moderate",
  aggressive: "Aggressive",
};

export function ClientsPage() {
  const queryClient = useQueryClient();

  const clients = useQuery({
    queryKey: ["clients"],
    queryFn: clientsApi.list,
  });

  const removeClient = useMutation({
    mutationFn: clientsApi.remove,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
  });

  return (
    <div className="clients">
      <section className="clients__form">
        <h2>New client</h2>
        <ClientForm
          onCreated={() => queryClient.invalidateQueries({ queryKey: ["clients"] })}
        />
      </section>

      <section className="clients__list">
        <h2>Clients</h2>

        {clients.isPending && <p className="muted">Loading…</p>}

        {clients.isError && (
          <p className="error">
            Failed to load clients
            {clients.error instanceof ApiError ? ` (${clients.error.status})` : ""}.
          </p>
        )}

        {clients.data?.results.length === 0 && (
          <p className="muted">No clients yet. Create the first one.</p>
        )}

        {clients.data && clients.data.results.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Risk</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {clients.data.results.map((client) => (
                <tr key={client.id}>
                  <td>{client.name}</td>
                  <td>{client.email}</td>
                  <td>{client.phone || "—"}</td>
                  <td>{RISK_LABELS[client.risk_profile]}</td>
                  <td>
                    <button
                      className="link-danger"
                      onClick={() => removeClient.mutate(client.id)}
                      disabled={removeClient.isPending}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
