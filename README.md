# Elegância Cristã — Site da loja

Site de uma loja de roupas femininas (vestidos, saias e conjuntos) com temática cristã.
Lema: *"Operando Deus quem impedirá"*. Projeto da Fidela Web, feito em Python, Django e Django REST Framework.

> Status: **v1 concluída** (etapas 1 a 8, tag `v1.0`). **v2 em desenvolvimento** na branch `v2`
> (pagamento online, contas de clientes e parcelamento): etapas 1 a 5 de 9 concluídas.
> ⚠️ **A v2 ainda não pode ir ao ar** (faltam o pagamento e a revisão final; o e-mail ainda sai só no console;
> o frete tem valores provisórios).
> O roteiro completo está no [CLAUDE.md](CLAUDE.md) e as decisões técnicas em [DECISIONS.md](DECISIONS.md).

## Versões
| Versão | Onde está | O que tem |
|---|---|---|
| v1.0 | tag `v1.0` (`git switch --detach v1.0` para ver) | Catálogo, carrinho na sessão, pedido enviado pelo WhatsApp, API de leitura, admin |
| v2 | branch `v2` | Tudo da v1 + contas de clientes, Pix, cartão parcelado e parcelamento configurável (em andamento) |

## Requisitos
- Python 3.12 ou superior (desenvolvido com 3.14)
- MySQL Server 8 ou superior

## Instalação (Windows / PowerShell)

1. **Criar e ativar o ambiente virtual** (isola as bibliotecas deste projeto):
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. **Instalar as dependências:**
   ```powershell
   pip install -r requirements.txt
   ```
3. **Criar o banco e o usuário no MySQL** (rode no MySQL Workbench, como administrador). Troque `SUA_SENHA_AQUI` por uma senha forte:
   ```sql
   CREATE DATABASE elegancia_crista CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   CREATE USER 'elegancia'@'localhost' IDENTIFIED BY 'SUA_SENHA_AQUI';
   GRANT ALL PRIVILEGES ON elegancia_crista.* TO 'elegancia'@'localhost';
   -- Banco que o Django cria ao rodar os testes. "\_" porque "_" é curinga no GRANT.
   GRANT ALL PRIVILEGES ON `test\_elegancia\_crista`.* TO 'elegancia'@'localhost';
   FLUSH PRIVILEGES;
   ```
   **Nunca use o `root` no `.env`** (decisão 70): o site só precisa do banco da loja. O usuário
   tem todos os privilégios **nesses dois bancos** porque as migrations criam e alteram tabelas.
   A senha fica só no `.env`. Para gerar uma senha forte:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`
4. **Configurar o `.env`:** copie `.env.example` para `.env` e preencha:
   ```powershell
   copy .env.example .env
   ```
   - `SECRET_KEY`: gere com
     `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`
   - `DB_PASSWORD`: a senha criada no passo 3.
   - O arquivo `.env` **nunca** vai para o Git.
5. **Criar as tabelas** e **rodar o servidor:**
   ```powershell
   python manage.py migrate
   python manage.py runserver
   ```
   Abra http://127.0.0.1:8000/ — deve aparecer a página inicial da loja.
6. **(Opcional) Cadastrar os produtos de exemplo** com as fotos de `assets/`:
   ```powershell
   python manage.py carregar_exemplos
   ```
   Preços e estoques são fictícios; ajuste no admin. Pode rodar de novo sem duplicar.
7. **Criar a conta de administração** (agora o login é pelo **e-mail**):
   ```powershell
   python manage.py createsuperuser
   ```
   O comando pede e-mail e senha (mínimo de 10 caracteres).
8. **Configurar o 2FA do admin** (obrigatório para entrar no `/admin/`, decisão 75):
   ```powershell
   python manage.py configurar_2fa seu-email@exemplo.com
   ```
   Leia o QR Code com um app autenticador (Google Authenticator, Microsoft Authenticator, Aegis...)
   e **guarde os 10 códigos de backup** em lugar seguro: eles aparecem uma única vez.
   No login do admin: e-mail, senha, escolha o dispositivo ("Celular" ou "Códigos de backup") e digite o código.
9. **Criar o grupo de permissões "Loja"** (decisão 76):
   ```powershell
   python manage.py criar_grupos
   ```

### Recuperar o acesso ao admin (2FA)
- **Perdeu o celular:** entre com um **código de backup** (cada um vale uma vez) e depois refaça o 2FA.
- **Perdeu o celular e os códigos:** alguém com acesso ao servidor roda
  `python manage.py configurar_2fa seu-email@exemplo.com --redefinir` (apaga o 2FA antigo e cria um novo).
- **Bloqueada por tentativas erradas** (15 minutos): espere, ou rode `python manage.py axes_reset`.

### Backup antes de migrar
No MySQL, uma migration que falha no meio **não** desfaz as mudanças de tabela que já fez. Antes de um
`migrate` que mexe em tabelas com dados (ex.: a v2 Etapa 5, que liga o pedido à conta), faça uma cópia:
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe" -u elegancia -p --single-transaction --no-tablespaces --result-file="C:\caminho\fora\do\projeto\backup.sql" elegancia_crista
```
(o `-p` pede a senha no terminal; o arquivo `backup.sql` tem dados pessoais: guarde fora do projeto e apague quando não precisar mais).

**Não use `>` para gravar o backup:** no PowerShell 5 o `>` grava em UTF-16 e estraga o arquivo
(acentos e restauração). O `--result-file` faz o próprio `mysqldump` gravar em UTF-8.

> A venv deste projeto se chama **`.venv`** (ative com `.venv\Scripts\activate`).

### Recriar o banco de desenvolvimento
Necessário uma vez, ao passar da v1 para a v2: a troca do modelo de usuário (v2 etapa 2, decisão 64)
não funciona num banco que já tem as tabelas da v1. **Apaga todos os dados**, use só em desenvolvimento.
```sql
DROP DATABASE elegancia_crista;
CREATE DATABASE elegancia_crista CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```
Depois: `python manage.py migrate`, `python manage.py carregar_exemplos`, `python manage.py createsuperuser`,
`python manage.py configurar_2fa <email>` e `python manage.py criar_grupos`.

## Variáveis de ambiente
| Variável | Para que serve |
|---|---|
| `SECRET_KEY` | Chave secreta do Django (obrigatória) |
| `DEBUG` | `True` em desenvolvimento, `False` em produção |
| `ALLOWED_HOSTS` | Domínios permitidos, separados por vírgula |
| `SECURE_HTTPS` | Deixe vazio: liga o HTTPS sozinho quando `DEBUG=False`. Use `False` só para testar localmente com `DEBUG=False` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexão com o MySQL |
| `WHATSAPP_NUMBER` | Número da loja (só dígitos, com DDI e DDD) |
| `CONTACT_EMAIL` | E-mail de contato e de privacidade (confirmado pela dona) |
| `STORE_LEGAL_NAME`, `STORE_CNPJ`, `STORE_ADDRESS` | Identificação do fornecedor (Decreto 7.962/2013). **Vazias** enquanto não houver CNPJ; nunca CPF nem endereço residencial (decisão 85) |
| `EMAIL_BACKEND` | Vazio = e-mails só no terminal (desenvolvimento). Produção: SMTP do Brevo (a configurar) |
| `DEFAULT_FROM_EMAIL` | Remetente dos e-mails (vazio = `Elegância Cristã <nao-responder@localhost>`) |
| `MERCADOPAGO_ACCESS_TOKEN` | Access Token do Mercado Pago (**de teste** no desenvolvimento). Vazio = pagamento online desligado |
| `MERCADOPAGO_WEBHOOK_SECRET` | Assinatura secreta do webhook (painel do Mercado Pago → Webhooks → modo Teste → evento "Order"). Vazia = o webhook responde 503 e não processa nada. Teste e produção têm chaves **diferentes** (v2 Etapa 7b) |
| `CSRF_TRUSTED_ORIGINS` | Opcional. Só ao abrir o site por um túnel (cloudflared, ngrok) para testar o webhook: o endereço do túnel **com** `https://`. Vazio = nenhuma origem extra |
| `MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME` | **Só no sandbox:** `APRO` faz o Pix de teste ser aprovado sozinho. Em produção, **vazio** |

