"""Responde comentários do Instagram que pedem o link (substitui o ManyChat).

  python3 scripts/comentarios.py ver      -> só lista os comentários e quais pediriam resposta (não envia nada)
  python3 scripts/comentarios.py          -> responde por DM (resposta privada) e no comentário

Primeira execução: marca os comentários que já existem como vistos, sem responder (evita repetir o que foi feito à mão).
Resposta privada: o Instagram só permite 1 por comentário e até 7 dias depois dele.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instagram as ig_mod  # noqa: E402
from instagram import ErroInstagram, chamar, id_da_conta, REGISTRO, RAIZ  # noqa: E402

ESTADO = RAIZ / "content" / "comentarios-respondidos.json"
PEDIDO = re.compile(
    r"\b(link|links|quero|eu quero|preco|valor|quanto|onde|comprar|compro|manda|mande|passa|passe|"
    r"me envia|envia|cade|adorei|amei|interessad[oa])\b")
MAX_POR_RODADA = 10
PUBLICAS = ["Te enviei por DM! 💛", "Mandei no seu direct 💛", "Link no seu direct! 🛍️", "Enviei por mensagem 💛"]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def mapa_midias() -> dict[str, str]:
    """id da mídia -> slug do produto ('' para Reels avulsos)."""
    reg = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    out = {}
    for k, v in reg.items():
        if k.startswith("story:"):
            continue
        slug = k.split("reel:", 1)[1] if k.startswith("reel:") else k
        out[str(v["midia"])] = "" if slug.startswith("avulso-") else slug
    return out


def comentarios(ig: str, midia: str) -> list[dict]:
    r = chamar("GET", f"{midia}/comments", fields="id,text,username,timestamp", limit=50)
    return r.get("data", [])


def mensagem(site_url: str, slug: str, nome: str) -> str:
    pagina = f"{site_url}/produto/{slug}/" if slug else f"{site_url}/links/"
    return (f"Oi{', ' + nome if nome else ''}! 💛 Aqui está o achadinho: {pagina}\n\n"
            "É só tocar em \"Ver no Mercado Livre\". Link de afiliado: a Achadoteca pode ganhar uma comissão, "
            "sem custo extra para você.\n\n"
            "Quer receber os próximos antes de todo mundo? O canal de ofertas está no link da bio.")


def main(ver: bool) -> None:
    import yaml
    site = yaml.safe_load((RAIZ / "site.yml").read_text(encoding="utf-8"))
    base = site["url"].rstrip("/")
    ig = id_da_conta()
    minha = chamar("GET", ig, fields="username").get("username", "")
    midias = mapa_midias()
    primeira = not ESTADO.exists()
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    recentes = chamar("GET", f"{ig}/media", fields="id,timestamp,comments_count", limit=30).get("data", [])
    if ver:
        import hashlib
        print('token:', ig_mod.descrever_token(), 'impressão', hashlib.sha256(ig_mod.token().encode()).hexdigest()[:8])
        for m in recentes[:1]:
            print('  bruto:', json.dumps(chamar('GET', f"{m['id']}/comments", fields='id,text,username,timestamp,from'), ensure_ascii=False)[:400])
        try:
            r = chamar('GET', f'{ig}/conversations', platform='instagram', limit=1)
            print('  mensagens (permissão): OK', len(r.get('data', [])), 'conversas')
        except ErroInstagram as e:
            print('  mensagens (permissão): ERRO', str(e)[:300])
        try:
            r = chamar('GET', recentes[0]['id'], fields='comments{id,text,username,from}')
            print('  comments{} no post:', json.dumps(r, ensure_ascii=False)[:300])
        except ErroInstagram as e:
            print('  comments{} ERRO', str(e)[:300])
        for m in recentes[:8]:
            print(f"mídia {m['id']} {m.get('timestamp')} comentários={m.get('comments_count')}")
            try:
                print('  leitura:', len(comentarios(ig, m['id'])), 'comentários')
            except ErroInstagram as e:
                print('  erro:', e)
    corte = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=6)
    fila = []
    for m in recentes:
        for c in comentarios(ig, m["id"]):
            if c["id"] in estado or c.get("username") == minha:
                continue
            quando = dt.datetime.fromisoformat(c["timestamp"].replace("+0000", "+00:00"))
            pede = bool(PEDIDO.search(norm(c.get("text") or "")))
            print(f"[{m['id']}] @{c.get('username')}: {c.get('text')!r} -> {'PEDE LINK' if pede else 'ignora'}")
            if primeira:
                estado[c["id"]] = {"status": "base", "data": time.strftime("%Y-%m-%d %H:%M")}
            elif pede and quando >= corte:
                fila.append((m["id"], c))
    if ver:
        print(f"{len(fila)} para responder; {'primeira execução marcaria tudo como visto' if primeira else 'modo ver: nada enviado'}.")
        return
    if primeira:
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n")
        print("Primeira execução: comentários existentes marcados como vistos, nada enviado.")
        return
    for midia, c in fila[:MAX_POR_RODADA]:
        slug = midias.get(str(midia), "")
        try:
            chamar("POST", f"{ig}/messages", recipient=json.dumps({"comment_id": c["id"]}),
                   message=json.dumps({"text": mensagem(base, slug, "")}))
            estado[c["id"]] = {"status": "dm", "data": time.strftime("%Y-%m-%d %H:%M")}
            try:
                chamar("POST", f"{c['id']}/replies", message=random.choice(PUBLICAS))
            except ErroInstagram as e:
                print(f"  (DM enviada; resposta pública falhou: {e})")
            print(f"  respondido @{c.get('username')} ({slug or 'links'})")
        except ErroInstagram as e:
            tent = estado.get(c["id"], {}).get("tentativas", 0) + 1
            estado[c["id"]] = {"status": "falhou" if tent >= 3 else "tentar", "tentativas": tent,
                               "erro": str(e)[:200], "data": time.strftime("%Y-%m-%d %H:%M")}
            print(f"  FALHOU @{c.get('username')}: {e}")
        time.sleep(4)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main(ver=sys.argv[1:] == ["ver"])
    except BaseException as e:  # o erro vai para o log (content/analise/comentarios.log)
        print(f"ERRO: {e}")
        sys.exit(1)
