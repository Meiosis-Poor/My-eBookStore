from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import get_conn  # noqa: E402
from app.embedding import dumps, embed_text  # noqa: E402


def main() -> None:
    with get_conn() as conn:
        rows = conn.cursor().execute(
            "SELECT book_info_id, book_name FROM book_infos WHERE embedding IS NULL OR LTRIM(RTRIM(embedding)) = ''"
        ).fetchall()
        for book_info_id, book_name in rows:
            conn.cursor().execute(
                "UPDATE book_infos SET embedding = ? WHERE book_info_id = ?",
                dumps(embed_text(book_name)),
                book_info_id,
            )
        print(f"backfilled {len(rows)} book embeddings.")


if __name__ == "__main__":
    main()