## Estrutura de pastas
```
PROJETO/
├── config/          # settings, urls, wsgi (configuração do projeto)
├── contas/          # (v2) conta da cliente: login por e-mail, cadastro, segurança, LGPD
│   ├── models.py      # User (e-mail verificado, anonymized_at), UserManager e Consent (aceite dos termos)
│   ├── forms.py       # SignupForm (com aceite), LoginForm, ResetForm, Minha conta e admin
│   ├── views.py       # cadastro, verificação de e-mail e Minha conta (dados, e-mail, exportar, excluir)
│   ├── urls.py        # /conta/...: login, logout, cadastro, verificação, senha, minha-conta
│   ├── tokens.py      # tokens assinados: verificação de e-mail e troca de e-mail (24 h)
│   ├── emails.py      # envio dos e-mails de segurança + limite de 1 a cada 2 min
│   ├── legal.py       # versões da Política/Termos e prazos de retenção (LGPD)
│   ├── privacy.py     # exportar, anonimizar e limpar dados antigos
│   ├── decorators.py  # verified_email_required (protege o checkout)
│   ├── axes.py        # padroniza o e-mail para o bloqueio de tentativas
│   ├── admin_site.py  # admin com 2FA obrigatório (OTPAdminSite)
│   ├── admin_config.py # troca o admin padrão pelo admin com 2FA
│   ├── admin.py       # admin de usuários adaptado ao e-mail
│   ├── test_utils.py  # ajudantes dos testes (conta verificada, login no admin com 2FA)
│   └── management/commands/  # configurar_2fa, criar_grupos, limpar_dados_antigos
├── loja/            # catálogo e StoreSettings (configuração da loja): models, views, urls, admin, testes
│   ├── serializers.py # API: models → JSON
│   ├── api_views.py   # API: endpoints de leitura
│   ├── api_urls.py    # API: rotas sob /api/
│   └── management/commands/carregar_exemplos.py  # cadastra os produtos de exemplo
├── carrinho/        # carrinho na sessão (sem models)
│   ├── cart.py        # classe Cart: regras do carrinho e do estoque
│   ├── forms.py       # validação de tamanho e quantidade
│   ├── views.py       # ver, adicionar, atualizar, remover
│   └── context_processors.py  # contador de peças no menu
├── pedidos/         # pedido, checkout, frete, reserva de estoque e Meus pedidos
│   ├── models.py      # Order (conta, status e transições), OrderItem, ShippingRate, active_orders
│   ├── checkout.py    # create_order: carrinho -> pedido com frete e reserva (transaction.atomic)
│   ├── shipping.py    # calculate_shipping: tabela por UF + frete grátis
│   ├── installments.py # calculate_installments e get_installment_limit: parcelas do cartão
│   ├── reservations.py # expira pedidos não pagos e devolve o estoque
│   ├── whatsapp.py    # format_brl e link wa.me "falar sobre o pedido"
│   ├── forms.py       # CheckoutForm (telefone e CEP só com dígitos)
│   ├── views.py       # checkout, Meus pedidos e detalhe do pedido
│   ├── rate_limit.py  # limite de pedidos por IP (anti-robô)
│   ├── admin.py       # painel de pedidos (ações de status) e tabela de frete
│   └── management/commands/expirar_pedidos.py  # para um agendador chamar
├── pagamentos/      # (v2) pagamento pelo Mercado Pago
│   ├── models.py      # Payment: IDs do gateway, situação, valor, prazo e "copia e cola" (sem dado pessoal)
│   ├── gateway.py     # ÚNICO arquivo que usa o SDK do Mercado Pago (simulado nos testes)
│   ├── pix.py         # start_pix_payment (cria/reaproveita o Pix) e cancel_pix_charge (cancela no gateway)
│   ├── webhook.py     # regra do webhook: reconsulta, confere valor, idempotência, pagamento tardio
│   ├── views.py       # Pagar com Pix, página do QR Code, situação em JSON e o webhook
│   ├── admin.py       # lista de pagamentos, só consulta, com aviso de "pago após expirar"/"divergente"
│   ├── tests.py       # Pix, página do QR e aviso do admin
│   └── test_webhook.py # webhook: assinatura, reconsulta, idempotência, tardio, cancelamento
├── templates/
│   ├── base.html      # cabeçalho, menu e rodapé de todas as páginas
│   ├── 404.html       # página "não encontrada" (com DEBUG=False)
│   ├── loja/          # home, catalog, product_detail, about, contact, privacy, terms
│   │                  # e _product_card.html (cartão reutilizado)
│   ├── carrinho/      # cart_detail.html
│   ├── contas/        # login, cadastro, verificação, senha, bloqueio, Minha conta (account*)
│   │   └── email/     # textos dos e-mails (verificação, aviso de cadastro, nova senha, troca de e-mail)
│   ├── pedidos/       # checkout, my_orders, order_detail e _campo.html (campo com rótulo e erro)
│   ├── pagamentos/    # pix.html (QR Code, "copia e cola" e prazo)
│   └── admin/contas/  # anonymize_confirmation.html (confirmação da ação "Anonimizar contas")
├── static/
│   ├── css/style.css  # todo o visual do site
│   ├── js/main.js     # menu mobile, animações de scroll, aviso de cookies e página do Pix (copiar e atualizar)
│   ├── fonts/         # fontes WOFF2 + licenças (OFL)
│   └── img/           # logo em WebP e favicon
├── media/           # fotos enviadas pelo admin (fora do Git)
├── staticfiles/     # gerada pelo collectstatic em produção (fora do Git)
├── assets/          # logo e fotos originais fornecidas pela loja (não servida pelo Django)
├── manage.py        # comando de controle do Django
├── requirements.txt # dependências com versões fixas
├── .env.example     # modelo das variáveis de ambiente
├── CLAUDE.md        # regras e roteiro do projeto
└── DECISIONS.md     # decisões de arquitetura
```

## Fluxo de cada parte

### Catálogo (app `loja/`) — etapa 2
- `loja/models.py`: `Category` (Vestidos, Saias, Conjuntos — fixas), `Product`, `ProductVariant` (tamanho + estoque) e `ProductImage` (várias fotos, uma principal).
- `loja/validators.py`: upload só aceita JPG, PNG ou WebP, até 2 MB.
- `loja/admin.py`: painel em http://127.0.0.1:8000/admin/ com variações e imagens dentro da página do produto.
- **Migrations:** são o "histórico" do banco. Alterou um model? Rode `python manage.py makemigrations` (gera o arquivo) e `python manage.py migrate` (aplica no MySQL). A migration `0002` insere as 3 categorias fixas.
- **Testes:** `python manage.py test`.

**Cadastrar um produto:**
1. `python manage.py createsuperuser` (escolha usuário e senha).
2. `python manage.py runserver`, entre em `/admin/` e vá em *Produtos > Adicionar*.
3. Preencha nome, categoria e preço; adicione os tamanhos com o estoque de cada um; adicione as fotos e marque uma como principal.
4. Para esconder um produto sem apagar, desmarque *ativo*.

### Visual e front-end — etapa 3
- **`templates/base.html`**: esqueleto de todas as páginas (cabeçalho com menu, `<main>`, rodapé). Cada página faz `{% extends 'base.html' %}` e preenche `{% block content %}`, `{% block title %}` e `{% block meta_description %}`.
- **Dados da loja nos templates**: o context processor `loja/context_processors.py` entrega `WHATSAPP_NUMBER`, `CONTACT_EMAIL`, `INSTAGRAM_HANDLE` e `STORE_MOTTO` a todos os templates. Para mudar, altere o `.env` ou `config/settings.py` — nunca o HTML.
- **CSS** (`static/css/style.css`): dividido em 10 seções comentadas. Mobile-first: as regras gerais valem para o celular; `@media (min-width: 640px)` ajusta para tablet e `(min-width: 1024px)` para desktop.
  - **Trocar a cor da loja:** altere só as variáveis no topo (`--cor-principal`, `--cor-principal-escura`, `--cor-principal-clara`).
- **JavaScript** (`static/js/main.js`): quatro funções independentes:
  - `ativarMenuMobile` — menu hambúrguer, fecha com Esc.
  - `ativarCabecalhoInteligente` — cabeçalho some ao descer e volta ao subir.
  - `ativarRevelacaoNoScroll` — elementos com o atributo `data-revelar` surgem ao entrar na tela (`data-atraso="1"` a `"3"` escalona).
  - `ativarParallax` — o fundo com `data-parallax` se move mais devagar.
- **Acessibilidade**: link "Pular para o conteúdo", foco visível, `aria-expanded` no menu e, com "reduzir movimento" ligado no sistema, nenhuma animação. Sem JavaScript, todo o conteúdo continua visível.

### Páginas — etapa 4
| Endereço | View (`loja/views.py`) | Template |
|---|---|---|
| `/` | `home` | `loja/home.html` |
| `/catalogo/` (`?categoria=vestidos`, `&pagina=2`) | `catalog` | `loja/catalog.html` |
| `/produto/<slug>/` | `product_detail` | `loja/product_detail.html` |
| `/sobre/` | `about` | `loja/about.html` |
| `/contato/` | `contact` | `loja/contact.html` |
| `/privacidade/` | `privacy` | `loja/privacy.html` |
| `/termos/` (v2 Etapa 4) | `terms` | `loja/terms.html` |

**Caminho de um pedido do navegador:** `config/urls.py` → `loja/urls.py` (acha a rota) → função em `loja/views.py` (busca os produtos no banco) → `render()` monta o template → HTML volta ao navegador.

- **Só aparecem produtos ativos.** Produto com *ativo* desmarcado some do site e a página dele dá 404. Os destaques da home são os produtos ativos com *destaque* marcado (até 8).
- **`active_products()`** carrega categoria, fotos e tamanhos de uma vez (`select_related`/`prefetch_related`), evitando dezenas de consultas.
- **Cartão de produto:** `templates/loja/_product_card.html`, incluído na home e no catálogo com `{% include %}`.
- **Página do produto:** tamanhos esgotados aparecem riscados. O botão de carrinho fica desativado até a etapa 6.
- **Textos para a loja revisar:** `about.html` (história da loja), `privacy.html` e `terms.html` (rascunhos para revisão jurídica, reescritos na v2 Etapa 4).

### API de leitura (Django REST Framework) — etapa 5
API **pública e somente leitura**. Cadastrar e editar produtos é só pelo admin: qualquer POST, PUT ou DELETE recebe `405`.

| Endpoint | O que devolve |
|---|---|
| `GET /api/categorias/` | As 3 categorias (`id`, `name`, `slug`) |
| `GET /api/produtos/` | Produtos ativos, 12 por página (`?page=2`) |
| `GET /api/produtos/?categoria=vestidos` | Filtra por categoria |
| `GET /api/produtos/?destaque=true` | Só os destaques |
| `GET /api/produtos/<slug>/` | Um produto, com descrição, fotos e tamanhos (inativo → 404) |

**Caminho de uma requisição:** `config/urls.py` → `loja/api_urls.py` → view em `loja/api_views.py` (monta a consulta, reaproveitando `active_products()`) → serializer em `loja/serializers.py` (escolhe os campos) → JSON.

