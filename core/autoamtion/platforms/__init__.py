from core.autoamtion.platforms.goofish.collector import GoofishAutomation
from core.autoamtion.platforms.jd.collector import JdAutomation
from core.autoamtion.platforms.pdd.collector import PddAutomation
from core.autoamtion.platforms.tb.collector import TbAutomation


PLATFORM_AUTOMATIONS = {
    "tb": TbAutomation,
    "jd": JdAutomation,
    "pdd": PddAutomation,
    "goofish": GoofishAutomation,
}


__all__ = ["PLATFORM_AUTOMATIONS"]
