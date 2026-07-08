from backend.app.embedding import cosine_distance, embed_text


def test_embedding_fallback_is_deterministic() -> None:
    first = embed_text("算法导论")
    second = embed_text("算法导论")
    assert first == second
    assert len(first) == 64


def test_cosine_distance_identity_is_zero() -> None:
    vec = embed_text("三体")
    assert abs(cosine_distance(vec, vec)) < 1e-9
