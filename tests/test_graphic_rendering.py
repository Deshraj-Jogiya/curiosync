import sys
import os

# Add G:\Linkedin post writer to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from app.services.image_service import generate_linkedin_image

def test_render():
    print("Testing infographic diagram rendering...")
    
    # 1. Flowchart metadata
    flowchart_meta = {
        "type": "flowchart",
        "title": "Scalable Daily Data Pipeline Process",
        "steps": [
            {"num": "1", "title": "Data Ingestion", "desc": "Process incoming segment batches from regional branches"},
            {"num": "2", "title": "Great Expectations", "desc": "Validate data against 98% reliability constraints"},
            {"num": "3", "title": "Tableau BI Sync", "desc": "Sync clean metrics with dashboards to reduce stock-outs"}
        ]
    }
    
    # 2. Comparison metadata
    comparison_meta = {
        "type": "comparison",
        "title": "Predictive Modeling Comparison Matrix",
        "headers": ["Framework", "Accuracy Target", "Deployment Latency"],
        "rows": [
            ["Random Forest", "92% Precision", "Batch (Moderate)"],
            ["Linear Regression", "90% R2 Score", "Real-time (Ultra Low)"],
            ["LSTM Time Series", "88% Accuracy", "Micro-batch (High)"]
        ]
    }
    
    # 3. Architecture metadata
    architecture_meta = {
        "type": "architecture",
        "title": "Technoid LLC Model Recommender Setup",
        "nodes": [
            {"id": "n1", "label": "Regional Branches"},
            {"id": "n2", "label": "FastAPI ETL Ingestion"},
            {"id": "n3", "label": "PostgreSQL (Supabase)"},
            {"id": "n4", "label": "OpenAI LLM recommendation"}
        ],
        "connections": [
            ["n1", "n2"],
            ["n2", "n3"],
            ["n3", "n4"]
        ]
    }
    
    print("Rendering flowchart...")
    img1 = generate_linkedin_image(flowchart_meta, subtitle="Technical Pipeline Workflow")
    print(f"Generated Flowchart: {img1}")
    
    print("Rendering comparison...")
    img2 = generate_linkedin_image(comparison_meta, subtitle="Framework Comparison Matrix")
    print(f"Generated Comparison: {img2}")
    
    print("Rendering architecture...")
    img3 = generate_linkedin_image(architecture_meta, subtitle="System Architecture Setup")
    print(f"Generated Architecture: {img3}")
    
    print("All renders completed successfully!")

if __name__ == "__main__":
    test_render()
