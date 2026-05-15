from core.autoamtion.webbridge_platforms.goofish import GoofishWebBridgeAutomation
from core.autoamtion.webbridge_platforms.jd import JdWebBridgeAutomation
from core.autoamtion.webbridge_platforms.pdd import PddWebBridgeAutomation
from core.autoamtion.webbridge_platforms.tb import TbWebBridgeAutomation


WEBBRIDGE_AUTOMATIONS = {
    "tb": TbWebBridgeAutomation,
    "jd": JdWebBridgeAutomation,
    "pdd": PddWebBridgeAutomation,
    "goofish": GoofishWebBridgeAutomation,
}


__all__ = ["WEBBRIDGE_AUTOMATIONS"]
