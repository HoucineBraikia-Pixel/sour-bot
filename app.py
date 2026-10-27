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
    "north": {"label": "الشمال", "douars": {"douar_north_1": "دوار الزيتون", "douar_north_2": "دوار النخيل", "douar_north_3": "دوار الأمل"}},
    "east": {"label": "الشرق", "douars": {"douar_east_1": "دوار الوديان", "douar_east_2": "دوار السلام", "douar_east_3": "دوار الفجر"}},
    "center": {"label": "الوسط", "douars": {"douar_center_1": "دوار الوسط", "douar_center_2": "دوار النور", "douar_center_3": "دوار الوحدة"}},
    "south": {"label": "الجنوب", "douars": {"douar_south_1": "دوار الواحة", "douar_south_2": "دوار الصحراء", "douar_south_3": "دوار الكرامة"}},
    "west": {"label": "الغرب", "douars": {"douar_west_1": "دوار الغروب", "douar_west_2": "دوار الشروق", "douar_west_3": "دوار التقدم"}},
}

ISSUES = {
    "water": {"label": "الماء", "response": "برنامجنا يضع تحسين التزود بالماء الصالح للشرب ضمن الأولويات: تأهيل الشبكات، إصلاح التسربات، وربط الدواوير بالمصادر المتاحة مع تتبع منتظم لجودة الخدمة."},
    "electricity": {"label": "الكهرباء", "response": "يتضمن البرنامج توسيع الربط بالكهرباء، صيانة الشبكات والإنارة العمومية، وتسريع معالجة الأعطاب لضمان خدمة آمنة ومستقرة."},
    "roads": {"label": "الطرقات", "response": "نلتزم بإعطاء الأولوية لفك العزلة: إصلاح المسالك، تحسين الطرقات المؤدية إلى الدواوير، ووضع برنامج للصيانة قبل وبعد فصل الأمطار."},
}

def quick_reply(title, payload):
    return {"content_type": "text", "title": title, "payload": payload}

def menu_replies():
    return [quick_reply(r["label"], f"REGION:{rid}") for rid, r in REGIONS.items()]

def menu_message():
    return {"text": "مرحبا بك. اختر المنطقة:", "quick_replies": menu_replies()}

def region_message(rid):
    region = REGIONS.get(rid)
    if not region:
        return None
    replies = [quick_reply(l, f"DOUAR:{d}") for d, l in region["douars"].items()]
    replies.append(quick_reply("العودة إلى القائمة", "MENU"))
    return {"text": f"اختر الدوار في {region['label']}:", "quick_replies": replies}

def douar_message(did):
    for region in REGIONS.values():
        if did in region["douars"]:
            replies = [quick_reply(i["label"], f"ISSUE:{iid}") for iid, i in ISSUES.items()]
            replies.append(quick_reply("العودة إلى القائمة", "MENU"))
            return {"text": f"ما الموضوع حول {region['douars'][did]}؟", "quick_replies": replies}
    return None

def issue_message(iid):
    issue = ISSUES.get(iid)
    if not issue:
        return None
    return {"text": issue["response"], "quick_replies": [quick_reply("العودة إلى القائمة", "MENU")]}

def send_message(rid, message):
    if not PAGE_ACCESS_TOKEN:
        return False
    try:
        r = requests.post(GRAPH_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json={"recipient": {"id": rid}, "message": message}, timeout=10)
        r.raise_for_status()
        return True
    except:
        return False

def handle_event(event):
    sid = event.get("sender", {}).get("id")
    if not sid:
        return
    msg = event.get("message", {})
    pb = event.get("postback", {})
    payload = msg.get("quick_reply", {}).get("payload") or pb.get("payload")
    out = None
    if payload:
        if payload == "MENU":
            out = menu_message()
        elif payload.startswith("REGION:"):
            out = region_message(payload[7:])
        elif payload.startswith("DOUAR:"):
            out = douar_message(payload[6:])
        elif payload.startswith("ISSUE:"):
            out = issue_message(payload[6:])
    else:
        text = msg.get("text", "").strip().lower()
        if text in {"مرحبا", "start", "بداية"}:
            out = menu_message()
    if out:
        send_message(sid, out)

@app.get("/")
def health():
    return jsonify({"status": "ok"})

@app.get("/webhook")
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Failed", 403

@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            handle_event(event)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
