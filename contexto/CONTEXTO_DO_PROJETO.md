# CiberBot PT — contexto do projeto

> Ficheiro para repositório público: sem segredos nem dados pessoais.

## 1. Objetivo

Pedido original do utilizador (palavras dele):

> «A ideia é criar um bot de informação que consiga encontrar informação em português, mas caso esteja em inglês que faça a tradução para português de Portugal… que recolher toda a informação sobre Cibersegurança.. como por exemplo ataques.. novas vulnerabilidades.. e informações relevantes»

Em resumo: um bot que junta informação de cibersegurança (ataques, novas vulnerabilidades, informação relevante), **prefere fontes em português** e **traduz para português de Portugal** o que estiver em inglês.

## 2. Escolhas do utilizador

| Pergunta | Resposta |
|---|---|
| Onde receber a informação? | Pediu a recomendação e disse que gostava de **todas** as opções: Telegram, email, Discord e página web. |
| Como deve funcionar? | **Resumo diário** (recomendado), ordenado por gravidade/relevância. Alertas em tempo real e consulta a pedido não foram escolhidos. |
| Como construir? | «Recomenda-me» → escolhido: **script em Python a correr no GitHub Actions** (grátis, sem servidor). |
| Repositório | Nome `ciberbot-pt`, **público** (necessário para o site grátis do GitHub Pages). Foi o utilizador que o criou vazio; o código foi enviado depois. |

Notas sobre a forma de trabalhar com o utilizador: nas explicações de configuração (segredos, tokens, passos no GitHub) pediu e usa-se **passos concretos, com links, em português**; não colar segredos na conversa.

## 3. Decisões de design e porquê

| Decisão | Porquê |
|---|---|
| Python só com biblioteca padrão | Sem instalação de pacotes no GitHub Actions (arranque rápido) e sem manutenção de dependências. Foi também a única opção testável no ambiente onde nasceu (sem acesso ao PyPI). |
| GitHub Actions + `cron` diário | Grátis, sem servidor, com histórico. O estado e o site ficam no próprio repositório (commit diário do bot). |
| Fontes estruturadas (RSS, JSON da CISA KEV, API do NVD) em vez de *scraping* de páginas | Mais estável, legítimo e fácil de interpretar. |
| CISA KEV como fonte principal de «vulnerabilidades exploradas» | Lista oficial de vulnerabilidades com exploração confirmada; indica uso em ransomware e prazo de correção. |
| NVD só com CVSS crítico | Evitar ruído; a KEV já cobre o mais urgente (duplicados removidos). |
| Tradução com a API da Claude (modelo Haiku), em lotes, com resposta em JSON | Qualidade boa em pt-PT e custo baixo (poucos textos curtos por dia). Glossário e regras no prompt (`traducao.SISTEMA`). |
| Se a tradução falhar, o item fica em inglês e assinalado «Em inglês» | Nunca perder informação por falha da API. |
| Pontuação por fonte + palavras-chave + CVSS + ransomware + frescura | Ordenar por relevância sem aprendizagem automática; tudo editável em `config.toml`. |
| Estado em `state/vistos.json` (ids vistos 90 dias; títulos 7 dias) | Nunca repetir notícias, nem a mesma história com título parecido vinda de outra fonte noutro dia. |
| Estado só gravado depois de pelo menos um canal publicar | Se tudo falhar, os itens voltam a ser tentados no dia seguinte. |
| Janela por **dias de calendário** (fuso `Europe/Lisbon`), não por horas exatas | A CISA KEV só indica a data (assume-se 12:00 UTC); assim não fica de fora por causa das horas. O estado evita repetições. |
| Uma mensagem de email por destinatário | Ninguém vê os endereços dos outros. |
| Página do dia cumulativa | Se houver duas execuções no mesmo dia, os itens juntam-se em vez de se perderem. |
| Canais opcionais, ativados só por variáveis de ambiente | Cada canal só liga se tiver os seus segredos; o `web` está sempre ativo (salvo `web.ativo = false`). |

## 4. Fontes configuradas na v1 (`config.toml`)

> Na v2: retirada «Segurança Informática» (bloqueia robôs), acrescentados Pplware, SAPO Tek e GitHub Advisories; THN limitado a 5. Ver `ESTADO_E_PENDENTES.md`.

