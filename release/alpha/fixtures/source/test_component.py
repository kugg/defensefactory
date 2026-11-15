import unittest

from component import release_credential


class ComponentTests(unittest.TestCase):
    def test_verified_peer_receives_synthetic_credential(self):
        self.assertEqual(release_credential("fixture", peer_verified=True), "fixture")


if __name__ == "__main__":
    unittest.main()
