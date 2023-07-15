from unittest import TestCase

from sweettooth.review.diffutils import get_chunks, new_chunk, new_line


def strip_regions(chunks):
    for chunk in chunks:
        for L in chunk["lines"]:
            L["oldregion"] = None
            L["newregion"] = None


class DiffTest(TestCase):
    def assertDiff(self, a, b, expected, test_regions=False):
        resulted = list(get_chunks(a, b))
        if not test_regions:
            strip_regions(resulted)

        self.assertEqual(resulted, expected)

    def testFakeUnchanged(self):
        a = ["a"]
        b = ["a"]
        self.assertDiff(a, b, [])

    def testFakeDeleted(self):
        a = ["a"]
        b = None
        self.assertDiff(a, b, [new_chunk(tag="delete", lines=[new_line(0, 0)])])

    def testFakeInserted(self):
        a = None
        b = ["a"]
        self.assertDiff(a, b, [new_chunk(tag="insert", lines=[new_line(0, 0)])])

    def testBasicInsert(self):
        a = ["a"]
        b = ["a", "b"]
        self.assertDiff(
            a,
            b,
            [
                new_chunk(tag="equal", lines=[new_line(0, 0)]),
                new_chunk(tag="insert", lines=[new_line(None, 1)]),
            ],
        )

    def testBasicDelete(self):
        a = ["a", "b"]
        b = ["a"]
        self.assertDiff(
            a,
            b,
            [
                new_chunk(tag="equal", lines=[new_line(0, 0)]),
                new_chunk(tag="delete", lines=[new_line(1, None)]),
            ],
        )

    def testBasicReplace(self):
        a = ["a", "b"]
        b = ["a", "c"]
        self.assertDiff(
            a,
            b,
            [
                new_chunk(tag="equal", lines=[new_line(0, 0)]),
                new_chunk(tag="replace", lines=[new_line(1, 1)]),
            ],
        )
