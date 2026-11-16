"""Curated pattern list (~230 well-known, non-premium LeetCode problems), cross-referenced with Striver's SDE Sheet.

Order matters: patterns are learned roughly top-to-bottom, and problems inside a
pattern go from easier to harder. Titles and difficulty are fetched from LeetCode
during `init`, so only slugs live here.
"""

PATTERNS: list[tuple[str, list[str]]] = [
    ("Arrays & Hashing", [
        "contains-duplicate", "valid-anagram", "two-sum", "majority-element",
        "pascals-triangle", "max-consecutive-ones", "group-anagrams", "top-k-frequent-elements", "product-of-array-except-self",
        "valid-sudoku", "longest-consecutive-sequence", "subarray-sum-equals-k",
        "sort-colors", "next-permutation", "set-matrix-zeroes", "spiral-matrix",
        "rotate-image", "majority-element-ii", "find-the-duplicate-number",
        "first-missing-positive", "reverse-pairs",
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
        "valid-parentheses", "implement-queue-using-stacks", "implement-stack-using-queues",
        "next-greater-element-i", "min-stack",
        "evaluate-reverse-polish-notation", "daily-temperatures", "next-greater-element-ii",
        "asteroid-collision", "decode-string", "online-stock-span", "car-fleet",
        "largest-rectangle-in-histogram",
    ]),
    ("Strings", [
        "roman-to-integer", "longest-common-prefix", "find-the-index-of-the-first-occurrence-in-a-string",
        "reverse-words-in-a-string", "integer-to-roman", "string-to-integer-atoi",
        "count-and-say", "compare-version-numbers", "repeated-string-match",
    ]),
    ("Binary Search", [
        "binary-search", "search-insert-position", "search-a-2d-matrix",
        "find-first-and-last-position-of-element-in-sorted-array", "koko-eating-bananas",
        "find-minimum-in-rotated-sorted-array", "search-in-rotated-sorted-array",
        "find-peak-element", "single-element-in-a-sorted-array", "capacity-to-ship-packages-within-d-days",
        "time-based-key-value-store", "split-array-largest-sum", "median-of-two-sorted-arrays",
    ]),
    ("Linked List", [
        "reverse-linked-list", "delete-node-in-a-linked-list", "merge-two-sorted-lists", "linked-list-cycle",
        "middle-of-the-linked-list", "palindrome-linked-list",
        "intersection-of-two-linked-lists", "remove-nth-node-from-end-of-list",
        "reorder-list", "add-two-numbers", "rotate-list", "copy-list-with-random-pointer",
        "linked-list-cycle-ii", "sort-list", "lru-cache", "lfu-cache", "merge-k-sorted-lists",
        "reverse-nodes-in-k-group",
    ]),
    ("Trees", [
        "binary-tree-inorder-traversal", "binary-tree-preorder-traversal",
        "binary-tree-postorder-traversal", "maximum-depth-of-binary-tree", "invert-binary-tree",
        "same-tree", "symmetric-tree", "diameter-of-binary-tree", "balanced-binary-tree",
        "subtree-of-another-tree", "binary-tree-level-order-traversal",
        "binary-tree-right-side-view", "binary-tree-zigzag-level-order-traversal",
        "maximum-width-of-binary-tree", "count-good-nodes-in-binary-tree",
        "lowest-common-ancestor-of-a-binary-tree", "path-sum-ii",
        "vertical-order-traversal-of-a-binary-tree", "flatten-binary-tree-to-linked-list",
        "populating-next-right-pointers-in-each-node",
        "construct-binary-tree-from-preorder-and-inorder-traversal",
        "construct-binary-tree-from-inorder-and-postorder-traversal",
        "binary-tree-maximum-path-sum", "serialize-and-deserialize-binary-tree",
    ]),
    ("Binary Search Trees", [
        "search-in-a-binary-search-tree", "convert-sorted-array-to-binary-search-tree",
        "lowest-common-ancestor-of-a-binary-search-tree", "validate-binary-search-tree",
        "kth-smallest-element-in-a-bst", "two-sum-iv-input-is-a-bst",
        "construct-binary-search-tree-from-preorder-traversal", "binary-search-tree-iterator",
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
        "palindrome-partitioning", "permutation-sequence", "n-queens", "sudoku-solver", "word-break-ii",
    ]),
    ("Tries", [
        "implement-trie-prefix-tree", "design-add-and-search-words-data-structure",
        "maximum-xor-of-two-numbers-in-an-array", "word-search-ii",
        "maximum-xor-with-an-element-from-array",
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
        "maximum-profit-in-job-scheduling",
    ]),
    ("2-D DP", [
        "unique-paths", "minimum-path-sum", "longest-common-subsequence",
        "coin-change-ii", "target-sum", "best-time-to-buy-and-sell-stock-with-cooldown",
        "edit-distance", "interleaving-string", "longest-increasing-path-in-a-matrix",
        "palindrome-partitioning-ii", "distinct-subsequences", "burst-balloons",
        "super-egg-drop", "regular-expression-matching",
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

# LeetCode problems that also appear in Striver's SDE Sheet (takeuforward.org),
# compiled from memory for reference; the sheet's GFG/InterviewBit-only items are not included.
STRIVER = set("""
set-matrix-zeroes pascals-triangle next-permutation maximum-subarray sort-colors
best-time-to-buy-and-sell-stock rotate-image merge-intervals merge-sorted-array
find-the-duplicate-number search-a-2d-matrix powx-n majority-element majority-element-ii
unique-paths reverse-pairs two-sum 4sum longest-consecutive-sequence
longest-substring-without-repeating-characters reverse-linked-list middle-of-the-linked-list
merge-two-sorted-lists remove-nth-node-from-end-of-list add-two-numbers delete-node-in-a-linked-list
intersection-of-two-linked-lists linked-list-cycle reverse-nodes-in-k-group palindrome-linked-list
linked-list-cycle-ii rotate-list copy-list-with-random-pointer 3sum trapping-rain-water
remove-duplicates-from-sorted-array max-consecutive-ones subsets-ii combination-sum
combination-sum-ii palindrome-partitioning permutation-sequence permutations n-queens
sudoku-solver word-break-ii single-element-in-a-sorted-array search-in-rotated-sorted-array
median-of-two-sorted-arrays kth-largest-element-in-an-array find-median-from-data-stream
top-k-frequent-elements implement-stack-using-queues implement-queue-using-stacks
valid-parentheses next-greater-element-i lru-cache lfu-cache largest-rectangle-in-histogram
sliding-window-maximum min-stack rotting-oranges online-stock-span reverse-words-in-a-string
longest-palindromic-substring roman-to-integer integer-to-roman string-to-integer-atoi
longest-common-prefix repeated-string-match find-the-index-of-the-first-occurrence-in-a-string
valid-anagram count-and-say compare-version-numbers binary-tree-inorder-traversal
binary-tree-preorder-traversal binary-tree-postorder-traversal vertical-order-traversal-of-a-binary-tree
maximum-width-of-binary-tree binary-tree-level-order-traversal maximum-depth-of-binary-tree
diameter-of-binary-tree balanced-binary-tree lowest-common-ancestor-of-a-binary-tree same-tree
binary-tree-zigzag-level-order-traversal binary-tree-maximum-path-sum
construct-binary-tree-from-preorder-and-inorder-traversal
construct-binary-tree-from-inorder-and-postorder-traversal symmetric-tree
flatten-binary-tree-to-linked-list populating-next-right-pointers-in-each-node
search-in-a-binary-search-tree convert-sorted-array-to-binary-search-tree
construct-binary-search-tree-from-preorder-traversal validate-binary-search-tree
lowest-common-ancestor-of-a-binary-search-tree kth-smallest-element-in-a-bst
two-sum-iv-input-is-a-bst binary-search-tree-iterator serialize-and-deserialize-binary-tree
kth-largest-element-in-a-stream flood-fill clone-graph number-of-islands is-graph-bipartite
course-schedule-ii network-delay-time min-cost-to-connect-all-points
maximum-product-subarray longest-increasing-subsequence longest-common-subsequence edit-distance
minimum-path-sum coin-change word-break palindrome-partitioning-ii super-egg-drop
maximum-profit-in-job-scheduling implement-trie-prefix-tree maximum-xor-of-two-numbers-in-an-array
maximum-xor-with-an-element-from-array
""".split())

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
