import type { ChatSession } from "../types";
import { generateId } from "./id";

export const STORAGE_KEY = "zlanze-ai-advisor-sessions-v1";
export const ACTIVE_KEY = "zlanze-ai-advisor-active-session-v1";

export function createSession(): ChatSession {
  const now = new Date().toISOString();
  return {
    id: generateId(),
    title: "New conversation",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

export function loadSessions(): ChatSession[] {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (!value) return [];
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap((candidate): ChatSession[] => {
      if (!candidate || typeof candidate !== "object") return [];
      const record = candidate as Partial<ChatSession>;
      if (typeof record.id !== "string") return [];
      const now = new Date().toISOString();
      const messages = Array.isArray(record.messages)
        ? record.messages.filter(
            (item): item is ChatSession["messages"][number] =>
              Boolean(
                item &&
                  typeof item === "object" &&
                  (item.role === "user" || item.role === "assistant") &&
                  typeof item.content === "string",
              ),
          )
        : [];
      return [{
        id: record.id,
        title: typeof record.title === "string" ? record.title : "Conversation",
        createdAt: typeof record.createdAt === "string" ? record.createdAt : now,
        updatedAt: typeof record.updatedAt === "string" ? record.updatedAt : now,
        messages: messages.map((item) => ({
          ...item,
          id: typeof item.id === "string" ? item.id : generateId(),
          createdAt: typeof item.createdAt === "string" ? item.createdAt : now,
        })),
      }];
    });
  } catch {
    return [];
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // Storage can be blocked or full. Chat must remain usable in memory.
  }
}

export function titleFromMessage(message: string): string {
  const clean = message.trim().replace(/\s+/g, " ");
  if (clean.length <= 38) return clean;
  return `${clean.slice(0, 38).trim()}…`;
}
