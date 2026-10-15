"""Manual location resolution, parent hints, and cross-script candidates."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.alias_memory import AliasStore  # noqa: E402
from map_story.catalog import connect, create_fixture, resolve_catalog_places, resolve_requests  # noqa: E402
from map_story.catalogue_api import apply_document  # noqa: E402
from map_story.identity import IdentityResolver, ResolutionCache, gather_candidates  # noqa: E402
from map_story.overrides import (  # noqa: E402
    acquire_clip_lock,
    apply_manual_override,
    publish_still_current,
    release_clip_lock,
    request_fingerprint,
    should_preserve_completed,
    user_point_id,
    validate_catalogue_selection,
    validate_custom_point,
)
from map_story.search import search_places  # noqa: E402
from map_story.transliterate import latin_forms  # noqa: E402


def decision(status, candidate_id=None):
    return json.dumps({
        "status": status,
        "candidate_id": candidate_id,
        "reason": "test",
        "evidence": {"name_match": "test", "geographic_context": "test", "feature_type": "test"},
        "alternative_candidate_ids": [],
    })


class Script:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.messages = []

    def __call__(self, messages):
        self.messages.append(messages)
        reply = self.replies[self.calls]
        self.calls += 1
        return reply


class LocationResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.sqlite"
        self.cache_path = Path(self.tmp.name) / "resolution-cache.sqlite"
        self.alias_path = Path(self.tmp.name) / "aliases.sqlite"
        create_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def resolver(self, script, **kwargs):
        return IdentityResolver(
            enabled=True,
            client=script,
            model="test-model",
            catalog_path=self.path,
            cache=ResolutionCache(self.cache_path),
            catalog_version_token="fixture-v1",
            alias_store=kwargs.get("alias_store"),
            overrides=kwargs.get("overrides"),
        )

    def test_inferred_parent_keeps_a_city_outside_that_state(self):
        conn = connect(self.path, readonly=True)
        try:
            context = resolve_requests([{
                "name": "Chandigarh",
                "level": "city",
                "parent_name": "Punjab",
            }], catalog_path=self.path)[0]["context"]
            candidates, limitation, diagnostics = gather_candidates(
                conn,
                {"name": "Chandigarh", "level": "city"},
                context,
            )
        finally:
            conn.close()
        self.assertIsNone(limitation)
        self.assertIn("gn-chandigarh", [item["id"] for item in candidates])
        self.assertFalse(context["membership_verified"])
        self.assertEqual(context["relationship_source"], "inferred")
        self.assertEqual(diagnostics["confirmed_constraints"]["state_id"], None)
        confirmed = resolve_requests([{
            "name": "Chandigarh",
            "level": "city",
            "state": "Haryana",
        }], catalog_path=self.path)[0]
        self.assertNotEqual(confirmed["status"], "resolved")
        self.assertTrue(confirmed["context"]["membership_verified"])
        conn = connect(self.path, readonly=True)
        try:
            blocked, reason, blocked_diagnostics = gather_candidates(
                conn,
                {"name": "Chandigarh", "level": "city"},
                confirmed["context"],
            )
        finally:
            conn.close()
        self.assertEqual(blocked, [])
        self.assertEqual(blocked_diagnostics["skipped_reason"], "confirmed_constraint_conflict")
        self.assertIn("Confirmed", reason or "")
        script = Script([decision("matched", "gn-chandigarh")])
        result = self.resolver(script).resolve([{
            "name": "Chandigarh",
            "level": "city",
            "state": "Haryana",
        }])[0]
        self.assertEqual(script.calls, 0)
        self.assertNotEqual(result.get("place", {}) and result["place"].get("id"), "gn-chandigarh")

    def test_shared_capital_context_is_not_administrative_membership(self):
        results = resolve_requests([
            {"name": "Chandigarh", "level": "city", "parent_name": "Punjab"},
            {"name": "Punjab", "level": "state"},
            {"name": "Haryana", "level": "state"},
        ], catalog_path=self.path)
        by_name = {item["place"]["name"]: item for item in results}
        self.assertEqual(by_name["Chandigarh"]["place"]["id"], "gn-chandigarh")
        self.assertNotEqual(by_name["Chandigarh"]["place"]["state_place_id"], "gb-adm1-IN-PB")
        self.assertFalse(by_name["Chandigarh"]["context"]["membership_verified"])
        self.assertEqual(by_name["Punjab"]["place"]["id"], "gb-adm1-IN-PB")
        self.assertEqual(by_name["Haryana"]["place"]["id"], "gb-adm1-IN-HR")

    def test_hindi_names_retrieve_english_candidates_without_auto_accept(self):
        self.assertIn("gandhinagar", latin_forms("गांधीनगर"))
        self.assertIn("indor", latin_forms("इंदौर"))
        for name, place_id in (("गांधीनगर", "gn-gandhinagar"), ("इंदौर", "gn-indore")):
            local = resolve_requests([{"name": name, "level": "city"}], catalog_path=self.path)[0]
            self.assertNotEqual(local["status"], "resolved")
            conn = connect(self.path, readonly=True)
            try:
                candidates, limitation, _diagnostics = gather_candidates(conn, {"name": name, "level": "city"}, local["context"])
            finally:
                conn.close()
            self.assertIsNone(limitation)
            match = next(item for item in candidates if item["id"] == place_id)
            self.assertEqual(match["match"]["method"], "transliteration")
        script = Script([decision("matched", "gn-gandhinagar")])
        chosen = self.resolver(script).resolve([{"name": "गांधीनगर", "level": "city", "parent_name": "Gujarat"}])[0]
        self.assertEqual(chosen["place"]["id"], "gn-gandhinagar")
        self.assertEqual(script.calls, 1)

    def test_ambiguous_names_keep_the_selected_canonical_id(self):
        local = resolve_requests([{"name": "Rampur", "level": "city"}], catalog_path=self.path)[0]
        self.assertEqual(local["status"], "ambiguous")
        ids = {item["id"] for item in local["candidates"]}
        self.assertIn("gn-rampur-up", ids)
        self.assertIn("gn-rampur-gj", ids)
        request = {"name": "Rampur", "level": "city", "request_id": "clip_01:0"}
        request["fingerprint"] = request_fingerprint(request, "Rampur in Gujarat")
        override = {
            "request_id": "clip_01:0",
            "fingerprint": request["fingerprint"],
            "source": "manual_catalogue_selection",
            "place_id": "gn-rampur-gj",
        }
        result = self.resolver(Script([]), overrides=[override]).resolve([request], passage="Rampur in Gujarat")[0]
        self.assertEqual(result["place"]["id"], "gn-rampur-gj")
        self.assertEqual(result["match_method"], "manual_catalogue_selection")

    def test_a_river_cannot_become_a_settlement(self):
        conn = connect(self.path, readonly=True)
        try:
            candidates, limitation, diagnostics = gather_candidates(conn, {"name": "Yamuna", "level": "river"}, {})
            self.assertEqual(candidates, [])
            self.assertEqual(diagnostics["skipped_reason"], "unsupported_feature")
            self.assertIn("river", limitation or "")
            with self.assertRaises(ValueError):
                validate_catalogue_selection(
                    conn,
                    place_id="gn-yamunanagar",
                    requested_name="Yamuna river",
                    requested_level="river",
                    type_correction=True,
                )
        finally:
            conn.close()

    def test_override_lifecycle_preserves_other_clips_and_rejects_stale_reuse(self):
        request = {"name": "Rampur", "level": "city", "request_id": "clip_01:0"}
        fingerprint = request_fingerprint(request, "Rampur in Gujarat")
        request["fingerprint"] = fingerprint
        override = {
            "request_id": "clip_01:0",
            "fingerprint": fingerprint,
            "source": "manual_catalogue_selection",
            "place_id": "gn-rampur-gj",
        }
        first = self.resolver(Script([]), overrides=[override]).resolve([request], passage="Rampur in Gujarat")[0]
        self.assertEqual(first["place"]["id"], "gn-rampur-gj")
        changed = dict(request)
        changed["fingerprint"] = request_fingerprint(request, "Rampur in Uttar Pradesh")
        stale = self.resolver(Script([decision("ambiguous")]), overrides=[override]).resolve(
            [changed],
            passage="Rampur in Uttar Pradesh",
        )[0]
        self.assertTrue(stale.get("override_stale"))
        self.assertNotEqual((stale.get("place") or {}).get("id"), "gn-rampur-gj")
        completed = {"status": "completed", "video": str(self.path), "override_revision": 1}
        self.assertTrue(should_preserve_completed(completed, 1))
        self.assertFalse(should_preserve_completed(completed, 2))
        self.assertTrue(publish_still_current(3, 3))
        self.assertFalse(publish_still_current(3, 4))
        lock = Path(self.tmp.name) / "clip_01" / "render.lock"
        self.assertTrue(acquire_clip_lock(lock))
        self.assertFalse(acquire_clip_lock(lock))
        release_clip_lock(lock)

    def test_duplicate_mapping_does_not_bump_the_revision(self):
        job = Path(self.tmp.name) / "job"
        job.mkdir()
        selection = {
            "clips": [{
                "id": "clip_01",
                "source_passage": "Gandhinagar",
                "place_requests": [{"name": "Gandhinagar", "level": "city"}],
            }],
        }
        (job / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
        body = {
            "job_dir": str(job),
            "job_id": "abc123",
            "script_hash": "hash",
            "uid": 4,
            "selections": [{
                "request_id": "clip_01:0",
                "source": "manual_catalogue_selection",
                "place_id": "gn-gandhinagar",
            }],
        }
        first = apply_document(body, catalog_path=self.path, alias_db=self.alias_path)
        second = apply_document(body, catalog_path=self.path, alias_db=self.alias_path)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["revision"], second["revision"])
        with self.assertRaises(ValueError):
            validate_catalogue_selection(
                connect(self.path, readonly=True),
                place_id="gn-missing",
                requested_name="Gandhinagar",
                requested_level="city",
            )

    def test_alias_memory_is_contextual_and_can_be_disabled(self):
        store = AliasStore(self.alias_path)
        store.remember({
            "name": "गांधीनगर",
            "place_id": "gn-gandhinagar",
            "level": "city",
            "feature_type": "populated_place",
            "country_code": "IN",
            "state_place_id": "gb-adm1-IN-GJ",
            "catalogue_version": "fixture",
            "uid": 2,
        })
        gujarat = resolve_requests([{"name": "गांधीनगर", "level": "city", "parent_name": "Gujarat"}], catalog_path=self.path)[0]
        other = resolve_requests([{"name": "गांधीनगर", "level": "city", "parent_name": "Punjab"}], catalog_path=self.path)[0]
        self.assertEqual(store.match("गांधीनगर", gujarat["context"])["place_id"], "gn-gandhinagar")
        self.assertIsNone(store.match("गांधीनगर", other["context"]))
        self.assertIsNone(store.match("गांधीनगर", {}))
        resolved = self.resolver(Script([]), alias_store=store).resolve([
            {"name": "गांधीनगर", "level": "city", "parent_name": "Gujarat"},
        ])[0]
        self.assertEqual(resolved["place"]["id"], "gn-gandhinagar")
        self.assertEqual(resolved["match_method"], "user_confirmed_alias")
        store.set_active(1, False)
        self.assertIsNone(store.match("गांधीनगर", gujarat["context"]))
        disabled = self.resolver(Script([decision("no_match")]), alias_store=store).resolve([
            {"name": "गांधीनगर", "level": "city", "parent_name": "Gujarat"},
        ])[0]
        self.assertNotEqual(disabled.get("match_method"), "user_confirmed_alias")
        self.assertNotEqual(disabled["status"], "resolved")

    def test_custom_point_is_a_point_and_rejects_bad_coordinates(self):
        with self.assertRaises(ValueError):
            validate_custom_point(name="Camp", latitude=120, longitude=10)
        geometry = validate_custom_point(name="Camp", latitude=23.2, longitude=72.6)
        self.assertEqual(geometry["type"], "Point")
        point_id = user_point_id("job", "clip_01:0")
        conn = connect(self.path, readonly=True)
        try:
            result = apply_manual_override(conn, {
                "requested": {"name": "Camp", "level": "city"},
                "context": {},
            }, {
                "source": "manual_custom_point",
                "place_id": point_id,
                "display_name": "Camp",
                "latitude": 23.2,
                "longitude": 72.6,
            })
        finally:
            conn.close()
        resolved = resolve_catalog_places({
            "places": [{"id": point_id, "name": "Camp", "level": "city"}],
        }, self.path, extras={
            point_id: {"id": point_id, "name": "Camp", "level": "city", "geometry": geometry},
        })
        self.assertEqual(resolved[point_id]["geometry"]["type"], "Point")
        self.assertNotIn("Polygon", json.dumps(resolved[point_id]["geometry"]))
        self.assertFalse(result["place"]["spatial_membership_verified"])

    def test_unknown_request_and_bad_place_are_rejected(self):
        job = Path(self.tmp.name) / "job-invalid"
        job.mkdir()
        (job / "selection.json").write_text(json.dumps({
            "clips": [{"id": "clip_01", "source_passage": "Vadnagar", "place_requests": [{"name": "Vadnagar", "level": "city"}]}],
        }), encoding="utf-8")
        rejected = apply_document({
            "job_dir": str(job),
            "job_id": "abc",
            "script_hash": "hash",
            "uid": 1,
            "selections": [
                {"request_id": "clip_01:9", "source": "manual_catalogue_selection", "place_id": "gn-vadnagar"},
                {"request_id": "clip_01:0", "source": "manual_catalogue_selection", "place_id": "gn-nope"},
            ],
        }, catalog_path=self.path, alias_db=self.alias_path)
        self.assertEqual(len(rejected["errors"]), 2)
        self.assertEqual(rejected["overrides"], [])

    def test_diagnostics_distinguish_empty_api_and_conflict(self):
        missing = self.resolver(Script([])).resolve([{"name": "Atlantis", "level": "city"}])[0]
        self.assertEqual(missing["fallback"]["skipped_reason"], "no_candidates")
        self.assertEqual(missing["fallback"]["error_kind"], None)
        self.assertNotEqual(missing["status"], "fallback_unavailable")
        unavailable = IdentityResolver(
            enabled=True,
            client=None,
            catalog_path=self.path,
            cache=ResolutionCache(self.cache_path),
            catalog_version_token="fixture-v1",
        ).resolve([{"name": "जम्मू-कश्मीर", "level": "state"}])[0]
        self.assertEqual(unavailable["status"], "fallback_unavailable")
        self.assertEqual(unavailable["fallback"]["error_kind"], "api_failure")
        self.assertNotEqual(unavailable["fallback"]["skipped_reason"], "no_candidates")
        hits = search_places("गांधीनगर", catalog_path=self.path)
        self.assertIn("gn-gandhinagar", [item["id"] for item in hits["results"]])
        self.assertNotIn("geometry", json.dumps(hits))


if __name__ == "__main__":
    unittest.main()
