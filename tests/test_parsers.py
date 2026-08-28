"""Unit tests for FreeRollPasswordParser and FreerollPassParser."""

import unittest
from datetime import date, time
from pokerparser.scrapers.parsers.freeroll_password import FreeRollPasswordParser
from pokerparser.scrapers.parsers.freerollpass import FreerollPassParser
from pokerparser.domain.models import Tournament
from pokerparser.domain.poker_room import PokerRoom
from pokerparser.domain.prize import Prize


SAMPLE_FREEROLL_PASSWORD_HTML = """
<div class="pt-cv-wrapper">
    <div class="pt-cv-content-item">
        <a href="/tournaments/ggpoker-special">
            <span class="exname">GGPoker Daily Freeroll</span>
        </a>
        <div class="fpexcerpt">
            <span class="exroom"></span> GGPoker
            <span class="date-display-single">August 28, 2026</span>
            <span class="extime"></span> 20:00 GMT+2
            <span class="exprize"></span> $500
            <span class="exname"></span> GGPoker Daily Freeroll
            <span class="expass2"> secret123 </span>
        </div>
    </div>
</div>
"""

SAMPLE_FREEROLLPASS_HTML = """
<ul id="freerollList">
    <li class="row">
        <div class="col-4">
            <div class="f-size-30-576-40">18:00</div>
            <div class="f-size-15-576-20">28.08.2026</div>
            <div class="c-yellow"><svg></svg>$1,000</div>
        </div>
        <div class="col-8">
            <div class="title-room">
                <a href="/rooms/pokerstars">PokerStars</a>
            </div>
            <a href="/freeroll/stars-weekly">
                <span class="fl-text-name"><svg></svg>Stars Weekly Special</span>
            </a>
            <div id="pwd-123">
                Password: <strong class="c-red-1">pass789</strong>
            </div>
        </div>
    </li>
</ul>
"""


