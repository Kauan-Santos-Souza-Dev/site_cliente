"""Limite de pedidos por IP: protege o estoque contra pedidos em massa.

Por que isso existe?
Cada pedido desconta o estoque na hora. Sem limite, um robô (ou alguém mal
intencionado) poderia fazer dezenas de pedidos com dados falsos e "esgotar"
a loja até a dona cancelar tudo no admin.

Como funciona?
Usamos o cache do Django, um "armário" de chave → valor com prazo de
validade. Para cada IP guardamos quantos pedidos ele fez; a contagem some
sozinha depois de 1 hora. Por padrão o cache fica na memória do servidor
(o mesmo que o limite da API usa; veja DECISIONS.md, decisões 34 e 47).
"""

from django.core.cache import cache

# Quantos pedidos um mesmo IP pode fazer dentro da janela de tempo.
MAX_ORDERS_PER_HOUR = 5
# Janela de tempo, em segundos (1 hora).
WINDOW_SECONDS = 60 * 60


def _cache_key(request):
    """Monta a chave do contador no cache a partir do IP da visitante.

    REMOTE_ADDR é o IP de quem conectou no servidor. Em produção, atrás de
    um proxy (Nginx, Cloudflare...), ele seria o IP do proxy, e todas as
    clientes dividiriam o mesmo contador. Nesse caso é preciso configurar o
    servidor para informar o IP real (veja o checklist no README).
    """
    ip = request.META.get('REMOTE_ADDR', 'desconhecido')
    return f'checkout:{ip}'


def too_many_orders(request):
    """Diz se este IP já atingiu o limite de pedidos na última hora."""
    count = cache.get(_cache_key(request), 0)
    return count >= MAX_ORDERS_PER_HOUR


def register_order(request):
    """Soma 1 ao contador de pedidos deste IP.

    cache.add só cria a chave se ela não existir (com validade de 1 hora);
    depois, cache.incr soma 1 sem mexer na validade. Assim a janela conta
    a partir do PRIMEIRO pedido, e não é renovada a cada novo pedido.
    """
    key = _cache_key(request)
    cache.add(key, 0, timeout=WINDOW_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        # A chave expirou bem entre o add e o incr (raríssimo): recomeça.
        cache.set(key, 1, timeout=WINDOW_SECONDS)
