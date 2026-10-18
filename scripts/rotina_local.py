"""Rotina diária do Achadoteca, rodando no computador do Marcos (sem gastar tokens).

  1. conecta ao Edge já logado no painel de afiliados do Mercado Livre (porta 9222);
  2. confere o preço de todos os produtos; atualiza e retira os que sumiram ou variaram mais de 60%;
  3. se o site ficou abaixo da meta, garimpa nas categorias com menos itens e cadastra os melhores;
  4. gera o site, faz commit e envia ao GitHub (o resto é automático lá);
  5. grava um resumo em content/analise/rotina.log.

Uso:  python scripts/rotina_local.py [--meta 80] [--max-novos 8] [--so-precos] [--sem-push] [--porta 9222]
Nunca digita senha: se o painel pedir login ou verificação, a rotina para e avisa.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import os

RAIZ = Path(__file__).resolve().parent.parent
HUB = "https://www.mercadolivre.com.br/afiliados/hub"
PASTA = RAIZ / "content" / "produtos"
ESTADO = RAIZ / "content" / "analise" / "garimpo-estado.json"
LOG = RAIZ / "content" / "analise" / "rotina.log"
PY = sys.executable
resumo: list[str] = []


ENV_UTF8 = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}   # Windows usa cp1252 por padrão
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def dizer(msg: str) -> None:
    print(msg, flush=True)
    resumo.append(msg)


def sh(*cmd: str, entrada: str | None = None, ok: bool = True) -> str:
    r = subprocess.run(cmd, cwd=RAIZ, input=entrada, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV_UTF8)
    if ok and r.returncode != 0:
        raise SystemExit(f"Falhou: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return (r.stdout or "") + (r.stderr or "")


# ---------------------------------------------------------------- painel

class Painel:
    def __init__(self, porta: int):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self.browser = self._pw.chromium.connect_over_cdp(f"http://localhost:{porta}")
        except Exception as e:
            raise SystemExit(f"Não consegui conectar ao Edge na porta {porta}. Abra o Edge com iniciar_edge.bat e tente de novo.\n{e}")
        ctx = self.browser.contexts[0]
        self.page = next((p for p in ctx.pages if "/afiliados/hub" in p.url), None) or ctx.new_page()
        self.page.goto(HUB, wait_until="domcontentloaded")
        self.page.wait_for_timeout(4000)
        self.checar_acesso()
        self.page.evaluate("(src) => (0, eval)(src)", (RAIZ / "static" / "admin" / "painel_ml.js").read_text(encoding="utf-8"))
        self.page.evaluate("window.AC.regras = null")

    def checar_acesso(self) -> None:
        texto = self.page.inner_text("body")[:3000].lower()
        if "/afiliados/hub" not in self.page.url or any(x in texto for x in ("verificação", "verificacao", "não sou um robô", "confirme que", "entrar na sua conta", "digite seu e-mail")):
            raise SystemExit("O Mercado Livre pediu login ou verificação. Faça isso no Edge (não vou contornar) e rode de novo.")
        if self.page.query_selector('input[placeholder="Busque produtos"]') is None:
            raise SystemExit("Não achei a busca do painel de afiliados. Abra a página do hub no Edge e rode de novo.")

    def rodar(self, chamada: str, espera_max: int = 900) -> str:
        """Dispara uma função AC.* e espera terminar; devolve AC.saida."""
        self.page.evaluate(chamada)
        self.page.wait_for_function("() => !window.AC.ocupado", timeout=espera_max * 1000, polling=2000)
        return self.page.evaluate("window.AC.saida") or ""

    def fechar(self) -> None:
        try:
            self._pw.stop()
        except Exception:
            pass


# ---------------------------------------------------------------- preços

def conferir_precos(painel: Painel) -> None:
    lista = json.loads(sh(PY, "scripts/atualizar_precos.py", "lista", "500"))
    dizer(f"Preços: conferindo {len(lista)} produtos.")
    resultados: list[dict] = []
    for i in range(0, len(lista), 20):
        lote = lista[i:i + 20]
        saida = painel.rodar(f"AC.precos({json.dumps(lote, ensure_ascii=False)})")
        if saida.startswith("ERRO"):
            raise SystemExit(f"Erro no painel: {saida}")
        resultados += json.loads(saida)
        painel.checar_acesso()
        if i + 20 < len(lista):
            time.sleep(random.uniform(40, 90))  # pausa entre lotes
    achados = sum(1 for r in resultados if "erro" not in r)
    if achados == 0:
        raise SystemExit("Nenhum preço foi lido: o painel mudou ou a busca falhou. Nada foi alterado.")
    if achados < len(resultados) * 0.5:
        raise SystemExit(f"Só {achados} de {len(resultados)} achados: parece falha do painel, não vou retirar nada.")
    saida = sh(PY, "scripts/atualizar_precos.py", entrada=json.dumps(resultados))
    retirados = [l.strip() for l in saida.splitlines() if "RETIRADO" in l]
    mudou = re.search(r"(\d+) preço", saida)
    dizer(f"Preços: {achados} lidos, {mudou.group(1) if mudou else 0} alterados, {len(retirados)} retirados.")
    for l in retirados:
        dizer("  " + l)


# ---------------------------------------------------------------- garimpo

def ativos_por_categoria() -> dict[str, int]:
    sys.path.insert(0, str(RAIZ / "scripts"))
    import novo_produto as n
    return n.contagem_por_categoria()


def garimpar(painel: Painel, meta: int, max_novos: int) -> None:
    sys.path.insert(0, str(RAIZ / "scripts"))
    import novo_produto as n
    cont = n.contagem_por_categoria()
    total = sum(cont.values())
    falta = meta - total
    dizer(f"Garimpo: {total} ativos, meta {meta}.")
    if falta <= 0:
        return
    quero = min(falta, max_novos)
    regras = n.REGRAS
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    cats = sorted(regras["buscas"], key=lambda c: cont.get(c, 0) / regras.get("pesos", {}).get(c, 1))[:4]   # as categorias mais vazias
    termos = []
    for c in cats:
        lst = regras["buscas"][c]
        i = estado.get(c, 0)
        for k in range(3 if c in ("beleza", "moda") else 2):
            termos.append([lst[(i + k) % len(lst)], c])
        estado[c] = (i + 2) % len(lst)
    painel.rodar(f"AC.go({json.dumps(termos, ensure_ascii=False)}, 4)")
    cand = painel.page.evaluate("window.AC.res") or []
    existentes = {f.stem for f in PASTA.glob("*.md")}
    boas = []
    for c in cand:
        c["vend"] = int(c["vend"])
        if n.aprovado(c) or n.slug(c["t"]) in existentes:
            continue
        desc = round((1 - c["p"] / c["de"]) * 100) if c.get("de") and c["de"] > c["p"] else 0
        if desc > regras["desconto_confiavel_max"]:
            continue   # desconto exagerado: preço de referência suspeito
        pts, _ = n.pontuar(c, cont)
        c["_pts"] = pts
        boas.append(c)
    boas.sort(key=lambda c: -c["_pts"])
    escolhidos, por_cat = [], {}
    for c in boas:
        if por_cat.get(c["cat"], 0) >= 3:
            continue
        por_cat[c["cat"]] = por_cat.get(c["cat"], 0) + 1
        escolhidos.append(c)
        if len(escolhidos) >= quero:
            break
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(estado))
    if not escolhidos:
        dizer("Garimpo: nenhum candidato passou nas regras desta vez.")
        return
    indices = [i for i, c in enumerate(cand) if any(c is e or (c["t"] == e["t"]) for e in escolhidos)]
    saida = painel.rodar(f"AC.go2({json.dumps(indices)})", 1200)
    if saida.startswith("ERRO"):
        raise SystemExit(f"Erro ao gerar links: {saida}")
    prontos = [x for x in json.loads(saida) if x.get("link") and x.get("id")]
    r = sh(PY, "scripts/novo_produto.py", entrada=json.dumps(prontos))
    novos = [l for l in r.splitlines() if l.startswith("+")]
    dizer(f"Garimpo: {len(novos)} produtos novos.")
    for l in novos:
        dizer("  " + l[:90])


# ---------------------------------------------------------------- principal

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=int, default=80)
    ap.add_argument("--max-novos", type=int, default=8)
    ap.add_argument("--porta", type=int, default=9222)
    ap.add_argument("--so-precos", action="store_true")
    ap.add_argument("--sem-push", action="store_true")
    a = ap.parse_args()

    dizer(f"Rotina Achadoteca {dt.datetime.now():%d/%m/%Y %H:%M}")
    sh("git", "fetch", "-q", "origin")
    sh("git", "reset", "-q", "--hard", "origin/main")   # sempre parte do estado oficial do GitHub
    painel = Painel(a.porta)
    try:
        conferir_precos(painel)
        if not a.so_precos:
            garimpar(painel, a.meta, a.max_novos)
    finally:
        painel.fechar()

    sh(PY, "build.py")
    LOG.parent.mkdir(exist_ok=True)
    antes = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
    LOG.write_text("\n".join(resumo) + "\n\n" + antes[:8000], encoding="utf-8")
    sh("git", "add", "-A")
    if sh("git", "status", "--porcelain").strip():
        sh("git", "commit", "-qm", "Rotina diária: preços e reposição")
        if not a.sem_push:
            sh("git", "pull", "-q", "--rebase", "origin", "main")
            sh("git", "push", "-q", "origin", "HEAD:main")
            dizer("Enviado ao GitHub; o site, os posts e o Pinterest se atualizam sozinhos.")
    else:
        dizer("Sem mudanças hoje.")


if __name__ == "__main__":
    main()
