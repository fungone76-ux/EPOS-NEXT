"""Convert the authored Azure Crown YAMLs into the strict EPOS Worldpack schema.

The source documents remain authoritative and untouched.  This converter only
normalizes their shape for the current runtime and carries unsupported fields in
``narrative_config``/``rendering_config`` instead of discarding them.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml

_LORA_TOKEN = re.compile(r"<lora:([^:>]+):(-?[0-9.]+)>")


def _load(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a YAML object")
    return raw


def _dump(path: Path, document: Mapping[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(
            dict(document),
            allow_unicode=True,
            sort_keys=False,
            width=120,
        ),
        encoding="utf-8",
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _clean_library_aliases(source: dict[str, Any]) -> dict[str, Any]:
    """Remove only aliases that ambiguously identify multiple authored entries."""
    entries = source.get("entries", [])
    owners: dict[str, set[str]] = {}
    for entry in entries:
        entry_id = entry["entry_id"]
        for alias in entry.get("aliases", []):
            key = " ".join(alias.strip().casefold().split())
            owners.setdefault(key, set()).add(entry_id)

    ambiguous = {key for key, entry_ids in owners.items() if len(entry_ids) > 1}
    cleaned = cast(dict[str, Any], _json_safe(source))
    for entry in cleaned.get("entries", []):
        unique: list[str] = []
        seen: set[str] = set()
        for alias in entry.get("aliases", []):
            key = " ".join(alias.strip().casefold().split())
            if key in ambiguous or key in seen:
                continue
            seen.add(key)
            unique.append(alias)
        entry["aliases"] = unique
    return cleaned


def _item_slot(name: str) -> str:
    lowered = name.casefold()
    if any(
        token in lowered
        for token in ("stiletto", "pump", "heel", "sandal", "boot", "barefoot")
    ):
        return "feet"
    if any(token in lowered for token in ("stocking", "skirt", "sarong", "bottom")):
        return "legs"
    if any(
        token in lowered
        for token in (
            "dress",
            "gown",
            "blouse",
            "shirt",
            "camisole",
            "swimsuit",
            "bikini",
            "robe",
            "kaftan",
            "lingerie",
            "bodysuit",
            "romper",
            "suit",
        )
    ):
        return "body"
    return "accessory"


def _outfit(
    *,
    outfit_id: str,
    owner_id: str,
    authored_items: list[str],
    tags: list[str],
) -> dict[str, Any]:
    return {
        "outfit_id": outfit_id,
        "owner_id": owner_id,
        "tags": tags,
        "items": [
            {
                "item_id": f"{outfit_id}_item_{index}",
                "name": item,
                "slot": _item_slot(item),
                "layer": index,
            }
            for index, item in enumerate(authored_items, start=1)
        ],
    }


def _convert_world(
    source: dict[str, Any],
    missions: dict[str, Any],
    events: dict[str, Any],
    schedules: dict[str, Any],
    wardrobes: dict[str, Any],
    existing_rendering: dict[str, Any],
    lora_weights: list[dict[str, Any]],
    visual: dict[str, Any],
) -> dict[str, Any]:
    player = source["player_start"]
    facts = {
        item["id"]: {
            "statement": item["statement"],
            "visibility": item["visibility"],
            "does_not_imply": item.get("does_not_imply", []),
        }
        for item in source.get("world_facts", [])
    }
    facts["premise"] = source["premise"]

    narrative_config = {
        "premise": source["premise"],
        "opening_narration": source["opening_narration"],
        "interactive_creation": source["interactive_creation"],
        "open_end": source["open_end"],
        "riserva_dice": source["riserva_dice"],
        "player_resources": player.get("resources", {}),
        "location_descriptions": {
            item["id"]: item["description"] for item in source.get("locations", [])
        },
        "pressures": source.get("pressures", []),
        "relationships": source.get("relationships", []),
        "campaign_missions": source.get("missions", []),
        "mission_progression": missions.get("missions", []),
        "event_definitions": events.get("events", []),
        "schedule_phases": schedules.get("phases", []),
        "schedule_matrix": schedules.get("schedules", {}),
        "wardrobe_location_overrides": wardrobes.get("location_overrides", {}),
        "source_schema_version": source.get("schema_version"),
        "source_id": source.get("id"),
    }
    rendering_config = dict(existing_rendering)
    a1111 = dict(rendering_config.get("a1111", {}))
    a1111["lora_weights"] = lora_weights
    rendering_config["a1111"] = a1111
    rendering_config["visual_policy"] = visual.get("visual_policy", {})
    rendering_config["visual_style_en"] = visual.get("visual_style_en", "")
    rendering_config["negative_extra_en"] = visual.get("negative_extra_en", "")

    return {
        "worldpack_id": source["world_id"],
        "title": source["title"],
        "initial_day": 1,
        "initial_phase": source["start_time_phase"],
        "player": {
            "entity_id": "player",
            "name": player.get("name") or "Protagonista",
            "location_id": source["start_location_id"],
            "adult_verified": True,
            "stats": player.get("skills", {}),
            "inventory": player.get("inventory", []),
            "conditions": player.get("conditions", []),
            "starting_outfit_id": "player_starting",
        },
        "world_truth": {"facts": facts},
        "narrative_config": _json_safe(narrative_config),
        "rendering_config": _json_safe(rendering_config),
    }


def _convert_npcs(source: dict[str, Any], visual: dict[str, Any]) -> dict[str, Any]:
    visual_by_id = {item["id"]: item for item in visual.get("characters", [])}
    converted: list[dict[str, Any]] = []
    for npc in source["npcs"]:
        npc_id = npc["id"]
        secrets = [
            {"secret_id": f"{npc_id}_secret_{index}", "fact": fact}
            for index, fact in enumerate(npc.get("secrets", []), start=1)
        ]
        disclosure_rules: list[dict[str, Any]] = []
        if npc_id == "luna" and secrets:
            disclosure_rules.append(
                {
                    "secret_id": secrets[0]["secret_id"],
                    "required_flags": ["luna_letter_mention_unlocked"],
                }
            )
            if len(secrets) > 1:
                disclosure_rules.append(
                    {
                        "secret_id": secrets[1]["secret_id"],
                        "required_flags": ["luna_letter_reveal_unlocked"],
                    }
                )

        knowledge = {
            f"knowledge_{index}": fact
            for index, fact in enumerate(npc.get("knowledge", []), start=1)
        }
        knowledge.update(
            {
                "age": npc["age"],
                "disclosure_policy": npc["disclosure_policy"],
                "intimate_profile": npc["intimate_profile"],
                "present_at_start": npc["present_at_start"],
            }
        )
        visual_entry = visual_by_id.get(npc_id, {})
        converted.append(
            {
                "entity_id": npc_id,
                "name": npc["name"],
                "role": visual_entry.get("role_prompt_en", "adult resort NPC"),
                "location_id": npc["location_id"],
                "adult_verified": True,
                "personality": npc.get("personality", []),
                "speech_style": npc.get("speech_style", ""),
                "desires": npc.get("desires", []),
                "fears": npc.get("fears", []),
                "goals": npc.get("goals", []),
                "secrets": secrets,
                "disclosure_rules": disclosure_rules,
                "red_lines": npc.get("red_lines", []),
                "stats": npc.get("skills", {}),
                "knowledge": {"facts": knowledge},
                "starting_outfit_id": f"{npc_id}_starting",
            }
        )
    return {"npcs": converted}


def _convert_visual(source: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    loras: dict[str, str] = {}
    weights: list[dict[str, Any]] = []
    characters: list[dict[str, Any]] = []
    for character in source["characters"]:
        converted = {
            "entity_id": character["id"],
            "base_prompt": character["base_prompt"],
            "role_prompt": character.get("role_prompt_en", ""),
            "negative_prompt": source.get("negative_extra_en", ""),
            "visual_gender": "man" if character["id"] == "player" else "woman",
            "canonical_traits": [],
        }
        authored_lora = character.get("character_lora_en")
        if authored_lora:
            match = _LORA_TOKEN.fullmatch(authored_lora.strip())
            if match is None:
                raise ValueError(f"invalid character_lora_en for {character['id']}")
            alias, weight = match.groups()
            converted["lora_alias"] = alias
            loras[alias] = alias if alias.endswith(".safetensors") else f"{alias}.safetensors"
            weights.append({"alias": alias, "weight": float(weight)})
        characters.append(converted)
    return (
        {
            "loras": loras,
            "characters": characters,
            "world_positive": [source["visual_style_en"]],
            "world_negative": [source["negative_extra_en"]],
        },
        weights,
    )


def _convert_wardrobes(
    source: dict[str, Any],
    npcs: dict[str, Any],
    world: dict[str, Any],
    schedules: dict[str, Any],
) -> dict[str, Any]:
    outfits = [
        _outfit(
            outfit_id="player_starting",
            owner_id="player",
            authored_items=world["player_start"]["outfit"],
            tags=["starting"],
        )
    ]
    for npc in npcs["npcs"]:
        outfits.append(
            _outfit(
                outfit_id=f"{npc['id']}_starting",
                owner_id=npc["id"],
                authored_items=npc["starting_outfit"],
                tags=["starting"],
            )
        )
    schedule_matrix = schedules.get("schedules", {})
    for owner_id, days in source["wardrobes"].items():
        for day, phases in days.items():
            for phase, authored_items in phases.items():
                location_id = schedule_matrix.get(owner_id, {}).get(day, {}).get(phase)
                tags = [f"day_{day}", str(phase)]
                if location_id is not None:
                    tags.append(str(location_id))
                outfits.append(
                    _outfit(
                        outfit_id=f"{owner_id}_day_{day}_{phase}",
                        owner_id=owner_id,
                        authored_items=authored_items,
                        tags=tags,
                    )
                )
    return {"outfits": outfits}


def _convert_missions(source: dict[str, Any]) -> dict[str, Any]:
    npc_by_id = {
        "mission_resort_future": ["victoria"],
        "mission_stella_promotion": ["stella"],
        "mission_maria_stability": ["maria"],
        "mission_luna_letter": ["luna"],
        "mission_victoria_save_resort": ["victoria"],
    }
    converted = []
    for mission in source.get("missions", []):
        converted.append(
            {
                "mission_id": mission["id"],
                "status": mission["state"],
                "npc_ids": npc_by_id.get(mission["id"], []),
                "location_ids": [mission["location_id"]],
            }
        )
    return {"missions": converted}


def _convert_events(source: dict[str, Any]) -> dict[str, Any]:
    converted = []
    for event in source.get("events", []):
        item = {
            "event_id": event["id"],
            "status": "pending",
            "npc_ids": event.get("npc_ids", []),
            "location_id": event.get("location_id"),
        }
        mission_active = event.get("trigger", {}).get("mission_active")
        if mission_active is not None:
            item["mission_id"] = mission_active
        converted.append(item)
    return {"events": converted}


def _convert_schedules(source: dict[str, Any]) -> dict[str, Any]:
    converted = []
    for npc_id, days in source.get("schedules", {}).items():
        entries = []
        for day, phases in days.items():
            for phase, location_id in phases.items():
                entries.append(
                    {
                        "phase": f"day_{day}_{phase}",
                        "location_id": location_id,
                    }
                )
        converted.append({"npc_id": npc_id, "entries": entries})
    return {"schedules": converted}


def convert(source_root: Path, target_root: Path) -> None:
    world = _load(source_root / "world.yaml")
    npcs = _load(source_root / "npcs.yaml")
    visual_source = _load(source_root / "visual.yaml")
    missions_source = _load(source_root / "missions.yaml")
    events_source = _load(source_root / "events.yaml")
    schedules_source = _load(source_root / "schedules.yaml")
    wardrobes_source = _load(source_root / "wardrobes.yaml")

    existing_world = _load(target_root / "world.yaml")
    existing_rendering = existing_world.get("rendering_config", {})
    visual, lora_weights = _convert_visual(visual_source)

    _dump(
        target_root / "world.yaml",
        _convert_world(
            world,
            missions_source,
            events_source,
            schedules_source,
            wardrobes_source,
            existing_rendering,
            lora_weights,
            visual_source,
        ),
    )
    _dump(
        target_root / "locations.yaml",
        {
            "locations": [
                {"location_id": item["id"], "name": item["name"]}
                for item in world["locations"]
            ]
        },
    )
    _dump(target_root / "npcs.yaml", _convert_npcs(npcs, visual_source))
    skill_ids = sorted(
        {
            *world["player_start"].get("skills", {}),
            *(skill for npc in npcs["npcs"] for skill in npc.get("skills", {})),
        }
    )
    check_intents = {
        "autorita": ["autorita", "authority", "intimidation"],
        "carisma": ["carisma", "charm"],
        "intuito": ["intuito", "insight", "observe"],
        "negoziazione": ["negoziazione", "persuasion", "bargain"],
        "prestanza": ["prestanza", "athletics", "physical"],
    }
    _dump(
        target_root / "skills.yaml",
        {
            "skills": [
                {
                    "skill_id": skill_id,
                    "name": skill_id.capitalize(),
                    "check_intents": check_intents.get(skill_id, [skill_id]),
                }
                for skill_id in skill_ids
            ]
        },
    )
    _dump(target_root / "missions.yaml", _convert_missions(world))
    _dump(target_root / "events.yaml", _convert_events(events_source))
    _dump(
        target_root / "wardrobes.yaml",
        _convert_wardrobes(wardrobes_source, npcs, world, schedules_source),
    )
    _dump(target_root / "visual.yaml", visual)
    _dump(target_root / "schedules.yaml", _convert_schedules(schedules_source))
    adult_source = source_root / "sex_library.yaml"
    if adult_source.is_file():
        _dump(target_root / "sex_library.yaml", _clean_library_aliases(_load(adult_source)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    convert(args.source, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
