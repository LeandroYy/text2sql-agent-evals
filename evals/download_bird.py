"""Baixa o BIRD Mini-Dev (licença CC BY-SA 4.0) para a pasta data/.

- Bancos SQLite: zip oficial (~800 MB; inclui versões MySQL/PostgreSQL, que são descartadas).
- Perguntas: versão atual (2026) do Hugging Face, com o SQL esperado revisado.

Uso: uv run python -m evals.download_bird
"""

import shutil
import urllib.request
import zipfile

from text2sql_agent.config import ROOT

DATA_DIR = ROOT / "data"
ZIP_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
QUESTIONS_URL = "https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/main/data/mini_dev_sqlite.jsonl"
PREFIX_IN_ZIP = "minidev/MINIDEV/dev_databases/"


def main():
    DATA_DIR.mkdir(exist_ok=True)

    questions = DATA_DIR / "mini_dev_sqlite.jsonl"
    print("Baixando perguntas...")
    urllib.request.urlretrieve(QUESTIONS_URL, questions)

    databases = DATA_DIR / "dev_databases"
    if databases.exists():
        print("Bancos já existem em data/dev_databases, pulando o zip.")
        return

    zip_path = DATA_DIR / "minidev.zip"
    print("Baixando bancos (~800 MB)...")
    urllib.request.urlretrieve(ZIP_URL, zip_path)

    print("Extraindo só os bancos SQLite...")
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.startswith(PREFIX_IN_ZIP):
                continue
            relative = info.filename[len(PREFIX_IN_ZIP) :]
            if ".." in relative:  # nunca escrever fora da pasta de destino
                continue
            target = databases / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)

    zip_path.unlink()
    print("Pronto.")


if __name__ == "__main__":
    main()
