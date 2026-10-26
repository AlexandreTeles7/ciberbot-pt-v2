"""Testes offline das melhorias da versão 2: tradutores gratuitos, GitHub Advisories, .env, notas."""
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import timedelta
from pathlib import Path
from unittest import mock

from ciberbot import cli, edicao, fontes, pontuacao, rede, traducao
from ciberbot.demo import AGORA_DEMO, FIXTURES, obter_de_ficheiros, traducao_simulada
from ciberbot.modelos import Item
from ciberbot.rede import ErroRede

AGORA = AGORA_DEMO
CFG = cli.carregar_config(FIXTURES / "config_demo.toml")


def item(titulo="Title", resumo="Summary", **kw) -> Item:
    base = dict(id=titulo, titulo=titulo, resumo=resumo, url="https://exemplo.test/x", fonte="F",
                idioma="en", categoria="noticias", publicado=AGORA - timedelta(hours=2))
    base.update(kw)
    return Item(**base)


def resposta_ia(msg: str, prefixo: str = "PT ") -> str:
    carga = json.loads(msg.split("<itens>\n", 1)[1].rsplit("\n</itens>", 1)[0])
    return json.dumps([{"i": c["i"], "titulo": prefixo + c["titulo"], "resumo": "pt"} for c in carga])


def mymemory_falso(traducoes: dict | None = None, aviso: bool = False):
    pedidos = []

    def obter(url, **kw):
        pedidos.append(url)
        if aviso:
            return json.dumps({"responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL "
                                                "AVAILABLE FREE TRANSLATIONS FOR TODAY"},
                               "quotaFinished": True, "responseStatus": 429}).encode()
        return json.dumps({"responseData": {"translatedText": "Olá &amp; adeus"},
                           "quotaFinished": False, "responseStatus": 200}).encode()
    return obter, pedidos


class TestTradutores(unittest.TestCase):
    def test_ordem_e_disponibilidade(self):
        conf = {}
        self.assertEqual([n for n, _ in traducao.tradutores(conf, {})], ["mymemory"])
        env = {"ANTHROPIC_API_KEY": "a", "GITHUB_TOKEN": "g"}
        self.assertEqual([n for n, _ in traducao.tradutores(conf, env)], ["anthropic", "github", "mymemory"])
        conf = {"fornecedores": ["github"]}
        self.assertEqual([n for n, _ in traducao.tradutores(conf, env)], ["github"])

    def test_github_models_usa_token_e_formato_openai(self):
        with mock.patch("ciberbot.traducao.enviar_json") as m:
            m.return_value = (200, {"choices": [{"message": {"content": "[]"}}]})
            self.assertEqual(traducao.chamar_github("sis", "msg", "openai/gpt-4.1-mini", "TOKEN"), "[]")
        url, carga, cab = m.call_args[0][:3]
        self.assertEqual(url, traducao.GITHUB_URL)
        self.assertEqual(carga["model"], "openai/gpt-4.1-mini")
        self.assertEqual(carga["messages"][0], {"role": "system", "content": "sis"})
        self.assertEqual(cab["Authorization"], "Bearer TOKEN")

    def test_erro_do_github_nao_expoe_o_token(self):
        with mock.patch("ciberbot.traducao.enviar_json", return_value=(401, {"error": {"message": "Bad credentials"}})):
            with self.assertRaises(traducao.ErroTraducao) as cm:
                traducao.chamar_github("s", "m", "modelo", "SEGREDO456")
        self.assertNotIn("SEGREDO456", str(cm.exception))
        self.assertIn("401", str(cm.exception))

    def test_se_a_claude_falha_o_github_traduz(self):
        def falso(url, carga, cab, **kw):
            if url == traducao.API_URL:
                return 529, {"error": {"message": "overloaded"}}
            return 200, {"choices": [{"message": {"content": resposta_ia(carga["messages"][1]["content"])}}]}
        itens = [item(f"Title {k}", id=str(k)) for k in range(3)]
        env = {"ANTHROPIC_API_KEY": "a", "GITHUB_TOKEN": "g"}
        with mock.patch("ciberbot.traducao.enviar_json", side_effect=falso):
            avisos = traducao.traduzir(itens, {"traducao": {"fornecedores": ["anthropic", "github"]}}, env)
        self.assertEqual(avisos, [])  # recuperado: a falha fica só nos registos
        self.assertTrue(all(i.traduzido and i.titulo_pt.startswith("PT ") for i in itens))

    def test_mymemory_traduz_e_desescapa(self):
        obter, pedidos = mymemory_falso()
        itens = [item("Hello", "World")]
        avisos = traducao.traduzir(itens, {"traducao": {"fornecedores": ["mymemory"]}}, {}, obter_fn=obter)
        self.assertEqual(avisos, [])
        self.assertEqual(itens[0].titulo_pt, "Olá & adeus")
        self.assertTrue(itens[0].traduzido)
        self.assertIn("langpair=en%7Cpt-PT", pedidos[0])
        self.assertTrue(pedidos[0].startswith(traducao.MYMEMORY_URL + "?"))

    def test_mymemory_limite_esgotado_avisa_e_mantem_ingles(self):
        obter, _ = mymemory_falso(aviso=True)
        itens = [item("Hello", "World")]
        avisos = traducao.traduzir(itens, {"traducao": {"fornecedores": ["mymemory"]}}, {}, obter_fn=obter)
        self.assertEqual(len(avisos), 1)
        self.assertIn("limite diário", avisos[0])
        self.assertTrue(itens[0].em_ingles)

    def test_mymemory_respeita_orcamento_por_relevancia(self):
        obter, pedidos = mymemory_falso()
        importante = item("A" * 50, "", id="i", pontuacao=90)
        menor = item("B" * 50, "", id="m", pontuacao=10)
        conf = {"traducao": {"fornecedores": ["mymemory"], "mymemory_max_caracteres": 60}}
        avisos = traducao.traduzir([menor, importante], conf, {}, obter_fn=obter)
        self.assertTrue(importante.traduzido)
        self.assertFalse(menor.traduzido)
        self.assertEqual(len(pedidos), 1)
        self.assertIn("1 itens sem tradução", avisos[0])


    def test_aportuguesar_corrige_portugues_do_brasil(self):
        a = traducao.aportuguesar
        self.assertEqual(a("Pesquisadores estão chamando a atenção"), "Investigadores estão a chamar a atenção")
        self.assertEqual(a("O usuário perdeu a senha do aplicativo"),
                         "O utilizador perdeu a palavra-passe da aplicação")
        self.assertEqual(a("Violação de dados na cadeia de suprimentos"), "Fuga de dados na cadeia de fornecimento")
        self.assertEqual(a("Arquivo CVE-2026-1234 em ficheiros"), "Ficheiro CVE-2026-1234 em ficheiros")
        self.assertEqual(a("arquivologia"), "arquivologia")  # só palavras inteiras


