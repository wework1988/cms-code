#!/usr/bin/env python3
"""HTTP client for Drupal Story Pipeline REST API."""

from __future__ import annotations

import os
from typing import Any

import requests


class DrupalStoryClient:
    """Talks to /api/story-pipeline/* on myresearch2."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = (base_url or os.environ["DRUPAL_BASE_URL"]).rstrip("/")
        self.api_key = api_key or os.environ["DRUPAL_API_KEY"]
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Story-Pipeline-Key": self.api_key,
                "Accept": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{path}"

    def get_story(self, story_id: int | str) -> dict[str, Any]:
        r = self.session.get(self._url(f"/api/story-pipeline/stories/{story_id}"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_bundle(self, story_id: int | str, pipeline: str = "storyboard") -> dict[str, Any]:
        r = self.session.get(
            self._url(f"/api/story-pipeline/stories/{story_id}/bundle"),
            params={"pipeline": pipeline},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def create_story(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self.session.post(
            self._url("/api/story-pipeline/stories"),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def queue_generate_story(
        self,
        story_id: int | str,
        youtube_urls: list[str] | str | None = None,
        duration_minutes: int | None = None,
        custom_instructions: str | None = None,
        generation_mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"story_id": str(story_id)}
        if youtube_urls is not None:
            payload["youtube_urls"] = youtube_urls
        if duration_minutes is not None:
            payload["duration_minutes"] = duration_minutes
        if custom_instructions is not None:
            payload["custom_instructions"] = custom_instructions
        if generation_mode is not None:
            payload["generation_mode"] = generation_mode

        r = self.session.post(
            self._url("/api/story-pipeline/generate-story"),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def queue_storyboard(self, story_id: int | str, max_step: int = 4) -> dict[str, Any]:
        r = self.session.post(
            self._url("/api/story-pipeline/run-storyboard"),
            json={"story_id": str(story_id), "max_step": max_step},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def update_story(self, story_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        r = self.session.post(
            self._url(f"/api/story-pipeline/stories/{story_id}/update"),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        try:
            return r.json()
        except ValueError as exc:
            preview = (r.text or "")[:500].strip()
            raise ValueError(
                f"Drupal update returned non-JSON (HTTP {r.status_code}, "
                f"{len(r.content)} bytes). Often caused by post_max_size when "
                f"uploading base64 MP3s — use STORY_ASSET_ROOT disk sync instead. "
                f"Body preview: {preview!r}"
            ) from exc
