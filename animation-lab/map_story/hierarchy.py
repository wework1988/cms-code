"""Allocate verified administrative levels across a clip's focus stages.

Parent links come only from resolved place cards. Missing parents, city-states,
and island countries stay as the chain that was actually verified.
"""
from __future__ import annotations

from map_story.schema import PlanValidationError

LEVEL_RANK = {"country": 0, "state": 1, "district": 2, "city": 3, "region": 4}


class HierarchyPlanError(PlanValidationError):
    """The verified hierarchy does not fit the focus budget without dropping a target."""


def parent_key(card: dict) -> str | None:
    parent = card.get("parent_id") or card.get("parent")
    if parent:
        return str(parent)
    return None


def chain_root_to_self(card: dict, by_id: dict[str, dict]) -> list[dict]:
    """Verified ancestors from broadest to the place itself. Do not invent links."""
    nodes = [card]
    seen = {str(card["id"])}
    parent = parent_key(card)
    while parent and parent not in seen and parent in by_id:
        seen.add(parent)
        nodes.append(by_id[parent])
        parent = parent_key(by_id[parent])
    nodes.reverse()
    return nodes


def ideal_sequence(subjects: list[dict], by_id: dict[str, dict]) -> list[dict]:
    """Shared ancestors once, then each target's remaining chain in narrative order."""
    sequence: list[dict] = []
    seen: set[str] = set()
    for subject in subjects:
        for node in chain_root_to_self(subject, by_id):
            pid = str(node["id"])
            if pid in seen:
                continue
            sequence.append(node)
            seen.add(pid)
    return sequence


def _ancestor_ids(card: dict, by_id: dict[str, dict]) -> list[str]:
    return [str(node["id"]) for node in chain_root_to_self(card, by_id)[:-1]]


def _last_context_for_a_target(sequence: list[dict], index: int, subject_ids: set[str], by_id: dict[str, dict]) -> bool:
    """True when removing this node would leave a later target with no earlier ancestor."""
    node_id = str(sequence[index]["id"])
    for later in sequence[index + 1:]:
        if str(later["id"]) not in subject_ids:
            continue
        ancestors = _ancestor_ids(later, by_id)
        if node_id not in ancestors:
            continue
        remaining = [
            str(item["id"])
            for item in sequence
            if str(item["id"]) != node_id and str(item["id"]) in ancestors
        ]
        if not remaining:
            return True
    return False


def compress_sequence(
    sequence: list[dict],
    subjects: list[dict],
    target: int,
    by_id: dict[str, dict],
) -> tuple[list[dict], list[str]]:
    """Drop the finest optional ancestors until the stage budget fits.

    Subjects are never removed. The last remaining ancestor before a target
    is never removed. A repeated zoom is not used to stand in for a missing level.
    """
    subject_ids = {str(card["id"]) for card in subjects}
    dropped: list[str] = []
    seq = list(sequence)
    while len(seq) > target:
        candidates = []
        for index, node in enumerate(seq):
            if str(node["id"]) in subject_ids:
                continue
            if _last_context_for_a_target(seq, index, subject_ids, by_id):
                continue
            rank = LEVEL_RANK.get(str(node.get("level")), 9)
            candidates.append((rank, index))
        if not candidates:
            raise HierarchyPlanError(
                f"Verified hierarchy needs more than {target} focus stages "
                f"for {len(subject_ids)} primary targets. Split the passage or repair the plan."
            )
        candidates.sort(key=lambda item: (-item[0], -item[1]))
        index = candidates[0][1]
        dropped.append(str(seq[index]["id"]))
        del seq[index]
    return seq, dropped


def validate_parent_context(sequence: list[dict], subjects: list[dict], by_id: dict[str, dict]) -> None:
    index = {str(card["id"]): pos for pos, card in enumerate(sequence)}
    for subject in subjects:
        sid = str(subject["id"])
        if sid not in index:
            raise HierarchyPlanError(f"Primary target {sid} was dropped from the focus sequence.")
        ancestors = _ancestor_ids(subject, by_id)
        if not ancestors:
            continue
        if not any(ancestor in index and index[ancestor] < index[sid] for ancestor in ancestors):
            raise HierarchyPlanError(
                f"Close focus on {sid} has no earlier verified parent stage."
            )


