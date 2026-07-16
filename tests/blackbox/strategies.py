from __future__ import annotations

import os

from hypothesis import HealthCheck, settings, strategies as st


PROFILE = os.getenv("EBOOKSTORE_BLACKBOX_PROFILE", "smoke").lower()
MAX_EXAMPLES = 100 if PROFILE == "full" else 20
STATEFUL_STEPS = 20 if PROFILE == "full" else 10

settings.register_profile(
    "ebookstore_blackbox",
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    print_blob=True,
)
settings.load_profile("ebookstore_blackbox")

valid_usernames = st.from_regex(r"[A-Za-z][A-Za-z0-9_]{2,15}", fullmatch=True)
valid_passwords = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=6, max_size=24
)
invalid_usernames = st.sampled_from(["", " ", "a", "ab", "\t", "\n"])
invalid_passwords = st.sampled_from(["", "1", "12345", "     ", None])
valid_phones = st.from_regex(r"1[3-9][0-9]{9}", fullmatch=True)
valid_emails = st.builds(lambda name: f"{name}@test.local", valid_usernames)
valid_isbns = st.from_regex(r"TEST-HYP-[A-Z0-9]{8,16}", fullmatch=True)
malicious_text = st.sampled_from(
    ["' OR 1=1--", '" OR "1"="1', "<script>alert(1)</script>", "../../etc/passwd", "\x00"]
)
search_types = st.sampled_from(["title", "author", "isbn"])
invalid_search_types = st.text(min_size=1, max_size=20).filter(
    lambda value: value not in {"title", "author", "isbn"}
)
valid_pages = st.integers(min_value=1, max_value=100)
invalid_page_values = st.sampled_from(["abc", "1.5", "--1", "", "null"])
valid_ratings = st.integers(min_value=1, max_value=5)
invalid_ratings = st.one_of(st.integers(max_value=0), st.integers(min_value=6, max_value=100))
valid_quantities = st.integers(min_value=1, max_value=5)
invalid_quantities = st.one_of(st.integers(max_value=0), st.integers(min_value=6, max_value=1000))
cart_actions = st.lists(
    st.tuples(st.sampled_from(["add", "update", "remove"]), valid_quantities),
    min_size=1,
    max_size=STATEFUL_STEPS,
)
