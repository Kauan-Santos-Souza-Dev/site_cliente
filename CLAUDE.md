# Elegância Cristã — Site da loja (projeto da Fidela Web)

## Sobre o projeto
Site de uma loja de roupas femininas (vestidos, saias e conjuntos) com temática cristã.
Lema da loja: "Operando Deus quem impedirá".
É um projeto real, feito por um estudante de back end (Kauan) que está aprendendo Python, Django e DRF.
**O código precisa ensinar:** ele vai estudar o projeto depois de pronto.

## Como trabalhar comigo (regras mais importantes)
1. **Trabalhe em etapas pequenas e pare ao fim de cada uma.** Resuma o que foi feito, mostre como testar e espere minha aprovação antes de seguir.
2. Antes de cada etapa, use o **modo de planejamento**: mostre o plano e espere eu aprovar.
3. **Simplicidade antes de elegância.** Não crie abstrações, camadas ou padrões de projeto que um iniciante não consiga acompanhar. Se houver duas formas de fazer, escolha a mais simples e legível.
4. **Explique as decisões.** Toda decisão de arquitetura relevante vai em `DECISIONS.md` (o que foi escolhido, por quê, alternativas descartadas).
5. Se algo for ambíguo ou faltar uma decisão de negócio, **pergunte** em vez de assumir.
6. Não instale dependências novas sem avisar e explicar para que servem.

## Padrões de código
- Nomes de classes, variáveis, funções e campos em **inglês** (`Product`, `Order`, `price`).
- **Comentários, docstrings, textos do site e mensagens ao usuário em português do Brasil.**
- Comentários didáticos: explique o *porquê*, não só o *quê*. Em trechos de Django que um iniciante estranharia (migrations, `select_related`, sessão, CSRF, `transaction.atomic`), explique o conceito em poucas linhas.
- Toda função, classe e model com docstring curta.
- Código legível acima de código curto. Funções pequenas, uma responsabilidade cada.
- Dinheiro **sempre** em `DecimalField`, nunca `float`.
- Mantenha o `README.md` atualizado: como instalar, rodar, estrutura de pastas e fluxo de cada parte.

## Stack da v1
- Python + **Django** (lógica de negócio, models, views, templates, admin).
- **Django REST Framework** para a API somente de leitura de produtos e categorias.
- **MySQL** acessado apenas pelo ORM do Django (Models e migrations). Sem SQL manual.
- **Front-end:** templates do Django + CSS puro + JavaScript puro. Sem Bootstrap, Tailwind, jQuery ou bibliotecas de animação.
- Sem login de clientes, sem pagamento online, sem cupons e sem cálculo automático de frete nesta versão.

## Estrutura sugerida (pode ajustar, justificando em DECISIONS.md)
- `config/` — settings, urls, wsgi.
- `loja/` — categorias, produtos, variações de tamanho, páginas institucionais, API.
- `carrinho/` — carrinho na sessão do Django.
- `pedidos/` — pedido, itens, checkout e mensagem do WhatsApp.
- `templates/`, `static/` (logo, CSS, JS), `media/` (fotos enviadas pelo admin).
- `assets/` — logo e fotos originais dos produtos, fornecidas por mim. Não é servida pelo Django: use como fonte para `static/` (logo) e para cadastrar os produtos de exemplo (fotos).

## Regras de negócio da v1
**Páginas:** Início, Catálogo (filtro por categoria), Produto, Carrinho, Sobre, Contato e Política de Privacidade.

**Produtos**
- Categorias fixas: Vestidos, Saias, Conjuntos.
- `Product` + `ProductVariant` (tamanho P, M, G, GG... com **estoque por tamanho**). Sem variação de cor.
- Várias imagens por produto, com uma principal.
- Campo `is_featured` para destaques da página inicial e `is_active` para ocultar produto sem apagar.

**Carrinho (sem login)**
- Fica na **sessão do Django**. O item é sempre uma variação (produto + tamanho).
- Validar estoque ao adicionar e de novo no checkout.
- Operações: adicionar, alterar quantidade, remover, ver total.

