#!/usr/bin/env python3
"""Fetch one public YouTube caption track.

Reads a JSON object from stdin: {"videoId": "...", "language": "hi"|"en"}.
Writes one JSON object to stdout. Proxy credentials are read from the
environment and are never included in the response.

Does not translate captions, solve CAPTCHAs, or read browser cookies.
"""

from __future__ import annotations

import json
import os
import sys

MAX_SEGMENTS = 20000
MAX_CHARS = 1_200_000


def select_caption(tracks, language):
    """Prefer human captions in the requested language, then automatic captions.

    Other languages are not substituted and captions are not translated.
    """

    requested = (language or "").lower()

    def matches(code):
        value = (code or "").lower()
        return value == requested or value.startswith(requested + "-")

    same = [track for track in tracks if matches(track.get("language_code", ""))]
    manual = next((track for track in same if not track.get("is_generated")), None)
    if manual:
        return manual, "manual"
    generated = next((track for track in same if track.get("is_generated")), None)
    if generated:
        return generated, "generated"
    return None, None


def run_self_test():
    human_preferred, human_kind = select_caption(
        [
            {"language_code": "hi", "is_generated": True, "id": "auto"},
            {"language_code": "hi", "is_generated": False, "id": "human"},
            {"language_code": "en", "is_generated": False, "id": "english"},
        ],
        "hi",
    )
    generated_only, generated_kind = select_caption(
        [{"language_code": "en-US", "is_generated": True, "id": "auto-en"}],
        "en",
    )
    other, other_kind = select_caption(
        [{"language_code": "es", "is_generated": False, "id": "spanish"}],
        "hi",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "cases": {
                    "humanPreferred": None if human_preferred is None else human_preferred["id"],
                    "humanKind": human_kind,
                    "generatedFallback": None if generated_only is None else generated_only["id"],
                    "generatedKind": generated_kind,
                    "otherLanguage": None if other is None else other["id"],
                    "otherKind": other_kind,
                },
            }
        )
    )


def fail(code, available=None, retry_after_ms=None):
    payload = {"ok": False, "code": code}
    if available is not None:
        payload["availableLanguages"] = available
    if retry_after_ms is not None:
        payload["retryAfterMs"] = retry_after_ms
    print(json.dumps(payload))


def parse_retry_after(value):
    if not value:
        return None
    text = str(value).strip()
    if text.isdigit():
        return int(text) * 1000
    return None


def proxy_config():
    mode = os.environ.get("YOUTUBE_TRANSCRIPT_PROXY", "off").strip().lower()
    if mode in ("", "off", "false", "0"):
        return None
    if mode == "webshare":
        from youtube_transcript_api.proxies import WebshareProxyConfig

        username = os.environ.get("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME", "").strip()
        password = os.environ.get("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD", "").strip()
        if not username or not password:
            return "config"
        locations = [
            part.strip()
            for part in os.environ.get("YOUTUBE_TRANSCRIPT_WEBSHARE_LOCATIONS", "").split(",")
            if part.strip()
        ]
        kwargs = {"proxy_username": username, "proxy_password": password}
        if locations:
            kwargs["filter_ip_locations"] = locations
        return WebshareProxyConfig(**kwargs)
    if mode == "generic":
        from youtube_transcript_api.proxies import GenericProxyConfig

        http_url = os.environ.get("YOUTUBE_TRANSCRIPT_HTTP_PROXY", "").strip()
        https_url = os.environ.get("YOUTUBE_TRANSCRIPT_HTTPS_PROXY", "").strip()
        if not http_url and not https_url:
            return "config"
        return GenericProxyConfig(
            http_url=http_url or https_url,
            https_url=https_url or http_url,
        )
    return "config"


def available_from(tracks):
    return [
        {
            "languageCode": track["language_code"],
            "language": track.get("language") or track["language_code"],
            "captionKind": "generated" if track.get("is_generated") else "manual",
        }
        for track in tracks
    ]


def main():
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        fail("invalid_url")
        return

    video_id = request.get("videoId")
    language = request.get("language")
    if not isinstance(video_id, str) or not isinstance(language, str):
        fail("invalid_url")
        return

    try:
        from requests import Session
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            AgeRestricted,
            InvalidVideoId,
            IpBlocked,
            NoTranscriptFound,
            RequestBlocked,
            TranscriptsDisabled,
            VideoUnavailable,
            VideoUnplayable,
            YouTubeRequestFailed,
        )
    except Exception:
        fail("provider_unavailable")
        return

    class StatusSession(Session):
        def __init__(self):
            super().__init__()
            self.last_status = None
            self.last_retry_after = None

        def send(self, prepared, **kwargs):
            response = super().send(prepared, **kwargs)
            self.last_status = response.status_code
            self.last_retry_after = response.headers.get("Retry-After")
            return response

    proxy = proxy_config()
    if proxy == "config":
        fail("provider_config")
        return

    session = StatusSession()
    api = YouTubeTranscriptApi(http_client=session, proxy_config=proxy) if proxy else YouTubeTranscriptApi(http_client=session)

    try:
        transcript_list = api.list(video_id)
        tracks = [
            {
                "language_code": transcript.language_code,
                "language": transcript.language,
                "is_generated": transcript.is_generated,
                "transcript": transcript,
            }
            for transcript in transcript_list
        ]
    except IpBlocked:
        fail("blocked")
        return
    except RequestBlocked:
        fail("blocked")
        return
    except TranscriptsDisabled:
        fail("no_captions")
        return
    except (VideoUnavailable, VideoUnplayable, AgeRestricted, InvalidVideoId):
        fail("unavailable")
        return
    except NoTranscriptFound:
        fail("no_captions")
        return
    except YouTubeRequestFailed:
        if session.last_status == 429:
            fail("rate_limited", retry_after_ms=parse_retry_after(session.last_retry_after))
        else:
            fail("temporary")
        return
    except Exception:
        fail("temporary")
        return

    if not tracks:
        fail("no_captions")
        return

    chosen, kind = select_caption(tracks, language)
    if chosen is None:
        fail("language_unavailable", available=available_from(tracks))
        return

    try:
        fetched = chosen["transcript"].fetch()
    except IpBlocked:
        fail("blocked")
        return
    except RequestBlocked:
        fail("blocked")
        return
    except YouTubeRequestFailed:
        if session.last_status == 429:
            fail("rate_limited", retry_after_ms=parse_retry_after(session.last_retry_after))
        else:
            fail("temporary")
        return
    except Exception:
        fail("temporary")
        return

    segments = []
    total_chars = 0
    for snippet in fetched:
        text = snippet.text or ""
        total_chars += len(text)
        if len(segments) >= MAX_SEGMENTS or total_chars > MAX_CHARS:
            fail("output_too_large")
            return
        segments.append(
            {
                "text": text,
                "start": float(snippet.start),
                "duration": float(snippet.duration),
            }
        )

    print(
        json.dumps(
            {
                "ok": True,
                "language": getattr(fetched, "language", None) or chosen["language"],
                "languageCode": getattr(fetched, "language_code", None) or chosen["language_code"],
                "captionKind": kind,
                "segments": segments,
            }
        )
    )


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        run_self_test()
    else:
        main()
