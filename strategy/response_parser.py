"""
AI Response Parser — AI响应 XML+JSON 双层解析
==============================================
参考 NOFX parseFullDecisionResponse，实现：
  1. Chain of Thought（<reasoning>）提取
  2. JSON决策（<decision>）提取 + 字符编码修复
  3. JSON格式校验 + 决策字段验证
  4. 风险参数校验

使用方式：
  from strategy.response_parser import ResponseParser, Decision
  parser = ResponseParser()
  result = parser.parse(raw_response, account_equity=1000.0)
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Action(Enum):
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"
    WAIT = "wait"


@dataclass
class Decision:
    """单条交易决策"""
    symbol: str
    action: Action
    leverage: float = 1.0
    position_size_usdt: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0
    risk_usdt: float = 0.0
    reasoning: str = ""
    # 附加校验
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class ParseResult:
    """完整解析结果"""
    reasoning: str                          # Chain of Thought
    decisions: List[Decision]               # 决策列表
    valid_count: int                        # 有效决策数
    total_count: int                        # 总决策数
    raw_json: str                           # 原始JSON字符串
    parse_error: Optional[str] = None        # 解析错误信息


class ResponseParser:
    """
    AI响应解析器
    从AI原始文本中提取决策，支持字符编码修复和容错处理
    """

    # 最小/最大仓位限制（代码层强制）
    MIN_POSITION_SIZE = 12.0    # USDT
    MAX_POSITION_SIZE = 1000.0  # USDT
    MIN_CONFIDENCE = 50.0       # 最低置信度
    MIN_LEVERAGE = 1.0
    MAX_LEVERAGE = 10.0

    # 最大持仓数
    MAX_POSITIONS = 3

    # 最小盈亏比
    MIN_RISK_REWARD = 1.5

    def __init__(self):
        # 编译常用正则
        self._re_reasoning_open = re.compile(r'<reasoning[\s>]', re.IGNORECASE)
        self._re_reasoning_close = re.compile(r'</reasoning>', re.IGNORECASE)
        self._re_decision_open = re.compile(r'<decision[\s>]', re.IGNORECASE)
        self._re_decision_close = re.compile(r'</decision>', re.IGNORECASE)
        self._re_json_block = re.compile(r'```(?:json)?\s*([\[\{][\s\S]*?)\s*```', re.DOTALL)
        self._re_bare_json = re.compile(r'\[\s*\{[\s\S]*\}\s*\]', re.DOTALL)

    def parse(
        self,
        raw_response: str,
        account_equity: float = 1000.0,
        current_positions: Optional[List[str]] = None,
    ) -> ParseResult:
        """
        解析AI响应
        Args:
            raw_response: AI模型原始输出文本
            account_equity: 当前账户权益
            current_positions: 当前持仓符号列表（用于判断是否close）
        """
        current_positions = current_positions or []

        # 1. 提取 Chain of Thought
        reasoning = self._extract_reasoning(raw_response)

        # 2. 提取 JSON 决策
        json_str = self._extract_decision_json(raw_response)
        if not json_str:
            return ParseResult(
                reasoning=reasoning,
                decisions=[],
                valid_count=0,
                total_count=0,
                raw_json="",
                parse_error="No decision JSON found in response",
            )

        # 3. 修复字符编码
        json_str = self._fix_encoding(json_str)

        # 4. 解析JSON
        decisions_raw = self._parse_json(json_str)
        if decisions_raw is None:
            return ParseResult(
                reasoning=reasoning,
                decisions=[],
                valid_count=0,
                total_count=0,
                raw_json=json_str,
                parse_error="Failed to parse JSON",
            )

        # 5. 构建决策对象并校验
        decisions = self._build_decisions(
            decisions_raw,
            account_equity,
            current_positions,
        )

        valid_count = sum(1 for d in decisions if d.is_valid)

        return ParseResult(
            reasoning=reasoning,
            decisions=decisions,
            valid_count=valid_count,
            total_count=len(decisions),
            raw_json=json_str,
        )

    # ======================== 提取逻辑 ========================

    def _extract_reasoning(self, response: str) -> str:
        """提取 <reasoning>...</reasoning> 标签内容"""
        open_match = self._re_reasoning_open.search(response)
        close_match = self._re_reasoning_close.search(response)
        if open_match and close_match:
            start = open_match.end()
            return response[start:close_match.start()].strip()

        # Fallback：决策标签之前的文本
        dec_match = self._re_decision_open.search(response)
        if dec_match:
            return response[:dec_match.start()].strip()

        # 最终fallback：原始响应前500字符
        return response[:500].strip()

    def _extract_decision_json(self, response: str) -> Optional[str]:
        """
        按优先级提取JSON：
        1. <decision><pre><code>json ...</code></pre></decision>
        2. ```json ... ```
        3. 裸JSON数组 [...]
        """
        # Priority 1: decision标签内（最精确匹配）
        dec_open = self._re_decision_open.search(response)
        dec_close = self._re_decision_close.search(response)
        if dec_open and dec_close:
            inner = response[dec_open.end():dec_close.start()]
            # 在标签内搜索代码块
            for match in self._re_json_block.finditer(inner):
                return match.group(1)
            # 尝试裸JSON（标签内直接是数组）
            bare = self._re_bare_json.search(inner)
            if bare:
                return bare.group(0)
            # 尝试 <decision> 标签紧跟的JSON（无代码块）
            # 去掉空白字符后直接取 ```json 之后的部分
            json_start = inner.find('```json')
            if json_start >= 0:
                block = inner[json_start+6:]
                end = block.find('```')
                if end >= 0:
                    return block[:end].strip()

        # Priority 2: 全局 ```json 代码块搜索
        for match in self._re_json_block.finditer(response):
            return match.group(1)

        # Priority 3: 裸JSON
        bare = self._re_bare_json.search(response)
        if bare:
            return bare.group(0)

        return None

    # ======================== 编码修复 ========================

    def _fix_encoding(self, json_str: str) -> str:
        """
        修复常见字符编码问题
        - 中文引号 → ASCII
        - 中文括号 → ASCII
        - 中文冒号/逗号 → ASCII
        """
        replacements = {
            "\u201c": '"', "\u201d": '"',   # 中文引号
            "\u2018": "'", "\u2019": "'",   # 中文单引号
            "\uff08": "(", "\uff09": ")",   # 中文括号
            "\u300c": "<", "\u300d": ">",   # 中文书名号（偶发）
            "\uff1a": ":",                  # 中文冒号
            "\uff0c": ",",                  # 中文逗号
            "\u3001": ",",                  # 中文顿号
            "\u3002": ".",                  # 中文句号
        }
        for old, new in replacements.items():
            json_str = json_str.replace(old, new)
        return json_str

    # ======================== JSON解析 ========================

    def _parse_json(self, json_str: str) -> Optional[List[Dict]]:
        """解析JSON字符串，支持容错"""
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                # 有时AI返回 {"decisions": [...]} 或 {"action": ...}
                if "decisions" in data:
                    return data["decisions"]
                elif "decision" in data:
                    return [data["decision"]]
                return [data]
            if isinstance(data, list):
                return data
            return None
        except json.JSONDecodeError as e:
            # 尝试清理常见问题后重试
            cleaned = self._preclean_json(json_str)
            try:
                return json.loads(cleaned)
            except Exception:
                logger.warning(f"JSON parse failed after cleanup: {e}")
                return None

    def _preclean_json(self, s: str) -> str:
        """JSON解析前的预处理"""
        # 移除控制字符
        s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
        # 修复常见的截断问题（最后一个对象缺少结尾）
        s = s.rstrip(', \t\n')
        return s

    # ======================== 决策构建与校验 ========================

    def _build_decisions(
        self,
        raw_list: List[Dict],
        account_equity: float,
        current_positions: List[str],
    ) -> List[Decision]:
        """构建决策对象并进行全量校验"""
        decisions = []
        open_count = 0

        for item in raw_list:
            if not isinstance(item, dict):
                continue

            symbol = str(item.get("symbol", "")).upper().strip()
            if not symbol:
                continue

            # 解析 action
            action_str = str(item.get("action", "wait")).lower().replace("-", "_").replace(" ", "_")
            try:
                action = Action(action_str)
            except ValueError:
                logger.warning(f"Unknown action: {action_str}, defaulting to wait")
                action = Action.WAIT

            # 统计开仓数（限制max_positions）
            if action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                open_count += 1
                if open_count > self.MAX_POSITIONS:
                    logger.warning(f"Exceeded max positions ({self.MAX_POSITIONS}), skipping {symbol}")
                    continue

            # 基本字段
            leverage = float(item.get("leverage", 1.0))
            position_size = float(item.get("position_size_usdt", 0.0))
            stop_loss = float(item.get("stop_loss", 0.0))
            take_profit = float(item.get("take_profit", 0.0))
            confidence = float(item.get("confidence", 0.0))
            risk_usdt = float(item.get("risk_usdt", 0.0))
            reasoning_text = str(item.get("reasoning", ""))

            # 构建决策对象
            decision = Decision(
                symbol=symbol,
                action=action,
                leverage=leverage,
                position_size_usdt=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                risk_usdt=risk_usdt,
                reasoning=reasoning_text,
            )

            # 校验
            self._validate_decision(decision, account_equity, current_positions)

            decisions.append(decision)

        return decisions

    def _validate_decision(
        self,
        d: Decision,
        account_equity: float,
        current_positions: List[str],
    ):
        """校验单条决策的合法性"""
        errors = []

        # 1. action 校验
        if d.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
            # 2. 仓位大小校验
            if d.position_size_usdt < self.MIN_POSITION_SIZE:
                errors.append(f"Position size ${d.position_size_usdt:.2f} < min ${self.MIN_POSITION_SIZE}")
                d.is_valid = False
            if d.position_size_usdt > min(self.MAX_POSITION_SIZE, account_equity * 0.5):
                errors.append(f"Position size ${d.position_size_usdt:.2f} exceeds max")
                d.is_valid = False

            # 3. 杠杆校验
            if not (self.MIN_LEVERAGE <= d.leverage <= self.MAX_LEVERAGE):
                errors.append(f"Leverage {d.leverage}x outside allowed range [{self.MIN_LEVERAGE}-{self.MAX_LEVERAGE}]")
                d.is_valid = False

            # 4. 止损/止盈 逻辑校验
            if d.stop_loss and d.take_profit and d.action == Action.OPEN_LONG:
                risk = abs(d.take_profit - d.stop_loss)
                reward = abs(d.take_profit - (d.stop_loss / 0.95))  # 估算入场价
                rr = reward / risk if risk > 0 else 0
                if rr < self.MIN_RISK_REWARD:
                    errors.append(f"Risk/Reward {rr:.2f} < min {self.MIN_RISK_REWARD}")
                    # 不设为无效，仅警告

            # 5. 置信度校验
            if d.confidence < self.MIN_CONFIDENCE:
                errors.append(f"Confidence {d.confidence:.0f} < min {self.MIN_CONFIDENCE}")
                d.is_valid = False

        elif d.action in (Action.CLOSE_LONG, Action.CLOSE_SHORT):
            # 平仓决策：symbol必须在当前持仓中
            if d.symbol not in current_positions:
                errors.append(f"Cannot close {d.symbol}: not in positions {current_positions}")
                # 不设为无效，因为可能AI基于旧持仓信息决策

        d.validation_errors = errors

    # ======================== 辅助方法 ========================

    def filter_valid(self, decisions: List[Decision]) -> List[Decision]:
        """返回所有有效决策"""
        return [d for d in decisions if d.is_valid]

    def sort_by_priority(self, decisions: List[Decision]) -> List[Decision]:
        """
        按执行优先级排序：
        1. 平仓（close）优先
        2. 开仓（open）
        3. 持仓/等待
        """
        def priority(d: Decision) -> int:
            if d.action in (Action.CLOSE_LONG, Action.CLOSE_SHORT):
                return 0
            if d.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                return 1
            return 2
        return sorted(decisions, key=priority)