"""Resume service containing structured resume info for LLM prompting."""

RESUME_DATA = {
    "summary": (
        "Research-focused data/ML engineer with over three years of extensive experience "
        "delivering ETL automation (70% efficiency gains), AI model optimization (25% accuracy boosts), "
        "and cloud data pipelines across research and industry roles. Expertise in "
        "Python/SQL/PostgreSQL, OpenAI APIs, Supabase/AWS/Snowflake, and ML techniques from "
        "K-Means clustering to NLP systems. ASU research alum and IBM certified, "
        "currently a Teleoperation Data Collection Associate at Objectways Technologies LLC."
    ),
    "education": [
        {
            "institution": "Arizona State University",
            "degree": "Master of Science, Information Technology",
            "dates": "Aug 2022 - Jul 2024",
            "gpa": "4.0/4.0",
            "location": "Tempe, AZ",
        },
        {
            "institution": "Institute of Advanced Research",
            "degree": "Bachelor of Technology, Computer Engineering",
            "dates": "Aug 2017 - Jul 2021",
            "gpa": "7.8/10",
            "location": "Gandhinagar, GJ",
        },
    ],
    "skills": {
        "programming": ["Python", "SQL", "PostgreSQL", "R/Tidyverse", "Git"],
        "data_science_ml": [
            "Regression Analysis",
            "Random Forest",
            "Scikit-learn",
            "Pandas",
            "NumPy",
            "A/B Testing",
            "Experiment Design",
            "Statistical Analysis",
            "Forecasting",
            "Deep Learning",
            "Neural Networks",
            "Model Evaluation",
            "Feature Engineering",
            "Time Series Analysis",
            "Anomaly Detection",
            "Recommendation Systems",
            "OpenAI API",
        ],
        "visualization": [
            "Tableau",
            "Power BI",
            "Seaborn",
            "Matplotlib",
            "Product Analytics",
        ],
        "cloud": ["Google Workspace", "Azure ML", "AWS", "Data Lakes", "Snowflake"],
        "data_engineering": [
            "ETL Pipeline Design",
            "Data Integration",
            "Data Transformation",
            "Data Warehousing",
            "Data Modeling",
            "Data Governance",
            "Data Quality",
            "Data Architecture",
        ],
    },
    "experience": [
        {
            "company": "Objectways Technologies LLC",
            "role": "Teleoperation Data Collection Associate",
            "location": "Tempe, Arizona",
            "dates": "May 2026 - Present (Part-Time)",
            "accomplishments": [
                "Collected and validated 10,000+ high-quality teleoperation data samples for AI/ML model training using Python-based workflows, improving dataset accuracy and consistency by 20%.",
                "Developed and maintained scalable data pipelines using Python, Scala, and Kubernetes to process and organize large datasets, reducing data processing time by 30% and enhancing system efficiency.",
                "Performed data analysis and quality assurance on robotics-generated datasets, identifying and resolving data inconsistencies, which improved model training performance and reduced error rates by 15%.",
            ],
        },
        {
            "company": "Technoid LLC",
            "role": "Applied Machine Learning Engineer",
            "location": "Piscataway, New Jersey",
            "dates": "Dec 2025 - May 2026 (Contract)",
            "accomplishments": [
                "Optimized GPT-4o mini models for resume analysis/tailoring using OpenAI APIs, SQL, and PostgreSQL, improving recommendation accuracy by 25%.",
                "Established Supabase data sync with RLS fixes and PostgreSQL backend, reducing data sync latency by 65% for real-time operations.",
                "Produced phased regression and UAT testing frameworks, cutting model deployment errors by 30%.",
            ],
        },
        {
            "company": "Zifatech Solutions LLC",
            "role": "Data Analyst / Data Engineer",
            "location": "Milwaukee, Wisconsin",
            "dates": "Jun 2025 - Dec 2025 (Contract)",
            "accomplishments": [
                "Transformed SQL/Python-based ETL pipelines to automate sales insights reporting, reducing manual effort by 70% and improving data refresh consistency.",
                "Migrated legacy data workflows to AWS Glue and S3, increasing data availability by 60% and streamlining integration with Snowflake and Power BI.",
                "Modernized Star Schema models in Snowflake using Great Expectations QA validations, achieving over 98% data reliability.",
                "Built interactive Power BI dashboards connected to Snowflake datasets, translating analytical outputs into actionable business insights for sales and operations teams.",
            ],
        },
        {
            "company": "Arizona State University",
            "role": "Data Engineer & Machine Learning Research Assistant",
            "location": "Tempe, Arizona",
            "dates": "Sep 2024 - Jun 2025",
            "accomplishments": [
                "Produced a real-time data pipeline utilizing Node.js and MongoDB to process streaming data, ensuring 99.9% uptime for 5,000 concurrent users, and optimized data output by 35%.",
                "Constructed a personalized recommendation engine utilizing behavioral data; refined algorithms weekly, leading to a 12% increase in content click-through rates and reduced user churn.",
                "Led the development of an NLP chatbot that analyzed user input, pinpointing the top three user interface pain points, and driving a 15% increase in positive user satisfaction.",
            ],
        },
        {
            "company": "Jetson Infinity",
            "role": "AI/ML Engineering Apprentice",
            "location": "Austin, Texas",
            "dates": "Jul 2024 - Aug 2024",
            "accomplishments": [
                "Implemented a Python-based data processing pipeline leveraging Pandas and NumPy, resulting in a 3% refinement in robotic arm precision and enhanced workflow efficiency by 10%.",
                "Automated data pipeline for robotic arm motion data employing Python and SQL, enhancing data processing efficiency by 17% and enabling real-time anomaly detection and faster analysis.",
                "Devised an internal knowledge base with Python tutorials and real-world case studies, accelerating new data analyst onboarding by 25% and improving team proficiency in Python.",
            ],
        },
        {
            "company": "Kronic Keys",
            "role": "Data Analyst",
            "location": "Junagadh, Gujarat",
            "dates": "Aug 2021 - Mar 2022",
            "accomplishments": [
                "Cleaned and prepared large datasets (500k+ rows), leading to more accurate sales and customer behavior insights and reducing reporting time by 30%.",
                "Built SQL queries and Tableau dashboards that improved sales reporting efficiency by 30%.",
                "Developed and maintained Tableau dashboards that visualized key sales performance indicators, helping drive a 12% increase in customer acquisition; dashboards were built using data extracted from PostgreSQL.",
            ],
        },
    ],
    "projects": [
        {
            "name": "Job Search CRM & AI Application Tailoring Center",
            "dates": "Feb 2026 – Present",
            "accomplishments": [
                "Full Stack Command Center: Local job placement command center with FastAPI, Python, Jinja2, and TailwindCSS UI, tracking applications, recruiter outreach, and resume versions.",
                "AI Prompt Tailoring Engine: Integrated OpenAI API prompt tailoring chains to automatically align candidate resumes with specific job description keywords, plus a standalone ReAct-pattern research agent with real tool-calling over the app's own data.",
                "Relational Database & ORM: Deployed a local SQLite database using SQLAlchemy ORM to manage application logs, recruiter follow-ups, and interview stages, backed by a GitHub Actions CI pipeline running 690+ pytest cases on every push.",
                "Automated Document Compiler: Built automated Python PDF compilation scripts with headless Edge printing to generate perfectly formatted 2-page resumes and 1-page cover letters, containerized with Docker for reproducible deployment.",
            ],
        },
        {
            "name": "CurioSync: Serverless Tech News & LinkedIn Publisher",
            "dates": "Apr 2026 – Jun 2026",
            "accomplishments": [
                "Serverless Automation Pipeline: Scheduled serverless news curation and publisher pipeline running on GitHub Actions cron workflows (100% hosting cost reduction).",
                "Glassmorphic Administrative Panel: Designed a Jinja2/HTMX control panel secured by Fernet symmetric encryption to protect user credentials with zero compliance leakage.",
                "LLM & Image Generation: Integrated Gemini LLM chains and developed custom Pillow image-processing engines to automatically render branding graphics (+150% engagement).",
                "Vector RAG Embeddings: Implemented pgvector semantic search and RAG retrieval pipelines to contextualize daily technical news articles automatically.",
            ],
        },
        {
            "name": "Member Messages QA System: Semantic Search & NER-Based Question Answering",
            "dates": "Oct 2025 – Nov 2025",
            "accomplishments": [
                "Semantic Search QA Engine: Built an interactive /ask API answering natural-language questions about member data, ranking unstructured messages by cosine similarity over SentenceTransformer (all-MiniLM-L6-v2) embeddings.",
                "Named Entity Recognition: Integrated spaCy NER with fuzzy first-name matching to identify a question's subject before ranking relevant messages.",
                "Dynamic Information Extraction: Implemented regex-based extraction for contact info, numeric quantities, and companion/group references from unstructured message text, with fallback to the closest-matching message when no structured answer applies.",
                "Architecture Tradeoff Analysis: Evaluated and documented five candidate approaches (rule-based matching, knowledge graphs, fine-tuned LLMs, hybrid retrieval) before selecting embeddings-based semantic search for its balance of speed, accuracy, and maintainability.",
                "LlamaIndex Retrieval Path: Built an alternative semantic-search retriever using LlamaIndex's VectorStoreIndex over the same embedding model, verified against the real message dataset.",
                "Semantic Kernel Orchestration: Wrapped the NER/ranking/extraction functions as native Semantic Kernel plugin functions, orchestrated through a real Kernel instance.",
                "Real RAG Pipeline: Built a genuine retrieve-then-generate RAG chain with LangChain, generating natural-language answers grounded in retrieved messages via a local model -- verified with both fast deterministic wiring tests and a real end-to-end generation test.",
            ],
        },
        {
            "name": "TalentVenue EventIntel: Enterprise Data Platform & Predictive Intelligence",
            "dates": "Aug 2025 – Nov 2025",
            "accomplishments": [
                "Enterprise Cloud Platform: Connected SQL Server, Azure ADLS Gen2, Snowflake, and Streamlit, accelerating financial queries by 45% and achieving 100% payment reconciliation accuracy.",
                "Interactive Multi-Page Web UI: Built a multi-page web application using Python and Streamlit, delivering intuitive event data visualization components.",
                "Predictive Contract Risk Model: Deployed a Random Forest model predicting contract cancellation risk with 86.20% accuracy (0.87 ROC-AUC), served via a Snowflake Python UDF for real-time inference directly from SQL.",
                "Infrastructure as Code: Provisioned the production data warehouse -- Azure ADLS Gen2 storage, Snowflake database/schemas/warehouse, and the storage integration connecting them -- via Terraform.",
                "Table Format Layer: Loaded staged extracts into real Delta Lake and Apache Iceberg tables (native deltalake library and pyiceberg's SQL catalog) as a transactional consumption layer over the raw Parquet staging area.",
                "Data Contract Validation: Built a TypeScript CLI (zod schema validation, Node's test runner) that verifies the ML pipeline's feature-mappings artifact before the dashboard relies on it for inference.",
                "CI/CD Pipeline: Authored a Jenkins declarative pipeline (per-stage Docker agents) mirroring the existing GitHub Actions CI, verified against a real temporary Jenkins instance -- found and fixed two real environment bugs (Docker socket group permissions, a missing system ODBC library) surfaced only by actually running it.",
            ],
        },
        {
            "name": "AI Model Observability & Fairness Audits",
            "dates": "Nov 2025 – Feb 2026",
            "accomplishments": [
                "MLOps Drift Monitoring: Audits machine learning models in production by running Kolmogorov-Smirnov (KS) tests and Population Stability Index (PSI) to monitor feature drift (-35% silent drift).",
                "Bias & Fairness Auditing: Evaluates demographic parity and Equal Opportunity bias metrics in compliance with high-risk AI regulatory frameworks (EU AI Act, US FTC).",
                "Compliance Reporting: Deployed SQLite audit logging with automated compliance reporting, visualized in a real, published interactive Tableau dashboard (public.tableau.com/app/profile/deshraj.jogiya/viz/AIModelObservabilityFairnessAuditDashboard) -- a live log-scale drift-trend chart plus a real subgroup fairness comparison over 30,000 simulated inference records.",
                "Model Quality Guardrails: Implemented automated data validation checks that trigger alerts when input distributions diverge from training baselines.",
                "Population Stability Index: Added a decile-binned PSI drift metric alongside the existing KS test, verified against real audit data -- PSI stays under 0.05 on stable days and climbs past 0.25 exactly where the KS p-value collapses, tracking the same real drift.",
            ],
        },
        {
            "name": "FinTech Credit Risk & Fraud Command Center",
            "dates": "Oct 2025 – Dec 2025",
            "accomplishments": [
                "Low-Latency API Pipeline: Engineered an end-to-end credit risk evaluation pipeline using FastAPI and Python, achieving sub-100ms API response latency for real-time validation.",
                "Machine Learning Risk Classifier: Trained and benchmarked XGBoost against a Random Forest ensemble in Scikit-Learn to predict loan default probability, selecting Random Forest for production with a 92% precision score, tracked in MLflow for experiment comparison.",
                "Interactive Chart.js Dashboard: Developed SQLite schemas and transactional fraud anomaly checks with Chart.js dashboard integration to streamline credit approval cycles.",
                "Real-Time Anomaly Flagging: Embedded automated rules checking transaction velocity and amount spikes to prevent fraudulent loan approvals.",
                "GraphQL API Layer: Added a Strawberry-GraphQL query layer alongside the existing REST endpoints, serving customer and loan data from the same database.",
            ],
        },
        {
            "name": "Sentence Transformers, Multi-Task Learning & LLM Fine-Tuning",
            "dates": "Apr 2025 – Sep 2026",
            "accomplishments": [
                "Sentence Transformer Architecture: Built a Sentence Transformer using a Small BERT model from TensorFlow Hub, encoding sentences into 128-dimensional contextual embeddings via mean pooling across token representations.",
                "Multi-Task Learning Expansion: Extended the shared transformer backbone with two task-specific heads (3-class sentence classification, 2-class sentiment classification), each with its own softmax output layer.",
                "Transfer Learning Strategy: Evaluated freezing strategies (full model vs. backbone-only vs. single task head) and proposed a staged fine-tuning approach -- freeze lower layers, fine-tune top layers and task heads.",
                "Training Loop Simulation: Simulated multi-task training with synthetic text and one-hot encoded labels via model.fit(), logging per-task loss and accuracy to validate the architecture end-to-end.",
                "Real LoRA Fine-Tuning: LoRA fine-tuned Qwen2.5-0.5B-Instruct on a real Databricks Dolly-15k subset (free Colab T4 GPU), with a real declining loss curve over 3 epochs and an honest before/after comparison on held-out prompts.",
            ],
        },
        {
            "name": "Multi-State Land Use Emissions Analysis",
            "dates": "Apr 2025 – Nov 2025",
            "accomplishments": [
                "Geospatial ETL Pipeline: Engineered a Python-based ETL pipeline processing daily land cover datasets across 5 U.S. states, saving 10 hours of manual preparation weekly.",
                "Emissions Predictive Forecasting: Centralized data in SQLite database tracking land-use shifts and built regression forecasts (Random Forest/Linear Regression) achieving 90% accuracy.",
                "ArcGIS Stakeholder Dashboards: Developed interactive ArcGIS Dashboards for regional stakeholder reporting, reducing anomaly detection times by 15%.",
                "Geospatial Aggregations: Applied spatial join transformations to correlate satellite land cover changes with regional greenhouse gas emissions inventories.",
            ],
        },
        {
            "name": "Tax Anomaly Audit Compliance Engine",
            "dates": "Sep 2025 – Oct 2025",
            "accomplishments": [
                "General Ledger Audit Pipeline: Engineered an automated compliance audit pipeline in Python and SQL to ingest and validate general ledger transaction logs (-40% data preparation time), orchestrated as a Dagster asset graph.",
                "Statistical & ML Anomaly Detection: Implemented Benford's Law distribution modeling and an unsupervised Isolation Forest anomaly detection algorithm to flag high-risk transactions (94% precision).",
                "Power BI Compliance Dashboard: Deployed interactive Power BI dashboards visualizing risk scores and transaction anomalies, accelerating audit review cycles by 25%.",
                "Lineage & Audit Control: Enforced strict data lineage logging and schema validation rules across enterprise financial audit records.",
            ],
        },
        {
            "name": "Automated Daily Data Insights",
            "dates": "Feb 2025 – Mar 2025",
            "accomplishments": [
                "Stateless Serverless ETL: Wrote Python scripts to fetch market and telemetry datasets from yFinance APIs with automated error handling and logging.",
                "Statistical Anomaly Detection: Programmed rolling statistical Z-score algorithms to detect price anomalies, triggering automated email alerts and report updates.",
                "Cron Schedule Uptime: Configured GitHub Actions to run the pipeline daily on cron schedules, achieving 99.9% uptime with $0 operational server cost.",
                "Automated Data Quality Validation: Embedded input data validation checks to prevent missing market records from corrupting downstream report charts.",
            ],
        },
        {
            "name": "Sales Analytics & RFM Customer Segmentation Pipeline",
            "dates": "Dec 2024 – Jan 2025",
            "accomplishments": [
                "Star Schema Database: Designed and implemented a SQL database with an optimized Star Schema modeling 100k+ customer transactions for business intelligence reporting.",
                "RFM & K-Means Clustering: Automated RFM scaling and unsupervised K-Means clustering in Python, identifying 4 customer personas capturing 92% of variance.",
                "Executive Power BI Dashboard: Built a real, interactive Power BI report with star-schema relationships and DAX measures over the pipeline live CSV exports -- including a K-Means cluster scatter plot and a persona slicer for marketing teams.",
                "Pareto 80/20 Insights: Applied Pareto analysis to isolate top-tier revenue generating customer segments for targeted retention campaigns.",
            ],
        },
        {
            "name": "Clinical Trials Patient Outcomes Analysis",
            "dates": "Oct 2024 – Nov 2024",
            "accomplishments": [
                "Clinical Data Ingestion Pipeline: Developed a secure clinical trials data ingestion pipeline in SQL/Python to clean and track patient survival, vital signs, and dosage levels.",
                "Biostatistical Survival Modeling: Conducted survival analysis using Kaplan-Meier curves and computed Log-Rank test statistics in SciPy to evaluate treatment efficacy across 3 cohorts.",
                "Tableau Research Reporting: Authored Tableau reports showcasing patient outcomes and statistical significance, improving decision reporting speed for researchers by 30%.",
                "HIPAA Data Anonymization: Enforced data privacy transformations to mask patient personal identifiable information (PII) across analytical schemas.",
            ],
        },
        {
            "name": "Real-Time IoT Telematics & Predictive Maintenance",
            "dates": "Jul 2024 – Sep 2024",
            "accomplishments": [
                "High-Frequency Telemetry Ingestion: Engineered a streaming simulation pipeline in Python to ingest high-frequency EV battery and motor telemetry sensor logs in micro-batches.",
                "Anomaly Detection & Device Health: Applied rolling statistical Z-score algorithms on sensor metrics to flag real-time anomalies and prevent device failures.",
                "Degradation & RUL Modeling: Implemented degradation modeling using exponential decay equations to estimate battery Remaining Useful Life (RUL) with Power BI dashboard tracking.",
                "Automated Alert Triggering: Integrated real-time threshold monitoring to broadcast predictive maintenance alerts before component breakdown.",
                "Jax-Accelerated Recurrence: Reimplemented the sequential health-decay/RUL calculation as a single JIT-compiled jax.lax.scan, verified numerically identical to the original per-row implementation.",
            ],
        },
        {
            "name": "AI-ML Data Science Simulation",
            "dates": "Apr 2024 – Jun 2024",
            "accomplishments": [
                "Multi-Branch ETL Automation: Created a scalable data automation system utilizing Python for daily sales data ingestion from 5 branches across states, simulating a real ETL pipeline.",
                "Inventory Centralization & Tableau: Centralized inventory datasets in SQL and visualized trend cycles in Tableau, driving actionable insights across weekly and monthly cycles.",
                "Predictive Inventory Forecasting: Deployed machine learning models (Linear Regression, Random Forest) achieving 90% forecast accuracy and enabling a 15% reduction in stock-outs.",
                "Automated Data Reconciliation: Built daily automated cross-branch data reconciliation checks to ensure dataset consistency across regional store databases.",
            ],
        },
        {
            "name": "Extending STEM across ASL",
            "dates": "Apr 2023 – Mar 2024",
            "accomplishments": [
                "Deep Learning Web Application: Pioneered an inclusive Python web platform leveraging TensorFlow, PyTorch, Keras, and Flask, making 7 STEM concepts accessible to ASL users.",
                "Gesture Recognition Algorithm: Implemented a sign recognition algorithm leveraging CNN models and contour geometry, cutting gesture redundancy and boosting learning efficiency by 30%.",
                "User Feedback & Evaluation: Synthesized feedback from 50+ STEM students, achieving a user satisfaction score of 4.6/5 based on post-lesson survey evaluations.",
                "Real-Time Video Frame Processing: Optimized OpenCV frame capture and pre-processing steps for low-latency web browser sign gesture classification.",
            ],
        },
        {
            "name": "Solid Object Detection & Identification",
            "dates": "May 2020 – Dec 2020",
            "accomplishments": [
                "Computer Vision & Geometry Pipeline: Developed a shape detection and identification pipeline using PyTorch, OpenCV, and custom CNN models.",
                "High Classification Accuracy: Achieved 98.97% classification accuracy on a 10,000+ image dataset, combining deep learning with traditional contour geometry approximations.",
                "Visualization Enhancements: Implemented visual bounding boxes and shape classification overlays, increasing visualization capabilities by 33%.",
                "Contour Analysis & Preprocessing: Applied Gaussian blurring and Canny edge detection in OpenCV to extract robust shape boundary features prior to neural network classification.",
                "Real-Time Serverless Inference: Deployed the trained model as a live AWS Lambda function triggered by real S3 image uploads -- exported to ONNX (~615KB) so it ships as a plain Lambda zip via onnxruntime, avoiding a PyTorch container image and its ECR storage cost. Verified end-to-end with a real live S3-to-Lambda integration test running in CI against the actual deployed AWS infrastructure.",
            ],
        },
        {
            "name": "Reactive Job Ingest Gateway",
            "dates": "Sep 2026",
            "accomplishments": [
                "Non-Blocking Ingestion API: Built a Spring WebFlux REST endpoint that persists incoming job-posting events via R2DBC without blocking a thread per request.",
                "Live SSE Stream: Republished ingested postings as a real-time Server-Sent-Events stream using a replaying Sinks.Many, so a client connecting mid-stream still sees recent history before live updates.",
                "Verified End-to-End: Packaged and ran the real application, hitting it with live curl requests (including a real SSE subscriber receiving an event ingested after it connected) -- found and fixed two real bugs surfaced only by running it, not just the test suite.",
            ],
        },
        {
            "name": "Job Search dbt Warehouse",
            "dates": "Sep 2026",
            "accomplishments": [
                "Dimensional Data Model: Built a dbt project (staging views into dimension and fact tables) on a live Databricks SQL warehouse, including a datediff-based days-to-decision measure and a row_number() window function for interview-round sequencing.",
                "Data Quality Testing: Wrote 15 dbt tests (uniqueness, not-null, referential integrity, accepted values) across the model, all passing against the real warehouse in CI.",
                "Verified End-to-End: Ran dbt seed/run/test against a live Databricks warehouse (not just parsed) and spot-checked the resulting tables by hand; CI re-runs the same three commands against the same warehouse on every push using repository secrets.",
            ],
        },
        {
            "name": "Job Market Lakehouse",
            "dates": "Sep 2026",
            "accomplishments": [
                "PySpark Transformation Pipeline: Built a real PySpark job over 60k synthetic postings -- a join, a groupBy/agg salary-stats aggregation, and a dense_rank() window function ranking postings within each industry.",
                "Scala Spark Job: Wrote a complementary Scala Spark SQL job (monthly posting-volume-by-source aggregation), run via spark-shell against a real Spark distribution.",
                "Data Quality Gating: Wrote 11 real Great Expectations checks (row counts, categorical sets, uniqueness, a cross-column comparison) validating the PySpark output.",
                "Pipeline Orchestration: Built a real Airflow DAG (generate -> transform -> validate) verified end-to-end via `airflow dags test` -- fixed a real pydantic/typing_extensions dependency conflict by isolating Airflow's own environment from the pipeline's.",
            ],
        },
        {
            "name": "Job Notes",
            "dates": "Sep 2026",
            "accomplishments": [
                "Express + MongoDB API: Built a real REST API (Express, Mongoose) for company-research notes, backed by a real MongoDB instance -- 4 integration tests (Jest + Supertest) against a real database, not a mock.",
                "Angular Frontend: Built a real Angular app (generated via the official CLI) fetching, creating, and deleting notes against the API, with 3 real TestBed + HttpClientTestingModule tests.",
                "Verified End-to-End: Both the real API and the real Angular test suite pass in CI; fixed a real bug (Puppeteer's Chromium has no arm64 Linux build) by switching to a system Chromium install.",
            ],
        },
        {
            "name": "Interview Prep API",
            "dates": "Sep 2026",
            "accomplishments": [
                "Minimal API: Built a real ASP.NET Core minimal API (C#) for browsing/adding interview questions, backed by Entity Framework Core + SQLite.",
                "Real Data Access: EF Core-managed schema and seeding, with filtering and a random-pick endpoint over real queries.",
                "Verified End-to-End: 5 real xUnit integration tests (WebApplicationFactory + a real in-memory SQLite connection) plus a hand-run curl verification against the live app -- all passing.",
            ],
        },
        {
            "name": "Company Blocklist",
            "dates": "Sep 2026",
            "accomplishments": [
                "CodeIgniter 4 App: Built a real PHP/CodeIgniter 4 app tracking companies to avoid in a job search, with a real migration, model (including a real is_unique validation rule), and controller.",
                "Verified End-to-End: 5 real feature tests (FeatureTestTrait + DatabaseTestTrait) hitting real routes through the real router/controller/model stack against a real SQLite database.",
                "Found and fixed two real CodeIgniter testing gotchas: DatabaseTestTrait's namespace defaulting to test-support fixtures only, and assertJSONFragment not doing nested matching against list responses.",
            ],
        },
        {
            "name": "Interview Prep Mobile",
            "dates": "Sep 2026",
            "accomplishments": [
                "React Native App: Built a real Expo app browsing/practicing interview-prep questions against a companion ASP.NET Core API, with local persistence via AsyncStorage.",
                "Verified End-to-End: Real React Native Testing Library tests, plus a full live integration check -- a real Metro web export served over nginx, loaded in real headless Chromium on the same Docker network as the real running API, confirming correct data end-to-end with zero console errors.",
                "Found and fixed two real bugs: AsyncStorage needing an explicit jest.mock() (not just the package installed), and Hermes' bytecode compiler having no arm64 Linux build -- documented transparently rather than skipped.",
            ],
        },
        {
            "name": "Company Search (HTMX)",
            "dates": "Sep 2026",
            "accomplishments": [
                "Live Search UI: Built a real live-search page using HTMX for partial-page updates (FastAPI + Jinja2 rendering real HTML, no client-side JS framework).",
                "Verified End-to-End: 5 real FastAPI TestClient tests, plus a full live interaction check with a real headless-Chromium session driving the actual running app.",
                "Found and fixed a real bug the TestClient tests couldn't catch: hx-trigger's keyup-only binding never fired for autofill/paste, only real keystrokes -- fixed to an input-based trigger and re-verified live.",
            ],
        },
        {
            "name": "ArcGIS Commute Insights",
            "dates": "Sep 2026",
            "accomplishments": [
                "Real Geocoding: Built a job-search tool geocoding home/company addresses via the live ArcGIS World Geocoding Service, ranking companies by real great-circle distance.",
                "Real Basemap Vector Tiles: Fetched and decoded real Mapbox Vector Tile (.pbf) data from Esri's World Basemap v2 service -- the tile URL template was discovered by reading the real basemap style JSON's sources, not assumed from docs, after an initial guessed URL returned a real 404.",
                "Verified End-to-End: All 7 tests hit the real ArcGIS APIs (no mocks) -- including a hand-verified slippy-map tile coordinate and assertions on real observed basemap layer names.",
            ],
        },
    ],
}


