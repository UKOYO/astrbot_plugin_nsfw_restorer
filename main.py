from __future__ import annotations

import re
from typing import Dict, Any
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Plain

PLUGIN_NAME = "astrbot_plugin_nsfw_restorer"

# 默认基础词典，作为配置为空时的保底
DEFAULT_MAPPINGS: Dict[str, str] = {
    "[§penis§]": "肉棒",
    "[§cock§]": "阴茎",
    "[§glans§]": "龟头",
    "[§vagina§]": "小穴",
    "[§cunt§]": "骚穴",
    "[§clit§]": "阴蒂",
    "[§breasts§]": "乳房",
    "[§nipples§]": "乳头",
    "[§ass§]": "屁股",
    "[§anus§]": "后穴",
    "[§fuck§]": "操",
    "[§thrust§]": "抽送",
    "[§penetrate§]": "插进",
    "[§cum§]": "射精",
    "[§creampie§]": "内射",
    "[§orgasm§]": "高潮",
    "[§squirt§]": "潮吹",
    "[§juices§]": "淫水",
    "[§semen§]": "精液",
    "[§leak§]": "流出",
    "[§wet§]": "湿透",
    "[§tight§]": "紧致",
    "[§spread§]": "掰开",
    "[§moan§]": "娇喘",
    "[§suck§]": "吸吮",
    "[§lick§]": "舔舐",
    "[§p§]": "肉棒",
    "[§v§]": "小穴",
    "[§c§]": "高潮",
    "[§s§]": "内射",
    "[§j§]": "淫水",
    "[§f§]": "狠狠操",
    "[§t§]": "抽插",
    "[§n§]": "乳头",
    "[§b§]": "大白兔",
    "[§ride§]": "骑乘",
    "[§climax§]": "绝顶",
    "[§fondle§]": "爱抚",
    "[§caress§]": "抚摸",
    "[§ejaculate§]": "射精",
    "[§fill§]": "填满",
    "[§swallow§]": "吞下",
    "[§blowjob§]": "口交",
    "[§paizuri§]": "乳交",
    "[§deepthroat§]": "深喉",
    "[§finger§]": "抠弄",
    "[§tease§]": "挑逗",
    "[§rub§]": "摩擦",
    "[§tremble§]": "颤抖",
    "[§spasm§]": "痉挛",
    "[§pant§]": "喘息",
    "[§kiss§]": "接吻",
    "[§strip§]": "脱光",
    "[§naked§]": "全裸",
    "[§dirty§]": "淫靡",
    "[§lewd§]": "色情",
    "[§sensual§]": "敏感",
    "[§heat§]": "燥热",
    "[§drool§]": "流口水",
    "[§thighs§]": "大腿内侧",
    "[§waist§]": "细腰",
    "[§uterus§]": "子宫口",
    "[§cervix§]": "宫颈",
    "[§areola§]": "乳晕",
    "[§groin§]": "腿心",
    "[§slit§]": "肉缝",
    "[§lips§]": "阴唇",
    "[§foreskin§]": "包皮",
    "[§m§]": "喘息",
    "[§k§]": "接吻",
    "[§l§]": "舔舐",
    "[§w§]": "湿透",
    "[§d§]": "深喉",
    "[§h§]": "做爱",
    "[§u§]": "子宫",
}


@register(
    PLUGIN_NAME,
    "唯笑 & 优可",
    "NSFW 占位符反混淆还原器",
    "1.1.0",
)
class NSFWRestorerPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._pattern = None
        self._active_mappings: Dict[str, str] = {}
        self._compile_rules()
        logger.info(
            "[NSFWRestorer] 占位符反混淆还原器已初始化，已加载 %d 条规则",
            len(self._active_mappings),
        )

    def _compile_rules(self) -> None:
        """从配置中加载并编译正则规则表"""
        cfg_mappings = self.config.get("mappings")
        if isinstance(cfg_mappings, dict) and cfg_mappings:
            self._active_mappings = {str(k): str(v) for k, v in cfg_mappings.items()}
        else:
            self._active_mappings = dict(DEFAULT_MAPPINGS)

        if not self._active_mappings:
            self._pattern = None
            return

        # 按 Key 长度倒序排序，避免短键前缀截断长键
        sorted_keys = sorted(self._active_mappings.keys(), key=len, reverse=True)
        regex_parts = [re.escape(k) for k in sorted_keys if k]
        if regex_parts:
            self._pattern = re.compile("|".join(regex_parts))
        else:
            self._pattern = None

    def _restore_text(self, text: str) -> tuple[str, int]:
        if not self._pattern:
            return text, 0

        count = 0

        def _replace(match: re.Match) -> str:
            nonlocal count
            matched_key = match.group(0)
            target = self._active_mappings.get(matched_key, matched_key)
            count += 1
            return target

        new_text = self._pattern.sub(_replace, text)
        return new_text, count

    @filter.on_decorating_result(priority=20)
    async def on_decorating_result(self, event: AstrMessageEvent) -> None:
        """在结果发送给用户前的最终修饰阶段，还原所有 Plain 组件中的占位符"""
        if not self.config.get("enabled", True):
            return

        result = event.get_result()
        if not result or not result.chain:
            return

        # 动态重载可能在运行时修改的配置
        self._compile_rules()

        total_restored = 0
        for comp in result.chain:
            if isinstance(comp, Plain) and comp.text:
                # 快速前置判断，避免全文无匹配时的正则遍历开销
                if any(k in comp.text for k in ("[§", "[#")):
                    new_text, hits = self._restore_text(comp.text)
                    if hits > 0:
                        comp.text = new_text
                        total_restored += hits

        if total_restored > 0 and self.config.get("log_restorations", True):
            logger.info(
                "[NSFWRestorer] 成功还原 %d 处占位符为真实直白词汇", total_restored
            )
