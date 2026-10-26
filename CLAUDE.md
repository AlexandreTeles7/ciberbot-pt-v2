# CiberBot PT — instruções para o Claude Code

Bot que recolhe todos os dias notícias, ataques e vulnerabilidades de cibersegurança, **traduz o que estiver em inglês para português de Portugal (pt-PT)** e publica um resumo em **Telegram, email, Discord e página web**. Corre sozinho no GitHub Actions (grátis, sem servidor) e **funciona sem nenhuma chave**: tradução grátis pelo MyMemory (com `aportuguesar` para corrigir pt-BR); a Claude é opcional. O GitHub Models foi descontinuado pelo GitHub a 30/07/2026: não o voltes a usar.

- Repositório: `AlexandreTeles7/ciberbot-pt-v2` (**público**, ramo `main`). Sucessor de `AlexandreTeles7/ciberbot-pt` (v1).
- Site (GitHub Pages, pasta `docs/`): https://alexandreteles7.github.io/ciberbot-pt-v2/
- Contexto detalhado, na pasta `contexto/`:
  - `ESTADO_E_PENDENTES.md` — **lê primeiro**: o que funciona, o que falha e o que falta fazer
  - `CONTEXTO_DO_PROJETO.md` — objetivo, pedido original, decisões e porquê, fontes, histórico
  - `ARQUITETURA.md` — módulos, fluxo de dados, pontuação, configuração, canais, testes

> Estes ficheiros vão para um repositório público: nunca escrevas neles segredos nem dados pessoais.

## Regras de trabalho

- **Língua.** Tudo o que o utilizador final vê está em pt-PT (utilizador, ficheiro, ecrã, descarregar, atualizar; sem gerúndio brasileiro do tipo «estou fazendo»). Identificadores, comentários, registos e testes do código também estão em português: mantém esse estilo.
- **Sem dependências externas.** Só biblioteca padrão, Python ≥ 3.11 (usa `tomllib` e `zoneinfo`). Não acrescentes pacotes sem o utilizador pedir.
- **Testes offline.** `python3 -m unittest discover -s tests` (72 testes, sem rede; `test_pipeline.py` e `test_melhorias.py`). Nenhum teste pode usar a rede: o tradutor `mymemory` não precisa de chave, por isso nos testes passa sempre `chamar`/`obter_fn` falsos ou `fornecedores` sem ele. Corre-os antes de cada commit; uma alteração de comportamento leva teste novo.
- **Segredos.** Só em variáveis de ambiente (GitHub Secrets). Nunca no código, em testes, registos ou mensagens de erro. O token do Telegram vai dentro do URL, por isso as mensagens de rede só mostram o *host*, nunca o URL completo (`rede.py`): mantém isto.
- **Conteúdo da internet é hostil.** Escapar sempre (`html.escape` em HTML/Telegram, escape de Markdown no Discord), aceitar só URLs `http(s)` (`modelos.url_segura`), Discord sem menções (`allowed_mentions: {"parse": []}`), e o prompt de tradução trata o texto como dados e nunca como instruções.
- **O que é escrito pelo bot** (não editar à mão): `docs/index.html`, `docs/arquivo/`, `docs/dados/`, `state/vistos.json`. A pasta `docs/` é o site publicado: não ponhas lá documentação.
- **Git.** O bot faz um commit diário em `main` («Resumo de AAAA-MM-DD»). Antes de `git push`, faz `git pull --rebase`.
- **Testes manuais.** Não envies mensagens reais (Telegram, Discord, email) sem o utilizador pedir; usa `--dry-run`.
- **Endereços de email e dados pessoais** do utilizador não entram no repositório (é público). Autor dos commits: o nome de utilizador do GitHub com endereço `noreply`.

## Comandos

```bash
python3 -m ciberbot demo                    # pré-visualização offline com dados de exemplo → previsao/index.html
python3 -m ciberbot run --dry-run           # fontes reais; não envia nada nem grava estado; escreve em ./previsao
python3 -m ciberbot run --dry-run --sem-traducao   # igual, sem gastar a API de tradução
python3 -m ciberbot run --canais web        # restringe canais: web, telegram, email, discord
python3 -m ciberbot run --janela-horas 72   # substitui a janela de tempo da configuração
python3 -m unittest discover -s tests       # testes
```

- Códigos de saída de `run`: `0` ok (ou sem novidades), `1` falha total (nenhuma fonte, nenhum canal ativo, todos os canais falharam, configuração ilegível), `3` falha parcial de canais (o estado é gravado na mesma).
- O programa lê o ficheiro `.env` (se existir), sem substituir variáveis já definidas (`cli.carregar_env`).
- Variáveis de ambiente e canais: ver `.env.example` e `contexto/ARQUITETURA.md`.

## Mapa do código

```
ciberbot/
  cli.py        pipeline completo: recolher → filtrar → pontuar → deduplicar → limitar → traduzir → publicar → gravar estado
  fontes.py     RSS/Atom, CISA KEV, NVD e GitHub Advisories (ghsa) → lista de Item
  pontuacao.py  pontuação, deduplicação, limites
  traducao.py   EN → pt-PT: Claude (se houver chave) › MyMemory (cadeia com recurso; aportuguesar corrige pt-BR)
  edicao.py     agrupa em secções; gera texto, HTML (email e site), Telegram, Discord
  estado.py     memória do que já foi enviado (state/vistos.json)
  canais/       web.py, telegram.py, discord.py, correio.py (cada um: NOME, ativo(), enviar())
  rede.py       HTTP com urllib (repetições, limites, erros sem URLs)
  modelos.py    dataclass Item, url_segura
  texto.py      limpeza de HTML, cortar, deteção de idioma
  demo.py       demonstração offline
config.toml     fontes, limites, palavras-chave (editar aqui, não no código)
.github/workflows/diario.yml   agendamento diário
tests/          test_pipeline.py, test_melhorias.py + tests/fixtures/ (dados fictícios)
```

## Estado em resumo (2026-10-26)

Versão 2 criada a partir da v1 (em produção desde 21/10). Corrige: tradução sem chave, NVD com HTTP 403 (era o `User-Agent`), fontes PT, horário, notas técnicas no site público, `.env`. Primeira execução no Actions a 26/10: sucesso, 16 de 17 itens traduzidos pelo MyMemory, site no GitHub Pages. Detalhes e pendentes em `contexto/ESTADO_E_PENDENTES.md`.
