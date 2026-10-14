"""``View``: the base of the views both consumers present (``consumers.shared``)."""

from pydantic import BaseModel, ConfigDict


class View(BaseModel):
    """Immutable; field names are the models' (D3), never the backend's."""

    model_config = ConfigDict(frozen=True)
