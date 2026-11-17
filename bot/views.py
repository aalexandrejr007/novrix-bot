import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from . import fluxo, whatsapp
from .models import Contato, Mensagem

log = logging.getLogger(__name__)


@require_GET
def saude(request):
    return JsonResponse({"ok": True})


def _extrair(msg):
    """Tipo, texto e id da opção escolhida (lista ou botão) de uma mensagem recebida."""
    tipo = msg.get("type", "")
    texto, escolha = "", ""
    if tipo == "text":
        texto = msg.get("text", {}).get("body", "")
    elif tipo == "interactive":
        it = msg.get("interactive", {})
        resp = it.get("list_reply") or it.get("button_reply") or {}
        escolha, texto = resp.get("id", ""), resp.get("title", "")
    elif tipo == "button":
        texto = msg.get("button", {}).get("text", "")
    return tipo, texto, escolha


def _processar_mensagem(msg, nomes):
    wa_id = msg.get("from")
    mid = msg.get("id")
    if not wa_id or not mid:
        return
    tipo, texto, escolha = _extrair(msg)
    contato, criado = Contato.objects.get_or_create(wa_id=wa_id, defaults={"nome": nomes.get(wa_id, "")})
    if not criado and nomes.get(wa_id) and not contato.nome:
        contato.nome = nomes[wa_id]
        contato.save(update_fields=["nome", "atualizado_em"])
    try:
        with transaction.atomic():
            Mensagem.objects.create(contato=contato, direcao=Mensagem.ENTRADA, wa_message_id=mid, tipo=tipo, texto=texto)
    except IntegrityError:
        return  # a Meta reenviou a mesma mensagem: já respondida
    fluxo.responder(contato, tipo, texto, escolha, primeira_vez=criado)


def _processar_eco(eco):
    """Mensagem que você mandou pelo app WhatsApp Business (modo coexistência): pausa o robô na conversa."""
    para = eco.get("to")
    if not para:
        return
    contato, _ = Contato.objects.get_or_create(wa_id=para)
    contato.pausar_robo(settings.PAUSA_HUMANO_HORAS)


@csrf_exempt
def webhook(request):
    cfg = settings.WHATSAPP
    if request.method == "GET":
        # Verificação que a Meta faz quando você cadastra o webhook.
        if (request.GET.get("hub.mode") == "subscribe"
                and cfg["VERIFY_TOKEN"]
                and request.GET.get("hub.verify_token") == cfg["VERIFY_TOKEN"]):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponseForbidden("token de verificação inválido")

    if request.method != "POST":
        return HttpResponse(status=405)

    if not whatsapp.assinatura_valida(request.body, request.headers.get("X-Hub-Signature-256", "")):
        return HttpResponseForbidden("assinatura inválida")

    try:
        dados = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponse(status=400)

    for entrada in dados.get("entry", []):
        for mudanca in entrada.get("changes", []):
            valor = mudanca.get("value", {})
            try:
                if mudanca.get("field") == "smb_message_echoes":
                    for eco in valor.get("message_echoes", []):
                        _processar_eco(eco)
                    continue
                nomes = {c.get("wa_id"): c.get("profile", {}).get("name", "") for c in valor.get("contacts", [])}
                for msg in valor.get("messages", []):
                    _processar_mensagem(msg, nomes)
            except Exception:
                # Responder 200 mesmo assim evita que a Meta reenvie sem parar; o erro fica no log.
                log.exception("Erro ao processar webhook")
    return HttpResponse("ok")
