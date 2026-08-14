"""Authoritative outfit state and deterministic layering."""

from pydantic import Field

from epos.domain.base import DomainModel


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


class OutfitState(DomainModel):
    items: tuple[OutfitItem, ...] = ()

    def ordered_items(self) -> tuple[OutfitItem, ...]:
        """Return a deterministic inner-to-outer rendering order."""

        return tuple(sorted(self.items, key=lambda item: (item.layer, item.slot, item.item_id)))
