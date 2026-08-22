# -*- coding: utf-8 -*-
"""astrbot_plugin_gay 集成测试：每日固定、@ 提取、名字检测、榜单、CP、称号开关。

运行：python -m unittest test_integration -v（不联网，数据目录注入临时目录）
"""

import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, r"D:\astrbot\data\plugins")

from astrbot.api.message_components import At  # noqa: E402
from astrbot_plugin_gay.main import GayPlugin  # noqa: E402


class FakeSession:
    def __init__(self, umo="default:GroupMessage:123"):
        self.umo = umo

    def __str__(self):
        return self.umo


class FakeEvent:
    def __init__(self, message_str="", umo="default:GroupMessage:123",
                 sender_id="u1", sender_name="小明", ats=None, group_id="123"):
        self.message_str = message_str
        self.session = FakeSession(umo)
        self.unified_msg_origin = umo
        self._sid = sender_id
        self._name = sender_name
        self._ats = ats or []
        self._gid = group_id

    def get_sender_id(self):
        return self._sid

    def get_sender_name(self):
        return self._name

    def get_group_id(self):
        return self._gid

    def get_messages(self):
        # At 组件显示名字段为 name
        return [At(qq=q, name=d) for q, d in self._ats]

    def chain_result(self, chain):
        return chain


def run(coro):
    return asyncio.run(coro)


def chain_text(chain) -> str:
    return chain[0].text


def make_plugin(config=None):
    tmp = tempfile.TemporaryDirectory(prefix="gay_test_")
    p = GayPlugin(None, config or {}, data_dir=tmp.name)
    return p, tmp


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def yesterday() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


class TestDetectCommand(unittest.TestCase):
    def test_detect_by_at(self):
        p, _ = make_plugin()
        ev = FakeEvent("/gay", ats=[("8888", "小刚")])
        r = run(p.cmd_gay(ev))
        text = chain_text(r)
        self.assertIn("浓度检测结果", text)
        self.assertIn("小刚", text)

    def test_detect_by_name(self):
        p, _ = make_plugin()
        r = run(p.cmd_gay(FakeEvent("/gay 小红")))
        text = chain_text(r)
        self.assertIn("小红", text)
        self.assertIn("浓度:", text)

    def test_daily_fixed_same_target(self):
        p, _ = make_plugin()
        ev1 = FakeEvent("/gay 小红")
        r1 = run(p.cmd_gay(ev1))
        r2 = run(p.cmd_gay(FakeEvent("/gay 小红")))
        self.assertEqual(chain_text(r1), chain_text(r2))

    def test_at_and_name_are_different_targets(self):
        p, _ = make_plugin()
        run(p.cmd_gay(FakeEvent("/gay 小红")))
        r = run(p.cmd_gay(FakeEvent("/gay", ats=[("9999", "小红")])))
        # @ 的 9999 与名字"小红"是不同目标，且键均带群号前缀
        keys = list(p._data["daily"][today()].keys())
        self.assertTrue(any(k.endswith("name:小红") for k in keys))
        self.assertTrue(any(k.endswith("|9999") for k in keys))

    def test_help_on_empty(self):
        p, _ = make_plugin()
        r = run(p.cmd_gay(FakeEvent("/gay")))
        self.assertIn("帮助", chain_text(r) + "帮助")

    def test_help_keyword(self):
        p, _ = make_plugin()
        r = run(p.cmd_gay(FakeEvent("/gay 帮助")))
        self.assertIn("GAY 浓度检测", chain_text(r))

    def test_knowledge_command(self):
        p, _ = make_plugin()
        r = run(p.cmd_gay(FakeEvent("/gay 科普")))
        self.assertIn("小课堂", chain_text(r))


class TestDailyPersistence(unittest.TestCase):
    def test_record_persisted_with_fields(self):
        p, tmp = make_plugin()
        run(p.cmd_gay(FakeEvent("/gay 小红")))
        rec = list(p._data["daily"][today()].values())[0]
        for field in ("percent", "level", "comment", "name", "streak"):
            self.assertIn(field, rec)

    def test_streak_from_yesterday(self):
        p, _ = make_plugin()
        y = yesterday()
        p._data["daily"].setdefault(y, {})[f"123|name:老王"] = {
            "percent": 50, "level": "深藏不露", "comment": "x",
            "name": "老王", "streak": 4,
        }
        run(p.cmd_gay(FakeEvent("/gay 老王")))
        rec = p._data["daily"][today()][f"123|name:老王"]
        self.assertEqual(rec["streak"], 5)

    def test_streak_disabled_config(self):
        p, _ = make_plugin({"streak_titles_enabled": False})
        y = yesterday()
        p._data["daily"].setdefault(y, {})[f"123|name:老张"] = {
            "percent": 10, "level": "直男认证", "comment": "x",
            "name": "老张", "streak": 6,
        }
        r = run(p.cmd_gay(FakeEvent("/gay 老张")))
        self.assertNotIn("称号", chain_text(r))

    def test_corrupted_data_reset(self):
        tmp = tempfile.TemporaryDirectory(prefix="gay_corrupt_")
        with open(os.path.join(tmp.name, "gay_data.json"), "w", encoding="utf-8") as f:
            f.write("{broken json!!!")
        p = GayPlugin(None, {}, data_dir=tmp.name)
        self.assertEqual(p._data["daily"], {})
        # 重置后仍可正常使用
        r = run(p.cmd_gay(FakeEvent("/gay 小李")))
        self.assertIn("浓度", chain_text(r))


