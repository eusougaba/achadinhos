/* Garimpo no painel de afiliados do Mercado Livre (rodar no Edge, logado, na página /afiliados/hub).
   Carregar com:  (async()=>{eval(await (await fetch('https://achadoteca.com.br/admin/painel_ml.js')).text())})()
   Uso:
     AC.go([['parafusadeira','ferramentas'],['fone bluetooth','tecnologia']])   // busca e filtra pelas regras
     await AC.esperar()        // devolve uma linha por candidato aprovado no filtro básico
     AC.go2([0,3,4])           // gera link e ID dos escolhidos (índices da lista)
     await AC.esperar()        // devolve o JSON para scripts/novo_produto.py
   Só lê e clica em "Compartilhar", como uma pessoa faria; poucas buscas por vez. */
(function () {
  if (window.AC && window.AC.v === 1) return;
  var BASE = 'https://achadoteca.com.br';
  var AC = { v: 1, res: [], copias: [], ocupado: false, saida: null, regras: null };
  window.AC = AC;

  // intercepta a cópia para eu ler o link e o ID sem depender da área de transferência
  var orig = navigator.clipboard.writeText.bind(navigator.clipboard);
  navigator.clipboard.writeText = function (t) { AC.copias.push(String(t)); return orig(t).catch(function () {}); };

  var esp = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var num = function (m) { return m ? parseFloat(m[1].replace(/\./g, '') + '.' + (m[2] || '00')) : null; };
  var vendas = function (s) { var m = (s || '').match(/([\d.]+)(mil)?/); return m ? parseInt(m[1].replace(/\./g, ''), 10) * (m[2] ? 1000 : 1) : 0; };

  function lis() {
    return [].slice.call(document.querySelectorAll('li')).filter(function (li) {
      return [].slice.call(li.querySelectorAll('button')).some(function (b) { return b.textContent.trim() === 'Compartilhar'; });
    });
  }

  function det(li) {
    var t = li.innerText.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
    var j = t.join(' ');
    var titulo = t.find(function (s) { return s.length > 20 && !/^(MAIS|OFERTA|PREÇO|CAMPANHA)/.test(s) && !/^GANHOS|^R\$|^\d/.test(s); });
    var semParc = j.replace(/\d+x\s*R\$.*$/, ''), nums = [], re = /R\$\s*([\d.]+)\s*(?:,\s*(\d{2}))?/g, m;
    while ((m = re.exec(semParc))) nums.push(num(m));
    var outros = j.match(/ou\s+R\$\s*([\d.]+)\s*(?:,\s*(\d{2}))?\s+em outros meios/);
    var off = j.match(/(\d+)% OFF/), g = j.match(/GANHOS (EXTRAS )?(\d+)%/), n = j.match(/(\d[.,]\d) \| \+?([\d.]+(?:mil)?) vendidos/);
    var p, de = null;
    if (outros) { de = nums[0]; p = num(outros); } else if (off && nums.length >= 2) { de = nums[0]; p = nums[1]; } else { p = nums[0]; }
    if (de !== null && de <= p) de = null;
    var im = [].slice.call(li.querySelectorAll('img')).map(function (i) { return i.currentSrc || i.src || ''; })
      .map(function (s) { var x = s.match(/D_(?:Q_NP_2X_|NQ_NP_|2X_)?(\d{5,}-ML[AB]\d+_\d+)/); return x ? x[1] : null; }).filter(Boolean)[0];
    return { t: titulo, p: p, de: de, com: g ? +g[2] : null, extra: !!(g && g[1]), nota: n ? n[1] : null, vend: n ? vendas(n[2]) : 0, img: im || null };
  }

  AC.busca = async function (q) {
    var inp = document.querySelector('input[placeholder="Busque produtos"]');
    var set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, q); inp.dispatchEvent(new Event('input', { bubbles: true }));
    ['keydown', 'keypress', 'keyup'].forEach(function (tp) { inp.dispatchEvent(new KeyboardEvent(tp, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true })); });
    await esp(4000);
  };

  function passa(c, mn) {
    var desc = c.de ? Math.round((1 - c.p / c.de) * 100) : 0;
    return c.t && c.nota && parseFloat(c.nota) >= mn.nota && c.vend >= mn.vendas && desc >= mn.desconto &&
      c.p >= mn.preco_min && c.p <= mn.preco_max && (c.com || 0) >= mn.comissao && c.img;
  }

  AC.go = function (lista, porBusca) {
    AC.ocupado = true; AC.saida = null; AC.res = [];
    (async function () {
      try {
        AC.regras = AC.regras || await (await fetch(BASE + '/admin/regras.json')).json();
        var vistos = {};
        for (var k = 0; k < lista.length; k++) {
          await AC.busca(lista[k][0]);
          var bons = lis().map(det).filter(function (c) { return passa(c, AC.regras.minimos) && !vistos[c.t]; })
            .sort(function (a, b) { return b.vend * b.nota - a.vend * a.nota; }).slice(0, porBusca || 3);
          bons.forEach(function (c) { vistos[c.t] = 1; c.q = lista[k][0]; c.cat = lista[k][1]; AC.res.push(c); });
        }
        AC.saida = AC.res.map(function (c, i) {
          var d = c.de ? Math.round((1 - c.p / c.de) * 100) : 0;
          return i + '|' + c.cat + '|' + c.t.slice(0, 52) + '|R$' + c.p + '|-' + d + '%|c' + c.com + (c.extra ? '+' : '') + '|' + c.nota + '|' + c.vend;
        }).join('\n') || 'nenhum passou nas regras';
      } catch (e) { AC.saida = 'ERRO ' + e; }
      AC.ocupado = false;
    })();
    return 'iniciado ' + lista.length + ' buscas';
  };

  function botao(txt, raiz) {
    return [].slice.call((raiz || document).querySelectorAll('button,[role="button"],a')).find(function (e) {
      return e.textContent.replace(/\s+/g, ' ').trim().indexOf(txt) === 0 && e.offsetParent !== null;
    });
  }

  AC.go2 = function (indices) {
    AC.ocupado = true; AC.saida = null;
    (async function () {
      var out = [], atual = null;
      try {
        for (var k = 0; k < indices.length; k++) {
          var c = AC.res[indices[k]];
          if (atual !== c.q) { await AC.busca(c.q); atual = c.q; }
          var li = lis().find(function (x) { return x.innerText.indexOf(c.t.slice(0, 40)) > -1; });
          if (!li) { out.push({ t: c.t, erro: 'não achei na tela' }); continue; }
          AC.copias = [];
          [].slice.call(li.querySelectorAll('button')).find(function (b) { return b.textContent.trim() === 'Compartilhar'; }).click();
          await esp(1800); var a = botao('Copiar link'); if (a) a.click(); await esp(1800);
          var b = botao('Copiar ID'); if (b) b.click(); await esp(1800);
          var link = AC.copias.find(function (x) { return /meli\.la/.test(x); }), id = AC.copias.find(function (x) { return /^EQMTUP/.test(x); });
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', keyCode: 27, bubbles: true }));
          var f = botao('Fechar'); if (f) f.click(); await esp(1500);
          out.push(link && id ? { t: c.t, p: c.p, de: c.de, com: c.com, nota: c.nota, vend: c.vend, link: link, id: id, img: c.img, cat: c.cat } : { t: c.t, erro: 'sem link' });
        }
        AC.saida = JSON.stringify(out);
      } catch (e) { AC.saida = 'ERRO ' + e; }
      AC.ocupado = false;
    })();
    return 'iniciado ' + indices.length + ' links';
  };

  // Atualiza preços: AC.precos([{s:'slug',t:'título cadastrado'}]) e depois await AC.esperar()
  AC.precos = function (itens) {
    AC.ocupado = true; AC.saida = null;
    (async function () {
      var out = [];
      try {
        for (var k = 0; k < itens.length; k++) {
          var it = itens[k];
          await AC.busca(it.t.split(/\s+/).slice(0, 7).join(' '));
          var nz = function (x) { return x.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').split(/[^a-z0-9]+/).filter(function (w) { return w.length > 1; }); };
          var A = nz(it.t), melhor = null, mp = 0;
          lis().map(det).forEach(function (x) {
            if (!x.t) return; var B = nz(x.t), com = A.filter(function (w) { return B.indexOf(w) > -1; }).length / A.length;
            if (com > mp) { mp = com; melhor = x; }
          });
          var c = mp >= 0.7 ? melhor : null;
          out.push(c ? { s: it.s, p: c.p, de: c.de } : { s: it.s, erro: 'não achei' });
        }
        AC.saida = JSON.stringify(out);
      } catch (e) { AC.saida = 'ERRO ' + e; }
      AC.ocupado = false;
    })();
    return 'iniciado ' + itens.length + ' preços';
  };

  AC.esperar = async function (max) {
    var t0 = Date.now();
    while (AC.ocupado && Date.now() - t0 < (max || 40000)) await esp(1500);
    return AC.ocupado ? 'ainda rodando' : AC.saida;
  };
})();
