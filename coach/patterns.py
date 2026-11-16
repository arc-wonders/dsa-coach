"""Curated pattern list (~190 well-known, non-premium LeetCode problems).

Order matters: patterns are learned roughly top-to-bottom, and problems inside a
pattern go from easier to harder. Titles and difficulty are fetched from LeetCode
during `init`, so only slugs live here.
"""

PATTERNS: list[tuple[str, list[str]]] = [
    ("Arrays & Hashing", [
        "contains-duplicate", "valid-anagram", "two-sum", "majority-element",
        "group-anagrams", "top-k-frequent-elements", "product-of-array-except-self",
        "valid-sudoku", "longest-consecutive-sequence", "subarray-sum-equals-k",
        "sort-colors", "next-permutation", "set-matrix-zeroes", "spiral-matrix",
        "rotate-image", "first-missing-positive",
    ]),
    ("Two Pointers", [
        "valid-palindrome", "merge-sorted-array", "move-zeroes",
        "remove-duplicates-from-sorted-array", "two-sum-ii-input-array-is-sorted",
        "3sum", "container-with-most-water", "4sum", "trapping-rain-water",
    ]),
    ("Sliding Window", [
        "best-time-to-buy-and-sell-stock", "longest-substring-without-repeating-characters",
        "longest-repeating-character-replacement", "permutation-in-string",
        "max-consecutive-ones-iii", "minimum-size-subarray-sum", "fruit-into-baskets",
        "find-all-anagrams-in-a-string", "minimum-window-substring", "sliding-window-maximum",
    ]),
    ("Stack", [
        "valid-parentheses", "next-greater-element-i", "min-stack",
        "evaluate-reverse-polish-notation", "daily-temperatures", "next-greater-element-ii",
        "asteroid-collision", "decode-string", "online-stock-span", "car-fleet",
        "largest-rectangle-in-histogram",
    ]),
    ("Binary Search", [
        "binary-search", "search-insert-position", "search-a-2d-matrix",
        "find-first-and-last-position-of-element-in-sorted-array", "koko-eating-bananas",
        "find-minimum-in-rotated-sorted-array", "search-in-rotated-sorted-array",
        "find-peak-element", "capacity-to-ship-packages-within-d-days",
        "time-based-key-value-store", "split-array-largest-sum", "median-of-two-sorted-arrays",
    ]),
    ("Linked List", [
        "reverse-linked-list", "merge-two-sorted-lists", "linked-list-cycle",
        "middle-of-the-linked-list", "palindrome-linked-list",
        "intersection-of-two-linked-lists", "remove-nth-node-from-end-of-list",
        "reorder-list", "add-two-numbers", "copy-list-with-random-pointer",
        "linked-list-cycle-ii", "sort-list", "lru-cache", "merge-k-sorted-lists",
        "reverse-nodes-in-k-group",
    ]),
    ("Trees", [
        "maximum-depth-of-binary-tree", "invert-binary-tree", "same-tree",
        "symmetric-tree", "diameter-of-binary-tree", "balanced-binary-tree",
        "subtree-of-another-tree", "binary-tree-level-order-traversal",
        "binary-tree-right-side-view", "binary-tree-zigzag-level-order-traversal",
        "lowest-common-ancestor-of-a-binary-search-tree", "validate-binary-search-tree",
        "kth-smallest-element-in-a-bst", "count-good-nodes-in-binary-tree",
        "lowest-common-ancestor-of-a-binary-tree", "path-sum-ii",
        "construct-binary-tree-from-preorder-and-inorder-traversal",
        "binary-tree-maximum-path-sum", "serialize-and-deserialize-binary-tree",
    ]),
    ("Heap / Priority Queue", [
        "kth-largest-element-in-a-stream", "last-stone-weight",
        "k-closest-points-to-origin", "kth-largest-element-in-an-array",
        "sort-characters-by-frequency", "task-scheduler", "design-twitter",
        "find-median-from-data-stream",
    ]),
    ("Backtracking", [
        "subsets", "combination-sum", "permutations", "subsets-ii",
        "combination-sum-ii", "generate-parentheses",
        "letter-combinations-of-a-phone-number", "word-search",
        "palindrome-partitioning", "n-queens",
    ]),
    ("Tries", [
        "implement-trie-prefix-tree", "design-add-and-search-words-data-structure",
        "word-search-ii",
    ]),
    ("Graphs", [
        "flood-fill", "number-of-islands", "max-area-of-island", "clone-graph",
        "rotting-oranges", "01-matrix", "number-of-provinces", "surrounded-regions",
        "pacific-atlantic-water-flow", "course-schedule", "course-schedule-ii",
        "is-graph-bipartite", "word-ladder",
    ]),
    ("Advanced Graphs", [
        "find-eventual-safe-states", "redundant-connection",
        "number-of-operations-to-make-network-connected", "accounts-merge",
        "network-delay-time", "path-with-minimum-effort",
        "cheapest-flights-within-k-stops", "min-cost-to-connect-all-points",
        "swim-in-rising-water", "reconstruct-itinerary",
    ]),
    ("1-D DP", [
        "climbing-stairs", "min-cost-climbing-stairs", "house-robber", "house-robber-ii",
        "coin-change", "decode-ways", "maximum-product-subarray", "word-break",
        "longest-increasing-subsequence", "partition-equal-subset-sum", "perfect-squares",
        "longest-palindromic-substring", "palindromic-substrings",
    ]),
    ("2-D DP", [
        "unique-paths", "minimum-path-sum", "longest-common-subsequence",
        "coin-change-ii", "target-sum", "best-time-to-buy-and-sell-stock-with-cooldown",
        "edit-distance", "interleaving-string", "longest-increasing-path-in-a-matrix",
        "distinct-subsequences", "burst-balloons", "regular-expression-matching",
    ]),
    ("Greedy", [
        "assign-cookies", "lemonade-change", "maximum-subarray", "jump-game",
        "jump-game-ii", "gas-station", "partition-labels", "hand-of-straights",
        "valid-parenthesis-string", "merge-triplets-to-form-target-triplet", "candy",
    ]),
    ("Intervals", [
        "merge-intervals", "insert-interval", "non-overlapping-intervals",
        "minimum-number-of-arrows-to-burst-balloons", "interval-list-intersections",
        "minimum-interval-to-include-each-query",
    ]),
    ("Bit Manipulation & Math", [
        "single-number", "number-of-1-bits", "counting-bits", "missing-number",
        "power-of-two", "reverse-bits", "happy-number", "plus-one",
        "reverse-integer", "powx-n", "sum-of-two-integers",
    ]),
]

