# Decisões de arquitetura

Cada decisão: o que foi escolhido, por quê e quais alternativas foram descartadas.

O título de cada decisão indica a etapa do roteiro (CLAUDE.md) em que ela foi tomada. As decisões 1 a 50 são da v1 ("Etapa N"); a partir da 51, da v2 ("v2 Etapa N"):

| Etapa | Assunto | Decisões |
|---|---|---|
| 1 | Ambiente, projeto Django, MySQL e variáveis de ambiente | 1 a 8 |
| 2 | Models e Admin | 9 a 13 |
| 3 | Templates base, identidade visual e animações | 14 a 19 |
| 4 | Páginas (Início, Catálogo, Produto, Sobre, Contato, Privacidade) | 20 a 28 |
| 5 | API DRF de leitura | 29 a 34 |
| 6 | Carrinho na sessão | 35 a 40 |
| 7 | Pedido, checkout e WhatsApp | 41 a 46 |
| 8 | Testes, revisão de segurança e documentação | 47 a 50 |
| v2 · 1 | Preparação da v2: versionamento, gateway e decisões de negócio | 51 a 63 |
| v2 · 2 | Usuário customizado e autenticação básica | 64 a 69 |
| v2 · 3 | Segurança da conta | 70 a 76 (e atualiza 65, 66 e 69) |
| v2 · 4 | LGPD: aceite, Minha conta, retenção, textos legais, cookies | 77 a 85 (e reescreve 69) |
| v2 · 5 | Pedido ligado à conta, status, reserva de estoque, frete, Meus pedidos | 86 a 94 (e atualiza 44, 46, 78 e 80) |
| v2 · 5b | Status "entregue", cancelamento pela cliente, devolução manual de estoque | 95 a 97 (e atualiza 87 e 92) |
| v2 · 6 | Parcelamento configurável: regra geral, limite por produto, cálculo, juros e gateway | 98 e 99 (e atualiza 56 e 57) |
| v2 · 7a | Pix: Orders API, SDK, model `Payment`, prazos, tela do QR, CPF | 100 a 105 (e atualiza 53, 58, 59, 88 e 89) |

## 1. Django 6.1 com Python 3.14 — Etapa 1
- **Escolha:** Django 6.1 (a versão instalada pelo `pip`), em Python 3.14.
- **Por quê:** é a versão atual, compatível com o Python da máquina, e o projeto é novo (sem código legado).
- **Descartado:** Django 5.2 LTS — tem suporte mais longo, mas não oficialmente para o Python 3.14.

## 2. Driver MySQL: PyMySQL — Etapa 1
- **Escolha:** `PyMySQL`, ativado em `config/__init__.py` com `pymysql.install_as_MySQLdb()`.
- **Por quê:** é escrito só em Python e instala no Windows sem compilar nada.
- **Descartado:** `mysqlclient` (driver oficial, mais rápido) — exige compilador C e costuma não ter pacote pronto para Python 3.14 no Windows. Para esta loja, a diferença de velocidade é irrelevante.

## 3. Variáveis de ambiente com python-dotenv — Etapa 1
- **Escolha:** `python-dotenv` lê o arquivo `.env` em `settings.py`.
- **Por quê:** mantém senhas e chaves fora do código e do Git, com pouca "mágica" e fácil de entender.
- **Descartado:** `django-environ` (mais recursos, porém mais uma abstração para aprender) e `os.environ` puro (exigiria definir variáveis manualmente no terminal a cada sessão).
- **Detalhe:** `SECRET_KEY` não tem valor padrão (falha com erro claro se faltar) e `DEBUG` tem padrão `False`, o lado mais seguro.

## 4. Pasta do projeto chamada `config/` — Etapa 1
- **Escolha:** `django-admin startproject config .`, deixando `manage.py` na raiz.
- **Por quê:** segue a estrutura sugerida no CLAUDE.md e evita a pasta duplicada com o mesmo nome do projeto.

## 5. DRF e Pillow adiados — Etapa 1 (atualizada na Etapa 2)
- **Escolha:** não instalar `djangorestframework` nem `Pillow` na etapa 1.
- **Por quê:** só serão usados na etapa 5 (API) e na etapa 2 (`ImageField`). Instalar só o necessário, quando for necessário, deixa claro para que serve cada pacote.
- **Atualização (etapa 2):** `Pillow` foi instalado, pois o `ImageField` o exige. O DRF continua para a etapa 5.

## 6. Dados da loja em variáveis de ambiente — Etapa 1
- **Escolha:** `WHATSAPP_NUMBER` e `CONTACT_EMAIL` vêm do `.env` e ficam em `settings.py`; os templates os lerão de lá.
- **Por quê:** o CLAUDE.md pede que não se espalhem pelos templates, e o e-mail ainda precisa ser confirmado com a loja.

## 7. Idioma e fuso — Etapa 1
- **Escolha:** `LANGUAGE_CODE = 'pt-br'`, `TIME_ZONE = 'America/Sao_Paulo'`, `USE_TZ = True`.
- **Por quê:** admin e mensagens em português, e horários dos pedidos no horário de Brasília. Com `USE_TZ`, o banco guarda em UTC e o Django converte ao exibir.

## 8. Banco e usuário dedicados — Etapa 1
- **Escolha:** banco `elegancia_crista` (utf8mb4) e usuário `elegancia`, só com acesso a esse banco.
- **Por quê:** princípio do menor privilégio: o site nunca usa o `root` do MySQL.

## 9. Categorias fixas criadas por migration de dados — Etapa 2
- **Escolha:** Vestidos, Saias e Conjuntos são inseridas pela migration `0002_criar_categorias_fixas`, e o admin não permite adicionar nem excluir categorias.
- **Por quê:** a loja tem categorias fixas; assim elas existem em qualquer instalação (inclusive no banco de testes) sem cadastro manual.
- **Descartado:** *fixtures* (`loaddata`) e cadastro manual — dependem de um passo extra que alguém pode esquecer. Um `TextChoices` no `Product` também foi descartado: o filtro e a API ficam mais simples com uma tabela.

## 10. `PROTECT` na categoria e `CASCADE` nas variações/imagens — Etapa 2
- **Escolha:** `Product.category` usa `on_delete=PROTECT`; variações e imagens usam `CASCADE`.
- **Por quê:** apagar uma categoria por engano não pode levar todos os produtos junto. Já variações e imagens não fazem sentido sem o produto.

## 11. Tamanhos fixos (P, M, G, GG) e unicidade por produto — Etapa 2
- **Escolha:** `size` com `choices` e `UniqueConstraint(product, size)`.
- **Por quê:** simples e impede cadastrar dois "M" no mesmo produto. Para novos tamanhos, basta ampliar a lista e gerar uma migration.
- **Descartado:** tabela própria de tamanhos — mais flexível, porém complexa demais para a v1.

## 12. Imagem principal controlada no `save()` — Etapa 2
- **Escolha:** ao salvar uma imagem com `is_main=True`, as outras do produto são desmarcadas. `Product.main_image` devolve a principal, ou a primeira se nenhuma estiver marcada.
- **Por quê:** regra visível e fácil de ler em um só lugar.
- **Limitação:** `update()` e a exclusão em massa não passam pelo `save()`; no admin isso não ocorre.

## 13. Validação de upload: JPG/PNG/WebP até 2 MB — Etapa 2
- **Escolha:** validador em `loja/validators.py` (extensão e tamanho), somado à checagem do `ImageField` via Pillow (confirma que é imagem de verdade).
- **Por quê:** requisito de segurança do CLAUDE.md, sem dependências extras.
- **Adiado:** converter automaticamente para WebP; por ora as fotos devem ser enviadas já otimizadas.

## 14. Cores: lilás do logo + tom escuro para texto — Etapa 3
- **Escolha:** `--cor-principal: #907690` (cor do logo) em fundos e detalhes; `--cor-principal-escura: #6b516b` em textos, links, botões e rodapé; `--cor-principal-clara: #f6f2f6` em seções alternadas. Fundo predominante branco.
- **Por quê:** o lilás do logo sobre branco tem contraste de cerca de 4:1, abaixo do mínimo de acessibilidade (4,5:1) para texto. O tom escuro dá cerca de 7:1. O degradê do banner termina em `#7d637d` para o texto branco manter o contraste.
- **Descartado:** roxo mais vivo, que se afastaria da identidade do logo.

## 15. Fontes do Google hospedadas no próprio projeto — Etapa 3
- **Escolha:** Cormorant Garamond (títulos) e Lato (texto), em WOFF2 com o subconjunto latin (inclui acentos), na pasta `static/fonts/`, com as licenças OFL. Os arquivos foram baixados uma única vez do pacote Fontsource. São só 4 arquivos, cerca de 90 KB no total.
- **Por quê:** visual mais refinado, sem chamar servidores do Google a cada visita. Isso evita enviar o IP dos visitantes a terceiros (LGPD) e não depende de serviço externo.
- **Descartado:** carregar do Google por `<link>` (privacidade e dependência externa) e fontes do sistema (visual menos marcante).

## 16. Mobile-first com dois breakpoints — Etapa 3
- **Escolha:** CSS base para celular; ajustes em `min-width: 640px` (tablet) e `min-width: 1024px` (desktop). As grades usam `repeat(auto-fill, minmax(...))`, que se adaptam sozinhas.
- **Por quê:** a maioria das clientes deve acessar pelo celular, e poucos breakpoints são mais fáceis de manter.

## 17. Animações como aprimoramento progressivo — Etapa 3
- **Escolha:** os elementos com `data-revelar` só começam invisíveis quando o `<html>` tem a classe `js`, colocada por uma linha de script no `<head>`. Com `prefers-reduced-motion`, o CSS desliga as transições e o JS não roda revelação nem parallax.
- **Por quê:** se o JavaScript falhar, nada fica escondido; e quem tem sensibilidade a movimento não é afetado.
- **Técnicas:** `IntersectionObserver` (o navegador avisa quando o elemento aparece, sem cálculo a cada rolagem) e `requestAnimationFrame` (no máximo uma atualização por quadro no scroll).
- **Descartado:** bibliotecas como AOS ou GSAP, que o CLAUDE.md proíbe e que não são necessárias.

## 18. Context processor para os dados da loja — Etapa 3
- **Escolha:** `loja.context_processors.store_info` disponibiliza WhatsApp, e-mail, Instagram e lema em todos os templates.
- **Por quê:** os dados ficam em um só lugar (settings/.env), sem repetir em cada view.
- **Descartado:** uma *template tag* própria, que exigiria mais código para o mesmo resultado.

## 19. Página inicial provisória — Etapa 3
- **Escolha:** a rota `''` usa `TemplateView` com `home.html`, contendo cartões de exemplo. Os links de páginas que ainda não existem ficam com `#`.
- **Por quê:** permite validar o visual e as animações antes de existirem as views reais da etapa 4, quando a rota passa para uma view com produtos do banco.

## 20. Views em função, sem classes genéricas — Etapa 4
- **Escolha:** `home`, `catalog`, `product_detail`, `about`, `contact` e `privacy` são funções simples em `loja/views.py`. A função auxiliar `active_products()` concentra o filtro `is_active=True` e o carregamento das relações.
- **Por quê:** o fluxo (buscar dados → montar contexto → `render`) fica todo visível de cima para baixo, o que facilita o estudo. As classes genéricas (`ListView`, `DetailView`) escondem esse fluxo em métodos herdados.
- **Descartado:** `ListView`/`DetailView` — menos código, mas exigem conhecer a ordem dos métodos internos do Django.

## 21. Rotas em português, sem namespace — Etapa 4
- **Escolha:** `/catalogo/`, `/produto/<slug>/`, `/sobre/`, `/contato/`, `/privacidade/`, definidas em `loja/urls.py`, com nomes curtos (`catalog`, `product_detail`...).
- **Por quê:** endereços legíveis para as clientes; nomes de rota em inglês, como o resto do código. Com um só app de páginas, o namespace (`loja:catalog`) não traz ganho.

## 22. Filtro por categoria na query string (`?categoria=vestidos`) — Etapa 4
- **Escolha:** um único endereço `/catalogo/`, com a categoria como parâmetro. Categoria inexistente devolve 404.
- **Por quê:** funciona sem JavaScript, pode ser salvo e compartilhado, e a paginação combina facilmente com o filtro (`?categoria=saias&pagina=2`).
- **Descartado:** uma URL por categoria (`/catalogo/vestidos/`) — também boa, mas exige uma segunda rota para a mesma página.

## 23. Paginação de 12 produtos com `Paginator` — Etapa 4
- **Escolha:** `Paginator(...).get_page()`, que trata sozinho números inválidos (`?pagina=abc` volta para a página 1).
- **Por quê:** o catálogo vai crescer; 12 divide bem em 2, 3 e 4 colunas.

