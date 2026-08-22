# -*- coding: utf-8 -*-
"""AstrBot GAY 浓度检测插件：娱乐向群聊整活

功能：
- /gay @对方 | /gay 名字：检测同性恋浓度（每人每日一次固定，跨天重抽）
- /gay榜：本群今日浓度排行 Top10（Gay 王榜）
- /cp @A @B | /cp A B：CP 配对（契合度 + 情侣名，当日稳定且与顺序无关）
- /gay 科普：随机一条友善科普
- 连续多日检测获得称号（可关）

说明：本插件为善意玩笑向娱乐内容，评语保持轻松幽默；
科普内容倡导尊重与平等，不针对任何群体。
"""

import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta

from astrbot.api import AstrBotConfig, logger
from astrbot.api.all import MessageEventResult
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register

PLUGIN_NAME = "astrbot_plugin_gay"
PLUGIN_AUTHOR = "云晓"
PLUGIN_DESC = "GAY 浓度检测：浓度检测/Gay王榜/CP配对/科普（娱乐向）"
PLUGIN_VERSION = "1.0.0"

# ==================== 内容库 ====================

# 浓度等级：（分数下限, 等级名, 评语列表）；按分数从高到低匹配
GAY_LEVELS = [
    (100, "天选 Gay 王", [
        "万中无一的绝世天资，全群的骄傲！",
        "浓度爆表！这不是检测，是认证仪式。",
        "传说中的人物竟然就在本群！",
    ]),
    (90, "Gay 中之光", [
        "这浓度已经不需要隐藏了，闪闪发光。",
        "彩虹在你头顶盘旋，光芒万丈。",
        "建议直接出道，浓度即实力。",
    ]),
    (70, "弯道超车", [
        "老司机都追不上你的弯道。",
        "方向盘已经焊死在弯道上了。",
        "这条路你走得又稳又快。",
    ]),
    (50, "深藏不露", [
        "表面风平浪静，内心波澜壮阔。",
        "一半海水一半火焰，谜一样的存在。",
        "平时不显山不露水，一测吓一跳。",
    ]),
    (30, "略有潜力", [
        "潜力股，值得长期观察。",
        "万事皆有可能，未来可期。",
        "种子选手，好好培养。",
    ]),
    (10, "直男认证", [
        "浓度合格，直男证书已邮寄到家。",
        "稳得很，兄弟情谊纯度 99%。",
        "放心，你就是普通兄弟。",
    ]),
    (0, "钢铁直男", [
        "浓度低到仪器差点报错，钢铁认证！",
        "直得能当标尺用，佩服佩服。",
        "检测建议：本机已无检测必要。",
    ]),
]

# 连续检测称号：（天数下限, 称号）；从高到低匹配
STREAK_TITLES = [
    (30, "月度钉子户"),
    (21, "三周老司机"),
    (14, "半月老弯"),
    (7, "七连铁 GAY"),
    (3, "入门弯友"),
]

# 科普条目（友善尊重向）
KNOWLEDGE = [
    "性取向不是选择题，而是每个人与生俱来的一部分。世界因多元而精彩。",
    "「Gay」一词原意为快乐，如今也指男同性恋者。无论何种含义，快乐都是好东西。",
    "1990 年 5 月 17 日，世界卫生组织将同性恋从疾病名单中除名。5.17 是国际不再恐同日。",
    "彩虹旗的六种颜色分别代表生命、治愈、阳光、自然、和谐与精神。",
    "研究表明，性取向由先天与环境共同塑造，无法被「矫正」，也不需要被矫正。",
    "对不同性取向的尊重，是一个人教养的基本体现。玩笑归玩笑，尊重要到位。",
    "爱情无关性别，重要的是真诚与陪伴。",
    "许多国家和地区早已承认同性婚姻。爱与承诺是普世价值。",
    "如果身边有朋友向你出柜，请记住：TA 信任你才告诉你，这份信任值得珍惜。",
    "歧视和嘲笑不会让任何人变得更好，善良才会。",
    "每个人的存在都值得被平等对待，这与性取向、性别认同无关。",
]

