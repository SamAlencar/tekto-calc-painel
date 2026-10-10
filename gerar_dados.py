#!/usr/bin/env python3
"""Gera data.json do Painel Tekto a partir dos repositórios privados da Tekto.

Para cada projeto em PROJETOS, lê (somente leitura, via `gh api`) docs/BACKLOG.md,
docs/DUVIDAS.md e os PRs mesclados. Publica apenas metadados de progresso —
nunca código. Faz commit+push no repositório do painel só se os dados mudaram.
Uso: python3 gerar_dados.py [--sem-push]
"""
import json, os, re, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO — para acompanhar um novo projeto, basta acrescentar um item.
#   slug:   identificador curto usado na URL do painel (#slug)
#   nome:   nome exibido
#   repo:   repositório privado (dono/nome), lido só via gh api
#   descricao: subtítulo do cartão
#   prefixo: prefixo dos IDs de tarefa (informativo)
#   normas_escopo: (opcional) lista (código, descrição) exibida mesmo sem tarefas
# ---------------------------------------------------------------------------
PROJETOS = [
    {
        "slug": "calc", "nome": "Tekto Calc", "repo": "SamAlencar/tekto-calc", "prefixo": "TC",
        "descricao": "Rotinas de cálculo de engenharia em Python",
        "normas_escopo": [
            ("NBR 6118", "Concreto armado e protendido"),
            ("NBR 8800", "Estruturas de aço"),
            ("NBR 14762", "Perfis de aço formados a frio"),
            ("NBR 7190", "Estruturas de madeira"),
            ("NBR 6122", "Fundações"),
            ("NBR 6120", "Ações para o cálculo de estruturas"),
            ("NBR 8681", "Ações e segurança nas estruturas"),
            ("NBR 5410", "Instalações elétricas de baixa tensão"),
            ("NBR 5626", "Água fria e água quente"),
            ("NBR 8160", "Esgoto sanitário"),
            ("NBR 10844", "Águas pluviais"),
        ],
    },
    {
        "slug": "docs", "nome": "Tekto Docs", "repo": "SamAlencar/tekto-docs", "prefixo": "TD",
        "descricao": "Memoriais, especificações, laudos e fichas técnicas",
    },
    {
        "slug": "model", "nome": "Tekto Model", "repo": "SamAlencar/tekto-model", "prefixo": "TM",
        "descricao": "Modelagem e BIM",
    },
]
CAMINHO_BACKLOG = "docs/BACKLOG.md"
CAMINHO_DUVIDAS = "docs/DUVIDAS.md"

DIR = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(DIR, "data.json")
TZ = ZoneInfo("America/Sao_Paulo")

RE_NORMA = re.compile(r"\bNBR\s*(ISO(?:/IEC)?\s*)?(\d{4,5})(?:-\d+)?(?:[:\s]*(\d{4})\b)?", re.I)
RE_ID = re.compile(r"`?\b([A-Z]{1,6}(?:[-_.][A-Z0-9]{1,6})*[-_.]?\d{1,4}(?:\.\d+)?)\b`?")
RE_CHECK = re.compile(r"^\s*[-*+]\s*\[([ xX~\-])\]\s*(.+)$")
RE_TAREFA_HEAD = re.compile(r"^\s*(?:\[[ xX]\]\s*)?`?\*{0,2}[A-Z]{1,6}(?:[-_.][A-Z0-9]{1,6})*[-_.]?\d{1,4}(?:\.\d+)?\b")
RE_CAMPO = re.compile(r"^\s*[-*+]\s*\*{0,2}([A-Za-zÀ-ú ]{3,30}?)\*{0,2}\s*:\s*\*{0,2}\s*(.*)$")
RE_HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FEITO_TXT = re.compile(r"\[x\]|✅|✔|☑|\bfeit[oa]\b|\bconclu[ií]d[oa]\b|\bdone\b|\bok\b|\bmesclad[oa]\b", re.I)
PEND_TXT = re.compile(r"\[ \]|⬜|☐|pendente|a fazer|todo|em andamento|aberto", re.I)


def gh_api(path, raw=False):
    cmd = ["gh", "api", path]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if "404" in (r.stderr + r.stdout) or "Not Found" in (r.stderr + r.stdout):
            return None
        raise RuntimeError(f"gh api {path} falhou: {r.stderr.strip()}")
    return r.stdout if raw else json.loads(r.stdout)


