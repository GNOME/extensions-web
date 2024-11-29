# The code in this file is adapted from ReviewBoard, MIT licensed
# https://github.com/reviewboard/reviewboard
# Copyright 2011 Review Board Team

import re
from difflib import SequenceMatcher
from itertools import zip_longest


class MyersDiffer:
    """
    An implementation of Eugene Myers's O(ND) Diff algorithm based on GNU diff.
    """

    SNAKE_LIMIT = 20

    DISCARD_NONE = 0
    DISCARD_FOUND = 1
    DISCARD_CANCEL = 2

    # The Myers diff algorithm effectively turns the diff problem into a graph
    # search.  It works by finding the "shortest middle snake," which

    class DiffData:
        def __init__(self, data):
            self.data = data
            self.length = len(data)
            self.modified = {}
            self.undiscarded = []
            self.undiscarded_lines = 0
            self.real_indexes = []

    def __init__(self, a, b, ignore_space=False):
        if type(a) is not type(b):
            raise TypeError

        self.a = a
        self.b = b
        self.code_table = {}
        self.last_code = 0
        self.a_data = self.b_data = None
        self.ignore_space = ignore_space
        self.minimal_diff = False

        # SMS State
        self.max_lines = 0
        self.fdiag = None
        self.bdiag = None
        self.downoff = 0
        self.upoff = 0

    def ratio(self):
        self._gen_diff_data()
        a_equals = self.a_data.length - len(self.a_data.modified)
        b_equals = self.b_data.length - len(self.b_data.modified)

        return 1.0 * (a_equals + b_equals) / (self.a_data.length + self.b_data.length)

    def get_opcodes(self):
        """
        Generator that returns opcodes representing the contents of the
        diff.

        The resulting opcodes are in the format of
        (tag, i1, i2, j1, j2)
        """
        self._gen_diff_data()

        a_line = b_line = 0
        last_group = None

        # Go through the entire set of lines on both the old and new files
        while a_line < self.a_data.length or b_line < self.b_data.length:
            a_start = a_line
            b_start = b_line

            if (
                a_line < self.a_data.length
                and not self.a_data.modified.get(a_line, False)
                and b_line < self.b_data.length
                and not self.b_data.modified.get(b_line, False)
            ):
                # Equal
                a_changed = b_changed = 1
                tag = "equal"
                a_line += 1
                b_line += 1
            else:
                # Deleted, inserted or replaced

                # Count every old line that's been modified, and the
                # remainder of old lines if we've reached the end of the new
                # file.
                while a_line < self.a_data.length and (
                    b_line >= self.b_data.length
                    or self.a_data.modified.get(a_line, False)
                ):
                    a_line += 1

                # Count every new line that's been modified, and the
                # remainder of new lines if we've reached the end of the old
                # file.
                while b_line < self.b_data.length and (
                    a_line >= self.a_data.length
                    or self.b_data.modified.get(b_line, False)
                ):
                    b_line += 1

                a_changed = a_line - a_start
                b_changed = b_line - b_start

                assert a_start < a_line or b_start < b_line
                assert a_changed != 0 or b_changed != 0

                if a_changed == 0 and b_changed > 0:
                    tag = "insert"
                elif a_changed > 0 and b_changed == 0:
                    tag = "delete"
                elif a_changed > 0 and b_changed > 0:
                    tag = "replace"

                    if a_changed != b_changed:
                        if a_changed > b_changed:
                            a_line -= a_changed - b_changed
                        elif a_changed < b_changed:
                            b_line -= b_changed - a_changed

                        a_changed = b_changed = min(a_changed, b_changed)

            if last_group and last_group[0] == tag:
                last_group = (
                    tag,
                    last_group[1],
                    last_group[2] + a_changed,
                    last_group[3],
                    last_group[4] + b_changed,
                )
            else:
                if last_group:
                    yield last_group

                last_group = (
                    tag,
                    a_start,
                    a_start + a_changed,
                    b_start,
                    b_start + b_changed,
                )

        if not last_group:
            last_group = ("equal", 0, self.a_data.length, 0, self.b_data.length)

        yield last_group

    def _gen_diff_data(self):
        """
        Generate all the diff data needed to return opcodes or the diff ratio.
        This is only called once during the liftime of a MyersDiffer instance.
        """
        if self.a_data and self.b_data:
            return

        self.a_data = self.DiffData(self._gen_diff_codes(self.a))
        self.b_data = self.DiffData(self._gen_diff_codes(self.b))

        self._discard_confusing_lines()

        self.max_lines = (
            self.a_data.undiscarded_lines + self.b_data.undiscarded_lines + 3
        )

        vector_size = self.a_data.undiscarded_lines + self.b_data.undiscarded_lines + 3
        self.fdiag = [0] * vector_size
        self.bdiag = [0] * vector_size
        self.downoff = self.upoff = self.b_data.undiscarded_lines + 1

        self._lcs(
            0,
            self.a_data.undiscarded_lines,
            0,
            self.b_data.undiscarded_lines,
            self.minimal_diff,
        )
        self._shift_chunks(self.a_data, self.b_data)
        self._shift_chunks(self.b_data, self.a_data)

    def _gen_diff_codes(self, lines):
        """
        Converts all unique lines of text into unique numbers. Comparing
        lists of numbers is faster than comparing lists of strings.
        """
        codes = []

        for line in lines:
            # TODO: Handle ignoring/triming spaces, ignoring casing, and
            #       special hooks

            stripped_line = line.lstrip()

            if self.ignore_space:
                # We still want to show lines that contain only whitespace.
                if len(stripped_line) > 0:
                    line = stripped_line

            try:
                code = self.code_table[line]
            except KeyError:
                # This is a new, unrecorded line, so mark it and store it.
                self.last_code += 1
                code = self.last_code
                self.code_table[line] = code

            codes.append(code)

        return codes

    def _find_sms(self, a_lower, a_upper, b_lower, b_upper, find_minimal):
        """
        Finds the Shortest Middle Snake.
        """
        down_vector = self.fdiag  # The vector for the (0, 0) to (x, y) search
        up_vector = self.bdiag  # The vector for the (u, v) to (N, M) search

        down_k = a_lower - b_lower  # The k-line to start the forward search
        up_k = a_upper - b_upper  # The k-line to start the reverse search
        odd_delta = (down_k - up_k) % 2 != 0

        down_vector[self.downoff + down_k] = a_lower
        up_vector[self.upoff + up_k] = a_upper

        dmin = a_lower - b_upper
        dmax = a_upper - b_lower

        down_min = down_max = down_k
        up_min = up_max = up_k

        cost = 0

        while True:
            cost += 1
            big_snake = False

            if down_min > dmin:
                down_min -= 1
                down_vector[self.downoff + down_min - 1] = -1
            else:
                down_min += 1

            if down_max < dmax:
                down_max += 1
                down_vector[self.downoff + down_max + 1] = -1
            else:
                down_max -= 1

            # Extend the forward path
            for k in range(down_max, down_min - 1, -2):
                tlo = down_vector[self.downoff + k - 1]
                thi = down_vector[self.downoff + k + 1]

                if tlo >= thi:
                    x = tlo + 1
                else:
                    x = thi

                y = x - k
                old_x = x

                # Find the end of the furthest reaching forward D-path in
                # diagonal k
                while (
                    x < a_upper
                    and y < b_upper
                    and self.a_data.undiscarded[x] == self.b_data.undiscarded[y]
                ):
                    x += 1
                    y += 1

                if (
                    odd_delta
                    and up_min <= k <= up_max
                    and up_vector[self.upoff + k] <= x
                ):
                    return x, y, True, True

                if x - old_x > self.SNAKE_LIMIT:
                    big_snake = True

                down_vector[self.downoff + k] = x

            # Extend the reverse path
            if up_min > dmin:
                up_min -= 1
                up_vector[self.upoff + up_min - 1] = self.max_lines
            else:
                up_min += 1

            if up_max < dmax:
                up_max += 1
                up_vector[self.upoff + up_max + 1] = self.max_lines
            else:
                up_max -= 1

            for k in range(up_max, up_min - 1, -2):
                tlo = up_vector[self.upoff + k - 1]
                thi = up_vector[self.upoff + k + 1]

                if tlo < thi:
                    x = tlo
                else:
                    x = thi - 1

                y = x - k
                old_x = x

                while (
                    x > a_lower
                    and y > b_lower
                    and self.a_data.undiscarded[x - 1] == self.b_data.undiscarded[y - 1]
                ):
                    x -= 1
                    y -= 1

                if (
                    not odd_delta
                    and down_min <= k <= down_max
                    and x <= down_vector[self.downoff + k]
                ):
                    return x, y, True, True

                if old_x - x > self.SNAKE_LIMIT:
                    big_snake = True

                up_vector[self.upoff + k] = x

            if find_minimal:
                continue

            # Heuristics courtesy of GNU diff.
            #
            # We check occasionally for a diagonal that made lots of progress
            # compared with the edit distance. If we have one, find the one
            # that made the most progress and return it.
            #
            # This gives us better, more dense chunks, instead of lots of
            # small ones often starting with replaces. It also makes the output
            # closer to that of GNU diff, which more people would expect.

            if cost > 200 and big_snake:
                ret_x, ret_y, best = self._find_diagonal(
                    down_min,
                    down_max,
                    down_k,
                    0,
                    self.downoff,
                    down_vector,
                    lambda x: x - a_lower,
                    lambda x: a_lower + self.SNAKE_LIMIT <= x < a_upper,
                    lambda y: b_lower + self.SNAKE_LIMIT <= y < b_upper,
                    lambda i, k: i - k,
                    1,
                    cost,
                )

                if best > 0:
                    return ret_x, ret_y, True, False

                ret_x, ret_y, best = self._find_diagonal(
                    up_min,
                    up_max,
                    up_k,
                    best,
                    self.upoff,
                    up_vector,
                    lambda x: a_upper - x,
                    lambda x: a_lower < x <= a_upper - self.SNAKE_LIMIT,
                    lambda y: b_lower < y <= b_upper - self.SNAKE_LIMIT,
                    lambda i, k: i + k,
                    0,
                    cost,
                )

                if best > 0:
                    return ret_x, ret_y, False, True

        raise Exception("The function should not have reached here.")

    def _find_diagonal(
        self,
        minimum,
        maximum,
        k,
        best,
        diagoff,
        vector,
        vdiff_func,
        check_x_range,
        check_y_range,
        discard_index,
        k_offset,
        cost,
    ):
        for d in range(maximum, minimum - 1, -2):
            dd = d - k
            x = vector[diagoff + d]
            y = x - d
            v = vdiff_func(x) * 2 + dd

            if v > 12 * (cost + abs(dd)):
                if v > best and check_x_range(x) and check_y_range(y):
                    # We found a sufficient diagonal.
                    k = k_offset
                    x_index = discard_index(x, k)
                    y_index = discard_index(y, k)

                    while (
                        self.a_data.undiscarded[x_index]
                        == self.b_data.undiscarded[y_index]
                    ):
                        if k == self.SNAKE_LIMIT - 1 + k_offset:
                            return x, y, v

                        k += 1
        return 0, 0, 0

    def _lcs(self, a_lower, a_upper, b_lower, b_upper, find_minimal):
        """
        The divide-and-conquer implementation of the Longest Common
        Subsequence (LCS) algorithm.
        """
        # Fast walkthrough equal lines at the start
        while (
            a_lower < a_upper
            and b_lower < b_upper
            and self.a_data.undiscarded[a_lower] == self.b_data.undiscarded[b_lower]
        ):
            a_lower += 1
            b_lower += 1

        while (
            a_upper > a_lower
            and b_upper > b_lower
            and self.a_data.undiscarded[a_upper - 1]
            == self.b_data.undiscarded[b_upper - 1]
        ):
            a_upper -= 1
            b_upper -= 1

        if a_lower == a_upper:
            # Inserted lines.
            while b_lower < b_upper:
                self.b_data.modified[self.b_data.real_indexes[b_lower]] = True
                b_lower += 1
        elif b_lower == b_upper:
            # Deleted lines
            while a_lower < a_upper:
                self.a_data.modified[self.a_data.real_indexes[a_lower]] = True
                a_lower += 1
        else:
            # Find the middle snake and length of an optimal path for A and B
            x, y, low_minimal, high_minimal = self._find_sms(
                a_lower, a_upper, b_lower, b_upper, find_minimal
            )

            self._lcs(a_lower, x, b_lower, y, low_minimal)
            self._lcs(x, a_upper, y, b_upper, high_minimal)

    def _shift_chunks(self, data, other_data):
        """
        Shifts the inserts/deletes of identical lines in order to join
        the changes together a bit more. This has the effect of cleaning
        up the diff.

        Often times, a generated diff will have two identical lines before
        and after a chunk (say, a blank line). The default algorithm will
        insert at the front of that range and include two blank lines at the
        end, but that does not always produce the best looking diff. Since
        the two lines are identical, we can shift the chunk so that the line
        appears both before and after the line, rather than only after.
        """
        i = j = 0
        i_end = data.length

        while True:
            # Scan forward in order to find the start of a run of changes.
            while i < i_end and not data.modified.get(i, False):
                i += 1

                while other_data.modified.get(j, False):
                    j += 1

            if i == i_end:
                return

            start = i

            # Find the end of these changes
            i += 1
            while data.modified.get(i, False):
                i += 1

            while other_data.modified.get(j, False):
                j += 1

            while True:
                run_length = i - start

                # Move the changed chunks back as long as the previous
                # unchanged line matches the last changed line.
                # This merges with the previous changed chunks.
                while start != 0 and data.data[start - 1] == data.data[i - 1]:
                    start -= 1
                    i -= 1

                    data.modified[start] = True
                    data.modified[i] = False

                    while data.modified.get(start - 1, False):
                        start -= 1

                    j -= 1
                    while other_data.modified.get(j, False):
                        j -= 1

                # The end of the changed run at the last point where it
                # corresponds to the changed run in the other data set.
                # If it's equal to i_end, then we didn't find a corresponding
                # point.
                if other_data.modified.get(j - 1, False):
                    corresponding = i
                else:
                    corresponding = i_end

                # Move the changed region forward as long as the first
                # changed line is the same as the following unchanged line.
                while i != i_end and data.data[start] == data.data[i]:
                    data.modified[start] = False
                    data.modified[i] = True

                    start += 1
                    i += 1

                    while data.modified.get(i, False):
                        i += 1

                    j += 1
                    while other_data.modified.get(j, False):
                        j += 1
                        corresponding = i

                if run_length == i - start:
                    break

            # Move the fully-merged run back to a corresponding run in the
            # other data set, if we can.
            while corresponding < i:
                start -= 1
                i -= 1

                data.modified[start] = True
                data.modified[i] = False

                j -= 1
                while other_data.modified.get(j, False):
                    j -= 1

    def _discard_confusing_lines(self):
        def build_discard_list(data, discards, counts):
            many = 5 * self._very_approx_sqrt(data.length / 64)

            for i, item in enumerate(data.data):
                if item != 0:
                    num_matches = counts[item]

                    if num_matches == 0:
                        discards[i] = self.DISCARD_FOUND
                    elif num_matches > many:
                        discards[i] = self.DISCARD_CANCEL

        def scan_run(discards, i, length, index_func):
            consec = 0

            for j in range(length):
                index = index_func(i, j)
                discard = discards[index]

                if j >= 8 and discard == self.DISCARD_FOUND:
                    break

                if discard == self.DISCARD_FOUND:
                    consec += 1
                else:
                    consec = 0

                    if discard == self.DISCARD_CANCEL:
                        discards[index] = self.DISCARD_NONE

                if consec == 3:
                    break

        def check_discard_runs(data, discards):
            i = 0
            while i < data.length:
                # Cancel the provisional discards that are not in the middle
                # of a run of discards
                if discards[i] == self.DISCARD_CANCEL:
                    discards[i] = self.DISCARD_NONE
                elif discards[i] == self.DISCARD_FOUND:
                    # We found a provisional discard
                    provisional = 0

                    # Find the end of this run of discardable lines and count
                    # how many are provisionally discardable.
                    # for j in range(i, data.length):
                    j = i
                    while j < data.length:
                        if discards[j] == self.DISCARD_NONE:
                            break
                        elif discards[j] == self.DISCARD_CANCEL:
                            provisional += 1
                        j += 1

                    # Cancel the provisional discards at the end and shrink
                    # the run.
                    while j > i and discards[j - 1] == self.DISCARD_CANCEL:
                        j -= 1
                        discards[j] = 0
                        provisional -= 1

                    length = j - i

                    # If 1/4 of the lines are provisional, cancel discarding
                    # all the provisional lines in the run.
                    if provisional * 4 > length:
                        while j > i:
                            j -= 1
                            if discards[j] == self.DISCARD_CANCEL:
                                discards[j] = self.DISCARD_NONE
                    else:
                        minimum = 1 + self._very_approx_sqrt(length / 4)
                        j = 0
                        consec = 0
                        while j < length:
                            if discards[i + j] != self.DISCARD_CANCEL:
                                consec = 0
                            else:
                                consec += 1
                                if minimum == consec:
                                    j -= consec
                                elif minimum < consec:
                                    discards[i + j] = self.DISCARD_NONE

                            j += 1

                        scan_run(discards, i, length, lambda x, y: x + y)
                        i += length - 1
                        scan_run(discards, i, length, lambda x, y: x - y)

                i += 1

        def discard_lines(data, discards):
            j = 0
            for i, item in enumerate(data.data):
                if self.minimal_diff or discards[i] == self.DISCARD_NONE:
                    data.undiscarded[j] = item
                    data.real_indexes[j] = i
                    j += 1
                else:
                    data.modified[i] = True

            data.undiscarded_lines = j

        self.a_data.undiscarded = [0] * self.a_data.length
        self.b_data.undiscarded = [0] * self.b_data.length
        self.a_data.real_indexes = [0] * self.a_data.length
        self.b_data.real_indexes = [0] * self.b_data.length
        a_discarded = [0] * self.a_data.length
        b_discarded = [0] * self.b_data.length
        a_code_counts = [0] * (1 + self.last_code)
        b_code_counts = [0] * (1 + self.last_code)

        for item in self.a_data.data:
            a_code_counts[item] += 1

        for item in self.b_data.data:
            b_code_counts[item] += 1

        build_discard_list(self.a_data, a_discarded, b_code_counts)
        build_discard_list(self.b_data, b_discarded, a_code_counts)

        check_discard_runs(self.a_data, a_discarded)
        check_discard_runs(self.b_data, b_discarded)

        discard_lines(self.a_data, a_discarded)
        discard_lines(self.b_data, b_discarded)

    def _very_approx_sqrt(self, i):
        result = 1
        i /= 4
        while i > 0:
            i /= 4
            result *= 2

        return result


