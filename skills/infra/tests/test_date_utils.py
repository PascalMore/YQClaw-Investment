import unittest

from skills.infra import get_next_trading_day, get_trading_dates, is_trading_day


class DateUtilsTest(unittest.TestCase):
    def test_get_trading_dates_includes_2026_06_01_session(self):
        self.assertEqual(
            get_trading_dates('2026-05-28', '2026-06-03'),
            [
                '2026-05-28',
                '2026-05-29',
                '2026-06-01',
                '2026-06-02',
                '2026-06-03',
            ],
        )

    def test_is_trading_day_uses_cn_exchange_calendar(self):
        self.assertTrue(is_trading_day('2026-06-01'))
        self.assertFalse(is_trading_day('2026-06-19'))

    def test_next_trading_day_crosses_hardcoded_boundary(self):
        self.assertEqual(get_next_trading_day('2026-05-29'), '2026-06-01')


if __name__ == '__main__':
    unittest.main()
