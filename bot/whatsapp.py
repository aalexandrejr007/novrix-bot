"""Envio de mensagens pela API oficial do WhatsApp (Cloud API da Meta)."""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)


def _cfg():
    return settings.WHATSAPP


def assinatura_valida(corpo: bytes, cabecalho: str) -> bool:
    """Confere o X-Hub-Signature-256 que a Meta manda em cada webhook."""
    segredo = _cfg()["APP_SECRET"]
    if not segredo:
        # Sem a chave configurada (só no computador), não dá para conferir.
        log.warning("WHATSAPP_APP_SECRET não configurado: assinatura do webhook não verificada.")
        return True
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho.split("=", 1)[1])


def _com_nono_digito(numero: str):
    """Celular brasileiro que a Meta entrega sem o 9 (55 + DDD + 8 dígitos) -> com o 9."""
    if numero and numero.isdigit() and len(numero) == 12 and numero.startswith("55") and numero[4] in "6789":
        return numero[:4] + "9" + numero[4:]
    return None


def _enviar(payload: dict):
    mid, erro = _post(payload)
    # Erro 131030 (número fora da lista de teste) com número brasileiro sem o 9: tenta com o 9.
    if erro == 131030:
        alt = _com_nono_digito(payload.get("to", ""))
        if alt:
            log.warning("Reenviando para %s com o nono dígito", alt)
            mid, _ = _post({**payload, "to": alt})
    return mid


def _post(payload: dict):
    cfg = _cfg()
    if not cfg["TOKEN"] or not cfg["PHONE_NUMBER_ID"]:
        log.error("WHATSAPP_TOKEN ou WHATSAPP_PHONE_NUMBER_ID não configurados; mensagem não enviada.")
        return None, None
    url = f"https://graph.facebook.com/{cfg['GRAPH_VERSION']}/{cfg['PHONE_NUMBER_ID']}/messages"
    try:
        r = requests.post(
            url,
            json={"messaging_product": "whatsapp", "recipient_type": "individual", **payload},
            headers={"Authorization": f"Bearer {cfg['TOKEN']}"},
            timeout=15,
        )
    except requests.RequestException:
        log.exception("Falha de rede ao enviar mensagem")
        return None, None
    if r.status_code >= 400:
        log.error("Meta recusou a mensagem (%s): %s", r.status_code, r.text[:500])
        try:
            codigo = r.json()["error"]["code"]
        except (ValueError, KeyError, TypeError):
            codigo = None
        return None, codigo
    try:
        return r.json()["messages"][0]["id"], None
    except (ValueError, KeyError, IndexError):
        return None, None


def enviar_texto(para: str, texto: str):
    return _enviar({"to": para, "type": "text", "text": {"preview_url": True, "body": texto}})


def enviar_botoes(para: str, texto: str, botoes: list[tuple[str, str]]):
    """Até 3 botões de resposta rápida. botoes = [(id, título até 20 caracteres)]."""
    return _enviar({
        "to": para,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": bid, "title": titulo[:20]}} for bid, titulo in botoes[:3]
            ]},
        },
    })


def enviar_lista(para: str, texto: str, botao: str, linhas: list[tuple[str, str, str]], rodape: str = ""):
    """Menu em lista. linhas = [(id, título até 24, descrição até 72)]."""
    interactive = {
        "type": "list",
        "body": {"text": texto},
        "action": {
            "button": botao[:20],
            "sections": [{
                "title": "Serviços",
                "rows": [{"id": i, "title": t[:24], "description": d[:72]} for i, t, d in linhas[:10]],
            }],
        },
    }
    if rodape:
        interactive["footer"] = {"text": rodape[:60]}
    return _enviar({"to": para, "type": "interactive", "interactive": interactive})
