"""
Script para LIMPIAR comentarios duplicados ya guardados en la BD.
Para TikTok: mismo texto + mismo autor estaba guardado en varios videos (error del scraper).
Deja UNA sola fila por (texto normalizado, autor) y elimina el resto.

Uso: python clean_duplicate_comments.py
      python clean_duplicate_comments.py --dry-run   (solo muestra qué se borraría, no borra)
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_utils import get_connection, USE_POSTGRES


def normalize_text(t: str) -> str:
    if not t:
        return ""
    return " ".join(str(t).lower().split())


def run_cleanup(dry_run: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    ph = "%s" if USE_POSTGRES else "?"

    try:
        print("=" * 60)
        print("LIMPIEZA DE COMENTARIOS DUPLICADOS (TikTok)")
        print("=" * 60)
        if dry_run:
            print("(MODO DRY-RUN: no se borrará nada, solo se muestra qué se eliminaría)\n")

        # Traer todos los comentarios de TikTok con (id, post_id, text, author)
        cursor.execute("""
            SELECT c.id, c.post_id, c.text, c.author
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE p.platform = 'tiktok'
            ORDER BY c.id
        """)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []

        def to_dict(r):
            if hasattr(r, "keys"):
                return dict(r)
            return dict(zip(cols, r)) if cols else {}

        comments = [to_dict(r) for r in rows]
        print(f"Total comentarios TikTok en la BD: {len(comments)}\n")

        # Agrupar por (texto normalizado, autor) - el mismo comentario repetido en varios videos
        groups = defaultdict(list)
        for c in comments:
            key = (
                normalize_text(c.get("text") or ""),
                (c.get("author") or "").strip()
            )
            if key[0] or key[1]:  # ignorar texto y autor vacíos
                groups[key].append(c["id"])

        ids_to_delete = []
        for key, ids in groups.items():
            if len(ids) > 1:
                # Quedamos con uno (el de menor id); el resto se borran
                keep_id = min(ids)
                ids_to_delete.extend(i for i in ids if i != keep_id)

        if not ids_to_delete:
            print("No hay duplicados (mismo texto + mismo autor en varios posts). Nada que limpiar.")
            return

        print(f"Duplicados a eliminar: {len(ids_to_delete)} filas")
        print(f"(Se mantendrá 1 fila por cada grupo texto+autor; el resto son el mismo comentario en otros videos)\n")

        if dry_run:
            print("IDs que se borrarían (primeros 20):", ids_to_delete[:20])
            if len(ids_to_delete) > 20:
                print(f"... y {len(ids_to_delete) - 20} más")
            return

        # Borrar en lotes para no sobrecargar
        batch = 500
        deleted = 0
        for i in range(0, len(ids_to_delete), batch):
            chunk = ids_to_delete[i : i + batch]
            placeholders = ", ".join([ph] * len(chunk))
            cursor.execute(f"DELETE FROM comments WHERE id IN ({placeholders})", chunk)
            deleted += cursor.rowcount

        conn.commit()
        print(f"Eliminadas {deleted} filas de comentarios duplicados.")
        print("Listo.")
    finally:
        conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    run_cleanup(dry_run=dry_run)