## 24. `select_related` + `prefetch_related` nas listagens — Etapa 4
- **Escolha:** `active_products()` usa `select_related('category')` e `prefetch_related('images', 'variants')`.
- **Por quê:** evita o problema "N+1" (uma consulta extra por produto para buscar foto e estoque). Com isso, o catálogo faz um número fixo de consultas, não importa quantos produtos tenha. As propriedades `main_image` e `total_stock` do model já usam esse cache.

## 25. Produtos de exemplo por management command — Etapa 4
- **Escolha:** `python manage.py carregar_exemplos` lê as fotos de `assets/`, converte para WebP (Pillow, já instalado), e cria produto, foto principal e tamanhos P/M/G/GG. Preços e estoques são fictícios. Se o slug já existe, o produto é pulado (pode rodar várias vezes). Cada produto é criado dentro de `transaction.atomic()`.
- **Por quê:** qualquer pessoa que instalar o projeto tem o catálogo de exemplo com um comando, e as fotos ficam ~15 vezes menores (PNG ~600 KB → WebP ~35 KB).
- **Descartado:** *fixtures* JSON (não convertem imagens) e cadastro manual (lento e sujeito a erro).
- **Categorias:** só há fotos de vestidos e conjuntos; a categoria Saias fica vazia até a loja cadastrar.

## 26. Página do produto antes do carrinho — Etapa 4
- **Escolha:** mostra os tamanhos (esgotado riscado, com texto oculto "(esgotado)" para leitor de tela) e um botão desativado "Carrinho disponível em breve". A escolha de tamanho vira formulário na etapa 6.
- **Galeria:** miniaturas são links para a foto; o JavaScript (`ativarGaleriaProduto`) apenas troca a foto grande. Sem JS, continua funcionando.

## 27. Contato sem formulário — Etapa 4
- **Escolha:** cartões com WhatsApp, Instagram e e-mail.
- **Por quê:** a loja já atende pelo WhatsApp; um formulário coletaria dados pessoais sem necessidade (LGPD) e exigiria proteção contra spam.

## 28. Página 404 própria — Etapa 4
- **Escolha:** `templates/404.html`, usada automaticamente pelo Django com `DEBUG=False`.
- **Por quê:** produto desativado ou link antigo levam a uma página no visual da loja, com link para o catálogo.

## 29. Django REST Framework para a API — Etapa 5
- **Escolha:** `djangorestframework==3.18.3` (pedido pelo CLAUDE.md). Arquivos: `loja/serializers.py`, `loja/api_views.py` e `loja/api_urls.py`, montados em `/api/`.
- **Descartado:** `django-filter` — os filtros `?categoria=` e `?destaque=true` cabem em poucas linhas de `get_queryset()`, sem dependência extra.

## 30. Na API, classes genéricas (nas páginas, funções) — Etapa 5
- **Escolha:** `ListAPIView` e `RetrieveAPIView`, uma classe por endpoint.
- **Por quê:** no DRF, as genéricas são o caminho padrão e já trazem paginação, permissões e JSON. Com funções (`@api_view`), teríamos de refazer a paginação à mão. Elas também só aceitam GET, e qualquer escrita recebe 405.
- **Descartado:** `ViewSet` + `Router` — menos linhas, mas as URLs ficam "mágicas" para quem está aprendendo.

## 31. Permissão padrão fechada (`IsAdminUser`) e `AllowAny` explícito — Etapa 5
- **Escolha:** em `REST_FRAMEWORK`, a permissão padrão é `IsAdminUser`; as três views públicas declaram `permission_classes = [AllowAny]`.
- **Por quê:** princípio de "seguro por padrão": uma view nova esquecida sem permissão fica fechada, em vez de pública.

## 32. Tamanhos com `available`, sem o estoque exato — Etapa 5
- **Escolha:** a API mostra `{"size": "M", "available": true}`; o campo `stock` nunca sai. Os serializers listam os campos um a um (nunca `'__all__'`).
- **Por quê:** decisão da loja: não revelar publicamente quantas peças existem. O site e o carrinho continuam usando o estoque real do banco.

## 33. Preço como texto no JSON — Etapa 5
- **Escolha:** manter o padrão do DRF, que entrega `DecimalField` como texto (`"199.90"`).
- **Por quê:** números com casas decimais em JavaScript são `float` e erram centavos (`0.1 + 0.2 = 0.30000000000000004`).

## 34. Paginação, limite de requisições e API navegável — Etapa 5
- **Escolha:** listas de produtos paginadas em 12 (`?page=2`; categorias, só 3, sem paginação); `AnonRateThrottle` de 60 requisições/minuto por IP; API navegável (página HTML do DRF) só com `DEBUG=True`.
- **Por quê:** respostas pequenas, proteção simples contra robôs copiando o catálogo, e nenhuma interface extra em produção.
- **Observação:** o throttling guarda a contagem no cache do Django (em memória, por padrão). Em produção com vários processos, a contagem fica por processo — suficiente para a v1.
- **Rota em português, parâmetro em inglês:** a página é `?page=` porque é o padrão do DRF; o site usa `?pagina=`.

## 35. Carrinho na sessão do Django — Etapa 6
- **Escolha:** app `carrinho/` sem models; o carrinho vive em `request.session['cart']`, gravado na tabela `django_session` (padrão do Django, validade de 2 semanas, cookie `HttpOnly`).
- **Por quê:** não exige login (requisito da v1) e a cliente não consegue alterar o conteúdo, porque o cookie guarda só um código aleatório; os dados ficam no servidor.
- **Descartado:** tabela `Cart` no banco (mais código, e carrinhos abandonados acumulariam) e carrinho em `localStorage`/cookie (a cliente poderia editar, e o servidor não enxerga).

## 36. Guardar só `{id da variação: quantidade}` — Etapa 6
- **Escolha:** nada de preço, nome ou foto na sessão; tudo é lido do banco ao exibir.
- **Por quê:** o carrinho sempre mostra o preço atual e o estado atual do produto. Se o produto for desativado ou a variação apagada, o item sai sozinho. O preço "congelado" fica no `OrderItem` (etapa 7). As chaves são texto porque a sessão é salva em JSON.

## 37. Classe `Cart` com a regra de estoque — Etapa 6
- **Escolha:** `carrinho/cart.py` concentra add/update/remove/items/total/count/clear. `add` e `update` devolvem a mensagem de erro (texto) ou `None`.
- **Por quê:** a regra de estoque precisa saber o que JÁ está no carrinho (2 no carrinho + 2 novas > 3 em estoque), e a `Cart` sabe disso. Os Forms validam só tipo e valor (é número? é ≥ 1? o tamanho é deste produto e tem estoque?). Devolver texto, em vez de lançar exceção, deixa a view mais fácil de ler para iniciantes.
- **Mensagem de estoque:** diz quantas peças restam ("Temos apenas 2 peças no tamanho M."), por decisão da loja. Não há limite extra por tamanho.

## 38. Sessão só é gravada quando o carrinho muda — Etapa 6
- **Escolha:** `Cart.__init__` usa `session.get()` (só lê) e grava com `session['cart'] = ...` em `save()`.
- **Por quê:** o contador do menu roda em todas as páginas; com `setdefault`, todo visitante ganharia uma linha em `django_session` e um cookie sem nem usar o carrinho (pior para o banco e para a privacidade). Há um teste garantindo isso.

## 39. Formulários POST + Post/Redirect/Get + mensagens — Etapa 6
- **Escolha:** adicionar/atualizar/remover são formulários HTML comuns com `{% csrf_token %}`, views com `@require_POST`, e redirecionamento ao final. Os avisos usam `django.contrib.messages`, exibidos no topo do `<main>` com `role="status"`.
- **Por quê:** funciona sem JavaScript, F5 não repete a ação, e o leitor de tela anuncia o resultado.
- **Descartado:** carrinho via JavaScript/`fetch` — mais interativo, mas bem mais código e exigiria tratar CSRF no JS.

## 40. Seletor de tamanho com rádios — Etapa 6
- **Escolha:** cada tamanho é um `<input type="radio">` escondido visualmente (mas focável), com um `<span>` estilizado ao lado; esgotados ficam `disabled` e riscados. O formulário de tamanho só aceita variações com estoque.
- **Por quê:** acessível por teclado (setas) e sem JavaScript.

## 41. `OrderItem` com cópia de nome, tamanho e preço — Etapa 7
- **Escolha:** `product_name`, `size` e `unit_price` são copiados do produto no momento da compra. O vínculo `variant` usa `on_delete=SET_NULL`.
- **Por quê:** o pedido é um registro histórico: se a loja mudar preço ou nome, ou apagar a variação, o pedido continua mostrando exatamente o que foi comprado. O vínculo com a variação serve só para devolver o estoque ao cancelar.

## 42. Checkout em `transaction.atomic()` com `select_for_update()` — Etapa 7
- **Escolha:** `pedidos/checkout.py::create_order` revalida o estoque de todos os itens, cria `Order` + `OrderItem` e desconta o estoque numa única transação, com as linhas das variações travadas.
- **Por quê:** ou tudo é salvo, ou nada (estoque insuficiente lança `OutOfStockError` e desfaz tudo). A trava impede que duas clientes comprem a última peça ao mesmo tempo. Reaproveita `Cart.check_stock`, a mesma regra do carrinho.

## 43. Cancelamento no `Order.save()`, e cancelado é final — Etapa 7
- **Escolha:** quando o status muda para `cancelado`, o `save()` devolve o estoque (com `F('stock') + quantidade`), dentro de uma transação e com a linha do pedido travada. Sair de `cancelado` é bloqueado no `clean()` (formulários/admin) e no `save()`.
- **Por quê:** a regra vale em qualquer caminho (página do pedido, lista editável, ação em massa, shell). A trava e a comparação com o status do banco impedem devolver o estoque duas vezes. "Cancelado é final" foi decisão da loja: evita ter de descontar o estoque de novo (que poderia já ter sido vendido).
- **Descartado:** *signals* (`post_save`) — escondem a regra longe do model, mais difícil para quem está aprendendo.

## 44. Página de confirmação + botão do WhatsApp (ajuste ao CLAUDE.md) — Etapa 7
- **Escolha:** depois de salvar, a cliente vai para `/pedido/confirmado/`, com o número do pedido, o resumo e o botão "Enviar pedido pelo WhatsApp" (link `wa.me` com a mensagem codificada por `urllib.parse.quote`).
- **Por quê:** decisão da loja. No redirecionamento direto, se o WhatsApp não abrir (computador sem o app), a cliente perde o número do pedido.
- **Segurança:** a URL não tem o número do pedido; ele vem da sessão (`last_order_id`). Assim ninguém vê o nome e o endereço de outra pessoa trocando um número na URL.
- **Atualização (v2 Etapa 5):** a página de confirmação e o `last_order_id` saíram. Com o pedido ligado à conta, o checkout leva ao detalhe do pedido em "Meus pedidos", protegido pelo filtro da dona (decisão 91).

## 45. Telefone e CEP só com dígitos — Etapa 7
- **Escolha:** o formulário aceita "(11) 91234-5678" e "01234-567", mas guarda só os dígitos (`clean_phone`, `clean_cep`). Telefone com 10 ou 11 dígitos; CEP com 8. A formatação volta na exibição (`format_phone`, `format_cep`, `format_brl` em `pedidos/whatsapp.py`).
- **Por quê:** dados uniformes no banco facilitam busca no admin e o link do WhatsApp.
- **Descartado:** consulta automática de CEP (ViaCEP) — chamada a serviço externo; fica para a v2.

## 46. Admin de pedidos — Etapa 7
- **Escolha:** itens somente leitura dentro do pedido; status editável na lista; ação "Cancelar pedidos selecionados (devolve o estoque)"; sem botão "Adicionar" (pedido só nasce pelo site, que desconta o estoque); exclusão permitida só para pedidos cancelados ou enviados, e sem a exclusão em massa padrão.
- **Por quê:** apagar um pedido "novo" sumiria com as peças reservadas sem devolvê-las.
- **Atualização (v2 Etapa 5):** o status deixou de ser editável na lista; muda só por ações que respeitam a tabela de transições (decisão 87). Só pedidos **cancelados ou expirados** podem ser apagados.
- **Sem `date_hierarchy`:** ele usa `CONVERT_TZ` do MySQL, que exige as tabelas de fuso horário instaladas no servidor (no MySQL para Windows elas não vêm) e quebraria a lista. O filtro lateral por data funciona sem isso. Os testes pegaram o problema.

