import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Suggestions } from "./Suggestions";
import type { Suggestion } from "../api";

const openSug: Suggestion = {
  ticker: "AAPL",
  consolidated_score: 1.0,
  contributing_signals: { source: "insider_form4", n_contributing: 2 },
  created_at: "2024-01-12",
  latest_known: "2024-01-12",
  horizon: "long",
  status: "open",
  user_decision: null,
  decided_at: null,
};

afterEach(() => vi.restoreAllMocks());

it("renders an open suggestion with accept/reject controls", () => {
  render(<Suggestions suggestions={[openSug]} onDecided={() => {}} />);
  expect(screen.getByText("AAPL")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /accept/i })).toBeInTheDocument();
});

it("posts a decision and refetches when Accept is clicked", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal("fetch", fetchMock);
  const onDecided = vi.fn();

  render(<Suggestions suggestions={[openSug]} onDecided={onDecided} />);
  fireEvent.click(screen.getByRole("button", { name: /accept/i }));

  await waitFor(() => expect(onDecided).toHaveBeenCalled());
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toContain("/suggestions/AAPL/2024-01-12/decision");
  expect(opts.method).toBe("POST");
  expect(JSON.parse(opts.body).decision).toBe("accepted");
});

it("shows the recorded decision instead of buttons for decided rows", () => {
  const decided: Suggestion = {
    ...openSug,
    status: "accepted",
    user_decision: "accepted",
    decided_at: "2024-01-15",
  };
  render(<Suggestions suggestions={[decided]} onDecided={() => {}} />);
  // default filter is "open"; switch to "All" so the decided row shows
  fireEvent.click(screen.getByRole("button", { name: "All" }));
  expect(screen.queryByRole("button", { name: /accept/i })).not.toBeInTheDocument();
  // decided rows show the recorded decision (chip + footer) instead of controls
  expect(screen.getAllByText(/accepted/i).length).toBeGreaterThan(0);
});
