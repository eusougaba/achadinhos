"""Gera o site estático em public/ a partir de content/, templates/ e static/.

Uso: python build.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

RAIZ = Path(__file__).parent
SAIDA = RAIZ / "public"


# ---------------------------------------------------------------- leitura

def ler_markdown(caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8")
    meta, corpo = {}, texto
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", texto, re.S)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as erro:
            raise SystemExit(f"Erro no cabeçalho de {caminho.name}: {erro}\n"
                             "Dica: textos com ':' precisam ficar entre aspas.")
        corpo = m.group(2)
    meta["slug"] = caminho.stem
    meta["corpo_html"] = markdown.markdown(corpo.strip(), extensions=["extra"])
    return meta


def ler_pasta(pasta: str) -> list[dict]:
    p = RAIZ / "content" / pasta
    return [ler_markdown(f) for f in sorted(p.glob("*.md"))] if p.exists() else []


def para_data(valor) -> dt.date | None:
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    if isinstance(valor, str) and valor:
        return dt.date.fromisoformat(valor[:10])
    return None


# ---------------------------------------------------------------- formatação

def brl(valor) -> str:
    if valor in (None, ""):
        return ""
    s = f"{float(valor):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def desconto(p: dict) -> int | None:
    atual, antigo = p.get("preco"), p.get("preco_antigo")
    if atual and antigo and float(antigo) > float(atual):
        return int((1 - float(atual) / float(antigo)) * 100)  # arredonda para baixo, como as lojas
    return None


def data_br(d) -> str:
    d = para_data(d)
    return d.strftime("%d/%m/%Y") if d else ""


# ---------------------------------------------------------------- build

def carregar() -> tuple[dict, list[dict]]:
    """Lê o site.yml e os produtos, já com desconto, categoria e data tratados."""
    site = yaml.safe_load((RAIZ / "site.yml").read_text(encoding="utf-8"))
    site["url"] = site["url"].rstrip("/")
    categorias = {c["slug"]: c for c in site["categorias"]}
    lojas = {l["slug"]: l for l in site.get("lojas", [])}

    produtos = [p for p in ler_pasta("produtos") if p.get("ativo", True) is not False]  # ativo: false = fora do site e do Instagram
    for p in produtos:
        p["data"] = para_data(p.get("data")) or dt.date.today()
        p["visto"] = para_data(p.get("atualizado")) or p["data"]
        p["desconto"] = desconto(p)
        p["cat"] = categorias.get(p.get("categoria"), {"slug": "outros", "nome": "Outros"})
        p["pros"] = p.get("pros") or []
        p["contras"] = p.get("contras") or []
        p["loja"] = p.get("loja") or "mercadolivre"
        p["lj"] = lojas.get(p["loja"], {"slug": p["loja"], "nome": p["loja"].title(), "em": f"na {p['loja'].title()}", "hashtag": "achadinhos"})
        p["sem_preco"] = bool(p.get("sem_preco", p["lj"].get("sem_preco", False)))
        p["codigo"] = p.get("codigo") or p.get("id_ml")  # código para buscar no app da loja
    produtos.sort(key=lambda p: (p["data"], p["slug"]), reverse=True)
    return site, produtos


# foco do Instagram (feed e Reels) vem de content/regras.yml
try:
    REGRAS_FOCO = yaml.safe_load((RAIZ / "content" / "regras.yml").read_text(encoding="utf-8")) or {}
except Exception:
    REGRAS_FOCO = {}


def main() -> None:
    site, produtos = carregar()
    # só mostra no menu as categorias que têm produto
    usadas = {p.get("categoria") for p in produtos}
    todas_categorias = list(site["categorias"])  # a área admin mostra todas
    site["categorias"] = [c for c in site["categorias"] if c["slug"] in usadas]
    por_slug = {p["slug"]: p for p in produtos}

    listas = ler_pasta("listas")
    for lst in listas:
        lst["data"] = para_data(lst.get("data")) or dt.date.today()
        lst["itens"] = [por_slug[s] for s in (lst.get("produtos") or []) if s in por_slug]
    listas.sort(key=lambda x: x["data"], reverse=True)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    shutil.copytree(RAIZ / "static", SAIDA)

    env = Environment(
        loader=FileSystemLoader(RAIZ / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(brl=brl, data_br=data_br, tojson_safe=lambda v: json.dumps(v, ensure_ascii=False))

    # avisos exigidos por lojas com produto ativo (ex.: Amazon)
    lojas_ativas = {p["loja"] for p in produtos}
    avisos_lojas = [l["aviso"] for l in site.get("lojas", []) if l.get("aviso") and l["slug"] in lojas_ativas]

    paginas: list[str] = []
    # muda a cada alteração do CSS, para o navegador não usar a versão antiga em cache
    import hashlib
    versao = hashlib.sha1((RAIZ / "static" / "css" / "style.css").read_bytes()).hexdigest()[:8]

    def render(modelo: str, caminho: str, **ctx) -> None:
        """caminho é a URL da página, ex.: '' ou 'produto/fone/'."""
        profundidade = caminho.count("/")
        raiz = "../" * profundidade or "./"

        def img(src: str) -> str:
            if not src:
                return raiz + "img/sem-foto.svg"
            return src if src.startswith("http") else raiz + src.lstrip("/")

        html = env.get_template(modelo).render(
            versao=versao, site=site, listas_menu=listas[:4], categorias=site["categorias"], raiz=raiz, img=img,
            canonico=f"{site['url']}/{caminho}", avisos_lojas=avisos_lojas, ano=dt.date.today().year, **ctx,
        )
        destino = SAIDA / caminho / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
        paginas.append(caminho)

    # últimos posts do feed do Instagram, para a pessoa tocar na foto e ir ao produto
    reg_ig = RAIZ / "content" / "instagram-postados.json"
    postados = json.loads(reg_ig.read_text()) if reg_ig.exists() else {}
    por_slug_ig = {p["slug"]: p for p in produtos}
    no_insta = [por_slug_ig[k] for k, v in sorted(postados.items(), key=lambda kv: kv[1]["data"], reverse=True)
                if not k.startswith(("story:", "reel:")) and k in por_slug_ig][:12]
    render("index.html", "", no_insta=no_insta, produtos=produtos, destaques=[p for p in produtos if p.get("destaque")][:3], listas=listas)
    for c in site["categorias"]:
        itens = [p for p in produtos if p.get("categoria") == c["slug"]]
        render("categoria.html", f"categoria/{c['slug']}/", categoria=c, produtos=itens)
    for p in produtos:
        relacionados = [o for o in produtos if o["cat"] is p["cat"] and o is not p][:4]
        listas_do_produto = [lst for lst in listas if p in lst["itens"]]
        render("produto.html", f"produto/{p['slug']}/", p=p, relacionados=relacionados, listas_do_produto=listas_do_produto)
    for lst in listas:
        render("lista.html", f"lista/{lst['slug']}/", lista=lst)
    render("sobre.html", "sobre/")
    render("blog.html", "blog/")
    render("busca.html", "busca/", produtos=produtos)
    contagem = {c["slug"]: sum(1 for p in produtos if p.get("categoria") == c["slug"]) for c in site["categorias"]}
    render("links.html", "links/", listas=listas, total=len(produtos), contagem=contagem, no_insta=no_insta)

    # admin: config do CMS gerada a partir do site.yml
    (SAIDA / "admin" / "config.yml").write_text(
        env.get_template("admin-config.yml").render(site={**site, "categorias": todas_categorias}), encoding="utf-8"
    )

    # imagens dos posts do Instagram (public/ig/<slug>.jpg)
    from scripts.instagram import gerar_card, gerar_story
    for p in produtos:
        card = SAIDA / "ig" / f"{p['slug']}.jpg"
        gerar_card(p, site, card)
        gerar_story(p, site, card, SAIDA / "ig" / f"story-{p['slug']}.jpg")

    # Reels (public/reels/<slug>.mp4): só os próximos da fila que foram bem na pontuação
    from scripts.reel import gerar_reel
    reg = json.loads((RAIZ / "content" / "instagram-postados.json").read_text()) if (RAIZ / "content" / "instagram-postados.json").exists() else {}
    fila = [p for p in produtos if p.get("feed", True) is not False and f"reel:{p['slug']}" not in reg]
    fila.sort(key=lambda p: (p.get("categoria") not in REGRAS_FOCO.get("instagram_foco", []), -(p.get("pontos") or 0), p["slug"]))
    for p in fila[:6]:
        gerar_reel(SAIDA / "ig" / f"story-{p['slug']}.jpg", SAIDA / "reels" / f"{p['slug']}.mp4")

    # lista de produtos para o gerador de oferta (admin/gerador.html)
    (SAIDA / "admin" / "produtos.json").write_text(json.dumps([{
        "slug": p["slug"], "titulo": p["titulo"], "categoria": p.get("categoria"), "loja": p["loja"],
        "preco": p.get("preco"), "preco_antigo": p.get("preco_antigo"), "link": p.get("link_afiliado"),
        "codigo": p.get("codigo"), "resumo": p.get("resumo"), "imagem": p.get("imagem"),
        "pagina": f"{site['url']}/produto/{p['slug']}/"} for p in produtos], ensure_ascii=False), encoding="utf-8")

    from scripts.instagram import gerar_pin_lista, gerar_pin_produto
    for lst in listas:
        gerar_pin_lista(lst, site, SAIDA / "pin" / f"{lst['slug']}.jpg")
    for p in produtos:
        gerar_pin_produto(p, site, SAIDA / "pin" / f"produto-{p['slug']}.jpg")
    regras = yaml.safe_load((RAIZ / "content" / "regras.yml").read_text(encoding="utf-8"))
    (SAIDA / "admin" / "regras.json").write_text(json.dumps(regras, ensure_ascii=False), encoding="utf-8")
    from scripts.pinterest import gerar_csv
    (SAIDA / "admin" / "pinterest-pins.csv").write_text(gerar_csv(produtos, listas, site), encoding="utf-8")

    hoje = dt.date.today().isoformat()
    urls = "\n".join(
        f"  <url><loc>{site['url']}/{c}</loc><lastmod>{hoje}</lastmod></url>" for c in paginas
    )
    (SAIDA / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n",
        encoding="utf-8",
    )
    regras = "Disallow: /\n" if site.get("prototipo") else "Disallow: /admin/\n"
    (SAIDA / "robots.txt").write_text(
        f"User-agent: *\n{regras}\nSitemap: {site['url']}/sitemap.xml\n", encoding="utf-8"
    )

    print(f"Site gerado em {SAIDA}: {len(paginas)} páginas, {len(produtos)} produtos, {len(listas)} listas, {len(produtos)} imagens de post.")


if __name__ == "__main__":
    main()
