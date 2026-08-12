"""Script único (rodar uma vez) pra migrar as capas/fotos que hoje vivem em
disco (modules/<modulo>/database/uploads/) pros bancos Turso, como BLOB
(colunas capa_dados/foto_dados adicionadas em cada db.py). Depois de rodar
com sucesso, o disco deixa de importar pra essas imagens — main.py não
serve mais /static/*-covers//*-uploads, cada módulo serve a própria imagem
via endpoint (ex.: GET /api/musica/albuns/{id}/capa).

Rodar de dentro de webapp/ (mesma convenção do uvicorn):
    cd webapp
    python migrar_imagens_para_blob.py
"""

import mimetypes
from pathlib import Path

import livros.db as livros_db
import musica.db as musica_db
import projetos.db as projetos_db


def _mime_de(caminho: Path) -> str:
    tipo, _ = mimetypes.guess_type(caminho.name)
    return tipo or "image/jpeg"


def migrar_musica() -> int:
    musica_db.inicializar_banco()
    conn = musica_db.get_connection()
    total = 0
    for arquivo in sorted(musica_db.UPLOADS_DIR.glob("*")):
        if not arquivo.is_file():
            continue
        try:
            album_id = int(arquivo.stem)
        except ValueError:
            print(f"[música] ignorando {arquivo.name} (nome não é um id numérico)")
            continue
        dados = arquivo.read_bytes()
        conn.execute(
            "UPDATE albuns SET capa_dados = ?, capa_mime = ? WHERE id = ?",
            (dados, _mime_de(arquivo), album_id),
        )
        total += 1
    conn.commit()
    print(f"[música] {total} capa(s) migrada(s).")
    return total


def migrar_livros() -> int:
    livros_db.inicializar_banco()
    conn = livros_db.get_connection()
    total = 0
    for arquivo in sorted(livros_db.UPLOADS_DIR.glob("*")):
        if not arquivo.is_file():
            continue
        try:
            livro_id = int(arquivo.stem)
        except ValueError:
            print(f"[livros] ignorando {arquivo.name} (nome não é um id numérico)")
            continue
        dados = arquivo.read_bytes()
        conn.execute(
            "UPDATE livros SET capa_dados = ?, capa_mime = ? WHERE id = ?",
            (dados, _mime_de(arquivo), livro_id),
        )
        total += 1
    conn.commit()
    print(f"[livros] {total} capa(s) migrada(s).")
    return total


def migrar_projetos() -> tuple[int, int]:
    projetos_db.inicializar_banco()
    conn = projetos_db.get_connection()
    total_projetos = total_itens = 0
    for arquivo in sorted(projetos_db.UPLOADS_DIR.glob("*")):
        if not arquivo.is_file():
            continue
        dados = arquivo.read_bytes()
        mime = _mime_de(arquivo)
        nome = arquivo.stem
        if nome.startswith("item_"):
            try:
                item_id = int(nome[len("item_"):])
            except ValueError:
                print(f"[projetos] ignorando {arquivo.name} (nome não é um id numérico)")
                continue
            conn.execute(
                "UPDATE projeto_checklist SET foto_dados = ?, foto_mime = ? WHERE id = ?",
                (dados, mime, item_id),
            )
            total_itens += 1
        else:
            try:
                projeto_id = int(nome)
            except ValueError:
                print(f"[projetos] ignorando {arquivo.name} (nome não é um id numérico)")
                continue
            conn.execute(
                "UPDATE projetos SET foto_dados = ?, foto_mime = ? WHERE id = ?",
                (dados, mime, projeto_id),
            )
            total_projetos += 1
    conn.commit()
    print(f"[projetos] {total_projetos} foto(s) de projeto migrada(s), {total_itens} foto(s) de item migrada(s).")
    return total_projetos, total_itens


if __name__ == "__main__":
    print("Migrando imagens de disco pro Turso (BLOB)...")
    migrar_musica()
    migrar_livros()
    migrar_projetos()
    print("Concluído.")
