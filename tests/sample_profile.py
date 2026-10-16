"""A trimmed copy of the portfolio's projects.json shape, for tests."""

SAMPLE_PROFILE = {
    "title": "Data Engineer & Machine Learning Engineer",
    "summary": "Data engineer and machine learning engineer (MS Information Technology, ASU, 4.0 GPA).",
    "education": [{"degree": "Master of Science, IT", "institution": "Arizona State University (ASU)", "date": "Aug 2022 - Jul 2024"}],
    "experience": [
        {
            "role": "Teleoperation Data Collection Associate",
            "company": "Objectways Technologies LLC | Tempe, AZ",
            "dates": "May 2026 - Present",
            "bullets": [{"html": "Lifted dataset accuracy by <strong>20%</strong> across <strong>10,000+</strong> samples."}],
        },
        {
            "role": "Applied Machine Learning Engineer",
            "company": "Technoid LLC | Remote",
            "dates": "Dec 2025 - May 2026",
            "bullets": [{"html": "Raised recommendation accuracy by <strong>25%</strong> with GPT-4o mini &amp; PostgreSQL."}],
        },
    ],
    "projects": [
        {"name": "Job Search CRM & AI Application Tailoring Center", "date": "2026", "desc": "Deployed job-search platform with 985 tests.",
         "bullets": [{"html": "Non-LLM guardrail on every generated claim."}]},
        {"name": "Job Search dbt Warehouse", "date": "2026", "desc": "dbt warehouse on Databricks.", "bullets": []},
        {"name": "CurioSync: Serverless Tech News & LinkedIn Publisher", "date": "2026", "desc": "Publisher.", "bullets": []},
        {"name": "Chef at Gathering", "date": "2023", "desc": "Team project.", "bullets": []},
    ],
}