def allocate_focus_stages(
    subjects: list[dict],
    orientations: list[dict],
    target: int,
) -> tuple[list[tuple[str, dict]], dict]:
    """Return (kind, card) stages and a hierarchy report."""
    by_id: dict[str, dict] = {}
    for card in list(orientations) + list(subjects):
        if card.get("id"):
            by_id[str(card["id"])] = card
    chosen = list(subjects)
    if not chosen:
        countries = [card for card in orientations if card.get("level") == "country"]
        chosen = countries or list(orientations)[:1]
        if not chosen:
            raise HierarchyPlanError("A map plan needs at least one resolved place.")
    sequence = ideal_sequence(chosen, by_id)
    sequence, dropped = compress_sequence(sequence, chosen, int(target), by_id)
    validate_parent_context(sequence, chosen, by_id)
    stages: list[tuple[str, dict]] = []
    for pos, card in enumerate(sequence):
        kind = "overview" if pos == 0 and card.get("level") == "country" else "focus"
        stages.append((kind, card))
    anchor = chosen[-1]
    while len(stages) < int(target):
        # Extra zooms only after every required level is already present.
        stages.append(("closer", anchor))
    report = {
        "primary_targets": [str(card["id"]) for card in chosen],
        "stage_ids": [str(card["id"]) for _kind, card in stages],
        "dropped_optional_levels": dropped,
        "parent_before_close": {
            str(card["id"]): next(
                (
                    ancestor
                    for ancestor in reversed(_ancestor_ids(card, by_id))
                    if ancestor in {str(item["id"]) for item in sequence}
                ),
                None,
            )
            for card in chosen
        },
    }
    return stages, report


def merge_verified_ancestors(plan: dict, summaries: list[dict] | None) -> dict:
    """Fill a missing parent from catalogue cards already verified for this clip.

    A model plan can name the city and leave parent empty even when the local
    summaries already contain the district, state, and country. Those summaries
    are the membership source. A parent that is not in the summaries stays empty.
    """
    if not summaries:
        return plan
    by_summary = {str(card["id"]): card for card in summaries if card.get("id")}
    places = [dict(place) for place in plan.get("places") or [] if place.get("id")]
    present = {str(place["id"]) for place in places}

    def apply_summary(place: dict) -> None:
        summary = by_summary.get(str(place["id"]))
        if not summary:
            return
        parent = summary.get("parent_id")
        if not place.get("parent") and parent in by_summary:
            place["parent"] = parent
        if not place.get("level") and summary.get("level"):
            place["level"] = summary["level"]
        if not place.get("representation") and summary.get("representation"):
            place["representation"] = summary["representation"]
        if not place.get("aliases") and summary.get("aliases"):
            place["aliases"] = list(summary["aliases"])

    for place in places:
        apply_summary(place)

    added = True
    while added:
        added = False
        for place in list(places):
            parent = place.get("parent")
            if not parent or parent in present or parent not in by_summary:
                continue
            card = by_summary[parent]
            grand = card.get("parent_id") if card.get("parent_id") in by_summary else None
            places.append({
                "id": card["id"],
                "name": card.get("name"),
                "level": card.get("level"),
                "parent": grand,
                "role": "orientation",
                "representation": card.get("representation"),
                "aliases": list(card.get("aliases") or []),
            })
            present.add(str(card["id"]))
            added = True

    updated = dict(plan)
    updated["places"] = places
    return updated


def cards_from_semantic_plan(plan: dict) -> list[dict]:
    """Place cards for hierarchy allocation. Representation follows markers, not names."""
    point_ids = set()
    for shot in plan.get("shots") or []:
        for action in shot.get("actions") or []:
            if action.get("type") == "show_marker" and action.get("place"):
                point_ids.add(str(action["place"]))
    cards = []
    for place in plan.get("places") or []:
        if not place.get("id"):
            continue
        card = dict(place)
        card["parent_id"] = parent_key(place)
        if str(place["id"]) in point_ids or place.get("representation") == "point":
            card["representation"] = "point"
        cards.append(card)
    return cards


def ordered_subjects(plan: dict, cards: list[dict]) -> list[dict]:
    explicit = [card for card in cards if card.get("role") == "subject"]
    if explicit:
        return explicit
    by_id = {str(card["id"]): card for card in cards}
    parent_ids = {parent_key(card) for card in cards if parent_key(card)}
    seen: list[str] = []
    for shot in plan.get("shots") or []:
        frame = shot.get("frame")
        if frame and frame != "world" and frame in by_id and frame not in seen:
            seen.append(str(frame))
        for action in shot.get("actions") or []:
            pid = action.get("place")
            if pid and str(pid) in by_id and str(pid) not in seen:
                seen.append(str(pid))
    leaves = [by_id[pid] for pid in seen if pid not in parent_ids]
    if leaves:
        return leaves
    return [by_id[pid] for pid in seen if pid in by_id]


def dedupe_labels(plan: dict) -> dict:
    """One label action per canonical place id. Later stages keep camera and markers."""
    seen: set[str] = set()
    for shot in plan.get("shots") or []:
        kept = []
        for action in shot.get("actions") or []:
            if action.get("type") == "show_label":
                pid = str(action.get("place") or "")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
            kept.append(action)
        if not kept:
            kept = [{"type": "hold"}]
        shot["actions"] = kept
    plan["label_identities"] = sorted(seen)
    return plan
