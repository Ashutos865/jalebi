"""TIES deterministic scoring engine.

Turns the Editorial Constitution (see app/knowledge/ties_constitution.md) into a
hybrid, reproducible scorer: ~70% deterministic rules + ~30% AI judgment, with hard
caps. Identical content produces an identical score every time.
"""
