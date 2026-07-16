from backend.app.embedding import _embed_text_fallback, cosine_distance, dumps
from backend.app.main import sort_title_search_results, title_token_coverage


def test_embedding_fallback_is_deterministic() -> None:
    first = _embed_text_fallback("算法导论")
    second = _embed_text_fallback("算法导论")
    assert first == second
    assert len(first) == 64


def test_cosine_distance_identity_is_zero() -> None:
    vec = _embed_text_fallback("三体")
    assert abs(cosine_distance(vec, vec)) < 1e-9


def test_title_token_coverage_normalizes_and_deduplicates_tokens() -> None:
    assert title_token_coverage("Python 入门 Python", " python   入门 PYTHON ") == 14 / 16
    assert title_token_coverage("深入理解Python", "python 入门") == 6 / 10
    assert title_token_coverage("算法导论", "算法") == 2 / 4
    assert title_token_coverage("数据库系统", "深度学习") == 0


def test_title_search_places_coverage_matches_before_embedding_fallback() -> None:
    target = [1.0, 0.0]
    books = [
        {
            "bookItemId": 3,
            "bookName": "Unmatched semantic result",
            "embedding": dumps(target),
            "salesCount": 100,
        },
        {
            "bookItemId": 2,
            "bookName": "Python Cookbook",
            "embedding": dumps([0.0, 1.0]),
            "salesCount": 1,
        },
        {
            "bookItemId": 1,
            "bookName": "Python 入门",
            "embedding": dumps([0.0, 1.0]),
            "salesCount": 1,
        },
        {
            "bookItemId": 4,
            "bookName": "Another unmatched result",
            "embedding": dumps([0.0, 1.0]),
            "salesCount": 200,
        },
    ]

    ranked = sort_title_search_results(books, "python 入门", target)

    assert [book["bookItemId"] for book in ranked] == [1, 2, 3, 4]
