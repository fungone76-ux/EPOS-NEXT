from epos.domain.outfit import OutfitItem, OutfitState


def test_outfit_layering_has_deterministic_inner_to_outer_order() -> None:
    jacket = OutfitItem(item_id="jacket", name="Jacket", slot="torso", layer=20)
    shirt = OutfitItem(item_id="shirt", name="Shirt", slot="torso", layer=10)
    shoes = OutfitItem(item_id="shoes", name="Shoes", slot="feet", layer=10)

    outfit = OutfitState(items=(jacket, shirt, shoes))

    assert [item.item_id for item in outfit.ordered_items()] == ["shoes", "shirt", "jacket"]