ALPHANUM_RE = re.compile(r"\w")


def get_line_changed_regions(oldline, newline):
    if oldline is None or newline is None:
        return (None, None)

    if oldline == newline:
        return (None, None)

    # Use the SequenceMatcher directly. It seems to give us better results
    # for this. We should investigate steps to move to the new differ.
    differ = SequenceMatcher(None, oldline, newline)

    # This thresholds our results -- we don't want to show inter-line diffs if
    # most of the line has changed, unless those lines are very short.

    # FIXME: just a plain, linear threshold is pretty crummy here.  Short
    # changes in a short line get lost.  I haven't yet thought of a fancy
    # nonlinear test.
    if differ.ratio() < 0.6:
        return (None, None)

    oldchanges = []
    newchanges = []
    back = (0, 0)

    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == "equal":
            if (i2 - i1 < 3) or (j2 - j1 < 3):
                back = (j2 - j1, i2 - i1)
            continue

        oldstart, oldend = i1 - back[0], i2
        newstart, newend = j1 - back[1], j2

        if oldchanges != [] and oldstart <= oldchanges[-1][1] < oldend:
            oldchanges[-1] = (oldchanges[-1][0], oldend)
        elif not oldline[oldstart:oldend].isspace():
            oldchanges.append((oldstart, oldend))

        if newchanges != [] and newstart <= newchanges[-1][1] < newend:
            newchanges[-1] = (newchanges[-1][0], newend)
        elif not newline[newstart:newend].isspace():
            newchanges.append((newstart, newend))

        back = (0, 0)

    return (oldchanges, newchanges)


