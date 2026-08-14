import json
from copy import deepcopy
from pathlib import Path

import pytest

from epos.domain.errors import EposValidationError
from epos.domain.ids import EntityId, LocationId, SkillId, WorldpackId
from epos.infrastructure.worldpacks.loader import FileSystemWorldpackLoader


def _base_documents() -> dict[str, dict[str, object]]:
    return {
        "world.yaml": {
            "worldpack_id": "resort_world",
            "title": "Resort World",
            "initial_day": 1,
            "initial_phase": "morning",
            "player": {
                "entity_id": "player",
                "name": "Alex",
                "location_id": "lobby",
                "adult_verified": True,
            },
            "world_truth": {"facts": {"setting": "Mediterranean resort"}},
            "narrative_config": {},
            "rendering_config": {},
        },
        "locations.yaml": {
            "locations": [
                {"location_id": "lobby", "name": "Lobby"},
                {"location_id": "pool", "name": "Pool"},
            ]
        },
        "npcs.yaml": {
            "npcs": [
                {
                    "entity_id": "victoria",
                    "name": "Victoria",
                    "role": "director",
                    "location_id": "lobby",
                    "adult_verified": True,
                    "personality": ["controlled", "observant"],
                    "speech_style": "formal",
                    "desires": ["protect the resort"],
                    "fears": [],
                    "goals": ["understand the player"],
                    "secrets": [],
                    "disclosure_rules": [],
                    "red_lines": [],
                    "knowledge": {"facts": {"luna": "guest"}},
                    "beliefs": {"facts": {}},
                    "false_beliefs": {"facts": {}},
                    "discoveries": {"facts": {}},
                    "starting_outfit_id": "victoria_day",
                }
            ]
        },
        "skills.yaml": {
            "skills": [
                {
                    "skill_id": "negoziazione",
                    "name": "Negoziazione",
                    "description": "Social bargaining and persuasion.",
                }
            ]
        },
        "missions.yaml": {
            "missions": [
                {
                    "mission_id": "welcome",
                    "status": "active",
                    "npc_ids": ["victoria"],
                    "location_ids": ["lobby"],
                    "required_skill_ids": ["negoziazione"],
                }
            ]
        },
        "events.yaml": {
            "events": [
                {
                    "event_id": "arrival",
                    "status": "pending",
                    "npc_ids": ["victoria"],
                    "location_id": "lobby",
                    "mission_id": "welcome",
                }
            ]
        },
        "wardrobes.yaml": {
            "outfits": [
                {
                    "outfit_id": "victoria_day",
                    "owner_id": "victoria",
                    "items": [
                        {
                            "item_id": "v_jacket",
                            "name": "White jacket",
                            "slot": "torso",
                            "layer": 2,
                            "coverage": ["torso"],
                            "color": "white",
                        }
                    ],
                }
            ]
        },
        "visual.yaml": {
            "loras": {"victoria_main": "victoria_main.safetensors"},
            "characters": [
                {
                    "entity_id": "victoria",
                    "base_prompt": "adult woman, dark hair",
                    "role_prompt": "resort director",
                    "negative_prompt": "identity drift",
                    "lora_alias": "victoria_main",
                    "visual_gender": "woman",
                    "canonical_traits": ["dark hair", "brown eyes"],
                }
            ],
            "world_positive": ["luxury Mediterranean resort"],
            "world_negative": ["lowres"],
        },
    }


def _write_pack(root: Path, documents: dict[str, dict[str, object]]) -> Path:
    root.mkdir(parents=True)
    for filename, document in documents.items():
        (root / filename).write_text(json.dumps(document), encoding="utf-8")
    return root


async def test_loader_builds_authoritative_world_state_and_keeps_visual_canon_separate(
    tmp_path: Path,
) -> None:
    pack_path = _write_pack(tmp_path / "resort_world", _base_documents())

    loaded = await FileSystemWorldpackLoader().load(pack_path, session_id="session-1")

    assert loaded.world_state.worldpack_id == WorldpackId("resort_world")
    assert loaded.world_state.player.location_id == LocationId("lobby")
    assert loaded.world_state.get_npc(EntityId("victoria")).identity.name == "Victoria"
    assert loaded.world_state.get_npc(EntityId("victoria")).outfit.items[0].item_id == "v_jacket"
    assert SkillId("negoziazione") in loaded.world_state.skill_definitions
    assert loaded.visual.characters[EntityId("victoria")].base_prompt == "adult woman, dark hair"
    assert not hasattr(loaded.world_state.get_npc(EntityId("victoria")), "base_prompt")


