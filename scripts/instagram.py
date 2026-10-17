"""Imagem e legenda dos posts do Instagram, e publicação pela API oficial.

- gerar_card(): cria a imagem 1080x1350 (JPEG) de um produto. Chamado pelo build.py,
  que salva em public/ig/<slug>.jpg (fica público junto com o site).
- legenda(): monta a legenda do post.
- python scripts/instagram.py publicar: publica o próximo produto ainda não postado.
  Precisa das variáveis IG_USER_ID e IG_ACCESS_TOKEN (segredos do GitHub).
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FONTES = Path(__file__).resolve().parent / "fontes"
REGISTRO = RAIZ / "content" / "instagram-postados.json"

W, H = 1080, 1350
TINTA = (22, 26, 39)        # grafite da marca
FUNDO = (244, 245, 247)
PAPEL = (255, 255, 255)
LILAS = (255, 138, 31)       # laranja da etiqueta
LILAS_TEXTO = (90, 42, 0)
VERDE = (22, 26, 39)         # selo de desconto
LARANJA = (254, 109, 1)
APAGADO = (91, 97, 112)
MARCA = RAIZ / "static" / "img" / "marca"


def fonte(peso: int, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / f"lexend-latin-{peso}-normal.woff"), tamanho)


def brl(v) -> str:
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def endereco_curto(site: dict) -> str:
    u = site["url"].split("://", 1)[-1].rstrip("/")
    return u[4:] if u.startswith("www.") else u


# ------------------------------------------------------------------ imagem

def carregar_foto(src: str | None) -> Image.Image | None:
    if not src or src.lower().endswith(".svg"):
        return None
    try:
        if src.startswith("http"):
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 achadoteca"})
            dados = urllib.request.urlopen(req, timeout=20).read()
            return Image.open(io.BytesIO(dados)).convert("RGB")
        caminho = RAIZ / "static" / src.lstrip("/")
        return Image.open(caminho).convert("RGB") if caminho.exists() else None
    except Exception as erro:  # sem foto não impede o post
        print(f"  aviso: não consegui abrir a foto {src}: {erro}")
        return None


def quebrar(texto: str, f: ImageFont.FreeTypeFont, largura: int, max_linhas: int) -> list[str]:
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = f"{atual} {p}".strip()
        if f.getlength(teste) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        while f.getlength(linhas[-1] + "…") > largura:
            linhas[-1] = linhas[-1].rsplit(" ", 1)[0]
        linhas[-1] += "…"
    return linhas


def etiqueta(p: dict) -> Image.Image:
    f_preco, f_de, f_off = fonte(800, 78), fonte(400, 36), fonte(800, 34)
    preco, de = brl(p["preco"]), brl(p["preco_antigo"]) if p.get("desconto") else ""
    off = f"-{p['desconto']}%" if p.get("desconto") else ""
    larg_de = f_de.getlength(de) + 22 if de else 0
    larg_off = f_off.getlength(off) + 44 if off else 0
    w = int(70 + larg_de + f_preco.getlength(preco) + (22 + larg_off if off else 0) + 40)
    h = 132
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(40, 0), (w, 0), (w, h), (40, h), (0, h / 2)], fill=LILAS)
    d.ellipse([22, h / 2 - 12, 46, h / 2 + 12], fill=(0, 0, 0, 0))
    x = 70
    if de:
        d.text((x, h / 2), de, font=f_de, fill=LILAS_TEXTO, anchor="lm")
        yb = h / 2 + 2
        d.line([(x, yb), (x + f_de.getlength(de), yb)], fill=LILAS_TEXTO, width=3)
        x += larg_de
    d.text((x, h / 2 + 2), preco, font=f_preco, fill=TINTA, anchor="lm")
    x += f_preco.getlength(preco) + 22
    if off:
        d.rounded_rectangle([x, h / 2 - 28, x + larg_off, h / 2 + 28], radius=12, fill=VERDE)
        d.text((x + larg_off / 2, h / 2), off, font=f_off, fill=PAPEL, anchor="mm")
    return img.rotate(2, resample=Image.BICUBIC, expand=True)


def gerar_card(p: dict, site: dict, destino: Path) -> None:
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)

    # marca
    logo = Image.open(MARCA / "logo-horizontal.png")
    logo.thumbnail((420, 82), Image.LANCZOS)
    img.paste(logo, (72, 92 - logo.height // 2), logo)
    d.text((W - 72, 92), p["cat"]["nome"], font=fonte(600, 32), fill=APAGADO, anchor="rm")

    # foto
    caixa = (72, 160, W - 72, 840)
    d.rounded_rectangle(caixa, radius=40, fill=PAPEL)
    foto = carregar_foto(p.get("imagem"))
    if foto:
        lw, lh = caixa[2] - caixa[0] - 80, caixa[3] - caixa[1] - 80
        foto.thumbnail((lw, lh), Image.LANCZOS)
        img.paste(foto, (caixa[0] + 40 + (lw - foto.width) // 2, caixa[1] + 40 + (lh - foto.height) // 2))
    else:
        icone = Image.open(MARCA / "icone-512.png")
        icone.thumbnail((360, 360), Image.LANCZOS)
        img.paste(icone, ((W - icone.width) // 2, (caixa[1] + caixa[3] - icone.height) // 2), icone)

    # título
    f_tit = fonte(600, 58)
    y = 880
    for linha in quebrar(p["titulo"], f_tit, W - 144, 2):
        d.text((72, y), linha, font=f_tit, fill=TINTA)
        y += 70

    # etiqueta de preço
    tag = etiqueta(p)
    img.paste(tag, (60, y + 22), tag)

    # rodapé
    rodape = f"Link na bio  ·  {endereco_curto(site)}"
    lj = p["lj"]
    if p.get("codigo"):
        artigo = "da" if lj["em"].startswith("na") else "do"
        d.text((72, H - 120), f"Busque no app {artigo} {lj['nome']}: {p['codigo']}", font=fonte(600, 34), fill=TINTA)
    else:
        d.text((72, H - 120), f"Vendido {lj['em']}", font=fonte(600, 34), fill=TINTA)
    d.text((72, H - 66), rodape, font=fonte(400, 32), fill=APAGADO)
    d.rectangle([0, H - 14, W, H], fill=LARANJA)

    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)


# ------------------------------------------------------------------ legenda

def legenda(p: dict, site: dict) -> str:
    linhas = [f"{p['titulo']} 🔥"]
    if p.get("desconto"):
        linhas.append(f"De {brl(p['preco_antigo'])} por {brl(p['preco'])} (-{p['desconto']}%)")
    else:
        linhas.append(f"Por {brl(p['preco'])}")
    if p.get("resumo"):
        linhas += ["", p["resumo"]]
    linhas.append("")
    lj = p["lj"]
    linhas.append(f"🛒 Vendido {lj['em']}")
    if p.get("codigo"):
        artigo = "da" if lj["em"].startswith("na") else "do"
        linhas.append(f"🔍 Busque no app {artigo} {lj['nome']}: {p['codigo']}")
    linhas.append(f"🔗 Link na bio: {endereco_curto(site)}")
    linhas.append("Preço visto na data do post, pode mudar a qualquer momento.")
    linhas += ["", f"#achadinhos #{lj['hashtag']} #{lj['slug']} #ofertas #achadoteca"]
    return "\n".join(linhas)


# ------------------------------------------------------------------ publicação

def token() -> str:
    """Token limpo (sem espaços, quebras de linha ou aspas coladas por engano)."""
    return os.environ.get("IG_ACCESS_TOKEN", "").strip().strip('"').strip("'").strip()


def api_base() -> str:
    # Token do login do Instagram começa com "IG"; o do login do Facebook, com "EAA".
    if token().startswith("EAA"):
        return "https://graph.facebook.com/v23.0"
    return "https://graph.instagram.com/v23.0"


def descrever_token() -> str:
    t = token()
    if t.startswith("IG"):
        tipo = "login do Instagram"
    elif t.startswith("EAA"):
        tipo = "login do Facebook"
    else:
        tipo = f"formato desconhecido (começa com '{t[:2]}')"
    return f"token de {tipo}, {len(t)} caracteres"


def id_da_conta() -> str:
    """ID da conta profissional, lido do próprio token (o IG_USER_ID é só conferência)."""
    eu = chamar("GET", "me", fields="user_id,username")
    real = str(eu.get("user_id") or eu.get("id"))
    informado = os.environ.get("IG_USER_ID", "").strip()
    if informado and informado != real:
        print(f"Aviso: o IG_USER_ID cadastrado não é o ID da conta @{eu.get('username')}; uso o ID certo automaticamente.")
    return real


def chamar(metodo: str, caminho: str, **params) -> dict:
    params["access_token"] = token()
    dados = urllib.parse.urlencode(params).encode()
    url = f"{api_base()}/{caminho}"
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{dados.decode()}")
    else:
        req = urllib.request.Request(url, data=dados, method="POST")
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as erro:
        raise SystemExit(f"Erro da API do Instagram ({erro.code}): {erro.read().decode()[:500]}")


def publicar() -> None:
    sys.path.insert(0, str(RAIZ))
    import build  # reaproveita a leitura dos produtos

    if not os.environ.get("IG_ACCESS_TOKEN"):
        print("Instagram ainda não configurado (falta IG_ACCESS_TOKEN). Nada a fazer.")
        return
    site, produtos = build.carregar()
    if site.get("prototipo"):
        print("Site em modo protótipo: não publico no Instagram.")
        return

    postados = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    # ordem: destaque primeiro, depois os mais recentes e, entre eles, os de maior desconto
    ordem = lambda p: (not p.get("destaque"), -p["data"].toordinal(), -(p.get("desconto") or 0), p["slug"])
    pendentes = [p for p in sorted(produtos, key=ordem)
                 if p["slug"] not in postados and p.get("instagram", True) is not False]
    if not pendentes:
        print("Nenhum produto novo para postar.")
        return

    p = pendentes[0]
    imagem = f"{site['url']}/ig/{p['slug']}.jpg"
    print(f"Publicando {p['slug']} com a imagem {imagem}")
    ig = id_da_conta()
    container = chamar("POST", f"{ig}/media", image_url=imagem, caption=legenda(p, site),
                       alt_text=f"{p['titulo']} por {brl(p['preco'])}")["id"]
    for _ in range(10):
        if chamar("GET", container, fields="status_code").get("status_code") == "FINISHED":
            break
        time.sleep(15)
    midia = chamar("POST", f"{ig}/media_publish", creation_id=container)["id"]

    postados[p["slug"]] = {"midia": midia, "data": time.strftime("%Y-%m-%d %H:%M")}
    REGISTRO.write_text(json.dumps(postados, ensure_ascii=False, indent=2) + "\n")
    print(f"Publicado: {midia}. Restam {len(pendentes) - 1} na fila.")


def testar() -> None:
    """Confere se o token funciona, sem publicar nada."""
    if not os.environ.get("IG_ACCESS_TOKEN"):
        raise SystemExit("Falta o segredo IG_ACCESS_TOKEN no GitHub.")
    print(f"Testando com {descrever_token()}.")
    ig = id_da_conta()
    conta = chamar("GET", ig, fields="username,media_count,account_type")
    print(f"Conta conectada: @{conta.get('username')} ({conta.get('account_type')}), {conta.get('media_count')} posts.")
    limite = chamar("GET", f"{ig}/content_publishing_limit", fields="quota_usage,config")
    dados = (limite.get("data") or [{}])[0]
    print(f"Posts pela API nas últimas 24h: {dados.get('quota_usage')} de {dados.get('config', {}).get('quota_total')}.")
    print("Tudo certo: a automação consegue publicar nessa conta.")


if __name__ == "__main__":
    if sys.argv[1:] == ["publicar"]:
        publicar()
    elif sys.argv[1:] == ["testar"]:
        testar()
    else:
        print(__doc__)
