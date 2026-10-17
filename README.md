# Achadinhos e Mais

Site de achados do Mercado Livre com links de afiliado. É um site estático gerado em
Python: os produtos ficam em arquivos de texto e o GitHub (ou GitLab) publica de graça.

## Como está organizado

| Pasta / arquivo | O que tem |
|---|---|
| `site.yml` | Nome, endereço, redes sociais e categorias |
| `content/produtos/` | Um arquivo `.md` por produto |
| `content/listas/` | Listas e comparativos ("Presentes até R$ 300") |
| `templates/` | O visual das páginas |
| `static/` | CSS, imagens, área admin e gerador de oferta |
| `build.py` | Gera o site em `public/` |

## Rodar no computador

```bash
pip install -r requirements.txt
python build.py
python -m http.server -d public 8000
```

Depois abra http://localhost:8000.

## Publicar no GitHub Pages

1. Crie um repositório público chamado `achadinhos` e suba estes arquivos.
2. No repositório, vá em **Settings → Pages** e em **Source** escolha **GitHub Actions**.
3. A cada envio para a branch `main`, o site é gerado e publicado sozinho.
4. Ajuste `url` e `repositorio.nome` no `site.yml` com o seu usuário.

No GitLab o arquivo `.gitlab-ci.yml` já faz o mesmo; troque `repositorio.servico` para `gitlab`.

## Cadastrar produtos

- **Área admin** (`/admin/`): entre com **Token de acesso**. No GitHub, crie em
  Settings → Developer settings → Fine-grained tokens, só para este repositório, com
  permissão de leitura e escrita em **Contents**. Cada produto salvo vira um commit e o
  site se atualiza em cerca de um minuto.
- **Gerador de oferta** (`/admin/gerador.html`): monta a mensagem do WhatsApp, a legenda
  do Instagram e o arquivo do produto a partir do mesmo formulário.

## Antes de divulgar

- Troque os produtos de exemplo por produtos reais e mude `prototipo: false` no
  `site.yml` (enquanto estiver `true`, o Google é orientado a não indexar o site).
- Use só links gerados pelo painel de afiliados do Mercado Livre e siga os termos do programa.
