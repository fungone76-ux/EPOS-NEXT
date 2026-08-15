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
    ReplaceNPCMemoryLayersMutation,
    ReplaceNPCOutfitMutation,
    ReplaceNPCRelationshipMutation,
    ReplacePlayerOutfitMutation,
    SetNPCIntentionsMutation,
    SetNPCLocationMutation,
    SetPlayerLocationMutation,
    SetWorldFlagMutation,
    SetWorldPhaseMutation,
    StateMutation,
    StateReference,
    UpsertWardrobeOutfitMutation,
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
    "ReplaceNPCMemoryLayersMutation",
    "ReplaceNPCOutfitMutation",
    "ReplaceNPCRelationshipMutation",
    "ReplacePlayerOutfitMutation",
    "SetNPCIntentionsMutation",
    "SetNPCLocationMutation",
    "SetPlayerLocationMutation",
    "SetWorldFlagMutation",
    "SetWorldPhaseMutation",
    "StaleAuthoritativeStateError",
    "StateMutation",
    "StateMutationError",
    "StateReference",
    "UpsertWardrobeOutfitMutation",
    "state_fingerprint",
]