## 47. Limite de 5 pedidos por hora por IP — Etapa 8
- **Escolha:** `pedidos/rate_limit.py` conta, no cache do Django, os pedidos criados por IP (`checkout:<IP>`, validade de 1 hora contada a partir do primeiro pedido). No 6º pedido a cliente vê um aviso para chamar no WhatsApp e nada é salvo. Só pedidos criados de verdade contam.
- **Por quê:** o estoque é descontado quando o pedido nasce, então pedidos falsos em massa "esgotariam" a loja. Cinco por hora é bem mais do que uma cliente real faz.
- **Descartado:** campo armadilha (*honeypot*), que só barra robôs simples; CAPTCHA externo (reCAPTCHA/hCaptcha), que envia dados das visitantes a terceiros (LGPD) e exige dependência e chaves; `django-ratelimit`, que seria uma dependência a mais para cerca de 20 linhas.
- **Limitações:** o cache em memória é por processo e zera ao reiniciar (o mesmo vale para a API, decisão 34); atrás de proxy, é preciso configurar o IP real (checklist do README). Nos testes, o cache não é apagado entre um teste e outro, por isso os `setUp` chamam `cache.clear()`.

## 48. HTTPS ligado automaticamente com `DEBUG=False` — Etapa 8
- **Escolha:** `SECURE_HTTPS` usa o padrão `not DEBUG` e liga `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` e `SECURE_HSTS_SECONDS = 3600`. `SECURE_HTTPS=False` desliga, para testar localmente com `DEBUG=False`.
- **Por quê:** produção fica segura sem precisar lembrar de mais uma variável. O HSTS começa curto porque é difícil voltar atrás: o navegador recusa `http://` pelo tempo configurado.
- **Não ligados:** `SECURE_HSTS_INCLUDE_SUBDOMAINS` e `SECURE_HSTS_PRELOAD` (avisos `W005`/`W021` do `check --deploy`). Ainda não sabemos o domínio nem se todos os subdomínios terão HTTPS, e o *preload* é praticamente irreversível.
- **Ajuste junto:** em `get_env_bool`, uma variável vazia (`SECURE_HTTPS=`) agora vale como "não definida" e usa o padrão. Antes, ela virava `False`.

## 49. `STATIC_ROOT = staticfiles/` — Etapa 8
- **Escolha:** pasta gerada pelo `collectstatic`, fora do Git.
- **Por quê:** em produção, com `DEBUG=False`, o Django não serve CSS/JS. O servidor web serve essa pasta, que junta os nossos estáticos com os do admin e do DRF.
- **Descartado:** `WhiteNoise` — prático, mas é uma dependência nova e o deploy está fora do escopo da v1.

## 50. Revisão de segurança da v1 — Etapa 8
- **Verificado e ok:** nenhum `safe`/`mark_safe` nos templates; nenhum SQL cru; `{% csrf_token %}` em todos os formulários POST (com teste usando `enforce_csrf_checks`); API fechada por padrão e só leitura; segredos só no `.env`; upload validado; confirmação do pedido sem número na URL; admin exige login (testado).
- **Corrigido nesta etapa:** limite de pedidos por IP (47), HTTPS em produção (48) e `STATIC_ROOT` (49).
- **Riscos conhecidos, aceitos na v1:**
  - O login do admin não bloqueia após várias senhas erradas. Mitigação: senha forte; na v2, `django-axes`.
  - Os limites (API e pedidos) usam cache em memória, por processo.
  - O e-mail de contato ainda não foi confirmado com a loja.
  - Os pedidos guardam nome, telefone e endereço sem exclusão automática. A página de Privacidade promete guardar os dados só "pelo tempo necessário" para a entrega e as trocas. Por isso, a loja deve apagar no admin, de tempos em tempos, os pedidos enviados ou cancelados antigos, e também quando a cliente pedir.

## 51. Tag `v1.0` e branch `v2` — v2 Etapa 1
- **Escolha:** a v1 concluída foi marcada com a tag anotada `v1.0` (commit `f29a01a`). A v2 é desenvolvida na branch `v2`, criada a partir dela. Tag e branch ficaram só locais (o push fica a critério do Kauan).
- **Por quê:** a tag é um "marcador fixo": dá para voltar exatamente ao código da v1 (`git switch --detach v1.0`) mesmo depois de a v2 mudar tudo. A tag **anotada** (`-a`) guarda autor, data e mensagem, ao contrário da tag "leve", que é só um nome.
- **Descartado:** reaproveitar a branch `feature/loginPagamentos` — o nome cobre só parte do escopo; `v2` deixa claro que a branch é a versão inteira.

## 52. Critérios e pesquisa para escolher o gateway — v2 Etapa 1
- **Critérios, em ordem:** (1) aceitar conta de **pessoa física** (a loja não tem CNPJ); (2) **cartão sem passar pelo nosso servidor** (checkout hospedado ou tokenização no navegador); (3) **Pix dinâmico com webhook** e forma clara de provar que o aviso veio do gateway; (4) sandbox; (5) SDK Python oficial e boa documentação (o projeto é de estudo); (6) taxas.
- **Resultado da pesquisa (nov/2026, documentação oficial e materiais dos gateways; taxas mudam, conferir antes de assinar):**
  - **Mercado Pago:** aceita CPF; Pix 0,99%; cartão ~4,98% (receber na hora) a ~3,99% (30 dias); cartão pelo **Checkout Pro** (página do Mercado Pago, com limite de parcelas configurável na preferência); Pix pela API devolve o QR Code e o "copia e cola"; webhook assinado com **HMAC** (cabeçalho `x-signature` + segredo); SDK Python oficial; sandbox com contas de teste.
  - **Asaas:** aceita CPF; Pix com tarifa fixa por cobrança (R$ 1,99 para pessoa física após os 3 primeiros meses); cartão ~R$ 0,49 + 2,99% a 3,99%, recebimento em 32 dias; webhook autenticado por **token fixo** no cabeçalho; **sem SDK Python oficial** (REST com `requests`); o cartão pela API envia os dados do cartão pelo nosso servidor, então seria preciso usar a fatura hospedada do Asaas.
  - **Efí:** aceita CPF; Pix 1,19%; SDK Python oficial (`efipay`); exige certificado `.p12`/`.pem` nas chamadas e **mTLS** no webhook (há o modo *skip-mTLS* com HMAC na URL), o que complica o desenvolvimento local com túnel; tarifas de cartão não publicadas.
  - **Pagar.me:** abertura de conta exige **CNPJ ou MEI** (Stone). **Eliminado** pelo critério 1.
- **Recomendação:** Mercado Pago. A escolha final está na decisão 53.

> As decisões 53 a 63 são as respostas de negócio da loja às perguntas da v2 Etapa 1. Cada uma diz em que etapa será implementada.

## 53. Gateway: Mercado Pago — v2 Etapa 1 (atualizada na v2 Etapa 7)
- **Escolha:** Mercado Pago. **Cartão pelo Checkout Pro** (a cliente digita o cartão na página do Mercado Pago) e **Pix pela API de pagamentos**, com QR Code dinâmico e "copia e cola" exibidos no nosso site. Começa no sandbox, com contas de teste.
- **Por quê:** aceita pessoa física; o Checkout Pro tira o cartão do nosso servidor; o webhook vem assinado com HMAC; tem SDK Python oficial (decisão 52).
- **Custo aceito:** é o mais caro no cartão. A taxa depende do prazo de recebimento escolhido na conta.
- **Descartado:** Asaas (sem SDK Python, webhook com token fixo, cartão só pela fatura hospedada), Efí (mTLS no webhook) e Pagar.me (exige CNPJ).
- **Implementação:** v2 Etapas 7 (Pix) e 8 (cartão). O SDK `mercadopago` será pedido para aprovação na Etapa 7.
- **Atualização (v2 Etapa 7):** o Pix usa a **Orders API** (`/v1/orders`), não a "API de pagamentos" (`/v1/payments`), que a documentação atual chama de *legacy* (decisão 100). O SDK foi aprovado (decisão 101).

## 54. Frete por tabela de UF, com frete grátis acima de um valor — v2 Etapa 1
- **Escolha:** o frete vem de uma **tabela por região/UF editável no admin**, com **frete grátis acima de um valor** também editável. Nenhum valor fica fixo no código. Os dados iniciais são **exemplos provisórios**, marcados assim no admin e no README, para a loja trocar.
- **Por quê:** com pagamento online, "frete a combinar" não funciona: a cliente precisa pagar o total certo de uma vez. Uma tabela simples resolve sem depender de serviço externo.
- **Descartado na v2:** Melhor Envio/Correios (integração externa, exige peso e medidas de cada peça).
- **Implementação:** v2 Etapa 5. O valor calculado é gravado em `Order.shipping_cost` (campo que já existe desde a v1), para o pedido não mudar se a tabela mudar depois.

## 55. Carrinho sem conta; conta obrigatória só no checkout — v2 Etapa 1
- **Escolha:** a visitante navega e monta o carrinho sem conta. Para finalizar a compra, precisa entrar ou se cadastrar. O carrinho **sobrevive ao login e ao cadastro**.
- **Por quê:** pedir a conta só no fim não afasta quem está só olhando. A conta no checkout liga o pedido a uma dona, o que permite "Meus pedidos" e o controle de acesso contra IDOR.
- **Cuidado técnico:** no login, o Django troca a chave da sessão (`cycle_key`, proteção contra *session fixation*) mas **mantém os dados**, então o carrinho continua lá. Os testes da v2 Etapa 2 vão provar isso.
- **Implementação:** v2 Etapa 2 (login e cadastro mantêm o carrinho) e Etapa 5 (checkout exige conta).

## 56. Política de juros como configuração — v2 Etapa 1
- **Escolha:** a dona ainda não decidiu se a loja absorve os juros ("sem juros") ou se a cliente paga. Por isso a política vira um campo do `StoreSettings`. O valor será perguntado na v2 Etapa 6.
- **Atenção:** no Mercado Pago, o "sem juros" é configurado **na conta do gateway**, não pela API. O que o site mostra precisa bater com essa configuração. Isso vai num aviso no admin e no checklist do README.
- **Implementação:** v2 Etapa 6 (decisão 99): campo `StoreSettings.interest_policy`, padrão "a loja absorve". O valor definitivo continua pendente da dona.

## 57. Até 3 parcelas, parcela mínima de R$ 50 — v2 Etapa 1
- **Escolha:** valores iniciais da regra geral: **até 3x** e **parcela mínima de R$ 50,00**, ambos editáveis no admin (e o máximo pode ser sobrescrito por produto). Exemplo: num carrinho de R$ 120, a parcela mínima permite no máximo 2x (2 × R$ 60).
- **Implementação:** v2 Etapa 6 (`StoreSettings` + função de cálculo, decisão 98). O máximo vai para o Checkout Pro na Etapa 8.

## 58. Pix expira em 30 minutos e devolve o estoque — v2 Etapa 1 (atualizada na v2 Etapa 7)
- **Escolha:** a cobrança Pix expira em **30 minutos** (configurável). Quando expira, o pedido vira "expirado" e o estoque reservado volta.
- **Por quê:** um pedido não pago prende peças que outra cliente poderia comprar. Trinta minutos dá tempo de abrir o app do banco sem segurar o estoque por muito tempo.
- **Implementação:** v2 Etapa 5 (reserva e expiração) e Etapa 7 (data de expiração enviada ao Mercado Pago).
- **Atualização (v2 Etapa 7a):** o Pix expira em `reservation_minutes` (mínimo 30, o menor prazo aceito pelo Mercado Pago) e a reserva do pedido termina no mesmo instante. A expiração do pedido continua pelo mecanismo existente (`expirar_pedidos`).

## 59. CPF não é armazenado — v2 Etapa 1 (atualizada na v2 Etapa 7)
- **Escolha:** o site **não guarda CPF**. No cartão, o Checkout Pro pede o CPF na página do Mercado Pago. No Pix, se o Mercado Pago exigir o CPF do pagador, ele é pedido no momento do pagamento e enviado direto ao gateway, sem ir para o banco de dados nem para os logs.
- **Por quê:** LGPD, princípio da necessidade: o CPF não serve para nada na loja. Dado que não guardamos não pode vazar.
- **Pendente:** confirmar no sandbox se o Pix exige o CPF (v2 Etapa 7). O resultado será informado ao Kauan.
- **Atualização (v2 Etapa 7):** a documentação atual da Orders API não exige CPF no Pix e o código **não envia** CPF (decisão 105). Falta só a confirmação no sandbox.

## 60. Troca e estorno: mínimo legal + estorno total no admin — v2 Etapa 1
- **Regra legal (CDC, art. 49):** na compra pela internet, a cliente pode desistir em até **7 dias corridos após receber** o produto, com devolução **integral** do valor pago (inclusive o frete). O frete de devolução é por conta da loja.
- **Escolha técnica:** **estorno total** pelo admin, feito pela API do Mercado Pago. O pedido vira "estornado" e o estoque volta. Estorno parcial fica fora da v2.
- **A definir pela dona:** prazos além do legal e troca de tamanho. Os textos (Termos de Uso, Política de Trocas) serão **rascunhos marcados para revisão jurídica**, sem texto definitivo inventado.
- **Implementação:** v2 Etapa 4 (textos) e Etapa 8 (estorno).

