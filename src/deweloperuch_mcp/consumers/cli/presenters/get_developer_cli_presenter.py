"""``GetDeveloperCliPresenter``: ``developers get`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import amount_text, count_text, status_text
from deweloperuch_mcp.consumers.shared.developer_views import DeveloperProfileView
from deweloperuch_mcp.models.values import WHOLE_COUNTRY
from deweloperuch_mcp.usecases.get_developer import GetDeveloperResult


class GetDeveloperCliPresenter:
    """The developer's profile: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetDeveloperResult) -> None:
        show(DeveloperProfileView.from_result(result), self._as_json, self._text)

    @staticmethod
    def _text(profile: DeveloperProfileView) -> str:
        developer = profile.developer
        scope = "cała Polska" if profile.city_slug == WHOLE_COUNTRY else f"[{profile.city_slug}]"
        lines = [f"{developer.name} [{developer.developer_slug}] · {scope}"]
        if developer.website:
            lines.append(f"Strona dewelopera: {developer.website}")
        if profile.developer_url:
            lines.append(f"Profil dewelopera: {profile.developer_url}")
        summary = profile.summary
        lines.append(
            f"Aktywne oferty: {count_text(summary.active_offers)} · inwestycje: "
            f"{count_text(profile.investments_total)} · miasta: {count_text(summary.cities)} · "
            "średnio: "
            + " · ".join(
                [
                    amount_text(summary.avg_price, "PLN"),
                    amount_text(summary.avg_area_m2, "m²", 2),
                    amount_text(summary.avg_price_per_m2, "PLN/m²"),
                ]
            )
        )
        shown = f"Inwestycje: pokazano {len(profile.investments)} z {profile.investments_total}"
        if profile.investments_omitted:
            shown += f" · pominięto {profile.investments_omitted} (zwiększ --limit)"
        lines.append(shown + ".")
        if profile.hint:
            lines.append(f"Wskazówka: {profile.hint}")
        for item in profile.investments:
            place = f" · {item.city}" if item.city else ""
            lines.append(
                f"[{item.investment_slug}] {item.name}{place} · {status_text(item.status)} · "
                f"aktywne oferty {count_text(item.active_offers)} z "
                f"{count_text(item.total_offers)} · "
                + " · ".join(
                    [
                        amount_text(item.avg_price, "PLN"),
                        amount_text(item.avg_area_m2, "m²", 2),
                        amount_text(item.avg_price_per_m2, "PLN/m²"),
                    ]
                )
            )
            if item.investment_url:
                lines.append(f"    {item.investment_url}")
        if profile.cities:
            lines.append("Miasta dewelopera (cała Polska):")
            lines += [
                f"  {city.city} [{city.city_slug}] · inwestycje {count_text(city.investments)} · "
                f"aktywne oferty {count_text(city.active_offers)} · "
                f"{amount_text(city.avg_price, 'PLN')} · "
                f"{amount_text(city.avg_price_per_m2, 'PLN/m²')}"
                for city in profile.cities
            ]
        return "\n".join(lines)
