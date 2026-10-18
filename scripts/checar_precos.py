"""Checa preços direto na página pública do Mercado Livre (sem navegador, sem tokens).

Uso: python3 scripts/checar_precos.py [N]   -> confere os N produtos com preço mais antigo (padrão 20)
Segue o link meli.la, lê o preço do JSON-LD/meta da página e atualiza o .md se mudou.
Se a página não responder ou não trouxer preço, o produto é pulado (nunca apaga nada).
Variação acima de 60% é ignorada (pode ser outro anúncio). Resumo no fim, e relatório em content/analise/precos.log.
"""
import json, re, sys, time, datetime, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atualizar_precos import PASTA, campo, trocar  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "ignore")


def ler_preco(html):
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        for x in (d if isinstance(d, list) else [d]):
            o = x.get("offers") if isinstance(x, dict) else None
            for of in (o if isinstance(o, list) else [o]):
                if isinstance(of, dict) and of.get("price"):
                    return float(of["price"]), of.get("availability", "")
    m = re.search(r'itemprop="price"\s+content="([\d.]+)"', html)
    return (float(m.group(1)), "") if m else (None, "")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    fs = []
    for f in PASTA.glob("*.md"):
        t = f.read_text(encoding="utf-8")
        if campo(t, "loja") == "mercadolivre" and campo(t, "link_afiliado"):
            fs.append((campo(t, "atualizado") or campo(t, "data") or "", f))
    fs.sort()
    hoje = datetime.date.today().isoformat()
    ok = mudou = falhou = 0
    log = []
    for _, f in fs[:n]:
        t = f.read_text(encoding="utf-8")
        try:
            url, html = baixar(campo(t, "link_afiliado"))
            novo, disp = ler_preco(html)
        except Exception as e:
            novo, disp, url = None, "", str(e)[:60]
        if not novo:
            falhou += 1; log.append(f"sem preço: {f.stem} ({url[:60]})"); time.sleep(2); continue
        ok += 1
        antigo = float(campo(t, "preco"))
        if "OutOfStock" in disp:
            log.append(f"ESGOTADO: {f.stem}")
        if abs(novo - antigo) / antigo > 0.6:
            log.append(f"ignorado (variação grande) {f.stem}: {antigo:g} -> {novo:g}")
        elif novo != antigo:
            t = trocar(t, "preco", f"{novo:g}")
            pa = campo(t, "preco_antigo")
            if pa and float(pa) <= novo:
                t = re.sub(r"^preco_antigo:.*\n", "", t, count=1, flags=re.M)
            log.append(f"{f.stem}: {antigo:g} -> {novo:g}")
            mudou += 1
        t = trocar(t, "atualizado", f"'{hoje}'")
        f.write_text(t, encoding="utf-8")
        time.sleep(2)
    resumo = f"{hoje}: lidos {ok}, alterados {mudou}, sem preço {falhou}"
    print("\n".join(log)); print(resumo)
    arq = PASTA.parent / "analise" / "precos.log"
    arq.parent.mkdir(exist_ok=True)
    antes = arq.read_text(encoding="utf-8") if arq.exists() else ""
    arq.write_text("\n".join([resumo] + log[:30]) + "\n\n" + antes[:6000], encoding="utf-8")
    if ok == 0 and falhou:
        sys.exit(0)


if __name__ == "__main__":
    main()
