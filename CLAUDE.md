# Elegância Cristã — Site da loja (projeto da Fidela Web)

## Sobre o projeto
Site de uma loja de roupas femininas (vestidos, saias e conjuntos) com temática cristã.
Lema da loja: "Operando Deus quem impedirá".
É um projeto real, feito por um estudante de back end (Kauan) que está aprendendo Python, Django e DRF.
**O código precisa ensinar:** ele vai estudar o projeto etapa por etapa.

**Versões:** a v1 (catálogo, carrinho, pedido pelo WhatsApp) está concluída e marcada com a tag `v1.0`.
A **v2** (pagamento online, contas de clientes e parcelamento) é desenvolvida na branch `v2`.

## Como trabalhar comigo (regras mais importantes)
1. **Trabalhe em etapas pequenas e pare ao fim de cada uma.** Entregue o resumo de fim de etapa (abaixo) e espere minha aprovação antes de seguir.
2. Antes de cada etapa, use o **modo de planejamento**: mostre o plano e espere eu aprovar.
3. **Simplicidade antes de elegância.** Não crie abstrações, camadas ou padrões de projeto que um iniciante não consiga acompanhar. Se houver duas formas de fazer, escolha a mais simples e legível.
4. **Explique as decisões.** Toda decisão de arquitetura relevante vai em `DECISIONS.md` (o que foi escolhido, por quê, alternativas descartadas). Decisões da v2 continuam a numeração (51 em diante) e levam " — v2 Etapa N" no título.
5. Se algo for ambíguo ou faltar uma decisão de negócio **ou de segurança**, **pergunte** em vez de assumir.
6. Não instale dependências novas sem avisar e explicar para que servem.
7. **Toda decisão de segurança é explicada:** o que protege, de qual ataque e onde está no código.

## Resumo ao fim de cada etapa
1. O que foi feito, em poucas linhas.
2. Arquivos criados ou alterados, cada um com seu papel em uma frase.
3. Diagrama em texto do caminho de UMA requisição da etapa (urls → view → model/serviço → template/resposta), nomeando os arquivos.
4. Conceitos novos (ex.: webhook, idempotência, hash) com explicação curta e o "porquê".
5. Como testar manualmente e como rodar os testes.
6. Decisões novas registradas no `DECISIONS.md`.
7. Perguntas que preciso responder antes da próxima etapa.

Atualize também a seção "Fluxo de cada parte" do `README.md` com a etapa concluída.

## Padrões de código
- Nomes de classes, variáveis, funções e campos em **inglês** (`Product`, `Order`, `price`).
- **Comentários, docstrings, textos do site e mensagens ao usuário em português do Brasil.**
- Comentários didáticos: explique o *porquê*, não só o *quê*. Em trechos de Django que um iniciante estranharia (migrations, `select_related`, sessão, CSRF, `transaction.atomic`, `AUTH_USER_MODEL`, webhooks), explique o conceito em poucas linhas.
- Toda função, classe e model com docstring curta.
- Código legível acima de código curto. Funções pequenas, uma responsabilidade cada.
- Dinheiro **sempre** em `Decimal`/`DecimalField`, nunca `float` (inclusive no cálculo de parcelas e na comparação com o valor pago informado pelo gateway).
- Mantenha o `README.md` atualizado: como instalar, rodar, estrutura de pastas e fluxo de cada parte.

## Stack
- Python + **Django** (lógica de negócio, models, views, templates, admin, autenticação).
- **Django REST Framework** para a API somente de leitura de produtos e categorias.
- **MySQL** acessado apenas pelo ORM do Django (Models e migrations). Sem SQL manual.
- **Front-end:** templates do Django + CSS puro + JavaScript puro. Sem Bootstrap, Tailwind, jQuery ou bibliotecas de animação. (Exceção possível: o script oficial do gateway, se a tokenização de cartão exigir.)
- **Gateway de pagamento:** **Mercado Pago**: cartão pelo **Checkout Pro** (página do Mercado Pago) e Pix com QR dinâmico pela API (decisão 53). Sempre começar no **sandbox**.
- **Senhas:** hash **Argon2** (`argon2-cffi`, decisão 63).
- **E-mail:** backend de console em desenvolvimento; **Brevo** via SMTP em produção (decisão 62).
- Dependências novas da v2 são propostas na Etapa 1 e instaladas só na etapa que as usa.

## Estrutura
- `config/` — settings, urls, wsgi.
- `loja/` — categorias, produtos, variações de tamanho, páginas institucionais, API.
- `carrinho/` — carrinho na sessão do Django.
- `pedidos/` — pedido, itens, checkout, frete e mensagem do WhatsApp.
- `contas/` (v2) — usuário customizado (login por e-mail), cadastro, login, "Minha conta", LGPD.
- `pagamentos/` (v2) — integração com o gateway, Pix, cartão, webhook, configuração de parcelamento.
- `templates/`, `static/` (logo, CSS, JS), `media/` (fotos enviadas pelo admin).
- `assets/` — logo e fotos originais dos produtos, fornecidas pela loja. Não é servida pelo Django.

