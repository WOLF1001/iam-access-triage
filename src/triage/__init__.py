"""AI-assisted IAM triage prototype.

Принцип: LLM — парсер, не суддя. Маршрут обирає детермінований policy engine
(config/policy.yaml) на основі сигналів з тексту, LLM і read-side джерел.
"""
