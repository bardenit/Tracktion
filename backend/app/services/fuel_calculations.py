from datetime import date
from typing import Iterable, Optional, Protocol


class FuelEntryLike(Protocol):
    mileage: float
    gallons: float
    cost: float
    partial_fillup: bool
    missed_fillup: bool
    mpg: Optional[float]
    cost_per_mile: Optional[float]


class DatedFuelEntryLike(Protocol):
    id: int
    date: date
    mileage: float


def validate_fuel_entry_order(
    entries: Iterable[DatedFuelEntryLike],
    entry_date: date,
    mileage: float,
    exclude_id: Optional[int] = None,
) -> None:
    ordered = [entry for entry in entries if entry.id != exclude_id]
    before = [entry for entry in ordered if (entry.date, entry.mileage) < (entry_date, mileage)]
    after = [entry for entry in ordered if (entry.date, entry.mileage) >= (entry_date, mileage)]

    previous = max(before, key=lambda entry: (entry.date, entry.mileage, entry.id), default=None)
    following = min(after, key=lambda entry: (entry.date, entry.mileage, entry.id), default=None)

    if previous and mileage <= previous.mileage:
        raise ValueError(f"Mileage must be greater than {int(previous.mileage):,} mi for this date")
    if following and mileage >= following.mileage:
        raise ValueError(f"Mileage must be less than {int(following.mileage):,} mi for this date")


def recalculate_fuel_economy(entries: Iterable[FuelEntryLike]) -> None:
    last_full = None
    interval_gallons = 0.0
    interval_cost = 0.0
    interval_is_valid = True

    for entry in entries:
        entry.mpg = None
        entry.cost_per_mile = None

        if last_full is None:
            if not entry.partial_fillup:
                last_full = entry
            continue

        interval_gallons += entry.gallons
        interval_cost += entry.cost
        if entry.missed_fillup:
            interval_is_valid = False

        if entry.partial_fillup:
            continue

        miles_driven = entry.mileage - last_full.mileage
        if interval_is_valid and miles_driven > 0 and interval_gallons > 0:
            entry.mpg = miles_driven / interval_gallons
            entry.cost_per_mile = interval_cost / miles_driven

        last_full = entry
        interval_gallons = 0.0
        interval_cost = 0.0
        interval_is_valid = True
