/*
 * Elegância Cristã — JavaScript do site (puro, sem bibliotecas).
 *
 * Cada função cuida de UMA coisa e é chamada no final do arquivo.
 * Tudo aqui é "aprimoramento": se o JavaScript falhar, o site continua
 * funcionando e com o conteúdo visível.
 */

// true quando a pessoa pediu ao sistema para reduzir animações.
const reduzirMovimento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Menu do celular: abre e fecha o painel ao clicar no botão "hambúrguer".
 * aria-expanded avisa ao leitor de tela se o menu está aberto ou fechado.
 */
function ativarMenuMobile() {
  const botao = document.querySelector('.menu-botao');
  const menu = document.getElementById('menu-principal');
  if (!botao || !menu) return;

  function definirAberto(aberto) {
    botao.setAttribute('aria-expanded', String(aberto));
    botao.querySelector('.visualmente-oculto').textContent = aberto ? 'Fechar menu' : 'Abrir menu';
    menu.classList.toggle('menu--aberto', aberto);
  }

  botao.addEventListener('click', function () {
    const estaAberto = botao.getAttribute('aria-expanded') === 'true';
    definirAberto(!estaAberto);
  });

  // Tecla Esc fecha o menu e devolve o foco ao botão.
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && botao.getAttribute('aria-expanded') === 'true') {
      definirAberto(false);
      botao.focus();
    }
  });
}

/**
 * Cabeçalho "inteligente": some ao rolar para baixo (mais espaço para o
 * conteúdo) e reaparece ao rolar para cima.
 */
function ativarCabecalhoInteligente() {
  const cabecalho = document.getElementById('cabecalho');
  if (!cabecalho) return;

  let ultimaPosicao = window.scrollY;
  let aguardandoQuadro = false;

  function atualizar() {
    const posicaoAtual = window.scrollY;
    const menuAberto = document.querySelector('.menu--aberto');
    // Só esconde depois de passar da altura do cabeçalho e com o menu fechado.
    const rolouParaBaixo = posicaoAtual > ultimaPosicao && posicaoAtual > cabecalho.offsetHeight;
    cabecalho.classList.toggle('cabecalho--oculto', rolouParaBaixo && !menuAberto);
    ultimaPosicao = posicaoAtual;
    aguardandoQuadro = false;
  }

  // O evento de scroll dispara dezenas de vezes por segundo.
  // requestAnimationFrame junta tudo em no máximo uma atualização por quadro.
  window.addEventListener('scroll', function () {
    if (!aguardandoQuadro) {
      aguardandoQuadro = true;
      window.requestAnimationFrame(atualizar);
    }
  }, { passive: true });

  // Se um link do cabeçalho receber foco pelo teclado, mostra o cabeçalho.
  cabecalho.addEventListener('focusin', function () {
    cabecalho.classList.remove('cabecalho--oculto');
  });
}

/**
 * Revelação no scroll: elementos com o atributo data-revelar surgem com
 * fade/deslize quando entram na tela. O IntersectionObserver avisa quando
 * isso acontece, sem precisar calcular posições a cada rolagem.
 */
function ativarRevelacaoNoScroll() {
  const elementos = document.querySelectorAll('[data-revelar]');

  // Sem suporte ou com movimento reduzido: mostra tudo de uma vez.
  if (reduzirMovimento || !('IntersectionObserver' in window)) {
    elementos.forEach(function (elemento) {
      elemento.classList.add('revelado');
    });
    return;
  }

  const observador = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (entrada) {
      if (entrada.isIntersecting) {
        entrada.target.classList.add('revelado');
        // Já apareceu: não precisa mais observar este elemento.
        observador.unobserve(entrada.target);
      }
    });
  }, {
    threshold: 0.15,                  // 15% do elemento visível
    rootMargin: '0px 0px -40px 0px',  // dispara um pouco antes do fim da tela
  });

  elementos.forEach(function (elemento) {
    observador.observe(elemento);
  });
}

/**
 * Parallax leve: o fundo do banner se move mais devagar que a página,
 * criando sensação de profundidade.
 */