## 61. Admin só da dona, com 2FA obrigatório — v2 Etapa 1
- **Escolha:** só a dona acessa o admin. Toda conta com acesso ao admin (`is_staff`) precisa de **autenticação em dois fatores** (código de um app autenticador no celular).
- **Por quê:** o admin mostra nome, telefone e endereço das clientes e permite estornar pagamentos. Com 2FA, uma senha vazada sozinha não abre o painel.
- **Grupos de permissão:** com uma única pessoa, um grupo "Loja" ainda é útil para separar a conta do dia a dia (sem ser superusuária) de uma conta técnica. A proposta detalhada vem na v2 Etapa 3.
- **Implementação:** v2 Etapa 3. As dependências `django-otp` e `qrcode` serão pedidas para aprovação nessa etapa.

## 62. E-mails pelo Brevo; console em desenvolvimento — v2 Etapa 1
- **Escolha:** em produção, os e-mails (verificação, redefinição de senha) saem pelo **Brevo**, um serviço de e-mail transacional, via SMTP (o backend SMTP do Django já faz isso, sem dependência nova). Em desenvolvimento, `EMAIL_BACKEND` de **console**: o e-mail aparece no terminal.
- **Por quê:** um serviço transacional entrega melhor (menos spam) que uma conta comum de Gmail, e as credenciais SMTP ficam no `.env`.
- **Pendente:** o e-mail da loja ainda não foi confirmado. O remetente fica numa variável de ambiente.
- **Implementação:** v2 Etapa 3.

## 63. Senhas com Argon2 (hash, não criptografia) — v2 Etapa 1
- **Escolha:** `PASSWORD_HASHERS` com `Argon2PasswordHasher` em primeiro lugar (dependência `argon2-cffi`, aprovada). Os outros hashers do Django ficam na lista só para conseguir ler senhas antigas, como a do superusuário da v1. No próximo login, o Django regrava a senha em Argon2.
- **Hash x criptografia:**
  - **Criptografia** é reversível: quem tem a chave volta ao texto original. Se a chave vazar junto com o banco, todas as senhas vazam.
  - **Hash** é de mão única: não existe chave para "desfazer". No login, o Django calcula o hash da senha digitada e compara com o guardado. Cada senha tem um **sal** (valor aleatório) próprio, então duas pessoas com a mesma senha têm hashes diferentes, e tabelas prontas de hashes não funcionam.
  - Por isso senha **nunca** é criptografada: ninguém, nem a loja, precisa ver a senha original.
- **PBKDF2 x Argon2:** os dois são lentos de propósito (cada tentativa de adivinhação custa caro). O PBKDF2 (padrão do Django) gasta só tempo de CPU, e placas de vídeo testam milhões de senhas em paralelo. O Argon2 também gasta **memória**, o que torna esse ataque em paralelo muito mais caro. É o hasher recomendado pela documentação do Django.
- **Implementação:** v2 Etapa 2.

## 64. Usuário próprio com login por e-mail (`contas.User`) — v2 Etapa 2
- **Escolha:** app `contas/` com `User(AbstractUser)` sem `username`, `email` único como `USERNAME_FIELD` e um `UserManager` que cria contas pelo e-mail. `AUTH_USER_MODEL = 'contas.User'`. Nome e sobrenome são os campos `first_name`/`last_name` do próprio Django.
- **E-mail sempre em minúsculas, pelo código:** `UserManager.normalize_email` (strip + lower) é usado ao criar a conta, no `User.save()` (vale para site, admin e shell) e no `get_by_natural_key`, que o Django chama em **todo login** (site e admin). Não dependemos da *collation* do MySQL, que pode mudar de servidor para servidor. Há teste de login com e-mail em maiúsculas.
- **Por quê agora:** o Django só permite trocar o modelo de usuário sem dor antes de existirem tabelas ligadas a ele. Por isso o banco de desenvolvimento foi **recriado** (só havia dados de exemplo; autorizado pelo Kauan). Receita no README.
- **Descartado:** `AbstractBaseUser` (teríamos de reescrever permissões e campos que o `AbstractUser` já tem); campo único "nome completo" (exigiria reescrever o admin e os métodos de nome do Django).
- **Regra para o código:** nunca importar `django.contrib.auth.models.User`. Use `get_user_model()` (ou `settings.AUTH_USER_MODEL` em `ForeignKey`).

## 65. Login e logout com as views do Django — v2 Etapa 2 (atualizada na v2 Etapa 3)
- **Escolha:** `/conta/entrar/` e `/conta/sair/` usam `LoginView` e `LogoutView` do próprio Django, só configurados em `contas/urls.py`. O cadastro (`/conta/cadastro/`) é uma view em função nossa.
- **Por quê (exceção à decisão 20):** em autenticação, código pronto e revisado por muita gente é mais seguro que código novo. Essas views já validam o `next` contra *open redirect*, trocam o código da sessão no login e, no logout, só aceitam **POST** (um link ou `<img>` em outro site não consegue deslogar a cliente).
- **Open redirect:** o `LoginView` só aceita `next` do próprio site (`url_has_allowed_host_and_scheme`). Um link `?next=https://site-falso` cai na página inicial. Testado.
- **Etapa 3:** o cadastro deixou de fazer login (decisão 73), então perdeu o `next` e a função `get_safe_next_url` foi removida. A redefinição de senha também usa as views prontas do Django (decisão 74).

## 66. Mensagens que não revelam e-mail (login e cadastro) — v2 Etapa 2 (atualizada na v2 Etapa 3)
- **Login:** a mesma frase ("E-mail ou senha incorretos...") para e-mail inexistente e senha errada (`contas/forms.py::LoginForm`). Assim ninguém descobre quem é cliente testando e-mails (**enumeração**). Há teste comparando as duas respostas.
- **Cadastro (Etapa 2):** mostrava "Já existe uma conta com este e-mail", um risco aceito só durante o desenvolvimento.
- **Cadastro (Etapa 3, resolvido):** a resposta é **sempre** a página "Confira seu e-mail", seja o e-mail novo, já verificado ou não verificado. Para isso, o `SignupForm` desliga a checagem de unicidade do `ModelForm` (`validate_unique`), que sozinha avisaria "já existe". O que muda acontece só na caixa de entrada da dona do e-mail (decisão 73). Teste compara as três respostas byte a byte.
- **Também não revelam:** o bloqueio de tentativas (decisão 71) e o "esqueci a senha" (decisão 74).

## 67. Carrinho no login (mantido) e no logout (apagado) — v2 Etapa 2
- **Login e cadastro:** `django.contrib.auth.login()` chama `cycle_key()`: gera um **código de sessão novo**, mas **copia os dados**, então o carrinho continua. O código novo protege contra *session fixation* (alguém que plantou ou conhecia o código antigo não "herda" a conta logada). Testado.
- **Logout:** `logout()` chama `flush()`, que apaga a sessão inteira, inclusive o carrinho. Decisão do Kauan: protege quem usa computador compartilhado.

## 68. Senha com no mínimo 10 caracteres — v2 Etapa 2
- **Escolha:** `MinimumLengthValidator` com `min_length: 10` (o padrão do Django é 8), mais os validadores padrão: parecida com nome/e-mail, lista de senhas comuns, só números. Vale para o site, o admin e o `createsuperuser`.
- **Por quê:** o tamanho é o fator que mais aumenta o número de tentativas necessárias para adivinhar uma senha. Exigir símbolos e maiúsculas, em vez disso, costuma gerar senhas previsíveis ("Senha@123").

## 69. Pendências de produção (sem bloquear o desenvolvimento) — v2 Etapa 2 (reescrita na v2 Etapa 4)
- **Histórico:** na Etapa 2, esta decisão dizia "não publicar antes da v2 Etapa 3", porque o login não bloqueava tentativas e o cadastro revelava e-mails. A Etapa 3 resolveu os dois pontos (decisões 71 e 73).
- **Agora:** o desenvolvimento segue normalmente. A loja só vai ao ar quando **todas** estas pendências estiverem resolvidas:
  1. v2 Etapas 7, 8 e 9 concluídas (pagamento e revisão final de segurança). A Etapa 5 (pedido ligado à conta) foi concluída.
  2. **Agendamento** dos comandos `limpar_dados_antigos` (decisão 79, diário) e `expirar_pedidos` (decisão 88, a cada 5 minutos). Hoje eles são manuais.
  3. **Hospedagem definida** (atualizar os operadores e o prazo de backup na Política, decisão 84).
  4. **Revisão jurídica** da Política de Privacidade e dos Termos de Uso.
  5. **Identificação do fornecedor** (nome, CNPJ, endereço comercial) preenchida pela dona no `.env` (decisão 85).
  6. **Valores reais do frete** (tabela por UF e frete grátis) confirmados pela dona e desmarcados como "PROVISÓRIO" no admin (decisão 90).
- O checklist do README ("Checklist antes de publicar") repete esta lista.

## 70. MySQL com usuário dedicado, sem root — v2 Etapa 3
- **Situação encontrada:** o `.env` conectava como `root` (contrariando a decisão 8) e o usuário `elegancia` não existia.
- **Escolha:** usuário `elegancia@localhost` com `ALL PRIVILEGES` **só** em `elegancia_crista` e em `test_elegancia_crista` (o banco que o Django cria nos testes). A senha foi gerada aleatoriamente (`secrets.token_urlsafe`) e gravada só no `.env`; não aparece no repositório nem em nenhum log.
- **Por quê:** princípio do **menor privilégio**. Se o site for invadido (ex.: uma falha que permita rodar SQL), o estrago fica limitado ao banco da loja. Com `root`, o invasor teria todos os bancos do servidor e poderia criar usuários.
- **No `GRANT`:** `_` é curinga no nome do banco, por isso o comando usa `test\_elegancia\_crista`.
- **Observação:** existe no MySQL local um usuário `Kauan@'%'` (`%` = aceita conexão de qualquer máquina). Não é usado pelo projeto; vale conferir se ele é necessário e se tem senha forte.

## 71. Bloqueio de tentativas com django-axes — v2 Etapa 3
- **Escolha:** `django-axes` (aprovado) com **5 erros → 15 minutos** de bloqueio do **par e-mail + IP** (`AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]`). Login certo zera o contador. Vale para o site e para o admin.
- **Contra o quê:** força bruta (testar milhares de senhas). Com 5 tentativas a cada 15 minutos, adivinhar uma senha de 10+ caracteres fica inviável.
- **Como funciona:** o `AxesStandaloneBackend` vem **antes** do `ModelBackend` em `AUTHENTICATION_BACKENDS`: se o par está bloqueado, ele recusa antes de a senha ser conferida (nem a senha certa entra). As falhas ficam no **banco** (`AccessAttempt`), o que vale para todos os processos (diferente do cache em memória da decisão 47). O `AxesMiddleware` transforma o bloqueio na página `contas/bloqueado.html` com status **429**.
- **Não revela e-mail:** o axes conta o texto digitado, exista a conta ou não, e a página não mostra o e-mail. Teste compara o bloqueio de um e-mail cadastrado com o de um inexistente.
- **Padronização do e-mail (`contas/axes.py`):** sem ela, variar maiúsculas daria 5 tentativas novas a cada variação. **Bug pego pelos testes:** o axes chama essa função com as credenciais em duas formas (chave `email` antes de conferir a senha e `username` ao registrar a falha). A primeira versão lia só `username`: as falhas eram gravadas, a página de bloqueio aparecia, mas **a senha certa ainda entrava**. Corrigido e coberto por teste.
- **Logs:** o axes já mascara e-mail e IP nas mensagens (`********`).
- **Limitações:** (1) um ataque distribuído (muitos IPs contra um e-mail) ganha 5 tentativas por IP; a senha longa e o 2FA do admin cobrem esse caso. (2) Atrás de proxy, é preciso configurar o IP real (checklist do README), senão todas as clientes viram "o mesmo IP".
- **Desbloquear:** `python manage.py axes_reset` (tudo) ou admin → Axes → tentativas de acesso.
- **Descartado:** bloqueio só por e-mail (um atacante travaria a conta de qualquer cliente de propósito); só por IP (clientes atrás do mesmo Wi-Fi seriam bloqueadas juntas).

## 72. Verificação de e-mail com token assinado; checkout só para conta verificada — v2 Etapa 3
- **Model:** `User.email_verified` (começa `False`; o `createsuperuser` e a migration `0002` deixam as contas do admin verificadas) e `User.last_email_sent_at` (limite de frequência, decisão 73).
- **Token (`contas/tokens.py`):** `django.core.signing.dumps({uid, email})` com *salt* próprio, conferido com `max_age` de **24 horas**. A assinatura (com a `SECRET_KEY`) impede falsificar o token; o e-mail dentro dele faz o link morrer se o e-mail da conta mudar. Não há tabela de tokens. O link não é de uso único, mas abrir de novo não faz mal (a conta só continua verificada).
- **Descartado:** tabela de tokens (mais código e limpeza periódica); reaproveitar o gerador de token do "esqueci a senha" (a validade dele é global, `PASSWORD_RESET_TIMEOUT`, e queremos 24 h aqui e 1 h lá).
- **Quem pode o quê:** a conta não verificada **entra** e **monta o carrinho**, mas não finaliza a compra. `contas/decorators.py::verified_email_required` protege `pedidos.views.checkout`: sem login → login com `next`; sem verificar → `/conta/verificacao-pendente/`, com botão "Reenviar o link" (POST + CSRF + limite de frequência).
- **Adiantado da Etapa 5 (decisão do Kauan):** exigir conta no checkout. A ligação `Order → usuário` continua na Etapa 5.

