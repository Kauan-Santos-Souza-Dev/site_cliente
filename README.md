# Elegância Cristã — Site da loja

Site de uma loja de roupas femininas (vestidos, saias e conjuntos) com temática cristã.
Lema: *"Operando Deus quem impedirá"*. Projeto da Fidela Web, feito em Python, Django e Django REST Framework.

> Status: **v1 concluída** (etapas 1 a 8, tag `v1.0`). **v2 em desenvolvimento** na branch `v2`
> (pagamento online, contas de clientes e parcelamento): etapas 1 a 3 de 9 concluídas.
> ⚠️ **A v2 ainda não pode ir ao ar** (faltam LGPD, pagamento e a revisão final; o e-mail ainda sai só no console).
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
├── loja/            # catálogo: models, views, urls, admin, validadores, testes
│   ├── serializers.py # API: models → JSON
│   ├── api_views.py   # API: endpoints de leitura
│   ├── api_urls.py    # API: rotas sob /api/
│   └── management/commands/carregar_exemplos.py  # cadastra os produtos de exemplo
├── carrinho/        # carrinho na sessão (sem models)
│   ├── cart.py        # classe Cart: regras do carrinho e do estoque
│   ├── forms.py       # validação de tamanho e quantidade
│   ├── views.py       # ver, adicionar, atualizar, remover
│   └── context_processors.py  # contador de peças no menu
├── pedidos/         # pedido, checkout e WhatsApp
│   ├── models.py      # Order e OrderItem (regra de cancelamento no save)
│   ├── checkout.py    # create_order: carrinho -> pedido (transaction.atomic)
│   ├── whatsapp.py    # mensagem do pedido e link wa.me
│   ├── forms.py       # CheckoutForm (telefone e CEP só com dígitos)
│   ├── views.py       # checkout e confirmação
│   ├── rate_limit.py  # limite de pedidos por IP (anti-robô)
│   └── admin.py       # painel de pedidos
├── templates/
│   ├── base.html      # cabeçalho, menu e rodapé de todas as páginas
│   ├── 404.html       # página "não encontrada" (com DEBUG=False)
│   ├── loja/          # home, catalog, product_detail, about, contact, privacy, terms
│   │                  # e _product_card.html (cartão reutilizado)
│   ├── carrinho/      # cart_detail.html
│   ├── contas/        # login, cadastro, verificação, senha, bloqueio, Minha conta (account*)
│   │   └── email/     # textos dos e-mails (verificação, aviso de cadastro, nova senha, troca de e-mail)
│   └── pedidos/       # checkout, confirmation e _campo.html (campo com rótulo e erro)
├── static/
│   ├── css/style.css  # todo o visual do site
│   ├── js/main.js     # menu mobile, animações de scroll e aviso de cookies
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
- Ainda não existe: pedido ligado à conta e "Meus pedidos" (etapa 5).

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

## Dados pessoais que o site guarda (LGPD)
Inventário real, por tabela e campo. A Política de Privacidade e a exclusão de conta se baseiam nele:
**se o site passar a guardar outro dado, atualize esta tabela, a Política e `contas/privacy.py`.**

| Tabela (model) | Campos com dado pessoal | Prazo / o que acontece |
|---|---|---|
| `contas_user` (`contas.User`) | `first_name`, `last_name`, `email`, `password` (só hash Argon2), `last_login`, `date_joined`, `email_verified`, `last_email_sent_at`, `anonymized_at` | Enquanto a conta existir; exclusão = anonimização. Nunca verificada: apagada após 30 dias |
| `contas_consent` (`Consent`) | `user`, versões aceitas, `accepted_at` | Fica como prova do aceite (sem dado pessoal depois da anonimização) |
| `pedidos_order` (`Order`) | `customer_name`, `phone`, `cep`, `street`, `number`, `complement`, `neighborhood`, `city`, `state` | 5 anos, depois anonimizado (ficam cidade e UF). Ligado à conta só na Etapa 5 |
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
| `pedidos/tests.py` | Checkout cria pedido e itens, preço guardado, estoque descontado, cancelamento devolve estoque, mensagem do WhatsApp, admin de pedidos, limite por IP, CSRF |
| `contas/tests.py` | Senha em Argon2, e-mail em minúsculas, cadastro com resposta idêntica (novo, verificado, não verificado), pré-sequestro, limite de e-mails, link de verificação (válido, adulterado, vencido, e-mail trocado), checkout só verificado, login sem enumeração, bloqueio do axes (5 erros, mesmo texto, maiúsculas, outro IP, 15 min, admin), esqueci a senha, 2FA (app, backup de uso único, comando), grupo "Loja", carrinho do cadastro ao login. **LGPD (v2 Etapa 4):** caixa de aceite desmarcada e obrigatória, versão e data gravadas, Minha conta só com login e só da própria conta, troca de e-mail (senha, link único, vencido, adulterado, e-mail ocupado sem enumeração), exportação JSON sem hash, exclusão (anonimiza, derruba outras sessões, limpa axes e histórico do admin, staff não exclui), comando de limpeza (prazos e `--dry-run` sem dado pessoal), páginas legais, aviso de cookies e nenhum histórico de login |

## Segurança
| Proteção | Onde |
|---|---|
| Segredos só em variáveis de ambiente (`.env` fora do Git) | `config/settings.py`, `.env.example`, `.gitignore` |
| `DEBUG` padrão `False`; HTTPS, cookies seguros e HSTS ligados com `DEBUG=False` | `config/settings.py` |
| Banco só pelo ORM (sem SQL escrito à mão); usuário MySQL com acesso a um único banco | models, README (instalação) |
| CSRF em todo formulário POST | templates (`{% csrf_token %}`), `CsrfViewMiddleware` |
| Escape automático nos templates (nenhum filtro `safe`) | `templates/` |
| Validação de entrada com Forms; upload só JPG/PNG/WebP até 2 MB | `pedidos/forms.py`, `carrinho/forms.py`, `loja/validators.py` |
| API somente leitura, fechada por padrão, sem estoque exato, limite de 60 req/min | `loja/api_views.py`, `REST_FRAMEWORK` |
| Confirmação do pedido sem número na URL (vem da sessão) | `pedidos/views.py` |
| Limite de 5 pedidos por hora por IP | `pedidos/rate_limit.py` |
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
- [ ] **Pendências de produção (decisão 69):** v2 Etapas 5 e 9 concluídas; hospedagem definida (atualizar operadores e prazo de backup na Política); revisão jurídica da Política e dos Termos; identificação do fornecedor (CNPJ) preenchida pela dona no `.env`.
- [ ] **Agendar** `python manage.py limpar_dados_antigos` para rodar sozinho (ex.: uma vez por dia). O jeito depende da hospedagem (decisão 79).
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
   - chaves do Mercado Pago (quando existirem, Etapas 7 e 8) e a senha/chave SMTP do Brevo;
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
8. Valor dos **juros do parcelamento** (perguntar na v2 Etapa 6).

## Roteiro da v2
O escopo e as etapas da v2 estão no [CLAUDE.md](CLAUDE.md#etapas-do-roteiro-da-v2). Cada etapa concluída ganha
uma subseção em "Fluxo de cada parte".

Ideias que ficaram fora da v2 (podem entrar numa v3): conversão automática das fotos para WebP no upload e
preenchimento do endereço pelo CEP (ViaCEP).
