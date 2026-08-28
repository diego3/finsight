import { http } from "../../api/http";
import type { Client, ClientInput, Paginated } from "./types";

export const clientsApi = {
  list: () => http<Paginated<Client>>("/clients/"),
  create: (input: ClientInput) =>
    http<Client>("/clients/", { method: "POST", body: JSON.stringify(input) }),
  remove: (id: number) => http<void>(`/clients/${id}/`, { method: "DELETE" }),
};
