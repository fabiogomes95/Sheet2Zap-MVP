"""
Gera screenshots (desktop + mobile) e um GIF de demonstração da vitrine.
Requer o servidor rodando em http://127.0.0.1:8000 (gunicorn/flask) e:
    pip install playwright pillow && playwright install chromium
Uso:
    python generate_assets.py
Saída: pasta ./assets
"""

import io
import os
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000/"
OUT = pathlib.Path(__file__).parent / "assets"
OUT.mkdir(exist_ok=True)

# Carrinho de exemplo (ids conforme a ordem da planilha).
CART_JS = (
    "carrinho = {"
    "'0':{nome:'Vestido Floral Midi',tamanho:'M',preco:189.9,qtd:1},"
    "'7':{nome:'Tênis Branco Casual',tamanho:'37',preco:229,qtd:1},"
    "'11':{nome:'Colar Dourado Delicado',tamanho:'Único',preco:45.5,qtd:2}"
    "}; salvar(); render();"
)


def esperar_imagens(page):
    """Aguarda todas as <img> terminarem de carregar."""
    page.wait_for_load_state("networkidle")
    page.evaluate(
        """() => Promise.all(Array.from(document.images)
             .filter(i => !i.complete)
             .map(i => new Promise(r => { i.onload = i.onerror = r; })))"""
    )
    page.wait_for_timeout(400)


def shots_estaticos(browser, tag, viewport, is_mobile):
    ctx = browser.new_context(
        viewport=viewport, device_scale_factor=2, is_mobile=is_mobile
    )
    page = ctx.new_page()

    # 1) Vitrine
    page.goto(BASE)
    esperar_imagens(page)
    page.evaluate("localStorage.clear(); if(window.carrinho){carrinho={};render();}")
    page.screenshot(path=OUT / f"{tag}-1-vitrine.png")

    # 2) Filtro por categoria
    page.locator(".chip", has_text="Vestidos").click()
    page.wait_for_timeout(300)
    page.screenshot(path=OUT / f"{tag}-2-filtro-vestidos.png")

    # 3) Carrinho / checkout
    page.locator(".chip", has_text="Todos").click()
    page.evaluate(CART_JS)
    page.wait_for_timeout(200)
    page.locator(".barra button", has_text="Ver").click()
    page.wait_for_selector("#modalCarrinho.show")
    page.wait_for_timeout(500)
    page.screenshot(path=OUT / f"{tag}-3-carrinho.png")

    ctx.close()
    print(f"  ✓ {tag}: 3 screenshots")


def gerar_gif(browser):
    """Grava o fluxo: adicionar itens -> abrir carrinho -> checkout WhatsApp."""
    ctx = browser.new_context(
        viewport={"width": 390, "height": 780}, device_scale_factor=1, is_mobile=True
    )
    page = ctx.new_page()
    page.goto(BASE)
    esperar_imagens(page)
    page.evaluate("localStorage.clear(); if(window.carrinho){carrinho={};render();}")

    frames = []

    def cap(repeat=1):
        for _ in range(repeat):
            frames.append(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))

    cap(3)                                             # vitrine parada
    adds = page.locator(".btn-add[data-id]")
    adds.nth(0).click(); page.wait_for_timeout(250); cap(2)   # + Vestido Floral
    adds.nth(1).click(); page.wait_for_timeout(250); cap(2)   # + Vestido Longo
    page.mouse.wheel(0, 380); page.wait_for_timeout(250); cap(2)
    adds.nth(3).click(); page.wait_for_timeout(250); cap(2)   # + mais um item
    page.mouse.wheel(0, -380); page.wait_for_timeout(200); cap(1)
    page.locator(".barra button", has_text="Ver").click()
    page.wait_for_selector("#modalCarrinho.show")
    page.wait_for_timeout(500); cap(4)                 # carrinho aberto
    page.locator("#btnFinalizarModal").hover(); page.wait_for_timeout(200); cap(3)

    ctx.close()

    # Downscale para deixar o GIF leve (bom pra WhatsApp/GitHub)
    w = 300
    frames = [f.resize((w, int(f.height * w / f.width))) for f in frames]
    durs = [700] * len(frames)
    durs[:3] = [900, 500, 500]
    durs[-3:] = [1200, 1200, 1600]
    frames[0].save(
        OUT / "demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=durs,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"  ✓ demo.gif ({len(frames)} frames)")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        shots_estaticos(browser, "desktop", {"width": 1366, "height": 850}, False)
        shots_estaticos(browser, "mobile", {"width": 390, "height": 780}, True)
        gerar_gif(browser)
        browser.close()
    print("Pronto! Arquivos em", OUT)


if __name__ == "__main__":
    main()
