"""``DeveloperDto``: a developer as the service nests it in an investment, a list item or a
profile (``developer``) [P]."""

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.offer import DeveloperRef


class DeveloperDto(Dto):
    developer_id: int | None = None
    name: str
    slug: str
    description: str | None = None
    website: str | None = None

    def to_model(self) -> DeveloperRef:
        return DeveloperRef(
            developer_slug=self.slug,
            name=self.name,
            website=self._text(self.website),
            description=self._text(self.description),
        )
