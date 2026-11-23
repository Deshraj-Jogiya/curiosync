"""Which skills employers are asking for, so posts show the ones that get his profile found.

data/market_skills.json is exported from Career Pilot (`python -m app.ingest.cli market-skills --out ...`): the skills required by the
target-role postings of the last 90 days (data engineering, data science, ML/AI engineering, analytics), ranked by the share of postings
that require each, with how strongly his profile shows it. Only skills his own work shows ("work") are offered here: a post can only
showcase what he has done.

A story qualifies for a post only when it shows at least one of those skills; stories are ranked by how much demand the skills they show
carry, and a draft must name the skills by name in the body (owner, 2026-11-18: reach only grows when a post showcases the skills the
roles he wants are hiring for; a post about a font-size setting showed none).
"""
import json
import os
import re
from datetime import date

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "market_skills.json")
MIN_SHARE = 5          # percent of target postings; below this a skill is too rare to carry a post
STALE_AFTER_DAYS = 45
MIN_STORY_SKILLS = 2  # a story must show at least this many demanded skills to be posted

# Words a story or post uses for a market skill. Only concrete names: a generic word ("pipeline", "chart", "model") would let any
# post pass. The market term itself always counts.
# A story shows a demanded skill when it names the skill or a tool that is that skill (pandas is Python, DuckDB is SQL, a confusion
# matrix is machine learning): the 11/22 bank had 17 unposted stories and none passed the gate because their skills were written
# as libraries (GeoPandas, scikit-learn, pandas) while the market list names the skill.
ALIASES = {
    "Python": ["python", "pandas", "numpy", "geopandas", "scikit-learn", "sklearn", "pytest", "fastapi", "polars", "matplotlib",
               "seaborn", "pyspark", "jupyter", "pydantic", "sqlalchemy"],
    "SQL": ["sql", "duckdb", "postgres", "postgresql", "sqlite", "bigquery", "snowflake", "sql server", "t-sql", "dbt"],
    "Machine Learning": ["machine learning", "scikit-learn", "sklearn", "random forest", "xgboost", "isolation forest", "gradient boost",
                         "logistic regression", "linear regression", "classifier", "ml model", "confusion matrix", "cross-validat",
                         "walk-forward", "backtest", "train/test", "hyperparameter", "feature importance", "neural network",
                         "deep learning", "model accuracy", "accuracy loss", "model drift", "drift monitor", "recommender", "clustering",
                         "k-means", "anomaly detection model"],
    "Statistics": ["statistic", "kolmogorov", "ks test", "ks-test", "population stability index", "psi", "z-score", "benford",
                   "permutation test", "p-value", "standard error", "confidence interval", "hypothesis test", "chi-square",
                   "standard deviation", "t-test", "a/b test", "correlation", "kaplan-meier", "log-rank", "survival",
                   "mean absolute", "median", "percentile", "variance", "rfm"],
    "Data visualization": ["data visualization", "tableau", "power bi", "matplotlib", "plotly", "dashboard", "seaborn", "arcgis",
                           "chart", "choropleth", "map layer", "streamlit"],
    "ETL": ["etl", "elt", "ingestion", "data pipeline", "pipeline", "parquet", "incremental load", "staging table", "data quality check"],
    "LLM": ["llm", "large language model", "claude", "gpt", "qwen", "lora", "fine-tun", "prompt"],
    "CI/CD": ["ci/cd", "github actions", "continuous integration", "fails the build", "fails ci", "in ci"],
    "PyTorch": ["pytorch"],
    "RAG": ["rag", "retrieval-augmented", "retrieval augmented"],
    "NLP": ["nlp", "spacy", "named entity", "ner", "sentence-transformers", "sentence transformers", "natural language",
            "semantic search", "embedding", "question answering", "tokeniz", "text classification"],
    "Spark": ["spark", "pyspark"],
    "PySpark": ["pyspark"],
    "Docker": ["docker", "container"],
    "Airflow": ["airflow"],
    "dbt": ["dbt"],
    "Git": ["git ", "github"],
    "AWS": ["aws", "amazon web services", "s3", "lambda", "glue", "athena"],
    "Azure": ["azure"],
    "S3": ["s3"],
}


def load(path: str | None = None) -> dict:
    try:
        with open(path or PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"skills": []}


def demanded(data: dict | None = None) -> list[dict]:
    """Skills employers require that his work shows, most demanded first."""
    data = load() if data is None else data
    return [s for s in data.get("skills", []) if s.get("evidence") == "work" and s.get("share", 0) >= MIN_SHARE]


def stale(data: dict | None = None, today: date | None = None) -> bool:
    data = load() if data is None else data
    try:
        made = date.fromisoformat(data.get("generated_at", ""))
    except ValueError:
        return True
    return ((today or date.today()) - made).days > STALE_AFTER_DAYS


def _words(term: str) -> list[str]:
    return [term.lower()] + ALIASES.get(term, [])


def _mentions(word: str, low: str) -> bool:
    # Short names (R, SQL, PSI, RAG, AWS) only as whole words; longer ones as word starts ("statistic" matches "statistical").
    word = word.strip()
    if len(word) <= 4 or not word.isalpha():
        return re.search(r"(?<![\w/])" + re.escape(word) + r"(?![\w])", low) is not None
    return re.search(r"(?<![\w])" + re.escape(word), low) is not None


def skills_in(text: str, data: dict | None = None) -> list[dict]:
    """The demanded skills a text names, most demanded first."""
    low = " " + text.lower() + " "
    return [s for s in demanded(data) if any(_mentions(w, low) for w in _words(s["term"]))]


def story_skills(story: dict, data: dict | None = None) -> list[dict]:
    """The demanded skills a story shows: in its own skills list, question, test, results or decision."""
    parts = [story.get("question", ""), story.get("test", ""), story.get("decision", ""), story.get("detail", ""),
             " ".join(story.get("skills") or []), " ".join(r.get("label", "") for r in story.get("results") or [])]
    return skills_in(" \n ".join(p for p in parts if p), data)


def demand_score(skills: list[dict], featured: set[str] | frozenset = frozenset()) -> float:
    """Sum of the posting shares of the skills shown; a skill featured in the last few posts counts a third, so posts rotate across
    the demanded skills instead of repeating Python every time."""
    return sum(s["share"] / (3 if s["term"].lower() in featured else 1) for s in skills)


def hashtag(term: str) -> str:
    return "#" + {"Machine Learning": "MachineLearning", "Data visualization": "DataVisualization", "CI/CD": "CICD",
                  "LLM": "LLM", "A/B testing": "ABTesting"}.get(term, re.sub(r"[^A-Za-z0-9]", "", term))
