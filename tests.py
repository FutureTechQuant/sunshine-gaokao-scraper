"""单元测试"""
import pytest
from scraper import GaokaoScraper, Specialty, SchoolSpecialty


class TestSpecialty:
    def test_to_dict(self):
        s = Specialty(
            specialty_id="080901",
            name="计算机科学与技术",
            level="本科",
            category="工学",
        )
        d = s.to_dict()
        assert d["specialty_id"] == "080901"
        assert d["name"] == "计算机科学与技术"
        assert d["level"] == "本科"


class TestSchoolSpecialty:
    def test_to_dict(self):
        s = SchoolSpecialty(
            specialty_id="080901",
            school_name="清华大学",
            province="北京",
        )
        d = s.to_dict()
        assert d["school_name"] == "清华大学"
        assert d["province"] == "北京"


class TestScraper:
    def test_init(self):
        scraper = GaokaoScraper()
        assert scraper.session is not None
