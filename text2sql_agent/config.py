"""Configurações do projeto, lidas do arquivo .env (veja .env.example)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

# Pasta com os bancos SQLite do BIRD Mini-Dev (um subdiretório por banco).
DATABASES_DIR = Path(os.getenv("DATABASES_DIR", ROOT / "data" / "dev_databases"))

# Modelos no formato "provedor:modelo" do init_chat_model do LangChain.
# O auditor usa outro modelo de propósito: quem responde não é quem julga.
AGENT_MODEL = os.getenv("AGENT_MODEL", "google_genai:gemini-3.5-flash-lite")
GUARDRAIL_MODEL = os.getenv("GUARDRAIL_MODEL", AGENT_MODEL)
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "google_genai:gemini-3.1-flash-lite")

# Limite de requisições por minuto, para caber na cota gratuita da API.
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "10"))

# Limites de segurança e de custo.
MAX_QUESTION_CHARS = 3000  # pré-filtro: perguntas maiores são recusadas sem chamar o LLM (a maior do BIRD tem ~1.600)
MAX_ROWS_TO_LLM = 50  # linhas de resultado que o agente vê (controla tokens)
QUERY_TIMEOUT_SECONDS = 20  # consultas mais longas são interrompidas
AGENT_MAX_STEPS = 15  # chamadas de ferramenta permitidas por pergunta
