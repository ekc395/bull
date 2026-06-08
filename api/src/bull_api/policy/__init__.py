"""Outcome-feedback learning layer (see plan.md → Outcome-feedback loop).

A wrapper learned around the fixed Opus policy: it derives a bucketed decision
context from each verdict's stored facts (`features.py`), and — in later phases
— calibrates confidence, measures per-context edge, and gates/sizes trades from
realized outcomes. No model weights change; the policy is an explicit,
auditable rule fitted on the `VerdictScore` outcome table.
"""