Exemplo (`/api/produtos/vestido-helena/`, resumido):
```json
{
  "id": 4,
  "name": "Vestido Helena",
  "slug": "vestido-helena",
  "category": {"id": 1, "name": "Vestidos", "slug": "vestidos"},
  "price": "229.90",
  "is_featured": true,
  "main_image": "http://127.0.0.1:8000/media/produtos/vestido-helena.webp",
  "url": "http://127.0.0.1:8000/produto/vestido-helena/",
  "description": "...",
  "images": [{"url": "...", "alt_text": "...", "is_main": true}],
  "variants": [{"size": "P", "available": true}, {"size": "GG", "available": false}]
}
```
- **`price` é texto** (`"229.90"`) para não perder centavos.
- **Tamanhos mostram só `available`**; o estoque exato nunca sai na API.
- **Limite:** 60 requisições por minuto por IP; acima disso, erro `429`.
- **Testar no navegador:** com `DEBUG=True`, abra http://127.0.0.1:8000/api/produtos/ para ver a "API navegável" do DRF. Com `DEBUG=False`, só JSON.

### Carrinho (app `carrinho/`) — etapa 6
| Endereço | View | Método |
|---|---|---|
| `/carrinho/` | `cart_detail` | GET |
| `/carrinho/adicionar/<id do produto>/` | `cart_add` | POST |
| `/carrinho/atualizar/<id da variação>/` | `cart_update` | POST |
| `/carrinho/remover/<id da variação>/` | `cart_remove` | POST |

**Onde fica o carrinho:** na sessão do Django. O navegador guarda só um cookie com um código aleatório; os dados ficam no banco, na tabela `django_session`, no formato `{"<id da variação>": quantidade}`. O preço **não** fica na sessão: é sempre lido do banco.

**Fluxo de "Adicionar ao carrinho":**
1. A cliente escolhe tamanho e quantidade na página do produto e envia o formulário (POST, com token CSRF).
2. `cart_add` valida com `AddToCartForm` (tamanho deste produto e com estoque; quantidade ≥ 1).
3. `Cart.add()` soma com o que já está no carrinho e confere o estoque. Se passar, diz quantas peças restam.
4. A view grava uma mensagem (`django.contrib.messages`) e **redireciona** (Post/Redirect/Get): para o carrinho se deu certo, para o produto se deu erro.

- **Estoque conferido** ao adicionar e ao alterar a quantidade. Se o estoque baixar depois, o item aparece com aviso no carrinho (e o checkout, na etapa 7, confere de novo).
- **Produto desativado** ou variação apagada somem sozinhos do carrinho.
- **Contador no menu:** `cart_count`, do context processor `carrinho.context_processors.cart_count`. Lê só a sessão, sem consultar o banco.
- **Quem só navega não ganha sessão:** a sessão só é gravada quando o carrinho muda.
- **Botão "Finalizar pedido"** leva ao checkout (fica desativado se algum item estiver com estoque em falta).

### Pedidos (app `pedidos/`) — etapa 7
| Endereço | View | O que faz |
|---|---|---|
| `/pedido/finalizar/` | `checkout` | Formulário com nome, WhatsApp e endereço; cria o pedido |
| `/pedido/confirmado/` | `order_confirmation` | "Pedido nº X recebido!" + botão do WhatsApp |

**Fluxo do checkout:**
1. Do carrinho, a cliente clica em *Finalizar pedido*. Se o carrinho estiver vazio ou com estoque em falta, volta ao carrinho com aviso.
2. Preenche o `CheckoutForm` (há um aviso da LGPD explicando o uso dos dados). Telefone e CEP podem ter máscara; são guardados só com dígitos.
   **Limite anti-robô:** cada IP pode fazer até 5 pedidos por hora (`pedidos/rate_limit.py`). Passou disso, aparece um aviso para chamar no WhatsApp e nada é salvo.
3. `create_order()` (`pedidos/checkout.py`), dentro de `transaction.atomic()`:
   trava as variações (`select_for_update`) → revalida o estoque → cria `Order` → cria cada `OrderItem` copiando nome, tamanho e **preço atual** → desconta o estoque.
   Faltou estoque? Nada é salvo e a cliente volta ao carrinho com a mensagem.
4. O carrinho é esvaziado, o número do pedido vai para a sessão, e a cliente é redirecionada para a confirmação.
5. Na confirmação, o botão abre `https://wa.me/<WHATSAPP_NUMBER>?text=<mensagem>` com número do pedido, itens, tamanhos, quantidades, total e endereço. Frete e pagamento são combinados na conversa.

**Para a loja (admin → Pedidos):**
- A lista mostra nº, cliente, telefone, data, total e status, com busca por nome/telefone/nº e filtros por status e data.
- O status (`novo`, `confirmado`, `enviado`, `cancelado`) pode ser trocado direto na lista ou dentro do pedido.
- **Cancelar devolve o estoque** automaticamente (também pela ação "Cancelar pedidos selecionados"). **Cancelado é final**: não dá para reabrir.
- Os itens aparecem dentro do pedido e não podem ser editados. Pedidos só são criados pelo site.
- Só dá para apagar pedido cancelado ou enviado (apagar um pedido novo sumiria com as peças reservadas).
- O campo *frete* existe, mas fica vazio na v1 (frete a combinar).

> **Mudou na v2 Etapa 5:** o checkout exige conta, calcula o frete e leva ao detalhe do pedido (não há mais
> `/pedido/confirmado/`); os status e as ações do admin são outros. Veja "Pedidos na v2" abaixo.

### Contas (app `contas/`) — v2 etapa 2
| Endereço | View | O que faz |
|---|---|---|
| `/conta/cadastro/` | `contas.views.signup` | Cria a conta (nome, sobrenome, e-mail, senha) e já entra |
| `/conta/entrar/` | `LoginView` do Django + `LoginForm` | Login por e-mail e senha |
| `/conta/sair/` | `LogoutView` do Django | Sai da conta (só por POST, pelo botão "Sair" do menu) |

**Caminho de um cadastro:**
```
POST /conta/cadastro/  →  config/urls.py ('conta/')  →  contas/urls.py ('cadastro/')
  →  contas/views.py::signup
       SignupForm (contas/forms.py): nome e sobrenome obrigatórios, e-mail em minúsculas e único,
                                     senha conferida pelos AUTH_PASSWORD_VALIDATORS
       form.save()  →  contas/models.py::User  (senha vira hash Argon2 com set_password)
       login(request, user)  →  sessão ganha código novo, carrinho mantido
  →  redirect para o "next" (se for deste site) ou para a página inicial
```
- O e-mail é sempre guardado e procurado **em minúsculas** (`UserManager`): "Maria@X.com" entra na conta "maria@x.com".
- Login errado mostra sempre "E-mail ou senha incorretos", exista o e-mail ou não.
- **Carrinho:** montado como visitante, continua depois do login e do cadastro; é apagado no logout.
- **Admin → Contas → Usuários:** lista com e-mail, nome, ativo, equipe e data de cadastro; busca por e-mail ou nome.
- Pedido ligado à conta e "Meus pedidos": v2 Etapa 5.

> **Mudou na etapa 3:** o cadastro não faz mais login automático e mostra sempre "Confira seu e-mail" (veja abaixo).

### Segurança da conta (app `contas/`) — v2 etapa 3
| Endereço | View | O que faz |
|---|---|---|
| `/conta/cadastro/` → `/conta/cadastro/enviado/` | `signup`, `signup_done` | Cadastro com resposta sempre igual; sem login |
| `/conta/verificar/<token>/` | `verify_email` | Link do e-mail (24 h): marca o e-mail como verificado |
| `/conta/verificacao-pendente/` | `verification_pending`, `resend_verification` | Explica e reenvia o link (POST, 1 a cada 2 min) |
| `/conta/senha/esqueci/` ... `/conta/senha/alterada/` | views do Django + `ResetForm` | Esqueci a senha (link de 1 h, uso único) |
| `/admin/` | `LojaAdminSite` | Login com e-mail, senha e código 2FA |

**Caminho de um cadastro:**
```
POST /conta/cadastro/ → config/urls.py → contas/urls.py → contas/views.py::signup
  → SignupForm.is_valid() (contas/forms.py): campos e senha; NÃO avisa e-mail repetido
  → register_signup():
       e-mail novo           → form.save() (hash Argon2) → emails.send_verification_email
       conta verificada      → make_password (só gasta tempo) → emails.send_account_exists_email
       conta não verificada  → troca nome e senha → emails.send_verification_email
       (emails.can_send_email: no máximo 1 e-mail a cada 2 min por conta)
  → redirect /conta/cadastro/enviado/ → templates/contas/signup_done.html (sempre a mesma página)
```

**Caminho do link de verificação:**
```
GET /conta/verificar/<token>/ → contas/views.py::verify_email
  → tokens.get_user_from_verification_token: assinatura ok? menos de 24 h? e-mail igual?
       não → templates/contas/verify_invalid.html (400)
       sim → user.email_verified = True → templates/contas/verify_done.html
```

**Checkout protegido:** `pedidos.views.checkout` tem `@verified_email_required`
(`contas/decorators.py`): visitante → login (com `next`); conta sem verificar → página pendente.

**Bloqueio de tentativas (django-axes):** 5 senhas erradas para o mesmo **e-mail + IP** → 15 minutos de
bloqueio (página `contas/bloqueado.html`, status 429). Vale também para o `/admin/`. A página é a mesma
exista o e-mail ou não. Desbloquear: `python manage.py axes_reset` ou admin → Axes.

**Caminho de um login bloqueado (6ª tentativa, mesmo e-mail + IP):**
```
POST /conta/entrar/ → contas/urls.py → LoginView do Django (LoginForm, contas/forms.py)
  → authenticate() percorre AUTHENTICATION_BACKENDS (config/settings.py), em ordem:
       1. axes.AxesStandaloneBackend → contas/axes.py::get_axes_username (e-mail em minúsculas)
          → AccessAttempt (banco) já tem 5 falhas há menos de 15 min → RECUSA
       2. ModelBackend (confere a senha) → nem chega a rodar
  → axes.middleware.AxesMiddleware vê o bloqueio → templates/contas/bloqueado.html (status 429)
```

