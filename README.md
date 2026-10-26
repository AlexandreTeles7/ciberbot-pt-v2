# 🛡️ CiberBot PT (v2)

Bot que recolhe todos os dias as novidades de cibersegurança (ataques, vulnerabilidades, alertas), **traduz para português de Portugal o que estiver em inglês** e publica um resumo ordenado por relevância: **página web** com arquivo diário e, se quiseres, **Telegram, email e Discord**.

Corre sozinho no GitHub Actions (grátis, sem servidor). Não tem dependências externas: só Python 3.11+.

**Funciona sem nenhuma chave nem token.** A tradução usa o GitHub Models com o token automático do GitHub Actions e, como reserva, o serviço gratuito MyMemory. A API da Claude é opcional.

## Como funciona

```
fontes (RSS, CISA KEV, NVD, GitHub Advisories) → últimas 36 h, sem repetir o que já foi enviado
→ pontua e remove duplicados → traduz EN→PT-PT (Claude › GitHub Models › MyMemory)
→ resumo diário → Página web · Telegram · Email · Discord
```

**Secções:** Portugal e em português · Vulnerabilidades exploradas ativamente · Vulnerabilidades críticas recentes · Ataques e notícias.

**Fontes** (editáveis em `config.toml`; todas confirmadas com pedidos reais em 26/10/2026):

| Fonte | Idioma | Notas |
|---|---|---|
| CNCS — Alertas de Segurança | PT | alertas oficiais do Centro Nacional de Cibersegurança |
| Pplware, SAPO Tek | PT | imprensa de tecnologia, filtrada por palavras de cibersegurança |
| CISA KEV | EN | exploração ativa confirmada; indica uso em ransomware |
| NVD (NIST) | EN | só CVE críticos; uma chave gratuita (`NVD_API_KEY`) evita bloqueios |
| GitHub Advisories | EN | vulnerabilidades críticas revistas pelo GitHub (pacotes npm, PyPI, Maven…) |
| BleepingComputer, The Hacker News, Krebs on Security | EN | notícias e ataques |

Se uma fonte falhar, as outras continuam; a falha fica nos registos e no resumo da execução no GitHub Actions (não aparece no site público).

## Tradução

| Tradutor | Precisa de | Qualidade | Notas |
|---|---|---|---|
| `anthropic` (Claude) | segredo `ANTHROPIC_API_KEY` | a melhor | tem custo (baixo); usado primeiro se existir |
| `github` (GitHub Models) | nada no Actions (`GITHUB_TOKEN` automático) | muito boa | grátis, com limite diário de pedidos largamente suficiente |
| `mymemory` | nada | razoável | grátis, ~5000 caracteres/dia; o bot corrige o português do Brasil mais comum |

Se um tradutor falhar, os itens em falta passam para o seguinte. Se todos falharem, o item fica em inglês, assinalado «Em inglês». A ordem muda-se em `[traducao] fornecedores`.

## Instalação

1. **Site:** *Settings → Pages → Deploy from a branch → `main` / pasta `/docs`*.
2. **Primeira execução:** *Actions → Resumo diário → Run workflow*. A partir daí corre todos os dias às 05:17 UTC (06:17 no verão em Lisboa; o GitHub pode atrasar).
3. **Canais opcionais** (*Settings → Secrets and variables → Actions → New repository secret*; nomes iguais aos de `.env.example`):
   - **Telegram:** fala com o `@BotFather`, cria um bot e guarda o token em `TELEGRAM_BOT_TOKEN`. Envia uma mensagem ao bot e abre `https://api.telegram.org/bot<TOKEN>/getUpdates` para encontrares `"chat":{"id": ...}`; guarda esse número em `TELEGRAM_CHAT_ID`.
   - **Discord:** no canal, *Editar canal → Integrações → Webhooks → Novo webhook → Copiar URL* para `DISCORD_WEBHOOK_URL`.
   - **Email:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_DE` e `EMAIL_PARA`. No Gmail: `smtp.gmail.com`, porta `587` e uma *palavra-passe de aplicação*.
4. **Extras opcionais:** `NVD_API_KEY` (gratuita, em https://nvd.nist.gov/developers/request-an-api-key) e `ANTHROPIC_API_KEY`.

## Experimentar no computador

```bash
python -m ciberbot demo                     # pré-visualização com dados de exemplo, sem rede (previsao/index.html)
python -m unittest discover -s tests        # testes (sem rede)
python -m ciberbot run --dry-run            # fontes reais, sem enviar nada nem gravar estado
python -m ciberbot run --canais telegram    # só um canal
```

O bot lê o ficheiro `.env` (copia `.env.example`), sem substituir variáveis já definidas.

## Personalizar (`config.toml`)

- **Fontes:** blocos `[[fontes]]` com `tipo` `rss`, `kev`, `nvd` ou `ghsa`. `idioma = "pt"` não traduz; `palavras_obrigatorias` filtra feeds generalistas.
- **Relevância:** `[palavras_chave]` e o `peso` de cada fonte.
- **Tamanho:** `max_itens`, `[limites]` por secção, `max_itens` por fonte e `janela_horas`.
- **Notas técnicas no site:** `[geral] notas_publicas = true` (por omissão ficam só nos registos).

## Segurança e limites

- Todo o texto vindo da internet é escapado (HTML, Telegram, Discord, email); só se aceitam ligações `http(s)`; o Discord nunca menciona ninguém.
- O prompt de tradução trata o conteúdo como dados e ignora instruções lá escritas.
- Segredos só em variáveis de ambiente; as mensagens de erro mostram apenas o nome do servidor.
- O bot identifica-se honestamente (`User-Agent` com o endereço do projeto) e não contorna proteções anti-robôs: um site que o bloqueie é retirado das fontes.
- A tradução é automática: confirma os detalhes críticos na fonte original (o link vai sempre com cada item).

## Estrutura

```
ciberbot/            código (fontes.py, pontuacao.py, traducao.py, edicao.py, estado.py, cli.py, canais/)
config.toml          fontes, tradutores, limites e palavras-chave
.github/workflows/   agendamento diário (testes → resumo → commit)
docs/                site gerado (GitHub Pages)
state/vistos.json    memória do que já foi enviado
tests/               testes e dados de exemplo
contexto/            notas do projeto (estado, decisões, arquitetura)
```