PATTERN_NAMES = [p for p, _ in PATTERNS]

# For problems you solve that are NOT in the list: map LeetCode topic tags to a
# pattern. Checked in this order, so more specific tags win.
TAG_TO_PATTERN: list[tuple[str, str]] = [
    ("Trie", "Tries"),
    ("Union Find", "Advanced Graphs"),
    ("Shortest Path", "Advanced Graphs"),
    ("Topological Sort", "Advanced Graphs"),
    ("Minimum Spanning Tree", "Advanced Graphs"),
    ("Backtracking", "Backtracking"),
    ("Dynamic Programming", "1-D DP"),
    ("Heap (Priority Queue)", "Heap / Priority Queue"),
    ("Linked List", "Linked List"),
    ("Binary Search Tree", "Trees"),
    ("Binary Tree", "Trees"),
    ("Tree", "Trees"),
    ("Graph", "Graphs"),
    ("Breadth-First Search", "Graphs"),
    ("Depth-First Search", "Graphs"),
    ("Monotonic Stack", "Stack"),
    ("Stack", "Stack"),
    ("Sliding Window", "Sliding Window"),
    ("Binary Search", "Binary Search"),
    ("Two Pointers", "Two Pointers"),
    ("Greedy", "Greedy"),
    ("Bit Manipulation", "Bit Manipulation & Math"),
    ("Hash Table", "Arrays & Hashing"),
    ("Math", "Bit Manipulation & Math"),
    ("String", "Arrays & Hashing"),
    ("Array", "Arrays & Hashing"),
]


def pattern_for_tags(tags: list[str]) -> str:
    s = set(tags)
    for tag, pattern in TAG_TO_PATTERN:
        if tag in s:
            return pattern
    return "Arrays & Hashing"
