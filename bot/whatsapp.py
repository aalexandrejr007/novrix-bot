"""Envio de mensagens pelo WhatsApp.

Dois caminhos, escolhidos pela variável WHATSAPP_PROVIDER:
- "meta":   direto na Cloud API da Meta (número de teste, ou número só da API);
- "ycloud": pela YCloud, parceira oficial da Meta, que permite usar o mesmo número
            no app WhatsApp Business e no robô ao mesmo tempo (coexistência).
"""
import hashlib
import hmac
import logging
import time

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


def assinatura_ycloud_valida(corpo: bytes, cabecalho: str, agora=None) -> bool:
    """Confere o cabeçalho YCloud-Signature: "t=TIMESTAMP,s=HMAC_SHA256_HEX(TIMESTAMP + "." + corpo)"."""
    segredo = _cfg()["YCLOUD_WEBHOOK_SECRET"]
    if not segredo:
        log.warning("YCLOUD_WEBHOOK_SECRET não configurado: assinatura do webhook não verificada.")
        return True
    campos = [p.strip().split("=", 1) for p in (cabecalho or "").split(",") if "=" in p]
    ts = [v for k, v in campos if k == "t"]
    assinaturas = [v for k, v in campos if k == "s"]
    if len(ts) != 1 or not ts[0].isdigit():
        return False
    if abs(int(agora or time.time()) - int(ts[0])) > 300:  # evita repetição de requisições antigas
        return False
    esperado = hmac.new(segredo.encode(), ts[0].encode() + b"." + corpo, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(esperado, a.lower()) for a in assinaturas)


def so_digitos(numero: str) -> str:
    return "".join(c for c in (numero or "") if c.isdigit())


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
    if _cfg().get("PROVIDER") == "ycloud":
        return _post_ycloud(payload)
    return _post_meta(payload)


def _post_ycloud(payload: dict):
    cfg = _cfg()
    if not cfg["YCLOUD_API_KEY"] or not cfg["YCLOUD_FROM"]:
        log.error("YCLOUD_API_KEY ou YCLOUD_FROM não configurados; mensagem não enviada.")
        return None, None
    corpo = {k: v for k, v in payload.items() if k != "to"}
    if corpo.get("type") == "text":
        corpo["text"] = {"body": corpo["text"]["body"]}
    corpo.update({"from": "+" + so_digitos(cfg["YCLOUD_FROM"]), "to": "+" + so_digitos(payload["to"])})
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages/sendDirectly",
            json=corpo,
            headers={"X-API-Key": cfg["YCLOUD_API_KEY"]},
            timeout=20,
        )
    except requests.RequestException:
        log.exception("Falha de rede ao enviar mensagem pela YCloud")
        return None, None
    if r.status_code >= 400:
        log.error("YCloud recusou a mensagem (%s): %s", r.status_code, r.text[:500])
        return None, None
    try:
        dados = r.json()
    except ValueError:
        return None, None
    log.info("YCloud: mensagem para %s com status %s", corpo["to"], dados.get("status"))
    if dados.get("status") == "failed":
        log.error("YCloud marcou a mensagem como falha: %s", str(dados)[:500])
        return None, None
    return dados.get("wamid") or dados.get("id"), None


def _post_meta(payload: dict):
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
