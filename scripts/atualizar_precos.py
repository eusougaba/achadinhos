"""Atualiza preços dos produtos do Mercado Livre.

  python3 scripts/atualizar_precos.py lista [N]   -> JSON [{s,t}] dos N mais antigos (para AC.precos)
  python3 scripts/atualizar_precos.py < saida.json -> aplica os preços lidos (AC.esperar())
Produto não achado no painel é retirado (ativo: false); com variação > 60% é retirado (pode ser outro anúncio).
"""
import json, re, sys, datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "content" / "produtos"


def campo(txt, nome):
    m = re.search(rf"^{nome}: *(.*)$", txt, re.M)
    return m.group(1).strip().strip("'\"") if m else None


def trocar(txt, nome, valor):
    linha = f"{nome}: {valor}"
    if re.search(rf"^{nome}:", txt, re.M):
        return re.sub(rf"^{nome}:.*$", linha, txt, count=1, flags=re.M)
    return txt.replace("\ndata:", f"\n{linha}\ndata:", 1)


def lista(n):
    itens = []
    for f in PASTA.glob("*.md"):
        t = f.read_text(encoding="utf-8")
        if campo(t, "loja") == "mercadolivre" and campo(t, "ativo") != "false":
            itens.append((campo(t, "atualizado") or campo(t, "data") or "", f.stem, campo(t, "titulo")))
    itens.sort()
    print(json.dumps([{"s": s, "t": t} for _, s, t in itens[:n]], ensure_ascii=False))


def aplicar():
    hoje = datetime.date.today().isoformat()
    mudou = 0
    for r in json.load(sys.stdin):
        f = PASTA / f"{r['s']}.md"
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        if "erro" in r:
            # não está mais no painel de afiliados: sai do site e do Instagram (arquivo fica, ativo: false)
            f.write_text(trocar(t, "ativo", "false"), encoding="utf-8")
            print("  RETIRADO (não achado no painel):", r["s"]); continue
        antigo = float(campo(t, "preco"))
        novo = float(r["p"])
        if abs(novo - antigo) / antigo > 0.6:
            # preço instável ou outro anúncio: não é produto sólido, sai do site e do Instagram
            f.write_text(trocar(t, "ativo", "false"), encoding="utf-8")
            print(f"  RETIRADO (variação grande) {r['s']}: {antigo:g} -> {novo:g}"); continue
        t = trocar(t, "atualizado", f"'{hoje}'")
        if novo != antigo:
            t = trocar(t, "preco", f"{novo:g}")
            if r.get("de"):
                t = trocar(t, "preco_antigo", f"{float(r['de']):g}")
            elif campo(t, "preco_antigo"):
                t = re.sub(r"^preco_antigo:.*\n", "", t, count=1, flags=re.M)
            print(f"  {r['s'][:40]}: {antigo:g} -> {novo:g}")
            mudou += 1
        f.write_text(t, encoding="utf-8")
    print(f"{mudou} preço(s) alterado(s)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "lista":
        lista(int(sys.argv[2]) if len(sys.argv) > 2 else 15)
    else:
        aplicar()