def limpa(t):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)  # links md -> texto
    t = re.sub(r"\*\*|__|`|(?<!\w)[*_]|[*_](?!\w)", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip(" -–—|:;")


def normas_em(t):
    out = []
    for m in RE_NORMA.finditer(t):
        n = f"NBR {'ISO ' if m.group(1) else ''}{m.group(2)}"
        if n not in out:
            out.append(n)
    return out


RE_OUTRAS = re.compile(r"\b(?:ISO(?:/IEC)?|IEC|EN|NR)[\s-]*\d{2,5}(?:-\d+)?|\bIFC\s*\d(?:\.\d)*", re.I)


def referencias_em(valor):
    """Códigos de norma do campo (NBR, ISO, IEC, NR, IFC...). Se não houver código,
    os itens curtos separados por ';' entram como texto (ex.: 'buildingSMART IDS')."""
    out = normas_em(valor)
    resto = RE_NORMA.sub(" ", valor)
    for m in RE_OUTRAS.finditer(resto):
        c = re.sub(r"\s+", " ", m.group(0).upper().replace("IFC", "IFC ")).strip().replace("  ", " ")
        if c not in out:
            out.append(c)
    if out:
        return out
    for parte in valor.split(";"):
        t = limpa(re.split(r"\.\s", re.sub(r"<[^>]*>|https?://\S+", "", parte))[0])
        if 2 <= len(t) <= 40 and not re.search(r"\b(nenhum\w*|n/a|não se aplica|a definir)\b", t, re.I) and t not in out:
            out.append(t)
    return out


def separa_tarefa(texto, disciplina):
    bruto = texto
    tid = None
    m = RE_ID.search(texto[:40])
    if m and not RE_NORMA.match(texto[m.start():]) and not m.group(1).upper().startswith("NBR"):
        tid = m.group(1)
        texto = texto[:m.start()] + texto[m.end():]
    normas = normas_em(bruto)
    titulo = limpa(texto)
    # corta critério de pronto / referência longa depois de separadores
    for sep in [" — ", " – ", " | ", " -- "]:
        partes = titulo.split(sep)
        if len(partes) > 1 and len(partes[0]) >= 6:
            titulo = partes[0]
            break
    titulo = re.sub(r"\(\s*(ABNT\s*)?NBR[^)]*\)", "", titulo).strip(" -–—:;")
    return {"id": tid, "titulo": titulo[:160], "normas": normas, "disciplina": disciplina}


def parse_backlog(md):
    tarefas, disc, headers, atual = [], "Geral", None, None
    for linha in md.splitlines():
        h = RE_HEAD.match(linha)
        if h:
            nivel = len(h.group(1))
            headers, atual = None, None
            # Formato "### TC-001 — Título" (tarefa como cabeçalho, campos em bullets)
            mt = RE_TAREFA_HEAD.match(h.group(2)) if nivel >= 3 else None
            if mt:
                t = separa_tarefa(h.group(2), disc)
                t["feito"] = bool(re.search(r"\[x\]|✅|✔", h.group(2), re.I))
                t["_status_explicito"] = False
                if t["titulo"]:
                    tarefas.append(t)
                    atual = t
                continue
            if nivel >= 2:
                disc = limpa(re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", h.group(2))) or disc
            continue
        if atual is not None:
            mc = RE_CAMPO.match(linha)
            if mc:
                chave, valor = limpa(mc.group(1)).lower(), mc.group(2)
                if chave.startswith(("status", "situa", "estado")):
                    atual["feito"] = bool(FEITO_TXT.search(valor)) and not re.search(r"\[ \]", valor)
                    atual["_status_explicito"] = True
                elif chave.startswith(("norma", "refer")):
                    for n in referencias_em(valor):
                        if n not in atual["normas"]:
                            atual["normas"].append(n)
                elif chave.startswith("depende"):
                    atual["depende"] = [x for x in re.findall(r"[A-Z]{1,6}-?\d{1,4}", valor)]
                continue
        c = RE_CHECK.match(linha)
        if c and not linha.startswith((" " * 4, "\t")):
            t = separa_tarefa(c.group(2), disc)
            t["feito"] = c.group(1) in "xX"
            if t["titulo"]:
                tarefas.append(t)
            continue
        s = linha.strip()
        if s.startswith("|") and s.count("|") >= 3:
            cels = [x.strip() for x in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", x) for x in cels if x):
                continue
            if headers is None:
                headers = [limpa(x).lower() for x in cels]
                continue
            row = dict(zip(headers, cels))
            def col(*nomes):
                for k, v in row.items():
                    if any(n in k for n in nomes):
                        return v
                return None
            st = col("status", "situa", "estado", "feito") or ""
            idc = col("id", "cód", "cod", "#")
            tit = col("tarefa", "título", "titulo", "descri", "item") or (cels[1] if len(cels) > 1 else cels[0])
            nor = col("norma", "refer")
            if not limpa(tit):
                continue
            if not st:
                st = " ".join(cels)
            feito = bool(FEITO_TXT.search(st)) and not re.search(r"\[ \]", st)
            t = separa_tarefa(tit, disc)
            if idc and limpa(idc):
                t["id"] = limpa(idc)
            if nor:
                t["normas"] = normas_em(nor) or t["normas"]
            t["feito"] = feito
            tarefas.append(t)
        elif s and not s.startswith("|"):
            if not RE_CHECK.match(linha) and not linha.startswith((" ", "\t")):
                headers = None
    for t in tarefas:
        t.pop("_status_explicito", None)
        t.pop("depende", None)
    return tarefas


def duvida_resolvida(st):
    if re.search(r"\[x\]|✅|✔", st, re.I):
        return True
    if re.search(r"\[ \]|parcial|em aberto|pendente", st, re.I):
        return False
    return bool(re.search(r"resolvid|respondid|fechad|encerrad", st, re.I))


def parse_duvidas(md):
    abertas, secao_fechada, atual = [], False, None
    tem_check = any(RE_CHECK.match(l) for l in md.splitlines())
    for linha in md.splitlines():
        h = RE_HEAD.match(linha)
        if h:
            nivel, txt = len(h.group(1)), limpa(h.group(2))
            if nivel <= 2 and re.search(r"resolvid|fechad|respondid|encerrad", txt, re.I):
                secao_fechada = True
                continue
            if nivel <= 2 and re.search(r"abert|pendente|em aberto", txt, re.I):
                secao_fechada = False
                continue
            if nivel >= 3 and not secao_fechada and txt:
                if re.search(r"resolvid|\[x\]|✅", h.group(2), re.I):
                    continue
                atual = {"texto": txt[:300], "normas": normas_em(txt)}
                abertas.append(atual)
            continue
        if secao_fechada:
            continue
        mc = RE_CAMPO.match(linha)
        if atual is not None and mc and limpa(mc.group(1)).lower().startswith(("status", "situa", "estado")):
            if duvida_resolvida(mc.group(2)) and atual in abertas:
                abertas.remove(atual)
            continue
        if atual is not None and mc:
            continue
        c = RE_CHECK.match(linha)
        if c and not linha.startswith((" ", "\t")):
            if c.group(1) in "xX":
                continue
            txt = limpa(c.group(2))
            if txt and not re.search(r"\bresolvid", txt, re.I):
                abertas.append({"texto": txt[:300], "normas": normas_em(txt)})
            continue
        m = re.match(r"^[-*+]\s+(.+)$", linha)
        if m and not tem_check:
            txt = limpa(m.group(1))
            if txt and atual is None and not re.search(r"\bresolvid", txt, re.I):
                abertas.append({"texto": txt[:300], "normas": normas_em(txt)})
    return abertas


def prs_mesclados(repo):
    prs = gh_api(f"repos/{repo}/pulls?state=closed&per_page=100&sort=updated&direction=desc") or []
    out = []
    for p in prs:
        if not p.get("merged_at"):
            continue
        dt = datetime.fromisoformat(p["merged_at"].replace("Z", "+00:00")).astimezone(TZ)
        out.append({"numero": p["number"], "titulo": p["title"].strip()[:200],
                    "data": dt.isoformat(timespec="minutes")})
    out.sort(key=lambda x: x["data"], reverse=True)
    return out


def gerar_projeto(cfg):
    repo = cfg["repo"]
    info = gh_api(f"repos/{repo}")
    branch = info["default_branch"] if info else "main"
    backlog = gh_api(f"repos/{repo}/contents/{CAMINHO_BACKLOG}?ref={branch}", raw=True) if info else None
    duvidas = gh_api(f"repos/{repo}/contents/{CAMINHO_DUVIDAS}?ref={branch}", raw=True) if info else None
    tarefas = parse_backlog(backlog) if backlog else []
    entregas = prs_mesclados(repo) if info else []

    areas = {}
    for t in tarefas:
        d = areas.setdefault(t["disciplina"], {"nome": t["disciplina"], "total": 0, "feitos": 0})
        d["total"] += 1
        d["feitos"] += t["feito"]
    for d in areas.values():
        d["percentual"] = round(100 * d["feitos"] / d["total"], 1) if d["total"] else 0

    total = len(tarefas)
    feitos = sum(t["feito"] for t in tarefas)
    escopo = cfg.get("normas_escopo", [])
    conhecidas = [n for n, _ in escopo]
    vistas = []
    for t in tarefas:
        vistas += [n for n in t["normas"] if n not in vistas and n not in conhecidas]
    normas = []
    for n, desc in list(escopo) + [(n, "") for n in vistas]:
        nt = sum(1 for t in tarefas if n in t["normas"])
        nf = sum(1 for t in tarefas if t["feito"] and n in t["normas"])
        estado = "coberta" if nt and nf == nt else "em_andamento" if nf else "planejada" if nt else "futura"
        normas.append({"norma": n, "descricao": desc, "tarefas": nt, "feitas": nf, "estado": estado})
    lista_duv = parse_duvidas(duvidas) if duvidas else []

    return {
        "slug": cfg["slug"],
        "nome": cfg["nome"],
        "descricao": cfg.get("descricao", ""),
        "estado": "ativo" if total else "preparacao",
        "repo_encontrado": info is not None,
        "backlog_encontrado": backlog is not None,
        "duvidas_encontrado": duvidas is not None,
        "total": total,
        "feitos": feitos,
        "percentual": round(100 * feitos / total, 1) if total else 0,
        "areas": list(areas.values()),
        "proximas": [{k: t[k] for k in ("id", "titulo", "normas", "disciplina")} for t in tarefas if not t["feito"]][:8],
        "entregas": entregas[:12],
        "total_entregas": len(entregas),
        "ultima_entrega": entregas[0]["data"] if entregas else None,
        "normas": normas,
        "normas_cobertas": sorted({n for t in tarefas if t["feito"] for n in t["normas"]}),
        "duvidas": lista_duv,
    }


def gerar():
    projetos = [gerar_projeto(c) for c in PROJETOS]
    total = sum(p["total"] for p in projetos)
    feitos = sum(p["feitos"] for p in projetos)
    datas = [p["ultima_entrega"] for p in projetos if p["ultima_entrega"]]
    return {
        "painel": "Painel Tekto",
        "geral": {
            "total": total, "feitos": feitos,
            "percentual": round(100 * feitos / total, 1) if total else 0,
            "duvidas": sum(len(p["duvidas"]) for p in projetos),
            "entregas": sum(p["total_entregas"] for p in projetos),
            "ultima_entrega": max(datas) if datas else None,
            "projetos_ativos": sum(p["estado"] == "ativo" for p in projetos),
        },
        "projetos": projetos,
    }


def git(*a):
    return subprocess.run(["git", "-C", DIR, *a], capture_output=True, text=True, check=True).stdout


def main():
    dados = gerar()
    antigo = None
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            antigo = json.load(f)
    comparar = lambda d: {k: v for k, v in (d or {}).items() if k != "atualizado_em"}
    if antigo and comparar(antigo) == dados:
        print("Sem mudanças nos dados; nada a publicar.")
        return
    dados = {"atualizado_em": datetime.now(TZ).isoformat(timespec="minutes"), **dados}
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    resumo = ", ".join(f"{p['nome']} {p['feitos']}/{p['total']}" for p in dados["projetos"])
    print(f"data.json atualizado: {resumo}")
    if "--sem-push" in sys.argv:
        return
    git("add", "data.json")
    if not git("status", "--porcelain", "data.json").strip():
        return
    git("commit", "-m", f"Atualiza dados do painel ({resumo})")
    git("push", "origin", "HEAD:main")
    print("Publicado no GitHub Pages.")


if __name__ == "__main__":
    main()