async def test_same_loader_accepts_two_radically_different_worldpacks(tmp_path: Path) -> None:
    resort = _write_pack(tmp_path / "resort", _base_documents())
    bronze_docs = _base_documents()
    bronze_docs["world.yaml"] = {
        "worldpack_id": "bronze_age",
        "title": "Bronze Age",
        "initial_day": 1,
        "initial_phase": "dawn",
        "player": {
            "entity_id": "wanderer",
            "name": "Wanderer",
            "location_id": "agora",
            "adult_verified": True,
        },
        "world_truth": {"facts": {"setting": "Aegean city state"}},
        "narrative_config": {},
        "rendering_config": {},
    }
    bronze_docs["locations.yaml"] = {"locations": [{"location_id": "agora", "name": "Agora"}]}
    bronze_docs["npcs.yaml"] = {
        "npcs": [
            {
                "entity_id": "theron",
                "name": "Theron",
                "role": "strategos",
                "location_id": "agora",
                "adult_verified": True,
                "personality": ["severe"],
                "speech_style": "laconic",
                "desires": [],
                "fears": [],
                "goals": [],
                "secrets": [],
                "disclosure_rules": [],
                "red_lines": [],
                "knowledge": {"facts": {}},
                "beliefs": {"facts": {}},
                "false_beliefs": {"facts": {}},
                "discoveries": {"facts": {}},
                "starting_outfit_id": "theron_armor",
            }
        ]
    }
    bronze_docs["skills.yaml"] = {
        "skills": [{"skill_id": "sarissa", "name": "Sarissa", "description": "Spear mastery."}]
    }
    bronze_docs["missions.yaml"] = {
        "missions": [
            {
                "mission_id": "hold_gate",
                "status": "active",
                "npc_ids": ["theron"],
                "location_ids": ["agora"],
                "required_skill_ids": ["sarissa"],
            }
        ]
    }
    bronze_docs["events.yaml"] = {
        "events": [
            {
                "event_id": "assembly",
                "status": "pending",
                "npc_ids": ["theron"],
                "location_id": "agora",
                "mission_id": "hold_gate",
            }
        ]
    }
    bronze_docs["wardrobes.yaml"] = {
        "outfits": [
            {
                "outfit_id": "theron_armor",
                "owner_id": "theron",
                "items": [
                    {
                        "item_id": "bronze_cuirass",
                        "name": "Bronze cuirass",
                        "slot": "torso",
                        "layer": 2,
                        "coverage": ["torso"],
                        "material": "bronze",
                    }
                ],
            }
        ]
    }
    bronze_docs["visual.yaml"] = {
        "loras": {"theron_main": "theron.safetensors"},
        "characters": [
            {
                "entity_id": "theron",
                "base_prompt": "adult man, weathered face",
                "role_prompt": "bronze age strategos",
                "negative_prompt": "modern clothing",
                "lora_alias": "theron_main",
                "visual_gender": "man",
                "canonical_traits": ["short dark hair"],
            }
        ],
        "world_positive": ["bronze age Aegean city"],
        "world_negative": ["modern objects"],
    }
    bronze = _write_pack(tmp_path / "bronze", bronze_docs)

    loader = FileSystemWorldpackLoader()
    resort_loaded = await loader.load(resort, session_id="r1")
    bronze_loaded = await loader.load(bronze, session_id="b1")

    assert set(resort_loaded.world_state.skill_definitions) == {SkillId("negoziazione")}
    assert set(bronze_loaded.world_state.skill_definitions) == {SkillId("sarissa")}
    assert set(resort_loaded.world_state.npcs) == {EntityId("victoria")}
    assert set(bronze_loaded.world_state.npcs) == {EntityId("theron")}


@pytest.mark.parametrize(
    ("document_name", "mutation", "expected"),
    [
        (
            "npcs.yaml",
            lambda doc: doc["npcs"][0].__setitem__("location_id", "missing_room"),
            "unknown location",
        ),
        (
            "missions.yaml",
            lambda doc: doc["missions"][0].__setitem__("required_skill_ids", ["missing_skill"]),
            "unknown skill",
        ),
        (
            "missions.yaml",
            lambda doc: doc["missions"][0].__setitem__("npc_ids", ["missing_npc"]),
            "unknown NPC",
        ),
        (
            "visual.yaml",
            lambda doc: doc["visual.yaml"] if False else doc["characters"][0].__setitem__(
                "lora_alias", "missing_lora"
            ),
            "unknown LoRA alias",
        ),
        (
            "npcs.yaml",
            lambda doc: doc["npcs"][0].__setitem__("starting_outfit_id", "missing_outfit"),
            "invalid outfit",
        ),
        (
            "events.yaml",
            lambda doc: doc["events"][0].__setitem__("mission_id", "missing_mission"),
            "invalid mission reference",
        ),
    ],
)
async def test_loader_rejects_unknown_cross_references(
    tmp_path: Path,
    document_name: str,
    mutation: object,
    expected: str,
) -> None:
    documents = deepcopy(_base_documents())
    typed_mutation = mutation
    assert callable(typed_mutation)
    typed_mutation(documents[document_name])
    pack_path = _write_pack(tmp_path / "bad_pack", documents)

    with pytest.raises(EposValidationError, match=expected):
        await FileSystemWorldpackLoader().load(pack_path, session_id="bad")


async def test_optional_worldpack_files_are_not_required(tmp_path: Path) -> None:
    documents = _base_documents()
    for filename in ("missions.yaml", "events.yaml", "wardrobes.yaml", "visual.yaml"):
        documents.pop(filename)
    documents["npcs.yaml"]["npcs"][0]["starting_outfit_id"] = None
    pack_path = _write_pack(tmp_path / "minimal_pack", documents)

    loaded = await FileSystemWorldpackLoader().load(pack_path, session_id="minimal")

    assert loaded.world_state.missions == {}
    assert loaded.world_state.events == {}
    assert loaded.visual.characters == {}


async def test_schema_rejects_unknown_fields_instead_of_ignoring_them(tmp_path: Path) -> None:
    documents = _base_documents()
    documents["world.yaml"]["invented_field"] = "must fail"
    pack_path = _write_pack(tmp_path / "extra_field", documents)

    with pytest.raises(EposValidationError, match="schema"):
        await FileSystemWorldpackLoader().load(pack_path, session_id="bad-schema")