**Caminho do login no admin com 2FA:**
```
POST /admin/login/ → config/urls.py → admin.site = contas/admin_site.py::LojaAdminSite (OTPAdminSite)
  → formulário do django-otp: e-mail + senha + dispositivo + código
       → authenticate() (o axes também conta aqui) → senha ok?
       → device.verify_token(código): TOTP do celular (30 s) ou código de backup (apagado ao usar)
  → login + marca na sessão "passou pelo 2FA" → OTPMiddleware: request.user.is_verified() = True
  → LojaAdminSite.has_permission(): is_staff E is_verified → painel /admin/
```

**Para testar no navegador:** com o `runserver` aberto, os e-mails aparecem **no terminal**. Copie o
link de lá e cole no navegador.

### LGPD e "Minha conta" (app `contas/`) — v2 etapa 4
| Endereço | View | O que faz |
|---|---|---|
| `/conta/cadastro/` | `signup` | Agora com a caixa de aceite (desmarcada) e registro em `Consent` |
| `/conta/minha-conta/` | `account` | Mostra os dados guardados e os aceites |
| `/conta/minha-conta/dados/` | `account_edit` | Corrige nome e sobrenome |
| `/conta/minha-conta/email/` → `/conta/minha-conta/email/confirmar/<token>/` | `email_change`, `email_change_confirm` | Troca de e-mail com link no novo endereço |
| `/conta/minha-conta/senha/` | `PasswordChangeView` do Django | Troca de senha (pede a atual) |
| `/conta/minha-conta/exportar/` | `account_export` | Baixa os dados em JSON (só POST) |
| `/conta/minha-conta/excluir/` → `/conta/conta-excluida/` | `account_delete`, `account_deleted` | Exclui a conta (anonimiza) |
| `/privacidade/`, `/termos/` | `loja.views.privacy`, `loja.views.terms` | Textos legais (rascunho, com versão) |

Nenhuma rota de "Minha conta" tem id na URL: todas usam `request.user` (contra IDOR).

**Caminho do aceite no cadastro:**
```
POST /conta/cadastro/ (accept_terms=on) → contas/urls.py → contas/views.py::signup
  → SignupForm.is_valid() (contas/forms.py): accept_terms é obrigatório (sem ele: erro, nada é gravado)
  → register_signup() → e-mail novo: transaction.atomic() { form.save() + record_consent(user) }
       record_consent → Consent(user, PRIVACY_POLICY_VERSION, TERMS_VERSION) (contas/legal.py)
                       → accepted_at = agora (auto_now_add) → tabela contas_consent
  → redirect /conta/cadastro/enviado/ (mesma página de sempre)
```

**Caminho da troca de e-mail:**
```
POST /conta/minha-conta/email/ → contas/views.py::email_change (@login_required)
  → EmailChangeForm (contas/forms.py): senha atual confere? e-mail diferente do atual?
  → e-mail livre?  sim → emails.send_email_change_link → tokens.make_email_change_token
                         (uid + e-mail atual + e-mail novo, assinado) → e-mail ao NOVO endereço
                   não → emails.send_email_in_use_notice → aviso "conta existente" ao dono dele
  → mesma mensagem nos dois casos → redirect /conta/minha-conta/
GET /conta/minha-conta/email/confirmar/<token>/ → views.email_change_confirm
  → tokens.read_email_change_token: assinatura? < 24 h? e-mail atual ainda é o do token?
  → user.email = novo (o unique do banco recusa se alguém ocupou) → aviso ao endereço antigo
  → templates/contas/email_change_done.html
```

**Caminho da exportação:**
```
POST /conta/minha-conta/exportar/ (CSRF) → contas/views.py::account_export (@login_required)
  → contas/privacy.py::export_user_data(request.user): conta + aceites (sem hash de senha)
  → json.dumps → HttpResponse com Content-Disposition: attachment → navegador baixa o .json
```

**Caminho da exclusão de conta:**
```
POST /conta/minha-conta/excluir/ → contas/views.py::account_delete (@login_required)
  → is_staff? → recusa (a dona não tranca o admin)
  → pedido ativo? (pedidos/models.py::active_orders, v2 Etapa 5) → página explica, nada muda
  → DeleteAccountForm: senha atual + caixa "entendo que é definitivo"
  → contas/privacy.py::anonymize_user, dentro de transaction.atomic():
       e-mail → anonimizada-<id>@anonimizado.invalid, nome vazio, senha inutilizável,
       is_active=False, anonymized_at=agora → registros do axes, 2FA e histórico do admin limpos
       (o hash da senha mudou → todas as outras sessões da conta caem)
  → logout(request) → redirect /conta/conta-excluida/
```

**Caminho do comando de limpeza (manual por enquanto):**
```
python manage.py limpar_dados_antigos [--dry-run]
  → contas/management/commands/limpar_dados_antigos.py::Command.handle
  → contas/privacy.py (prazos de contas/legal.py):
       anonymize_old_orders → Order com mais de 5 anos: nome, telefone, endereço apagados
       delete_old_unverified_accounts → User nunca verificado com mais de 30 dias: apagado
       delete_old_login_attempts → AccessAttempt > 30 dias e todo o AccessLog: apagados
  → call_command('clearsessions') → sessões vencidas apagadas
  → terminal: só quantidades
```

**Caminho do aviso de cookies:**
```
GET de qualquer página → templates/base.html: <div id="aviso-cookies" hidden>
  → static/js/main.js::ativarAvisoCookies: localStorage tem "aviso-cookies-visto"?
       sim → continua escondido     não → mostra a faixa
  → clique em "Entendi" → esconde e grava no localStorage (nada vai ao servidor; nenhum cookie novo)
```

**Identificação do fornecedor (pronta para o CNPJ):** `STORE_LEGAL_NAME`, `STORE_CNPJ` e `STORE_ADDRESS`
no `.env` → `config/settings.py` → `loja/context_processors.py::store_info` → Política, Termos e rodapé.
Vazias, mostram "[A DEFINIR PELA DONA]" (o rodapé não mostra nada). Nunca coloque CPF nem endereço residencial.

### Pedidos na v2: conta, status, reserva e frete (app `pedidos/`) — v2 etapa 5
| Endereço | View | O que faz |
|---|---|---|
| `/pedido/finalizar/` | `checkout` | Formulário de entrega + resumo com frete; cria o pedido da conta |
| `/pedido/meus-pedidos/` | `my_orders` | Lista **só** os pedidos da conta logada |
| `/pedido/meus-pedidos/<id>/` | `order_detail` | Detalhe (status, reserva, itens, frete, entrega); pedido de outra conta = 404 |

**Status e transições** (`Order.ALLOWED_TRANSITIONS`; o `Order.save()` recusa o resto):

| De \ Para | pago | expirado | cancelado | enviado | estornado |
|---|---|---|---|---|---|
| **aguardando pagamento** | gateway (Etapas 7/8) | prazo vencido | admin | — | — |
| **pago** | — | — | — | admin | estorno (Etapa 8) |
| **enviado** | — | — | — | — | estorno (Etapa 8) |
| **expirado, cancelado, estornado** | finais | | | | |

O estoque volta em: aguardando → expirado, aguardando → cancelado e pago → estornado. No estorno de pedido
**enviado**, a peça volta ao estoque pela mão da dona, quando chegar (pergunta pendente).

**Caminho de um checkout:**
```
POST /pedido/finalizar/ → config/urls.py → pedidos/urls.py → pedidos/views.py::checkout
  (@verified_email_required, contas/decorators.py)
  → reservations.expire_overdue_orders()   libera reservas vencidas antes de conferir o estoque
  → CheckoutForm.is_valid() (pedidos/forms.py)
  → checkout.create_order(cart, form, request.user), dentro de transaction.atomic():
       ProductVariant.select_for_update().order_by('pk')   trava as peças (em ordem de id)
       Cart.check_stock em cada item                        falta peça → OutOfStockError, nada salvo
       shipping.calculate_shipping(UF, soma)                ShippingRate + StoreSettings.free_shipping_threshold
                                                            UF sem frete → ShippingUnavailableError, nada salvo
       Order(user, status=aguardando_pagamento, shipping_cost, expires_at = agora + reserva)
       OrderItem (preço congelado) + estoque descontado = RESERVA
  → carrinho esvaziado → redirect /pedido/meus-pedidos/<id>/ → templates/pedidos/order_detail.html
```

**Caminho da expiração** (comando ou "preguiçosa"):
```
python manage.py expirar_pedidos        (agendador, a cada 5 min)
GET /produto/<slug>/, POST /carrinho/adicionar/, /pedido/finalizar/, /pedido/meus-pedidos/   (rede de segurança)
  → pedidos/reservations.py::expire_overdue_orders()
       overdue_orders(): status=aguardando E expires_at < agora   (índice order_status_expires_idx)
       para cada um → expire_order(id), em transaction.atomic():
            Order.select_for_update() + confere DE NOVO aguardando e vencido
               não está mais? (pago ou já expirado por outro processo) → não faz nada
               está → status = expirado → Order.save() → restore_stock(): F('stock') + qtd
```

**Caminho de "Meus pedidos" (contra IDOR):**
```
GET /pedido/meus-pedidos/7/ → pedidos/urls.py → views.order_detail (@login_required)
  → get_object_or_404(request.user.orders, pk=7)    SQL: WHERE id = 7 AND user_id = <conta logada>
       é da conta → order_detail.html     não é (ou não existe) → 404, a mesma resposta
```

- **Frete:** admin → *Fretes por UF* (preço editável na lista) e *Configuração da loja* (frete grátis a partir de,
  minutos de reserva). **Os valores atuais são PROVISÓRIOS** (exemplos por região, grátis a partir de R$ 299,00);
  o admin avisa enquanto houver algum. No checkout, com JavaScript, frete e total aparecem ao escolher a UF
  (`ativarFreteCheckout`, em `static/js/main.js`, somando em centavos); sem JavaScript, há a tabela num "Ver tabela de frete".
