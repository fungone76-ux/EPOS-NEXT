"""Authoritative state authority and crash-recovery API."""

from epos.application.state.checkpoint import DiceCheckpointService, state_fingerprint
from epos.application.state.commit import AuthoritativeStateManager
from epos.application.state.errors import (
    CheckpointStateMismatchError,
    MutationAuthorityError,
    StaleAuthoritativeStateError,
    StateMutationError,
)
from epos.application.state.models import (
    AdvanceTurnMutation,
    DiceCheckpoint,
    MutationAuthority,
    MutationBatch,
    ReplaceNPCBondStateMutation,
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
    "AdvanceTurnMutation",
    "AuthoritativeStateManager",
    "CheckpointStateMismatchError",
    "DiceCheckpoint",
    "DiceCheckpointService",
    "DiceCheckpointStorePort",
    "MutationAuthority",
    "MutationAuthorityError",
    "MutationBatch",
    "ReplaceNPCBondStateMutation",
    "ReplaceNPCEmotionalStateMutation",
    "ReplaceNPCRelationshipMutation",
    "SetNPCIntentionsMutation",
    "SetNPCLocationMutation",
    "SetPlayerLocationMutation",
    "SetWorldFlagMutation",
    "SetWorldPhaseMutation",
    "StaleAuthoritativeStateError",
    "StateMutation",
    "StateMutationError",
    "StateReference",
    "state_fingerprint",
]
