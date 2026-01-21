# app/modules/seo_engine.py

from typing import List, Dict


# ======================
# CONFIGURAZIONE PUNTEGGI
# ======================

CATEGORY_WEIGHTS = {
    "technical": 0.35,
    "onpage": 0.30,
    "content": 0.20,
    "performance": 0.10,
    "other": 0.05,
    "ux": 0.05,
    "security": 0.05
}

SEVERITY_WEIGHTS = {
    "error": 100,
    "warning": 60,
    "notice": 30
}

DIFFICULTY_WEIGHTS = {
    "easy": 20,
    "medium": 60,
    "hard": 100
}


# ============================
# CLASSE: SEO ERROR (DETECTED)
# ============================

class SEOError:
    def __init__(self,
                 error_id: str,
                 category: str,
                 description: str,
                 severity: str,
                 penalty: int,
                 difficulty: str,
                 suggested_fix: str = "",
                 snippet_code: str = ""):

        self.error_id = error_id
        self.category = category
        self.description = description
        self.severity = severity
        self.penalty = penalty
        self.difficulty = difficulty
        self.suggested_fix = suggested_fix
        self.snippet_code = snippet_code
        self.priority = None  # calcolata dopo


    def compute_priority(self):
        severity_weight = SEVERITY_WEIGHTS.get(self.severity, 30)
        impact_weight = 20 if self.penalty <= 10 else 60 if self.penalty <= 20 else 100
        difficulty_weight = DIFFICULTY_WEIGHTS.get(self.difficulty, 60)

        score = (
            (severity_weight * 0.5) +
            (impact_weight * 0.3) +
            (difficulty_weight * 0.2)
        )

        if score > 70:
            self.priority = "high"
        elif score > 40:
            self.priority = "medium"
        else:
            self.priority = "low"

        return self.priority


# ======================
# SEO SCORING ENGINE
# ======================

class SEOScoringEngine:
    def __init__(self, errors: list[dict], performance_score: int | None = None):
        self.errors = errors
        self.performance_score = performance_score

    # --------------------------------------------------
    # GROUP ERRORS BY CATEGORY
    # --------------------------------------------------
    def categorize(self):
        categories = {}
        for err in self.errors:
            cat = err.get("category", "other")
            categories.setdefault(cat, []).append(err)
        return categories

    # --------------------------------------------------
    # COUNT ERRORS BY SEVERITY
    # --------------------------------------------------
    def severity_count(self):
        sev = {"error": 0, "warning": 0, "notice": 0}
        for err in self.errors:
            level = err.get("severity", "notice")
            if level in sev:
                sev[level] += 1
        return sev

    # --------------------------------------------------
    # SCORE PER CATEGORY (100 - penalties)
    # --------------------------------------------------
    def score_by_category(self):
        penalties = {}

        for err in self.errors:
            cat = err.get("category", "other")
            penalties.setdefault(cat, 0)
            penalties[cat] += err.get("penalty", 0)

        scores = {}
        for cat, penalty in penalties.items():
            score = max(0, 100 - penalty)
            scores[cat] = score

        return scores

    # --------------------------------------------------
    # FINAL WEIGHTED SCORE
    # --------------------------------------------------
    def weighted_total_score(self):
        cat_scores = self.score_by_category()

        total = 0
        total_weights = 0

        for cat, score in cat_scores.items():
            weight = CATEGORY_WEIGHTS.get(cat, 0.05)
            total += score * weight
            total_weights += weight

        if self.performance_score is not None:
            total += self.performance_score * CATEGORY_WEIGHTS["performance"]
            total_weights += CATEGORY_WEIGHTS["performance"]

        final = int(round(total / total_weights))
        return min(max(final, 0), 100)

    # --------------------------------------------------
    # FINAL OUTPUT FOR API
    # --------------------------------------------------
    def generate_output(self):
        return {
            "final_score": self.weighted_total_score(),
            "category_breakdown": self.score_by_category(),
            "performance_score": self.performance_score,
            "errors": self.errors,
            "errors_by_category": self.categorize(),
            "severity_summary": self.severity_count()
        }