- **Admin → Pedidos:** status só leitura; ações "Marcar como enviado (só pedidos pagos)", "Marcar como entregue (só
  enviados)", "Cancelar (só aguardando pagamento; devolve o estoque)" e "Devolver peças ao estoque" (etapa 5b). Não existe "marcar como pago": só o gateway confirma pagamento. Só apaga pedido
  cancelado ou expirado. Busca também pelo e-mail da conta.
- **Pedidos da v1** (sem conta): migrados para "aguardando pagamento", **sem prazo** (não expiram sozinhos). Ficam só
  no admin; a dona decide cancelar ou não.
- **Excluir a conta com pedido ativo** (aguardando pagamento, pago, enviado ou entregue há menos de 30 dias, etapa 5b): a página explica
  e não mostra o formulário. **Admin → Usuários → ação "Anonimizar contas selecionadas"** (só a superusuária): pede
  confirmação, pula equipe, contas já anonimizadas e contas com pedido ativo. Antes de usar a pedido de alguém,
  confira que o pedido veio do e-mail da conta.
- **Exportação de dados** (Minha conta) inclui os pedidos da conta.

### Entregue, cancelamento pela cliente e estoque manual (app `pedidos/`) — v2 etapa 5b
| Endereço | View | O que faz |
|---|---|---|
| `/pedido/meus-pedidos/<id>/cancelar/` | `cancel_order` | **Só POST.** Cancela pedido da conta logada que aguarda pagamento e devolve o estoque |

**Status e transições finais** (`Order.ALLOWED_TRANSITIONS`, decisão 95):

| De \ Para | pago | expirado | cancelado | enviado | entregue | estornado |
|---|---|---|---|---|---|---|
| **aguardando pagamento** | gateway (Etapas 7/8) | prazo vencido | admin ou a própria cliente | — | — | — |
| **pago** | — | — | — | admin | — | estorno (Etapa 8) |
| **enviado** | — | — | — | — | admin | estorno (Etapa 8) |
| **entregue** | — | — | — | — | — | estorno (Etapa 8) |
| **expirado, cancelado, estornado** | finais | | | | | |

- O estoque volta sozinho em: aguardando → expirado, aguardando → cancelado e pago → estornado.
- Estorno de pedido **enviado ou entregue** não devolve estoque sozinho: no admin, ação **"Devolver peças ao estoque"**
  (só para estornado que já foi enviado), usada pela dona depois de conferir a peça. Fica no histórico do pedido
  (quem e quando), em `stock_restored_at`, e não se repete (decisão 97). Devolve todas as peças do pedido.
- **Pedido ativo** (bloqueia a exclusão da conta): aguardando, pago, enviado (sem limite) ou entregue há menos de 30 dias
  (a contar da **entrega**). Se a dona esquecer de marcar "entregue", o pedido segue bloqueando a exclusão.

**Caminho do cancelamento pela cliente:**
```
POST /pedido/meus-pedidos/7/cancelar/ → config/urls.py → pedidos/urls.py → pedidos/views.py::cancel_order
  (@login_required, @require_POST, CSRF)
  → expire_overdue_orders(user)                      se o prazo venceu, vira "expirado" (e não "cancelado")
  → get_object_or_404(request.user.orders, pk=7)     pedido de outra conta = 404
  → reservations.cancel_order_by_customer(user, 7), em transaction.atomic():
       Order.select_for_update() + confere DE NOVO aguardando e da conta
          não está mais? → False ("não pode mais ser cancelado")
          está → status = cancelado → Order.save() → restore_stock(): F('stock') + qtd
  → messages + redirect /pedido/meus-pedidos/ → templates/pedidos/my_orders.html
```

### Parcelamento no cartão (apps `loja/` e `pedidos/`) — v2 etapa 6
O admin escolhe quantas parcelas são possíveis e se o limite vale para todos os produtos ou só para um
(decisões 98 e 99). **O site só mostra as opções e (na Etapa 8) envia o limite ao Mercado Pago; quem divide e cobra é o
gateway.** Os valores mostrados são **estimativa**. Pix é sempre à vista.

**Como configurar (admin):**
- **Configuração da loja → Parcelamento no cartão:** máximo de parcelas (padrão 3, de 1 a 12), valor mínimo da parcela
  (padrão R$ 50,00) e política de juros (padrão "a loja absorve").
- **Produtos → coluna "máximo de parcelas":** editável direto na lista (botão "Salvar"). Vazio = regra geral; preenchido =
  vale só para aquele produto, para mais ou para menos. A ação **"Voltar à regra geral de parcelas da loja"** limpa os marcados.
- **Carrinho com vários produtos:** vale o **menor** limite entre os itens, e a parcela mínima ainda limita o resultado.

| Carrinho | Limite dos produtos | Resultado |
|---|---|---|
| R$ 300 | geral (3) | até 3x (R$ 100 cada) |
| R$ 120 | geral (3) | até **2x** (a parcela mínima de R$ 50 vence) |
| R$ 120 | um produto com 10x | até **2x** (a parcela mínima vence o limite do produto) |
| R$ 600 | um com 6x + um sem limite (geral 3) | até **3x** (o menor limite vale) |
| R$ 30 | qualquer | só 1x |

**Centavos:** a soma das parcelas é sempre exatamente o total. A parcela comum é truncada em centavos e a sobra fica na
primeira: R$ 100,00 em 3x = 33,34 + 33,33 + 33,33.

**Caminho do checkout (GET):**
```
GET /pedido/finalizar/ → config/urls.py → pedidos/urls.py → pedidos/views.py::checkout
  → Cart(request).items()                                    itens com o produto de cada um
  → installments.get_installment_limit(produtos)             menor limite: Product.max_installments ou StoreSettings
  → installments.calculate_installments(total dos produtos, limite)
       → StoreSettings.load()                                parcela mínima e política de juros
  → templates/pedidos/checkout.html                          "Pix: à vista / Cartão: em até Nx" + estimativa
```
A página do produto (`loja/views.py::product_detail`) usa as mesmas duas funções para a linha "ou em até Nx no cartão".

**Antes de aplicar a migration `loja/0005_parcelamento`** (4 `AddField`), faça o backup do banco (veja "Backup antes de migrar").

**Checklist sandbox → produção:** a política de juros do site precisa ser **igual** à da conta do Mercado Pago (o
"sem juros" é configurado lá, não pela API). Veja o checklist no fim deste arquivo.

### Pagamento com Pix (app `pagamentos/`) — v2 etapa 7a
A cliente gera um Pix com **QR Code dinâmico** e "copia e cola" no detalhe do pedido (decisões 100 a 105). É uma
cobrança **imediata** do Mercado Pago (Orders API), **não** o "Pix Automático" de cobranças recorrentes.
**Nesta parte (7a) o pedido ainda não vira "pago"**: quem confirma é o webhook, na Etapa 7b (seção seguinte).

**Regras principais:**
- Só o arquivo `pagamentos/gateway.py` fala com o Mercado Pago (SDK oficial `mercadopago` 3.6.0). Nos testes ele é simulado.
- Um Pix por pedido. Clicar de novo reaproveita o mesmo; a chave de idempotência evita cobrança duplicada no gateway.
- **Prazos:** o Pix vale `reservation_minutes` (mínimo 30) e a reserva do pedido vence no mesmo instante.
  Exemplo, com 30 min: Pix gerado às 14:00 → Pix e reserva vencem às 14:30.
- Vai ao Mercado Pago só o **e-mail** da conta e o **valor**. Sem CPF, nome ou endereço. No banco fica o `Payment`:
  IDs do gateway, situação, valor, prazo, "copia e cola" e imagem QR em Base64.
- A página do QR pergunta ao **nosso** servidor, a cada 5 s, se o pedido mudou. O navegador só atualiza a tela; nunca confirma pagamento.

**Caminho de "Pagar com Pix" (POST):**
```
POST /pagamentos/pedido/<id>/pix/gerar/ → config/urls.py → pagamentos/urls.py → pagamentos/views.py::start_pix
  → @login_required + get_object_or_404(request.user.orders, pk=id)     404 se não for da conta (IDOR)
  → gateway.is_configured()                                            sem token no .env: "indisponível"
  → pagamentos/pix.py::start_pix_payment(order)
       1. transaction.atomic + select_for_update no Order               aguardando e dentro do prazo?
          → Payment.objects.get_or_create(order, método pix)             status "criando", chave de idempotência
       2. gateway.create_pix_order(...)  (sem trava)                     POST /v1/orders no Mercado Pago (SDK)
          → build_pix_order_body: valor em texto, "PT30M", só o e-mail
       3. transaction.atomic + select_for_update                         grava IDs, "copia e cola", QR e prazo do Pix
          → Order.expires_at = Payment.expires_at                       (a reserva nunca passa a validade do Pix)
  → redirect /pagamentos/pedido/<id>/pix/ → views.pix_page
       → templates/pagamentos/pix.html exibe o QR Base64 salvo e o "copia e cola"
       → static/js/main.js::ativarPaginaPix → GET .../pix/situacao/ a cada 5 s → views.pix_status (JSON do nosso banco)
```

**Testar no sandbox (7a):**
1. Crie uma aplicação em [Suas integrações](https://www.mercadopago.com.br/developers/panel/app) (pode ser na sua conta de
   pessoa física) e copie o **Access Token de teste** para `MERCADOPAGO_ACCESS_TOKEN` no `.env`. Se a Orders API recusar
   (a documentação se contradiz sobre isso, decisão 100), crie um **usuário de teste vendedor** no painel e use as credenciais dele.
2. `pip install -r requirements.txt` e faça o backup do banco antes de `python manage.py migrate` (migrations `loja/0006` e
   `pagamentos/0001`). Depois, `python manage.py criar_grupos` (o grupo "Loja" ganha "ver pagamentos").
