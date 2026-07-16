"""Resume service containing structured resume info for LLM prompting."""

RESUME_DATA = {
    "summary": (
        "Research-focused data/ML engineer with over five years of extensive experience "
        "delivering ETL automation (70% efficiency gains), AI model optimization (25% accuracy boosts), "
        "and cloud data pipelines across research and industry roles. Expertise in "
        "Python/SQL/PostgreSQL, OpenAI APIs, Supabase/AWS/Snowflake, and ML techniques from "
        "K-Means clustering to NLP systems. ASU research alum and IBM certified, "
        "currently engineering real-time ML solutions at Technoid LLC."
    ),
    "education": [
        {
            "institution": "Arizona State University",
            "degree": "Master of Science, Information Technology",
            "dates": "Aug 2022 - May 2024",
            "gpa": "4.0/4.0",
            "location": "Tempe, AZ",
        },
        {
            "institution": "Institute of Advanced Research",
            "degree": "Bachelor of Technology, Computer Engineering",
            "dates": "Aug 2017 - May 2021",
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
            "dates": "May 2026 - Present",
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
            "dates": "Dec 2025 - May 2026",
            "accomplishments": [
                "Optimized GPT-4o mini models for resume analysis/tailoring using OpenAI APIs, SQL, and PostgreSQL, improving recommendation accuracy by 25%.",
                "Established Supabase data sync with RLS fixes and PostgreSQL backend, reducing data sync latency by 65% for real-time operations.",
                "Produced phased regression and UAT testing frameworks, cutting model deployment errors by 30%.",
            ],
        },
        {
            "company": "ElevateMe Bootcamp",
            "role": "Data Analytics & Machine Learning Fellow Trainee",
            "location": "Columbus, Ohio",
            "dates": "Jan 2025 - Mar 2026",
            "accomplishments": [
                "Analyzed company financial and operational data with Python and Excel, identifying 4 key revenue-impacting trends that guided department-level strategic actions.",
                "Deployed interactive Power BI dashboards to visualize KPIs and financial trends, improving executive insight and reporting efficiency.",
                "Led customer segmentation using K-Means clustering and PCA for dimensionality reduction, visualized results in Power BI, and identified six segments that captured 92% of data variance.",
                "Led marketing intelligence strategy using classification models and Power BI analytics, increasing campaign click-through rates by 12%.",
            ],
        },
        {
            "company": "Zifatech Solutions LLC",
            "role": "Data Analyst",
            "location": "Milwaukee, Wisconsin",
            "dates": "Jun 2025 - Dec 2025",
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
            "role": "AI-ML Analyst Apprentice",
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
            "name": "Multi-State Land Use Emissions Analysis",
            "dates": "Apr 2025 - Nov 2025",
            "accomplishments": [
                "Engineered Python ETL pipeline for daily land cover datasets from 5 U.S. states, automating emissions inventory compilation with geospatial data transformations, saving 10 hours weekly.",
                "Centralized SQL database tracking land use changes (e.g., urban expansion, forest loss); Improved Linear Regression/Random Forest forecasts achieving 90% accuracy for CO2 trends.",
                "Authored an ArcGIS Dashboard for interactive visualization of land cover shifts and emission summaries across regional scales, reducing anomaly detection time by 15%.",
            ],
        },
        {
            "name": "AI-ML Data Science Simulation Project",
            "dates": "Apr 2024 - Jun 2024",
            "accomplishments": [
                "Created a scalable data automation system imposing Python for daily sales data ingestion from 5 branches across states, simulating a real ETL pipeline.",
                "Centralized inventory data implementing SQL and visualized trends in Tableau, driving actionable insights across weekly and monthly cycles.",
                "Operated machine learning models (e.g., Linear Regression, Random Forest) that achieved 90% forecast accuracy and enabled a 15% reduction in stock-outs.",
            ],
        },
        {
            "name": "Extending STEM across ASL",
            "dates": "Apr 2023 - Mar 2024",
            "accomplishments": [
                "Pioneered an inclusive Python platform leveraging TensorFlow and Keras, enabling 7 previously inaccessible STEM concepts to users with and without ASL proficiency.",
                "Implemented a novel search functionality and sign recognition algorithm cannibalizing Python, cutting gesture redundancy, boosting learning efficiency by 30%, and presented to the Department Head.",
                "Synthesized feedback from 50+ STEM students to identify key areas to improve lesson design, achieving a user satisfaction score of 4.6/5, based on post-lesson surveys.",
            ],
        },
        {
            "name": "Stay Aware of Branch",
            "dates": "Jul 2023 - Dec 2023",
            "accomplishments": [
                "Developed an application that links parents and schools through the React Native Android framework.",
                "Improved communication between parents and teachers, leading to a 40% boost in parent involvement.",
                "Implementing features such as integrated progress reports and attendance monitoring decreased the 25% administrative workload.",
            ],
        },
        {
            "name": "Chef at Gathering",
            "dates": "Nov 2022 - Mar 2023",
            "accomplishments": [
                "Developed a React app easing event organization and professional catering arrangements.",
                "Streamlined event management processes, resulting in a 50% reduction in coordination time.",
                "Curated chefs to showcase specialties, leading to a 20% increase in chef bookings.",
            ],
        },
        {
            "name": "City Forums",
            "dates": "Jun 2022 - Oct 2022",
            "accomplishments": [
                "Created an online forum using CodeIgniter 3, promoting community engagement and event sharing.",
                "Increased user base by 50% within the first three months through targeted marketing strategies.",
                "Established a thriving online marketplace generating $10,000 in revenue through classified advertisements and event listings.",
            ],
        },
        {
            "name": "Make It Short",
            "dates": "Jan 2022 - Apr 2022",
            "accomplishments": [
                "Integrated Link Shortening and view tracking into a CodeIgniter 4 app, resulting in 10,000+ shortened URLs.",
                "Achieved a 15% increase in user engagement by implementing gamification elements.",
                "Generated $500 in revenue through redeemable points earned by users.",
            ],
        },
        {
            "name": "Get your Token",
            "dates": "Jul 2021 - Dec 2021",
            "accomplishments": [
                "Published a front-end marketplace and administrative panel for NFT cryptocurrency transactions by reducing the time by 20%.",
                "Facilitated the creation and purchase of Penky tokens, resulting in 1,000+ transactions within the first month.",
                "Collaborated with stakeholders to meet project requirements, resulting in a 90% satisfaction rate among users and developers.",
            ],
        },
        {
            "name": "Solid Object Detection and Identification using Image Processing",
            "dates": "May 2020 - Dec 2020",
            "accomplishments": [
                "Developed a robust shape detection and identification algorithm using Python, PyTorch, and OpenCV, achieving a classification accuracy of 99.20%.",
                "Implemented traditional contour-based geometry feature extraction alongside a CNN classifier, refining shape recognition with a 33% increase in traditional visualization capabilities.",
                "Evaluated the model over a dataset of 10,000 images, predicting bounding-box regression with a high-precision Mean IoU of 0.90.",
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
    for proj in RESUME_DATA["projects"]:
        lines.append(f"- {proj['name']} ({proj['dates']})")
        for acc in proj["accomplishments"]:
            lines.append(f"  * {acc}")
    return "\n".join(lines)
