"""Imagem e legenda dos posts do Instagram, e publicação pela API oficial.

- gerar_card(): cria a imagem 1080x1350 (JPEG) de um produto. Chamado pelo build.py,
  que salva em public/ig/<slug>.jpg (fica público junto com o site).
- legenda(): monta a legenda do post.
- python scripts/instagram.py publicar: publica o próximo produto ainda não postado.
  Precisa das variáveis IG_USER_ID e IG_ACCESS_TOKEN (segredos do GitHub).
"""
from __future__ import annotations

import io
import datetime as dt
import json
import os
import re
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
    preco, de = brl(p.get("preco") or 0), brl(p["preco_antigo"]) if p.get("desconto") else ""
    off = f"-{p['desconto']}%" if p.get("desconto") else ""
    if p.get("sem_preco"):
        preco, de, off = "Ver preço", "", ""
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


def gerar_story(p: dict, site: dict, card: Path, destino: Path) -> None:
    """Story 1080x1920: o card do feed no centro, com chamada em cima e código embaixo."""
    img = Image.new("RGB", (1080, 1920), TINTA)
    d = ImageDraw.Draw(img)
    d.text((540, 230), "Achadinho do momento", font=fonte(800, 64), fill=PAPEL, anchor="mm")
    d.text((540, 305), f"{p['cat']['nome']} · {p['lj']['nome']}", font=fonte(400, 38), fill=(201, 205, 214), anchor="mm")
    c = Image.open(card).convert("RGB").resize((920, 1150), Image.LANCZOS)
    mascara = Image.new("L", c.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, *c.size], radius=36, fill=255)
    img.paste(c, (80, 380), mascara)
    rodape = "Link na bio: " + endereco_curto(site)
    if p.get("codigo"):
        artigo = "da" if p["lj"]["em"].startswith("na") else "do"
        d.text((540, 1600), f"Busque no app {artigo} {p['lj']['nome']}:", font=fonte(400, 40), fill=(201, 205, 214), anchor="mm")
        d.text((540, 1665), p["codigo"], font=fonte(800, 64), fill=LARANJA, anchor="mm")
    d.text((540, 1760), rodape, font=fonte(600, 40), fill=PAPEL, anchor="mm")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)


