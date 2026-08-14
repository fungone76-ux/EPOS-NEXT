import pytest
from pydantic import ValidationError

from epos.domain.bond import BondPhase
from epos.domain.ids import EntityId, LocationId
from epos.domain.intimacy import IntimacyState
from epos.domain.npc import NPCIdentity, NPCState
from epos.domain.player import PlayerState


def test_bond_phase_is_general_and_not_love_specific() -> None:
    assert {phase.value for phase in BondPhase} == {
        "none",
        "forming",
        "established",
        "deep",
    }


def test_intimacy_state_has_bounded_npc_owned_dimensions() -> None:
    state = IntimacyState(
        sexual_attraction=8.0,
        desire=7.0,
        arousal=6.0,
        comfort=5.0,
        tension=4.0,
    )

    assert state.completed_sexual_encounters == 0
    assert "consent" not in state.model_fields

    with pytest.raises(ValidationError):
        IntimacyState(desire=10.01)

    with pytest.raises(ValidationError):
        IntimacyState(arousal=-0.01)


def test_npc_tracks_intimacy_per_partner_but_player_desire_is_not_engine_owned() -> None:
    player_id = EntityId("player")
    npc = NPCState(
        identity=NPCIdentity(entity_id=EntityId("victoria"), name="Victoria", role="director"),
        location_id=LocationId("suite"),
        adult_verified=True,
        intimacy={player_id: IntimacyState(desire=4.0)},
    )

    assert npc.adult_verified is True
    assert npc.intimacy[player_id].desire == 4.0

    with pytest.raises(ValidationError):
        PlayerState(
            entity_id=player_id,
            name="Player",
            location_id=LocationId("suite"),
            adult_verified=True,
            desire=5.0,
        )
