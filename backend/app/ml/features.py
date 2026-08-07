"""
Hand-crafted features for obligation detection.

TF-IDF alone learns the *vocabulary* of the synthetic corpus. These features
encode the things that make a sentence an obligation in any regulatory text —
deontic modality ("shall", "must"), a following verb, a bound party, a timeline —
plus the structural giveaways of the noise found in real PDFs (contents lists,
abbreviation tables, page furniture).

Lives in its own module because scikit-learn pipelines are pickled by reference:
joblib must be able to import this class when the bundle is loaded.
"""
from __future__ import annotations

import re
from typing import List

import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin

_DEONTIC = re.compile(
    r'\b(shall|must|is required to|are required to|is obliged to|are obliged to|'
    r'is to be|are to be|has to|have to|needs to|need to)\b', re.IGNORECASE)
_PROHIBITION = re.compile(
    r'\b(shall not|must not|shall refrain|is prohibited|are prohibited|no\s+\w+\s+shall)\b',
    re.IGNORECASE)
_DISCRETION = re.compile(r'\b(may|should|is encouraged|endeavour|at its discretion)\b',
                         re.IGNORECASE)
_MODAL_VERB = re.compile(
    r'\b(?:shall|must)\s+(?:not\s+)?(?:be\s+)?([a-z]{3,})\b', re.IGNORECASE)
_PARTY = re.compile(
    r'\b(stock broker|trading member|clearing member|depository|depositories|'
    r'depository participant|listed entit|listed compan|investment adviser|'
    r'research analyst|portfolio manager|asset management|mutual fund|registrar|'
    r'share transfer agent|intermediar|member|participant|company|board|committee|'
    r'officer|director)\b', re.IGNORECASE)
_TIMELINE = re.compile(
    r'\b(within\s+\w+\s+(?:working\s+|calendar\s+|business\s+)?(?:days?|weeks?|months?|hours?)|'
    r'daily|weekly|monthly|quarterly|half-yearly|annually|every\s+\w+\s+(?:quarter|month|year)|'
    r'on\s+or\s+before|not\s+later\s+than|with\s+effect\s+from)\b', re.IGNORECASE)
_EVIDENCE_NOUN = re.compile(
    r'\b(report|register|record|policy|log|statement|certificate|audit|minutes|'
    r'disclosure|declaration|acknowledgement|document)\b', re.IGNORECASE)

# Structural noise signatures that appear in real circular PDFs
_DOT_LEADER = re.compile(r'\.{3,}|\s\.\s\.\s')
_TRAILING_PAGENO = re.compile(r'[a-zA-Z)\]]\s*\d{1,3}\s*$')
_ONLY_REFERENCE = re.compile(
    r'^(?:refer|see|as per|in terms of|pursuant to|under)\b.{0,80}$', re.IGNORECASE)
_DEFINITION = re.compile(r'["‘’“”].{2,40}["‘’“”]\s+means\b',
                         re.IGNORECASE)
# Annexure/appendix index entries. A run of two or more in one line is an index,
# never an obligation — even though the titles listed often contain "shall".
_ANNEX_REF = re.compile(r'\b(?:annexure|appendix|schedule)\s*[-–—:]?\s*\d+', re.IGNORECASE)
_STARTS_ANNEX = re.compile(r'^\s*(?:annexure|appendix|schedule|chapter)\b', re.IGNORECASE)

FEATURE_NAMES: List[str] = [
    "has_deontic", "has_prohibition", "has_discretion", "modal_followed_by_verb",
    "names_party", "has_timeline", "has_evidence_noun",
    "len_words_norm", "digit_ratio", "caps_ratio", "punct_ratio",
    "dot_leader", "trailing_page_number", "reference_only", "is_definition",
    "starts_with_clause_number", "ends_with_period", "comma_density",
    "annexure_index_run", "starts_with_annexure",
]


class ModalityFeatures(BaseEstimator, TransformerMixin):
    """Dense linguistic/structural features, returned sparse for the FeatureUnion."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = [self._row(str(t)) for t in X]
        return sparse.csr_matrix(np.asarray(rows, dtype=np.float64))

    def get_feature_names_out(self, input_features=None):
        return np.asarray(FEATURE_NAMES, dtype=object)

    @staticmethod
    def _row(s: str) -> List[float]:
        words = s.split()
        n = max(len(words), 1)
        chars = max(len(s), 1)
        alpha = [c for c in s if c.isalpha()]
        return [
            1.0 if _DEONTIC.search(s) else 0.0,
            1.0 if _PROHIBITION.search(s) else 0.0,
            1.0 if _DISCRETION.search(s) else 0.0,
            1.0 if _MODAL_VERB.search(s) else 0.0,
            1.0 if _PARTY.search(s) else 0.0,
            1.0 if _TIMELINE.search(s) else 0.0,
            1.0 if _EVIDENCE_NOUN.search(s) else 0.0,
            min(n / 60.0, 1.0),
            sum(c.isdigit() for c in s) / chars,
            (sum(c.isupper() for c in alpha) / len(alpha)) if alpha else 0.0,
            sum(not c.isalnum() and not c.isspace() for c in s) / chars,
            1.0 if _DOT_LEADER.search(s) else 0.0,
            1.0 if _TRAILING_PAGENO.search(s.strip()) else 0.0,
            1.0 if _ONLY_REFERENCE.match(s.strip()) else 0.0,
            1.0 if _DEFINITION.search(s) else 0.0,
            1.0 if re.match(r'^\s*\d+(\.\d+)*\s', s) else 0.0,
            1.0 if s.strip().endswith('.') else 0.0,
            min(s.count(',') / n * 5, 1.0),
            1.0 if len(_ANNEX_REF.findall(s)) >= 2 else 0.0,
            1.0 if _STARTS_ANNEX.match(s) else 0.0,
        ]