def gerar_pin_lista(lista: dict, site: dict, destino: Path) -> None:
    """Pin do Pinterest (1000x1500) para uma lista: título grande e mosaico de até 4 fotos."""
    W2, H2 = 1000, 1500
    img = Image.new("RGB", (W2, H2), FUNDO)
    d = ImageDraw.Draw(img)
    logo = Image.open(MARCA / "logo-horizontal.png"); logo.thumbnail((380, 74), Image.LANCZOS)
    img.paste(logo, ((W2 - logo.width) // 2, 60), logo)
    f_tit = fonte(800, 72)
    y = 190
    for linha in quebrar(lista["titulo"], f_tit, W2 - 120, 3):
        d.text((W2 // 2, y), linha, font=f_tit, fill=TINTA, anchor="ma"); y += 86
    d.text((W2 // 2, y + 10), f"{len(lista['itens'])} achadinhos selecionados", font=fonte(400, 36), fill=APAGADO, anchor="ma")
    topo, base = y + 90, H2 - 230
    lado = (W2 - 60 * 2 - 30) // 2
    altura = min(lado, (base - topo - 30) // 2)
    for i, p in enumerate(lista["itens"][:4]):
        x = 60 + (i % 2) * (lado + 30); yy = topo + (i // 2) * (altura + 30)
        d.rounded_rectangle([x, yy, x + lado, yy + altura], radius=28, fill=PAPEL)
        foto = carregar_foto(p.get("imagem"))
        if foto:
            foto.thumbnail((lado - 50, altura - 90), Image.LANCZOS)
            img.paste(foto, (x + (lado - foto.width) // 2, yy + 20 + (altura - 90 - foto.height) // 2))
        d.text((x + lado // 2, yy + altura - 42), "Ver preço" if p.get("sem_preco") else brl(p["preco"]), font=fonte(800, 38), fill=LARANJA, anchor="mm")
    d.rectangle([0, H2 - 170, W2, H2], fill=TINTA)
    d.text((W2 // 2, H2 - 108), "Veja todos com preço e link", font=fonte(600, 40), fill=PAPEL, anchor="mm")
    d.text((W2 // 2, H2 - 55), endereco_curto(site), font=fonte(800, 40), fill=LARANJA, anchor="mm")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)


def gerar_pin_produto(p: dict, site: dict, destino: Path) -> None:
    """Pin do Pinterest (1000x1500) de um produto: foto grande, título, etiqueta de preço e o endereço do site."""
    W2, H2 = 1000, 1500
    img = Image.new("RGB", (W2, H2), FUNDO)
    d = ImageDraw.Draw(img)
    logo = Image.open(MARCA / "logo-horizontal.png"); logo.thumbnail((380, 74), Image.LANCZOS)
    img.paste(logo, ((W2 - logo.width) // 2, 56), logo)
    caixa = (60, 170, W2 - 60, 900)
    d.rounded_rectangle(caixa, radius=40, fill=PAPEL)
    foto = carregar_foto(p.get("imagem"))
    if foto:
        lw, lh = caixa[2] - caixa[0] - 70, caixa[3] - caixa[1] - 70
        foto.thumbnail((lw, lh), Image.LANCZOS)
        img.paste(foto, (caixa[0] + 35 + (lw - foto.width) // 2, caixa[1] + 35 + (lh - foto.height) // 2))
    else:
        icone = Image.open(MARCA / "icone-512.png"); icone.thumbnail((360, 360), Image.LANCZOS)
        img.paste(icone, ((W2 - icone.width) // 2, (caixa[1] + caixa[3] - icone.height) // 2), icone)
    f_tit = fonte(800, 56)
    y = 940
    for linha in quebrar(p["titulo"], f_tit, W2 - 120, 3):
        d.text((60, y), linha, font=f_tit, fill=TINTA); y += 68
    tag = etiqueta(p)
    if tag.width > W2 - 100:
        tag = tag.resize((W2 - 100, int(tag.height * (W2 - 100) / tag.width)), Image.LANCZOS)
    img.paste(tag, (50, y + 14), tag)
    d.rectangle([0, H2 - 120, W2, H2], fill=TINTA)
    d.text((W2 // 2, H2 - 60), f"Veja no site  ·  {endereco_curto(site)}", font=fonte(800, 38), fill=LARANJA, anchor="mm")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=90, optimize=True)


# ------------------------------------------------------------------ legenda

# hashtags: o que o mercado usa + loja + categoria + o produto específico
HASHTAGS_BASE = ["achadinhos", "achadinhosdodia", "promocao", "ofertas", "comprasonline", "dicadecompra", "desconto"]
SEM_VALOR = {"de", "da", "do", "das", "dos", "com", "para", "por", "em", "e", "a", "o", "um", "uma", "kit", "sem", "ou",
             "pcs", "unidades", "original", "novo", "nova", "premium", "preto", "preta", "branco", "branca", "cor", "tamanho"}


def _sem_acento(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def hashtags(p: dict, site: dict, limite: int = 14) -> list[str]:
    """Ordem: o que mais importa primeiro (produto, categoria, loja, mercado). Sem repetir, no máximo `limite`.
    Para escolher as do produto à mão, use `hashtags: [airfryer, cozinhapratica]` no cabeçalho do produto."""
    lj = p["lj"]
    cat = next((c for c in site.get("categorias", []) if c["slug"] == p.get("categoria")), {})
    do_produto = [str(h).lstrip("#") for h in (p.get("hashtags") or [])]
    if not do_produto:  # automático: palavras que descrevem o produto no título (sem marca-modelo, números ou medidas)
        palavras = [w for w in re.findall(r"[A-Za-zÀ-ÿ]+", _sem_acento(p["titulo"]).lower())
                    if len(w) > 3 and w not in SEM_VALOR]
        do_produto = palavras[:1]  # o tipo do produto vem primeiro no título (air fryer, secador, whey...)
        if len(palavras) >= 2:
            do_produto.append(palavras[0] + palavras[1])
    ordem = do_produto + list(cat.get("hashtags") or [])[:3] + [lj["hashtag"], lj["slug"], "achadoteca"] + HASHTAGS_BASE
    vistas, saida = set(), []
    for h in ordem:
        h = _sem_acento(h).lower().replace(" ", "")
        if h and h not in vistas:
            vistas.add(h); saida.append("#" + h)
    return saida[:limite]


def legenda(p: dict, site: dict) -> str:
    linhas = [f"{p['titulo']} 🔥"]
    if p.get("sem_preco"):
        linhas.append(f"Veja o preço atual {p['lj']['em']}")
    elif p.get("desconto"):
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
    linhas.insert(2, "💬 Comente QUERO que eu te mando o link no direct!")
    linhas.append("🔗 Ou no link da bio: toque na foto deste post")
    if site.get("whatsapp"):
        linhas.append("💬 Receba os achadinhos no WhatsApp: canal no link da bio")
    if not p.get("sem_preco"):
        linhas.append("Preço visto na data do post, pode mudar a qualquer momento.")
    if p["lj"].get("aviso"):
        linhas.append(p["lj"]["aviso"])
    linhas += ["", " ".join(hashtags(p, site))]
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
        corpo = erro.read().decode()[:500]
        raise ErroInstagram(f"Erro da API do Instagram ({erro.code}): {corpo}", corpo)


class ErroInstagram(SystemExit):
    def __init__(self, msg: str, corpo: str = ""):
        super().__init__(msg)
        self.corpo = corpo


def publicar(modo: str = "feed") -> None:
    """modo='feed' publica no feed (poucos por dia); modo='story' publica um story."""
    sys.path.insert(0, str(RAIZ))
    import build  # reaproveita a leitura dos produtos

    if not os.environ.get("IG_ACCESS_TOKEN"):
        print("Instagram ainda não configurado (falta IG_ACCESS_TOKEN). Nada a fazer.")
        return
    site, produtos = build.carregar()
    if site.get("prototipo"):
        print("Site em modo protótipo: não publico no Instagram.")
        return

    registro = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    prefixo = {"feed": "", "story": "story:", "reel": "reel:"}[modo]
    chave = lambda slug: f"{prefixo}{slug}"
    feitos = {k: v for k, v in registro.items() if (k.startswith(prefixo) if prefixo else ":" not in k)}
    # ordem: destaque primeiro, depois os mais recentes e, entre eles, os de maior desconto
    # feed e Reels: primeiro as categorias de foco (beleza e moda feminina); stories ficam variados
    foco = set(build.REGRAS_FOCO.get("instagram_foco", [])) if modo != "story" else set()
    ordem = lambda p: (p.get("categoria") not in foco, not p.get("destaque"), -p["data"].toordinal(), -(p.get("pontos") or p.get("desconto") or 0), p["slug"])
    pendentes = [p for p in sorted(produtos, key=ordem)
                 if chave(p["slug"]) not in registro and p.get("instagram", True) is not False
                 and (modo == "story" or p.get("feed", True) is not False)
                 and (p.get("sem_preco") or (dt.date.today() - p["visto"]).days <= 21)]  # preço velho não vai para o Instagram  # feed só para quem pontuou bem
    if modo != "story" and foco and any(p.get("categoria") in foco for p in pendentes):
        pendentes = [p for p in pendentes if p.get("categoria") in foco]   # só sai produto de foco enquanto houver
    if not pendentes:
        print(f"Nenhum produto novo para {modo}.")
        return

    # intervalo mínimo entre publicações do mesmo tipo
    minimo = {"story": 50, "feed": 150, "reel": 360}[modo]
    if feitos:
        ultimo = max(time.mktime(time.strptime(v["data"], "%Y-%m-%d %H:%M")) for v in feitos.values())
        if time.time() - ultimo < minimo * 60:
            print(f"Último {modo} foi há menos de {minimo} minutos; o próximo sai na próxima rodada.")
            return

    p = pendentes[0]
    ig = id_da_conta()
    if modo == "story":
        imagem = f"{site['url']}/ig/story-{p['slug']}.jpg"
        print(f"Publicando story de {p['slug']} com a imagem {imagem}")
        container = chamar("POST", f"{ig}/media", image_url=imagem, media_type="STORIES")["id"]
    elif modo == "reel":
        imagem = f"{site['url']}/reels/{p['slug']}.mp4"
        print(f"Publicando reel de {p['slug']} com o vídeo {imagem}")
        container = chamar("POST", f"{ig}/media", video_url=imagem, media_type="REELS", caption=legenda(p, site),
                           share_to_feed="true")["id"]
    else:
        imagem = f"{site['url']}/ig/{p['slug']}.jpg"
        print(f"Publicando no feed {p['slug']} com a imagem {imagem}")
        container = chamar("POST", f"{ig}/media", image_url=imagem, caption=legenda(p, site),
                           alt_text=p["titulo"] if p.get("sem_preco") else f"{p['titulo']} por {brl(p['preco'])}")["id"]
    # espera o Instagram processar a imagem (até ~5 min) e tenta publicar com novas tentativas
    for _ in range(60 if modo == "reel" else 30):
        time.sleep(10)
        estado = chamar("GET", container, fields="status_code").get("status_code")
        if estado == "FINISHED":
            break
        if estado == "ERROR":
            raise SystemExit(f"O Instagram recusou a imagem {imagem}.")
    midia = None
    for tentativa in range(6):
        try:
            midia = chamar("POST", f"{ig}/media_publish", creation_id=container)["id"]
            break
        except ErroInstagram as erro:
            if "9007" in erro.corpo and tentativa < 5:
                print("Imagem ainda processando; tentando de novo em 20 s.")
                time.sleep(20)
                continue
            raise

    registro[chave(p["slug"])] = {"midia": midia, "data": time.strftime("%Y-%m-%d %H:%M")}
    REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n")
    print(f"Publicado: {midia}. Restam {len(pendentes) - 1} na fila.")


def automatico() -> None:
    """Story a cada rodada (respeitando o intervalo) e até 3 posts no feed por dia, das 9h às 20h."""
    try:
        publicar("story")
    except SystemExit as erro:
        print(f"Story não publicado: {erro}")
    agora = time.gmtime(time.time() - 3 * 3600)  # horário de Brasília
    if not (9 <= agora.tm_hour <= 20):
        print("Fora do horário do feed (9h às 20h).")
        return
    registro = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    hoje = time.strftime("%Y-%m-%d", agora)
    feed_hoje = 0
    for k, v in registro.items():
        if k.startswith(("story:", "reel:")):
            continue
        quando = time.gmtime(time.mktime(time.strptime(v["data"], "%Y-%m-%d %H:%M")) - 3 * 3600)
        if time.strftime("%Y-%m-%d", quando) == hoje:
            feed_hoje += 1
    if feed_hoje >= 3:
        print("Já foram 3 posts no feed hoje.")
        return
    publicar("feed")
    # um Reel por dia, no fim da tarde
    if agora.tm_hour >= 17 and not any(k.startswith("reel:") and v["data"][:10] == hoje for k, v in registro.items()):
        try:
            publicar("reel")
        except (SystemExit, ErroInstagram) as erro:
            print(f"Reel não publicado: {erro}")


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
    if sys.argv[1:] in (["publicar"], ["feed"]):
        publicar("feed")
    elif sys.argv[1:] == ["story"]:
        publicar("story")
    elif sys.argv[1:] == ["reel"]:
        publicar("reel")
    elif sys.argv[1:] == ["auto"]:
        automatico()
    elif sys.argv[1:] == ["testar"]:
        testar()
    else:
        print(__doc__)
