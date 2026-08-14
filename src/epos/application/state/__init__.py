"""Module 09 state authority API."""

from epos.application.state.checkpoint import DiceCheckpointService, state_fingerprint
from epos.application.state.commit import AuthoritativeStateManager
from epos.application.state.errors import (
    CheckpointStateMismatchError,
    MutationAuthorityError,
    StateMutationError,
)
from epos.application.state.models import (
    DiceCheckpoint,
    MutationAuthority,
    MutationBatch,
    ReplaceNPCEmotionalStateMutation,
    ReplaceNPCRelationshipMutation,
    SetNPCIntentionsMutation,
    SetNPCLocationMutation,
    SetPlayerLocationMutation,
    SetWorldFlagMutation,
    SetWorldPhaseMutation,
    StateMutation,
    StateReference,
)
from epos.application.state.ports import DiceCheckpointStorePort

__all__ = [
    "AuthoritativeStateManager",
    "CheckpointStateMismatchError",
    "DiceCheckpoint",
    "DiceCheckpointService",
    "DiceCheckpointStorePort",
    "MutationAuthority",
    "MutationAuthorityError",
    "MutationBatch",
    "ReplaceNPCEmotionalStateMutation",
    "ReplaceNPCRelationshipMutation",
    "SetNPCIntentionsMutation",
    "SetNPCLocationMutation",
    "SetPlayerLocationMutation",
    "SetWorldFlagMutation",
    "SetWorldPhaseMutation",
    "StateMutation",
    "StateMutationError",
    "StateReference",
    "state_fingerprint",
]