## 73. Cadastro com resposta genérica, sem login, contra pré-sequestro — v2 Etapa 3
- **Escolha:** o cadastro **nunca** faz login e sempre leva à página "Confira seu e-mail" (decisão 66). Por trás (`contas/views.py::register_signup`):
  - e-mail **novo** → cria a conta e envia o link;
  - e-mail de conta **verificada** → não muda nada; envia à dona um **aviso** ("alguém tentou criar conta com seu e-mail") com links de login e de nova senha;
  - e-mail de conta **não verificada** → o cadastro novo **substitui nome e senha** e envia link novo.
- **Pré-sequestro (por que substituir):** sem isso, um atacante poderia cadastrar o e-mail da vítima com uma senha que ele conhece; quando a vítima clicasse no link, a conta ficaria verificada e o atacante entraria nela. Substituindo a senha, a do atacante deixa de valer, e as sessões dele caem (o Django invalida sessões quando a senha muda). Custo aceito: alguém pode trocar a senha de uma conta **ainda não verificada**; a dona legítima recupera com um novo cadastro ou "esqueci a senha".
- **Mail bombing:** no máximo **1 e-mail de segurança a cada 2 minutos por conta** (`contas/emails.py::can_send_email`, guardado no banco). Vale para verificação, aviso e "esqueci a senha". A tela não muda quando o envio é segurado.
- **Tempo de resposta:** no caso "conta verificada", o código calcula um hash Argon2 à toa para demorar parecido com a criação de uma conta. Risco residual aceito: o envio de e-mail ainda pode criar pequenas diferenças de tempo.
- **Corrida:** dois cadastros iguais no mesmo instante → o `unique` do banco recusa um; o `IntegrityError` é tratado como "e-mail existente".
- **Carrinho:** como não há login, a sessão fica intacta; o carrinho continua após o cadastro, a verificação e o login (teste ponta a ponta).

## 74. "Esqueci a senha" com as views do Django e link de 1 hora — v2 Etapa 3
- **Escolha:** `PasswordResetView`, `...DoneView`, `...ConfirmView` e `...CompleteView` do Django, com templates em português, sob `/conta/senha/...`. `PASSWORD_RESET_TIMEOUT = 1 hora` (padrão: 3 dias). `contas/forms.py::ResetForm` só acrescenta o limite de frequência.
- **O que essas views já garantem:** a resposta é a mesma exista o e-mail ou não (teste); o token do link depende do hash da senha atual, então **vale uma vez só**; a página do link troca o token da URL por um marcador (o token não vaza pelo cabeçalho `Referer`); depois da troca, as outras sessões da conta caem.
- **Descartado:** escrever as views à mão (mais código e mais chances de erro em algo sensível).

## 75. 2FA obrigatório no admin com django-otp; recuperação pelo servidor — v2 Etapa 3
- **Escolha:** `LojaAdminSite` (`contas/admin_site.py`) herda o `OTPAdminSite`: o login do admin pede e-mail, senha, **dispositivo** e **código**. Quem não passou pelo 2FA na sessão é tratado como não-staff. A troca do site padrão é feita por `contas/admin_config.py::LojaAdminConfig` (no lugar de `django.contrib.admin` no `INSTALLED_APPS`), então nenhum `admin.py` mudou. O nome continua `admin` (`reverse('admin:...')`).
- **Dispositivos:** `otp_totp` (app autenticador no celular, código de 6 dígitos que muda a cada 30 s) e `otp_static` (**10 códigos de backup**, cada um de uso único). O `django-otp` exige **escolher o dispositivo** na tela de login: testar o código em todos registraria falhas nos outros. Ele também atrasa cada nova tentativa depois de códigos errados.
- **Primeiro acesso e recuperação:** como o próprio login do admin exige o código, o celular é cadastrado **no servidor**: `python manage.py configurar_2fa <email>` mostra o QR Code no terminal (é para isso que serve o `qrcode`) e os 10 códigos de backup, uma única vez. Celular perdido: entrar com um código de backup; perdeu também os códigos: quem tem acesso ao servidor roda `configurar_2fa <email> --redefinir`, que apaga e recria tudo. O QR e a URL `otpauth://` contêm a chave secreta e não devem ser fotografados, colados em conversas ou salvos em log.
- **Só para o admin:** clientes não usam 2FA (decisão 61).
- **`colorama` no `requirements.txt`:** não foi escolhido por nós; é dependência do `qrcode`, que o declara só para Windows (`colorama ; sys_platform == "win32"`), para o terminal do Windows desenhar o QR Code. Entrou no arquivo pelo `pip freeze`. Em Linux/macOS não é necessário (instalar não faz mal; é uma biblioteca pequena, sem dependências).
- **Pequena pendência visual:** algumas mensagens da tela de 2FA do `django-otp` aparecem em inglês (ex.: "Please select a device."), porque a tradução da biblioteca não as cobre.

## 76. Grupo "Loja" criado por comando — v2 Etapa 3
- **Escolha:** `python manage.py criar_grupos` cria (ou atualiza) o grupo **"Loja"** com 17 permissões: produtos, variações e imagens (todas as ações), categorias (só ver), pedidos (ver, editar, apagar; o admin já limita o que pode ser apagado, decisão 46) e itens de pedido (só ver).
- **Fora do grupo, de propósito:** contas de clientes, grupos e permissões, dispositivos 2FA e registros do axes. Sugestão de uso: a dona trabalha no dia a dia com uma conta `is_staff` do grupo "Loja" (com 2FA), e a superusuária fica para administrar contas e segurança.
- **Por que comando e não migration:** as permissões do Django só são criadas depois das migrations (sinal `post_migrate`); numa migration de dados elas podem não existir ainda. O comando pode rodar quantas vezes quiser (`get_or_create` + `permissions.set`).

## 77. Aceite versionado no cadastro (model `Consent`) — v2 Etapa 4
- **Escolha:** caixa "Li e aceito os Termos de Uso e a Política de Privacidade", **desmarcada por padrão** e obrigatória no cadastro (`SignupForm.accept_terms`). Cada aceite vira uma linha em `contas_consent`: usuária, versão da Política, versão dos Termos e data/hora (`accepted_at`). As versões ficam em `contas/legal.py` (`PRIVACY_POLICY_VERSION`, `TERMS_VERSION`) e aparecem no topo das páginas.
- **Por quê:** a LGPD põe na loja o ônus de provar o aceite (art. 8º, § 2º); guardar a **versão** permite provar o que foi aceito mesmo depois de o texto mudar. Caixa pré-marcada não vale como manifestação livre (art. 5º, XII).
- **Nuance da base legal:** os dados da conta são tratados para **executar o contrato** (art. 7º, V), não "por consentimento". A caixa registra ciência e aceite de textos versionados. Se um dia houver tratamento baseado em consentimento (ex.: newsletter), ele terá caixa própria e separada.
- **Onde:** `contas/models.py` (`Consent`), `contas/views.py` (`record_consent`, chamada no cadastro novo e no cadastro refeito de conta não verificada; a conta verificada não muda, para a resposta continuar idêntica, decisão 73). Admin **somente leitura** (`ConsentAdmin`); por isso o admin também não apaga uma conta que tenha aceite (o caminho é anonimizar, decisão 78).
- **Descartado:** guardar IP/navegador no aceite (não é necessário para a prova; minimização); duas caixas separadas (mais atrito, mesmo efeito).

## 78. Excluir conta = anonimizar — v2 Etapa 4
- **Escolha:** "Excluir minha conta" (com senha atual + caixa de confirmação) chama `anonymize_user` (`contas/privacy.py`): e-mail vira `anonimizada-<id>@anonimizado.invalid`, nome e sobrenome vazios, senha inutilizável, conta inativa, `anonymized_at` preenchido. Também apaga os registros do axes daquele e-mail, os dispositivos 2FA e troca o e-mail no histórico do admin (`django_admin_log`) por "Conta anonimizada". Tudo dentro de `transaction.atomic()`.
- **Por quê:** a linha da conta continua existindo para que os pedidos (ligados à conta na Etapa 5) sigam guardados pelo prazo da decisão 79, sem identificar a cliente (dado anonimizado não é dado pessoal, art. 12). A senha inutilizável muda o hash, e o Django derruba **todas** as sessões abertas da conta.
- **Segurança:** pede a senha (protege contra quem acha o computador com a conta aberta); POST com CSRF; contas `is_staff` não se excluem pelo site (a dona trancaria o admin).
- **Pendência para a Etapa 5 (resolvida):** a exclusão é bloqueada enquanto houver pedido **ativo** (decisão 92), e a dona também pode anonimizar pelo admin (decisão 94).
- **Descartado:** apagar a linha (`delete()`): os pedidos perderiam o vínculo ou seriam apagados junto, contra a guarda legal.

## 79. Prazos de retenção e comando de limpeza (manual por enquanto) — v2 Etapa 4
- **Escolha:** prazos em `contas/legal.py`, aplicados por `python manage.py limpar_dados_antigos` (com `--dry-run`). A saída mostra só quantidades, nunca dados pessoais.

| Dado | Prazo | Fundamento |
|---|---|---|
| Conta | enquanto existir; exclusão = anonimização imediata | LGPD arts. 15, 16 e 18, VI |
| Nome, telefone e endereço do pedido | 5 anos do pedido, depois anonimizados (ficam cidade, UF, itens e valores) | LGPD art. 16, I, e art. 7º, VI; CDC art. 27 (5 anos para pedir reparação por fato do produto). **Atenção:** o art. 27 conta do *conhecimento do dano*, então "5 anos do pedido" é uma referência, não um prazo exato. Revisão jurídica. Com CNPJ, prazos fiscais (CTN arts. 173 e 195) podem se somar. |
| Conta nunca verificada | 30 dias, depois apagada | Sem prazo legal; minimização (art. 6º, III). Não pode ter pedido (decisão 72). |
| Tentativas de login (axes) | 30 dias | Sem prazo legal; interesse legítimo de segurança (art. 7º, IX). |
| Histórico de logins bem-sucedidos | não guardado | Decisão 83. |
| Sessões | 14 dias (`SESSION_COOKIE_AGE`) + `clearsessions` | Configuração técnica. |

- **Honestidade:** hoje o comando é **manual**; a Política diz isso. O agendamento (ex.: diário) depende da hospedagem e é **pré-requisito de produção** (decisão 69).
- **Fontes:** [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm), [CDC](https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm), [Marco Civil da Internet](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm), [CTN](https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm).
- **Descartado:** guardar pedidos para sempre (sem base legal depois do prazo).

## 80. Exportação dos dados em JSON — v2 Etapa 4
- **Escolha:** botão "Baixar meus dados" (POST com CSRF) devolve `meus-dados-elegancia-crista.json` com a conta e os aceites (`export_user_data`). Sem o hash da senha.
- **Por quê:** atende acesso e portabilidade (art. 18, II e V) num formato aberto, legível por pessoas e programas, sem dependência nova. POST impede que outro site dispare o download com a sessão da cliente.
- **Etapa 5 (feito):** os pedidos da conta entram na exportação (decisão 93).
- **Descartado:** PDF (precisaria de biblioteca nova); CSV (ruim para dados aninhados, como a lista de aceites).

## 81. Troca de e-mail verificada no novo endereço — v2 Etapa 4
- **Escolha:** a cliente informa o novo e-mail + senha atual; enviamos ao **novo** endereço um link assinado (salt próprio, 24 h, `contas/tokens.py`). O e-mail só muda quando o link é aberto; depois, o endereço **antigo** recebe um aviso.
- **Contra enumeração:** se o novo e-mail já tem conta, a tela mostra a mesma mensagem e o dono daquele e-mail recebe o aviso de "conta existente" (sem link de troca). O intervalo mínimo entre e-mails (decisão 74) vale para as duas contas.
- **Segurança:** o token leva o e-mail atual: link antigo ou já usado não vale. Se outro cadastro ocupar o e-mail antes do clique, o `unique` do banco recusa e nada muda.
- **Descartado:** trocar na hora (permitiria pôr na conta um e-mail de outra pessoa); só pelo atendimento (a correção dependeria de trabalho manual da dona).

