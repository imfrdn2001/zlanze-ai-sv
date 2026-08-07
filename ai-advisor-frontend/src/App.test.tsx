import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

it("creates a session and renders an advisor response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        chat_id: "test",
        response: "I found five matching freelancers.",
        intents: ["find_developer"],
        data: {
          developers: [],
          cost: null,
          time: null,
          technology_used: ["react"],
        },
      }),
    }),
  );

  render(<App />);
  fireEvent.change(screen.getByLabelText("Message the advisor"), {
    target: { value: "Find a React developer" },
  });
  fireEvent.click(screen.getByLabelText("Send message"));

  expect(
    screen.getByText("Find a React developer", { selector: "p" }),
  ).toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getByText("I found five matching freelancers."),
    ).toBeInTheDocument(),
  );
  expect(screen.getByText("zLanze AI recommendation")).toBeInTheDocument();
});