function ativarParallax() {
  const fundos = document.querySelectorAll('[data-parallax]');
  if (reduzirMovimento || fundos.length === 0) return;

  const VELOCIDADE = 0.3; // 0 = parado; 1 = acompanha a rolagem
  let aguardandoQuadro = false;

  function atualizar() {
    const deslocamento = window.scrollY * VELOCIDADE;
    fundos.forEach(function (fundo) {
      fundo.style.transform = 'translate3d(0, ' + deslocamento + 'px, 0)';
    });
    aguardandoQuadro = false;
  }

  window.addEventListener('scroll', function () {
    // Depois que o banner sai da tela, não há o que mover.
    if (window.scrollY > window.innerHeight) return;
    if (!aguardandoQuadro) {
      aguardandoQuadro = true;
      window.requestAnimationFrame(atualizar);
    }
  }, { passive: true });
}

/**
 * Galeria da página do produto: clicar numa miniatura troca a foto grande.
 * Sem JavaScript, a miniatura é um link comum e abre a foto sozinha.
 */
function ativarGaleriaProduto() {
  const principal = document.getElementById('galeria-principal');
  const miniaturas = document.querySelectorAll('.galeria__miniatura');
  if (!principal || miniaturas.length === 0) return;

  miniaturas.forEach(function (miniatura) {
    miniatura.addEventListener('click', function (evento) {
      // Impede o navegador de seguir o link (abrir a foto em outra página).
      evento.preventDefault();
      principal.src = miniatura.href;
      principal.alt = miniatura.dataset.alt;
      // Marca qual miniatura está selecionada (o CSS desenha a borda).
      miniaturas.forEach(function (outra) {
        outra.removeAttribute('aria-current');
      });
      miniatura.setAttribute('aria-current', 'true');
    });
  });
}

/**
 * Aviso de cookies (decisão 82): mostra a faixa até a pessoa clicar em "Entendi".
 *
 * A escolha fica no localStorage, um armazenamento do próprio navegador.
 * Diferente de um cookie, ele NÃO é enviado ao servidor a cada página.
 * try/catch: em janela anônima ou com armazenamento bloqueado, o acesso
 * pode dar erro; nesse caso o aviso só aparece de novo, sem quebrar nada.
 */
function ativarAvisoCookies() {
  const aviso = document.getElementById('aviso-cookies');
  const botao = document.getElementById('aviso-cookies-ok');
  if (!aviso || !botao) return;
  const CHAVE = 'aviso-cookies-visto';

  let jaViu = false;
  try {
    jaViu = window.localStorage.getItem(CHAVE) === '1';
  } catch (erro) {
    jaViu = false;
  }
  if (jaViu) return;

  aviso.hidden = false;
  botao.addEventListener('click', function () {
    aviso.hidden = true;
    try {
      window.localStorage.setItem(CHAVE, '1');
    } catch (erro) {
      // Sem armazenamento: o aviso volta na próxima página. Tudo bem.
    }
  });
}

/**
 * Checkout: mostra o frete e o total ao escolher a UF (v2 Etapa 5, decisão 90).
 *
 * A tabela vem do servidor num <script type="application/json"> (filtro
 * json_script do Django). É só para MOSTRAR: o valor cobrado é calculado de
 * novo pelo servidor ao confirmar o pedido.
 *
 * Dinheiro em CENTAVOS (números inteiros): em JavaScript, 0.1 + 0.2 dá
 * 0.30000000000000004. Somando centavos inteiros não há esse erro.
 */
function ativarFreteCheckout() {
  const dadosTabela = document.getElementById('tabela-frete');
  const campoUF = document.getElementById('id_state');
  const totais = document.querySelector('.checkout__totais');
  if (!dadosTabela || !campoUF || !totais) return;

  const tabela = JSON.parse(dadosTabela.textContent);
  const freteValor = document.getElementById('frete-valor');
  const totalValor = document.getElementById('total-valor');

  // "229.90" -> 22990 (centavos)
  function emCentavos(texto) {
    const [reais, centavos = '0'] = texto.split('.');
    return Number(reais) * 100 + Number(centavos.padEnd(2, '0').slice(0, 2));
  }
  // 22990 -> "R$ 229,90"
  function emReais(centavos) {
    const reais = Math.floor(centavos / 100).toLocaleString('pt-BR');
    return 'R$ ' + reais + ',' + String(centavos % 100).padStart(2, '0');
  }

  const totalProdutos = emCentavos(totais.dataset.totalProdutos);

  function atualizar() {
    const uf = campoUF.value;
    if (!uf) {
      freteValor.textContent = 'escolha a UF';
      totalValor.textContent = emReais(totalProdutos) + ' + frete';
      return;
    }
    if (!(uf in tabela.rates)) {
      freteValor.textContent = 'ainda não entregamos nesta UF';
      totalValor.textContent = emReais(totalProdutos);
      return;
    }
    const gratis = tabela.free_from !== null && totalProdutos >= emCentavos(tabela.free_from);
    const frete = gratis ? 0 : emCentavos(tabela.rates[uf]);
    freteValor.textContent = gratis ? 'grátis' : emReais(frete);
    totalValor.textContent = emReais(totalProdutos + frete);
  }

  campoUF.addEventListener('change', atualizar);
  atualizar(); // o formulário pode voltar com a UF já escolhida (erro em outro campo)
}