class TestGithubAdvisories(unittest.TestCase):
    def fonte(self):
        return next(f for f in CFG["fontes"] if f["tipo"] == "ghsa")

    def test_interpreta_e_ignora_retirados(self):
        itens = fontes.interpretar_ghsa((FIXTURES / "ghsa.json").read_bytes(), self.fonte(), AGORA)
        self.assertEqual([i.id for i in itens], ["ghsa:CVE-2026-90020", "ghsa:CVE-2026-90010"])
        a = itens[0]
        self.assertEqual(a.cves, ["CVE-2026-90020"])
        self.assertIn("CVSS 9.8", a.etiquetas)
        self.assertIn("npm: exemplo-parser", a.etiquetas)
        self.assertNotIn("##", a.resumo)
        self.assertNotIn("](", a.resumo)
        self.assertIn("the advisory", a.resumo)
        self.assertEqual(a.categoria, "criticas")
        self.assertIn("CVSS 9.1", itens[1].etiquetas)

    def test_url_tem_gravidade_e_data(self):
        url = fontes.construir_url_ghsa(self.fonte(), AGORA, 36)
        self.assertIn("severity=critical", url)
        self.assertIn("published=%3E%3D2026-10-18", url)
        self.assertIn("type=reviewed", url)

    def test_json_inesperado(self):
        with self.assertRaises(fontes.ErroFonte):
            fontes.interpretar_ghsa(b'{"message": "rate limited"}', self.fonte(), AGORA)

    def test_token_opcional_vai_no_cabecalho(self):
        recebidos = []
        def obter(url, cabecalhos=None, **kw):
            if "ghsa" in url:
                recebidos.append(cabecalhos)
            return obter_de_ficheiros(url)
        fontes.recolher(CFG, AGORA, {"GITHUB_TOKEN": "tok"}, obter_fn=obter)
        self.assertEqual(recebidos[0]["Authorization"], "Bearer tok")

    def test_mesmo_cve_no_nvd_e_no_ghsa_aparece_uma_vez(self):
        a = item("nvd", id="nvd:CVE-9", categoria="criticas", cves=["CVE-2026-99999"], pontuacao=50)
        b = item("ghsa", id="ghsa:X", categoria="criticas", cves=["CVE-2026-99999"], pontuacao=40)
        self.assertEqual([i.id for i in pontuacao.deduplicar([b, a])], ["nvd:CVE-9"])


    def test_cve_enviado_noutro_dia_nao_volta_por_outra_fonte(self):
        from ciberbot.estado import Estado
        with tempfile.TemporaryDirectory() as t:
            e = Estado(Path(t) / "v.json")
            e.marcar(["nvd:CVE-2026-99999", "noticia-sem-cve"], AGORA.date())
            self.assertEqual(e.cves_enviados(), {"CVE-2026-99999"})
        b = item("ghsa", id="ghsa:CVE-2026-99999", categoria="criticas", cves=["CVE-2026-99999"])
        self.assertEqual(pontuacao.deduplicar([b], cves_kev={"CVE-2026-99999"}), [])


