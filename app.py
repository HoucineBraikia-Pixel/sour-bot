import logging
import os
from typing import Any, Dict, Iterable, Optional

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VERIFY_TOKEN = "sour_bot_2026"
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GRAPH_API_URL = "https://graph.facebook.com/v20.0/me/messages"

REGIONS = {
    "north": {
        "label": "الشمال",
        "douars": {
            "douar_north_1": "دوار الزيتون",
            "douar_north_2": "دوار النخيل",
            "douar_north_3": "دوار الأمل",
        },
    },
    "east": {
        "label": "الشرق",
        "douars": {
            "douar_east_1": "دوار الوديان",
            "douar_east_2": "دوار السلام",
            "douar_east_3": "دوار الفجر",
        },
    },
    "center": {
        "label": "الوسط",
        "douars": {
            "douar_center_1": "دوار الوسط",
            "douar_center_2": "دوار النور",
            "douar_center_3": "دوار الوحدة",
        },
    },
    "south": {
        "label": "الجنوب",
        "douars": {
            "douar_south_1": "دوار الواحة",
            "douar_south_2": "دوار الصحراء",
            "douar_south_3": "دوار الكرامة",
        },
    },
    "west": {
        "label": "الغرب",
        "douars": {
            "douar_west_1": "دوار الغروب",
            "douar_west_2": "دوار الشروق",
            "douar_west_3": "دوار التقدم",
        },
    },
}

ISSUES = {
    "water": {
        "label": "الماء",
        "response": (
            "برنامجنا يضع تحسين التزود بالماء الصالح للشرب ضمن الأولويات: "
            "تأهيل الشبكات، إصلاح التسربات، وربط الدواوير بالمصادر المتاحة "
            "مع تتبع منتظم لجودة الخدمة."
        ),
    },
    "electricity": {
        "label": "الكهرباء",
        "response": (
            "يتضمن البرنامج توسيع الربط بالكهرباء، صيانة الشبكات والإنارة "
            "العمومية، وتسريع معالجة الأعطاب لضمان خدمة آمنة ومستقرة."
        ),
    },
    "roads": {
        "label": "الطرقات",
        "response": (
            "نلتزم بإعطاء الأولوية لفك العزلة: إصلاح المسالك، تحسين الطرقات "
            "المؤدية إلى الدواوير، ووضع برنامج للصيانة قبل وبعد فصل الأمطار."
        ),
    },
}


def quick_reply(title: str, payload: str) -> Dict[str, str]:
    return {"content_type": "text", "title": title, "payload": payload}


def menu_replies() -> list:
    return [
        quick_reply(region["label"], f"REGION:{region_id}")
        for region_id, region in REGIONS.items()
    ]


def menu_message() -> Dict[str, Any]:
    return {
        "text": "مرحبا بك. اختر المنطقة التي تريد معرفة برنامجنا فيها:",
        "quick_replies": menu_replies(),
    }


def region_message(region_id: str) -> Optional[Dict[str, Any]]:
    region = REGIONS.get(region_id)
    if not region:
        return None

    replies = [
        quick_reply(label, f"DOUAR:{douar_id}")
        for douar_id, label in region["douars"].items()
    ]
    replies.append(quick_reply("العودة إلى القائمة", "MENU"))
    return {
        "text": f"اختر الدوار في منطقة {region['label']}:",
        "quick_replies": replies,
    }


def douar_message(douar_id: str) -> Optional[Dict[str, Any]]:
    for region in REGIONS.values():
        if douar_id in region["douars"]:
            douar_label = region["douars"][douar_id]
            replies = [
                quick_reply(issue["label"], f"ISSUE:{issue_id}")
                for issue_id, issue in ISSUES.items()
            ]
            replies.append(quick_reply("العودة إلى القائمة", "MENU"))
            return {
                "text": f"ما الموضوع الذي تريد معرفته حول {douar_label}؟",
                "quick_replies": replies,
            }
    return None


def issue_message(issue_id: str) -> Optional[Dict[str, Any]]:
    issue = ISSUES.get(issue_id)
    if not issue:
        return None
    return {
        "text": issue["response"],
        "quick_replies": [
            quick_reply("العودة إلى القائمة", "MENU"),
        ],
    }


def send_message(recipient_id: str, message: Dict[str, Any]) -> bool:
    if not PAGE_ACCESS_TOKEN:
        logger.error(
            "PAGE_ACCESS_TOKEN is not configured; cannot send to Messenger "
            "(recipient=%s)",
            recipient_id,
        )
        return False

    try:
        response = requests.post(
            GRAPH_API_URL,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={"recipient": {"id": recipient_id}, "message": message},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Messenger API request failed for recipient=%s", recipient_id)
        return False


def iter_messaging_events(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for entry in payload.get("entry", []):
        yield from entry.get("messaging", [])


def response_for_payload(payload: str) -> Optional[Dict[str, Any]]:
    if payload == "MENU":
        return menu_message()
    if payload.startswith("REGION:"):
        return region_message(payload.removeprefix("REGION:"))
    if payload.startswith("DOUAR:"):
        return douar_message(payload.removeprefix("DOUAR:"))
    if payload.startswith("ISSUE:"):
        return issue_message(payload.removeprefix("ISSUE:"))
    return None


def handle_messaging_event(event: Dict[str, Any]) -> None:
    sender = event.get("sender", {})
    sender_id = sender.get("id")
    if not sender_id:
        return

    message = event.get("message", {})
    postback = event.get("postback", {})
    payload = (
        message.get("quick_reply", {}).get("payload")
        or postback.get("payload")
    )

    outgoing_message: Optional[Dict[str, Any]] = None
    if payload:
        outgoing_message = response_for_payload(payload)
    else:
        text = message.get("text", "").strip().lower()
        if text in {"مرحبا", "start"}:
            outgoing_message = menu_message()

    if outgoing_message:
        send_message(sender_id, outgoing_message)


@app.get("/")
def health_check():
    return jsonify({"status": "ok", "service": "Facebook Messenger bot"})


@app.get("/webhook")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge or "", 200, {"Content-Type": "text/plain; charset=utf-8"}
    return "Verification failed", 403


@app.post("/webhook")
def receive_webhook():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON payload"}), 400

    if payload.get("object") not in (None, "page"):
        return jsonify({"error": "Unsupported webhook object"}), 404

    for event in iter_messaging_events(payload):
        handle_messaging_event(event)

    return "EVENT_RECEIVED", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
