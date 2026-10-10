(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtData = (iso, hora) => {
    if (!iso) return "—";
    const o = { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric" };
    if (hora) Object.assign(o, { hour: "2-digit", minute: "2-digit" });
    return new Intl.DateTimeFormat("pt-BR", o).format(new Date(iso));
  };
  const pct = (v) => (Math.round((v || 0) * 10) / 10).toLocaleString("pt-BR");
  const barra = (p, cls = "") => `<div class="barra ${cls}" role="progressbar" aria-valuenow="${p}" aria-valuemin="0" aria-valuemax="100"><span style="width:${Math.max(0, Math.min(100, p || 0))}%"></span></div>`;
  const plural = (n, s, p) => `${n} ${n === 1 ? s : p}`;
  const ROTULO = { coberta: "Coberta", em_andamento: "Em andamento", planejada: "Planejada no backlog", futura: "Prevista" };
  const COR = { coberta: "verde", em_andamento: "laranja", planejada: "plan", futura: "cinza" };
  let DADOS = null;

  // Compatibilidade com o formato antigo (projeto único)
  function normaliza(d) {
    if (d.projetos) return d;
    const p = Object.assign({ slug: "calc", nome: "Tekto Calc", descricao: "", areas: d.disciplinas || [] }, d);
    p.ultima_entrega = (d.entregas && d.entregas[0] && d.entregas[0].data) || null;
    return { atualizado_em: d.atualizado_em, projetos: [p], geral: { total: d.total, feitos: d.feitos, percentual: d.percentual, duvidas: (d.duvidas || []).length, entregas: d.total_entregas || 0, ultima_entrega: p.ultima_entrega } };
  }

  function normasHTML(d) {
    const n = d.normas || [];
    if (!n.length) return `<p class="vazio">Nenhuma norma ou referência mapeada ainda.</p>`;
    return `<div class="chips">${n.map((x) => `<span class="chip ${esc(x.estado)}" title="${esc(ROTULO[x.estado] || "")}${x.tarefas ? ` · ${x.feitas}/${x.tarefas} tarefas` : ""}"><i></i><b>${esc(x.norma)}</b>${x.descricao ? `<span class="d">${esc(x.descricao)}</span>` : ""}</span>`).join("")}</div>
      <div class="leg-chips">${Object.entries(ROTULO).map(([k, v]) => `<span><i style="background:var(--${COR[k]})"></i>${v}</span>`).join("")}</div>`;
  }
  const duvidasHTML = (d) => (d.duvidas || []).length ? d.duvidas.map((x) => `<div class="duvida">${esc(x.texto)}</div>`).join("") : `<p class="vazio">Nenhuma dúvida em aberto.</p>`;
  const entregasHTML = (d) => (d.entregas || []).length
    ? `<ul class="lista">${d.entregas.map((e) => `<li><span class="tid">#${esc(e.numero)}</span><span>${esc(e.titulo)}</span><span class="data">${fmtData(e.data)}</span></li>`).join("")}</ul>`
    : `<p class="vazio">Nenhuma entrega mesclada ainda.</p>`;

  function cartaoProjeto(p, sel) {
    const prep = p.estado !== "ativo";
    return `<a class="proj ${sel ? "sel" : ""}" href="#${esc(p.slug)}" data-slug="${esc(p.slug)}">
      <h3><span>${esc(p.nome)}</span>${prep ? "" : `<b>${pct(p.percentual)}%</b>`}</h3>
      ${p.descricao ? `<div class="sub">${esc(p.descricao)}</div>` : ""}
      ${prep ? `<span class="selo">Em preparação</span>` : barra(p.percentual)}
      <div class="meta"><span>${prep ? "backlog ainda não publicado" : `${p.feitos}/${p.total} tarefas`}</span><span>${plural((p.duvidas || []).length, "dúvida", "dúvidas")}</span></div>
      <div class="meta"><span>Última entrega</span><span>${fmtData(p.ultima_entrega)}</span></div>
    </a>`;
  }

  function detalheHTML(d) {
    if (d.estado !== "ativo") {
      return `
      <section class="cartao prep">
        <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M8 54h48M14 54V30l18-14 18 14v24M26 54V40h12v14" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><path d="M44 10l8 8M52 10l-8 8" stroke="#8da9c4" stroke-width="2"/></svg>
        <h2>${esc(d.nome)} em preparação</h2>
        <p>A estrutura do repositório e o backlog de tarefas estão sendo montados. Assim que o backlog for publicado, esta seção passa a mostrar o progresso por área, as próximas tarefas e as entregas.</p>
      </section>
      <section class="cartao meio"><h2>Últimas entregas</h2>${entregasHTML(d)}</section>
      <section class="cartao meio"><h2>Dúvidas em aberto</h2>${duvidasHTML(d)}</section>
      ${(d.normas || []).length ? `<section class="cartao"><h2>Normas e referências</h2>${normasHTML(d)}</section>` : ""}`;
    }
    const areas = d.areas || d.disciplinas || [];
    return `
    <section class="cartao">
      <h2>Progresso geral · ${esc(d.nome)}</h2>
      <div class="geral">
        <div class="pct">${pct(d.percentual)}<small>%</small></div>
        <div class="geral-info">
          ${barra(d.percentual, "grossa")}
          <div class="legenda"><span>${d.feitos} de ${d.total} tarefas concluídas</span><span>${d.total - d.feitos} pendentes</span></div>
          <div class="kpis">
            <div class="kpi"><b>${d.feitos}/${d.total}</b><span>tarefas</span></div>
            <div class="kpi"><b>${areas.length}</b><span>áreas</span></div>
            <div class="kpi"><b>${(d.normas_cobertas || []).length}</b><span>normas cobertas</span></div>
            <div class="kpi"><b>${d.total_entregas || 0}</b><span>entregas mescladas</span></div>
            <div class="kpi"><b>${(d.duvidas || []).length}</b><span>dúvidas em aberto</span></div>
          </div>
        </div>
      </div>
    </section>
    <section class="cartao meio">
      <h2>Progresso por área</h2>
      ${areas.map((x) => `<div class="disc"><div class="disc-top"><span>${esc(x.nome)}</span><span class="n">${x.feitos}/${x.total} · ${pct(x.percentual)}%</span></div>${barra(x.percentual)}</div>`).join("") || `<p class="vazio">Sem áreas.</p>`}
    </section>
    <section class="cartao meio">
      <h2>Próximas tarefas</h2>
      ${(d.proximas || []).length ? `<ul class="lista">${d.proximas.map((t) => `<li>${t.id ? `<span class="tid">${esc(t.id)}</span>` : ""}<span>${esc(t.titulo)}<br><span class="sub">${esc(t.disciplina)}${t.normas && t.normas.length ? " · " + esc(t.normas.join(", ")) : ""}</span></span></li>`).join("")}</ul>` : `<p class="vazio">Backlog concluído! 🎉</p>`}
    </section>
    <section class="cartao meio"><h2>Últimas entregas</h2>${entregasHTML(d)}</section>
    <section class="cartao meio"><h2>Dúvidas em aberto</h2>${duvidasHTML(d)}</section>
    <section class="cartao"><h2>Normas e referências</h2>${normasHTML(d)}</section>`;
  }

  function render() {
    const d = DADOS, ps = d.projetos, g = d.geral || {};
    const slug = (location.hash || "").slice(1);
    const atual = ps.find((p) => p.slug === slug) || ps[0];
    $("#atualizado").textContent = "Atualizado em " + fmtData(d.atualizado_em, true) + " (BRT)";
    $("#conteudo").innerHTML = `
      <h2 class="secao-titulo">Visão geral</h2>
      <div class="projetos">
        <div class="proj total">
          <h3><span>Todos os projetos</span><b>${pct(g.percentual)}%</b></h3>
          <div class="sub">${plural(ps.length, "projeto", "projetos")} · ${plural(g.projetos_ativos ?? ps.filter((p) => p.estado === "ativo").length, "ativo", "ativos")}</div>
          ${barra(g.percentual)}
          <div class="meta"><span>${g.feitos}/${g.total} tarefas</span><span>${plural(g.duvidas || 0, "dúvida", "dúvidas")}</span></div>
          <div class="meta"><span>${plural(g.entregas || 0, "entrega", "entregas")} · última</span><span>${fmtData(g.ultima_entrega)}</span></div>
        </div>
        ${ps.map((p) => cartaoProjeto(p, p === atual)).join("")}
      </div>
      <div class="abas" role="tablist">${ps.map((p) => `<button role="tab" aria-selected="${p === atual}" data-slug="${esc(p.slug)}">${esc(p.nome)}</button>`).join("")}</div>
      <div id="detalhe" role="tabpanel">${detalheHTML(atual)}</div>`;
    document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => {
      history.replaceState(null, "", "#" + b.dataset.slug); render();
    }));
  }

  window.addEventListener("hashchange", () => DADOS && render());
  fetch("data.json?t=" + Date.now(), { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((d) => { DADOS = normaliza(d); render(); })
    .catch(() => {
      $("#atualizado").textContent = "Sem dados";
      $("#conteudo").innerHTML = `<section class="cartao prep"><h2>Painel em preparação</h2><p>Os dados do painel ainda não estão disponíveis. Volte em breve.</p></section>`;
    });
})();