## Regras de negócio (v1, continuam valendo)
**Páginas:** Início, Catálogo (filtro por categoria), Produto, Carrinho, Sobre, Contato e Política de Privacidade.

**Produtos**
- Categorias fixas: Vestidos, Saias, Conjuntos.
- `Product` + `ProductVariant` (tamanho P, M, G, GG... com **estoque por tamanho**). Sem variação de cor.
- Várias imagens por produto, com uma principal.
- Campo `is_featured` para destaques da página inicial e `is_active` para ocultar produto sem apagar.

**Carrinho**
- Fica na **sessão do Django**. O item é sempre uma variação (produto + tamanho).
- Validar estoque ao adicionar e de novo no checkout.
- Operações: adicionar, alterar quantidade, remover, ver total.
- O carrinho precisa **sobreviver ao login**.

**Pedido**
- O carrinho vira `Order` + `OrderItem` no banco, dentro de `transaction.atomic()`.
- `OrderItem` guarda **o preço no momento da compra**.
- `Order.shipping_cost` passa a ser usado na v2 e guarda o frete calculado no momento da compra.

**API (DRF)** — somente leitura, pública: listar categorias, listar produtos (filtro por categoria e destaques) e detalhar produto. Escrita só pelo Django Admin.

**Painel da loja:** Django Admin personalizado (listagens úteis, busca, filtros, variações e imagens dentro do produto, pedidos com itens visíveis e mudança de status).

## Escopo da v2
1. **Pagamento online via gateway**
   - **Pix com QR Code dinâmico** (cobrança imediata) e confirmação automática por webhook. **Não** é o "Pix Automático" do Banco Central (cobrança recorrente): esse produto não deve ser usado.
   - **Cartão de crédito**, com parcelamento.
2. **Contas de clientes:** cadastro, login, logout, verificação de e-mail, redefinição de senha, "Minha conta" (ver, corrigir, exportar e excluir dados).
3. **Parcelamento configurável no admin:** regra geral da loja (máximo de parcelas, valor mínimo da parcela, política de juros) e campo opcional no `Product` que **sobrescreve** a regra geral. Num carrinho com vários produtos, vale o **menor** limite entre os itens.
4. **Pedido ligado à conta**, novos status com transições permitidas, **reserva de estoque com expiração** para pedidos não pagos, frete e página "Meus pedidos".

### Decisões de negócio da v2 (decisões 53 a 63 no `DECISIONS.md`)
- **Frete:** tabela fixa por região/UF + frete grátis acima de um valor, **tudo editável no admin**, nenhum valor fixo no código. Os dados iniciais são exemplos **marcados como provisórios**. Melhor Envio/Correios fora da v2.
- **Conta:** a visitante navega e monta o carrinho sem conta; a **conta é obrigatória só no checkout**. O carrinho sobrevive ao login **e** ao cadastro.
- **Juros do parcelamento:** ainda não decididos pela dona. Ficam como **configuração** no `StoreSettings`; **perguntar o valor na v2 Etapa 6**. O "sem juros" do Mercado Pago é configurado na conta do gateway, e o site precisa ficar alinhado com ela.
- **Parcelas:** padrão inicial **até 3x**, **parcela mínima R$ 50,00**, ambos editáveis no admin (máximo sobrescrevível por produto; no carrinho vale o menor).
- **Pix:** expira em **30 minutos** (configurável); ao expirar, o pedido vira "expirado" e o estoque volta.
- **CPF:** **não armazenar**. Se o Pix exigir, pedir no pagamento e enviar direto ao gateway. Confirmar no sandbox (v2 Etapa 7) e avisar o Kauan.
- **Troca e estorno:** mínimo legal do CDC (art. 49): desistência em até 7 dias corridos após o recebimento, devolução integral (inclusive frete), frete de devolução por conta da loja. **Estorno total pelo admin.** Prazos além do legal e troca de tamanho são política a definir pela dona: textos como **rascunho marcado para revisão jurídica**.
- **Admin:** só a dona acessa; **2FA obrigatório** para contas do admin.
- **E-mail da loja:** ainda não confirmado (vale para o contato e para o remetente).

### Dependências da v2
- **Aprovadas e instaladas:** `argon2-cffi` (Etapa 2); `django-axes`, `django-otp` e `qrcode` (Etapa 3).
- **Pedir aprovação na etapa em que for usada:** `mercadopago` (Etapa 7).
- **E-mail:** só o backend de console até o Kauan enviar as credenciais do Brevo.

