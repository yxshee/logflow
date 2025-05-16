import unittest
from code.app import bytes_to_readable, format_timedelta
from datetime import timedelta

class TestHelpers(unittest.TestCase):
    def test_bytes_to_readable(self):
        self.assertEqual(bytes_to_readable(500), "500 B")
        self.assertEqual(bytes_to_readable(2048), "2.00 KB")
        self.assertEqual(bytes_to_readable(5 * 1024**2), "5.00 MB")
        self.assertEqual(bytes_to_readable(3 * 1024**3), "3.00 GB")

    def test_format_timedelta(self):
        td = timedelta(days=1, hours=2, minutes=3, seconds=4)
        self.assertEqual(format_timedelta(td), "1d 02:03:04")
        td2 = timedelta(seconds=45)
        self.assertEqual(format_timedelta(td2), "0d 00:00:45")

if __name__ == '__main__':
    unittest.main()
