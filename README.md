# Vitrine MVP — Flask + Google Sheets + WhatsApp

Vitrine mobile-first que lê os produtos de uma planilha do Google Sheets e
finaliza o pedido enviando um resumo formatado para o WhatsApp da lojista.
Sem banco de dados, sem painel admin, sem gateway de pagamento.

## Como funciona
- **Produtos** = planilha do Google Sheets publicada como CSV (a lojista edita direto lá).
- **Carrinho** = 100% no navegador (LocalStorage). Nada é salvo no servidor.
- **Checkout** = botão gera um link `wa.me` com o pedido e o total; a lojista responde com o PIX.
- Produto com **Estoque = 0** aparece cinza e como "Esgotado".

## 1. Preparar a planilha
Crie uma planilha com estas colunas **na primeira linha**:

| Nome | Foto URL | Tamanho | Preco | Estoque |
|------|----------|---------|-------|---------|
| Vestido Floral | https://.../foto.jpg | M | 89,90 | 3 |
| Bolsa de Palha | https://.../bolsa.jpg | Único | 120,00 | 0 |

Depois: **Arquivo → Compartilhar → Publicar na web → aba desejada → formato CSV → Publicar.**
Copie o link gerado (termina em `output=csv`).

> Dica: as fotos precisam ser URLs públicas (ex: Imgur, Google Drive com link direto, etc.).

## 2. Configurar e rodar
```bash
pip install -r requirements.txt
cp .env.example .env      # preencha SHEET_CSV_URL e WHATSAPP_LOJISTA
python app.py
```
Abra http://localhost:5000

> Sem `SHEET_CSV_URL` configurado, o app carrega automaticamente o
> `produtos_exemplo.csv` — ótimo para testar tudo antes de ligar na planilha real.

### Fotos do Google Drive
Cole o link normal de compartilhamento do Drive (`.../file/d/ID/view?...`) na
coluna **Foto URL**. O `app.py` converte sozinho para um link de imagem que
funciona dentro do `<img>` (`converter_link_drive`). Só garanta que o arquivo
esteja compartilhado como **"qualquer pessoa com o link"**.

## 3. Deploy no Render (grátis)
O repo já vem com `Procfile` e `render.yaml`. Passo a passo:

1. Suba este projeto para um repositório no GitHub.
2. No [dashboard do Render](https://dashboard.render.com): **New + → Blueprint**.
3. Conecte o repositório. O Render lê o `render.yaml` e cria o Web Service sozinho.
4. Em **Environment**, preencha as variáveis marcadas como `sync: false`:
   `SHEET_CSV_URL`, `WHATSAPP_LOJISTA`, `CHAVE_PIX` (e ajuste `NOME_LOJA`).
5. **Create** → aguarde o build. A loja fica em `https://loja-mvp.onrender.com`.

> **Plano free do Render "dorme"** após ~15 min sem acesso; o primeiro request
> depois disso leva alguns segundos. Para loja de baixo movimento é aceitável.
> Se precisar sempre ligada, suba para o plano Starter (US$ 7/mês).

Se preferir sem o Blueprint: **New + → Web Service**, e configure manualmente
`Build: pip install -r requirements.txt` e `Start: gunicorn app:app --bind 0.0.0.0:$PORT`.

### Rodar como em produção localmente
```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## Variáveis de ambiente (.env)
| Variável | Descrição |
|----------|-----------|
| `SHEET_CSV_URL` | Link CSV publicado do Google Sheets |
| `WHATSAPP_LOJISTA` | Número da lojista, só dígitos, com DDI+DDD (ex: 5511999999999) |
| `NOME_LOJA` | Nome exibido no cabeçalho |
| `CHAVE_PIX` | Chave PIX (opcional, aparece na mensagem) |
| `CACHE_TTL` | Segundos de cache da planilha (padrão 60) |

## Alternativa: API oficial do Google Sheets
A abordagem CSV publicado é a mais barata (sem credenciais). Se um dia precisar
de dados privados ou escrita, troque `carregar_produtos()` por algo assim:

```python
# pip install gspread google-auth
import gspread
gc = gspread.service_account(filename="credenciais.json")  # service account
aba = gc.open("Produtos").sheet1
registros = aba.get_all_records()  # lista de dicts, mesmo formato do CSV
```
Requer criar um projeto no Google Cloud, ativar a Sheets API e compartilhar a
planilha com o e-mail da service account. Para o MVP, mantenha o CSV.
