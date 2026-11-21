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
| v2 · 1 | Preparação da v2: versionamento e escolha do gateway | 51 e 52 |

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

## 45. Telefone e CEP só com dígitos — Etapa 7
- **Escolha:** o formulário aceita "(11) 91234-5678" e "01234-567", mas guarda só os dígitos (`clean_phone`, `clean_cep`). Telefone com 10 ou 11 dígitos; CEP com 8. A formatação volta na exibição (`format_phone`, `format_cep`, `format_brl` em `pedidos/whatsapp.py`).
- **Por quê:** dados uniformes no banco facilitam busca no admin e o link do WhatsApp.
- **Descartado:** consulta automática de CEP (ViaCEP) — chamada a serviço externo; fica para a v2.

## 46. Admin de pedidos — Etapa 7
- **Escolha:** itens somente leitura dentro do pedido; status editável na lista; ação "Cancelar pedidos selecionados (devolve o estoque)"; sem botão "Adicionar" (pedido só nasce pelo site, que desconta o estoque); exclusão permitida só para pedidos cancelados ou enviados, e sem a exclusão em massa padrão.
- **Por quê:** apagar um pedido "novo" sumiria com as peças reservadas sem devolvê-las.
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
- **Recomendação:** Mercado Pago (detalhes na resposta da v2 Etapa 1). **A escolha é do Kauan/da loja** e será registrada numa decisão própria.