def get_resume_context() -> str:
    """Format the resume data as context for LLM prompting."""
    lines = []
    lines.append("USER PROFILE SUMMARY:")
    lines.append(RESUME_DATA["summary"])
    lines.append("\nEDUCATION:")
    for edu in RESUME_DATA["education"]:
        lines.append(
            f"- {edu['degree']} from {edu['institution']} ({edu['dates']}) - GPA: {edu['gpa']}"
        )
    lines.append("\nTECHNICAL SKILLS:")
    for category, skills in RESUME_DATA["skills"].items():
        lines.append(f"- {category.replace('_', ' ').title()}: {', '.join(skills)}")
    lines.append("\nPROFESSIONAL EXPERIENCE:")
    for exp in RESUME_DATA["experience"][:4]:  # limit to top 4 for token efficiency
        lines.append(f"- {exp['role']} at {exp['company']} ({exp['dates']})")
        for acc in exp["accomplishments"]:
            lines.append(f"  * {acc}")
    lines.append("\nACADEMIC / PERSONAL PROJECTS:")
    # Limit to the most recent projects, same reasoning as the experience cap above:
    # dumping all 25 projects' full bullet lists (~6k tokens) into every prompt diluted
    # the model's focus and plausibly contributed to it inventing figures (like "five
    # years of experience") not actually present anywhere in this context.
    for proj in RESUME_DATA["projects"][:6]:
        lines.append(f"- {proj['name']} ({proj['dates']})")
        for acc in proj["accomplishments"]:
            lines.append(f"  * {acc}")
    return "\n".join(lines)
