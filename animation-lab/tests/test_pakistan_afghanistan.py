"""Pakistan and Afghanistan catalogue behaviour. DeepSeek is mocked."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_story.alias_memory import AliasStore  # noqa: E402
from map_story.catalog import add_regional_fixture, create_fixture, lookup, resolve_requests  # noqa: E402
from map_story.compile import compile_resolved_plan  # noqa: E402
from map_story.countries import iso_for_token, parse_country_list  # noqa: E402
from map_story.geo import GeoResolveError  # noqa: E402
from map_story.identity import IdentityResolver, ResolutionCache, cache_key, gather_candidates  # noqa: E402
from map_story.catalog import connect  # noqa: E402
from map_story.overrides import request_fingerprint  # noqa: E402
from map_story.scene_publish import publish_scene_mp4  # noqa: E402
from map_story.search import catalogue_filters, search_places  # noqa: E402

def decision(status, candidate_id=None, alternatives=None):
    return json.dumps({
        "status": status,
        "candidate_id": candidate_id,
        "reason": "test selection",
        "evidence": {"name_match": "supplied alias", "geographic_context": "supplied parent", "feature_type": "compatible"},
        "alternative_candidate_ids": alternatives or [],
    })


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


def _place(pid, name, level, bbox, parent=None, representation="boundary"):
    west, south, east, north = bbox
    return {
        "id": pid,
        "name": name,
        "level": level,
        "parent": parent,
        "source_id": f"fixture:{pid}",
        "representation": representation,
        "bbox": bbox,
        "anchor": [(west + east) / 2, (south + north) / 2],
    }


class RegionalCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.sqlite"
        self.cache_path = Path(self.tmp.name) / "resolution-cache.sqlite"
        create_fixture(self.path)
        self.india_only = Path(self.tmp.name) / "india.sqlite"
        create_fixture(self.india_only)

    def tearDown(self):
        self.tmp.cleanup()

    def regional(self):
        add_regional_fixture(self.path)

    def resolver(self, script, **kwargs):
        return IdentityResolver(
            enabled=True,
            client=script,
            model="test-model",
            catalog_path=self.path,
            cache=ResolutionCache(self.cache_path),
            catalog_version_token=kwargs.get("version", "fixture-v1"),
            overrides=kwargs.get("overrides"),
            alias_store=kwargs.get("alias_store"),
        )

    def test_india_fixture_behaviour_stays_unchanged(self):
        gujarat = lookup("गुजरात", country="IN", catalog_path=self.india_only)
        self.assertEqual(gujarat["place"]["id"], "gb-adm1-IN-GJ")
        punjab = lookup("Punjab", level="state", catalog_path=self.india_only)
        self.assertEqual(punjab["place"]["id"], "gb-adm1-IN-PB")
        self.assertEqual(punjab["place"]["country_code"], "IN")

    def test_iso_codes_are_normalised_and_unknown_codes_fail(self):
        self.assertEqual(parse_country_list("IND,PAK,AFG"), ["IN", "PK", "AF"])
        self.assertEqual(iso_for_token("PAK"), "PK")
        self.assertEqual(iso_for_token("AFG"), "AF")
        self.assertEqual(iso_for_token("IND"), "IN")
        with self.assertRaises(GeoResolveError):
            parse_country_list("ZZ")

    def test_punjab_is_disambiguated_by_country(self):
        self.regional()
        self.assertEqual(lookup("Punjab", level="state", catalog_path=self.path)["status"], "ambiguous")
        india = lookup("Punjab", level="state", country="IND", catalog_path=self.path)
        pakistan = lookup("Punjab", level="state", country="PAK", catalog_path=self.path)
        self.assertEqual(india["place"]["id"], "gb-adm1-IN-PB")
        self.assertEqual(pakistan["place"]["id"], "gb-adm1-PK-PB")
        self.assertEqual(pakistan["place"]["country_code"], "PK")
        self.assertEqual(pakistan["place"]["admin_label"], "Province / Territory")

    def test_pakistan_cities_keep_their_provinces(self):
        self.regional()
        lahore = lookup("लाहौर", level="city", country="Pakistan", catalog_path=self.path)
        self.assertEqual(lahore["place"]["id"], "gn-lahore")
        self.assertEqual(lahore["place"]["state_name"], "Punjab")
        self.assertEqual(lahore["place"]["representation"], "point")
        quetta = lookup("Quetta", level="city", state="Balochistan", catalog_path=self.path)
        self.assertEqual(quetta["place"]["id"], "gn-quetta")
        self.assertEqual(quetta["place"]["state_place_id"], "gb-adm1-PK-BA")
        islamabad = lookup("इस्लामाबाद", level="city", country="PK", catalog_path=self.path)
        self.assertEqual(islamabad["place"]["id"], "gn-islamabad")
        self.assertEqual(islamabad["place"]["state_place_id"], "gb-adm1-PK-IS")
        territory = lookup("Islamabad Capital Territory", level="state", country="PK", catalog_path=self.path)
        self.assertEqual(territory["place"]["feature_type"], "national_capital_territory")
        self.assertNotEqual(territory["place"]["id"], islamabad["place"]["id"])

    def test_kabul_and_herat_keep_city_and_province_separate(self):
        self.regional()
        cities = lookup("Kabul", level="city", country="AF", catalog_path=self.path)
        provinces = lookup("Kabul", level="state", country="AFG", catalog_path=self.path)
        self.assertEqual(cities["place"]["id"], "gn-kabul")
        self.assertEqual(cities["place"]["representation"], "point")
        self.assertEqual(provinces["place"]["id"], "gb-adm1-AF-KAB")
        self.assertEqual(provinces["place"]["representation"], "boundary")
        self.assertEqual(lookup("हेरात", level="city", catalog_path=self.path)["place"]["id"], "gn-herat")
        self.assertEqual(lookup("Herat", level="state", country="Afghanistan", catalog_path=self.path)["place"]["id"], "gb-adm1-AF-HER")
        both = lookup("काबुल", catalog_path=self.path)
        self.assertEqual(both["status"], "ambiguous")
        self.assertEqual({item["id"] for item in both["candidates"]}, {"gn-kabul", "gb-adm1-AF-KAB"})

    def test_hindi_aliases_retrieve_candidates_without_hardcoding_identity_logic(self):
        self.regional()
        for name, place_id in (
            ("पाकिस्तान", "ne-adm0-pak"),
            ("अफ़ग़ानिस्तान", "ne-adm0-afg"),
            ("बलूचिस्तान", "gb-adm1-PK-BA"),
            ("क्वेटा", "gn-quetta"),
            ("कंधार", "gn-kandahar"),
            ("मजार-ए-शरीफ", "gn-mazar"),
        ):
            found = lookup(name, catalog_path=self.path)
            self.assertEqual(found["status"], "resolved", name)
            self.assertEqual(found["place"]["id"], place_id)

    def test_misspelling_returns_candidates_and_does_not_force_identity(self):
        self.regional()
        local = lookup("Kabule", country="Afghanistan", catalog_path=self.path)
        self.assertEqual(local["status"], "not_found")
        self.assertIsNone(local["place"])
        ids = {item["id"] for item in local["candidates"]}
        self.assertIn("gn-kabul", ids)
        self.assertTrue(all(item.get("suggestion_only") for item in local["candidates"]))
        conn = connect(self.path, readonly=True)
        try:
            candidates, _limitation, diagnostics = gather_candidates(
                conn,
                {"name": "Kabule", "level": None, "country": "Afghanistan"},
                {"country": "Afghanistan", "country_code": "AF", "verified": {"country": True, "state": False, "district": False}},
            )
        finally:
            conn.close()
        self.assertIn("gn-kabul", {item["id"] for item in candidates})
        self.assertIn("gb-adm1-AF-KAB", {item["id"] for item in candidates})
        self.assertIsNone(diagnostics["skipped_reason"])
        script = Script([decision("ambiguous", alternatives=["gn-kabul", "gb-adm1-AF-KAB"])])
        reviewed = self.resolver(script).resolve([{"name": "Kabule", "country": "Afghanistan"}])[0]
        self.assertEqual(reviewed["status"], "ambiguous")
        self.assertIsNone(reviewed.get("place"))

    def test_inferred_wrong_parent_stays_reviewable(self):
        self.regional()
        local = resolve_requests(
            [{"name": "Lahore", "level": "city", "country": "Pakistan", "state": "Sindh"}],
            catalog_path=self.path,
        )[0]
        self.assertNotEqual(local["status"], "resolved")
        self.assertIn("gn-lahore", {item["id"] for item in local["candidates"]})

    def test_confirmed_wrong_country_selection_is_rejected(self):
        self.regional()
        request = {"name": "Punjab", "level": "state", "country": "Pakistan", "request_id": "clip_01:0"}
        request["fingerprint"] = request_fingerprint(request, "Punjab, Pakistan")
        override = {
            "request_id": "clip_01:0",
            "fingerprint": request["fingerprint"],
            "source": "manual_catalogue_selection",
            "place_id": "gb-adm1-IN-PB",
            "catalogue_version": "fixture-v1",
        }
        result = self.resolver(Script([]), overrides=[override]).resolve([request], passage="Punjab, Pakistan")[0]
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("verified country", result["reason"])
        self.assertNotEqual((result.get("place") or {}).get("id"), "gb-adm1-IN-PB")

    def test_unknown_places_and_rivers_stay_unresolved(self):
        self.regional()
        missing = lookup("Atlantis", country="PK", catalog_path=self.path)
        self.assertEqual(missing["status"], "not_found")
        self.assertIsNone(missing["place"])
        conn = connect(self.path, readonly=True)
        try:
            candidates, limitation, diagnostics = gather_candidates(
                conn, {"name": "Indus", "level": "river"}, {"verified": {}},
            )
        finally:
            conn.close()
        self.assertEqual(candidates, [])
        self.assertEqual(diagnostics["skipped_reason"], "unsupported_feature")
        self.assertIn("river", limitation or "")
        script = Script([decision("matched", "gn-made-up"), decision("matched", "gn-made-up")])
        rejected = self.resolver(script).resolve([{"name": "Kabule", "country": "Afghanistan"}])[0]
        self.assertNotEqual((rejected.get("place") or {}).get("id"), "gn-made-up")

    def test_canonical_ids_and_user_aliases_survive_a_rebuild(self):
        self.regional()
        other = Path(self.tmp.name) / "again.sqlite"
        create_fixture(other)
        add_regional_fixture(other)
        first = connect(self.path, readonly=True)
        second = connect(other, readonly=True)
        try:
            left = [row["id"] for row in first.execute("SELECT id FROM place WHERE country_code IN ('PK','AF') ORDER BY id")]
            right = [row["id"] for row in second.execute("SELECT id FROM place WHERE country_code IN ('PK','AF') ORDER BY id")]
        finally:
            first.close()
            second.close()
        self.assertEqual(left, right)
        self.assertIn("ne-adm0-ind", [row["id"] for row in connect(self.path, readonly=True).execute("SELECT id FROM place WHERE id='ne-adm0-ind'")])
        alias_path = Path(self.tmp.name) / "confirmed-aliases.sqlite"
        store = AliasStore(alias_path)
        store.remember({
            "name": "Punjab",
            "place_id": "gb-adm1-IN-PB",
            "feature_type": "adm1_territory",
            "level": "state",
            "country_code": "IN",
            "state_place_id": "gb-adm1-IN-PB",
            "catalogue_version": "fixture-v1",
        })
        create_fixture(self.path)
        add_regional_fixture(self.path)
        self.assertTrue(alias_path.is_file())
        india_context = {"country_code": "IN", "state_id": "gb-adm1-IN-PB", "verified": {"country": True}}
        pakistan_context = {"country_code": "PK", "state_id": "gb-adm1-PK-PB", "verified": {"country": True}}
        self.assertEqual(store.match("Punjab", india_context)["place_id"], "gb-adm1-IN-PB")
        self.assertIsNone(store.match("Punjab", pakistan_context))

    def test_cms_filters_follow_catalogue_coverage(self):
        india = catalogue_filters(self.india_only)
        self.assertEqual([item["country_code"] for item in india["countries"]], ["IN"])
        self.regional()
        covered = catalogue_filters(self.path)
        self.assertEqual({item["country_code"] for item in covered["countries"]}, {"IN", "PK", "AF"})
        found = search_places("लाहौर", country="PK", level="city", catalog_path=self.path)
        self.assertEqual(found["results"][0]["id"], "gn-lahore")
        self.assertEqual(found["results"][0]["country_name"], "Pakistan")
        self.assertEqual(found["results"][0]["representation"], "point")

    def test_opening_camera_uses_the_selected_country(self):
        plan = {
            "schema_version": "1.0",
            "type": "map_focus_sequence",
            "duration_seconds": 8,
            "language": "hi",
            "style": "documentary_relief_bold",
            "places": [
                {"id": "ne-adm0-pak", "name": "Pakistan", "level": "country"},
                {"id": "gb-adm1-PK-PB", "name": "Punjab", "level": "state", "parent": "ne-adm0-pak"},
                {"id": "gn-lahore", "name": "Lahore", "level": "city", "parent": "gb-adm1-PK-PB"},
            ],
            "shots": [{
                "id": "open",
                "start": 0,
                "end": 8,
                "frame": "ne-adm0-pak",
                "actions": [
                    {"type": "zoom_to_boundary", "place": "ne-adm0-pak", "padding": 0.10},
                    {"type": "highlight", "place": "ne-adm0-pak", "color": "#E52B32"},
                    {"type": "show_label", "place": "ne-adm0-pak", "text": "पाकिस्तान"},
                ],
            }],
        }
        places = {
            "ne-adm0-pak": _place("ne-adm0-pak", "Pakistan", "country", [60, 23, 75, 37]),
            "gb-adm1-PK-PB": _place("gb-adm1-PK-PB", "Punjab", "state", [70, 28, 75, 33], "ne-adm0-pak"),
            "gn-lahore": _place("gn-lahore", "Lahore", "city", [74.2, 31.4, 74.4, 31.6], "gb-adm1-PK-PB", "point"),
        }
        resolved = compile_resolved_plan(plan, places, job_settings={})
        center = resolved["camera"]["keyframes"][0]["center"]
        self.assertEqual(resolved["composition"]["opening"]["policy"], "country_centered")
        self.assertEqual(resolved["composition"]["opening"]["primary_country_id"], "ne-adm0-pak")
        self.assertGreater(center[1], 26)
        self.assertLess(center[0], 72)
        self.assertIn("PAK ADM1/ADM2", resolved["attribution"])
        layer_ids = [layer["id"] for layer in resolved["terrain"]["layers"]]
        self.assertIn("regional", layer_ids)

    def test_country_outside_relief_drops_the_regional_layer(self):
        plan = {
            "schema_version": "1.0",
            "type": "map_focus_sequence",
            "duration_seconds": 6,
            "language": "en",
            "style": "documentary_relief_bold",
            "places": [{"id": "ne-adm0-elsewhere", "name": "Elsewhere", "level": "country"}],
            "shots": [{
                "id": "open",
                "start": 0,
                "end": 6,
                "frame": "ne-adm0-elsewhere",
                "actions": [{"type": "zoom_to_boundary", "place": "ne-adm0-elsewhere", "padding": 0.10}],
            }],
        }
        places = {
            "ne-adm0-elsewhere": _place("ne-adm0-elsewhere", "Elsewhere", "country", [-20, 10, -5, 20]),
        }
        resolved = compile_resolved_plan(plan, places, job_settings={})
        self.assertNotIn("regional", [layer["id"] for layer in resolved["terrain"]["layers"]])
        self.assertLessEqual(resolved["camera"]["keyframes"][0]["zoom"], 5.2)
        self.assertTrue(any("outside the South Asia relief" in item for item in resolved["limitations"]))

    def test_scene_output_name_and_cache_version_stay_in_place(self):
        rendered = Path(self.tmp.name) / "clip.mp4"
        rendered.write_bytes(b"ftyp" + b"\0" * 1200)
        published = publish_scene_mp4(
            Path(self.tmp.name) / "story",
            scene_number=4,
            rendered=rendered,
            entry={"clip_id": "clip_04"},
            job_created=1,
        )
        self.assertEqual(published.name, "scene_4.mp4")
        self.assertEqual(published.parent.name, "animation")
        shared = dict(request={"name": "Lahore"}, context={}, candidate_ids=["gn-lahore"], passage="Lahore")
        self.assertNotEqual(
            cache_key(**shared, version="catalog-a"),
            cache_key(**shared, version="catalog-b"),
        )

    def test_saved_selection_is_revalidated_when_the_catalogue_version_changes(self):
        self.regional()
        request = {"name": "Lahore", "level": "city", "country": "Pakistan", "request_id": "clip_02:0"}
        request["fingerprint"] = request_fingerprint(request, "Lahore")
        override = {
            "request_id": "clip_02:0",
            "fingerprint": request["fingerprint"],
            "source": "manual_catalogue_selection",
            "place_id": "gn-lahore",
            "catalogue_version": "previous-catalogue",
        }
        result = self.resolver(Script([]), overrides=[override]).resolve([request], passage="Lahore")[0]
        self.assertEqual(result["place"]["id"], "gn-lahore")
        self.assertTrue(result["catalogue_revalidated"])