class TestRede(unittest.TestCase):
    def test_user_agent_so_ascii(self):
        rede.UA.encode("ascii")

    def test_bloqueio_anti_robos_e_explicado_sem_url(self):
        erro = urllib.error.HTTPError("https://x.test/a?token=SEGREDO", 403, "Forbidden", {},
                                      io.BytesIO(b"<html><title>Just a moment...</title></html>"))
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            with self.assertRaises(ErroRede) as cm:
                rede.obter("https://x.test/a?token=SEGREDO", tentativas=1)
        self.assertIn("anti-robôs", str(cm.exception))
        self.assertNotIn("SEGREDO", str(cm.exception))


class TestEnv(unittest.TestCase):
    def test_le_env_sem_substituir_variaveis_existentes(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / ".env"
            f.write_text("# comentário\nA=1\nexport B=\"dois\"\nC=\nD='x'\nJA=novo\nlixo\n", encoding="utf-8")
            env = {"JA": "antigo"}
            self.assertEqual(cli.carregar_env(f, env), 3)
            self.assertEqual(env, {"JA": "antigo", "A": "1", "B": "dois", "D": "x"})

    def test_sem_ficheiro_nao_faz_nada(self):
        env = {}
        self.assertEqual(cli.carregar_env("/nao/existe/.env", env), 0)
        self.assertEqual(env, {})


class TestNotas(unittest.TestCase):
    def correr(self, tmp, cfg_extra=None, env=None):
        cfg = json.loads(json.dumps(CFG))
        cfg["web"] = {"pasta": str(Path(tmp) / "docs")}
        cfg["geral"].update(cfg_extra or {})

        def obter(url, **kw):
            if "atom" in url:
                raise ErroRede("exemplo.test: HTTP 503")
            return obter_de_ficheiros(url)
        cli.executar(cfg, env or {}, AGORA, obter_fn=obter, chamar_traducao=traducao_simulada,
                     pasta_estado=Path(tmp) / "v.json")
        return (Path(tmp) / "docs" / "index.html").read_text(encoding="utf-8")

    def test_notas_tecnicas_nao_vao_para_o_publico(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertNotIn("Notas desta edição", self.correr(t))

    def test_notas_publicas_se_configurado(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIn("Blogue (Atom)", self.correr(t, {"notas_publicas": True}))

    def test_notas_vao_para_o_resumo_do_actions(self):
        with tempfile.TemporaryDirectory() as t:
            resumo = Path(t) / "resumo.md"
            self.correr(t, env={"GITHUB_STEP_SUMMARY": str(resumo)})
            texto = resumo.read_text(encoding="utf-8")
            self.assertIn("Edição de 2026-10-20", texto)
            self.assertIn("Blogue (Atom)", texto)


class TestDemo(unittest.TestCase):
    def test_demo_inclui_github_advisories_traduzido(self):
        ed_texto = []
        with tempfile.TemporaryDirectory() as t, mock.patch("builtins.print", side_effect=ed_texto.append):
            from ciberbot.demo import executar_demo
            executar_demo(str(Path(t) / "p"))
        texto = "\n".join(ed_texto)
        self.assertIn("poluição de protótipo", texto)
        self.assertIn("detail/CVE-2026-90010", texto)  # o mesmo CVE no NVD e no GHSA: só uma vez
        self.assertNotIn("GHSA-dddd-eeee-ffff", texto)
        self.assertIn(edicao.AVISO_TRADUCAO, texto)


if __name__ == "__main__":
    unittest.main()
