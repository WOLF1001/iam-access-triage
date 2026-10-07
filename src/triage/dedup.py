"""Deduplication of incoming requests (ticket-triage). Stateful, so it lives in the service, not in the pipeline.

Three levels, all configured in config/policy.yaml → dedup:
  1. same Slack event_id (Slack retries an event it did not get an ack for) → return the cached result,
     do not run triage or write actions again;
  2. same requester + type + system within a window → mark as a repeat of the earlier request
     (the human sees one thread, no second approval is requested);
  3. same type + system from several different requesters → a pattern: candidate for a KB article
     or a known issue (current-state.md §3, repeat clusters).

In-memory in the prototype; in production — a shared store (Redis / DB) because n8n may retry to any replica.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from . import config


def request_keys(requester: str | None, decisions: list[dict]) -> list[tuple[str, str, str]]:
    """(requester, type, system) per sub-request; requests without a known system are not deduplicated."""
    return [(requester or "?", d["type"], d["primary_app"]) for d in decisions if d.get("primary_app")]


@dataclass
class DedupStore:
    events: dict[str, tuple[float, dict]] = field(default_factory=dict)
    requests: dict[tuple[str, str, str], tuple[float, str]] = field(default_factory=dict)
    seen_by: dict[tuple[str, str], dict[str, float]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def _prune(self, now: float, cfg: dict) -> None:
        """Bound memory: drop entries older than their window (called under lock)."""
        ev_ttl, same_ttl = cfg["event_window_hours"] * 3600, cfg["same_request_window_hours"] * 3600
        pat_ttl = cfg["pattern_window_days"] * 86400
        self.events = {k: v for k, v in self.events.items() if now - v[0] <= ev_ttl}
        self.requests = {k: v for k, v in self.requests.items() if now - v[0] <= same_ttl}
        self.seen_by = {k: w for k, v in self.seen_by.items()
                        if (w := {r: t for r, t in v.items() if now - t <= pat_ttl})}

    def cached(self, event_id: str | None, now: float | None = None) -> dict | None:
        if not event_id:
            return None
        now = now or time.time()
        ttl = config.policy()["dedup"]["event_window_hours"] * 3600
        with self.lock:
            hit = self.events.get(event_id)
            return hit[1] if hit and now - hit[0] <= ttl else None

    def record(self, event_id: str | None, requester: str | None, result: dict, now: float | None = None) -> dict:
        """Register a fresh result; returns the dedup block to attach to the response."""
        now = now or time.time()
        cfg = config.policy()["dedup"]
        same_ttl = cfg["same_request_window_hours"] * 3600
        pattern_ttl = cfg["pattern_window_days"] * 86400
        info: dict = {"repeat_of": None, "patterns": []}
        with self.lock:
            self._prune(now, cfg)
            for key in request_keys(requester, result["decisions"]):
                prev = self.requests.get(key)
                if prev and now - prev[0] <= same_ttl and prev[1] != event_id:
                    info["repeat_of"] = info["repeat_of"] or prev[1]
                else:
                    self.requests[key] = (now, event_id or f"local-{now}")
                pkey = key[1:]
                who = {r: t for r, t in self.seen_by.get(pkey, {}).items() if now - t <= pattern_ttl}
                who[key[0]] = now
                self.seen_by[pkey] = who
                if len(who) >= cfg["pattern_threshold"]:
                    info["patterns"].append({"type": pkey[0], "system": pkey[1], "requesters": len(who)})
            if event_id:
                self.events[event_id] = (now, result)
        return info
