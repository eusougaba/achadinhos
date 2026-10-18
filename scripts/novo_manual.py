"""Cadastro manual de produto (Shopee, Amazon ou outra loja).

Uso (JSON no stdin, uma lista de objetos):
  [{"t": "título", "cat": "beleza", "loja": "shopee", "link": "https://s.shopee.com.br/...",
    "img": "https://.../foto.jpg", "p": 60.0, "de": 80.0, "nota": 4.9, "vend": 100000}]

Campos: t, cat, loja, link, img obrigatórios. p (preço) é obrigatório, exceto em lojas que
não mostram preço (Amazon). de, nota e vend são opcionais. Não afirmamos nada que não foi informado.
Rode com --dry para simular.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys

import yaml

from novo_produto import PASTA, REGRAS, brl, contagem_por_categoria, mil, slug

RAIZ = PASTA.parent.parent
SITE = yaml.safe_load((RAIZ / "site.yml").read_text(encoding="utf-8"))
LOJAS = {l["slug"]: l for l in SITE["lojas"]}


def validar(c: dict) -> str | None:
    for k in ("t", "cat", "loja", "link", "img"):
        if not c.get(k):
            return f"falta o campo {k}"
    if c["loja"] not in LOJAS:
        return f"loja desconhecida: {c['loja']}"
    if c["cat"] not in REGRAS["textos"]:
        return f"categoria desconhecida: {c['cat']}"
    if not LOJAS[c["loja"]].get("sem_preco") and not c.get("p"):
        return "falta o preço (p)"
    if not str(c["link"]).startswith("https://"):
        return "o link precisa começar com https://"
    return None


def escrever(c: dict) -> str:
    loja = LOJAS[c["loja"]]
    sem_preco = bool(loja.get("sem_preco"))
    tx = REGRAS["textos"][c["cat"]]
    pros = []
    if c.get("nota"):
        pros.append(f"Nota {c['nota']}" + (f" e mais de {mil(int(c['vend']))} unidades vendidas" if c.get("vend") else ""))
    elif c.get("vend"):
        pros.append(f"Mais de {mil(int(c['vend']))} unidades vendidas")
    if c.get("de") and c.get("p") and c["de"] > c["p"] and not sem_preco:
        pros.append(f"{round((1 - c['p'] / c['de']) * 100)}% abaixo do preço de referência do anúncio")
    contras = list(tx["contras"])[:3]
    contras.append("Confira o vendedor, o prazo e a política de troca no anúncio")
    titulo = " ".join(c["t"].split())
    curto = titulo if len(titulo) <= 62 else titulo[:61].rsplit(" ", 1)[0] + "…"
    resumo = f"{curto}, vendido {loja['em']}."
    if c.get("p") and not sem_preco:
        resumo = f"{curto} por {brl(c['p'])}, vendido {loja['em']}."
    fm = {
        "titulo": titulo, "categoria": c["cat"], "loja": c["loja"], "imagem": c["img"],
        "link_afiliado": c["link"], "data": dt.date.today().isoformat(), "resumo": resumo,
        "pros": pros, "contras": contras[:3], "feed": True,
    }
    if sem_preco:
        fm["sem_preco"] = True
    else:
        fm["preco"] = c["p"]
        if c.get("de") and c["de"] > c["p"]:
            fm["preco_antigo"] = c["de"]
    corpo = f"{curto} está entre as opções que escolhemos {loja['em']}. Confira no anúncio as medidas, o que acompanha e as avaliações antes de comprar."
    nome = slug(c["t"])
    (PASTA / f"{nome}.md").write_text(
        "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n" + corpo + "\n", encoding="utf-8")
    return nome


def main() -> None:
    dry = "--dry" in sys.argv
    candidatos = json.load(sys.stdin)
    existentes = {f.stem for f in PASTA.glob("*.md")}
    links = set(re.findall(r"link_afiliado:\s*(\S+)", "".join(f.read_text(encoding="utf-8") for f in PASTA.glob("*.md"))))
    ok = 0
    for c in candidatos:
        motivo = validar(c)
        if not motivo and c["link"] in links:
            motivo = "link já cadastrado"
        if not motivo and slug(c["t"]) in existentes:
            motivo = "slug repetido"
        if motivo:
            print(f"- {c.get('t', '?')[:50]:50s} RECUSADO: {motivo}")
            continue
        if not dry:
            existentes.add(escrever(c))
        ok += 1
        print(f"+ {c['t'][:50]:50s} {c['loja']} {c['cat']}")
    print(f"{ok} produto(s) gravado(s)" + (" (simulação)" if dry else ""))


if __name__ == "__main__":
    main()
