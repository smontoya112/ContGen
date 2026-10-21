"""Horarios de publicación: próximos huecos diarios en una zona horaria."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Bogota"


def parse_local(text: str, tz: str = DEFAULT_TZ) -> datetime:
    """`2026-11-02T18:30` (hora local de `tz`) o con zona explícita (`...Z`, `...-05:00`) -> datetime con zona."""
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=ZoneInfo(tz))


def next_slots(
    after: datetime,
    times: Iterable[time],
    count: int,
    *,
    tz: str = DEFAULT_TZ,
    taken: Iterable[datetime] = (),
) -> list[datetime]:
    """Los próximos `count` huecos (a las horas `times` de cada día, en `tz`) posteriores a `after`
    que no estén en `taken`. Devuelve datetimes con zona."""
    zone = ZoneInfo(tz)
    busy = {t.astimezone(UTC) for t in taken}
    hours = sorted(times)
    if not hours:
        raise ValueError("indica al menos una hora del día")
    slots: list[datetime] = []
    day = after.astimezone(zone).date()
    while len(slots) < count:
        for hour in hours:
            slot = datetime.combine(day, hour, tzinfo=zone)
            if slot > after and slot.astimezone(UTC) not in busy:
                slots.append(slot)
                if len(slots) == count:
                    break
        day += timedelta(days=1)
    return slots