**Pedido e finalização**
- No checkout, o cliente informa só o necessário: nome, telefone/WhatsApp e endereço de entrega (CEP, rua, número, complemento, bairro, cidade, UF).
- O carrinho vira `Order` + `OrderItem` no banco, dentro de `transaction.atomic()`.
- `OrderItem` guarda **o preço no momento da compra** (o preço do produto pode mudar depois).
- Status do pedido: `novo`, `confirmado`, `enviado`, `cancelado`. Cancelar devolve o estoque.
- O estoque é descontado quando o pedido é criado.
- `Order` tem o campo `shipping_cost` (opcional, vazio na v1) para a v2 integrar frete sem refatorar.
- **Frete na v1:** o site mostra "frete a combinar pelo WhatsApp".
- Depois de salvar, redirecionar ao WhatsApp da loja (`https://wa.me/<número>?text=<mensagem>`) com mensagem pronta: número do pedido, itens, tamanhos, quantidades, total e endereço. Codificar o texto com `urllib.parse.quote`.
- O pagamento (Pix etc.) é combinado pela dona da loja na conversa. Gateway de pagamento fica para a v2.

**API (DRF)** — somente leitura, pública: listar categorias, listar produtos (filtro por categoria e destaques) e detalhar produto. Escrita só pelo Django Admin.

**Painel da loja:** Django Admin personalizado (listagens úteis, busca, filtros, variações e imagens dentro do produto, pedidos com itens visíveis e mudança de status).

## Identidade visual e front-end
- Fundo predominante **branco**, cor principal **roxo** (definida em variável CSS, ex.: `--cor-principal`), visual elegante e simples.
- **Mobile-first e responsivo**: CSS Grid/Flexbox, breakpoints simples. Testar em celular, tablet e desktop.
- **Sensação de movimento no scroll**, em JavaScript puro: elementos que surgem com fade/deslize (`IntersectionObserver`), cabeçalho que esconde ao rolar para baixo e reaparece ao rolar para cima, parallax leve no banner inicial. Respeitar `prefers-reduced-motion`.
- Imagens em WebP, `loading="lazy"` e `alt` descritivo. HTML semântico e boa acessibilidade (contraste, foco visível, rótulos nos formulários).

## Dados de contato da loja
- WhatsApp: (11) 98533-5054 (formato para o link: 5511985335054)
- E-mail: elegancia.crist@gmail.com (**confirmar com a loja antes de publicar**)
- Instagram: @elegancia.crista.oficial
- A loja ainda **não tem CNPJ**. Não colocar CNPJ, nota fiscal ou razão social no site.
- Número e e-mail ficam em variáveis de ambiente/configuração, não espalhados pelos templates.

## Segurança e privacidade (obrigatório)
- Credenciais (senha do MySQL, `SECRET_KEY`, etc.) **somente em variáveis de ambiente** (`.env`, fora do Git). Criar `.env.example` sem valores reais e `.gitignore` cobrindo `.env`, `media/` e `__pycache__`.
- Nunca colocar chaves, senhas ou credenciais no código.
- `DEBUG` e `ALLOWED_HOSTS` configurados por ambiente. Usar `DEBUG=False` em produção.
- Usar os mecanismos nativos do Django: ORM (sem SQL cru), proteção CSRF em todo formulário POST, validação com Forms, escape automático dos templates, admin com permissões.
- API pública apenas de leitura, com permissões explícitas (`AllowAny` só em leitura).
- **LGPD:** coletar só o necessário, página simples de Política de Privacidade e aviso no checkout dizendo para que os dados são usados.
- Validar upload de imagens (tipo e tamanho).

## Testes
Escreva testes simples com `django.test.TestCase`, comentados, para: carrinho (adicionar, estoque, remover), criação de pedido (preço guardado, estoque descontado, cancelamento devolve estoque) e API de produtos. Rode os testes ao fim de cada etapa.

## Etapas do roteiro
1. Ambiente, projeto Django, MySQL, variáveis de ambiente, `README` e `DECISIONS.md` iniciais.
2. Models (categoria, produto, variação, imagem) + migrations + Admin.
3. Templates base, identidade visual, responsividade e animações de scroll.
4. Páginas: Início, Catálogo, Produto, Sobre, Contato, Privacidade.
5. API DRF de leitura (categorias e produtos).
6. Carrinho na sessão.
7. Pedido, checkout e redirecionamento ao WhatsApp.
8. Testes, revisão de segurança e documentação final.

## Fora do escopo da v1 (não implementar)
Login/cadastro de clientes, pagamento online, cupons de desconto, frete automático dos Correios, variação de cor, deploy em produção.