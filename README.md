# Achadinhos e Mais

Site de achadinhos com links de afiliado (Mercado Livre, Shopee, Amazon, Magalu, AliExpress). É um site estático gerado em
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
- Use só links gerados pelo painel de afiliados de cada loja e siga os termos de cada programa.
- Para incluir outra loja, adicione um bloco em `lojas:` no `site.yml`.

## Postar no Instagram automaticamente

Cada produto ganha uma imagem pronta para o feed em `/ig/<produto>.jpg` (1080×1350).
O workflow **Postar no Instagram** publica um produto novo por vez, com imagem e legenda,
logo depois de cada publicação do site e de hora em hora entre 9h e 20h. O que já foi
postado fica registrado em `content/instagram-postados.json`. Para um produto não ir para o
Instagram, coloque `instagram: false` no arquivo dele.

Para ligar:

1. Conta do Instagram como **profissional** (Criador de conteúdo ou Empresa).
2. App na Meta for Developers com o produto **Instagram** e login pelo Instagram, com as
   permissões `instagram_business_basic` e `instagram_business_content_publish`.
3. Gere o token de acesso (longa duração) e pegue o ID da conta do Instagram.
4. No GitHub: Settings → Secrets and variables → Actions → crie `IG_USER_ID` e `IG_ACCESS_TOKEN`.
5. Mude `prototipo: false` no `site.yml` (em modo protótipo nada é postado).

O token dura 60 dias: renove antes de vencer e atualize o segredo `IG_ACCESS_TOKEN`.
