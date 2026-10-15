"""Identity fallback. The model is mocked, so these tests stay offline."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.catalog import apply_feature_policy, connect, create_fixture, resolve_requests  # noqa: E402
from map_story.identity import (  # noqa: E402
    FALLBACK_VERSION,
    SYSTEM_PROMPT,
    IdentityResolver,
    ResolutionCache,
    accept_match,
    generate_candidates,
    is_name_extension,
)


def decision(status, candidate_id=None, alternatives=None):
    return json.dumps({
        "status": status,
        "candidate_id": candidate_id,
        "reason": "test selection",
        "evidence": {
            "name_match": "supplied alias",
            "geographic_context": "supplied parent",
            "feature_type": "compatible",
        },
        "alternative_candidate_ids": alternatives or [],
    }, ensure_ascii=False)


class Script:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.messages = []

    def __call__(self, messages):
        self.calls += 1
        self.messages.append(messages)
        if not self.responses:
            raise AssertionError("DeepSeek was called with no scripted response")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class IdentityFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.sqlite"
        self.cache_path = Path(self.tmp.name) / "resolution-cache.sqlite"
        create_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def resolver(self, script, *, version="fixture-v1", max_calls=24):
        return IdentityResolver(
            enabled=True,
            client=script,
            model="test-model",
            catalog_path=self.path,
            cache=ResolutionCache(self.cache_path),
            catalog_version_token=version,
            max_calls=max_calls,
        )

    def test_exact_local_match_makes_zero_api_calls(self):
        script = Script([])
        result = self.resolver(script).resolve([
            {"name": "वडनगर", "level": "city", "parent_name": "गुजरात", "country": "भारत"},
        ])[0]
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["place"]["id"], "gn-vadnagar")
        self.assertEqual(script.calls, 0)
        self.assertFalse(result["fallback"]["attempted"])
        self.assertIn("Select only from the supplied candidate IDs.", SYSTEM_PROMPT)

    def test_failed_local_match_accepts_a_supplied_candidate(self):
        script = Script([decision("matched", "gb-adm1-IN-JK")])
        result = self.resolver(script).resolve([
            {"name": "जम्मू-कश्मीर", "level": "state", "country": "भारत"},
        ], passage="जम्मू-कश्मीर के श्रीनगर में")[0]
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["place"]["id"], "gb-adm1-IN-JK")
        self.assertEqual(script.calls, 1)
        self.assertEqual(result["fallback"]["cache"], "miss")
        self.assertEqual(result["fallback"]["accepted_id"], "gb-adm1-IN-JK")
        user = json.loads(script.messages[0][1]["content"])
        self.assertNotIn("coordinates", json.dumps(user["candidates"]))
        self.assertNotIn("geometry", json.dumps(user["candidates"]))

    def test_ambiguous_match_can_use_state_context(self):
        script = Script([decision("matched", "gn-rampur-gj")])
        result = self.resolver(script).resolve([
            {"name": "Rampur", "level": "city"},
        ], passage="Rampur in Gujarat")[0]
        self.assertEqual(result["local_status"], "ambiguous")
        self.assertEqual(result["place"]["id"], "gn-rampur-gj")
        self.assertEqual(script.calls, 1)

    def test_hindi_and_english_alias_stays_local(self):
        script = Script([])
        hindi = self.resolver(script).resolve([{"name": "श्रीनगर", "level": "city"}])[0]
        self.assertEqual(hindi["place"]["id"], "gn-srinagar")
        english = resolve_requests([{"name": "Srinagar", "level": "city"}], catalog_path=self.path)[0]
        self.assertEqual(english["place"]["id"], "gn-srinagar")
        self.assertEqual(script.calls, 0)

    def test_city_and_district_namesakes_keep_their_level(self):
        script = Script([])
        city = self.resolver(script).resolve([{"name": "Gorakhpur", "level": "city"}])[0]
        district = self.resolver(script).resolve([{"name": "Gorakhpur", "level": "district"}])[0]
        self.assertEqual(city["place"]["id"], "gn-gorakhpur-city")
        self.assertEqual(district["place"]["id"], "gb-adm2-gorakhpur")
        self.assertEqual(script.calls, 0)

    def test_similar_names_in_different_states_can_stay_ambiguous(self):
        script = Script([decision("ambiguous", alternatives=["gn-rampur-gj", "gn-rampur-up"])])
        result = self.resolver(script).resolve([{"name": "Rampur", "level": "city"}])[0]
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result.get("place"))
        self.assertEqual(script.calls, 1)

    def test_yamuna_cannot_become_yamunanagar(self):
        self.assertTrue(is_name_extension("Yamuna", "Yamunanagar"))
        script = Script([decision("matched", "gn-yamunanagar")])
        conn = connect(self.path, readonly=True)
        try:
            candidates, limitation = generate_candidates(conn, {"name": "Yamuna", "level": "river"}, {})
        finally:
            conn.close()
        self.assertEqual(candidates, [])
        self.assertIn("river", limitation or "")
        result = self.resolver(script).resolve([{"name": "Yamuna", "level": "river"}])[0]
        self.assertNotEqual(result.get("place", {}) and result["place"].get("id"), "gn-yamunanagar")
        self.assertEqual(script.calls, 0)

    def test_no_candidates_makes_no_api_request(self):
        script = Script([decision("matched", "gn-vadnagar")])
        result = self.resolver(script).resolve([{"name": "Atlantis", "level": "city"}])[0]
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(script.calls, 0)

    def test_unknown_id_is_rejected(self):
        script = Script([decision("matched", "gn-nope"), decision("matched", "gn-nope")])
        result = self.resolver(script).resolve([{"name": "जम्मू-कश्मीर", "level": "state"}])[0]
        self.assertEqual(result["status"], "needs_review")
        self.assertIsNone(result.get("place"))
        self.assertGreaterEqual(script.calls, 1)

    def test_wrong_feature_type_is_rejected(self):
        conn = connect(self.path, readonly=True)
        try:
            candidates, _ = generate_candidates(conn, {"name": "Gorakhpur", "level": None}, {})
            district = next(item for item in candidates if item["id"] == "gb-adm2-gorakhpur")
            accepted, error = accept_match(
                conn,
                request={"name": "Gorakhpur", "level": "city"},
                context={"verified": {}, "state_id": None, "district_id": None},
                candidates=[district],
                decision=json.loads(decision("matched", "gb-adm2-gorakhpur")),
            )
        finally:
            conn.close()
        self.assertIsNone(accepted)
        self.assertIn("district", error or "")

    def test_verified_parent_contradiction_is_rejected(self):
        conn = connect(self.path, readonly=True)
        try:
            candidates, _ = generate_candidates(
                conn,
                {"name": "Rampur", "level": "city"},
                {"verified": {}, "state_id": None, "district_id": None},
            )
            accepted, error = accept_match(
                conn,
                request={"name": "Rampur", "level": "city"},
                context={"verified": {"state": True}, "state_id": "gb-adm1-IN-GJ", "district_id": None},
                candidates=candidates,
                decision=json.loads(decision("matched", "gn-rampur-up")),
            )
        finally:
            conn.close()
        self.assertIsNone(accepted)
        self.assertIn("state", error or "")

    def test_no_match_is_preserved(self):
        script = Script([decision("no_match")])
        result = self.resolver(script).resolve([{"name": "जम्मू-कश्मीर", "level": "state"}])[0]
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["fallback"]["status"], "no_match")

    def test_malformed_response_gets_one_repair(self):
        script = Script(["not-json", decision("matched", "gb-adm1-IN-JK")])
        result = self.resolver(script).resolve([{"name": "जम्मू-कश्मीर", "level": "state"}])[0]
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["place"]["id"], "gb-adm1-IN-JK")
        self.assertEqual(script.calls, 2)

    def test_api_failure_is_not_missing_geography(self):
        script = Script([RuntimeError("DeepSeek HTTP 503: unavailable")])
        result = self.resolver(script).resolve([{"name": "जम्मू-कश्मीर", "level": "state"}])[0]
        self.assertEqual(result["status"], "fallback_unavailable")
        self.assertIn("503", result["reason"])
        policy = apply_feature_policy([result])
        self.assertEqual(policy["status"], "fallback_unavailable")
        self.assertNotEqual(policy["status"], "blocked")

    def test_context_sensitive_cache_and_catalog_version(self):
        first = Script([decision("matched", "gn-rampur-gj")])
        resolver = self.resolver(first, version="fixture-v1")
        gujarat_passage = "Rampur in Gujarat"
        resolved = resolver.resolve([{"name": "Rampur", "level": "city"}], passage=gujarat_passage)[0]
        self.assertEqual(resolved["place"]["id"], "gn-rampur-gj")
        again = Script([])
        cached = self.resolver(again, version="fixture-v1").resolve(
            [{"name": "Rampur", "level": "city"}], passage=gujarat_passage,
        )[0]
        self.assertEqual(cached["place"]["id"], "gn-rampur-gj")
        self.assertEqual(again.calls, 0)
        self.assertEqual(cached["fallback"]["cache"], "hit")
        other = Script([decision("matched", "gn-rampur-up")])
        uttar = self.resolver(other, version="fixture-v1").resolve(
            [{"name": "Rampur", "level": "city"}], passage="Rampur in Uttar Pradesh",
        )[0]
        self.assertEqual(uttar["place"]["id"], "gn-rampur-up")
        self.assertEqual(other.calls, 1)
        refreshed = Script([decision("matched", "gn-rampur-gj")])
        changed = self.resolver(refreshed, version="fixture-v2").resolve(
            [{"name": "Rampur", "level": "city"}], passage=gujarat_passage,
        )[0]
        self.assertEqual(changed["place"]["id"], "gn-rampur-gj")
        self.assertEqual(refreshed.calls, 1)
        self.assertEqual(FALLBACK_VERSION, "2026.10-identity-fallback-v1")

    def test_concurrent_cache_writes(self):
        cache = ResolutionCache(self.cache_path)
        errors = []

        def write(index):
            try:
                cache.put(f"key-{index}", {
                    "status": "no_match",
                    "place_id": None,
                    "catalog_version": "v",
                    "fallback_version": FALLBACK_VERSION,
                    "created_at": "2026-10-13T00:00:00+00:00",
                })
            except Exception as error:  # noqa: BLE001 — the test records the thread failure
                errors.append(error)

        threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(cache.get("key-3")["status"], "no_match")

    def test_missing_optional_feature_does_not_block_a_city(self):
        script = Script([])
        results = self.resolver(script).resolve([
            {"name": "वडनगर", "level": "city", "parent_name": "गुजरात"},
            {"name": "पिछोला झील", "level": "city", "parent_name": "वडनगर"},
        ])
        policy = apply_feature_policy(results)
        self.assertEqual(policy["status"], "ready")
        self.assertEqual(policy["resolved"][0]["place"]["id"], "gn-vadnagar")
        self.assertEqual(policy["omitted_features"][0]["name"], "पिछोला झील")
        self.assertEqual(script.calls, 0)


if __name__ == "__main__":
    unittest.main()
