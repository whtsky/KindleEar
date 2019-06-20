import itertools

from .cartoonmadbase import CartoonMadBaseBook
from .dmzjbase import DMZJBaseBook
from .gufengbase import GuFengBaseBook
from .manhuaduibase import ManHuaDuiBaseBook
from .manhuaguibase import ManHuaGuiBaseBook
from .manhuarenbase import ManHuaRenBaseBook
from .seven33sobase import Seven33SoBaseBook
from .tencentbase import TencentBaseBook
from .tohomhbase import ToHoMHBaseBook
from .twoanimxbase import TwoAniMxBaseBook

ComicBaseClasses = [
    CartoonMadBaseBook,
    TencentBaseBook,
    TwoAniMxBaseBook,
    ManHuaDuiBaseBook,
    ManHuaGuiBaseBook,
    ManHuaRenBaseBook,
    Seven33SoBaseBook,
    ToHoMHBaseBook,
    DMZJBaseBook,
    GuFengBaseBook,
]

comic_domains = tuple(itertools.chain(*[x.accept_domains for x in ComicBaseClasses]))
