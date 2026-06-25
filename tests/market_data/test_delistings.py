"""Tests for the FREE delisting list (SEC EDGAR full-text search + CSV cache).

The fetch parsing is exercised against a captured EDGAR FTS JSON shape; the
network is behind an injected fetcher, so no live call is made. The CSV
round-trip proves the offline-first path the eval/CLI actually use.
"""
import datetime as dt
import json

from signal_trader.market_data.delistings import (
    DelistingEvent,
    fetch_delistings,
    load_delistings_csv,
    parse_fts_hits,
    save_delistings_csv,
)


def _hit(display_names, file_date, form="25-NSE"):
    return {"_source": {"display_names": display_names, "file_date": file_date, "form": form}}


def test_parse_extracts_ticker_and_filing_date_from_display_names():
    hits = [_hit(["Acme Corp.  (ACME)  (CIK 0000123)"], "2024-06-28")]
    events = parse_fts_hits(hits)
    assert events == [DelistingEvent(ticker="ACME", delisted_known=dt.date(2024, 6, 28))]


def test_parse_takes_first_ticker_when_multiple_classes_listed():
    hits = [_hit(["Oxford Lane Capital Corp.  (OXLC, OXLCI, OXLCL)  (CIK 0001495222)"],
                 "2024-01-15")]
    events = parse_fts_hits(hits)
    assert events == [DelistingEvent(ticker="OXLC", delisted_known=dt.date(2024, 1, 15))]


def test_parse_skips_hits_with_no_resolvable_ticker():
    # CIK-only parenthetical (no ticker mapping) -> skipped, never fabricated.
    hits = [_hit(["Some Defunct LLC  (CIK 0000999)"], "2024-03-01")]
    assert parse_fts_hits(hits) == []


def test_parse_normalizes_dotted_ticker_to_yahoo_dash_form():
    hits = [_hit(["Berkshire Hathaway  (BRK.B)  (CIK 0000067)"], "2024-02-02")]
    events = parse_fts_hits(hits)
    assert events[0].ticker == "BRK-B"


def test_parse_handles_multiple_hits():
    hits = [
        _hit(["Acme Corp.  (ACME)  (CIK 0000123)"], "2024-06-28"),
        _hit(["Beta Inc.  (BETA)  (CIK 0000456)"], "2023-11-30", form="25"),
    ]
    events = parse_fts_hits(hits)
    assert {e.ticker for e in events} == {"ACME", "BETA"}


def test_csv_round_trip_is_offline(tmp_path):
    events = [
        DelistingEvent(ticker="ACME", delisted_known=dt.date(2024, 6, 28)),
        DelistingEvent(ticker="BETA", delisted_known=dt.date(2023, 11, 30)),
    ]
    path = tmp_path / "delistings.csv"
    save_delistings_csv(events, path)
    loaded = load_delistings_csv(path)
    assert loaded == events


def test_load_missing_csv_returns_empty_list(tmp_path):
    assert load_delistings_csv(tmp_path / "nope.csv") == []


def test_fetch_paginates_and_requires_identity_offline():
    """fetch_delistings drives the SEC FTS endpoint via an INJECTED fetcher (no
    live call): it must page through hits.total.value and pass the identity as a
    User-Agent. The fake records the URLs/headers it was asked for."""
    calls: list[tuple[str, dict]] = []

    def fake_get(url: str, headers: dict) -> bytes:
        calls.append((url, headers))
        # total of 2 hits across 2 pages of size 1
        if "from=0" in url or "from=" not in url:
            page = {"hits": {"total": {"value": 2}, "hits": [
                {"_source": {"display_names": ["Acme  (ACME)  (CIK 1)"],
                             "file_date": "2024-06-28", "form": "25-NSE"}}]}}
        else:
            page = {"hits": {"total": {"value": 2}, "hits": [
                {"_source": {"display_names": ["Beta  (BETA)  (CIK 2)"],
                             "file_date": "2023-11-30", "form": "25-NSE"}}]}}
        return json.dumps(page).encode()

    events = fetch_delistings(
        forms=("25-NSE",), start="2023-01-01", end="2024-12-31",
        identity="Tester tester@example.com", page_size=1, http_get=fake_get,
    )
    assert {e.ticker for e in events} == {"ACME", "BETA"}
    assert len(calls) == 2  # paged once more after the first page
    # SEC fair-access: a contactable User-Agent must be sent on every request
    assert all("tester@example.com" in h.get("User-Agent", "") for _, h in calls)
