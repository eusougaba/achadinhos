"""Planilha (CSV) para o Pinterest criar pins em lote, já com data de publicação.

Uso: o build.py chama gerar_csv() e salva em public/admin/pinterest-pins.csv.
No Pinterest: Criar > Criar pins em massa (upload em massa) > enviar esse arquivo.
A imagem de cada pin fica pública no site (public/pin/...), e o link leva à página do produto ou da lista.
"""
from __future__ import annotations

import csv
import datetime as dt
import io

PINS_POR_DIA = 4
HORARIOS_BRT = [9, 12, 17, 20]          # horários de publicação, no fuso de São Paulo
QUADRO_LISTAS = "Listas de achadinhos"
UTM = "?utm_source=pinterest&utm_medium=pin&utm_campaign=achados"   # o Google Analytics mostra a origem da visita
CABECALHO = ["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"]


def _corta(texto: str, limite: int) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[: limite - 1].rsplit(" ", 1)[0] + "…"


def _brl(v) -> str:
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_csv(produtos: list[dict], listas: list[dict], site: dict, comeco: dt.date | None = None) -> str:
    base = site["url"]
    comeco = comeco or (dt.date.today() + dt.timedelta(days=1))
    itens = []
    # alterna produto e lista para o perfil ficar variado
    lst = [("lista", l) for l in listas]
    prod = [("produto", p) for p in produtos]
    while lst or prod:
        if prod: itens.append(prod.pop(0))
        if prod: itens.append(prod.pop(0))
        if lst: itens.append(lst.pop(0))
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator="\n")
    w.writerow(CABECALHO)
    for i, (tipo, x) in enumerate(itens[:200]):
        dia = comeco + dt.timedelta(days=i // PINS_POR_DIA)
        hora_utc = HORARIOS_BRT[i % PINS_POR_DIA] + 3          # São Paulo = UTC-3
        quando = dt.datetime.combine(dia, dt.time(hora_utc % 24)) + dt.timedelta(days=hora_utc // 24)
        if tipo == "produto":
            titulo = _corta(f"{x['titulo']}: vale a pena?", 100)
            preco = f"Por {_brl(x['preco'])}" + (f" (de {_brl(x['preco_antigo'])})" if x.get("desconto") else "")
            desc = _corta(f"{x.get('resumo') or x['titulo']} {preco}. Veja os detalhes, prós e contras no site. "
                          f"Preço visto hoje, pode mudar.", 480)
            midia = f"{base}/pin/produto-{x['slug']}.jpg"
            link = f"{base}/produto/{x['slug']}/{UTM}"
            quadro = x["cat"]["nome"]
            chaves = [x["cat"]["nome"], x["lj"]["nome"], "achadinhos", "oferta"] + x["titulo"].split()[:2]
        else:
            titulo = _corta(x["titulo"], 100)
            desc = _corta(f"{x.get('descricao') or x['titulo']} Veja a lista completa com preços e prós e contras de cada item.", 480)
            midia = f"{base}/pin/{x['slug']}.jpg"
            link = f"{base}/lista/{x['slug']}/{UTM}"
            quadro = QUADRO_LISTAS
            chaves = ["achadinhos", "lista de compras", "ofertas", x["titulo"]]
        w.writerow([titulo, midia, quadro, "", desc, link, quando.strftime("%Y-%m-%dT%H:%M:%S"), ",".join(dict.fromkeys(chaves))])
    return saida.getvalue()
