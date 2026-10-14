"""Test data of the offer market of a city: synthetic market offers."""

from deweloperuch_mcp.models.market_statistics import CityOffers, MarketOffer
from deweloperuch_mcp.models.values import CitySlug

KRAKOW = CitySlug("krakow")


def sale(
    offer_id: int,
    developer: str | None,
    price: float | None,
    area: float | None,
    *,
    investment: str | None = None,
    status: str = "active",
) -> MarketOffer:
    return MarketOffer(
        offer_id=offer_id,
        investment_slug=investment or (None if developer is None else f"{developer}-1"),
        developer_slug=developer,
        status=status,
        price=price,
        area_m2=area,
    )


OFFERS = CityOffers(
    city=KRAKOW,
    offers=(
        sale(1, "atal", 500_000.0, 50.0),
        sale(2, "atal", 700_000.0, 70.0, investment="atal-2"),
        sale(3, "dom", 600_000.0, 40.0),
        sale(4, "dom", 900_000.0, 60.0),
        sale(5, "yit", 300_000.0, 30.0),
        sale(6, None, 400_000.0, 40.0),  # an investment the city does not list
        sale(7, "yit", None, 45.0),  # no price
        sale(8, "yit", 350_000.0, None),  # no area
        sale(9, "atal", 1.0, 1.0, status="archived"),  # never in the summary
    ),
)
