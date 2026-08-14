from epos.domain.ids import EntityId, SessionId, WorldpackId


def test_ids_are_statically_distinct_newtypes() -> None:
    assert SessionId.__supertype__ is str
    assert EntityId.__supertype__ is str
    assert WorldpackId.__supertype__ is str
    assert SessionId("session-1") == "session-1"
