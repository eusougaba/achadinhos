"""Análise semanal do Instagram: lê o alcance de cada post registrado e gera um relatório curto.

Saída: content/analise/AAAA-Wss.md  (e resumo no terminal). Não gasta tokens: é só Python.
Se o token não tiver permissão de insights, o relatório sai só com o que a API deixar ler.
"""
from __future__ import annotations
import collections, datetime, json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import instagram as ig  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FEED = ["reach", "saved", "shares", "likes", "comments"]
STORY = ["reach", "replies", "shares"]


def categoria(slug: str) -> str:
    f = RAIZ / "content" / "produtos" / f"{slug}.md"
    if f.exists():
        m = re.search(r"^categoria: *(.+)$", f.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return "?"


def metricas(midia: str, nomes: list[str]) -> dict:
    try:
        r = ig.chamar("GET", f"{midia}/insights", metric=",".join(nomes))
        return {d["name"]: (d["values"][0]["value"] if d.get("values") else d.get("total_value", {}).get("value", 0)) for d in r.get("data", [])}
    except Exception as e:  # permissão, mídia antiga, story expirado
        return {"_erro": str(e)[:80]}


def main() -> None:
    if not os.environ.get("IG_ACCESS_TOKEN"):
        print("Sem IG_ACCESS_TOKEN; nada a analisar."); return
    postados = json.loads((RAIZ / "content" / "instagram-postados.json").read_text())
    linhas, por_cat, erros = [], collections.defaultdict(lambda: [0, 0, 0]), 0
    for chave, v in postados.items():
        story = chave.startswith("story:")
        slug = chave.split(":", 1)[-1]
        m = metricas(v["midia"], STORY if story else FEED)
        if "_erro" in m:
            erros += 1; continue
        alcance = m.get("reach", 0)
        interacao = sum(m.get(k, 0) for k in ("saved", "shares", "comments", "replies"))
        c = categoria(slug)
        por_cat[(c, "story" if story else "feed")][0] += alcance
        por_cat[(c, "story" if story else "feed")][1] += interacao
        por_cat[(c, "story" if story else "feed")][2] += 1
        linhas.append((alcance, interacao, "story" if story else "feed", slug, c))
    try:
        conta = ig.chamar("GET", "me", fields="username,followers_count,media_count")
    except Exception:
        conta = {}
    hoje = datetime.date.today()
    out = [f"# Análise {hoje.isocalendar()[0]}-W{hoje.isocalendar()[1]:02d}", "",
           f"Conta @{conta.get('username','?')}: {conta.get('followers_count','?')} seguidores, {conta.get('media_count','?')} posts.",
           f"Posts lidos: {len(linhas)} (sem permissão/expirados: {erros}).", ""]
    if linhas:
        linhas.sort(reverse=True)
        out += ["## Melhores (alcance / interações)"] + [f"- {t} {s} ({c}): {a} / {i}" for a, i, t, s, c in linhas[:5]]
        out += ["", "## Piores"] + [f"- {t} {s} ({c}): {a} / {i}" for a, i, t, s, c in linhas[-3:]]
        out += ["", "## Por categoria (alcance médio, interações médias, posts)"]
        for (c, t), (a, i, n) in sorted(por_cat.items(), key=lambda x: -x[1][0] / x[1][2]):
            out.append(f"- {c} {t}: {a // n}, {i / n:.1f}, {n}")
        melhor = max(por_cat.items(), key=lambda x: x[1][0] / x[1][2])[0][0]
        out += ["", f"Sugestão: priorizar a categoria **{melhor}** no garimpo da próxima semana."]
    else:
        out.append("Nenhum dado de insights disponível ainda. Confira se o token tem a permissão instagram_business_manage_insights.")
    pasta = RAIZ / "content" / "analise"
    pasta.mkdir(exist_ok=True)
    arq = pasta / f"{hoje.isocalendar()[0]}-W{hoje.isocalendar()[1]:02d}.md"
    arq.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
