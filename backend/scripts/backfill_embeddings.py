from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import get_conn  # noqa: E402
from app.embedding import dumps, embed_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill book/search embeddings.")
    parser.add_argument("--force", action="store_true", help="Recompute embeddings even when a value already exists.")
    args = parser.parse_args()

    with get_conn() as conn:
        book_where = "1 = 1" if args.force else "embedding IS NULL OR LTRIM(RTRIM(embedding)) = ''"
        rows = conn.cursor().execute(f"SELECT book_info_id, book_name FROM book_infos WHERE {book_where}").fetchall()
        for book_info_id, book_name in rows:
            conn.cursor().execute(
                "UPDATE book_infos SET embedding = ? WHERE book_info_id = ?",
                dumps(embed_text(book_name)),
                book_info_id,
            )

        search_where = "1 = 1" if args.force else "keyword_embedding IS NULL OR LTRIM(RTRIM(keyword_embedding)) = ''"
        try:
            search_rows = conn.cursor().execute(
                f"SELECT search_id, keyword FROM search_history WHERE {search_where}"
            ).fetchall()
        except Exception:
            search_rows = []
        for search_id, keyword in search_rows:
            conn.cursor().execute(
                "UPDATE search_history SET keyword_embedding = ? WHERE search_id = ?",
                dumps(embed_text(keyword)),
                search_id,
            )
        try:
            conn.cursor().execute(
                """
                WITH ranked AS (
                    SELECT search_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY user_id
                               ORDER BY created_time DESC, search_id DESC
                           ) AS rn
                    FROM search_history
                )
                DELETE FROM ranked WHERE rn > 5
                """
            )
        except Exception:
            pass
        print(f"backfilled {len(rows)} book embeddings and {len(search_rows)} search embeddings.")


if __name__ == "__main__":
    main()
