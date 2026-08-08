"""Eval harness: golden examples + deterministic checks + LLM-as-judge.

Public surface:
    from evals.schema import load_golden_examples, list_categories
    from evals.runner import run_category, check_deterministic, summarize
    from evals.runner import save_baseline, load_baseline, check_regression
    from evals.judge import judge_response, JudgeScore
"""
