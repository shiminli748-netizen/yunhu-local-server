#!/usr/bin/env python3
"""
云湖(YHChat)模拟服务器
HTTPS端口8443, WSS端口8444
"""

import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import ssl
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from aiohttp import web, WSMsgType

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
CERT_DIR = BASE_DIR / "cert"
ADMIN_DIR = BASE_DIR / "admin"
DB_PATH = DATA_DIR / "yunhu.db"

HTTPS_PORT = 8443
WSS_PORT = 8444

# ============================================================
# 工具函数
# ============================================================

def success(data=None, msg="success"):
    if data is None:
        data = {}
    return web.json_response({"code": 1, "data": data, "msg": msg})


def fail(msg="fail", code=-1):
    return web.json_response({"code": code, "data": {}, "msg": msg})


def now_ts():
    return int(time.time() * 1000)


def gen_id():
    return str(uuid.uuid4()).replace("-", "")


def gen_token():
    return str(uuid.uuid4())


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        email TEXT DEFAULT '',
        password TEXT DEFAULT '',
        avatar_url TEXT DEFAULT '',
        avatar_id INTEGER DEFAULT 0,
        token TEXT DEFAULT '',
        coin REAL DEFAULT 0,
        is_vip INTEGER DEFAULT 0,
        vip_expired_time INTEGER DEFAULT 0,
        invitation_code TEXT DEFAULT '',
        device_id TEXT DEFAULT '',
        platform TEXT DEFAULT '',
        register_time TEXT DEFAULT '',
        online_day INTEGER DEFAULT 0,
        continuous_online_day INTEGER DEFAULT 0,
        introduction TEXT DEFAULT '',
        gender INTEGER DEFAULT 0,
        birthday INTEGER DEFAULT 0,
        province TEXT DEFAULT '',
        city TEXT DEFAULT '',
        district TEXT DEFAULT '',
        location_code TEXT DEFAULT '',
        is_banned INTEGER DEFAULT 0,
        ban_time INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id TEXT UNIQUE,
        chat_id TEXT,
        chat_type INTEGER DEFAULT 0,
        sender_id TEXT,
        content TEXT DEFAULT '',
        content_type INTEGER DEFAULT 1,
        quote_msg_id TEXT DEFAULT '',
        timestamp INTEGER,
        msg_seq INTEGER DEFAULT 0,
        is_deleted INTEGER DEFAULT 0,
        is_recalled INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS groups (
        id TEXT PRIMARY KEY,
        name TEXT DEFAULT '',
        avatar_url TEXT DEFAULT '',
        introduction TEXT DEFAULT '',
        owner_id TEXT DEFAULT '',
        headcount INTEGER DEFAULT 0,
        create_time INTEGER,
        category TEXT DEFAULT '',
        is_dissolved INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT,
        user_id TEXT,
        nickname TEXT DEFAULT '',
        permission_level INTEGER DEFAULT 0,
        join_time INTEGER,
        is_gagged INTEGER DEFAULT 0,
        gag_until INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        friend_id TEXT,
        remark TEXT DEFAULT '',
        no_notify INTEGER DEFAULT 0,
        is_black INTEGER DEFAULT 0,
        add_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS friend_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id TEXT,
        to_id TEXT,
        target_id TEXT DEFAULT '',
        target_type INTEGER DEFAULT 0,
        remark TEXT DEFAULT '',
        result INTEGER DEFAULT 0,
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        chat_id TEXT,
        chat_type INTEGER DEFAULT 0,
        last_content TEXT DEFAULT '',
        last_timestamp INTEGER DEFAULT 0,
        unread_count INTEGER DEFAULT 0,
        is_do_not_disturb INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bots (
        id TEXT PRIMARY KEY,
        name TEXT DEFAULT '',
        avatar_url TEXT DEFAULT '',
        introduction TEXT DEFAULT '',
        owner_id TEXT DEFAULT '',
        token TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        headcount INTEGER DEFAULT 0,
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS medals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        medal_id INTEGER,
        medal_name TEXT DEFAULT '',
        sort INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS stickers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        name TEXT DEFAULT '',
        cover TEXT DEFAULT '',
        sort INTEGER DEFAULT 0,
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS expressions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        sticker_id INTEGER DEFAULT 0,
        name TEXT DEFAULT '',
        url TEXT DEFAULT '',
        sort INTEGER DEFAULT 0,
        is_top INTEGER DEFAULT 0,
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS stickies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        target_id TEXT,
        target_type INTEGER DEFAULT 0,
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS shares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        share_id TEXT UNIQUE,
        user_id TEXT,
        content TEXT DEFAULT '',
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        target_id TEXT,
        target_type INTEGER DEFAULT 0,
        reason TEXT DEFAULT '',
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        event_type TEXT DEFAULT '',
        content TEXT DEFAULT '',
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS user_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        data_key TEXT DEFAULT '',
        data_value TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS module_ignore (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        module_id TEXT DEFAULT '',
        is_ignored INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS group_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT,
        keyword TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS group_manage_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT,
        setting_key TEXT DEFAULT '',
        setting_value TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bot_group_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id TEXT,
        group_id TEXT,
        permission TEXT DEFAULT '{}'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bot_followers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id TEXT,
        user_id TEXT,
        create_time INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bot_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id TEXT,
        group_id TEXT,
        create_time INTEGER
    )""")

    # 创建默认管理员
    c.execute("SELECT id FROM users WHERE id='admin'")
    if not c.fetchone():
        admin_token = gen_token()
        c.execute(
            "INSERT INTO users (id,name,phone,email,password,token,is_admin,register_time) VALUES (?,?,?,?,?,?,?,?)",
            ("admin", "管理员", "13800000000", "admin@yunhu.local", "admin123", admin_token, 1, str(now_ts())),
        )
        print(f"默认管理员账号: admin / admin123, token: {admin_token}")

    # 创建默认测试群
    c.execute("SELECT id FROM groups WHERE id='default_group'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO groups (id,name,owner_id,headcount,create_time,category) VALUES (?,?,?,?,?,?)",
            ("default_group", "测试群聊", "admin", 1, now_ts(), "其他"),
        )
        c.execute(
            "INSERT INTO group_members (group_id,user_id,permission_level,join_time) VALUES (?,?,?,?)",
            ("default_group", "admin", 100, now_ts()),
        )

    # 创建默认机器人
    c.execute("SELECT id FROM bots WHERE id='default_bot'")
    if not c.fetchone():
        bot_token = gen_token()
        c.execute(
            "INSERT INTO bots (id,name,owner_id,token,create_time) VALUES (?,?,?,?,?)",
            ("default_bot", "测试机器人", "admin", bot_token, now_ts()),
        )

    conn.commit()
    conn.close()


# ============================================================
# Token验证中间件
# ============================================================

async def get_user_by_token(request):
    token = request.headers.get("token", "") or request.query.get("token", "")
    if not token:
        # 尝试从cookie获取
        token = request.cookies.get("token", "")
    if not token:
        return None
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    return None


def require_token(handler):
    async def wrapper(request):
        user = await get_user_by_token(request)
        if not user:
            return fail("未登录或token无效", 401)
        request["user"] = user
        return await handler(request)
    return wrapper


# ============================================================
# WSS连接管理
# ============================================================

class WSSManager:
    def __init__(self):
        self.connections = {}  # user_id -> set of WebSocketResponse

    def add(self, user_id, ws):
        if user_id not in self.connections:
            self.connections[user_id] = set()
        self.connections[user_id].add(ws)

    def remove(self, user_id, ws):
        if user_id in self.connections:
            self.connections[user_id].discard(ws)
            if not self.connections[user_id]:
                del self.connections[user_id]

    async def push_to_user(self, user_id, data):
        if user_id in self.connections:
            msg = json.dumps(data, ensure_ascii=False)
            dead = set()
            for ws in self.connections[user_id]:
                try:
                    await ws.send_str(msg)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self.connections[user_id].discard(ws)

    async def push_to_group(self, group_id, data, exclude_user_id=None):
        conn = get_db()
        try:
            rows = conn.execute("SELECT user_id FROM group_members WHERE group_id=?", (group_id,)).fetchall()
            for row in rows:
                uid = row["user_id"]
                if uid != exclude_user_id:
                    await self.push_to_user(uid, data)
        finally:
            conn.close()

    async def push_to_chat(self, chat_id, chat_type, data, exclude_user_id=None):
        if chat_type == 1:  # 私聊
            await self.push_to_user(chat_id, data)
        elif chat_type == 2:  # 群聊
            await self.push_to_group(chat_id, data, exclude_user_id)


wss_manager = WSSManager()


# ============================================================
# 消息序列号管理
# ============================================================

_msg_seq = 0

def next_msg_seq():
    global _msg_seq
    _msg_seq += 1
    return _msg_seq


# ============================================================
# 用户相关API
# ============================================================

async def user_captcha(request):
    captcha_id = gen_id()
    return success({
        "captchaId": captcha_id,
        "captchaUrl": f"https://127.0.0.1:{HTTPS_PORT}/static/captcha_placeholder.png"
    })


async def user_verification_login(request):
    data = await request.json()
    phone = data.get("mobile", data.get("phone", data.get("phoneNumber", "")))
    code = data.get("captcha", data.get("code", data.get("verificationCode", "")))
    device_id = data.get("deviceId", "")
    platform = data.get("platform", "android")

    if not phone:
        return fail("手机号不能为空")

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        if row:
            user = dict(row)
            token = gen_token()
            conn.execute("UPDATE users SET token=?, device_id=?, platform=? WHERE id=?",
                         (token, device_id, platform, user["id"]))
            conn.commit()
            user["token"] = token
        else:
            uid = gen_id()[:16]
            token = gen_token()
            name = f"用户{uid[:6]}"
            conn.execute(
                "INSERT INTO users (id,name,phone,token,device_id,platform,register_time,invitation_code) VALUES (?,?,?,?,?,?,?,?)",
                (uid, name, phone, token, device_id, platform, str(now_ts()), gen_id()[:8]),
            )
            conn.commit()
            user = dict(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

        return success({
            "userId": user["id"],
            "token": user["token"],
            "nickname": user["name"],
            "avatarUrl": user["avatar_url"],
            "phone": user["phone"],
        })
    finally:
        conn.close()


async def user_email_login(request):
    data = await request.json()
    email = data.get("email", "")
    password = data.get("password", "")
    device_id = data.get("deviceId", "")
    platform = data.get("platform", "android")

    if not email:
        return fail("邮箱不能为空")

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            user = dict(row)
            if user["password"] and user["password"] != password:
                return fail("密码错误")
            token = gen_token()
            conn.execute("UPDATE users SET token=?, device_id=?, platform=? WHERE id=?",
                         (token, device_id, platform, user["id"]))
            conn.commit()
            user["token"] = token
        else:
            uid = gen_id()[:16]
            token = gen_token()
            name = f"用户{uid[:6]}"
            conn.execute(
                "INSERT INTO users (id,name,email,password,token,device_id,platform,register_time,invitation_code) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, name, email, password, token, device_id, platform, str(now_ts()), gen_id()[:8]),
            )
            conn.commit()
            user = dict(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

        return success({
            "userId": user["id"],
            "token": user["token"],
            "nickname": user["name"],
            "avatarUrl": user["avatar_url"],
            "email": user["email"],
        })
    finally:
        conn.close()


async def user_jverify_login(request):
    data = await request.json()
    device_id = data.get("deviceId", "")
    platform = data.get("platform", "android")

    uid = gen_id()[:16]
    token = gen_token()
    name = f"用户{uid[:6]}"

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (id,name,token,device_id,platform,register_time,invitation_code) VALUES (?,?,?,?,?,?,?)",
            (uid, name, token, device_id, platform, str(now_ts()), gen_id()[:8]),
        )
        conn.commit()
    finally:
        conn.close()

    return success({
        "userId": uid,
        "token": token,
        "nickname": name,
    })


async def user_verification_register(request):
    data = await request.json()
    phone = data.get("mobile", data.get("phone", data.get("phoneNumber", "")))
    code = data.get("captcha", data.get("code", data.get("verificationCode", "")))
    password = data.get("password", "")
    device_id = data.get("deviceId", "")
    platform = data.get("platform", "android")

    if not phone:
        return fail("手机号不能为空")

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        if row:
            return fail("手机号已注册")
        uid = gen_id()[:16]
        token = gen_token()
        name = f"用户{uid[:6]}"
        conn.execute(
            "INSERT INTO users (id,name,phone,password,token,device_id,platform,register_time,invitation_code) VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, name, phone, password, token, device_id, platform, str(now_ts()), gen_id()[:8]),
        )
        conn.commit()
        return success({
            "userId": uid,
            "token": token,
            "nickname": name,
        })
    finally:
        conn.close()


@require_token
async def user_info(request):
    user = request["user"]
    return success({
        "userId": user["id"],
        "nickname": user["name"],
        "avatarUrl": user["avatar_url"],
        "avatarId": user["avatar_id"],
        "phone": user["phone"],
        "email": user["email"],
        "coin": user["coin"],
        "isVip": user["is_vip"],
        "vipExpiredTime": user["vip_expired_time"],
        "introduction": user["introduction"],
        "gender": user["gender"],
        "birthday": user["birthday"],
        "province": user["province"],
        "city": user["city"],
        "district": user["district"],
        "invitationCode": user["invitation_code"],
        "onlineDay": user["online_day"],
        "continuousOnlineDay": user["continuous_online_day"],
        "isAdmin": user["is_admin"],
    })


async def user_get_user(request):
    data = await request.json()
    uid = data.get("userId", "")
    if not uid:
        return fail("用户ID不能为空")

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return fail("用户不存在")
        user = dict(row)
    finally:
        conn.close()

    return success({
        "userId": user["id"],
        "nickname": user["name"],
        "avatarUrl": user["avatar_url"],
        "avatarId": user["avatar_id"],
        "introduction": user["introduction"],
        "gender": user["gender"],
        "birthday": user["birthday"],
        "province": user["province"],
        "city": user["city"],
        "district": user["district"],
        "isVip": user["is_vip"],
        "vipExpiredTime": user["vip_expired_time"],
    })


@require_token
async def user_edit_nickname(request):
    data = await request.json()
    nickname = data.get("nickname", "")
    if not nickname:
        return fail("昵称不能为空")
    conn = get_db()
    try:
        conn.execute("UPDATE users SET name=? WHERE id=?", (nickname, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def user_edit_avatar(request):
    data = await request.json()
    avatar_url = data.get("avatarUrl", "")
    avatar_id = data.get("avatarId", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE users SET avatar_url=?, avatar_id=? WHERE id=?",
                     (avatar_url, avatar_id, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def user_logout(request):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET token='' WHERE id=?", (request["user"]["id"],))
        conn.commit()
    finally:
        conn.close()
    return success()


async def user_recommend_category_list(request):
    categories = [
        {"id": "1", "name": "游戏", "icon": "🎮"},
        {"id": "2", "name": "技术", "icon": "💻"},
        {"id": "3", "name": "生活", "icon": "🏠"},
        {"id": "4", "name": "娱乐", "icon": "🎉"},
        {"id": "5", "name": "学习", "icon": "📚"},
        {"id": "6", "name": "其他", "icon": "📌"},
    ]
    return success({"list": categories})


async def user_recommend_list(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM groups WHERE is_dissolved=0 LIMIT 20").fetchall()
        groups = []
        for r in rows:
            groups.append({
                "groupId": r["id"],
                "name": r["name"],
                "avatarUrl": r["avatar_url"],
                "introduction": r["introduction"],
                "headcount": r["headcount"],
                "category": r["category"],
            })
    finally:
        conn.close()
    return success({"list": groups})


async def user_recommend(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM bots WHERE is_active=1 LIMIT 10").fetchall()
        bots = []
        for r in rows:
            bots.append({
                "botId": r["id"],
                "name": r["name"],
                "avatarUrl": r["avatar_url"],
                "introduction": r["introduction"],
                "headcount": r["headcount"],
            })
    finally:
        conn.close()
    return success({"list": bots})


@require_token
async def user_module_ignore_info(request):
    return success({"list": []})


@require_token
async def user_module_ignore(request):
    return success()


@require_token
async def user_notification_status(request):
    return success({"status": 1})


@require_token
async def user_notification_info(request):
    return success()


@require_token
async def user_gold_coin_record(request):
    return success({"list": [], "total": 0})


@require_token
async def user_bind_phone(request):
    return success()


@require_token
async def user_bind_email(request):
    return success()


@require_token
async def user_change_phone_check(request):
    return success()


@require_token
async def user_change_email_check(request):
    return success()


@require_token
async def user_forget_password(request):
    return success()


@require_token
async def user_save_user_data(request):
    data = await request.json()
    user = request["user"]
    conn = get_db()
    try:
        fields = []
        values = []
        mapping = {
            "nickname": "name",
            "introduction": "introduction",
            "gender": "gender",
            "birthday": "birthday",
            "province": "province",
            "city": "city",
            "district": "district",
            "locationCode": "location_code",
        }
        for key, col in mapping.items():
            if key in data:
                fields.append(f"{col}=?")
                values.append(data[key])
        if fields:
            values.append(user["id"])
            conn.execute(f"UPDATE users SET {','.join(fields)} WHERE id=?", values)
            conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def user_get_user_data(request):
    user = request["user"]
    return success({
        "nickname": user["name"],
        "introduction": user["introduction"],
        "gender": user["gender"],
        "birthday": user["birthday"],
        "province": user["province"],
        "city": user["city"],
        "district": user["district"],
        "locationCode": user["location_code"],
    })


async def user_get_user_show_adv(request):
    return success({"showAdv": False})


@require_token
async def user_save_user_remarks(request):
    data = await request.json()
    friend_id = data.get("friendId", data.get("userId", ""))
    remark = data.get("remark", "")
    conn = get_db()
    try:
        conn.execute("UPDATE friends SET remark=? WHERE user_id=? AND friend_id=?",
                     (remark, request["user"]["id"], friend_id))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def user_cancel_user(request):
    uid = request["user"]["id"]
    conn = get_db()
    try:
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.execute("DELETE FROM friends WHERE user_id=? OR friend_id=?", (uid, uid))
        conn.execute("DELETE FROM group_members WHERE user_id=?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def user_device_offline(request):
    return success()


@require_token
async def user_medal(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM medals WHERE user_id=?", (request["user"]["id"],)).fetchall()
        medals = [dict(r) for r in rows]
    finally:
        conn.close()
    return success({"list": medals})


@require_token
async def user_clients(request):
    return success({"list": []})


async def user_ad_code(request):
    return success({"code": ""})


@require_token
async def user_ban_appeal(request):
    return success()


async def user_check_version(request):
    return success({
        "version": "99.99.99",
        "isForce": False,
        "downloadUrl": "",
        "description": "已是最新版本",
    })


# ============================================================
# 验证相关API
# ============================================================

async def verification_get_code(request):
    return success()


async def verification_get_email_code(request):
    return success()


# ============================================================
# 消息相关API
# ============================================================

@require_token
async def msg_send_message(request):
    data = await request.json()
    user = request["user"]
    chat_id = data.get("chatId", "")
    chat_type = data.get("chatType", 1)
    content = data.get("content", "")
    content_type = data.get("contentType", 1)
    quote_msg_id = data.get("quoteMsgId", "")

    if not chat_id:
        return fail("chatId不能为空")

    msg_id = gen_id()
    ts = now_ts()
    seq = next_msg_seq()

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO messages (msg_id,chat_id,chat_type,sender_id,content,content_type,quote_msg_id,timestamp,msg_seq) VALUES (?,?,?,?,?,?,?,?,?)",
            (msg_id, chat_id, chat_type, user["id"], content, content_type, quote_msg_id, ts, seq),
        )

        # 更新会话
        conn.execute(
            "INSERT OR REPLACE INTO conversations (user_id,chat_id,chat_type,last_content,last_timestamp,unread_count) VALUES (?,?,?,?,?,0)",
            (user["id"], chat_id, chat_type, content, ts),
        )

        # 如果是私聊，对方也有会话
        if chat_type == 1:
            conn.execute(
                "INSERT OR REPLACE INTO conversations (user_id,chat_id,chat_type,last_content,last_timestamp,unread_count) VALUES (?,?,?,?,?,1)",
                (chat_id, user["id"], chat_type, content, ts),
            )

        conn.commit()
    finally:
        conn.close()

    msg_data = {
        "type": "push_message",
        "data": {
            "msgId": msg_id,
            "chatId": chat_id,
            "chatType": chat_type,
            "senderId": user["id"],
            "senderNickname": user["name"],
            "senderAvatarUrl": user["avatar_url"],
            "content": content,
            "contentType": content_type,
            "quoteMsgId": quote_msg_id,
            "timestamp": ts,
            "msgSeq": seq,
        }
    }

    if chat_type == 1:
        await wss_manager.push_to_user(chat_id, msg_data)
        await wss_manager.push_to_user(user["id"], msg_data)
    elif chat_type == 2:
        await wss_manager.push_to_group(chat_id, msg_data, exclude_user_id=user["id"])
        await wss_manager.push_to_user(user["id"], msg_data)

    return success({
        "msgId": msg_id,
        "timestamp": ts,
        "msgSeq": seq,
    })


@require_token
async def msg_edit_message(request):
    data = await request.json()
    msg_id = data.get("msgId", "")
    content = data.get("content", "")
    if not msg_id:
        return fail("msgId不能为空")
    conn = get_db()
    try:
        conn.execute("UPDATE messages SET content=? WHERE msg_id=?", (content, msg_id))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def msg_list_message(request):
    data = await request.json()
    chat_id = data.get("chatId", "")
    limit = data.get("limit", 20)
    offset = data.get("offset", 0)
    start_seq = data.get("startSeq", 0)

    conn = get_db()
    try:
        if start_seq > 0:
            rows = conn.execute(
                "SELECT * FROM messages WHERE chat_id=? AND msg_seq<? AND is_deleted=0 ORDER BY msg_seq DESC LIMIT ?",
                (chat_id, start_seq, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE chat_id=? AND is_deleted=0 ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (chat_id, limit, offset),
            ).fetchall()

        messages = []
        for r in rows:
            sender = conn.execute("SELECT id,name,avatar_url FROM users WHERE id=?", (r["sender_id"],)).fetchone()
            messages.append({
                "msgId": r["msg_id"],
                "chatId": r["chat_id"],
                "chatType": r["chat_type"],
                "senderId": r["sender_id"],
                "senderNickname": sender["name"] if sender else "",
                "senderAvatarUrl": sender["avatar_url"] if sender else "",
                "content": r["content"],
                "contentType": r["content_type"],
                "quoteMsgId": r["quote_msg_id"],
                "timestamp": r["timestamp"],
                "msgSeq": r["msg_seq"],
                "isRecalled": r["is_recalled"],
            })
    finally:
        conn.close()
    return success({"list": messages})


@require_token
async def msg_list_message_by_seq(request):
    return await msg_list_message(request)


@require_token
async def msg_list_message_by_mid_seq(request):
    return await msg_list_message(request)


@require_token
async def msg_recall_msg(request):
    data = await request.json()
    msg_id = data.get("msgId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE messages SET is_recalled=1 WHERE msg_id=?", (msg_id,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def msg_recall_msg_batch(request):
    data = await request.json()
    msg_ids = data.get("msgIds", [])
    conn = get_db()
    try:
        for mid in msg_ids:
            conn.execute("UPDATE messages SET is_recalled=1 WHERE msg_id=?", (mid,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def msg_delete(request):
    data = await request.json()
    msg_id = data.get("msgId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE messages SET is_deleted=1 WHERE msg_id=?", (msg_id,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def msg_clean(request):
    data = await request.json()
    chat_id = data.get("chatId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE messages SET is_deleted=1 WHERE chat_id=?", (chat_id,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def msg_pic_list_message_by_mid_seq(request):
    return await msg_list_message(request)


async def msg_a2ui_form_report(request):
    return success()


async def msg_button_report(request):
    return success()


async def msg_file_download_record(request):
    return success()


# ============================================================
# 好友相关API
# ============================================================

@require_token
async def friend_apply(request):
    data = await request.json()
    user = request["user"]
    target_id = data.get("targetId", data.get("toId", ""))
    target_type = data.get("targetType", 1)  # 1用户, 2群, 3机器人
    remark = data.get("remark", "")

    if not target_id:
        return fail("目标ID不能为空")

    conn = get_db()
    try:
        # 检查是否已经是好友
        if target_type == 1:
            row = conn.execute(
                "SELECT id FROM friends WHERE user_id=? AND friend_id=? AND is_black=0",
                (user["id"], target_id),
            ).fetchone()
            if row:
                return fail("已经是好友")

        req_id = conn.execute(
            "INSERT INTO friend_requests (from_id,to_id,target_id,target_type,remark,create_time) VALUES (?,?,?,?,?,?)",
            (user["id"], target_id, target_id, target_type, remark, now_ts()),
        ).lastrowid
        conn.commit()

        # 通知对方
        await wss_manager.push_to_user(target_id, {
            "type": "invite_apply",
            "data": {
                "requestId": req_id,
                "fromId": user["id"],
                "fromNickname": user["name"],
                "fromAvatarUrl": user["avatar_url"],
                "targetId": target_id,
                "targetType": target_type,
                "remark": remark,
            }
        })
    finally:
        conn.close()
    return success()


@require_token
async def friend_delete_friend(request):
    data = await request.json()
    friend_id = data.get("friendId", "")
    conn = get_db()
    try:
        conn.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (request["user"]["id"], friend_id))
        conn.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (friend_id, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def friend_agree_apply(request):
    data = await request.json()
    request_id = data.get("requestId", "")
    user = request["user"]

    conn = get_db()
    try:
        req = conn.execute("SELECT * FROM friend_requests WHERE id=?", (request_id,)).fetchone()
        if not req:
            return fail("请求不存在")

        from_id = req["from_id"]
        target_id = req["target_id"]
        target_type = req["target_type"]

        conn.execute("UPDATE friend_requests SET result=1 WHERE id=?", (request_id,))

        if target_type == 1:  # 加好友
            conn.execute(
                "INSERT OR IGNORE INTO friends (user_id,friend_id,add_time) VALUES (?,?,?)",
                (from_id, user["id"], now_ts()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO friends (user_id,friend_id,add_time) VALUES (?,?,?)",
                (user["id"], from_id, now_ts()),
            )
        elif target_type == 2:  # 加群
            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id,user_id,permission_level,join_time) VALUES (?,?,0,?)",
                (target_id, from_id, now_ts()),
            )
            conn.execute("UPDATE groups SET headcount=headcount+1 WHERE id=?", (target_id,))
        elif target_type == 3:  # 加机器人
            conn.execute(
                "INSERT OR IGNORE INTO bot_followers (bot_id,user_id,create_time) VALUES (?,?,?)",
                (target_id, from_id, now_ts()),
            )
            conn.execute("UPDATE bots SET headcount=headcount+1 WHERE id=?", (target_id,))

        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def friend_ignore_apply(request):
    data = await request.json()
    request_id = data.get("requestId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE friend_requests SET result=2 WHERE id=?", (request_id,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def friend_address_book_list(request):
    user = request["user"]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT f.*, u.name as friend_name, u.avatar_url as friend_avatar FROM friends f "
            "LEFT JOIN users u ON f.friend_id=u.id WHERE f.user_id=? AND f.is_black=0 ORDER BY u.name",
            (user["id"],),
        ).fetchall()
        friends = []
        for r in rows:
            friends.append({
                "friendId": r["friend_id"],
                "nickname": r["friend_name"] or "",
                "avatarUrl": r["friend_avatar"] or "",
                "remark": r["remark"] or "",
                "noNotify": r["no_notify"],
            })
    finally:
        conn.close()
    return success({"list": friends})


@require_token
async def friend_request_list(request):
    user = request["user"]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT fr.*, u.name as from_name, u.avatar_url as from_avatar FROM friend_requests fr "
            "LEFT JOIN users u ON fr.from_id=u.id WHERE fr.to_id=? ORDER BY fr.create_time DESC",
            (user["id"],),
        ).fetchall()
        requests = []
        for r in rows:
            requests.append({
                "requestId": r["id"],
                "fromId": r["from_id"],
                "fromNickname": r["from_name"] or "",
                "fromAvatarUrl": r["from_avatar"] or "",
                "targetId": r["target_id"],
                "targetType": r["target_type"],
                "remark": r["remark"] or "",
                "result": r["result"],
                "createTime": r["create_time"],
            })
    finally:
        conn.close()
    return success({"list": requests})


@require_token
async def friend_no_notify(request):
    data = await request.json()
    friend_id = data.get("friendId", "")
    no_notify = data.get("noNotify", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE friends SET no_notify=? WHERE user_id=? AND friend_id=?",
                     (no_notify, request["user"]["id"], friend_id))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def friend_delete_request(request):
    data = await request.json()
    request_id = data.get("requestId", "")
    conn = get_db()
    try:
        conn.execute("DELETE FROM friend_requests WHERE id=?", (request_id,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def friend_set_black_list(request):
    data = await request.json()
    friend_id = data.get("friendId", "")
    is_black = data.get("isBlack", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE friends SET is_black=? WHERE user_id=? AND friend_id=?",
                     (is_black, request["user"]["id"], friend_id))
        conn.commit()
    finally:
        conn.close()
    return success()


# ============================================================
# 群组相关API
# ============================================================

@require_token
async def group_create_group(request):
    data = await request.json()
    user = request["user"]
    name = data.get("name", "新群组")
    introduction = data.get("introduction", "")
    category = data.get("category", "")

    gid = gen_id()[:16]
    ts = now_ts()

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO groups (id,name,owner_id,headcount,create_time,category,introduction) VALUES (?,?,?,?,?,?,?)",
            (gid, name, user["id"], 1, ts, category, introduction),
        )
        conn.execute(
            "INSERT INTO group_members (group_id,user_id,permission_level,join_time) VALUES (?,?,100,?)",
            (gid, user["id"], ts),
        )
        conn.commit()
    finally:
        conn.close()

    return success({
        "groupId": gid,
        "name": name,
        "ownerId": user["id"],
    })


async def group_info(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    gid = data.get("groupId", "")

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM groups WHERE id=?", (gid,)).fetchone()
        if not row:
            return fail("群组不存在")
        g = dict(row)
    finally:
        conn.close()

    return success({
        "groupId": g["id"],
        "name": g["name"],
        "avatarUrl": g["avatar_url"],
        "introduction": g["introduction"],
        "ownerId": g["owner_id"],
        "headcount": g["headcount"],
        "createTime": g["create_time"],
        "category": g["category"],
        "isDissolved": g["is_dissolved"],
    })


@require_token
async def group_edit_group(request):
    data = await request.json()
    gid = data.get("groupId", "")
    conn = get_db()
    try:
        fields = []
        values = []
        for key, col in [("name", "name"), ("avatarUrl", "avatar_url"), ("introduction", "introduction"), ("category", "category")]:
            if key in data:
                fields.append(f"{col}=?")
                values.append(data[key])
        if fields:
            values.append(gid)
            conn.execute(f"UPDATE groups SET {','.join(fields)} WHERE id=?", values)
            conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def group_dismiss_group(request):
    data = await request.json()
    gid = data.get("groupId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE groups SET is_dissolved=1 WHERE id=?", (gid,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def group_invite(request):
    data = await request.json()
    gid = data.get("groupId", "")
    user_ids = data.get("userIds", [])

    conn = get_db()
    try:
        for uid in user_ids:
            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id,user_id,permission_level,join_time) VALUES (?,?,0,?)",
                (gid, uid, now_ts()),
            )
        conn.execute("UPDATE groups SET headcount=(SELECT COUNT(*) FROM group_members WHERE group_id=?) WHERE id=?", (gid, gid))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def group_remove_member(request):
    data = await request.json()
    gid = data.get("groupId", "")
    uid = data.get("userId", "")
    conn = get_db()
    try:
        conn.execute("DELETE FROM group_members WHERE group_id=? AND user_id=?", (gid, uid))
        conn.execute("UPDATE groups SET headcount=headcount-1 WHERE id=? AND headcount>0", (gid,))
        conn.commit()
    finally:
        conn.close()
    return success()


async def group_list_member(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    gid = data.get("groupId", "")

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT gm.*, u.name as user_name, u.avatar_url as user_avatar FROM group_members gm "
            "LEFT JOIN users u ON gm.user_id=u.id WHERE gm.group_id=? ORDER BY gm.permission_level DESC",
            (gid,),
        ).fetchall()
        members = []
        for r in rows:
            members.append({
                "userId": r["user_id"],
                "nickname": r["nickname"] or r["user_name"] or "",
                "avatarUrl": r["user_avatar"] or "",
                "permissionLevel": r["permission_level"],
                "joinTime": r["join_time"],
                "isGagged": r["is_gagged"],
                "gagUntil": r["gag_until"],
            })
    finally:
        conn.close()
    return success({"list": members})


@require_token
async def group_gag_member(request):
    data = await request.json()
    gid = data.get("groupId", "")
    uid = data.get("userId", "")
    is_gag = data.get("isGag", 1)
    gag_until = data.get("gagUntil", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE group_members SET is_gagged=?, gag_until=? WHERE group_id=? AND user_id=?",
                     (is_gag, gag_until, gid, uid))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def group_edit_my_group_nickname(request):
    data = await request.json()
    gid = data.get("groupId", "")
    nickname = data.get("nickname", "")
    conn = get_db()
    try:
        conn.execute("UPDATE group_members SET nickname=? WHERE group_id=? AND user_id=?",
                     (nickname, gid, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def group_transfer_group(request):
    data = await request.json()
    gid = data.get("groupId", "")
    new_owner = data.get("userId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE groups SET owner_id=? WHERE id=?", (new_owner, gid))
        conn.execute("UPDATE group_members SET permission_level=100 WHERE group_id=? AND user_id=?", (gid, new_owner))
        conn.execute("UPDATE group_members SET permission_level=0 WHERE group_id=? AND user_id=? AND user_id!=?",
                     (gid, request["user"]["id"], new_owner))
        conn.commit()
    finally:
        conn.close()
    return success()


async def group_live_room(request):
    return success({})


async def group_bot_list(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    gid = data.get("groupId", "")
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT b.* FROM bots b JOIN bot_groups bg ON b.id=bg.bot_id WHERE bg.group_id=?",
            (gid,),
        ).fetchall()
        bots = []
        for r in rows:
            bots.append({
                "botId": r["id"],
                "name": r["name"],
                "avatarUrl": r["avatar_url"],
                "introduction": r["introduction"],
            })
    finally:
        conn.close()
    return success({"list": bots})


async def group_remove_bot(request):
    return success()


async def group_category(request):
    return success({"list": [
        {"id": "1", "name": "游戏"},
        {"id": "2", "name": "技术"},
        {"id": "3", "name": "生活"},
        {"id": "4", "name": "娱乐"},
        {"id": "5", "name": "学习"},
        {"id": "6", "name": "其他"},
    ]})


async def group_manage_setting(request):
    return success({})


async def group_check_master_is_vip(request):
    return success({"isVip": True})


async def group_member_is_removed(request):
    return success({"isRemoved": False})


async def group_edit_auto_delete_message(request):
    return success()


async def group_edit_stop_member_upload_group_file(request):
    return success()


async def group_edit_group_keyword(request):
    return success()


async def group_msg_type_limit(request):
    return success({"list": []})


async def group_info_add_friend(request):
    return success()


async def group_instruction_list(request):
    return success({"list": []})


async def group_instruction_setting(request):
    return success()


async def group_instruction_sort(request):
    return success()


async def group_recommend_switch(request):
    return success()


async def group_list_manage(request):
    user = request["user"] if "user" in request else None
    conn = get_db()
    try:
        if user:
            rows = conn.execute(
                "SELECT g.* FROM groups g JOIN group_members gm ON g.id=gm.group_id WHERE gm.user_id=? AND g.is_dissolved=0",
                (user["id"],),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM groups WHERE is_dissolved=0").fetchall()
        groups = []
        for r in rows:
            groups.append({
                "groupId": r["id"],
                "name": r["name"],
                "avatarUrl": r["avatar_url"],
                "headcount": r["headcount"],
                "ownerId": r["owner_id"],
            })
    finally:
        conn.close()
    return success({"list": groups})


async def group_agree_invite(request):
    data = await request.json()
    gid = data.get("groupId", "")
    user = request.get("user")
    if not user:
        return fail("未登录")
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO group_members (group_id,user_id,permission_level,join_time) VALUES (?,?,0,?)",
            (gid, user["id"], now_ts()),
        )
        conn.execute("UPDATE groups SET headcount=headcount+1 WHERE id=?", (gid,))
        conn.commit()
    finally:
        conn.close()
    return success()


# ============================================================
# 会话相关API
# ============================================================

@require_token
async def conversation_dismiss_notification(request):
    data = await request.json()
    chat_id = data.get("chatId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE conversations SET unread_count=0 WHERE user_id=? AND chat_id=?",
                     (request["user"]["id"], chat_id))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def conversation_list(request):
    user = request["user"]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id=? ORDER BY last_timestamp DESC",
            (user["id"],),
        ).fetchall()
        convs = []
        for r in rows:
            chat_id = r["chat_id"]
            chat_type = r["chat_type"]
            name = ""
            avatar = ""
            if chat_type == 1:  # 私聊
                u = conn.execute("SELECT name,avatar_url FROM users WHERE id=?", (chat_id,)).fetchone()
                if u:
                    name = u["name"]
                    avatar = u["avatar_url"]
            elif chat_type == 2:  # 群聊
                g = conn.execute("SELECT name,avatar_url FROM groups WHERE id=?", (chat_id,)).fetchone()
                if g:
                    name = g["name"]
                    avatar = g["avatar_url"]

            convs.append({
                "chatId": chat_id,
                "chatType": chat_type,
                "name": name,
                "avatarUrl": avatar,
                "lastContent": r["last_content"],
                "lastTimestamp": r["last_timestamp"],
                "unreadCount": r["unread_count"],
                "isDoNotDisturb": r["is_do_not_disturb"],
                "sortOrder": r["sort_order"],
            })
    finally:
        conn.close()
    return success({"list": convs})


@require_token
async def conversation_sort_change(request):
    return success()


@require_token
async def conversation_remove(request):
    data = await request.json()
    chat_id = data.get("chatId", "")
    conn = get_db()
    try:
        conn.execute("DELETE FROM conversations WHERE user_id=? AND chat_id=?",
                     (request["user"]["id"], chat_id))
        conn.commit()
    finally:
        conn.close()
    return success()


# ============================================================
# 杂项API
# ============================================================

async def misc_configure_distribution(request):
    return success({
        "apiUrl": f"https://127.0.0.1:{HTTPS_PORT}",
        "wsUrl": f"wss://127.0.0.1:{WSS_PORT}/ws",
        "uploadUrl": f"https://127.0.0.1:{HTTPS_PORT}/v1/upload",
        "cdnUrl": f"https://127.0.0.1:{HTTPS_PORT}/static",
        "fileUrl": f"https://127.0.0.1:{HTTPS_PORT}/static/uploads",
    })


async def misc_qiniu_token(request):
    return success({
        "token": "fake_qiniu_token_" + gen_id()[:8],
        "key": gen_id()[:12],
        "domain": f"https://127.0.0.1:{HTTPS_PORT}/static/uploads",
    })


async def misc_qiniu_token_audio(request):
    return await misc_qiniu_token(request)


async def misc_qiniu_token2(request):
    return await misc_qiniu_token(request)


async def misc_qiniu_token_video(request):
    return await misc_qiniu_token(request)


async def misc_qiniu_token_group_disk(request):
    return await misc_qiniu_token(request)


async def misc_setting(request):
    return success({
        "enableRegistration": True,
        "enableGroupCreation": True,
        "enableBotCreation": True,
        "maxGroupMembers": 500,
        "maxFileSize": 104857600,
    })


async def misc_gray_status(request):
    return success({"status": 0})


async def misc_auto_update(request):
    return success({"needUpdate": False})


# ============================================================
# 检查相关API
# ============================================================

async def check_version_mobile(request):
    return success({
        "version": "99.99.99",
        "isForce": False,
        "downloadUrl": "",
        "description": "已是最新版本",
    })


async def check_latest_version(request):
    return success({
        "version": "99.99.99",
        "downloadUrl": "",
    })


async def check_version(request):
    return success({
        "version": "99.99.99",
        "isForce": False,
        "downloadUrl": "",
    })


# ============================================================
# 机器人相关API
# ============================================================

async def bot_new_list(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM bots WHERE is_active=1 ORDER BY create_time DESC LIMIT 20").fetchall()
        bots = []
        for r in rows:
            bots.append({
                "botId": r["id"],
                "name": r["name"],
                "avatarUrl": r["avatar_url"],
                "introduction": r["introduction"],
                "headcount": r["headcount"],
            })
    finally:
        conn.close()
    return success({"list": bots})


async def bot_banner(request):
    return success({"list": []})


async def bot_bot_detail(request):
    data = await request.json()
    bot_id = data.get("botId", "")
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
        if not row:
            return fail("机器人不存在")
        bot = dict(row)
    finally:
        conn.close()
    return success({
        "botId": bot["id"],
        "name": bot["name"],
        "avatarUrl": bot["avatar_url"],
        "introduction": bot["introduction"],
        "ownerId": bot["owner_id"],
        "token": bot["token"],
        "isActive": bot["is_active"],
        "headcount": bot["headcount"],
        "createTime": bot["create_time"],
    })


async def bot_bot_info(request):
    return await bot_bot_detail(request)


@require_token
async def bot_create_bot(request):
    data = await request.json()
    user = request["user"]
    name = data.get("name", "新机器人")
    introduction = data.get("introduction", "")

    bid = gen_id()[:16]
    token = gen_token()
    ts = now_ts()

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO bots (id,name,owner_id,token,create_time,introduction) VALUES (?,?,?,?,?,?)",
            (bid, name, user["id"], token, ts, introduction),
        )
        conn.commit()
    finally:
        conn.close()

    return success({
        "botId": bid,
        "name": name,
        "token": token,
    })


@require_token
async def bot_edit_bot(request):
    data = await request.json()
    bid = data.get("botId", "")
    conn = get_db()
    try:
        fields = []
        values = []
        for key, col in [("name", "name"), ("avatarUrl", "avatar_url"), ("introduction", "introduction")]:
            if key in data:
                fields.append(f"{col}=?")
                values.append(data[key])
        if fields:
            values.append(bid)
            conn.execute(f"UPDATE bots SET {','.join(fields)} WHERE id=?", values)
            conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def bot_stop_bot(request):
    data = await request.json()
    bid = data.get("botId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE bots SET is_active=0 WHERE id=?", (bid,))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def bot_reset_bot_token(request):
    data = await request.json()
    bid = data.get("botId", "")
    new_token = gen_token()
    conn = get_db()
    try:
        conn.execute("UPDATE bots SET token=? WHERE id=?", (new_token, bid))
        conn.commit()
    finally:
        conn.close()
    return success({"token": new_token})


@require_token
async def bot_console_my_bots(request):
    user = request["user"]
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM bots WHERE owner_id=?", (user["id"],)).fetchall()
        bots = []
        for r in rows:
            bots.append({
                "botId": r["id"],
                "name": r["name"],
                "avatarUrl": r["avatar_url"],
                "introduction": r["introduction"],
                "token": r["token"],
                "isActive": r["is_active"],
                "headcount": r["headcount"],
                "createTime": r["create_time"],
            })
    finally:
        conn.close()
    return success({"list": bots})


async def bot_follower_list(request):
    data = await request.json()
    bot_id = data.get("botId", "")
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT bf.*, u.name as user_name, u.avatar_url as user_avatar FROM bot_followers bf "
            "LEFT JOIN users u ON bf.user_id=u.id WHERE bf.bot_id=?",
            (bot_id,),
        ).fetchall()
        followers = []
        for r in rows:
            followers.append({
                "userId": r["user_id"],
                "nickname": r["user_name"] or "",
                "avatarUrl": r["user_avatar"] or "",
            })
    finally:
        conn.close()
    return success({"list": followers})


async def bot_remove_follower(request):
    return success()


async def bot_add_friend_bot_info(request):
    data = await request.json()
    bot_id = data.get("botId", "")
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
        if not row:
            return fail("机器人不存在")
        bot = dict(row)
    finally:
        conn.close()
    return success({
        "botId": bot["id"],
        "name": bot["name"],
        "avatarUrl": bot["avatar_url"],
        "introduction": bot["introduction"],
    })


async def bot_board(request):
    return success({})


async def bot_group_permission_get(request):
    return success({"permission": {}})


async def bot_group_permission_edit(request):
    return success()


async def bot_join_group_list(request):
    data = await request.json()
    bot_id = data.get("botId", "")
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT g.* FROM groups g JOIN bot_groups bg ON g.id=bg.group_id WHERE bg.bot_id=?",
            (bot_id,),
        ).fetchall()
        groups = []
        for r in rows:
            groups.append({
                "groupId": r["id"],
                "name": r["name"],
            })
    finally:
        conn.close()
    return success({"list": groups})


async def bot_remove_group(request):
    return success()


async def bot_edit_subscribed_link(request):
    return success()


async def bot_bot_link_reset(request):
    return success({"link": gen_id()[:12]})


async def bot_edit_setting_json(request):
    return success()


async def bot_send_setting_json(request):
    return success()


async def bot_get_user_settings_json(request):
    return success({"settingsJson": "{}"})


# ============================================================
# 搜索相关API
# ============================================================

async def search_home_search(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    keyword = data.get("keyword", "")
    results = {"users": [], "groups": [], "bots": []}

    if keyword:
        conn = get_db()
        try:
            rows = conn.execute("SELECT id,name,avatar_url FROM users WHERE name LIKE ? LIMIT 5", (f"%{keyword}%",)).fetchall()
            for r in rows:
                results["users"].append({"userId": r["id"], "nickname": r["name"], "avatarUrl": r["avatar_url"]})

            rows = conn.execute("SELECT id,name,avatar_url,headcount FROM groups WHERE name LIKE ? AND is_dissolved=0 LIMIT 5", (f"%{keyword}%",)).fetchall()
            for r in rows:
                results["groups"].append({"groupId": r["id"], "name": r["name"], "avatarUrl": r["avatar_url"], "headcount": r["headcount"]})

            rows = conn.execute("SELECT id,name,avatar_url FROM bots WHERE name LIKE ? AND is_active=1 LIMIT 5", (f"%{keyword}%",)).fetchall()
            for r in rows:
                results["bots"].append({"botId": r["id"], "name": r["name"], "avatarUrl": r["avatar_url"]})
        finally:
            conn.close()

    return success(results)


async def search_chat_search(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    keyword = data.get("keyword", "")
    results = []
    if keyword:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM messages WHERE content LIKE ? AND is_deleted=0 LIMIT 20", (f"%{keyword}%",)
            ).fetchall()
            for r in rows:
                results.append({
                    "msgId": r["msg_id"],
                    "chatId": r["chat_id"],
                    "chatType": r["chat_type"],
                    "senderId": r["sender_id"],
                    "content": r["content"],
                    "contentType": r["content_type"],
                    "timestamp": r["timestamp"],
                })
        finally:
            conn.close()
    return success({"list": results})


# ============================================================
# 表情包相关API
# ============================================================

@require_token
async def sticker_list(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM stickers WHERE user_id=? ORDER BY sort", (request["user"]["id"],)).fetchall()
        stickers = [dict(r) for r in rows]
    finally:
        conn.close()
    return success({"list": stickers})


@require_token
async def sticker_add(request):
    data = await request.json()
    name = data.get("name", "")
    conn = get_db()
    try:
        conn.execute("INSERT INTO stickers (user_id,name,create_time) VALUES (?,?,?)",
                     (request["user"]["id"], name, now_ts()))
        conn.commit()
    finally:
        conn.close()
    return success()


async def sticker_detail(request):
    return success({})


@require_token
async def sticker_remove_sticker_pack(request):
    data = await request.json()
    sid = data.get("stickerId", 0)
    conn = get_db()
    try:
        conn.execute("DELETE FROM stickers WHERE id=? AND user_id=?", (sid, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


async def sticker_sort(request):
    return success()


# ============================================================
# 表情相关API
# ============================================================

@require_token
async def expression_add(request):
    data = await request.json()
    name = data.get("name", "")
    url = data.get("url", "")
    sticker_id = data.get("stickerId", 0)
    conn = get_db()
    try:
        conn.execute("INSERT INTO expressions (user_id,sticker_id,name,url,create_time) VALUES (?,?,?,?,?)",
                     (request["user"]["id"], sticker_id, name, url, now_ts()))
        conn.commit()
    finally:
        conn.close()
    return success()


async def expression_create(request):
    return await expression_add(request)


@require_token
async def expression_delete(request):
    data = await request.json()
    eid = data.get("expressionId", 0)
    conn = get_db()
    try:
        conn.execute("DELETE FROM expressions WHERE id=? AND user_id=?", (eid, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def expression_list(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM expressions WHERE user_id=? ORDER BY is_top DESC, sort, create_time",
                            (request["user"]["id"],)).fetchall()
        expressions = [dict(r) for r in rows]
    finally:
        conn.close()
    return success({"list": expressions})


@require_token
async def expression_topping(request):
    data = await request.json()
    eid = data.get("expressionId", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE expressions SET is_top=1 WHERE id=? AND user_id=?", (eid, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


# ============================================================
# 置顶相关API
# ============================================================

@require_token
async def sticky_list(request):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM stickies WHERE user_id=?", (request["user"]["id"],)).fetchall()
        items = [dict(r) for r in rows]
    finally:
        conn.close()
    return success({"list": items})


@require_token
async def sticky_topping(request):
    data = await request.json()
    target_id = data.get("targetId", "")
    target_type = data.get("targetType", 0)
    conn = get_db()
    try:
        conn.execute("INSERT INTO stickies (user_id,target_id,target_type,create_time) VALUES (?,?,?,?)",
                     (request["user"]["id"], target_id, target_type, now_ts()))
        conn.commit()
    finally:
        conn.close()
    return success()


@require_token
async def sticky_delete(request):
    data = await request.json()
    sid = data.get("stickyId", 0)
    conn = get_db()
    try:
        conn.execute("DELETE FROM stickies WHERE id=? AND user_id=?", (sid, request["user"]["id"]))
        conn.commit()
    finally:
        conn.close()
    return success()


# ============================================================
# 分享相关API
# ============================================================

@require_token
async def share_create(request):
    data = await request.json()
    share_id = gen_id()[:12]
    content = json.dumps(data, ensure_ascii=False)
    conn = get_db()
    try:
        conn.execute("INSERT INTO shares (share_id,user_id,content,create_time) VALUES (?,?,?,?)",
                     (share_id, request["user"]["id"], content, now_ts()))
        conn.commit()
    finally:
        conn.close()
    return success({"shareId": share_id})


async def share_info(request):
    data = await request.json()
    share_id = data.get("shareId", "")
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM shares WHERE share_id=?", (share_id,)).fetchone()
        if not row:
            return fail("分享不存在")
        content = json.loads(row["content"]) if row["content"] else {}
    finally:
        conn.close()
    return success(content)


# ============================================================
# 举报相关API
# ============================================================

@require_token
async def report_create(request):
    data = await request.json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO reports (user_id,target_id,target_type,reason,create_time) VALUES (?,?,?,?,?)",
            (request["user"]["id"], data.get("targetId", ""), data.get("targetType", 0), data.get("reason", ""), now_ts()),
        )
        conn.commit()
    finally:
        conn.close()
    return success()


# ============================================================
# 事件相关API
# ============================================================

@require_token
async def event_list(request):
    return success({"list": []})


@require_token
async def event_edit(request):
    return success()


# ============================================================
# 文件上传API
# ============================================================

async def upload_file(request):
    reader = await request.multipart()
    field = await reader.next()
    if not field:
        return fail("没有文件")

    filename = field.filename or gen_id()[:12]
    ext = os.path.splitext(filename)[1]
    save_name = gen_id()[:16] + ext
    save_path = UPLOAD_DIR / save_name

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with open(save_path, "wb") as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)

    file_url = f"https://127.0.0.1:{HTTPS_PORT}/static/uploads/{save_name}"
    return success({
        "url": file_url,
        "filename": filename,
        "size": os.path.getsize(save_path),
    })


# ============================================================
# Bot发送消息API (开放接口)
# ============================================================

async def open_api_bot_send(request):
    data = await request.json()
    bot_token = data.get("token", "")
    chat_id = data.get("chatId", "")
    content = data.get("content", "")
    content_type = data.get("contentType", 1)

    if not bot_token:
        return fail("token不能为空")

    conn = get_db()
    try:
        bot = conn.execute("SELECT * FROM bots WHERE token=?", (bot_token,)).fetchone()
        if not bot:
            return fail("机器人不存在")
        bot = dict(bot)

        msg_id = gen_id()
        ts = now_ts()
        seq = next_msg_seq()

        conn.execute(
            "INSERT INTO messages (msg_id,chat_id,chat_type,sender_id,content,content_type,timestamp,msg_seq) VALUES (?,?,?,?,?,?,?,?)",
            (msg_id, chat_id, 2, bot["id"], content, content_type, ts, seq),
        )
        conn.commit()
    finally:
        conn.close()

    msg_data = {
        "type": "push_message",
        "data": {
            "msgId": msg_id,
            "chatId": chat_id,
            "chatType": 2,
            "senderId": bot["id"],
            "senderNickname": bot["name"],
            "senderAvatarUrl": bot["avatar_url"],
            "content": content,
            "contentType": content_type,
            "timestamp": ts,
            "msgSeq": seq,
        }
    }
    await wss_manager.push_to_group(chat_id, msg_data)

    return success({"msgId": msg_id, "timestamp": ts, "msgSeq": seq})


# ============================================================
# 通用通配API
# ============================================================

async def generic_handler(request):
    return success()


async def generic_get_handler(request):
    return success()


# ============================================================
# Admin后台API
# ============================================================

async def admin_login(request):
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=? AND password=? AND is_admin=1", (username, password)).fetchone()
        if not row:
            return fail("用户名或密码错误")
        token = gen_token()
        conn.execute("UPDATE users SET token=? WHERE id=?", (token, username))
        conn.commit()
    finally:
        conn.close()
    return success({"token": token, "userId": username})


async def admin_check(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)
    return success({"userId": user["id"], "nickname": user["name"]})


async def admin_users(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY register_time DESC").fetchall()
        users = []
        for r in rows:
            users.append({
                "id": r["id"],
                "name": r["name"],
                "phone": r["phone"],
                "email": r["email"],
                "isVip": r["is_vip"],
                "isAdmin": r["is_admin"],
                "isBanned": r["is_banned"],
                "coin": r["coin"],
                "registerTime": r["register_time"],
            })
    finally:
        conn.close()
    return success({"list": users})


async def admin_set_vip(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)
    data = await request.json()
    uid = data.get("userId", "")
    is_vip = data.get("isVip", 0)
    expired = data.get("expiredTime", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_vip=?, vip_expired_time=? WHERE id=?", (is_vip, expired, uid))
        conn.commit()
    finally:
        conn.close()
    return success()


async def admin_set_admin(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)
    data = await request.json()
    uid = data.get("userId", "")
    is_admin = data.get("isAdmin", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_admin=? WHERE id=?", (is_admin, uid))
        conn.commit()
    finally:
        conn.close()
    return success()


async def admin_ban_user(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)
    data = await request.json()
    uid = data.get("userId", "")
    is_banned = data.get("isBanned", 1)
    ban_time = data.get("banTime", 0)
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_banned=?, ban_time=? WHERE id=?", (is_banned, ban_time, uid))
        conn.commit()
    finally:
        conn.close()
    return success()


async def admin_groups(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM groups ORDER BY create_time DESC").fetchall()
        groups = []
        for r in rows:
            groups.append({
                "id": r["id"],
                "name": r["name"],
                "ownerId": r["owner_id"],
                "headcount": r["headcount"],
                "category": r["category"],
                "isDissolved": r["is_dissolved"],
                "createTime": r["create_time"],
            })
    finally:
        conn.close()
    return success({"list": groups})


async def admin_dissolve_group(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)
    data = await request.json()
    gid = data.get("groupId", "")
    conn = get_db()
    try:
        conn.execute("UPDATE groups SET is_dissolved=1 WHERE id=?", (gid,))
        conn.commit()
    finally:
        conn.close()
    return success()


async def admin_messages(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT m.*, u.name as sender_name FROM messages m LEFT JOIN users u ON m.sender_id=u.id "
            "ORDER BY m.timestamp DESC LIMIT 200"
        ).fetchall()
        messages = []
        for r in rows:
            messages.append({
                "msgId": r["msg_id"],
                "chatId": r["chat_id"],
                "chatType": r["chat_type"],
                "senderId": r["sender_id"],
                "senderName": r["sender_name"] or "",
                "content": r["content"],
                "contentType": r["content_type"],
                "timestamp": r["timestamp"],
                "isDeleted": r["is_deleted"],
                "isRecalled": r["is_recalled"],
            })
    finally:
        conn.close()
    return success({"list": messages})


async def admin_bots(request):
    user = await get_user_by_token(request)
    if not user or not user.get("is_admin"):
        return fail("无权限", 403)

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM bots ORDER BY create_time DESC").fetchall()
        bots = []
        for r in rows:
            bots.append({
                "id": r["id"],
                "name": r["name"],
                "ownerId": r["owner_id"],
                "isActive": r["is_active"],
                "headcount": r["headcount"],
                "createTime": r["create_time"],
            })
    finally:
        conn.close()
    return success({"list": bots})


# ============================================================
# WSS处理
# ============================================================

async def wss_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    user_id = None
    token = request.query.get("token", "")

    if token:
        conn = get_db()
        try:
            row = conn.execute("SELECT id FROM users WHERE token=?", (token,)).fetchone()
            if row:
                user_id = row["id"]
        finally:
            conn.close()

    if user_id:
        wss_manager.add(user_id, ws)
        print(f"WSS: 用户 {user_id} 已连接")

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                cmd = data.get("type", data.get("cmd", ""))

                if cmd == "login":
                    login_token = data.get("token", "")
                    conn = get_db()
                    try:
                        row = conn.execute("SELECT id FROM users WHERE token=?", (login_token,)).fetchone()
                        if row:
                            user_id = row["id"]
                            wss_manager.add(user_id, ws)
                            await ws.send_str(json.dumps({"type": "login_resp", "code": 1, "msg": "success"}))
                            print(f"WSS: 用户 {user_id} 登录成功")
                        else:
                            await ws.send_str(json.dumps({"type": "login_resp", "code": -1, "msg": "token无效"}))
                    finally:
                        conn.close()

                elif cmd == "heartbeat":
                    await ws.send_str(json.dumps({"type": "heartbeat_resp", "code": 1, "timestamp": now_ts()}))

                elif cmd == "inputInfo":
                    # 输入状态通知
                    chat_id = data.get("chatId", "")
                    chat_type = data.get("chatType", 1)
                    if user_id and chat_id:
                        push_data = {
                            "type": "inputInfo",
                            "data": {
                                "userId": user_id,
                                "chatId": chat_id,
                                "chatType": chat_type,
                            }
                        }
                        if chat_type == 1:
                            await wss_manager.push_to_user(chat_id, push_data)
                        elif chat_type == 2:
                            await wss_manager.push_to_group(chat_id, push_data, exclude_user_id=user_id)

            elif msg.type == WSMsgType.ERROR:
                print(f"WSS错误: {ws.exception()}")
    finally:
        if user_id:
            wss_manager.remove(user_id, ws)
            print(f"WSS: 用户 {user_id} 已断开")

    return ws


# ============================================================
# 静态文件和Admin页面
# ============================================================

async def serve_admin(request):
    index_path = ADMIN_DIR / "index.html"
    if index_path.exists():
        return web.FileResponse(index_path)
    return web.Response(text="Admin page not found", status=404)


async def serve_static(request):
    file_path = STATIC_DIR / request.match_info.get("path", "")
    if file_path.exists() and file_path.is_file():
        return web.FileResponse(file_path)
    return web.Response(text="File not found", status=404)


# ============================================================
# 路由注册
# ============================================================

def create_app():
    app = web.Application()

    # 静态文件
    app.router.add_get("/static/{path:.*}", serve_static)

    # Admin页面
    app.router.add_get("/admin/", serve_admin)
    app.router.add_get("/admin/index.html", serve_admin)

    # Admin API
    app.router.add_post("/api/admin/login", admin_login)
    app.router.add_get("/api/admin/check", admin_check)
    app.router.add_get("/api/admin/users", admin_users)
    app.router.add_post("/api/admin/set-vip", admin_set_vip)
    app.router.add_post("/api/admin/set-admin", admin_set_admin)
    app.router.add_post("/api/admin/ban-user", admin_ban_user)
    app.router.add_get("/api/admin/groups", admin_groups)
    app.router.add_post("/api/admin/dissolve-group", admin_dissolve_group)
    app.router.add_get("/api/admin/messages", admin_messages)
    app.router.add_get("/api/admin/bots", admin_bots)

    # 用户相关
    app.router.add_post("/v1/user/captcha", user_captcha)
    app.router.add_post("/v1/user/verification-login", user_verification_login)
    app.router.add_post("/v1/user/email-login", user_email_login)
    app.router.add_get("/v1/user/info", user_info)
    app.router.add_post("/v1/user/get-user", user_get_user)
    app.router.add_post("/v1/user/edit-nickname", user_edit_nickname)
    app.router.add_post("/v1/user/edit-avatar", user_edit_avatar)
    app.router.add_post("/v1/user/logout", user_logout)
    app.router.add_post("/v1/user/recommend-category-list", user_recommend_category_list)
    app.router.add_post("/v1/user/recommend-list", user_recommend_list)
    app.router.add_post("/v1/user/recommend", user_recommend)
    app.router.add_post("/v1/user/module-ignore-info", user_module_ignore_info)
    app.router.add_post("/v1/user/module-ignore", user_module_ignore)
    app.router.add_post("/v1/user/notification-status", user_notification_status)
    app.router.add_post("/v1/user/notification-info", user_notification_info)
    app.router.add_post("/v1/user/gold-coin-increase-decrease-record", user_gold_coin_record)
    app.router.add_post("/v1/user/bing-phone", user_bind_phone)
    app.router.add_post("/v1/user/bing-email", user_bind_email)
    app.router.add_post("/v1/user/change-phone-check", user_change_phone_check)
    app.router.add_post("/v1/user/change-email-check", user_change_email_check)
    app.router.add_post("/v1/user/forget-password", user_forget_password)
    app.router.add_post("/v1/user/save-user-data", user_save_user_data)
    app.router.add_post("/v1/user/get-user-data", user_get_user_data)
    app.router.add_post("/v1/user/get-user-show-adv", user_get_user_show_adv)
    app.router.add_post("/v1/user/save-user-remarks", user_save_user_remarks)
    app.router.add_post("/v1/user/cancel-user", user_cancel_user)
    app.router.add_post("/v1/user/device-offline", user_device_offline)
    app.router.add_post("/v1/user/medal", user_medal)
    app.router.add_post("/v1/user/jverify-login", user_jverify_login)
    app.router.add_post("/v1/user/verification-register", user_verification_register)
    app.router.add_post("/v1/user/clients", user_clients)
    app.router.add_post("/v1/user/ad-code", user_ad_code)
    app.router.add_post("/v1/user/ban-appeal", user_ban_appeal)
    app.router.add_get("/v1/user/check-version", user_check_version)

    # 验证相关
    app.router.add_post("/v1/verification/get-verification-code", verification_get_code)
    app.router.add_post("/v1/verification/get-email-verification-code", verification_get_email_code)

    # 消息相关
    app.router.add_post("/v1/msg/send-message", msg_send_message)
    app.router.add_post("/v1/msg/edit-message", msg_edit_message)
    app.router.add_post("/v1/msg/list-message", msg_list_message)
    app.router.add_post("/v1/msg/list-message-by-seq", msg_list_message_by_seq)
    app.router.add_post("/v1/msg/list-message-by-mid-seq", msg_list_message_by_mid_seq)
    app.router.add_post("/v1/msg/recall-msg", msg_recall_msg)
    app.router.add_post("/v1/msg/recall-msg-batch", msg_recall_msg_batch)
    app.router.add_post("/v1/msg/delete", msg_delete)
    app.router.add_post("/v1/msg/clean", msg_clean)
    app.router.add_post("/v1/msg/pic-list-message-by-mid-seq", msg_pic_list_message_by_mid_seq)
    app.router.add_post("/v1/msg/a2ui-form-report", msg_a2ui_form_report)
    app.router.add_post("/v1/msg/button-report", msg_button_report)
    app.router.add_post("/v1/msg/file-download-record", msg_file_download_record)

    # 好友相关
    app.router.add_post("/v1/friend/apply", friend_apply)
    app.router.add_post("/v1/friend/delete-friend", friend_delete_friend)
    app.router.add_post("/v1/friend/agree-apply", friend_agree_apply)
    app.router.add_post("/v1/friend/ignore-apply", friend_ignore_apply)
    app.router.add_post("/v1/friend/address-book-list", friend_address_book_list)
    app.router.add_post("/v1/friend/request-list", friend_request_list)
    app.router.add_post("/v1/friend/no-notify", friend_no_notify)
    app.router.add_post("/v1/friend/delete-request", friend_delete_request)
    app.router.add_post("/v1/friend/set-black-list", friend_set_black_list)

    # 群组相关
    app.router.add_post("/v1/group/create-group", group_create_group)
    app.router.add_post("/v1/group/info", group_info)
    app.router.add_post("/v1/group/edit-group", group_edit_group)
    app.router.add_post("/v1/group/dismiss-group", group_dismiss_group)
    app.router.add_post("/v1/group/invite", group_invite)
    app.router.add_post("/v1/group/remove-member", group_remove_member)
    app.router.add_post("/v1/group/list-member", group_list_member)
    app.router.add_post("/v1/group/gag-member", group_gag_member)
    app.router.add_post("/v1/group/edit-my-group-nickname", group_edit_my_group_nickname)
    app.router.add_post("/v1/group/transfer-group", group_transfer_group)
    app.router.add_post("/v1/group/live-room", group_live_room)
    app.router.add_post("/v1/group/bot-list", group_bot_list)
    app.router.add_post("/v1/group/remove-bot", group_remove_bot)
    app.router.add_post("/v1/group/category", group_category)
    app.router.add_post("/v1/group/manage-setting", group_manage_setting)
    app.router.add_post("/v1/group/check-master-is-vip", group_check_master_is_vip)
    app.router.add_post("/v1/group/member-is-removed", group_member_is_removed)
    app.router.add_post("/v1/group/edit-auto-delete-message", group_edit_auto_delete_message)
    app.router.add_post("/v1/group/edit-stop-member-upload-group-file", group_edit_stop_member_upload_group_file)
    app.router.add_post("/v1/group/edit-group-keyword", group_edit_group_keyword)
    app.router.add_post("/v1/group/msg-type-limit", group_msg_type_limit)
    app.router.add_post("/v1/group/info-add-friend", group_info_add_friend)
    app.router.add_post("/v1/group/instruction-list", group_instruction_list)
    app.router.add_post("/v1/group/instruction-setting", group_instruction_setting)
    app.router.add_post("/v1/group/instruction-sort", group_instruction_sort)
    app.router.add_post("/v1/group/recommend/switch", group_recommend_switch)
    app.router.add_post("/v1/group/list-manage", group_list_manage)
    app.router.add_post("/v1/group/agree-invite", group_agree_invite)

    # 会话相关
    app.router.add_post("/v1/conversation/dismiss-notification", conversation_dismiss_notification)
    app.router.add_post("/v1/conversation/list", conversation_list)
    app.router.add_post("/v1/conversation/sort-change", conversation_sort_change)
    app.router.add_post("/v1/conversation/remove", conversation_remove)

    # 杂项
    app.router.add_get("/v1/misc/configure-distribution", misc_configure_distribution)
    app.router.add_get("/v1/misc/qiniu-token", misc_qiniu_token)
    app.router.add_get("/v1/misc/qiniu-token-audio", misc_qiniu_token_audio)
    app.router.add_get("/v1/misc/qiniu-token2", misc_qiniu_token2)
    app.router.add_get("/v1/misc/qiniu-token-video", misc_qiniu_token_video)
    app.router.add_get("/v1/misc/qiniu-token-group-disk", misc_qiniu_token_group_disk)
    app.router.add_get("/v1/misc/setting", misc_setting)
    app.router.add_get("/v1/misc/gray-status", misc_gray_status)
    app.router.add_get("/v1/misc/auto-update", misc_auto_update)

    # 检查
    app.router.add_post("/v1/check/check-version-mobile", check_version_mobile)
    app.router.add_post("/v1/check/get-latest-version", check_latest_version)
    app.router.add_post("/v1/check/check-version", check_version)

    # 机器人
    app.router.add_post("/v1/bot/new-list", bot_new_list)
    app.router.add_post("/v1/bot/banner", bot_banner)
    app.router.add_post("/v1/bot/bot-detail", bot_bot_detail)
    app.router.add_post("/v1/bot/bot-info", bot_bot_info)
    app.router.add_post("/v1/bot/create-bot", bot_create_bot)
    app.router.add_post("/v1/bot/edit-bot", bot_edit_bot)
    app.router.add_post("/v1/bot/stop-bot", bot_stop_bot)
    app.router.add_post("/v1/bot/reset-bot-token", bot_reset_bot_token)
    app.router.add_post("/v1/bot/console/my-bots", bot_console_my_bots)
    app.router.add_post("/v1/bot/follower-list", bot_follower_list)
    app.router.add_post("/v1/bot/remove-follower", bot_remove_follower)
    app.router.add_post("/v1/bot/add-friend-bot-info", bot_add_friend_bot_info)
    app.router.add_post("/v1/bot/board", bot_board)
    app.router.add_post("/v1/bot/group-permission-get", bot_group_permission_get)
    app.router.add_post("/v1/bot/group-permission-edit", bot_group_permission_edit)
    app.router.add_post("/v1/bot/join-group-list", bot_join_group_list)
    app.router.add_post("/v1/bot/remove-group", bot_remove_group)
    app.router.add_post("/v1/bot/edit-subscribed-link", bot_edit_subscribed_link)
    app.router.add_post("/v1/bot/bot-link-reset", bot_bot_link_reset)
    app.router.add_post("/v1/bot/edit-setting-json", bot_edit_setting_json)
    app.router.add_post("/v1/bot/send-setting-json", bot_send_setting_json)
    app.router.add_post("/v1/bot/get-user-settings-json", bot_get_user_settings_json)

    # 搜索
    app.router.add_post("/v1/search/home-search", search_home_search)
    app.router.add_post("/v1/search/chat-search", search_chat_search)

    # 表情包
    app.router.add_post("/v1/sticker/list", sticker_list)
    app.router.add_post("/v1/sticker/add", sticker_add)
    app.router.add_post("/v1/sticker/detail", sticker_detail)
    app.router.add_post("/v1/sticker/remove-sticker-pack", sticker_remove_sticker_pack)
    app.router.add_post("/v1/sticker/sort", sticker_sort)

    # 表情
    app.router.add_post("/v1/expression/add", expression_add)
    app.router.add_post("/v1/expression/create", expression_create)
    app.router.add_post("/v1/expression/delete", expression_delete)
    app.router.add_post("/v1/expression/list", expression_list)
    app.router.add_post("/v1/expression/topping", expression_topping)

    # 置顶
    app.router.add_post("/v1/sticky/list", sticky_list)
    app.router.add_post("/v1/sticky/topping", sticky_topping)
    app.router.add_post("/v1/sticky/delete", sticky_delete)

    # 分享
    app.router.add_post("/v1/share/create", share_create)
    app.router.add_post("/v1/share/info", share_info)

    # 举报
    app.router.add_post("/v1/report/create", report_create)

    # 事件
    app.router.add_post("/v1/event/list", event_list)
    app.router.add_post("/v1/event/edit", event_edit)

    # 文件上传
    app.router.add_post("/v1/upload", upload_file)

    # Bot开放API
    app.router.add_get("/open-apis/v1/bot/send", open_api_bot_send)
    app.router.add_post("/open-apis/v1/bot/send", open_api_bot_send)

    # 通配路由 - 处理所有未匹配的API
    app.router.add_post("/v1/bot/llm/{path:.*}", generic_handler)
    app.router.add_post("/v1/live/{path:.*}", generic_handler)
    app.router.add_post("/v1/file/{path:.*}", generic_handler)
    app.router.add_post("/v1/group-tag/{path:.*}", generic_handler)
    app.router.add_post("/v1/instruction/{path:.*}", generic_handler)
    app.router.add_post("/v1/menu/{path:.*}", generic_handler)
    app.router.add_post("/v1/disk/{path:.*}", generic_handler)
    app.router.add_post("/v1/coin/{path:.*}", generic_handler)
    app.router.add_post("/v1/community/{path:.*}", generic_handler)
    app.router.add_post("/v1/chat-background/{path:.*}", generic_handler)
    app.router.add_post("/v1/vip/{path:.*}", generic_handler)
    app.router.add_post("/v1/mount-setting/{path:.*}", generic_handler)
    app.router.add_post("/v1/beta/{path:.*}", generic_handler)

    # 最后的通配 - 兜底
    app.router.add_post("/{path:.*}", generic_handler)
    app.router.add_get("/{path:.*}", generic_get_handler)

    return app


def create_wss_app():
    app = web.Application()
    app.router.add_get("/ws", wss_handler)
    return app


# ============================================================
# 启动服务器
# ============================================================

async def start_servers():
    init_db()

    cert_file = CERT_DIR / "cert.pem"
    key_file = CERT_DIR / "key.pem"

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(str(cert_file), str(key_file))

    # HTTPS服务器
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTPS_PORT, ssl_context=ssl_context)
    await site.start()
    print(f"HTTPS服务器已启动: https://127.0.0.1:{HTTPS_PORT}")

    # WSS服务器
    wss_app = create_wss_app()
    wss_runner = web.AppRunner(wss_app)
    await wss_runner.setup()
    wss_site = web.TCPSite(wss_runner, "0.0.0.0", WSS_PORT, ssl_context=ssl_context)
    await wss_site.start()
    print(f"WSS服务器已启动: wss://127.0.0.1:{WSS_PORT}/ws")

    print(f"Admin后台: https://127.0.0.1:{HTTPS_PORT}/admin/")
    print(f"默认管理员: admin / admin123")

    # 永久等待
    while True:
        await asyncio.sleep(3600)


def main():
    # 检查证书
    cert_file = CERT_DIR / "cert.pem"
    key_file = CERT_DIR / "key.pem"
    if not cert_file.exists() or not key_file.exists():
        print("SSL证书不存在，正在生成...")
        import subprocess
        subprocess.run([sys.executable, str(BASE_DIR / "gen_cert.py")], check=True)

    asyncio.run(start_servers())


if __name__ == "__main__":
    main()
