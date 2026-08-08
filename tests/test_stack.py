from app.stack import normalize_suggested_stack


def test_standard_shopify_store_drops_incoherent_database_components() -> None:
    assert normalize_suggested_stack(
        "standard online electrical store",
        ["shopify", "liquid", "postgresql"],
    ) == ["shopify"]


def test_headless_shopify_stack_keeps_custom_components() -> None:
    assert normalize_suggested_stack(
        "custom headless Shopify storefront",
        ["shopify", "react", "node.js"],
    ) == ["shopify", "react", "node.js"]


def test_custom_stack_is_unchanged() -> None:
    assert normalize_suggested_stack(
        "custom booking application",
        ["react", "fastapi", "postgresql"],
    ) == ["react", "fastapi", "postgresql"]

