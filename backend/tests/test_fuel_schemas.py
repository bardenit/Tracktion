from datetime import date
import unittest

from app.schemas import FuelEntryUpdate


def fuel_update(**overrides):
    values = {
        "date": date(2026, 8, 6),
        "mileage": 10_000,
        "gallons": 10,
        "cost": 30,
    }
    values.update(overrides)
    return FuelEntryUpdate(**values)


class FuelEntryUpdateTests(unittest.TestCase):
    def test_partial_fillup_tracks_omission_separately_from_explicit_false(self):
        omitted = fuel_update()
        explicit_false = fuel_update(partial_fillup=False)

        self.assertNotIn("partial_fillup", omitted.model_fields_set)
        self.assertIn("partial_fillup", explicit_false.model_fields_set)


if __name__ == "__main__":
    unittest.main()
