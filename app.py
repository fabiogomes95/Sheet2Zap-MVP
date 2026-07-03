"""
Vitrine MVP — Flask + Google Sheets (CSV publicado) + Checkout via WhatsApp.

Arquitetura minimalista de propósito:
- Banco de dados = uma planilha do Google Sheets publicada como CSV.
- Sem painel admin: a lojista edita produtos direto na planilha.
- Sem gateway de pagamento: o checkout gera um link do WhatsApp com o pedido.

Rode com:
    pip install -r requirements.txt
    cp .env.example .env   # e preencha os valores
    python app.py
"""

import csv
import io
import os
import re
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

load_dotenv()

app = Flask(__name__)

SHEET_CSV_URL = os.getenv("SHEET_CSV_URL", "")
WHATSAPP_LOJISTA = os.getenv("WHATSAPP_LOJISTA", "5511999999999")
NOME_LOJA = os.getenv("NOME_LOJA", "Minha Loja")
CHAVE_PIX = os.getenv("CHAVE_PIX", "")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

# CSV local usado como fallback quando SHEET_CSV_URL não está configurado.
# Assim o app roda de cara para testes/demo, sem precisar da planilha.
CSV_EXEMPLO = os.path.join(os.path.dirname(__file__), "produtos_exemplo.csv")

# Cache simples em memória para não bater no Google a cada request.
_cache = {"data": None, "ts": 0.0}

# Extrai o ID de qualquer formato comum de link do Google Drive.
_DRIVE_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)|[?&]id=([a-zA-Z0-9_-]+)")


def converter_link_drive(url):
    """Transforma um link de compartilhamento do Google Drive em link de imagem.

    O link normal do Drive (…/file/d/ID/view) NÃO funciona dentro de <img>.
    O endpoint 'thumbnail' é o mais confiável para embutir imagens.

    Aceita formatos como:
        https://drive.google.com/file/d/ID/view?usp=sharing
        https://drive.google.com/open?id=ID
        https://drive.google.com/uc?export=view&id=ID
    Qualquer outra URL (Unsplash, Imgur, etc.) é devolvida sem alteração.
    """
    if not url or "drive.google.com" not in url:
        return url
    m = _DRIVE_ID_RE.search(url)
    if not m:
        return url
    file_id = m.group(1) or m.group(2)
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800"


def _to_float(valor):
    """Converte '19,90' ou '19.90' em float. Retorna 0.0 se vazio/inválido."""
    if valor is None:
        return 0.0
    txt = str(valor).strip().replace("R$", "").replace(" ", "")
    if not txt:
        return 0.0
    # Trata formato brasileiro: milhar com '.' e decimal com ','
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return 0.0


def _to_int(valor):
    """Converte estoque em inteiro. Retorna 0 se vazio/inválido."""
    try:
        return int(float(str(valor).strip().replace(",", ".")))
    except (ValueError, AttributeError):
        return 0


def carregar_produtos():
    """Lê o CSV publicado do Google Sheets e devolve uma lista de produtos.

    Colunas esperadas na planilha (primeira linha = cabeçalho):
        Nome | Foto URL | Tamanho | Preco | Estoque

    Nomes de coluna são normalizados (minúsculas, sem acento básico) para
    tolerar pequenas variações ("Preço", "Foto", etc.).
    """
    agora = time.time()
    if _cache["data"] is not None and (agora - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    if SHEET_CSV_URL:
        resp = requests.get(SHEET_CSV_URL, timeout=10)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        conteudo = resp.text
    else:
        # Sem planilha configurada: usa o CSV de exemplo para não ficar vazio.
        with open(CSV_EXEMPLO, encoding="utf-8") as f:
            conteudo = f.read()

    leitor = csv.DictReader(io.StringIO(conteudo))

    def chave(nome):
        return (
            nome.strip().lower()
            .replace("ç", "c").replace("á", "a").replace("ã", "a")
            .replace("â", "a").replace("é", "e").replace("ê", "e")
            .replace("í", "i").replace("ó", "o").replace("ô", "o")
            .replace("ú", "u")
        )

    produtos = []
    for i, linha_bruta in enumerate(leitor):
        linha = {chave(k): (v or "").strip() for k, v in linha_bruta.items() if k}

        nome = linha.get("nome", "")
        if not nome:
            continue  # ignora linhas em branco

        foto = linha.get("foto url") or linha.get("foto") or linha.get("fotourl", "")
        foto = converter_link_drive(foto)
        estoque = _to_int(linha.get("estoque", "0"))

        produtos.append(
            {
                "id": i,
                "nome": nome,
                "foto": foto,
                "tamanho": linha.get("tamanho", ""),
                "preco": _to_float(linha.get("preco") or linha.get("preço", "0")),
                "estoque": estoque,
                "esgotado": estoque <= 0,
            }
        )

    _cache["data"] = produtos
    _cache["ts"] = agora
    return produtos


@app.route("/")
def index():
    try:
        produtos = carregar_produtos()
        erro = None
    except Exception as exc:  # noqa: BLE001 — MVP: mostra erro amigável na tela
        produtos = []
        erro = f"Não consegui ler a planilha: {exc}"

    return render_template(
        "index.html",
        produtos=produtos,
        erro=erro,
        nome_loja=NOME_LOJA,
        whatsapp_lojista=WHATSAPP_LOJISTA,
        chave_pix=CHAVE_PIX,
    )


@app.route("/api/produtos")
def api_produtos():
    """Endpoint JSON opcional — útil para debug ou um front separado."""
    try:
        return jsonify(carregar_produtos())
    except Exception as exc:  # noqa: BLE001
        return jsonify({"erro": str(exc)}), 502


if __name__ == "__main__":
    # debug=True só em desenvolvimento. Em produção use gunicorn/waitress.
    app.run(host="0.0.0.0", port=5000, debug=True)