/**
 * Confirmação antes de ações sem volta (ex.: cancelar pedido).
 *
 * Formulários com data-confirmar="texto" pedem confirmação ao enviar.
 * Melhora progressiva: sem JavaScript o formulário envia direto, e o servidor
 * continua validando tudo (dono do pedido, status, CSRF).
 */
function ativarConfirmacaoDeFormularios() {
  document.querySelectorAll('form[data-confirmar]').forEach((formulario) => {
    formulario.addEventListener('submit', (evento) => {
      if (!window.confirm(formulario.dataset.confirmar)) evento.preventDefault();
    });
  });
}

/**
 * Botão "Copiar código" do Pix (data-copiar="#id-do-campo").
 *
 * navigator.clipboard só existe em página segura (HTTPS ou localhost). Se não
 * existir, o botão continua escondido e a cliente copia selecionando o texto.
 */
function ativarBotoesCopiar() {
  if (!navigator.clipboard) return;
  document.querySelectorAll('[data-copiar]').forEach((botao) => {
    const campo = document.querySelector(botao.dataset.copiar);
    if (!campo) return;
    botao.hidden = false;
    botao.addEventListener('click', () => {
      navigator.clipboard.writeText(campo.value).then(
        () => { botao.textContent = 'Código copiado!'; },
        () => { campo.select(); }  // sem permissão: ao menos seleciona o texto
      );
    });
  });
}

/**
 * Página do Pix: pergunta ao NOSSO servidor, a cada 5 segundos, se a situação
 * do pedido mudou. Se mudou (pago ou expirado), recarrega a página.
 *
 * IMPORTANTE: isto só ATUALIZA A TELA. Quem marca o pedido como pago é o
 * webhook do Mercado Pago, no servidor. O navegador nunca confirma nada.
 *
 * Economia: não pergunta com a aba escondida (visibilitychange) e para
 * depois que o prazo do Pix passa (o servidor já terá expirado o pedido).
 */
function ativarPaginaPix() {
  const caixa = document.querySelector('[data-pix]');
  if (!caixa || !window.fetch) return;
  const urlSituacao = caixa.dataset.statusUrl;
  const situacaoAtual = caixa.dataset.statusAtual;
  const expiraEm = new Date(caixa.dataset.expiraEm);
  const aviso = caixa.querySelector('[data-pix-aviso]');
  const INTERVALO = 5000;  // milissegundos
  // Margem de 3 minutos depois do prazo, para o servidor expirar o pedido.
  const PARAR_EM = expiraEm.getTime() + 3 * 60 * 1000;
  let temporizador = null;

  function perguntar() {
    if (Date.now() > PARAR_EM) return;  // para de perguntar
    fetch(urlSituacao, { headers: { Accept: 'application/json' } })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((dados) => {
        if (dados && dados.status !== situacaoAtual) {
          aviso.textContent = 'A situação do pedido mudou. Atualizando…';
          window.location.reload();
          return;
        }
        agendar();
      })
      .catch(agendar);  // sem internet por um instante: tenta de novo depois
  }

  function agendar() {
    if (!document.hidden) temporizador = window.setTimeout(perguntar, INTERVALO);
  }

  document.addEventListener('visibilitychange', () => {
    window.clearTimeout(temporizador);
    if (!document.hidden) perguntar();  // voltou para a aba: pergunta na hora
  });
  agendar();
}

ativarMenuMobile();
ativarCabecalhoInteligente();
ativarRevelacaoNoScroll();
ativarParallax();
ativarGaleriaProduto();
ativarAvisoCookies();
ativarFreteCheckout();
ativarConfirmacaoDeFormularios();
ativarBotoesCopiar();
ativarPaginaPix();
