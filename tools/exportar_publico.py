"""Crea una carpeta segura para subir el sitio público a Cloudflare Pages."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public"
ASSET_TYPES = {".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico", ".woff", ".woff2"}


def main():
    if OUTPUT.is_symlink() or OUTPUT.resolve() != ROOT / "public":
        raise RuntimeError("La carpeta public debe estar dentro del proyecto.")

    files = [ROOT / "index.html"]
    files.extend((ROOT / "pages").glob("*.html"))
    files.extend(
        file for file in (ROOT / "assets").rglob("*")
        if file.is_file() and file.suffix.lower() in ASSET_TYPES
    )
    for file in files:
        if file.is_symlink() or not file.resolve().is_relative_to(ROOT):
            raise RuntimeError("No se pueden incluir enlaces a carpetas privadas.")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for file in files:
        destination = OUTPUT / file.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, destination)
    (OUTPUT / "404.html").write_text(
        '<!doctype html><html lang="es"><meta charset="utf-8">'
        '<title>No encontrado</title><h1>Página no encontrada</h1>'
        '<a href="/">Volver al inicio</a></html>',
        encoding="utf-8",
    )
    print(f"Listo: {len(files)} archivos públicos preparados en {OUTPUT}")


if __name__ == "__main__":
    main()