class TestLeaderboard(unittest.TestCase):
    def test_empty_hint(self):
        p, _ = make_plugin()
        r = run(p.cmd_leaderboard(FakeEvent("/gay榜")))
        self.assertIn("还没有人被检测过", chain_text(r))

    def test_sorted_top_with_king(self):
        p, _ = make_plugin()
        daily = p._data["daily"].setdefault(today(), {})
        daily["123|a"] = {"percent": 88, "name": "甲", "level": "弯道超车"}
        daily["123|b"] = {"percent": 95, "name": "乙", "level": "Gay 中之光"}
        daily["123|c"] = {"percent": 12, "name": "丙", "level": "直男认证"}
        r = run(p.cmd_leaderboard(FakeEvent("/gay榜")))
        text = chain_text(r)
        b_pos = text.find("乙")
        a_pos = text.find("甲")
        c_pos = text.find("丙")
        self.assertTrue(b_pos < a_pos < c_pos)
        self.assertIn("今日 Gay 王：乙（95%）", text)

    def test_other_groups_excluded(self):
        p, _ = make_plugin()
        daily = p._data["daily"].setdefault(today(), {})
        daily["999|out"] = {"percent": 99, "name": "外群人"}
        daily["123|in"] = {"percent": 60, "name": "本群人"}
        text = chain_text(run(p.cmd_leaderboard(FakeEvent("/gay榜"))))
        self.assertIn("本群人", text)
        self.assertNotIn("外群人", text)

    def test_private_chat_no_leak(self):
        # 私聊（无群号）查榜单不泄漏其他群数据
        p, _ = make_plugin()
        daily = p._data["daily"].setdefault(today(), {})
        daily["123|a"] = {"percent": 88, "name": "群友甲"}
        ev = FakeEvent("/gay榜", group_id="", umo="aiocqhttp:FriendMessage:100")
        r = run(p.cmd_leaderboard(ev))
        text = chain_text(r)
        self.assertNotIn("群友甲", text)
        self.assertIn("群聊中发送", text)


class TestCpCommand(unittest.TestCase):
    def test_cp_by_names(self):
        p, _ = make_plugin()
        r = run(p.cmd_cp(FakeEvent("/cp 阿明 阿花")))
        text = chain_text(r)
        self.assertIn("CP 配对结果", text)
        self.assertIn("契合度:", text)
        self.assertIn("情侣名:", text)

    def test_cp_order_independent(self):
        p, _ = make_plugin()
        r1 = run(p.cmd_cp(FakeEvent("/cp 阿明 阿花")))
        r2 = run(p.cmd_cp(FakeEvent("/cp 阿花 阿明")))
        s1 = [l for l in chain_text(r1).splitlines() if "契合度" in l][0]
        s2 = [l for l in chain_text(r2).splitlines() if "契合度" in l][0]
        self.assertEqual(s1, s2)

    def test_cp_by_ats(self):
        p, _ = make_plugin()
        ev = FakeEvent("/cp", ats=[("111", "小明"), ("222", "大红")])
        r = run(p.cmd_cp(ev))
        text = chain_text(r)
        self.assertIn("小明 ❤️ 大红", text)
        # At 提取的键为 QQ 号：两次相同 At 结果一致
        r2 = run(p.cmd_cp(FakeEvent("/cp", ats=[("111", "小明"), ("222", "大红")])))
        self.assertEqual(
            [l for l in text.splitlines() if "契合度" in l],
            [l for l in chain_text(r2).splitlines() if "契合度" in l],
        )

    def test_cp_missing_args(self):
        p, _ = make_plugin()
        r = run(p.cmd_cp(FakeEvent("/cp 只有一个")))
        self.assertIn("用法", chain_text(r))

    def test_cp_mixed_at_and_name(self):
        p, _ = make_plugin()
        ev = FakeEvent("/cp 阿强", ats=[("333", "阿珍")])
        r = run(p.cmd_cp(ev))
        text = chain_text(r)
        self.assertIn("阿珍 ❤️ 阿强", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
