"""
Script de consola para diagnosticar comentarios duplicados en la BD.
Ayuda a saber si los repetidos vienen de la base de datos o del scraping (ej. TikTok).

Uso: python check_duplicate_comments.py
"""
import sys
from pathlib import Path

# Asegurar que el proyecto esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_utils import get_connection, USE_POSTGRES


def normalize_text(t: str) -> str:
    if not t:
        return ""
    return " ".join(str(t).lower().split())


def run_checks():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if USE_POSTGRES else "?"
        print("=" * 60)
        print("DIAGNÓSTICO DE COMENTARIOS DUPLICADOS")
        print("=" * 60)

        # 1) Totales por plataforma
        q_platform = """
            SELECT p.platform, COUNT(c.id) as total
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            GROUP BY p.platform
            ORDER BY total DESC
        """
        cursor.execute(q_platform)
        rows = cursor.fetchall()
        print("\n1. Total comentarios por plataforma:")
        for row in rows:
            platform = row[0] if isinstance(row, (list, tuple)) else row["platform"]
            total = row[1] if isinstance(row, (list, tuple)) else row["total"]
            print(f"   {platform}: {total}")

        # 2) ¿Existen duplicados por (post_id, comment_id)? No debería (UNIQUE)
        q_unique = """
            SELECT post_id, comment_id, COUNT(*) as cnt
            FROM comments
            GROUP BY post_id, comment_id
            HAVING COUNT(*) > 1
        """
        cursor.execute(q_unique)
        dup_unique = cursor.fetchall()
        if dup_unique:
            print("\n2. DUPLICADOS por (post_id, comment_id) - ERROR en BD:")
            for row in dup_unique[:10]:
                print(f"   post_id={row[0]}, comment_id={row[1][:40]}..., count={row[2]}")
            if len(dup_unique) > 10:
                print(f"   ... y {len(dup_unique) - 10} más")
        else:
            print("\n2. No hay duplicados por (post_id, comment_id). La BD respeta UNIQUE.")

        # 3) Comentarios con mismo texto + mismo autor (varios registros)
        # Traer comentarios con platform para filtrar TikTok
        q_all = """
            SELECT c.id, c.post_id, c.comment_id, c.text, c.author, p.platform, p.post_id as post_external_id
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            ORDER BY p.platform, c.text, c.author
        """
        cursor.execute(q_all)
        all_rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        if not cols and all_rows:
            cols = ["id", "post_id", "comment_id", "text", "author", "platform", "post_external_id"]

        def row_dict(r):
            if hasattr(r, "keys"):
                return dict(r)
            return dict(zip(cols, r)) if cols else {}

        comments = [row_dict(r) for r in all_rows]

        # Agrupar por (texto normalizado, autor, plataforma)
        from collections import defaultdict
        groups = defaultdict(list)
        for c in comments:
            key = (normalize_text(c.get("text") or ""), (c.get("author") or "").strip(), (c.get("platform") or "").lower())
            if key[0]:  # ignorar texto vacío
                groups[key].append(c)

        repeated = {k: v for k, v in groups.items() if len(v) > 1}
        print("\n3. Grupos de comentarios repetidos (mismo texto + mismo autor):")
        print(f"   Total de grupos con repetición: {len(repeated)}")

        # Por plataforma
        by_platform = defaultdict(lambda: {"groups": 0, "total_rows": 0})
        for key, items in repeated.items():
            platform = key[2] or "unknown"
            by_platform[platform]["groups"] += 1
            by_platform[platform]["total_rows"] += len(items)
        print("   Por plataforma:")
        for plat, data in sorted(by_platform.items(), key=lambda x: -x[1]["total_rows"]):
            print(f"     {plat}: {data['groups']} grupos, {data['total_rows']} filas (repetidas)")

        # 4) En los repetidos de TikTok: ¿mismo post_id interno o distinto?
        tiktok_repeated = [(k, v) for k, v in repeated.items() if k[2] == "tiktok"]
        if tiktok_repeated:
            same_post = 0
            diff_post = 0
            for key, items in tiktok_repeated:
                post_ids = {x.get("post_id") for x in items}
                if len(post_ids) == 1:
                    same_post += 1
                else:
                    diff_post += 1
            print("\n4. TikTok - Comentarios repetidos (mismo texto + autor):")
            print(f"   Grupos donde todos están en el mismo post (post_id): {same_post}")
            print(f"   Grupos donde están en posts distintos (post_id): {diff_post}")
            if diff_post > 0:
                print("   -> Si hay muchos en 'posts distintos', el mismo comentario se guardó")
                print("      asociado a varios videos; suele ser scraping/importación, no BD.")

        # 5) Ejemplo: 3 grupos de TikTok repetidos con detalle
        if tiktok_repeated:
            print("\n5. Ejemplo de grupos TikTok repetidos (primeros 3):")
            for i, (key, items) in enumerate(tiktok_repeated[:3]):
                text_preview = (key[0][:50] + "...") if len(key[0]) > 50 else key[0]
                print(f"\n   Grupo {i+1}: texto=\"{text_preview}\" autor={key[1]}")
                post_externals = [str(x.get("post_external_id") or "") for x in items]
                post_internals = [x.get("post_id") for x in items]
                print(f"   Cantidad de filas: {len(items)}")
                print(f"   post_id (interno) distintos: {len(set(post_internals))}")
                print(f"   post_external_id (video) distintos: {len(set(post_externals))}")
                if len(set(post_externals)) > 1:
                    print("   -> Mismo comentario aparece en VARIOS VIDEOS (post_external_id distinto).")
                    print("      Probable causa: scraping/actor devuelve el mismo comentario para varios posts.")

        print("\n" + "=" * 60)
        print("INTERPRETACIÓN:")
        print("- Si en (2) no hay duplicados: la BD no duplica por (post_id, comment_id).")
        print("- Si en (4) TikTok tiene muchos 'posts distintos': el mismo comentario se")
        print("  guardó para varios videos; suele ser el scraper/actor (Apify) devolviendo")
        print("  el mismo comentario en varios posts, no un fallo de la BD.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_checks()