## 82. Aviso de cookies apenas informativo — v2 Etapa 4
- **Escolha:** faixa no pé da tela explicando que só há cookies estritamente necessários (`sessionid`, `csrftoken`, `messages`), com link para a Política e botão "Entendi". A dispensa fica no `localStorage` (não é cookie e não vai ao servidor). Sem JS, a faixa não aparece; a Política tem a tabela completa.
- **Por quê:** a ANPD orienta que cookies estritamente necessários não dependem de consentimento ([Guia Orientativo: Cookies e proteção de dados pessoais, 2022](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/processo-guia-orientativo-cookies-e-protecao-de-dados-pessoais.pdf)). Botão "recusar" seria enganoso: recusar quebraria o carrinho e o login. Nenhum cookie de rastreamento ou análise foi adicionado.
- **Pendência para as Etapas 7 e 8:** reavaliar o aviso quando o Mercado Pago entrar (o Checkout Pro roda no domínio dele, mas qualquer script do gateway nas nossas páginas pode criar cookies de terceiros).
- **Descartado:** cookie para guardar a dispensa (seria mais um cookie); biblioteca de "consent banner" (dependência para um caso que não precisa de consentimento).

## 83. Histórico de login do axes desligado; auditoria de logs — v2 Etapa 4
- **Escolha:** `AXES_DISABLE_ACCESS_LOG = True` (o axes deixa de gravar e-mail, IP e navegador de cada login **bem-sucedido**) e `AXES_SENSITIVE_PARAMETERS` explícito (e-mail e IP aparecem como `********` nos avisos do axes). O comando de limpeza esvazia o histórico antigo.
- **Por quê:** o bloqueio de tentativas não depende do histórico; guardar sem necessidade contraria a minimização (art. 6º, III). O Marco Civil (art. 15) só obriga a guarda de registros de acesso por 6 meses a provedor constituído como **pessoa jurídica**; a loja não tem CNPJ. **Rever quando houver CNPJ.**
- **Auditoria de logs (o que grava o quê):**
  - O projeto não tem `LOGGING`, `logger` nem `print` próprios.
  - Django com `DEBUG=False`: erros 500 iriam para `mail_admins`, mas `ADMINS` está vazio, então nada é enviado. Com `DEBUG=True`, o `runserver` imprime só método, caminho e status (os links de verificação/redefinição aparecem no caminho; só em desenvolvimento).
  - Backend de e-mail de console (desenvolvimento) imprime os e-mails com nome e links, de propósito (decisão 62). Em produção é SMTP.
  - axes: avisos mascarados; a senha nunca é registrada.
  - `limpar_dados_antigos`: só números.
  - Dados de pagamento: ainda não existem (as Etapas 7 e 8 mantêm a regra "logs sem dados de pagamento").

## 84. Política de Privacidade e Termos de Uso como rascunho versionado — v2 Etapa 4
- **Escolha:** `templates/loja/privacy.html` (reescrita) e `templates/loja/terms.html` (nova, rota `/termos/`), em linguagem simples, com faixa **"RASCUNHO — pendente de revisão jurídica"** e versão no topo. A Política se baseia no inventário real de dados (README, "Dados pessoais que o site guarda").
- **Operadores citados:** Mercado Pago (decisão 53), Brevo (decisão 62) e **hospedagem: PROVISÓRIO, empresa não definida** (nenhum nome é citado até a escolha). Entrega: "transportadora ou Correios", genérico.
- **Backups:** parágrafo explicando que dado apagado pode ficar em cópia antiga até ela expirar, com prazo **PROVISÓRIO de 30 dias** (proposta técnica, sem fundamento legal específico) até a hospedagem ser definida.
- **Contato de privacidade:** `elegancia.crist@gmail.com`, confirmado pela dona. Prazo de resposta de 15 dias, do art. 19, II.
- **Descartado:** gerador automático de política (texto genérico, não bate com o que o site faz).

## 85. Loja sem CNPJ por enquanto; identificação do fornecedor pronta para o CNPJ — v2 Etapa 4
- **Contexto:** o site é um projeto de portfólio do Kauan para uma loja micro, que ainda não tem CNPJ; a dona pretende abrir CNPJ no futuro. Seguir sem CNPJ por enquanto é uma **decisão consciente** do Kauan e da dona.
- **O que a lei pede:** o Decreto 7.962/2013, art. 2º, I e II ([texto](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7962.htm)), pede no site o nome e o CPF ou CNPJ do fornecedor e o endereço físico e eletrônico.
- **Escolha:** três variáveis de ambiente, `STORE_LEGAL_NAME`, `STORE_CNPJ` e `STORE_ADDRESS`, lidas no `settings.py` e entregues aos templates por `loja.context_processors.store_info`. Vazias: Política e Termos mostram "[A DEFINIR PELA DONA]" e o rodapé não mostra nada. Preenchidas: aparecem na Política, nos Termos e no rodapé de todas as páginas, **sem mexer em template ou código**.
- **Cuidados:** só existe campo de **CNPJ** (não de CPF) e o endereço é o **comercial**: o site não deve exibir CPF nem endereço residencial da dona. Nenhum dado pessoal real dela entra no repositório (o `.env` fica fora do Git).
- **Pendência:** preencher quando o CNPJ existir (decisão 69, item 5).
- **Descartado:** constantes em `contas/legal.py` (preencher exigiria commit e colocaria dados no Git); model editável no admin (mais código para três textos que mudam uma vez).

## 86. Pedido ligado à conta; pedidos da v1 ficam sem dona — v2 Etapa 5
- **Escolha:** `Order.user` (`ForeignKey` para `AUTH_USER_MODEL`, `related_name='orders'`) com `on_delete=PROTECT` e `null=True`. Todo pedido novo recebe a conta em `create_order(cart, form, user)`.
- **PROTECT:** o banco recusa apagar uma conta que tem pedido. A exclusão pedida pela cliente é anonimização (decisão 78), que mantém a linha. Por isso o pedido segue ligado à conta pelo prazo da decisão 79.
- **Migração dos pedidos existentes:** ficam com `user = NULL`. Descartado "adivinhar" a dona pelo nome ou telefone: um palpite errado mostraria nome e endereço de uma cliente para outra (vazamento). Eles aparecem no admin e não aparecem em nenhum "Meus pedidos".
- **Migrations separadas:** `pedidos/0002` (estrutura) e `0003`/`0004` (dados), cada uma com função de volta. Testado ida e volta no banco de desenvolvimento.
- **Cuidado:** no MySQL, mudanças de estrutura não são desfeitas se a migration falhar no meio. Antes do `migrate`, faça backup com `mysqldump` (README).

## 87. Seis status e uma tabela de transições no model — v2 Etapa 5
- **Status:** `aguardando_pagamento`, `pago`, `expirado`, `cancelado`, `enviado`, `estornado`. Os da v1 foram migrados: `novo → aguardando_pagamento` (sem prazo) e `confirmado → pago`.
- **Tabela (`Order.ALLOWED_TRANSITIONS`):**
  - aguardando → pago / expirado / cancelado;
  - pago → enviado / estornado;
  - enviado → estornado;
  - expirado, cancelado e estornado são finais.
- **Estoque (`STOCK_RETURNING_TRANSITIONS`):** volta em aguardando → expirado, aguardando → cancelado e pago → estornado. **Não** volta no estorno de pedido enviado: a peça está com a cliente e só entra no estoque quando chegar e for conferida (pergunta à dona).
- **Onde:** no `Order.save()`, como na decisão 43. Ele lê o status do banco **com trava**, recusa transição proibida (`ValidationError`), preenche `shipped_at` e devolve o estoque. Vale para o admin, o comando, o shell e o webhook das Etapas 7 e 8.
- **"Pago" nunca à mão:** no admin, o status é só leitura e muda por duas ações: "Marcar como enviado" (só de pago) e "Cancelar" (só de aguardando). Não existe ação "marcar como pago": quem confirma pagamento é o gateway (regra inegociável do CLAUDE.md).
- **Descartado:** biblioteca de máquina de estados (`django-fsm`), mais uma dependência para um dicionário de 6 linhas.

## 88. Reserva de estoque com prazo: comando + expiração "preguiçosa" — v2 Etapa 5
- **Reserva:** a baixa do estoque no checkout (decisão 42) já é a reserva. `Order.expires_at = agora + StoreSettings.reservation_minutes` (30 min, decisão 58). Pedidos sem prazo (os da v1) nunca expiram sozinhos.
- **Expiração (`pedidos/reservations.py`):** `expire_order` abre uma transação, busca o pedido **com trava** e confere de novo "aguardando **e** vencido" antes de marcar "expirado". O `save()` devolve o estoque.
- **Quem chama:**
  1. o comando `python manage.py expirar_pedidos [--dry-run]`, para qualquer agendador (cron, Agendador de Tarefas do Windows, scheduler da hospedagem), sugerido a cada 5 minutos;
  2. a **expiração preguiçosa**: `expire_overdue_orders()` no começo da página do produto, de "adicionar ao carrinho", do checkout e de "Meus pedidos". No caso comum é uma consulta só, pelo índice `(status, expires_at)`.
- **Por que os dois:** a hospedagem não foi escolhida. Sem agendador, a peça vencida volta assim que alguém tenta comprá-la. Com agendador, o estoque também fica certo no catálogo e na API.
- **Concorrência:**
  - (a) A trava na linha do pedido faz o 2º processo esperar e reler: comando + página, ou expiração + pagamento, nunca devolvem o estoque duas vezes (teste da "corrida").
  - (b) A devolução usa `F('stock') + qtd`.
  - (c) As variações são travadas e atualizadas **em ordem de id** no checkout e na devolução, para evitar *deadlock* (dois processos esperando um pelo outro).
- **Pendência para a Etapa 7:** pagamento que chega depois de o pedido expirar. O Pix será criado no Mercado Pago com o mesmo `expires_at`, e o caso residual vira estorno.
  - **v2 Etapa 7a:** a validade do Pix e a reserva terminam juntas; o timestamp local parte do início da chamada ao gateway para não passar da validade da cobrança. O estorno de confirmação tardia fica na Etapa 7b.
- **Descartado:** Celery/fila de tarefas (infraestrutura demais para uma loja pequena); expirar só pela página (sem garantia de que alguém abra).

## 89. `StoreSettings`: configuração única da loja no admin — v2 Etapa 5 (atualizada na v2 Etapa 7)
- **Escolha:** `loja.StoreSettings`, uma linha só (o `save()` força `id=1`; `StoreSettings.load()` lê ou cria).
  - Campos desta etapa: `reservation_minutes` (5 a 1440) e `free_shipping_threshold` (com marca de provisório).
  - **v2 Etapa 7:** `reservation_minutes` passa a ir de **30** a 1440 (decisão 103). A migration `loja/0006` sobe para 30 qualquer valor menor.
  - A v2 Etapa 6 acrescenta o parcelamento aqui.
- **Admin:** sem "adicionar" quando a linha existe e sem "excluir". O grupo "Loja" pode ver e editar.
- **Por que no app `loja`:** são regras da loja inteira (frete, reserva, parcelas), não de um app só.
- **Descartado:** valores no `settings.py`/`.env` (a dona dependeria de programador para mudar); biblioteca de "settings no admin" (dependência para um model de 3 campos).

## 90. Frete por UF com frete grátis, valores provisórios — v2 Etapa 5
- **Escolha:** `pedidos.ShippingRate` (UF única, região, preço, `is_provisional`), editável na lista do admin.
  - UF sem linha = "ainda não entregamos neste estado": o checkout recusa, com mensagem no campo UF.
  - Frete grátis quando a **soma dos produtos ≥ limite** (`StoreSettings`).
- **Valores iniciais (PROVISÓRIOS, migration `0004`):** Sudeste R$ 19,90 · Sul R$ 24,90 · Centro-Oeste R$ 29,90 · Nordeste R$ 34,90 · Norte R$ 39,90; grátis a partir de R$ 299,00. O admin mostra um aviso enquanto houver UF provisória.
- **Cálculo (`pedidos/shipping.py::calculate_shipping`):** dentro da transação do checkout, com os preços das variações travadas. O resultado fica em `Order.shipping_cost`: mudar a tabela depois não muda o pedido.
- **Tela:**
  - A tabela vai para a página por `json_script`, e o JavaScript mostra frete e total ao escolher a UF, somando em **centavos inteiros** (sem erro de `float`).
  - Sem JS, um `<details>` mostra a tabela.
  - O valor cobrado é sempre o do servidor. A cliente vê o total final no pedido **antes** de pagar (Etapas 7 e 8).
- **Descartado:** tabela por região (com 27 linhas, a dona pode dar preço diferente a um estado sem mudar o código); consulta ao servidor a cada troca de UF (mais uma rota para o mesmo resultado).

## 91. "Meus pedidos" filtrado pela dona; detalhe substitui a confirmação — v2 Etapa 5
- **Escolha:** `/pedido/meus-pedidos/` e `/pedido/meus-pedidos/<id>/`, com `@login_required`.
  - A consulta parte **sempre** de `request.user.orders`.
  - O detalhe usa `get_object_or_404(request.user.orders, pk=pk)`.
