# CiberBot PT v2 — estado e pendentes

> Atualizado em **2026-10-26**. Ficheiro para repositório público: sem segredos nem dados pessoais.
> O histórico da v1 (repositório `ciberbot-pt`, 21–26/10/2026) está em `CONTEXTO_DO_PROJETO.md`.

## 1. Porquê uma v2

A v1 corria todos os dias sem erros, mas falhava no essencial: **0 de 61 itens traduzidos** (não havia `ANTHROPIC_API_KEY`), o NVD dava HTTP 403 todos os dias, a única fonte portuguesa com conteúdo era o CNCS e o resumo chegava 5–7 horas atrasado. O utilizador não tem (nem quer, para já) chaves de API: a v2 tem de funcionar sem nenhuma.

## 2. O que mudou (verificado localmente em 26/10/2026)

| Problema da v1 | Solução na v2 | Verificação |
|---|---|---|
| Tradução só pela Claude (sem chave → nada traduzido) | Cadeia de tradutores `anthropic › github › mymemory` (`[traducao] fornecedores`). O GitHub Models usa o `GITHUB_TOKEN` automático do Actions (`permissions: models: read`). O MyMemory não precisa de chave (~5000 caracteres/dia; os itens mais relevantes primeiro). `aportuguesar()` corrige o pt-BR mais comum do MyMemory. | `--dry-run` local: 16 itens traduzidos pelo MyMemory. **GitHub Models não testado** (precisa do token do Actions). |
| NVD: HTTP 403 | A causa era o `User-Agent` com «ç»: com o UA novo, só ASCII (`CiberBotPT/2.0 (+URL do projeto)`), o NVD respondeu 200 no mesmo computador onde o UA antigo dava 403. Erros 403 passam a indicar «bloqueado pela proteção anti-robôs» quando é o caso. | `--dry-run` local: 6 CVE críticos do NVD. Falta confirmar a partir dos IP do GitHub. |
| Sem segunda fonte de vulnerabilidades críticas | Nova fonte `ghsa` (GitHub Advisory Database, revistas e críticas). O mesmo CVE do NVD e do GHSA só aparece uma vez, também entre dias (`Estado.cves_enviados`). | Testes + pedido real à API. |
| «Segurança Informática» sem itens | O site bloqueia robôs (Cloudflare, HTTP 403). Retirado. Não se contornam proteções anti-robôs. | Pedido real. |
| Pouco conteúdo em português | Pplware e SAPO Tek com `palavras_obrigatorias` de cibersegurança. Secção renomeada «Portugal e em português». | Pedido real (Pplware: 2 de 12 itens passaram o filtro; SAPO Tek: 0 nesse dia). 4gnews testado e **rejeitado** (o filtro deixava passar ruído). |
| The Hacker News domina | `max_itens = 5`. | — |
| Agendamento 5–7 h atrasado | `cron "17 5 * * *"` (minuto «estranho», mais cedo). | **Por medir** nos próximos dias. |
| Notas técnicas no site público | Por omissão ficam nos registos e no resumo da execução do Actions (`GITHUB_STEP_SUMMARY`); `[geral] notas_publicas = true` repõe o comportamento antigo. | Testes. |
| `.env` não era lido | `cli.carregar_env()` lê `.env` sem substituir variáveis existentes. | Testes. |
| Acentos rebentavam a consola do Windows | `stdout`/`stderr` em UTF-8. | `demo` no Windows. |
| Workflow sem testes nem `pull --rebase` | Passo «Testes (sem rede)» antes do resumo; `git pull --rebase` antes do `push`. | — |

Testes: 73 (51 da v1, adaptados, + 22 em `tests/test_melhorias.py`), todos offline.

## 3. Pendentes, por prioridade

### P1 — Primeira execução no GitHub Actions
Ativar o GitHub Pages (*Settings → Pages → `main` / `docs`*) e correr *Actions → Resumo diário → Run workflow*. Confirmar no resumo da execução: quantos itens foram traduzidos e por que tradutor («Tradução: N itens traduzidos por github»), e se o NVD respondeu.
Se o GitHub Models falhar (modelo indisponível, permissão em falta), o MyMemory entra sozinho; corrigir `[traducao] modelo_github` se a API disser que o modelo não existe.

### P2 — Rever a qualidade do pt-PT
Ler algumas edições. Se aparecer pt-BR, acrescentar pares a `PT_BR_PARA_PT` em `traducao.py` (só afeta o MyMemory) ou reforçar o prompt `SISTEMA`.

### P3 — Medir o horário
Ver a que horas arrancam as execuções agendadas com `17 5 * * *`. Se continuar muito atrasado: disparo externo por `workflow_dispatch`.

### P4 — Desligar a v1
Enquanto as duas versões estiverem ativas, há dois resumos por dia. Quando a v2 estiver confirmada: no repositório `ciberbot-pt`, *Actions → Resumo diário → «…» → Disable workflow* (ou arquivar o repositório). Se a v1 tinha segredos de canais (Telegram, Discord, email), copiá-los para a v2.

### P5 — Mais fontes em português
Continuar a procurar fontes pt-PT de cibersegurança com RSS que aceitem robôs. Confirmar sempre com um pedido real (`rede.obter`) antes de as pôr na configuração.

### P6 — Opcionais
- `NVD_API_KEY` (gratuita) se o NVD voltar a dar 403 a partir do GitHub.
- `ANTHROPIC_API_KEY` se se quiser a melhor qualidade de tradução (tem custo).
- Funcionalidades não pedidas: comando `/pesquisar` no Telegram, alertas imediatos, resumo semanal.

## 4. Riscos conhecidos
- GitHub Models e MyMemory são serviços gratuitos: podem mudar limites ou condições. A cadeia de recurso e o aviso «Em inglês» evitam perder informação.
- O texto enviado ao MyMemory vai no URL do pedido (é a API deles); só se envia texto público das notícias.
- A tradução é automática: manter sempre o aviso e o link para a fonte.
- A data da KEV assume 12:00 UTC (a fonte só dá o dia).
