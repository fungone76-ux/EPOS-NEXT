"""Authoritative wardrobe/outfit state and deterministic layering."""

from pydantic import Field

from epos.domain.base import DomainModel
from epos.domain.ids import EntityId


class OutfitItem(DomainModel):
    item_id: str
    name: str
    slot: str
    layer: int = Field(ge=0)
    coverage: tuple[str, ...] = ()
    material: str | None = None
    color: str | None = None
    state: str | None = None
    visual_entry_id: str | None = None

    @property
    def is_worn(self) -> bool:
        """Removed items stay in state for continuity but are not rendered."""

        return self.state is None or self.state.strip().casefold() not in {
            "removed",
            "off",
        }


class OutfitState(DomainModel):
    items: tuple[OutfitItem, ...] = ()

    def ordered_items(self) -> tuple[OutfitItem, ...]:
        """Return a deterministic inner-to-outer rendering order."""

        return tuple(sorted(self.items, key=lambda item: (item.layer, item.slot, item.item_id)))

    def visible_items(self) -> tuple[OutfitItem, ...]:
        """Return only currently worn items in deterministic rendering order."""

        return tuple(item for item in self.ordered_items() if item.is_worn)


class WardrobeOutfit(DomainModel):
    """One canonical outfit available to exactly one actor."""

    outfit_id: str
    owner_id: EntityId
    tags: tuple[str, ...] = ()
    items: tuple[OutfitItem, ...] = ()
