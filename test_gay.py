# -*- coding: utf-8 -*-
"""astrbot_plugin_gay 纯函数单元测试（不依赖 AstrBot 运行时）。"""

import sys
import unittest

sys.path.insert(0, r"D:\astrbot\data\plugins")

from astrbot_plugin_gay.main import (  # noqa: E402
    GAY_LEVELS,
    KNOWLEDGE,
    STREAK_TITLES,
    GayPlugin,
)


class TestHashPercent(unittest.TestCase):
    def test_range(self):
        for i in range(200):
            v = GayPlugin.hash_percent(f"2026-08-22|key{i}")
            self.assertTrue(0 <= v <= 100, f"v={v}")

    def test_deterministic(self):
        self.assertEqual(
            GayPlugin.hash_percent("abc"),
            GayPlugin.hash_percent("abc"),
        )

    def test_different_keys_differ(self):
        values = {GayPlugin.hash_percent(f"k{i}") for i in range(50)}
        self.assertGreater(len(values), 10)

    def test_full_coverage_low_and_high(self):
        # 大样本下应能覆盖低分段与高分段
        lows = any(GayPlugin.hash_percent(f"x{i}") < 20 for i in range(500))
        highs = any(GayPlugin.hash_percent(f"y{i}") > 80 for i in range(500))
        self.assertTrue(lows and highs)


class TestLevels(unittest.TestCase):
    def test_all_scores_have_level(self):
        for score in range(0, 101):
            name, comments = GayPlugin.level_for(score)
            self.assertTrue(name)
            self.assertTrue(comments)

    def test_boundaries(self):
        self.assertEqual(GayPlugin.level_for(0)[0], "钢铁直男")
        self.assertEqual(GayPlugin.level_for(100)[0], "天选 Gay 王")
        self.assertEqual(GayPlugin.level_for(90)[0], "Gay 中之光")
        self.assertEqual(GayPlugin.level_for(89)[0], "弯道超车")

    def test_levels_sorted_desc(self):
        mins = [m for m, _, _ in GAY_LEVELS]
        self.assertEqual(mins, sorted(mins, reverse=True))


class TestStreakTitles(unittest.TestCase):
    def test_below_3_no_title(self):
        self.assertEqual(GayPlugin.streak_title(1), "")
        self.assertEqual(GayPlugin.streak_title(2), "")

    def test_titles(self):
        self.assertEqual(GayPlugin.streak_title(3), "入门弯友")
        self.assertEqual(GayPlugin.streak_title(7), "七连铁 GAY")
        self.assertEqual(GayPlugin.streak_title(14), "半月老弯")
        self.assertEqual(GayPlugin.streak_title(30), "月度钉子户")
        self.assertEqual(GayPlugin.streak_title(99), "月度钉子户")

    def test_table_sorted_desc(self):
        days = [d for d, _ in STREAK_TITLES]
        self.assertEqual(days, sorted(days, reverse=True))


class TestCoupleName(unittest.TestCase):
    def test_basic_split(self):
        # 小明(x) + 小红(y) -> 小 + 小红? 各取前半：明/红 长度1取1
        name = GayPlugin.couple_name("小明", "小红")
        self.assertEqual(name, "小小"[:2] if len("小明") // 2 == 1 else name)
        # 只验证非空且由双方字符组成
        self.assertTrue(name)

    def test_length_rule(self):
        # 各取前半：floor(len/2) 至少 1 字
        self.assertEqual(GayPlugin.couple_name("ABCD", "EFGH"), "ABEF")
        self.assertEqual(GayPlugin.couple_name("ABC", "DEFGH"), "ADE")

    def test_empty_fallback(self):
        # 空名回退 "TA"，各取前半后为 "TT"
        name = GayPlugin.couple_name("", "")
        self.assertEqual(name, "TT")

    def test_long_name_truncated(self):
        a = "很长的名字一" * 5
        b = "另一个名字" * 5
        name = GayPlugin.couple_name(a, b)
        self.assertLessEqual(len(name), 12)


class TestCpScore(unittest.TestCase):
    def test_range_40_100(self):
        for i in range(100):
            s = GayPlugin.cp_score(f"a{i}", f"b{i}", "2026-08-22")
            self.assertTrue(40 <= s <= 100)

    def test_order_independent(self):
        self.assertEqual(
            GayPlugin.cp_score("alice", "bob", "2026-08-22"),
            GayPlugin.cp_score("bob", "alice", "2026-08-22"),
        )

    def test_daily_stable(self):
        self.assertEqual(
            GayPlugin.cp_score("a", "b", "2026-08-21"),
            GayPlugin.cp_score("a", "b", "2026-08-21"),
        )

    def test_days_differ(self):
        scores = {GayPlugin.cp_score("a", "b", f"2026-01-{d:02d}") for d in range(1, 15)}
        self.assertGreater(len(scores), 3)


class TestCpLevel(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(GayPlugin.cp_level(98), "天作之合")
        self.assertEqual(GayPlugin.cp_level(88), "甜到发齁")
        self.assertEqual(GayPlugin.cp_level(75), "配一脸")
        self.assertEqual(GayPlugin.cp_level(60), "有点东西")
        self.assertEqual(GayPlugin.cp_level(41), "塑料兄弟情")


class TestKnowledge(unittest.TestCase):
    def test_at_least_10_entries(self):
        self.assertGreaterEqual(len(KNOWLEDGE), 10)

    def test_all_nonempty(self):
        for k in KNOWLEDGE:
            self.assertTrue(k.strip())