class TestParsers(unittest.TestCase):
    """Test suite verifying HTML scrapers parse domain models with typed Value Objects."""

    def test_freeroll_password_parser(self):
        parser = FreeRollPasswordParser(timezone="Europe/Budapest")
        tournaments = parser.parse(SAMPLE_FREEROLL_PASSWORD_HTML)

        self.assertEqual(len(tournaments), 1)
        t = tournaments[0]

        self.assertEqual(t.name, "GGPoker Daily Freeroll")
        self.assertIsInstance(t.room, PokerRoom)
        self.assertEqual(t.room.name, "GGPoker")
        self.assertEqual(t.room.clean_id, "ggpoker")

        self.assertIsInstance(t.prize, Prize)
        self.assertEqual(t.prize.amount, 500)
        self.assertEqual(t.prize.currency, "USD")

        self.assertEqual(t.password, "secret123")
        self.assertEqual(t.date, date(2026, 8, 28))
        self.assertEqual(t.time, time(20, 0))
        self.assertFalse(t.is_all_day)
        self.assertEqual(t.source, "freeroll-password.com")
        self.assertEqual(t.url, "https://www.freeroll-password.com/tournaments/ggpoker-special")

    def test_freerollpass_parser(self):
        parser = FreerollPassParser(timezone="Europe/Budapest")
        tournaments = parser.parse(SAMPLE_FREEROLLPASS_HTML)

        self.assertEqual(len(tournaments), 1)
        t = tournaments[0]

        self.assertEqual(t.name, "Stars Weekly Special")
        self.assertIsInstance(t.room, PokerRoom)
        self.assertEqual(t.room.name, "PokerStars")
        self.assertEqual(t.room.clean_id, "pokerstars")

        self.assertIsInstance(t.prize, Prize)
        self.assertEqual(t.prize.amount, 1000)

        self.assertEqual(t.password, "pass789")
        self.assertEqual(t.source, "freerollpass.com")
        self.assertEqual(t.url, "https://freerollpass.com/freeroll/stars-weekly")

    def test_freerollpass_stakepoker_password_badge_variations(self):
        """Test parsing real-world password badge variations like stakepoker-319536 with cooler password."""
        html = """
        <ul id="freerollList">
            <li class="row bg-list hot-bg">
                <div class="col-4">
                    <div class="f-size-30-576-40">20:00</div>
                    <div class="f-size-15-576-20">28.08.2026</div>
                    <div class="c-yellow">$250</div>
                </div>
                <div class="col-8">
                    <div class="title-room"><a href="https://freerollpass.com/stakepoker">Stake Poker</a></div>
                    <a href="https://freerollpass.com/stakepoker-319536"><span class="fl-text-name">PokerWired $250 GTD</span></a>
                    <div class="pt-1" id="319536">
                        <strong class="f-weight-500">Password</strong>:
                        <strong class="f-weight-500 fl-badge bg-red" style="border-radius:5px">cooler</strong>
                    </div>
                </div>
            </li>
            <li class="row">
                <div class="col-4">
                    <div class="f-size-30-576-40">16:00</div>
                    <div class="f-size-15-576-20">28.08.2026</div>
                    <div class="c-yellow">$100</div>
                </div>
                <div class="col-8">
                    <div class="title-room"><a href="https://freerollpass.com/888poker">888poker</a></div>
                    <a href="https://freerollpass.com/888poker-320354"><span class="fl-text-name">Special Freeroll</span></a>
                    <div class="pt-1" id="320354">
                        <strong class="f-weight-500">Password</strong>: will be available at
                        <span class="d-inline-block"><strong class="fl-badge bg-red">16:30</strong></span>
                    </div>
                </div>
            </li>
        </ul>
        """
        parser = FreerollPassParser(timezone="Europe/Budapest")
        tournaments = parser.parse(html)
        self.assertEqual(len(tournaments), 2)
        # 1. Stake Poker should extract 'cooler'
        self.assertEqual(tournaments[0].room.name, "Stake Poker")
        self.assertEqual(tournaments[0].password, "cooler")
        self.assertEqual(tournaments[0].has_password, True)

        # 2. Upcoming countdown should be 'n/a'
        self.assertEqual(tournaments[1].password, "n/a")

    def test_tournament_from_raw_and_pure_dataclass(self):
        """Test Tournament pure dataclass constructor and from_raw factory."""
        t1 = Tournament(
            name="Manual",
            room=PokerRoom.from_raw("888"),
            date=date(2026, 8, 28),
            time=time(12, 0),
            is_all_day=False,
            prize=Prize.from_raw("€200"),
            password="none",
            source="test",
        )
        self.assertEqual(t1.room.name, "888poker")
        self.assertEqual(t1.prize.amount, 200)
        self.assertEqual(t1.prize.currency, "EUR")

        t2 = Tournament.from_raw(
            name="Raw Factory",
            room="unibet",
            date=date(2026, 8, 28),
            time=None,
            is_all_day=True,
            prize="£50",
            source="test",
        )
        self.assertEqual(t2.room.name, "Unibet")
        self.assertEqual(t2.prize.amount, 50)
        self.assertEqual(t2.prize.currency, "GBP")
        self.assertTrue(t2.is_all_day)

    def test_event_hash_source_independence(self):
        """Test that identical tournaments from different sources produce identical event_hash."""
        t_src1 = Tournament.from_raw(
            name="Daily Free $500",
            room="GGPoker",
            date=date(2026, 8, 28),
            time=time(20, 0),
            is_all_day=False,
            prize="$500",
            password="pwd",
            source="freeroll-password.com",
        )

        t_src2 = Tournament.from_raw(
            name="  daily free $500  ",
            room="gg",
            date=date(2026, 8, 28),
            time=time(20, 0),
            is_all_day=False,
            prize="$500",
            password="different_or_none",
            source="freerollpass.com",
        )

        self.assertEqual(t_src1.event_hash, t_src2.event_hash)

    def test_value_objects_hashability(self):
        """Test that PokerRoom and Prize are hashable and follow hash/equality invariants."""
        room1 = PokerRoom.from_raw("PokerStars")
        room2 = PokerRoom.from_raw("stars")
        room3 = PokerRoom.from_raw("GGPoker")

        self.assertEqual(hash(room1), hash(room2))
        room_set = {room1, room2, room3}
        self.assertEqual(len(room_set), 2)

        room_dict = {room1: "Stars Data"}
        self.assertEqual(room_dict[room2], "Stars Data")

        prize1 = Prize.from_raw("$100")
        prize2 = Prize.from_raw("100 USD")
        prize3 = Prize.from_raw("€200")

        self.assertEqual(hash(prize1), hash(prize2))
        prize_set = {prize1, prize2, prize3}
        self.assertEqual(len(prize_set), 2)


if __name__ == "__main__":
    unittest.main()
