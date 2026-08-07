import type { AdvisorResponse } from "../types";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8002").replace(
  /\/$/,
  "",
);

export async function sendMessage(
  chatId: string,
  query: string,
  signal?: AbortSignal,
): Promise<AdvisorResponse> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, query }),
    signal,
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : "The advisor could not answer right now.";
    throw new Error(detail);
  }
  return payload as AdvisorResponse;
}