3. `MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME=APRO` no `.env` (o Mercado Pago aprova o Pix de teste sozinho).
4. Faça um pedido → detalhe do pedido → **"Pagar com Pix"** → a página mostra o QR e o "copia e cola".
5. Confira no painel do Mercado Pago (modo Teste → pagamentos de teste) e no admin (**Pagamentos**). Se o Mercado Pago
   recusar, o terminal do `runserver` mostra só `"criar Pix" recusado (HTTP 4xx)`.
6. Sem o webhook configurado, o pedido continua "aguardando pagamento". Para ele virar "pago", siga a seção da 7b abaixo.

### Webhook do Pix: confirmação, pagamento tardio e cancelamento (app `pagamentos/`) — v2 etapa 7b
Quando a cliente paga, o **Mercado Pago avisa o site** (webhook) e o pedido vira "pago" sozinho (decisões 106 a 109).
O aviso é só uma "campainha": o site **pergunta de novo ao Mercado Pago** o que aconteceu, com o próprio token,
e só então muda o pedido.

| Endereço | View | O que faz |
|---|---|---|
| `/pagamentos/webhook/mercadopago/` | `mercadopago_webhook` | **Só POST, sem login e sem CSRF** (protegido pela assinatura). Recebe o aviso do Mercado Pago |

**Regras principais:**
- **Assinatura:** o cabeçalho `x-signature` é conferido com a chave `MERCADOPAGO_WEBHOOK_SECRET` pelo validador oficial do
  SDK. Errada ou ausente: **401** e nada acontece. Se falhar com o ID como chegou, tenta com ele em minúsculas (decisão 106).
- **Reconsulta:** o corpo do aviso é ignorado; vale o que `GET /v1/orders/{id}` responde. "Pago" = `processed` + `accredited`.
- **Conferência (em `Decimal`):** ID da order, `external_reference` (`pagamento-<id>`), valor total, valor pago e total do
  pedido precisam bater. Senão, o pagamento fica **"Valor divergente (conferir)"** e o pedido **não** vira pago.
- **Idempotência:** o mesmo aviso pode chegar várias vezes. Com trava no banco, só o primeiro confirma; os outros saem
  como "repetido" (resposta 200, nada muda).
- **Respostas:** 401 (assinatura), 200 (aceito, repetido, order desconhecida ou aviso de outro tipo), 503 (problema
  nosso ou Mercado Pago fora do ar: ele reenvia depois).
- **Pago depois de expirar ou cancelar (opção B, decisão 108):** o pedido **não** volta. O pagamento fica
  **"Pago após expirar (decidir)"**, o admin mostra um aviso e a dona decide, com a cliente, se entrega ou estorna.
  Na página do Pix, a cliente vê: "Recebemos seu pagamento depois do prazo. A loja vai entrar em contato."
- **Cancelar o pedido cancela o Pix no Mercado Pago** (decisão 109), depois do cancelamento local e sem desfazê-lo se o
  gateway falhar. A **expiração** continua só local (o Pix vence sozinho no mesmo instante).

**Caminho do aviso do Mercado Pago (POST):**
```
POST /pagamentos/webhook/mercadopago/?data.id=ORD01...&type=order     (cabeçalhos x-signature e x-request-id)
  → config/urls.py → pagamentos/urls.py → pagamentos/views.py::mercadopago_webhook  (@csrf_exempt, @require_POST)
  → chave e token no .env?                                    não → 503
  → gateway.is_webhook_signature_valid(x-signature, x-request-id, data.id)
       → SDK WebhookSignatureValidator (HMAC-SHA256)          inválida → 401
  → type é "order"/"orders"?                                  não → 200 (não é conosco)
  → pagamentos/webhook.py::process_order_notification(data.id)
       1. Payment.objects.filter(gateway_order_id=data.id)     não achou → 200 ("desconhecida")
       2. gateway.get_order(data.id)  (sem trava)              GET /v1/orders/{id}; fora do ar → 503
       3. apply_gateway_order, em transaction.atomic():
            select_for_update no Order e depois no Payment
            Payment já final?                     → "repetido"
            não pago?                             → só atualiza o espelho (ou cancelado/expirado)
            valor/referência não batem?           → Payment "divergente"
            pedido aguardando                     → Order "pago" (Order.save valida a transição) + Payment "aprovado"
            pedido expirado/cancelado             → Payment "pago após expirar" (pedido não muda)
  → 200 (resposta vazia)
Depois: a página do Pix (main.js, a cada 5 s) lê pix_status → vê "pago" → recarrega → templates/pagamentos/pix.html
```

**Como a dona fica sabendo de um caso para decidir:** **Admin → Pagamentos** mostra um aviso amarelo no topo enquanto
houver pagamento "Pago após expirar" ou "Valor divergente" (com a contagem). Use o filtro "situação" para achá-los.
Ainda **não** há aviso por e-mail ou WhatsApp: fica para quando o Brevo for configurado (pendência na decisão 108).
Hoje o aviso só some quando o pagamento sair dessas situações (o estorno pelo admin chega na Etapa 8).

**O que configurar à mão para testar no sandbox:**
1. **Túnel:** o Mercado Pago precisa alcançar o seu `runserver` pela internet. Use um túnel, por exemplo
   `cloudflared tunnel --url http://localhost:8000` (Cloudflare) ou `ngrok http 8000`. Ele mostra um endereço
   `https://...` que muda a cada vez que o túnel é aberto.
2. **Host no `.env`:** ponha o host do túnel em `ALLOWED_HOSTS` (sem `https://`) e, se for navegar pelo endereço do túnel,
   também em `CSRF_TRUSTED_ORIGINS` (com `https://`). Reinicie o `runserver`.
   ```
   ALLOWED_HOSTS=localhost,127.0.0.1,abc-123.trycloudflare.com
   CSRF_TRUSTED_ORIGINS=https://abc-123.trycloudflare.com
   ```
