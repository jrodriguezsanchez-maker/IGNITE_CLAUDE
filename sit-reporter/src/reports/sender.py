"""
Envía emails usando Microsoft Graph API con la cuenta Accenture del usuario.
"""
import base64
import json
import requests


GRAPH_SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/me/sendMail"


def send_report_email(
    graph_token: str,
    from_address: str,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    attachments: list[dict] = None,
):
    """
    Envía el reporte HTML como email.
    attachments: lista de {"name": "report.html", "content": "<bytes>"}
    """
    to_recipients = [{"emailAddress": {"address": addr}} for addr in to_addresses]

    message = {
        "subject": subject,
        "importance": "Normal",
        "body": {
            "contentType": "HTML",
            "content": html_body,
        },
        "toRecipients": to_recipients,
        "from": {"emailAddress": {"address": from_address}},
    }

    if attachments:
        message["attachments"] = []
        for att in attachments:
            content_bytes = att["content"]
            if isinstance(content_bytes, str):
                content_bytes = content_bytes.encode("utf-8")
            message["attachments"].append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": att["name"],
                "contentType": "text/html",
                "contentBytes": base64.b64encode(content_bytes).decode("utf-8"),
            })

    payload = {"message": message, "saveToSentItems": True}

    resp = requests.post(
        GRAPH_SEND_MAIL_URL,
        headers={
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
    )
    resp.raise_for_status()
    print(f"[Email] Enviado correctamente a: {', '.join(to_addresses)}")