# 帮助文本
HELP_TEXT = (
    "🏳️‍🌈 GAY 浓度检测 v1.0.0\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔍 /gay @对方 | /gay 名字   检测 TA 的浓度\n"
    "🏆 /gay榜                  本群今日 Gay 王榜 Top10\n"
    "💕 /cp @A @B | /cp A B     CP 配对（契合度+情侣名）\n"
    "📚 /gay 科普               随机一条友善小知识\n"
    "❓ /gay 帮助               显示本帮助\n"
    "ℹ️ 每人每日结果固定，次日自动重抽；纯属娱乐，请勿当真"
)

# 指令参数解析正则
_GAY_RE = re.compile(r"^[\\/／]?\s*gay\s*(.*)$", re.IGNORECASE | re.S)
_CP_RE = re.compile(r"^[\\/／]?\s*cp\s+(.*)$", re.IGNORECASE | re.S)


@register(PLUGIN_NAME, PLUGIN_AUTHOR, PLUGIN_DESC, PLUGIN_VERSION)
class GayPlugin(Star):
    """GAY 浓度检测：每人每日一次固定，含 Gay 王榜 / CP 配对 / 连续称号 / 科普"""

    def __init__(self, context: Context, config: AstrBotConfig = None, data_dir: str = None):
        super().__init__(context)
        self.config = config or {}
        # 数据目录（默认 plugin_data/<插件名>，测试可注入临时目录）
        if data_dir:
            self.data_dir = data_dir
        else:
            self.data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "plugin_data",
                PLUGIN_NAME,
            )
        os.makedirs(self.data_dir, exist_ok=True)
        self._data = {"daily": {}}
        self._load()
        logger.info(f"【{PLUGIN_NAME}】插件初始化完成，数据目录: {self.data_dir}")

    # ==================== 配置安全取值 ====================

    def _int_cfg(self, key: str, default: int) -> int:
        """安全读取整数配置：脏值回退默认值"""
        v = self.config.get(key, default)
        try:
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def _bool_cfg(self, key: str, default: bool) -> bool:
        """安全读取布尔配置：脏值回退默认值"""
        v = self.config.get(key, default)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            low = v.strip().lower()
            if low in ("1", "true", "yes", "on", "是"):
                return True
            if low in ("0", "false", "no", "off", "否", ""):
                return False
            return default
        if isinstance(v, (int, float)):
            return bool(v)
        return default

    # ==================== 纯函数工具 ====================

    @staticmethod
    def hash_percent(key: str) -> int:
        """按 key 哈希生成 0~100 的浓度值（同 key 同结果）"""
        digest = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)
        return digest % 101

    @classmethod
    def level_for(cls, percent: int) -> tuple[str, list[str]]:
        """按分数定位等级：(等级名, 评语列表)"""
        for min_score, name, comments in GAY_LEVELS:
            if percent >= min_score:
                return name, comments
        return GAY_LEVELS[-1][1], GAY_LEVELS[-1][2]

    @staticmethod
    def streak_title(streak: int) -> str:
        """连续天数对应称号；不足 3 天返回空串"""
        for days, title in STREAK_TITLES:
            if streak >= days:
                return title
        return ""

    @staticmethod
    def couple_name(a: str, b: str) -> str:
        """生成情侣名：双方各取前半段拼接"""
        a = (a or "TA").strip()[:12] or "TA"
        b = (b or "TA").strip()[:12] or "TA"
        head_a = a[: max(1, len(a) // 2)]
        head_b = b[: max(1, len(b) // 2)]
        return f"{head_a}{head_b}"

    @staticmethod
    def cp_score(a: str, b: str, date: str) -> int:
        """CP 契合度（40~100）：按双方标识 + 日期哈希，顺序无关"""
        pair = sorted([str(a or "A"), str(b or "B")])
        digest = int(hashlib.md5(f"{date}|{pair[0]}|{pair[1]}".encode("utf-8")).hexdigest(), 16)
        return 40 + digest % 61

    @classmethod
    def cp_level(cls, score: int) -> str:
        """契合度等级文案"""
        if score >= 95:
            return "天作之合"
        if score >= 85:
            return "甜到发齁"
        if score >= 70:
            return "配一脸"
        if score >= 55:
            return "有点东西"
        return "塑料兄弟情"

    # ==================== 数据持久化 ====================

    def _data_path(self) -> str:
        return os.path.join(self.data_dir, "gay_data.json")

    def _load(self):
        """从磁盘加载数据（结构校验，损坏时重置）"""
        try:
            path = self._data_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("daily"), dict):
                    self._data = data
                else:
                    logger.warning("【%s】持久化数据格式异常，已重置", PLUGIN_NAME)
        except Exception as e:
            logger.warning(f"【{PLUGIN_NAME}】加载数据失败: {e}")

    def _save(self):
        """保存数据到磁盘（清理过期记录）"""
        try:
            keep_days = max(1, self._int_cfg("keep_days", 7))
            cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
            self._data["daily"] = {
                d: v for d, v in self._data["daily"].items() if d >= cutoff
            }
            tmp = self._data_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._data_path())
        except Exception as e:
            logger.warning(f"【{PLUGIN_NAME}】保存数据失败: {e}")

    # ==================== 会话与目标解析 ====================

    def _session_key(self, event: AstrMessageEvent) -> str:
        """会话唯一标识（优先 unified_msg_origin，回退 session）"""
        umo = getattr(event, "unified_msg_origin", None)
        if umo:
            return str(umo)
        return str(getattr(event, "session", "default"))

    @staticmethod
    def _sender_name(event: AstrMessageEvent) -> str:
        """发送者昵称（失败返回空串）"""
        try:
            return str(event.get_sender_name() or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _extract_at(event: AstrMessageEvent) -> tuple[str, str]:
        """提取消息中被 @ 者的 (QQ号, 显示名)；无则返回空元组。

        AstrBot At 组件的显示名字段为 name。
        """
        try:
            from astrbot.api.message_components import At
            for comp in event.get_messages() or []:
                if isinstance(comp, At):
                    qq = str(getattr(comp, "qq", "") or "").strip()
                    if not qq or qq == "all":
                        continue
                    display = str(
                        getattr(comp, "name", "")
                        or getattr(comp, "display_name", "")
                        or ""
                    ).strip()
                    return qq, display
        except Exception:
            pass
        return "", ""

    def _group_id(self, event: AstrMessageEvent) -> str:
        """群号（失败返回空串）"""
        try:
            return str(event.get_group_id() or "").strip()
        except Exception:
            return ""

    def resolve_target(self, event: AstrMessageEvent, args: str) -> tuple[str, str]:
        """解析检测目标：(唯一键, 显示名)。@ 优先，其次名字文本。

        键带群号前缀避免跨群串数据：@ 者为 {群}|{QQ}；名字者为 {群}|name:{文本}。
        """
        gid = self._group_id(event)
        at_qq, at_name = self._extract_at(event)
        if at_qq:
            key = f"{gid}|{at_qq}" if gid else at_qq
            return key, (at_name or f"用户{at_qq[-4:]}")
        text = args.strip()
        if text:
            key = f"{gid}|name:{text}" if gid else f"name:{text}"
            return key, text
        return "", ""

    # ==================== 核心检测逻辑 ====================

    def _get_result(self, event: AstrMessageEvent, target_key: str, target_name: str,
                    is_self_check: bool = False) -> dict:
        """获取（或生成并持久化）目标的今日检测结果。

        streak 以被检测目标的记录为准连续推算。
        """
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self._data["daily"].setdefault(today, {})
        existing = daily.get(target_key)
        if existing:
            return existing
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        prev = self._data["daily"].get(yesterday, {}).get(target_key)
        try:
            streak = int(prev.get("streak", 0)) + 1 if prev else 1
        except (AttributeError, TypeError, ValueError):
            streak = 1
        # 连续称号开关关闭时不累计天数
        if not self._bool_cfg("streak_titles_enabled", True):
            streak = 1
        percent = self.hash_percent(f"{today}|{target_key}")
        level, comments = self.level_for(percent)
        rnd = random.Random(f"{today}|{target_key}")
        record = {
            "percent": percent,
            "level": level,
            "comment": rnd.choice(comments),
            "name": target_name[:20],
            "streak": streak,
            "self": bool(is_self_check),
        }
        max_records = max(1, self._int_cfg("max_daily_records", 1000))
        if len(daily) >= max_records:
            del daily[next(iter(daily))]
        daily[target_key] = record
        self._save()
        return record

    @classmethod
    def format_detect(cls, record: dict) -> str:
        """格式化单次检测结果"""
        hearts = "🌈" * max(1, round(record["percent"] / 20))
        lines = [
            "🏳️‍🌈 GAY 浓度检测结果",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"🎯 目标: {record['name']}",
            f"{hearts}",
            f"📊 浓度: {record['percent']}% · {record['level']}",
            f"💬 {record['comment']}",
        ]
        title = cls.streak_title(int(record.get("streak", 1)))
        if title:
            lines.append(f"🔥 连续检测 {record['streak']} 天，获得称号「{title}」")
        lines.append("ℹ️ 今日结果已固定，明天再来重抽～")
        return "\n".join(lines)

    # ==================== 排行榜 ====================

    def leaderboard_text(self, event: AstrMessageEvent) -> str:
        """渲染本群今日 Gay 王榜 Top10；私聊（无群号）提示到群内使用"""
        today = datetime.now().strftime("%Y-%m-%d")
        gid = self._group_id(event)
        if not gid:
            return (
                "🏆 今日 Gay 王榜\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ 榜单按群独立统计，请在群聊中发送 /gay榜 查看"
            )
        prefix = f"{gid}|"
        rows = []
        for k, rec in self._data["daily"].get(today, {}).items():
            if prefix and not k.startswith(prefix):
                continue
            try:
                percent = int(rec.get("percent", 0))
            except (TypeError, ValueError):
                continue
            rows.append((percent, str(rec.get("name") or k), str(rec.get("level", ""))))
        if not rows:
            return (
                "🏆 今日 Gay 王榜\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📭 今天还没有人被检测过\n发送 /gay @某人 抢占榜首！"
            )
        rows.sort(key=lambda r: -r[0])
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"🏆 今日 Gay 王榜 · {today}（共 {len(rows)} 人上榜）",
                 "━━━━━━━━━━━━━━━━━━━━━━"]
        for i, (percent, name, level) in enumerate(rows[:10]):
            icon = medals[i] if i < 3 else f"{i + 1}."
            display = name if len(name) <= 12 else name[:11] + "…"
            lines.append(f"{icon} {display} · {percent}% · {level}")
        king = rows[0]
        lines.append(f"👑 今日 Gay 王：{king[1]}（{king[0]}%）")
        return "\n".join(lines)

    # ==================== 指令处理 ====================

    @filter.command("gay", priority=200)
    async def cmd_gay(self, event: AstrMessageEvent) -> MessageEventResult:
        """/gay [@对方|名字] 浓度检测；/gay 科普；/gay 帮助"""
        try:
            raw = str(getattr(event, "message_str", "") or "").strip()
            m = _GAY_RE.match(raw)
            args = (m.group(1) or "").strip() if m else ""
            if args in ("帮助", "help"):
                return self._send_text(event, HELP_TEXT)
            if args == "科普":
                line = random.choice(KNOWLEDGE)
                return self._send_text(
                    event,
                    f"📚 GAY 小课堂\n━━━━━━━━━━━━━━━━━━━━━━\n💡 {line}",
                )

            # 目标解析：@ 优先（/gay @某人 时 message_str 可能只有 /gay），
            # 其次名字文本；都没有时默认检测自己
            target_key, target_name = self.resolve_target(event, args)
            if not target_key:
                try:
                    uid = str(event.get_sender_id() or "").strip()
                except Exception:
                    uid = ""
                if uid:
                    target_key = uid
                    target_name = self._sender_name(event) or f"用户{uid[-4:]}"
                else:
                    return self._send_text(event, "❌ 用法: /gay @对方 或 /gay 名字")
            record = self._get_result(event, target_key, target_name)
            return self._send_text(event, self.format_detect(record))
        except Exception as e:
            logger.error(f"【{PLUGIN_NAME}】浓度检测失败: {e}")
            return self._send_text(event, f"❌ 检测失败: {str(e)}")

    @filter.command("gay榜", alias={"gay王榜"}, priority=200)
    async def cmd_leaderboard(self, event: AstrMessageEvent) -> MessageEventResult:
        """本群今日 Gay 王榜 Top10"""
        try:
            return self._send_text(event, self.leaderboard_text(event))
        except Exception as e:
            logger.error(f"【{PLUGIN_NAME}】榜单查询失败: {e}")
            return self._send_text(event, f"❌ 榜单生成失败: {str(e)}")

    @filter.command("cp", priority=200)
    async def cmd_cp(self, event: AstrMessageEvent) -> MessageEventResult:
        """/cp @A @B 或 /cp A B：CP 配对（契合度 + 情侣名，当日稳定）"""
        try:
            raw = str(getattr(event, "message_str", "") or "").strip()
            m = _CP_RE.match(raw)
            rest = (m.group(1) or "").strip() if m else ""
            names: list[tuple[str, str]] = []  # [(键, 名)]

            # 依次提取消息中的所有 @（最多取两个）；显示名字段为 At.name
            try:
                from astrbot.api.message_components import At
                for comp in event.get_messages() or []:
                    if isinstance(comp, At):
                        qq = str(getattr(comp, "qq", "") or "").strip()
                        if not qq or qq == "all":
                            continue
                        display = str(
                            getattr(comp, "name", "")
                            or getattr(comp, "display_name", "")
                            or ""
                        ).strip()
                        names.append((qq, display or f"用户{qq[-4:]}"))
                        if len(names) >= 2:
                            break
            except Exception:
                pass

            # 不足两个则从文本参数补齐
            if len(names) < 2 and rest:
                parts = [x.strip() for x in re.split(r"[\s,，&＋+]+", rest) if x.strip()]
                for part in parts:
                    if len(names) >= 2:
                        break
                    names.append((f"name:{part}", part))

            if len(names) < 2:
                return self._send_text(event, "❌ 用法: /cp @A @B 或 /cp A B\n例如: /cp 小明 小红")

            today = datetime.now().strftime("%Y-%m-%d")
            score = self.cp_score(names[0][0], names[1][0], today)
            couple = self.couple_name(names[0][1], names[1][1])
            level = self.cp_level(score)
            hearts = "💗" * max(1, round(score / 20))
            return self._send_text(event, "\n".join([
                "💕 CP 配对结果",
                "━━━━━━━━━━━━━━━━━━━━━━",
                f"👫 {names[0][1]} ❤️ {names[1][1]}",
                f"{hearts}",
                f"💞 契合度: {score}% · {level}",
                f"🏷️ 情侣名: {couple}",
                "ℹ️ 当日结果固定，明日重新牵线",
            ]))
        except Exception as e:
            logger.error(f"【{PLUGIN_NAME}】CP 配对失败: {e}")
            return self._send_text(event, f"❌ 配对失败: {str(e)}")

    # ==================== 工具方法 ====================

    @staticmethod
    def _send_text(event, text: str) -> MessageEventResult:
        """构造纯文本回复结果"""
        return event.chain_result([Plain(text)])

    async def terminate(self):
        """插件卸载时保存数据"""
        try:
            self._save()
        except Exception:
            pass
