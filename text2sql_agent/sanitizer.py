"""Última barreira: tira da resposta coisas que nunca devem chegar ao usuário."""

import re

# Cada padrão tem um motivo:
PATTERNS = [
    # trecho de traceback do Python
    (re.compile(r"Traceback \(most recent call last\):.*", re.DOTALL), "[internal error removed]"),
    # caminhos de arquivo do Windows (C:\...) e do Linux (/home/..., /etc/...)
    (re.compile(r"[A-Za-z]:\\[^\s'\"]+"), "[path removed]"),
    (re.compile(r"(?<![\w.])/(?:home|etc|var|usr|opt|root)/[^\s'\"]+"), "[path removed]"),
    # connection strings e pares chave=valor de credenciais
    (re.compile(r"\b\w+://[^\s:/]+:[^\s@/]+@\S+"), "[connection string removed]"),
    (re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\s*[=:]\s*\S+"), r"\1=[removed]"),
]


def sanitize(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
