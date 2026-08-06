import unittest
from datetime import date
from types import SimpleNamespace

from app.services.fuel_calculations import recalculate_fuel_economy, validate_fuel_entry_order


def entry(mileage, gallons, cost, *, partial_fillup=False, missed_fillup=False):
    return SimpleNamespace(
        mileage=mileage,
        gallons=gallons,
        cost=cost,
        partial_fillup=partial_fillup,
        missed_fillup=missed_fillup,
        mpg=999,
        cost_per_mile=999,
    )


class RecalculateFuelEconomyTests(unittest.TestCase):
    def test_partial_fill_is_combined_with_next_full_fill(self):
        entries = [
            entry(1_000, 10, 30),
            entry(1_100, 4, 12, partial_fillup=True),
            entry(1_250, 6, 18),
        ]

        recalculate_fuel_economy(entries)

        self.assertIsNone(entries[1].mpg)
        self.assertEqual(entries[2].mpg, 25)
        self.assertEqual(entries[2].cost_per_mile, 0.12)

    def test_multiple_partial_fills_are_accumulated(self):
        entries = [
            entry(2_000, 8, 24),
            entry(2_100, 2, 6, partial_fillup=True),
            entry(2_200, 3, 9, partial_fillup=True),
            entry(2_300, 5, 15),
        ]

        recalculate_fuel_economy(entries)

        self.assertEqual(entries[3].mpg, 30)
        self.assertEqual(entries[3].cost_per_mile, 0.1)

    def test_missed_fill_invalidates_open_partial_interval(self):
        entries = [
            entry(3_000, 10, 30),
            entry(3_100, 3, 9, partial_fillup=True, missed_fillup=True),
            entry(3_250, 7, 21),
            entry(3_450, 10, 30),
        ]

        recalculate_fuel_economy(entries)

        self.assertIsNone(entries[2].mpg)
        self.assertEqual(entries[3].mpg, 20)

    def test_partial_fills_before_first_full_tank_do_not_create_mpg(self):
        entries = [
            entry(4_000, 3, 9, partial_fillup=True),
            entry(4_100, 7, 21),
        ]

        recalculate_fuel_economy(entries)

        self.assertIsNone(entries[0].mpg)
        self.assertIsNone(entries[1].mpg)


class ValidateFuelEntryOrderTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            SimpleNamespace(id=1, date=date(2026, 1, 1), mileage=1_000),
            SimpleNamespace(id=2, date=date(2026, 1, 10), mileage=1_200),
        ]

    def test_accepts_backdated_entry_between_neighbor_mileages(self):
        validate_fuel_entry_order(self.entries, date(2026, 1, 5), 1_100)

    def test_rejects_backdated_entry_above_next_mileage(self):
        with self.assertRaisesRegex(ValueError, "less than"):
            validate_fuel_entry_order(self.entries, date(2026, 1, 5), 1_300)

    def test_rejects_update_above_next_mileage(self):
        entries = self.entries + [SimpleNamespace(id=3, date=date(2026, 1, 20), mileage=1_400)]

        with self.assertRaisesRegex(ValueError, "less than"):
            validate_fuel_entry_order(entries, date(2026, 1, 10), 1_500, exclude_id=2)


if __name__ == "__main__":
    unittest.main()
