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
  const pct = (v) => (Math.round(v * 10) / 10).toLocaleString("pt-BR");
  const barra = (p, cls = "") => `<div class="barra ${cls}" role="progressbar" aria-valuenow="${p}" aria-valuemin="0" aria-valuemax="100"><span style="width:${Math.max(0, Math.min(100, p))}%"></span></div>`;
  const ROTULO = { coberta: "Coberta", em_andamento: "Em andamento", planejada: "Planejada no backlog", futura: "Prevista" };

  function normasHTML(d) {
    const n = d.normas || [];
    if (!n.length) return `<p class="vazio">Nenhuma norma mapeada ainda.</p>`;
    return `<div class="chips">${n.map((x) => `<span class="chip ${esc(x.estado)}" title="${esc(ROTULO[x.estado] || "")}${x.tarefas ? ` · ${x.feitas}/${x.tarefas} tarefas` : ""}"><i></i><b>${esc(x.norma)}</b><span class="d">${esc(x.descricao)}</span></span>`).join("")}</div>
      <div class="leg-chips">${Object.entries(ROTULO).map(([k, v]) => `<span><i style="background:var(--${{ coberta: "verde", em_andamento: "laranja", planejada: "plan", futura: "cinza" }[k]})"></i>${v}</span>`).join("")}</div>`;
  }

  function duvidasHTML(d) {
    const l = d.duvidas || [];
    return l.length ? l.map((x) => `<div class="duvida">${esc(x.texto)}</div>`).join("") : `<p class="vazio">Nenhuma dúvida normativa em aberto.</p>`;
  }

  function entregasHTML(d) {
    const l = d.entregas || [];
    return l.length
      ? `<ul class="lista">${l.map((e) => `<li><span class="tid">#${esc(e.numero)}</span><span>${esc(e.titulo)}</span><span class="data">${fmtData(e.data)}</span></li>`).join("")}</ul>`
      : `<p class="vazio">Nenhuma entrega mesclada ainda.</p>`;
  }

  function render(d) {
    $("#atualizado").textContent = "Atualizado em " + fmtData(d.atualizado_em, true) + " (BRT)";
    const m = $("#conteudo");
    if (d.estado !== "ativo") {
      m.innerHTML = `
      <section class="cartao prep">
        <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M8 54h48M14 54V30l18-14 18 14v24M26 54V40h12v14" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><path d="M44 10l8 8M52 10l-8 8" stroke="#8da9c4" stroke-width="2"/></svg>
        <h2>Projeto em preparação</h2>
        <p>A estrutura do repositório e o backlog de tarefas estão sendo montados. Assim que o backlog for publicado, este painel passa a mostrar o progresso por disciplina, as próximas tarefas e as entregas diárias.</p>
      </section>
      <section class="cartao meio"><h2>Últimas entregas</h2>${entregasHTML(d)}</section>
      <section class="cartao meio"><h2>Dúvidas normativas em aberto</h2>${duvidasHTML(d)}</section>
      <section class="cartao"><h2>Normas do escopo</h2>${normasHTML(d)}</section>`;
      return;
    }
    const pend = d.total - d.feitos;
    m.innerHTML = `
    <section class="cartao">
      <h2>Progresso geral</h2>
      <div class="geral">
        <div class="pct">${pct(d.percentual)}<small>%</small></div>
        <div class="geral-info">
          ${barra(d.percentual, "grossa")}
          <div class="legenda"><span>${d.feitos} de ${d.total} tarefas concluídas</span><span>${pend} pendentes</span></div>
          <div class="kpis">
            <div class="kpi"><b>${d.feitos}/${d.total}</b><span>tarefas</span></div>
            <div class="kpi"><b>${(d.disciplinas || []).length}</b><span>frentes de trabalho</span></div>
            <div class="kpi"><b>${(d.normas_cobertas || []).length}</b><span>normas cobertas</span></div>
            <div class="kpi"><b>${d.total_entregas || 0}</b><span>entregas mescladas</span></div>
            <div class="kpi"><b>${(d.duvidas || []).length}</b><span>dúvidas em aberto</span></div>
          </div>
        </div>
      </div>
    </section>
    <section class="cartao meio">
      <h2>Progresso por disciplina</h2>
      ${(d.disciplinas || []).map((x) => `<div class="disc"><div class="disc-top"><span>${esc(x.nome)}</span><span class="n">${x.feitos}/${x.total} · ${pct(x.percentual)}%</span></div>${barra(x.percentual)}</div>`).join("") || `<p class="vazio">Sem disciplinas.</p>`}
    </section>
    <section class="cartao meio">
      <h2>Próximas tarefas</h2>
      ${(d.proximas || []).length ? `<ul class="lista">${d.proximas.map((t) => `<li>${t.id ? `<span class="tid">${esc(t.id)}</span>` : ""}<span>${esc(t.titulo)}<br><span class="sub">${esc(t.disciplina)}${t.normas && t.normas.length ? " · " + esc(t.normas.join(", ")) : ""}</span></span></li>`).join("")}</ul>` : `<p class="vazio">Backlog concluído! 🎉</p>`}
    </section>
    <section class="cartao meio"><h2>Últimas entregas</h2>${entregasHTML(d)}</section>
    <section class="cartao meio"><h2>Dúvidas normativas em aberto</h2>${duvidasHTML(d)}</section>
    <section class="cartao"><h2>Normas</h2>${normasHTML(d)}</section>`;
  }

  fetch("data.json?t=" + Date.now(), { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(render)
    .catch(() => {
      $("#atualizado").textContent = "Sem dados";
      $("#conteudo").innerHTML = `<section class="cartao prep"><h2>Projeto em preparação</h2><p>Os dados do painel ainda não estão disponíveis. Volte em breve.</p></section>`;
    });
})();