## Regras inegociáveis de segurança (v2)
- **Dados de cartão NUNCA passam pelo nosso servidor**, nem em log. Usar checkout hospedado ou tokenização do gateway.
- O pedido só vira **"pago" por confirmação do gateway** (webhook validado ou consulta à API do gateway). Nunca por redirecionamento do navegador nem por dado enviado pelo cliente.
- **Webhook:** validar autenticidade (assinatura/segredo ou reconsulta ao gateway), ser **idempotente** (o mesmo aviso pode chegar várias vezes) e conferir que o **valor pago bate com o total do pedido**.
- Chaves do gateway e segredos **só em variáveis de ambiente** (`.env`, fora do Git; atualizar `.env.example`). Começar **sempre no sandbox**.
- Senhas com o hash do Django (PBKDF2 ou Argon2). Mensagens de login e de "esqueci a senha" **não revelam** se um e-mail está cadastrado.
- Cada cliente só acessa **os próprios** pedidos e dados (contra **IDOR**: nunca buscar pedido só pelo ID da URL, sempre filtrar pelo dono).
- **Logs sem dados pessoais e sem dados de pagamento.**
- Nos testes, o gateway é **simulado** (sem chamadas reais de rede).

## Segurança e privacidade (já valiam na v1)
- Credenciais **somente em variáveis de ambiente** (`.env`, fora do Git). `.env.example` sem valores reais; `.gitignore` cobrindo `.env`, `media/` e `__pycache__`.
- `DEBUG` e `ALLOWED_HOSTS` configurados por ambiente. `DEBUG=False` em produção.
- Mecanismos nativos do Django: ORM (sem SQL cru), CSRF em todo POST (o **webhook** é a única exceção, e é protegido pela validação de autenticidade), validação com Forms, escape automático dos templates, admin com permissões.
- API pública apenas de leitura, com permissões explícitas (`AllowAny` só em leitura).
- **LGPD:** coletar só o necessário (justificar antes de guardar CPF, telefone ou endereço; se o CPF só serve ao gateway, preferir não armazená-lo), consentimento registrado (o que, quando, versão da política), Política de Privacidade e Termos de Uso (rascunhos para revisão jurídica), exclusão de conta por **anonimização** preservando o pedido pelo prazo legal, prazos de retenção documentados.
- Validar upload de imagens (tipo e tamanho).

## Identidade visual e front-end
- Fundo predominante **branco**, cor principal **roxo** (variável CSS), visual elegante e simples.
- **Mobile-first e responsivo**: CSS Grid/Flexbox, breakpoints simples.
- **Movimento no scroll** em JavaScript puro (`IntersectionObserver`, cabeçalho que esconde/reaparece, parallax leve), respeitando `prefers-reduced-motion`.
- Imagens em WebP, `loading="lazy"` e `alt` descritivo. HTML semântico e boa acessibilidade (contraste, foco visível, rótulos nos formulários).

## Dados de contato da loja
- WhatsApp: (11) 98533-5054 (formato para o link: 5511985335054)
- E-mail: elegancia.crist@gmail.com (**confirmar com a loja antes de publicar**)
- Instagram: @elegancia.crista.oficial
- A loja ainda **não tem CNPJ**. Não colocar CNPJ, nota fiscal ou razão social no site. Isso também restringe a escolha do gateway (conta de pessoa física).
- Número e e-mail ficam em variáveis de ambiente/configuração, não espalhados pelos templates.

## Testes
Testes simples com `django.test.TestCase`, comentados. Gateway sempre simulado. Além dos da v1 (carrinho, pedido, API), a v2 cobre: cadastro/login (sem enumeração de e-mail), carrinho após login, IDOR em pedidos e dados, cálculo de parcelas, reserva e expiração de estoque, webhook (assinatura inválida, repetição, valor divergente). **Rode a suíte inteira ao fim de cada etapa.**

## Etapas do roteiro da v2
1. Preparação e decisões: tag `v1.0`, branch `v2`, este CLAUDE.md, comparação de gateways, perguntas de negócio, roteiro e dependências. (Sem código de funcionalidade.)
2. Usuário customizado (login por e-mail) **antes** de qualquer outra mudança em models; cadastro, login, logout, validadores de senha; carrinho sobrevive ao login.
3. Segurança da conta: verificação de e-mail, redefinição de senha (e-mail no console em desenvolvimento), bloqueio de tentativas repetidas de login, admin reforçado (2FA e grupos de permissão).
4. LGPD: consentimento registrado, Política de Privacidade e Termos de Uso, aviso de cookies, "Minha conta" (ver, corrigir, exportar, excluir/anonimizar), prazos de retenção.
5. Pedido ligado à conta, novos status e transições, reserva de estoque com expiração, frete, "Meus pedidos".
6. Parcelamento no admin: configuração geral da loja + sobrescrita por produto + função única e testada de cálculo das parcelas.
7. Pagamento com Pix: cobrança no gateway, QR Code e "copia e cola", status atualizado na tela, webhook seguro e idempotente, expiração.
8. Pagamento com cartão parcelado: checkout hospedado/tokenização, parcelas da Etapa 6, webhook, recusa com mensagem clara, estorno básico pelo admin.
9. Revisão final: lista de ameaças e onde cada uma é tratada, `check --deploy`, README (fluxos e checklist sandbox → produção), DECISIONS.md.

## Fora do escopo da v2 (não implementar)
Deploy em produção, Pix Automático/cobranças recorrentes e assinaturas, boleto, cupons de desconto, variação de cor, login social (Google etc.), emissão de nota fiscal.