def new_chunk(lines, collapsable=False, tag="equal"):
    return {
        "lines": lines,
        "change": tag,
        "collapsable": collapsable,
    }


def get_fake_chunk(numlines, tag):
    lines = [new_line(oldindex=n, newindex=n) for n in range(numlines)]
    return new_chunk(lines, tag=tag)


def get_linenum(idx):
    if idx is not None:
        return idx + 1
    else:
        return None


def new_line(oldindex, newindex, oldregion=None, newregion=None):
    oldlinenum, newlinenum = get_linenum(oldindex), get_linenum(newindex)
    return dict(
        oldlinenum=oldlinenum,
        newlinenum=newlinenum,
        oldindex=oldindex,
        newindex=newindex,
        oldregion=oldregion,
        newregion=newregion,
    )


def diff_line(old, new):
    oldindex, oldline = old
    newindex, newline = new

    oldregion, newregion = get_line_changed_regions(oldline, newline)
    return new_line(oldindex, newindex, oldregion, newregion)


def get_chunks(a, b):
    if a == b:
        return

    if a is None:
        yield get_fake_chunk(len(b), tag="insert")
        return

    if b is None:
        yield get_fake_chunk(len(a), tag="delete")
        return

    a_num_lines = len(a)
    b_num_lines = len(b)

    linenum = 1

    ignore_space = True

    differ = MyersDiffer(a, b, ignore_space=ignore_space)

    context_num_lines = 3
    collapse_threshold = 2 * context_num_lines + 3

    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        numlines = max(i2 - i1, j2 - j1)

        oldlines = zip(range(i1, i2), a[i1:i2], strict=True)
        newlines = zip(range(j1, j2), b[j1:j2], strict=True)

        lines = [
            diff_line(old, new)
            for old, new in zip_longest(oldlines, newlines, fillvalue=(None, None))
        ]

        if tag == "equal" and numlines > collapse_threshold:
            last_range_start = numlines - context_num_lines

            if linenum == 1:
                yield new_chunk(lines[:last_range_start], collapsable=True)
                yield new_chunk(lines[last_range_start:numlines])
            else:
                yield new_chunk(lines[:context_num_lines])

                if i2 == a_num_lines and j2 == b_num_lines:
                    yield new_chunk(lines[context_num_lines:numlines], collapsable=True)
                else:
                    yield new_chunk(
                        lines[context_num_lines:last_range_start], collapsable=True
                    )
                    yield new_chunk(lines[last_range_start:numlines])
        else:
            yield new_chunk(lines[:numlines], collapsable=False, tag=tag)

        linenum += numlines


def is_valid_move_range(lines):
    """Determines if a move range is valid and should be included.

    This performs some tests to try to eliminate trivial changes that
    shouldn't have moves associated.

    Specifically, a move range is valid if it has at least one line
    with alpha-numeric characters and is at least 4 characters long when
    stripped.
    """
    for line in lines:
        line = line.strip()

        if len(line) >= 4 and ALPHANUM_RE.search(line):
            return True

    return False


def _test(oldfile, newfile):
    old, new = open(oldfile, "r"), open(newfile, "r")
    a, b = old.read().splitlines(), new.read().splitlines()

    chunks = list(get_chunks(a, b))
    old.close()
    new.close()

    return chunks


def main():
    import pprint
    import sys

    pprint.pprint(_test(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
