"""Local (non-LLM) machine-learning layer for RegGraph.

Everything here runs offline on a model trained from the synthetic SEBI corpus,
so a circular can be recognised, classified and turned into obligations even when
the LLM provider is unreachable or out of quota.
"""
