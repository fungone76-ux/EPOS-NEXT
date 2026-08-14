"""Statically distinct identifiers used across EPOS contracts."""

from typing import NewType

SessionId = NewType("SessionId", str)
WorldpackId = NewType("WorldpackId", str)
EntityId = NewType("EntityId", str)
LocationId = NewType("LocationId", str)
SkillId = NewType("SkillId", str)
MissionId = NewType("MissionId", str)
EventId = NewType("EventId", str)
MemoryId = NewType("MemoryId", str)
SceneId = NewType("SceneId", str)
TurnNumber = NewType("TurnNumber", int)
StateVersion = NewType("StateVersion", int)
