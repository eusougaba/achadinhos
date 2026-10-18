"""Pontua candidatos e cadastra os aprovados em content/produtos/.

Entrada (stdin, JSON): lista de objetos com
  t (título), p (preço), de (preço antigo), com (% comissão), nota, vend (vendas, número), link, id, img, cat
Uso:
  python scripts/novo_produto.py < candidatos.json          # grava os arquivos
  python scripts/novo_produto.py --dry < candidatos.json    # só mostra a pontuação
Saída: uma linha curta por candidato (não imprime nada além disso, para gastar poucos tokens).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
REGRAS = yaml.safe_load((RAIZ / "content" / "regras.yml").read_text(encoding="utf-8"))
PASTA = RAIZ / "content" / "produtos"


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slug(titulo: str) -> str:
    palavras = re.findall(r"[a-z0-9]+", sem_acento(titulo).lower())
    ignora = {"de", "da", "do", "para", "com", "e", "em", "a", "o", "kit"}
    ok = [w for w in palavras if w not in ignora] or palavras
    s = "-".join(ok[:9])
    return s[:70].rstrip("-")


def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mil(n: int) -> str:
    return f"{n // 1000} mil" if n >= 1000 else str(n)


def contagem_por_categoria() -> dict[str, int]:
    cont: dict[str, int] = {}
    for f in PASTA.glob("*.md"):
        m = re.search(r"^categoria:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
        if m:
            cont[m.group(1)] = cont.get(m.group(1), 0) + 1
    return cont


def marca_de(titulo: str) -> str | None:
    t = sem_acento(titulo).lower()
    for m in REGRAS["marcas"]:
        if sem_acento(m).lower() in t:
            return m.title()
    return None


def pontuar(c: dict, cont: dict[str, int]) -> tuple[float, str | None]:
    pe, mn = REGRAS["pesos"], REGRAS["minimos"]
    desc = round((1 - c["p"] / c["de"]) * 100) if c.get("de") and c["de"] > c["p"] else 0
    pts = pe["nota"] * max(0.0, min(1.0, (float(c["nota"]) - mn["nota"]) / 0.5))
    pts += pe["vendas"] * max(0.0, min(1.0, math.log10(max(c["vend"], 1)) / 5))
    if desc <= REGRAS["desconto_confiavel_max"]:
        pts += pe["desconto"] * min(desc, 40) / 40
    pts += pe["comissao"] * min(c.get("com") or 0, 16) / 16
    marca = marca_de(c["t"])
    if marca:
        pts += pe["marca"]
    n = cont.get(c["cat"], 0)
    pts += pe["categoria"] * (1.0 if n < 10 else 0.6 if n < 20 else 0.0)
    return round(pts), marca


def aprovado(c: dict) -> str | None:
    mn = REGRAS["minimos"]
    desc = round((1 - c["p"] / c["de"]) * 100) if c.get("de") and c["de"] > c["p"] else 0
    if float(c["nota"]) < mn["nota"]: return "nota baixa"
    if c["vend"] < mn["vendas"]: return "poucas vendas"
    if desc < mn["desconto"]: return "desconto pequeno"
    if not mn["preco_min"] <= c["p"] <= mn["preco_max"]: return "fora da faixa de preço"
    if (c.get("com") or 0) < mn["comissao"]: return "comissão baixa"
    return None


def curto(t: str, n: int = 62) -> str:
    t = " ".join(t.split())
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0]


def escrever(c: dict, pontos: int, marca: str | None, feed: bool) -> str:
    tx = REGRAS["textos"][c["cat"]]
    desc = round((1 - c["p"] / c["de"]) * 100) if c.get("de") and c["de"] > c["p"] else 0
    pros = [f"Nota {c['nota']} e mais de {mil(c['vend'])} unidades vendidas"]
    if desc >= 10:
        pros.append(f"{desc}% abaixo do preço de referência do anúncio")
    if marca:
        pros.append(f"Marca conhecida: {marca}")
    contras = list(tx["contras"])
    if desc >= 40:
        contras.insert(0, "O desconto é sobre o preço de referência do anúncio; compare com outras lojas")
    fm = {
        "titulo": " ".join(c["t"].split()), "categoria": c["cat"], "loja": "mercadolivre",
        "imagem": f"https://http2.mlstatic.com/D_NQ_NP_{c['img']}-O.webp",
        "preco": c["p"], "preco_antigo": c.get("de"), "link_afiliado": c["link"], "codigo": c["id"],
        "data": dt.date.today().isoformat(),
        "resumo": f"{curto(c['t'])} por {brl(c['p'])}, com nota {c['nota']} e mais de {mil(c['vend'])} vendidos.",
        "pros": pros, "contras": contras[:3], "pontos": pontos, "feed": feed,
    }
    if not fm["preco_antigo"]:
        del fm["preco_antigo"]
    corpo = tx["corpo"].format(curto=curto(c["t"], 48))
    nome = slug(c["t"])
    (PASTA / f"{nome}.md").write_text(
        "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n" + corpo + "\n", encoding="utf-8")
    return nome


def main() -> None:
    dry = "--dry" in sys.argv
    candidatos = json.load(sys.stdin)
    cont = contagem_por_categoria()
    existentes = {f.stem for f in PASTA.glob("*.md")}
    codigos = set(re.findall(r"codigo:\s*(\S+)", "".join(f.read_text(encoding="utf-8") for f in PASTA.glob("*.md"))))
    gravados = 0
    for c in candidatos:
        motivo = aprovado(c)
        if c.get("id") in codigos:
            motivo = "já cadastrado"
        elif slug(c["t"]) in existentes:
            motivo = "slug repetido"
        pontos, marca = pontuar(c, cont)
        feed = pontos >= REGRAS["feed_min_pontos"]
        if motivo:
            print(f"- {pontos:3d} {c['t'][:48]:48s} RECUSADO: {motivo}")
            continue
        if not dry:
            nome = escrever(c, pontos, marca, feed)
            existentes.add(nome)
            cont[c["cat"]] = cont.get(c["cat"], 0) + 1
            gravados += 1
        print(f"+ {pontos:3d} {c['t'][:48]:48s} {'FEED' if feed else 'só stories'} {c['cat']}")
    print(f"{gravados} produto(s) gravado(s)" + (" (simulação)" if dry else ""))


if __name__ == "__main__":
    main()