- **IDOR:** pedido de outra cliente, pedido sem dona e número inexistente dão a **mesma** resposta: 404. Um 403 confirmaria que o número existe. Testado.
- **Depois do checkout:** a cliente vai direto ao detalhe do pedido (status, "reservado até HH:MM", itens, frete, total, entrega). A página `/pedido/confirmado/` e a chave de sessão `last_order_id` (decisão 44) saíram: o filtro pela dona faz o mesmo papel em qualquer aparelho.
- **WhatsApp:** o botão "Falar com a loja sobre este pedido" leva só o **número** do pedido na mensagem (a v1 levava nome, telefone e endereço na URL). Menos dado pessoal circulando; a loja vê o resto no admin.

## 92. Pedido "ativo" bloqueia a exclusão da conta — v2 Etapa 5
- **Definição (`pedidos/models.py::active_orders`):**
  - **Ativos:** aguardando pagamento, pago, ou **enviado há menos de 30 dias** (`SHIPPED_ACTIVE_PERIOD`).
  - **Não ativos:** expirado, cancelado, estornado, enviado há mais de 30 dias.
- **Por quê:** enquanto o pedido está em curso, a loja precisa da conta para entregar, devolver o dinheiro (desistência do CDC, 7 dias **após o recebimento**) ou falar com a cliente. Os 30 dias depois do envio cobrem transporte + prazo de desistência. **Pergunta à dona.**
- **Onde:** `contas/views.py::account_delete`.
  - Bloqueia no GET (não mostra o formulário) **e** no POST (contra quem envia o formulário direto), com mensagem e os números dos pedidos.
  - A Política de Privacidade explica a regra (versão `2026-11-22.2`).
- **Defesa extra:** `delete_old_unverified_accounts` ignora contas com pedido (além do `PROTECT`).

## 93. Exportação JSON com os pedidos — v2 Etapa 5
- **Escolha:** `export_user_data` ganhou `"pedidos"`: número, data, status, itens, produtos, frete, total e dados de entrega.
- **Detalhes:** dinheiro como texto (`"319.90"`, decisão 33). Só entra `user.orders`; um teste garante que o pedido de outra conta não aparece.

## 94. Ação "Anonimizar contas" no admin — v2 Etapa 5
- **Escolha:** ação em `contas/admin.py::UserAdmin`, para atender pedidos de exclusão que chegam por e-mail ou WhatsApp. Reaproveita `anonymize_user` (decisão 78).
- **Confirmação em 2 passos**, como o "excluir selecionados" do Django:
  1. O 1º POST mostra `templates/admin/contas/anonymize_confirmation.html` ("não dá para desfazer", lista do que será feito e do que será pulado) e não muda nada.
  2. O 2º POST, com `confirm=yes`, executa. As regras são conferidas **de novo** nesse passo.
- **Pula (e diz por quê):** contas da equipe (`is_staff`/`is_superuser`), contas já anonimizadas e contas com pedido ativo (decisão 92).
- **Permissão:** `permissions=['change']`. Só quem edita contas (a superusuária) vê a ação; o grupo "Loja" recebe 403. Testado.
- **Atenção à dona:** antes de anonimizar a pedido de alguém por e-mail ou WhatsApp, confirmar que o pedido veio **do e-mail da conta**. Senão, qualquer pessoa poderia pedir a exclusão da conta de outra.

## 95. Status "entregue"; o prazo de pedido ativo conta da entrega — v2 Etapa 5b
- **Escolha:** novo status `entregue` (`Order.Status.DELIVERED`) e campo `delivered_at`, preenchido no `save()` como o `shipped_at`. Ação "Marcar como entregue (só pedidos enviados)" no admin. **Atualiza a decisão 87.**
- **Tabela final de transições:**

| De \ Para | pago | expirado | cancelado | enviado | entregue | estornado |
|---|---|---|---|---|---|---|
| aguardando pagamento | sim | sim | sim | | | |
| pago | | | | sim | | sim |
| enviado | | | | | sim | sim |
| entregue | | | | | | sim |
| expirado, cancelado, estornado | finais | | | | | |

  Não existe "pago → entregue": a peça passa por "enviado". "Entregue → estornado" cobre a desistência do CDC (art. 49), que corre do **recebimento**.
- **Pedido ativo (atualiza a decisão 92):** aguardando, pago, **enviado (sem limite de tempo)** ou **entregue há menos de 30 dias** (`DELIVERED_ACTIVE_PERIOD`, antes `SHIPPED_ACTIVE_PERIOD`). Os 30 dias foram **aprovados como padrão pelo Kauan**; a dona pode mudar (constante em `pedidos/models.py`).
- **Consequência aceita:** um pedido "enviado" que a dona esquecer de marcar como entregue bloqueia a exclusão da conta indefinidamente. Preferimos bloquear a anonimizar uma conta com entrega pendente. O filtro por status do admin ajuda a achar esses pedidos.
- **Migração:** pedidos já "enviados" ficam com `delivered_at` vazio e continuam ativos (lado seguro). Sem migration de dados.
- **Política de Privacidade:** a frase da exclusão passou a falar em "entrega", e `PRIVACY_POLICY_VERSION` subiu para `2026-11-22.3`.
- **PENDÊNCIA DE PRODUÇÃO (antes de ter clientes reais): não existe reaceite.** O aceite grava a versão da Política **só no cadastro** (`contas/views.py`, model `Consent`). Subir a versão **não** afeta as contas existentes: elas continuam com a versão antiga gravada, não veem aviso e não são chamadas a aceitar a nova. Hoje isso é inofensivo (não há clientes reais, e a mudança só detalha uma regra). Mas, quando houver clientes, uma mudança **material** na Política exigirá avisar e/ou pedir novo aceite (LGPD art. 8º, §6º). Não implementado agora, de propósito.

## 96. A cliente cancela sozinha o pedido aguardando pagamento — v2 Etapa 5b
- **Escolha:** `POST /pedido/meus-pedidos/<id>/cancelar/` (`pedidos/views.py::cancel_order`), com botão em "Meus pedidos" e no detalhe, e confirmação por `data-confirmar` (JavaScript, melhora progressiva).
- **Segurança:**
  - Só POST (`@require_POST`; GET dá 405) e CSRF do Django: um link ou robô não cancela nada.
  - `@login_required`, e a busca parte de `request.user.orders`: pedido de outra conta, sem dona ou inexistente dá 404 (contra IDOR, como na decisão 91).
  - Só cancela se o status é "aguardando pagamento".
- **Concorrência:** `reservations.py::cancel_order_by_customer` tem o mesmo molde de `expire_order`: `transaction.atomic()` + `select_for_update()` na linha do pedido, relendo o status dentro da trava. Cancelar, expirar e (Etapa 7) pagar ao mesmo tempo: o segundo a chegar não acha um pedido "aguardando" e não faz nada. O estoque volta uma só vez, pelo `Order.save()`.
- **Antes de cancelar**, a view expira os pedidos vencidos da conta, para a mensagem ficar certa.
- **Pendência para a Etapa 7:** se já existir um Pix gerado, o cancelamento deve também cancelar a cobrança no Mercado Pago, e um pagamento que chegue depois para pedido cancelado vira estorno.
- **Aprovado como padrão** pelo Kauan; a dona pode mudar.
- **Descartado:** cancelar por GET (inseguro); botão sem confirmação (clique acidental sem volta: a cliente teria de refazer o pedido).

## 97. Estorno de peça já enviada: estoque volta só por ação manual da dona — v2 Etapa 5b
- **Escolha:** `enviado → estornado` e `entregue → estornado` continuam **sem** devolver estoque sozinhos (decisão 87). Nova ação do admin **"Devolver peças ao estoque"**, para a dona usar depois de receber a peça de volta e conferir. **Atualiza a decisão 87.**
- **Registro:** campo `Order.stock_restored_at` (preenchido por qualquer devolução, automática ou manual) e uma entrada no **histórico do pedido** do admin (`log_change`: quem, quando e o quê).
- **Trava:** `Order.restore_stock_manually()` roda em `transaction.atomic()`, trava o pedido com `select_for_update()` e confere de novo: estornado, já foi enviado (`shipped_at`) e `stock_restored_at` vazio. Clique duplo, ou duas pessoas ao mesmo tempo, não devolvem em dobro. Pedido estornado quando estava só "pago" não é elegível (o estoque já voltou sozinho).
- **Limitação (pergunta à dona):** a ação devolve **todas** as peças do pedido. **Devolução parcial** (só uma das peças) ainda não existe: hoje a dona teria de ajustar o estoque à mão na variação. Precisamos saber se isso acontece na loja.
- **Devolução parcial — decisão da dona:** por enquanto é **ajuste manual do estoque** na variação (admin → produto), sem ação própria. Se acontecer com frequência, vira uma ação por item numa etapa futura.
- **O que os testes NÃO provam:** rodam no MySQL (`test_elegancia_crista`), mas as requisições vão uma depois da outra, na mesma conexão e na transação do `TestCase`; ali o `select_for_update()` nunca espera ninguém. Provam a lógica (clique duplo, status já mudado), não a corrida real de duas requisições simultâneas. Isso vale para as decisões 88, 96 e 97 (a de 88 tem teste de "corrida" simulada, não de concorrência real).
- **Permissão:** sem model novo, então o grupo "Loja" (que edita pedidos) já pode usar a ação.
- **Descartado:** devolver o estoque no momento do estorno (a peça ainda está com a cliente e poderia ser vendida de novo sem existir na loja); campo de texto livre para a dona "registrar" (o histórico do admin já grava quem e quando).

## 98. Parcelamento: regra geral na loja, limite opcional por produto, o menor vale no carrinho — v2 Etapa 6
- **Escolha:**
  - **Regra geral** no `StoreSettings` (sem tabela nova): `max_installments` (padrão **3**, de 1 a 12) e `min_installment_value` (padrão **R$ 50,00**, mínimo aceito R$ 5,00). Os dois são editáveis no admin (decisão 57).
  - **Por produto:** `Product.max_installments`, opcional (de 1 a 12). **Vazio** = vale a regra geral. **Preenchido** = **substitui** a regra geral, para mais ou para menos (ex.: um conjunto de R$ 400 pode ter 6x mesmo com a regra geral em 3x).
  - **Carrinho com vários produtos:** cada item tem o seu limite (o do produto, ou o geral se estiver vazio) e vale o **MENOR** entre os itens (`pedidos/installments.py::get_installment_limit`). Sobre esse limite ainda se aplica a parcela mínima: `número máximo = total ÷ parcela mínima` (divisão inteira, nunca menos que 1). Exemplo: carrinho de R$ 120, limite 3, mínimo R$ 50 → **2x** (2 × R$ 60). Um produto com limite próprio de 10x num carrinho de R$ 120 também fica em 2x: **a parcela mínima vence**.
  - **No admin:** a coluna "máximo de parcelas" é **editável na lista de produtos** (`list_editable`), então a dona muda vários produtos de uma vez; e a ação **"Voltar à regra geral de parcelas da loja"** limpa o campo dos produtos marcados. Os validadores do model (1 a 12) valem também na edição em lista (testado com 0 e 13).
- **Onde aparece (informativo):** página do produto ("ou em até Nx no cartão") e checkout (Pix à vista; cartão em até Nx). Nada de "sem juros" nem valor final prometido: os valores são **estimativa**, até a Etapa 8 confirmar no sandbox. Não aparece no carrinho (o frete ainda não é conhecido ali).
- **Permissões:** nenhum model novo, então o grupo "Loja" (que edita `Product` e `StoreSettings`) já pode mexer nos campos novos, e `criar_grupos` não mudou. Um teste confirma.
- **Descartado:** nova tabela de configuração (o `StoreSettings` já existe); ação do admin com tela intermediária para "definir limite X" (a edição em lista resolve com menos código; pode entrar se a dona pedir); o limite por produto só poder diminuir (a dona quer poder oferecer mais parcelas num produto caro).

