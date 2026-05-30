"""
strategy/ — 策略模块
参考 NOFX decision/engine.go 完整策略循环

子模块：
  data_assembler.py   — 市场数据组装层（多时间框架K线+指标+OI+资金流向）
  prompt_builder.py   — 结构化 Prompt 构建器（System 8段式 + User Prompt）
  response_parser.py  — AI响应解析器（XML+JSON双层 + 字符编码修复 + 决策校验）
  engine.py           — 策略执行引擎（串联整个循环：数据→Prompt→AI→解析→风控→执行）
"""

from .data_assembler import DataAssembler, TradingContext, AccountData, PositionData, MarketData, QuantData
from .prompt_builder import PromptBuilder, TradingMode, RiskControlConfig
from .response_parser import ResponseParser, Decision, Action, ParseResult
from .engine import AITradingEngine

__all__ = [
    "DataAssembler",
    "TradingContext",
    "AccountData",
    "PositionData",
    "MarketData",
    "QuantData",
    "PromptBuilder",
    "TradingMode",
    "RiskControlConfig",
    "ResponseParser",
    "Decision",
    "Action",
    "ParseResult",
    "AITradingEngine",
]