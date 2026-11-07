import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import testsets  # noqa: E402

HAVE_DATA = os.path.isdir(f"{testsets.ROOT}/gtzan/audio/genres")


@unittest.skipUnless(HAVE_DATA, "test-set data not on this machine")
class Sets(unittest.TestCase):
    def test_gtzan_duplicates_are_removed_keeping_the_first_copy_and_the_corrupt_file_is_skipped(self):
        removed = testsets.gtzan_removed_duplicates()
        self.assertEqual(len(removed), 14)
        ids = {c["id"] for c in testsets.gtzan_clips()}
        every = {c["id"] for c in testsets.gtzan_clips(all_files=True)}
        self.assertEqual(len(every), 1000)
        self.assertEqual(len(ids), 1000 - 14 - 1)
        for gone, kept in removed.items():
            self.assertNotIn(gone, ids)
            self.assertIn(kept, ids)
            self.assertLess(kept, gone)                       # the lowest id is kept (same genre: numeric order; rock.00016 vs metal.00058: genre order)
        self.assertNotIn("gtzan/jazz.00054", ids)

    def test_ballroom_has_698_clips_with_style_labels_and_annotations(self):
        clips = testsets.ballroom_clips()
        self.assertEqual(len(clips), 698)
        self.assertEqual(sum(c["style"] in testsets.TRIPLE_STYLES for c in clips), 110 + 65)
        self.assertTrue(all(len(c["beats"]) > 10 for c in clips if c["id"] != "ballroom/Media-103911"))

    def test_hash_lists_match_the_files_on_disk(self):
        self.assertEqual(testsets.verify_lists(), 0)


if __name__ == "__main__":
    unittest.main()