## 99. Cálculo das parcelas, política de juros e alinhamento com o Mercado Pago — v2 Etapa 6
- **Função única:** `pedidos/installments.py::calculate_installments(total, max_installments=None)` devolve a lista de `InstallmentOption(number, amounts, total)`, de 1x até o maior número permitido. Sempre existe 1x. `total` precisa ser `Decimal` positivo (`float` dá `TypeError`).
- **Centavos:** a parcela comum é `total ÷ n` **truncada** em centavos (`ROUND_DOWN`) e a **sobra vai para a primeira parcela**, então a soma é **exatamente** o total. Ex.: R$ 100,00 em 3x = 33,34 + 33,33 + 33,33. Arredondar cada parcela poderia dar R$ 99,99 ou R$ 100,01. Testado em vários totais e de 1x a 12x.
- **Política de juros** (`StoreSettings.interest_policy`, decisão 56): `no_interest` (a loja absorve, **padrão**, o mais simples) ou `customer_pays`. O site **não calcula juros de gateway**: com "cliente paga" mostra só o número de parcelas, sem valor por parcela (o site não sabe a taxa). Valor definitivo: pergunta à dona.
- **Alinhamento com o Mercado Pago** (documentação consultada em 24/11/2026):
  - Na preferência do Checkout Pro, `payment_methods.installments` é o **número máximo** de parcelas oferecidas. Existe também `default_installments` (parcela pré-selecionada) no exemplo da API, mas a busca não trouxe a definição dele.
  - O "sem juros" **não é campo da preferência**: é configurado na **conta** do Mercado Pago. O site não consegue forçá-lo. Por isso o `help_text` da política avisa no admin, e o checklist do README ganhou o item.
  - Não encontramos campo de **parcela mínima** na preferência. Quem garante o mínimo é o nosso cálculo: enviamos o limite já reduzido pela parcela mínima.
  - Um exemplo em Python da documentação escreve `"installations"`, parece erro de digitação; o nome é `installments`.
  - **Quem divide e cobra é o Mercado Pago.** O site mostra opções e envia o limite; os valores do site são estimativa. O que vale é o valor confirmado pelo gateway (webhook, conferido contra o total do pedido).
  - Os nomes exatos dos campos serão confirmados no sandbox na Etapa 8. Nenhum SDK foi instalado nesta etapa.
- **Estimativa sem frete:** no checkout, o cálculo usa o valor dos **produtos**, sem o frete (a UF é escolhida na mesma tela). Como o total real é maior, o limite mostrado nunca passa do real: erramos para o lado seguro.
- **PENDÊNCIA DA ETAPA 8 (segurança):** o limite de parcelas enviado ao Mercado Pago deve ser **calculado no servidor**, sobre o **total do pedido** (produtos + frete), com `get_installment_limit` + `calculate_installments`, e **congelado no pedido na criação** (novo campo no `Order`, como o `shipping_cost`). **Nunca aceitar o número de parcelas, o limite ou o valor da parcela vindos do navegador.** Hoje o checkout só exibe a estimativa; nenhum dado de parcelas é enviado nem aceito pelo servidor.
- **PENDÊNCIA PARA A REVISÃO JURÍDICA:** se a política virar "a cliente paga os juros", a informação ao consumidor sobre juros no parcelamento (**CDC, art. 52**: preço à vista, taxa de juros, acréscimos, número e periodicidade das prestações, soma total a pagar) precisa estar nas telas e nos Termos. Hoje os textos são genéricos, de propósito, e a política padrão é a loja absorver.
- **Descartado:** calcular juros do gateway no site (a taxa é do Mercado Pago e pode mudar); mostrar "sem juros" nas telas (a promessa depende da conta do gateway, que o site não controla); arredondar cada parcela (a soma não bate); mostrar parcelas no carrinho (sem frete o valor mente).

## 100. Pix pela Orders API do Mercado Pago — v2 Etapa 7
- **Escolha:** o Pix é criado com `POST /v1/orders` (Orders API) e, na Etapa 7b, consultado (`GET /v1/orders/{id}`), cancelado (`/cancel`) e estornado (`/refund`). **Atualiza a decisão 53**, que falava em "API de pagamentos".
- **Por quê:** a página atual de Pix do Checkout API (consultada em 24/11/2026) usa a Orders API. A Payments API (`/v1/payments`) aparece como *legacy*: continua funcionando, mas "deixou de adicionar novas funcionalidades". O README do SDK oficial também recomenda a Orders API, e o teste do Pix no sandbox está documentado nela (`payer.first_name = "APRO"` aprova sozinho).
- **O que muda para nós:**
  - O "copia e cola" vem em `transactions.payments[0].payment_method.qr_code`.
  - O prazo vai como duração ISO 8601 (`expiration_time: "PT30M"`), de 30 minutos a 30 dias.
  - O cabeçalho `X-Idempotency-Key` é **obrigatório**.
  - O webhook é configurado **no painel** (evento "Order"), não por campo no pedido (Etapa 7b).
- **A confirmar no sandbox:** qual credencial funciona (a documentação se contradiz: "Access Token de teste" na página do Pix x "use usuários de teste com credenciais de produção" na referência da Orders API) e se o CPF é exigido (decisão 105).
- **Descartado:** Payments API (sem novidades; a migração para Orders seria trabalho repetido depois).
- **Fontes:** [Pix (Orders)](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/websites/pix), [criar order](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api/create-order/post), [status da order](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-management/status/order-status), [migração Payments → Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/resources/migrate-payments-to-orders), [teste do Pix](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/integration-test/pix).

## 101. SDK oficial `mercadopago` 3.6.0, isolado em `pagamentos/gateway.py` — v2 Etapa 7
- **Escolha:** `mercadopago==3.6.0` (publicado em 10/09/2026), aprovado pelo Kauan no plano. A 3.6.1 saiu em 24/11/2026, o dia desta etapa, e ficou de fora pela regra de "versão publicada há mais de 14 dias".
- **Dependências fixadas no `requirements.txt`** (datas conferidas no PyPI, todas até 09/11/2026): `requests==2.34.2`, `urllib3==2.8.0`, `idna==3.20`, `certifi==2026.10.23`, `charset-normalizer==3.5.2`.
- **Por que o SDK e não `requests` direto:**
  - `sdk.order().create/get/cancel/refund` já monta URL, cabeçalhos e corpo.
  - O validador de assinatura do webhook (`WebhookSignatureValidator`) é mantido pelo próprio Mercado Pago. A documentação não traz o texto exato que entra no HMAC; o SDK traz (Etapa 7b).
  - O SDK traz o `requests` de qualquer jeito: a diferença em dependências é só o próprio SDK.
- **Isolamento:** só `pagamentos/gateway.py` importa o SDK, e o import fica **dentro das funções**. O resto do site chama funções simples e recebe um `GatewayOrder` (dataclass). Os testes simulam essas funções com `mock.patch`: nenhuma chamada de rede.
- **Erros:** código HTTP fora de 200/201, ou falha de rede, vira `GatewayError` com mensagem genérica. O log registra só a operação e o código HTTP (nunca o corpo, que traz o e-mail da pagadora).
- **Descartado:** `requests` direto (manter à mão o que o SDK já faz, inclusive o manifesto da assinatura); a 3.6.1 (nova demais).

## 102. Model `pagamentos.Payment`: só IDs, status, valor e prazos — v2 Etapa 7
- **Escolha:** app novo, `pagamentos`, com o model `Payment` ligado ao pedido (`ForeignKey`, `PROTECT`). Campos: forma (`pix`), situação própria (criando, pendente, aprovado, cancelado, expirado, divergente, estorno pendente, estornado, estorno falhou), valor **congelado** na criação, chave de idempotência (UUID), IDs e status do Mercado Pago, "copia e cola", QR Code Base64, prazo do Pix e data da aprovação.
- **Um Pix por pedido:** `UniqueConstraint(order, method)`, **sem condição** (o MySQL não aceita as condicionais). Basta um, porque quando o Pix expira o pedido expira junto (decisão 103).
- **O que NÃO fica:** CPF, nome, e-mail, dados bancários e o corpo inteiro das respostas do gateway. O QR Code Base64 necessário para exibição é guardado em campo próprio.
- **"Copia e cola" guardado (`pix_code`):** não é dado da cliente; é o código da cobrança da loja e morre com o Pix. Guardar evita consultar o Mercado Pago a cada visita à página do QR.
- **Chave de idempotência gravada antes da chamada:** se a 1ª tentativa cair no meio, a 2ª manda a mesma chave e o Mercado Pago devolve a mesma cobrança, sem duplicar.
- **Admin:** só consulta (sem adicionar, editar ou apagar). O grupo "Loja" ganhou só `view_payment` (agora 24 permissões).
- **Situação do `Payment` separada do status do pedido:** um pagamento pode estar "aprovado" com o pedido "expirado" (pagamento tardio, Etapa 7b).
- **Descartado:** guardar a resposta inteira do gateway (traz dados pessoais); campos de pagamento direto no `Order` (a Etapa 8 traz o cartão, e um pedido pode ter tentativas de formas diferentes).

## 103. Prazo do Pix igual ao da reserva — v2 Etapa 7a
- **Regra atual:** validade da cobrança e `Order.expires_at` coincidem. O horário local é contado do início da requisição ao Mercado Pago, para que a reserva nunca passe dos N minutos de validade configurados para a cobrança.
- **Reserva renovada uma vez:** o Pix é gerado depois do checkout (a cliente pode demorar a clicar). Sem renovar, ela poderia receber um Pix de 30 minutos para um pedido que vence em 5. Como só existe um Pix por pedido, a reserva é renovada uma vez quando a cobrança é criada.
- **Por que havia 2 minutos:** a decisão original adicionou `ORDER_EXPIRY_MARGIN` para cobrir latência e diferença de relógio, receando aceitar um Pix após devolver o estoque. O requisito confirmado é igualdade, sem validade do Pix maior que a reserva; a margem foi removida.
- **Mínimo de 30 minutos:** o menor prazo que o Mercado Pago aceita. `reservation_minutes` passou de 5–1440 para **30–1440** (atualiza a decisão 89; a migration `loja/0006` sobe valores menores para 30). `pix_minutes()` ainda usa `max(N, 30)` por segurança.
- **Três passos, sem segurar a trava durante a rede:** (1) com `select_for_update()` no pedido, confere "aguardando e dentro do prazo" e cria o `Payment` "criando"; (2) sem trava, chama o Mercado Pago; (3) com trava, grava IDs e prazos. Clique duplo: as duas requisições mandam a mesma chave de idempotência e só a primeira grava no passo 3.
- **Na Etapa 7b:** pagamento que chega depois de expirar ou cancelar vira estorno automático com aviso à dona; cancelar o pedido cancela o Pix no gateway. A expiração do pedido permanece local e não chama o gateway.
- **Descartado:** criar o Pix no checkout (a Etapa 8 põe a escolha entre Pix e cartão no detalhe do pedido).

## 104. Tela do Pix: QR salvo do gateway e consulta só ao nosso banco — v2 Etapa 7a
- **Onde:** no detalhe do pedido, enquanto "aguardando pagamento", o botão **"Pagar com Pix"** (POST + CSRF; a Etapa 8 põe o cartão ao lado). Ele leva a `/pagamentos/pedido/<id>/pix/`: QR Code, "copia e cola" com botão "Copiar", valor e prazo. Depois de gerado, o detalhe mostra "Ver o QR Code do Pix".
- **QR Code:** imagem Base64 (`qr_code_base64`) retornada e salva da Orders API. Cobranças antigas sem essa imagem podem usar SVG gerado localmente a partir do "copia e cola".
- **Como a tela descobre que pagou:** o JavaScript consulta a cada 5 segundos `GET /pagamentos/pedido/<id>/pix/situacao/`, que devolve só `{"status": ...}` lido do **nosso banco**. Quando muda, a página recarrega. Essa rota **não fala com o Mercado Pago e não confirma nada**; quem muda o pedido para "pago" é o webhook (Etapa 7b). A única escrita possível nela é a expiração "preguiçosa" (decisão 88). Para de perguntar com a aba escondida e depois do prazo; `@never_cache` impede o navegador de reaproveitar uma resposta velha. Sem JavaScript: link "Já paguei, atualizar".
- **Segurança:** todas as rotas com `@login_required` e busca por `request.user.orders` (IDOR: outra conta, pedido da v1 ou inexistente dão 404). Pedido que não aguarda pagamento ou já vencido não gera Pix.
- **Sem Access Token no `.env`:** o botão some e aparece "pagamento online indisponível". O site funciona sem o Mercado Pago configurado.
- **Erros genéricos na tela:** "Não foi possível gerar o Pix agora. Tente de novo em instantes."
- **Descartado:** o `ticket_url` (página externa); consultar o Mercado Pago a partir da tela (o navegador passaria a disparar chamadas ao gateway, e só o webhook confirma).

## 105. CPF no Pix: não enviado; confirmação no sandbox pendente — v2 Etapa 7
- **Situação:** a documentação atual do Pix na Orders API manda só `payer.email` (e `first_name` no exemplo de teste). Nenhuma página consultada exige CPF. O código envia **só o e-mail** da conta (`gateway.build_pix_order_body`), e um teste garante que não há `identification` no corpo.
- **Sandbox:** `MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME=APRO` faz o Mercado Pago aprovar o Pix de teste sozinho. Em produção a variável fica **vazia** e nenhum nome é enviado.
- **Pendente:** gerar um Pix no sandbox com as credenciais do Kauan e confirmar que o Mercado Pago não recusa por falta de CPF. Se exigir, o CPF será pedido na tela do Pix e enviado **direto** ao gateway, sem ir ao banco nem aos logs (decisão 59), com nova aprovação do Kauan.
- **Política de Privacidade:** passou a dizer o que vai ao Mercado Pago no Pix (e-mail e valor) e o que fica no `Payment`. Versão `2026-11-24` (a pendência de reaceite da decisão 95 continua valendo).
