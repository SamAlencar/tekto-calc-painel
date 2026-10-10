#!/usr/bin/env python3
"""Gera data.json do painel Tekto Calc a partir do repositório privado.

Lê (somente leitura, via `gh api`) docs/BACKLOG.md, docs/DUVIDAS.md e os PRs
mesclados de SamAlencar/tekto-calc. Publica apenas metadados de progresso —
nunca código. Faz commit+push no repositório do painel só se os dados mudaram.
Uso: python3 gerar_dados.py [--sem-push]
"""
import json, os, re, subprocess, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

REPO_PRIVADO = "SamAlencar/tekto-calc"
DIR = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(DIR, "data.json")
TZ = ZoneInfo("America/Sao_Paulo")

NORMAS_PROJETO = [
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
]

RE_NORMA = re.compile(r"\bNBR\s*(\d{4,5})(?:[-:\s]*(\d{4}))?", re.I)
RE_ID = re.compile(r"`?\b([A-Z]{1,6}(?:[-_.][A-Z0-9]{1,6})*[-_.]?\d{1,4}(?:\.\d+)?)\b`?")
RE_CHECK = re.compile(r"^\s*[-*+]\s*\[([ xX~\-])\]\s*(.+)$")
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
        n = f"NBR {m.group(1)}"
        if n not in out:
            out.append(n)
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
    tarefas, disc, headers = [], "Geral", None
    for linha in md.splitlines():
        h = RE_HEAD.match(linha)
        if h:
            nivel = len(h.group(1))
            if nivel >= 2:
                disc = limpa(re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", h.group(2))) or disc
            headers = None
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
    return tarefas


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


def prs_mesclados():
    prs = gh_api(f"repos/{REPO_PRIVADO}/pulls?state=closed&per_page=100&sort=updated&direction=desc") or []
    out = []
    for p in prs:
        if not p.get("merged_at"):
            continue
        dt = datetime.fromisoformat(p["merged_at"].replace("Z", "+00:00")).astimezone(TZ)
        out.append({"numero": p["number"], "titulo": p["title"].strip()[:200],
                    "data": dt.isoformat(timespec="minutes")})
    out.sort(key=lambda x: x["data"], reverse=True)
    return out


def gerar():
    repo = gh_api(f"repos/{REPO_PRIVADO}")
    branch = repo["default_branch"] if repo else "main"
    backlog = gh_api(f"repos/{REPO_PRIVADO}/contents/docs/BACKLOG.md?ref={branch}", raw=True)
    duvidas = gh_api(f"repos/{REPO_PRIVADO}/contents/docs/DUVIDAS.md?ref={branch}", raw=True)
    tarefas = parse_backlog(backlog) if backlog else []
    entregas = prs_mesclados() if repo else []

    disciplinas = {}
    for t in tarefas:
        d = disciplinas.setdefault(t["disciplina"], {"nome": t["disciplina"], "total": 0, "feitos": 0, "normas": []})
        d["total"] += 1
        d["feitos"] += t["feito"]
        for n in t["normas"]:
            if n not in d["normas"]:
                d["normas"].append(n)
    for d in disciplinas.values():
        d["percentual"] = round(100 * d["feitos"] / d["total"], 1) if d["total"] else 0

    total = len(tarefas)
    feitos = sum(t["feito"] for t in tarefas)
    cobertas = {n for t in tarefas if t["feito"] for n in t["normas"]}
    planejadas = {n for t in tarefas for n in t["normas"]}
    normas = []
    conhecidas = [n for n, _ in NORMAS_PROJETO]
    for n, desc in NORMAS_PROJETO + [(n, "") for n in sorted(planejadas) if n not in conhecidas]:
        nt = sum(1 for t in tarefas if n in t["normas"])
        nf = sum(1 for t in tarefas if t["feito"] and n in t["normas"])
        estado = "coberta" if nt and nf == nt else "em_andamento" if nf else "planejada" if nt else "futura"
        normas.append({"norma": n, "descricao": desc, "tarefas": nt, "feitas": nf, "estado": estado})

    return {
        "projeto": "Tekto Calc",
        "estado": "ativo" if total else "preparacao",
        "backlog_encontrado": backlog is not None,
        "total": total,
        "feitos": feitos,
        "percentual": round(100 * feitos / total, 1) if total else 0,
        "disciplinas": list(disciplinas.values()),
        "proximas": [{k: t[k] for k in ("id", "titulo", "normas", "disciplina")} for t in tarefas if not t["feito"]][:8],
        "entregas": entregas[:12],
        "total_entregas": len(entregas),
        "normas": normas,
        "normas_cobertas": sorted(cobertas),
        "duvidas": parse_duvidas(duvidas) if duvidas else [],
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
    print(f"data.json atualizado: {dados['feitos']}/{dados['total']} tarefas, estado={dados['estado']}")
    if "--sem-push" in sys.argv:
        return
    git("add", "data.json")
    if not git("status", "--porcelain", "data.json").strip():
        return
    git("commit", "-m", f"Atualiza dados do painel ({dados['feitos']}/{dados['total']})")
    git("push", "origin", "HEAD:main")
    print("Publicado no GitHub Pages.")


if __name__ == "__main__":
    main()
