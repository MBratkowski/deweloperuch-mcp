"""``BuildingDto``: ``GET /api/map/transactions/visible/{investRcnSlug}`` [P] (sample
``api.tx_visible``), a building of the price register with every unit (``UnitDto``) and
its transactions (``TransactionDto``).

The DTOs declare only what the models use; the rest is ignored, among it the raw register
record (``additionalData``, with personal data), ``is_flipped`` (its meaning is [H],
docs/discovery/entities.md), the duplicate ``events`` list (not in the endpoint's
documentation) and the service's counters (``transactions``, ``total_events``): the
models count the units and transactions they get.
"""

import datetime as dt
from collections.abc import Mapping

from deweloperuch_mcp.api.dto.dto import DateText, Dto, Number
from deweloperuch_mcp.models.building import (
    ANOMALY_HIGH,
    ANOMALY_LOW,
    BULK,
    DISCOUNT,
    ENFORCEMENT,
    GOVERNMENT,
    LEGAL_PERSON,
    NATURAL_PERSON,
    PRIMARY,
    REGULAR,
    SECONDARY,
    SHARE,
    Building,
    Transaction,
    Unit,
)

_MARKETS = dict(pierwotny=PRIMARY, wtorny=SECONDARY)
_PARTIES = dict(osobaFizyczna=NATURAL_PERSON, osobaPrawna=LEGAL_PERSON)
# [W] docs/discovery/entities.md, `classification` (RCN): the values are [P]; what each
# means is read from its Polish label (the service's default list shows `transakcja`
# only [P z kodu], hence "regular").
_CLASSES = dict(
    transakcja=REGULAR,
    udzial=SHARE,
    hurt=BULK,
    rzadowa=GOVERNMENT,
    egzekucja=ENFORCEMENT,
    bonifikata=DISCOUNT,
    anomalia_down=ANOMALY_LOW,
    anomalia_up=ANOMALY_HIGH,
)


class TransactionDto(Dto):
    """An entry of a unit's ``sale_event_rcn`` [P]: one transaction; amounts as text."""

    sale_event_rcn_id: int
    amount: Number | None
    amount_sqm: Number | None = None
    currency: str | None = None
    buyerType: str | None = None
    sellerType: str | None = None
    classification: str | None = None
    marketType: str | None = None
    participation: str | None = None
    creation_date: DateText | None = None

    def to_model(self) -> Transaction:
        return Transaction(
            # [W] the day of the deed: in every transaction of the sample api.tx_visible it is
            # the raw record's `transactionDate`, which the core tests of buildings check.
            date=self._day(self.creation_date),
            price=self._number(self.amount),
            price_per_m2=self._number(self.amount_sqm),
            currency=self._text(self.currency),
            market=self._word(self.marketType, _MARKETS),
            classification=self._word(self.classification, _CLASSES),
            buyer=self._word(self.buyerType, _PARTIES),
            seller=self._word(self.sellerType, _PARTIES),
            share=self._text(self.participation),
        )

    @classmethod
    def _word(cls, value: str | None, words: Mapping[str, str]) -> str | None:
        """The models' word for a value of the service; an unknown one passes unchanged."""
        raw = cls._text(value)
        return None if raw is None else words.get(raw, raw)


class UnitDto(Dto):
    """A unit (``sale``) of ``BuildingDto`` [P]."""

    sale_rcn_id: int
    name: str
    floor_number: Number | None = None
    rooms_number: Number | None = None
    size: Number | None = None
    sale_event_rcn: list[TransactionDto]

    def to_model(self) -> Unit:
        """The unit with its transactions oldest first; those of one day in the order the
        register numbered them (the service's own order is not relied on)."""
        ordered = sorted(self.sale_event_rcn, key=self._chronological)
        return Unit(
            unit_id=self.sale_rcn_id,
            name=self.name,
            floor=self._exact_whole(self.floor_number),
            rooms=self._exact_whole(self.rooms_number),
            area_m2=self._number(self.size),
            transactions=tuple(transaction.to_model() for transaction in ordered),
        )

    @classmethod
    def _chronological(cls, transaction: TransactionDto) -> tuple[dt.date, int]:
        return cls._day(transaction.creation_date) or dt.date.min, transaction.sale_event_rcn_id


class BuildingDto(Dto):
    """``GET /api/map/transactions/visible/{investRcnSlug}`` [P] (sample ``api.tx_visible``)."""

    invest_rcn_id: int
    name: str
    city: str
    city_slug: str
    street: str | None = None
    slug: str
    latitude: Number | None = None
    longitude: Number | None = None
    avg_amount: Number | None = None
    avg_size: Number | None = None
    avg_price_sqm: Number | None = None
    sale: list[UnitDto]

    def to_model(self) -> Building:
        """The building with every unit, in the service's order."""
        return Building(
            building_id=self.invest_rcn_id,
            building_slug=self.slug,
            name=self.name,
            city=self.city,
            city_slug=self.city_slug,
            street=self._text(self.street),
            lat=self._number(self.latitude),
            lng=self._number(self.longitude),
            # [W] docs/discovery/endpoints.md, map/transactions/visible: that `avg_amount`,
            # `avg_size` and `avg_price_sqm` are the service's own means over the building
            # follows from their names; over which transactions (all classes or not) is not
            # known, so they are passed on as given, never recomputed (tests pin the sample's).
            avg_price=self._number(self.avg_amount),
            avg_area_m2=self._number(self.avg_size),
            avg_price_per_m2=self._number(self.avg_price_sqm),
            units=tuple(unit.to_model() for unit in self.sale),
        )