3. **Painel do Mercado Pago** ([Suas integrações](https://www.mercadopago.com.br/developers/panel/app)) → sua aplicação →
   **Webhooks** → **modo Teste**: URL `https://<host-do-túnel>/pagamentos/webhook/mercadopago/` e evento **"Order"**. Salve.
4. **Chave no `.env`:** copie a **assinatura secreta** que o painel mostra para `MERCADOPAGO_WEBHOOK_SECRET` e reinicie o `runserver`.
5. Com `MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME=APRO`, gere um Pix: o Mercado Pago aprova sozinho, avisa o site e a página
   do Pix muda para "Pagamento confirmado". No terminal aparece `Webhook: pedido N, pagamento M, resultado "pago".`
6. **Pendente (decisão 106):** confirmar se o Mercado Pago assina o ID como ele chega ou em minúsculas. O log atual
   não diz qual das duas tentativas bateu; um jeito de descobrir é desligar uma delas temporariamente e repetir o teste.
7. Se aparecer `Webhook recusado: assinatura inválida`, confira a chave (a de **teste**, não a de produção) e se a URL do
   painel é a do túnel **atual**.

**Testes:** `python manage.py test pagamentos` (webhook em `pagamentos/test_webhook.py`; aviso do admin e mensagem de
pagamento tardio em `pagamentos/tests.py`). O Mercado Pago é sempre simulado; a assinatura é calculada de verdade
com uma chave falsa.

## Dados pessoais que o site guarda (LGPD)
Inventário real, por tabela e campo. A Política de Privacidade e a exclusão de conta se baseiam nele:
**se o site passar a guardar outro dado, atualize esta tabela, a Política e `contas/privacy.py`.**

| Tabela (model) | Campos com dado pessoal | Prazo / o que acontece |
|---|---|---|
| `contas_user` (`contas.User`) | `first_name`, `last_name`, `email`, `password` (só hash Argon2), `last_login`, `date_joined`, `email_verified`, `last_email_sent_at`, `anonymized_at` | Enquanto a conta existir; exclusão = anonimização. Nunca verificada: apagada após 30 dias |
| `contas_consent` (`Consent`) | `user`, versões aceitas, `accepted_at` | Fica como prova do aceite (sem dado pessoal depois da anonimização) |
| `pedidos_order` (`Order`) | `user` (a conta), `customer_name`, `phone`, `cep`, `street`, `number`, `complement`, `neighborhood`, `city`, `state` | 5 anos, depois anonimizado (ficam cidade e UF). Continua ligado à conta anonimizada. Entra na exportação |
| `pagamentos_payment` (`Payment`) | nenhum dado pessoal: pedido, IDs do Mercado Pago, situação, valor, prazo e "copia e cola". O e-mail vai ao Mercado Pago, mas não é copiado aqui | Junto com o pedido (registro financeiro) |
| `django_session` | carrinho, id da conta, dispositivo 2FA, id do último pedido (codificados) | 14 dias + `clearsessions` |
| `axes_accessattempt` | e-mail digitado, IP, navegador, caminho, horário | 30 dias |
| `axes_accesslog` | (desligado: não grava mais) | esvaziado pelo comando |
| `django_admin_log` | ação da dona; o "nome" de uma conta editada é o e-mail | limpo na anonimização |
| `otp_*` (2FA) | segredo e nome do dispositivo da dona | só contas do admin |

**Não guardamos:** CPF, data de nascimento, dados de cartão, histórico de logins bem-sucedidos, nada de rastreamento.
**Cookies:** `sessionid`, `csrftoken` e `messages` (todos estritamente necessários). O aviso de cookies usa `localStorage`.

## Testes
Rode todos os testes (o Django cria um banco de testes temporário e apaga no fim):
```powershell
python manage.py test
```
Ou só os de um app: `python manage.py test pedidos`.

| Arquivo | O que testa |
|---|---|
| `loja/tests.py` | Models do catálogo, validação de upload, páginas, API (só leitura, sem estoque exato), admin exige login |
| `carrinho/tests.py` | Adicionar, somar, limite de estoque, alterar quantidade, remover, total, produto desativado, sessão só quando necessário |
| `pedidos/tests.py` | Checkout cria pedido da conta e itens, preço guardado, estoque descontado, limite por IP, CSRF. **v2 Etapa 5:** prazo da reserva, frete por UF, grátis no limite, UF sem frete, frete congelado; todas as transições da tabela (`subTest`), estoque devolvido uma vez só; expiração (comando, `--dry-run`, idempotência, corrida com o pagamento, páginas que expiram); Meus pedidos (só os da conta, 404 para outra conta/sem dona/inexistente, login); pedido ativo; link do WhatsApp sem dado pessoal; admin (status só leitura, sem "pago", ações, exclusão, frete provisório, configuração única). **v2 Etapa 5b:** transições com "entregue"; pedido ativo a contar da entrega; cancelamento pela cliente (só POST, login, 404 para outra conta, só aguardando, clique duplo, pedido vencido); ações "entregue" e "Devolver peças ao estoque" (uma vez só, histórico, só estorno de enviado). Não provam concorrência real (ver decisão 97). **v2 Etapa 6:** parcelas (limite, parcela mínima, soma exata dos centavos em 1x a 12x, `Decimal`, política "cliente paga"); menor limite do carrinho; produto com limite maior que o geral em compra pequena (a parcela mínima vence); páginas do produto e do checkout (estimativa, nunca "sem juros"); admin (edição em lista recusa 0 e 13, ação "voltar à regra geral", grupo "Loja") |
| `pagamentos/tests.py` | **v2 Etapa 7a** (Mercado Pago simulado): corpo do Pix (valor em texto, `PT30M`, só e-mail, sem CPF, `APRO` só se configurado, `float` recusado); erro e falha de rede viram mensagem genérica e log sem token/e-mail; gerar Pix (prazo da cobrança igual ao da reserva, QR persistido, configuração da loja, reaproveita no 2º clique, mesma chave de idempotência após falha); 404 para outra conta, pedido da v1 e inexistente; não gera Pix para pedido cancelado, expirado ou vencido; só POST; login; sem token = indisponível; nunca marca "pago"; página do QR e situação em JSON (só lê o banco, `never_cache`, 404 para outra conta); reserva mínima de 30 min. **v2 Etapa 7b:** mensagem de pagamento tardio na página do Pix (pedido expirado e cancelado, sem QR, 404 para outra conta); aviso no admin de pagamentos ("Pago após expirar" e "Valor divergente", contagem, some sem casos) |
| `pagamentos/test_webhook.py` | **v2 Etapa 7b** (Mercado Pago simulado, assinatura HMAC calculada de verdade com chave falsa): assinatura inválida, ausente, malformada, de outro ID ou `x-request-id` (401), ID em minúsculas, sem chave (503), só POST, sem login/CSRF, tipo de aviso e order desconhecidos (200 sem consultar), gateway fora do ar (503), corpo ignorado, log sem segredos; pago, repetido (idempotência), valores e referência divergentes, pendente, cancelado/expirado no gateway, reembolso parcial não é pago, reserva definitiva, pagamento tardio (expirado e cancelado); cancelamento do Pix ao cancelar o pedido (falha do gateway não desfaz); chamadas reais do SDK com HTTP simulado; dois avisos simultâneos confirmam uma vez só |
| `contas/tests.py` | Senha em Argon2, e-mail em minúsculas, cadastro com resposta idêntica (novo, verificado, não verificado), pré-sequestro, limite de e-mails, link de verificação (válido, adulterado, vencido, e-mail trocado), checkout só verificado, login sem enumeração, bloqueio do axes (5 erros, mesmo texto, maiúsculas, outro IP, 15 min, admin), esqueci a senha, 2FA (app, backup de uso único, comando), grupo "Loja", carrinho do cadastro ao login. **LGPD (v2 Etapa 4):** caixa de aceite desmarcada e obrigatória, versão e data gravadas, Minha conta só com login e só da própria conta, troca de e-mail (senha, link único, vencido, adulterado, e-mail ocupado sem enumeração), exportação JSON sem hash, exclusão (anonimiza, derruba outras sessões, limpa axes e histórico do admin, staff não exclui), comando de limpeza (prazos e `--dry-run` sem dado pessoal), páginas legais, aviso de cookies e nenhum histórico de login. **v2 Etapa 5:** exclusão bloqueada com pedido ativo (GET e POST), liberada com pedidos encerrados; exportação com os próprios pedidos; ação "Anonimizar" (confirmação, pula equipe e pedido ativo, grupo "Loja" sem acesso); limpeza não apaga conta com pedido |

## Segurança
| Proteção | Onde |
|---|---|
| Segredos só em variáveis de ambiente (`.env` fora do Git) | `config/settings.py`, `.env.example`, `.gitignore` |
| `DEBUG` padrão `False`; HTTPS, cookies seguros e HSTS ligados com `DEBUG=False` | `config/settings.py` |
| Banco só pelo ORM (sem SQL escrito à mão); usuário MySQL com acesso a um único banco | models, README (instalação) |
| CSRF em todo formulário POST | templates (`{% csrf_token %}`), `CsrfViewMiddleware` |
| Escape automático nos templates (único `safe`: o SVG do QR Code, gerado pela biblioteca `qrcode`) | `templates/`, `pagamentos/views.py::make_qr_svg` |
| Validação de entrada com Forms; upload só JPG/PNG/WebP até 2 MB | `pedidos/forms.py`, `carrinho/forms.py`, `loja/validators.py` |
| API somente leitura, fechada por padrão, sem estoque exato, limite de 60 req/min | `loja/api_views.py`, `REST_FRAMEWORK` |
| Pedido só visível para a dona (contra IDOR): consulta sempre por `request.user.orders`, 404 igual para tudo | `pedidos/views.py::my_orders`, `order_detail` |
| Status só muda pela tabela de transições, com trava na linha; "pago" não existe no admin | `pedidos/models.py::Order.save`, `pedidos/admin.py` |
| Estoque devolvido uma vez só, mesmo com expiração e pagamento ao mesmo tempo | `pedidos/reservations.py::expire_order` |
| Frete, status e dona definidos pelo servidor (campos fora do formulário são ignorados) | `pedidos/checkout.py`, `pedidos/forms.py` |
| Link do WhatsApp sem dado pessoal na URL | `pedidos/whatsapp.py` |
| Anonimizar pelo admin: só superusuária, com confirmação, pula equipe e pedido ativo | `contas/admin.py::UserAdmin.anonymize_accounts` |
| Limite de 5 pedidos por hora por IP | `pedidos/rate_limit.py` |
| Pix: chaves do Mercado Pago só no `.env`; nunca em log; log sem e-mail, valor ou "copia e cola" | `config/settings.py`, `pagamentos/gateway.py` |
| Pix: só a dona do pedido gera e vê o Pix (404 igual para tudo); gerar só por POST + CSRF | `pagamentos/views.py` |
| Pix: nenhuma tela marca "pago"; a página só lê a situação no nosso banco | `pagamentos/views.py::pix_status` |
| Pix: sem cobrança duplicada (chave de idempotência gravada antes da chamada) e sem trava do banco durante a rede | `pagamentos/pix.py` |
| Pix: sem CPF; vai ao gateway só o e-mail e o valor | `pagamentos/gateway.py::build_pix_order_body` |
| Webhook: assinatura HMAC conferida pelo validador do SDK (aviso forjado = 401); única rota POST sem CSRF | `pagamentos/gateway.py::is_webhook_signature_valid`, `pagamentos/views.py::mercadopago_webhook` |
| Webhook: "pago" só depois de reconsultar o Mercado Pago com o nosso token; corpo do aviso ignorado | `pagamentos/webhook.py::process_order_notification` |
| Webhook: valor pago, valor da order e total do pedido conferidos em `Decimal`, mais ID e `external_reference` | `pagamentos/webhook.py::_matches_our_payment` |
| Webhook: idempotente (aviso repetido ou simultâneo confirma uma vez só, com trava no banco) | `pagamentos/webhook.py::apply_gateway_order` |
| Pagamento tardio não reativa o pedido (não vende a mesma peça duas vezes); a dona decide | `pagamentos/webhook.py::_mark_late`, `pagamentos/admin.py` |
| LGPD: só os dados necessários, aviso no checkout, Política e Termos (rascunhos versionados) | `templates/pedidos/checkout.html`, `templates/loja/privacy.html`, `templates/loja/terms.html` |
| Aceite registrado (versão + data/hora), caixa desmarcada | `contas/models.py::Consent`, `contas/views.py::record_consent` |
| Minha conta sem id na URL: só a própria conta (contra IDOR) | `contas/views.py`, `contas/urls.py` |
| Troca de e-mail e exclusão pedem a senha atual; e-mail novo provado por link | `contas/forms.py`, `contas/tokens.py` |
| Exclusão por anonimização (derruba todas as sessões) e prazos de retenção | `contas/privacy.py`, `limpar_dados_antigos` |
| Sem histórico de logins; logs sem dados pessoais (e-mail e IP mascarados no axes) | `AXES_DISABLE_ACCESS_LOG`, `AXES_SENSITIVE_PARAMETERS` |
| Só cookies estritamente necessários; aviso informativo | `templates/base.html`, `static/js/main.js` |
| Senhas com hash Argon2 e mínimo de 10 caracteres | `PASSWORD_HASHERS` e `AUTH_PASSWORD_VALIDATORS` em `config/settings.py` |
| Login, cadastro, bloqueio e "esqueci a senha" não revelam se o e-mail existe (enumeração) | `contas/forms.py`, `contas/views.py::register_signup`, `templates/contas/bloqueado.html` |
| Força bruta: 5 erros → 15 min de bloqueio por e-mail + IP (site e admin) | `django-axes`, `AXES_*` em `config/settings.py`, `contas/axes.py` |
| 2FA obrigatório no admin (app autenticador + códigos de backup) | `contas/admin_site.py`, `contas/admin_config.py`, `configurar_2fa` |
| E-mail verificado para comprar; cadastro sem login; anti pré-sequestro | `contas/decorators.py`, `contas/views.py`, `contas/tokens.py` |
| Limite de e-mails de segurança (1 a cada 2 min por conta) | `contas/emails.py::can_send_email` |
| Banco acessado por usuário com acesso só ao banco da loja | `.env`, README (instalação) |
| Grupo "Loja" sem acesso a contas de clientes e à segurança | `contas/management/commands/criar_grupos.py` |
| Código da sessão trocado no login (*session fixation*); logout só por POST | `LoginView`/`LogoutView` do Django, `contas/urls.py` |
| `next` só para páginas do próprio site (*open redirect*) | `LoginView` do Django |

## Checklist antes de publicar
- [ ] Gerar uma **nova `SECRET_KEY`** para produção (nunca reaproveitar a de desenvolvimento).
- [ ] `DEBUG=False` e `ALLOWED_HOSTS` com o domínio do site.
- [ ] Senha do MySQL forte e diferente da de desenvolvimento.
- [ ] `python manage.py migrate` e `python manage.py collectstatic` (copia os estáticos para `staticfiles/`, que o servidor web serve, junto com `media/`).
- [ ] `python manage.py check --deploy`: devem sobrar só os avisos `W005` e `W021` (HSTS em subdomínios e *preload*), desligados de propósito (veja DECISIONS.md, decisão 48).
- [ ] **Pendências de produção (decisão 69):** v2 Etapas 7, 8 e 9 concluídas; valores reais do frete (e "PROVISÓRIO" desmarcado); hospedagem definida (atualizar operadores e prazo de backup na Política); revisão jurídica da Política e dos Termos; identificação do fornecedor (CNPJ) preenchida pela dona no `.env`.
- [ ] **Agendar** `python manage.py limpar_dados_antigos` para rodar sozinho (ex.: uma vez por dia). O jeito depende da hospedagem (decisão 79).
- [ ] **Agendar** `python manage.py expirar_pedidos` a cada 5 minutos (decisão 88). Sem ele, a reserva vencida só é liberada quando alguém abre o produto, o carrinho, o checkout ou "Meus pedidos".
- [ ] Backup do banco (`mysqldump`) antes de cada `migrate` em produção.
- [ ] **Parcelamento:** a "política de juros" do admin (Configuração da loja) é igual à configurada na **conta do Mercado Pago**; se for "a cliente paga", a **revisão jurídica** cobre a informação sobre juros (CDC, art. 52); na Etapa 8, o limite de parcelas é calculado no servidor e congelado no pedido, nunca vindo do navegador (decisão 99).
- [ ] **Mercado Pago (v2 Etapa 7):** trocar o Access Token de teste pelo de **produção**; deixar `MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME` **vazio**; fazer um Pix real de valor baixo e estornar.
- [ ] **Webhook do Mercado Pago (v2 Etapa 7b):** no painel, **modo Produção**, URL `https://<domínio-da-loja>/pagamentos/webhook/mercadopago/` com o evento **"Order"**; copiar a **assinatura secreta de produção** (é diferente da de teste) para `MERCADOPAGO_WEBHOOK_SECRET`; tirar do `.env` os hosts de túnel (`ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`); conferir no Pix real que o pedido vira "pago" sozinho; o site precisa estar em **HTTPS**.
- [ ] **Aviso à dona por e-mail ou WhatsApp** quando houver "Pago após expirar" ou "Valor divergente" (decisão 108), junto com a configuração do Brevo. Até lá, ela precisa abrir **Admin → Pagamentos** com frequência.
- [ ] Banco com usuário **dedicado** (nunca `root`) e senha forte, diferente da de desenvolvimento (decisão 70).
- [ ] **E-mail de verdade:** configurar o SMTP do Brevo (`EMAIL_BACKEND` e credenciais no `.env`) e um `DEFAULT_FROM_EMAIL` de um domínio da loja. Com o backend de console, ninguém recebe o link de verificação nem o de nova senha.
- [ ] Criar a conta da dona com `createsuperuser` (login por e-mail) e **senha forte**, rodar `configurar_2fa` e guardar os códigos de backup; rodar `criar_grupos`.
- [ ] **IP real atrás de proxy** (Nginx, Cloudflare...): sem isso, o bloqueio de tentativas (axes) e o limite de pedidos tratam todas as clientes como **um único IP** (o do proxy) e bloqueiam todo mundo junto. Configure só se houver proxy **de confiança** na frente: `AXES_IPWARE_PROXY_COUNT = 1` (número de proxies) e `AXES_IPWARE_META_PRECEDENCE_ORDER = ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR']`, e ajuste `pedidos/rate_limit.py` do mesmo jeito. **Perigo:** ligar isso **sem** proxy deixa qualquer pessoa inventar o cabeçalho `X-Forwarded-For` e trocar de IP a cada tentativa, fugindo do bloqueio.
- [ ] Conferir que `python manage.py axes_reset` funciona no servidor (desbloqueio de emergência).
- [ ] Depois de alguns dias com o HTTPS funcionando, aumentar `SECURE_HSTS_SECONDS` (ex.: `31536000`, 1 ano).
- [ ] Rodar `python manage.py test` uma última vez.

## Se houver vazamento de dados
Passos práticos se houver suspeita de que alguém acessou dados que não devia (banco copiado, servidor invadido,
`.env` publicado por engano...). **Anote tudo com data e hora desde o início**: a ANPD pede esse registro.

1. **Conter:** tirar do ar o que estiver exposto (ex.: arquivo público, porta do banco aberta), trocar o acesso de
   quem não devia ter, desligar a conta comprometida.
2. **Trocar chaves e senhas** (na ordem):
   - `SECRET_KEY` (derruba todas as sessões e invalida os links de verificação e de nova senha);
   - senha do usuário do MySQL (`DB_PASSWORD`);
   - Access Token e assinatura do webhook do Mercado Pago (gerar novos no painel) e a senha/chave SMTP do Brevo;
   - senha e 2FA da conta da dona (`configurar_2fa --redefinir`).
3. **Avaliar o risco:** quais dados (use a tabela "Dados pessoais que o site guarda"), de quantas pessoas, desde quando.
   Senhas estão em hash Argon2, mas, se o banco vazou, vale pedir às clientes que troquem a senha.
4. **Comunicar a ANPD e as clientes afetadas** quando o incidente puder causar risco ou dano relevante
   ([LGPD, art. 48](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)). O Regulamento de
   Comunicação de Incidente (Resolução CD/ANPD nº 15/2024) fixa **3 dias úteis**, com prazos em dobro para agentes de
   pequeno porte. Confira o texto oficial e o formulário no site da ANPD na hora: as regras podem mudar.
   A comunicação às clientes vai para o e-mail delas, em linguagem simples: o que aconteceu, quais dados, o que a loja fez
   e o que elas podem fazer.
5. **Corrigir a causa** e registrar o que aconteceu e o que mudou (um novo item no `DECISIONS.md`).

## Pendências da dona da loja
Decisões de negócio que só a dona pode tomar (algumas com orientação jurídica). Até lá, os textos mostram
"[A DEFINIR PELA DONA]" ou "PROVISÓRIO".

1. **Identificação no site** (Decreto 7.962/2013, art. 2º): nome, CNPJ e endereço comercial. A loja segue sem CNPJ
   por decisão consciente (decisão 85); quando houver, preencher `STORE_LEGAL_NAME`, `STORE_CNPJ` e `STORE_ADDRESS` no `.env`.
2. Nome que aparece como **responsável** (controladora dos dados) na Política.
3. Concordância com o prazo de **5 anos** para guardar nome, telefone e endereço dos pedidos (sujeito à revisão jurídica).
4. Política de **troca de tamanho** e prazos além dos 7 dias legais (para os Termos).
5. **Prazo e forma de entrega** (para os Termos).
6. **Contato para assuntos de privacidade** (encarregado). Proposta: o próprio `elegancia.crist@gmail.com`.
7. Quem fará a **revisão jurídica** da Política e dos Termos antes da publicação.
8. **Parcelamento (v2 Etapa 6, perguntas à dona):** (a) **juros**: a loja absorve ou a cliente paga? (padrão atual: a loja absorve);
   (b) **parcela mínima** (padrão R$ 50,00); (c) **máximo padrão** (3x) e se algum produto de valor mais alto deve ter mais
   parcelas; (d) quem configura o "sem juros" na **conta do Mercado Pago**, e quando (antes da Etapa 8).
9. **Frete (v2 Etapa 5):** valor real por estado (ou região), valor a partir do qual o frete é grátis e se a loja entrega
   nos 27 estados. Hoje: valores PROVISÓRIOS.
10. **Estorno de pedido já enviado:** a peça volta ao estoque só depois de chegar e ser conferida, pela ação do admin (etapa 5b). Confirmar com a dona. **Devolução parcial** (só uma das peças): por enquanto é ajuste manual do estoque (definido pelo Kauan); a ação devolve todas as peças.
11. **Exclusão de conta:** bloquear por 30 dias depois da **entrega** (etapa 5b) está aprovado como padrão (a dona pode mudar). Quem marca "entregue" é a dona, no admin.
12. ~~Cancelamento pela cliente~~ e ~~status "entregue"~~: feitos na etapa 5b. Aprovados como padrão; a dona pode mudar.
13. **Antes de ter clientes reais:** a Política não tem reaceite (decisão 95). Decidir como avisar as clientes quando o texto mudar.
14. **Pix pago depois do prazo (v2 Etapa 7b, decisão 108):** o pedido não volta sozinho; a dona decide caso a caso se
    entrega (se ainda houver a peça) ou estorna. Confirmar com a dona e definir como ela prefere ser avisada (e-mail ou WhatsApp).

## Roteiro da v2
O escopo e as etapas da v2 estão no [CLAUDE.md](CLAUDE.md#etapas-do-roteiro-da-v2). Cada etapa concluída ganha
uma subseção em "Fluxo de cada parte".

Ideias que ficaram fora da v2 (podem entrar numa v3): conversão automática das fotos para WebP no upload e
preenchimento do endereço pelo CEP (ViaCEP).
