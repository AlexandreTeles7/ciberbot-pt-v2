"""Linha de comandos e orquestração do pipeline diário."""
from __future__ import annotations

import argparse
import logging
import os
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import canais as _canais
from .canais import web as canal_web
from .edicao import Edicao, agrupar, texto_simples
from .estado import Estado
from .fontes import recolher
from .pontuacao import deduplicar, limitar, pontuar
from .traducao import traduzir

log = logging.getLogger("ciberbot")

TITULO_PADRAO = "CiberBot PT — Resumo diário de cibersegurança"


def carregar_config(caminho: str | Path) -> dict:
    with open(caminho, "rb") as f:
        return tomllib.load(f)


def carregar_env(caminho: str | Path = ".env", env: dict | None = None) -> int:
    """Lê linhas CHAVE=valor de um ficheiro .env (se existir) sem substituir variáveis já definidas.

    Devolve o número de variáveis acrescentadas. Os valores nunca são registados.
    """
    env = os.environ if env is None else env
    try:
        linhas = Path(caminho).read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    n = 0
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip().removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if chave and valor and not env.get(chave):
            env[chave] = valor
            n += 1
    return n


def _resumo_actions(env: dict, linhas: list[str]) -> None:
    """Escreve as notas da execução no resumo do GitHub Actions (visível só a quem gere o repositório)."""
    destino = env.get("GITHUB_STEP_SUMMARY")
    if not destino:
        return
    try:
        with open(destino, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
    except OSError:
        pass


def _fuso(cfg: dict):
    nome = cfg.get("geral", {}).get("fuso_horario", "Europe/Lisbon")
    try:
        return ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc  # por exemplo, Windows sem o pacote tzdata


def executar(cfg: dict, env: dict, agora: datetime, *, dry_run: bool = False,
             sem_traducao: bool = False, selecao_canais: list[str] | None = None,
             obter_fn: Callable | None = None, chamar_traducao: Callable | None = None,
             pasta_estado: str | Path | None = None, pasta_previsao: str = "previsao") -> int:
    """Corre o pipeline. Códigos de saída: 0 = ok, 1 = falha total, 3 = falha parcial de canais."""
    geral = cfg.get("geral", {})
    fuso = _fuso(cfg)
    hoje = agora.astimezone(fuso).date()
    janela = int(geral.get("janela_horas", 36))

    # 1. Recolher
    extra = {"obter_fn": obter_fn} if obter_fn else {}
    todos, avisos = recolher(cfg, agora, env, **extra)
    log.info("Recolhidos %d itens de %d fontes", len(todos), len(cfg.get("fontes", [])))
    for a in avisos:
        log.warning(a)
    if not todos and avisos:
        log.error("Nenhuma fonte devolveu dados.")
        return 1

    # 2. Filtrar (janela de tempo + ainda não enviados), pontuar, deduplicar, limitar
    estado = Estado(pasta_estado or geral.get("estado", "state/vistos.json")).carregar()
    if estado.aviso:
        avisos.append(estado.aviso)
    # A janela conta dias de calendário (no fuso configurado): fontes que só indicam a data
    # (como a CISA KEV) não ficam de fora por causa das horas. O estado evita repetições.
    primeiro_dia = (agora - timedelta(hours=janela)).astimezone(fuso).date()
    novos = [i for i in todos
             if i.publicado.astimezone(fuso).date() >= primeiro_dia and not estado.ja_visto(i.id)]
    cves_kev = {c for i in todos if i.categoria == "exploradas" for c in i.cves}
    pontuar(novos, cfg, cves_kev, agora)
    # CVE já enviados noutros dias também contam: o mesmo CVE crítico pode chegar pelo NVD
    # num dia e pela GitHub Advisory Database no seguinte.
    cobertos = cves_kev | estado.cves_enviados()
    escolhidos = limitar(deduplicar(novos, cobertos, estado.titulos_recentes()), cfg)
    if not escolhidos:
        log.info("Sem novidades desde a última edição. Nada a publicar.")
        return 0

    # 3. Traduzir (inglês → português de Portugal)
    if not sem_traducao:
        avisos += traduzir(escolhidos, cfg, env, chamar_traducao)
    for a in avisos:
        if a.startswith("Tradução"):
            log.warning(a)
    traduzidos = sum(1 for i in escolhidos if i.traduzido)
    em_ingles = sum(1 for i in escolhidos if i.em_ingles)
    _resumo_actions(env, [f"## Edição de {hoje.isoformat()}",
                          f"- {len(escolhidos)} destaques; {traduzidos} traduzidos; {em_ingles} em inglês",
                          *[f"- ⚠️ {a}" for a in avisos]])

    ed = Edicao(
        titulo=geral.get("titulo", TITULO_PADRAO),
        data=hoje,
        seccoes=agrupar(escolhidos, geral.get("ordem_seccoes")),
        # As notas técnicas (fontes em baixo, tradução) ficam nos registos; só vão para o
        # público se [geral] notas_publicas = true.
        avisos=avisos if geral.get("notas_publicas", False) else [],
        gerado_em=agora,
        fuso=fuso,
        url_publica=cfg.get("web", {}).get("url_publica", ""),
    )
    log.info("Edição de %s com %d destaques", hoje.isoformat(), ed.total)

    # 4a. Pré-visualização: não envia nada nem altera o estado
    if dry_run:
        print(texto_simples(ed))
        canal_web.enviar(ed, cfg, env, pasta=pasta_previsao)
        log.info("Pré-visualização em %s/index.html (nada foi enviado)", pasta_previsao)
        return 0

    # 4b. Publicar
    nomes = _canais.ativos(cfg, env, selecao_canais)
    if not nomes:
        log.error("Nenhum canal ativo. Defina as variáveis de ambiente (ver .env.example).")
        return 1
    sucessos = 0
    for nome in nomes:
        try:
            log.info("[%s] %s", nome, _canais.CANAIS[nome].enviar(ed, cfg, env))
            sucessos += 1
        except _canais.ErroCanal as e:
            log.error("[%s] falhou: %s", nome, e)
    if sucessos == 0:
        return 1

    # 5. Guardar estado (só depois de pelo menos um canal ter publicado)
    estado.marcar([i.id for i in ed.itens()], hoje)
    estado.registar_titulos(ed.itens(), hoje)
    estado.podar(hoje)
    estado.guardar()
    return 0 if sucessos == len(nomes) else 3


def principal(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["run"] + argv

    p = argparse.ArgumentParser(prog="ciberbot", description="Resumo diário de cibersegurança em PT-PT.")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("run", help="recolhe, traduz e publica o resumo diário")
    r.add_argument("--config", default="config.toml", help="ficheiro de configuração (por omissão: config.toml)")
    r.add_argument("--dry-run", action="store_true",
                   help="não envia nada nem altera o estado; gera uma pré-visualização em ./previsao")
    r.add_argument("--sem-traducao", action="store_true", help="não usa a API de tradução")
    r.add_argument("--canais", help="restringe os canais, separados por vírgulas: web,telegram,email,discord")
    r.add_argument("--janela-horas", type=int, help="substitui a janela de tempo da configuração")
    sub.add_parser("demo", help="gera uma pré-visualização com dados de exemplo (sem rede)")
    args = p.parse_args(argv)

    for fluxo in (sys.stdout, sys.stderr):  # consola do Windows: acentos e emojis sem erros
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    if args.comando == "demo":
        from .demo import executar_demo
        return executar_demo()

    if carregar_env():
        log.info("Variáveis lidas do ficheiro .env")
    try:
        cfg = carregar_config(args.config)
    except (OSError, tomllib.TOMLDecodeError) as e:
        log.error("Não foi possível ler %s: %s", args.config, e)
        return 1
    if args.janela_horas:
        cfg.setdefault("geral", {})["janela_horas"] = args.janela_horas
    selecao = [c.strip() for c in args.canais.split(",")] if args.canais else None
    return executar(cfg, dict(os.environ), datetime.now(timezone.utc), dry_run=args.dry_run,
                    sem_traducao=args.sem_traducao, selecao_canais=selecao)
