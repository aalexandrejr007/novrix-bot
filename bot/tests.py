import hashlib
import hmac
import json
from datetime import datetime
from unittest import mock

from django.test import TestCase, override_settings

from . import fluxo
from .models import Contato, Mensagem

WA = {"TOKEN": "t", "PHONE_NUMBER_ID": "123", "VERIFY_TOKEN": "palavra-secreta",
      "APP_SECRET": "segredo", "GRAPH_VERSION": "v23.0"}


def corpo_texto(texto, mid="wamid.1", de="5511999990000", nome="Maria Souza"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "contacts": [{"wa_id": de, "profile": {"name": nome}}],
        "messages": [{"from": de, "id": mid, "timestamp": "1", "type": "text", "text": {"body": texto}}],
    }}]}]}


def corpo_escolha(escolha, mid, de="5511999990000", tipo="list_reply"):
    return {"entry": [{"changes": [{"field": "messages", "value": {
        "contacts": [{"wa_id": de, "profile": {"name": "Maria Souza"}}],
        "messages": [{"from": de, "id": mid, "type": "interactive",
                      "interactive": {"type": tipo, tipo: {"id": escolha, "title": escolha}}}],
    }}]}]}


@override_settings(WHATSAPP=WA, PAUSA_HUMANO_HORAS=24)
class WebhookTests(TestCase):
    def setUp(self):
        self.p_texto = mock.patch("bot.whatsapp.enviar_texto", return_value="out.t")
        self.p_lista = mock.patch("bot.whatsapp.enviar_lista", return_value="out.l")
        self.p_botoes = mock.patch("bot.whatsapp.enviar_botoes", return_value="out.b")
        self.texto = self.p_texto.start()
        self.lista = self.p_lista.start()
        self.botoes = self.p_botoes.start()
        self.addCleanup(mock.patch.stopall)
        n = iter(range(1, 10_000))
        # IDs de saída únicos para não colidirem no banco
        for m in (self.texto, self.lista, self.botoes):
            m.side_effect = lambda *a, **k: f"out.{next(n)}"

    def post(self, dados, assinar=True):
        corpo = json.dumps(dados).encode()
        headers = {}
        if assinar:
            sig = hmac.new(b"segredo", corpo, hashlib.sha256).hexdigest()
            headers["HTTP_X_HUB_SIGNATURE_256"] = f"sha256={sig}"
        return self.client.post("/webhook/", corpo, content_type="application/json", **headers)

    # --- cadastro do webhook ---
    def test_verificacao_ok(self):
        r = self.client.get("/webhook/", {"hub.mode": "subscribe", "hub.verify_token": "palavra-secreta", "hub.challenge": "42"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"42")

    def test_verificacao_token_errado(self):
        r = self.client.get("/webhook/", {"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "42"})
        self.assertEqual(r.status_code, 403)

    def test_assinatura_invalida_e_recusada(self):
        r = self.post(corpo_texto("oi"), assinar=False)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Contato.objects.exists())

    # --- conversa ---
    def test_primeira_mensagem_recebe_saudacao_e_menu(self):
        r = self.post(corpo_texto("Boa tarde, quero um site"))
        self.assertEqual(r.status_code, 200)
        self.lista.assert_called_once()
        para, texto, botao, linhas = self.lista.call_args.args[:4]
        self.assertEqual(para, "5511999990000")
        self.assertIn("Olá, Maria!", texto)
        self.assertEqual(botao, "Ver opções")
        ids = [l[0] for l in linhas]
        self.assertEqual(ids, ["sites", "automacoes", "planilhas", "sistemas", "oschurch", "humano"])
        for _, titulo, desc in linhas:
            self.assertLessEqual(len(titulo), 24)
            self.assertLessEqual(len(desc), 72)
        c = Contato.objects.get()
        self.assertEqual(c.nome, "Maria Souza")
        self.assertEqual(c.mensagens.filter(direcao=Mensagem.ENTRADA).count(), 1)

    def test_escolher_servico_mostra_detalhes_com_botoes(self):
        self.post(corpo_texto("oi"))
        self.post(corpo_escolha("oschurch", "wamid.2"))
        self.botoes.assert_called_once()
        texto, botoes = self.botoes.call_args.args[1], self.botoes.call_args.args[2]
        self.assertIn("OS-Church", texto)
        self.assertEqual([b[0] for b in botoes], ["orcamento", "menu"])
        for _, titulo in botoes:
            self.assertLessEqual(len(titulo), 20)
        self.assertEqual(Contato.objects.get().interesse, "oschurch")

    def test_pedir_orcamento_passa_para_pessoa_e_pausa_robo(self):
        self.post(corpo_texto("oi"))
        self.post(corpo_escolha("orcamento", "wamid.2", tipo="button_reply"))
        c = Contato.objects.get()
        self.assertTrue(c.quer_orcamento)
        self.assertTrue(c.robo_pausado)
        self.texto.assert_called_once()
        # com o robô pausado, novas mensagens não recebem resposta automática
        chamadas = (self.texto.call_count, self.lista.call_count, self.botoes.call_count)
        self.post(corpo_texto("então, preciso de um site", mid="wamid.3"))
        self.assertEqual((self.texto.call_count, self.lista.call_count, self.botoes.call_count), chamadas)
        self.assertEqual(c.mensagens.filter(direcao=Mensagem.ENTRADA).count(), 3)

    def test_palavra_atendente_tambem_passa_para_pessoa(self):
        self.post(corpo_texto("oi"))
        self.post(corpo_texto("Atendente", mid="wamid.2"))
        self.assertTrue(Contato.objects.get().robo_pausado)

    def test_texto_livre_reenvia_opcoes(self):
        self.post(corpo_texto("oi"))
        self.post(corpo_texto("quanto custa?", mid="wamid.2"))
        self.texto.assert_called_once()
        self.assertEqual(self.lista.call_count, 2)

    def test_mensagem_repetida_pela_meta_nao_responde_duas_vezes(self):
        self.post(corpo_texto("oi"))
        self.post(corpo_texto("oi"))
        self.assertEqual(self.lista.call_count, 1)
        self.assertEqual(Mensagem.objects.filter(direcao=Mensagem.ENTRADA).count(), 1)

    def test_resposta_pelo_app_pausa_o_robo(self):
        self.post(corpo_texto("oi"))
        eco = {"entry": [{"changes": [{"field": "smb_message_echoes", "value": {
            "message_echoes": [{"from": "5511957554987", "to": "5511999990000", "id": "wamid.eco", "type": "text",
                                "text": {"body": "Oi Maria, aqui é o Alexandre!"}}]}}]}]}
        self.post(eco)
        self.assertTrue(Contato.objects.get().robo_pausado)

    def test_status_de_entrega_e_ignorado(self):
        status = {"entry": [{"changes": [{"field": "messages", "value": {"statuses": [{"id": "x", "status": "read"}]}}]}]}
        r = self.post(status)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Contato.objects.exists())


class HorarioTests(TestCase):
    def test_horario(self):
        tz = fluxo.FUSO
        self.assertTrue(fluxo.dentro_do_horario(datetime(2026, 11, 16, 10, 0, tzinfo=tz)))   # segunda 10h
        self.assertFalse(fluxo.dentro_do_horario(datetime(2026, 11, 16, 18, 0, tzinfo=tz)))  # segunda 18h
        self.assertTrue(fluxo.dentro_do_horario(datetime(2026, 11, 14, 12, 59, tzinfo=tz)))  # sábado 12h59
        self.assertFalse(fluxo.dentro_do_horario(datetime(2026, 11, 14, 13, 0, tzinfo=tz)))  # sábado 13h
        self.assertFalse(fluxo.dentro_do_horario(datetime(2026, 11, 15, 10, 0, tzinfo=tz)))  # domingo


class EnvioTests(TestCase):
    @override_settings(WHATSAPP=WA)
    def test_formato_do_envio_para_a_meta(self):
        from . import whatsapp
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"messages": [{"id": "wamid.out"}]}
        with mock.patch("bot.whatsapp.requests.post", return_value=resp) as post:
            mid = whatsapp.enviar_botoes("5511999990000", "Oi", [("a", "Quero orçamento")])
        self.assertEqual(mid, "wamid.out")
        url = post.call_args.args[0]
        self.assertEqual(url, "https://graph.facebook.com/v23.0/123/messages")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["interactive"]["action"]["buttons"][0]["reply"]["id"], "a")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer t")


class PaginasTests(TestCase):
    def test_privacidade(self):
        r = self.client.get("/privacidade/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Política de Privacidade")