| Fonte | Tipo | Idioma | Secção | Peso | Máx. | URL | Estado real (21–26/10/2026) |
|---|---|---|---|---|---|---|---|
| CNCS — Alertas de Segurança | rss | pt | portugal | 40 | 8 | `https://www.cncs.gov.pt/docs/alertas-seguranca/feed-rss/index.xml` | ✅ funciona (2 itens em 6 dias) |
| Segurança Informática | rss | pt | portugal | 20 | 4 | `https://seguranca-informatica.pt/feed/` | ⚠️ sem erros, mas **0 itens** em 6 dias |
| CISA — Vulnerabilidades exploradas (KEV) | kev | en | exploradas | 60 | 8 | `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | ✅ funciona (7 itens, nos dias 21 e 24) |
| NVD — CVE críticos | nvd | en | criticas | 30 | 6 | `https://services.nvd.nist.gov/rest/json/cves/2.0` | ❌ **HTTP 403 todos os dias** |
| BleepingComputer | rss | en | noticias | 25 | 8 | `https://www.bleepingcomputer.com/feed/` | ✅ 15 itens |
| The Hacker News | rss | en | noticias | 25 | 8 | `https://feeds.feedburner.com/TheHackersNews` | ✅ 36 itens (domina) |
| Krebs on Security | rss | en | noticias | 25 | 3 | `https://krebsonsecurity.com/feed/` | ✅ 1 item (publica pouco) |

(«Máx.» = `max_itens` da fonte; sem valor próprio vale `geral.max_por_fonte = 8`.)

A única fonte portuguesa confirmada com alertas é o CNCS. O feed do CNCS foi confirmado por pesquisa (agregador Feeder, ~4 publicações por semana).

## 5. Ambiente onde o projeto foi criado (limitações já ultrapassadas)

O código nasceu numa sessão em nuvem (claude.ai) com rede restrita:
- Não tinha acesso aos feeds reais nem ao PyPI → por isso os testes usam **dados fictícios** (`tests/fixtures/`) e a `demo` traz **traduções escritas à mão** (`demo_pt.json`).
- O acesso ao GitHub era limitado: sem `gh repo create` (GraphQL), sem ativar o Pages, sem ler segredos nem registos do Actions. O repositório foi criado pelo utilizador e o código enviado por `git push`.

No Claude Code local estas limitações não se aplicam: podes correr `--dry-run` com as fontes reais e testar tudo.

## 6. Cronologia

| Data | Acontecimento |
|---|---|
| 2026-10-20 | Pedido e escolhas. Código escrito e testado offline (51 testes). Repositório criado pelo utilizador; primeiro push (`5e0008c`) e definição de `url_publica` (`d710f62`). |
| 2026-10-21 (manhã) | O utilizador perguntou onde obter os segredos; foi explicado onde obter cada um (chave da API, Telegram, Discord, Gmail) e como os guardar em *Settings → Secrets and variables → Actions*. |
| 2026-10-21 → 26 | Execuções diárias automáticas, todas com sucesso (commits «Resumo de AAAA-MM-DD» do bot, primeira execução a 21/10 às ~12:47 UTC). GitHub Pages ativo e a publicar. A chave `ANTHROPIC_API_KEY` continua por configurar. |
| 2026-10-26 | Verificação do estado real: tradução inativa (sem chave), NVD com 403, atraso do agendamento. Preparação destes documentos para continuar o desenvolvimento no Claude Code. |
| 2026-10-26 | O utilizador (sem chaves de API nem tokens) pediu melhorias e um repositório novo: **`ciberbot-pt-v2`** (público). Escolheu tradução gratuita «GitHub Models + MyMemory». Ver `ESTADO_E_PENDENTES.md`. |

## 7. Glossário rápido

- **KEV** — Known Exploited Vulnerabilities, catálogo da CISA (EUA) de falhas com exploração confirmada.
- **NVD** — National Vulnerability Database (NIST), base de dados de CVE com pontuação CVSS.
- **CNCS** — Centro Nacional de Cibersegurança (Portugal).
- **CVE / CVSS** — identificador de vulnerabilidade / pontuação de gravidade (0–10).
- **Secção** — grupo no resumo: `portugal`, `exploradas`, `criticas`, `noticias`.
- **Edição** — o resumo de um dia.
