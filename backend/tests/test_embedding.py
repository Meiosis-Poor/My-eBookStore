from backend.app.embedding import _embed_text_fallback, cosine_distance


def test_embedding_fallback_is_deterministic() -> None:
    first = _embed_text_fallback("算法导论")
    second = _embed_text_fallback("算法导论")
    assert first == second
    assert len(first) == 64


def test_cosine_distance_identity_is_zero() -> None:
    vec = _embed_text_fallback("三体")
    assert abs(cosine_distance(vec, vec)) < 1e-9
