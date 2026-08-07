import { beforeEach, describe, expect, it } from "vitest";
import {
  createSession,
  loadSessions,
  saveSessions,
  STORAGE_KEY,
  titleFromMessage,
} from "./sessions";

describe("session storage", () => {
  beforeEach(() => localStorage.clear());

  it("creates and persists a chat session", () => {
    const session = createSession();
    saveSessions([session]);
    expect(loadSessions()).toEqual([session]);
  });

  it("repairs legacy sessions with missing message arrays", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ id: "legacy", title: "Old chat" }]),
    );

    const sessions = loadSessions();

    expect(sessions).toHaveLength(1);
    expect(sessions[0].messages).toEqual([]);
    expect(sessions[0].createdAt).toBeTruthy();
  });

  it("creates a concise title from the first message", () => {
    expect(titleFromMessage("  Build   me a portfolio  ")).toBe(
      "Build me a portfolio",
    );
    expect(titleFromMessage("a".repeat(50))).toHaveLength(39);
  });
});
