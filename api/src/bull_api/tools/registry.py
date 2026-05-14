"""Anthropic tool-schema registry.

We don't use the tool-use loop for orchestration (tools are called deterministically
in Python first). The single schema here is `submit_verdict`, used for structured output
on the synthesis call.
"""

SUBMIT_VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the final swing-trading verdict for the ticker.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["BUY", "HOLD", "SELL"]},
            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            "headline": {"type": "string", "maxLength": 280},
            "report": {
                "type": "object",
                "properties": {
                    "technical": {"type": "string"},
                    "fundamentals_and_supply_chain": {"type": "string"},
                    "news_sentiment": {"type": "string"},
                    "risks": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
                "required": [
                    "technical",
                    "fundamentals_and_supply_chain",
                    "news_sentiment",
                    "risks",
                    "reasoning",
                ],
            },
            "key_levels": {
                "type": "object",
                "properties": {
                    "support": {"type": "array", "items": {"type": "object"}},
                    "resistance": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["support", "resistance"],
            },
        },
        "required": ["action", "confidence", "headline", "report", "key_levels"],
    },
}

TOOLS = [SUBMIT_VERDICT_TOOL]
