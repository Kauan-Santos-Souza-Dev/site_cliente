"""Versões dos textos legais e prazos de retenção de dados (LGPD, v2 Etapa 4).

Tudo que é "regra de privacidade" fica num lugar só, para que o código, a
Política de Privacidade e os testes usem os MESMOS valores.

Versões dos textos (decisão 77):
Quando a Política de Privacidade ou os Termos de Uso mudarem, troque a
versão abaixo (usamos a data da mudança; se mudar duas vezes no mesmo dia,
acrescente ".2", ".3"...). Cada aceite gravado no banco
(model `Consent`) guarda a versão que a cliente leu. Assim dá para provar
O QUE foi aceito e QUANDO, mesmo depois que o texto mudar.

Prazos de retenção (decisão 79):
São PROPOSTAS com fundamento citado no DECISIONS.md e na Política. Os que
dependem de lei estão marcados para revisão jurídica. Quem aplica os prazos
é o comando `python manage.py limpar_dados_antigos`.
"""

from datetime import timedelta

# --- Versões dos textos ---------------------------------------------------
# .2 (v2 Etapa 5): pedido ligado à conta, exportação com pedidos, exclusão
# bloqueada com pedido em andamento.
# .3 (v2 Etapa 5b): o prazo de "pedido em andamento" passa a contar da ENTREGA.
PRIVACY_POLICY_VERSION = '2026-11-22.3'
TERMS_VERSION = '2026-11-22'

# --- Prazos de retenção ---------------------------------------------------
# Dados pessoais do pedido (nome, telefone, endereço): 5 anos a partir do
# pedido, depois anonimizados. Referência: CDC art. 27 (5 anos para pedir
# reparação) + LGPD art. 16 I e art. 7º VI. Pendente de revisão jurídica.
ORDER_RETENTION = timedelta(days=5 * 365)

# Conta que nunca confirmou o e-mail: 30 dias. Sem prazo legal; é
# minimização (LGPD art. 6º III). Ela não pode ter pedido (decisão 72).
UNVERIFIED_ACCOUNT_RETENTION = timedelta(days=30)

# Tentativas de login guardadas pelo django-axes: 30 dias. Sem prazo legal;
# o bloqueio só precisa delas por 15 minutos (decisão 71). A sobra serve
# para a dona notar um ataque recente.
LOGIN_ATTEMPT_RETENTION = timedelta(days=30)
