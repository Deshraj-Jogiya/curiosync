# ⚡ CurioSync: Serverless Tech News & LinkedIn Publisher

CurioSync is a production-ready, self-hosted Python/FastAPI automation system that curates the day's top tech stories, programmatically renders high-engagement visual branding card graphics, and drafts LinkedIn posts that are published only after the owner approves each one.

Designed for engineering leaders and content creators, it operates **100% free of hosting costs** using a stateless GitHub Actions runner and an in-memory SQLite database, eliminating the need to maintain a persistent 24/7 server.

---

## 🚀 Key Features

* **Serverless Drafting with Human Approval** — A free GitHub Actions schedule drafts three posts a week (Monday project breakdown, Wednesday news take, Friday engineering lesson); each waits on a required-reviewer environment and is posted only when approved, since LinkedIn's API terms do not allow unattended automated posting. An in-memory database keeps runs stateless.
* **Smart Content Curation** — Fetches top stories across 6 major tech RSS streams (TechCrunch, Ars Technica, Wired, BBC Tech, etc.) and deduplicates near-identical articles using fuzzy title comparison (SequenceMatcher).
* **Profile-Grounded Writing** — Every fact in a post comes from the live portfolio's `projects.json`, which is regenerated from the master profile, so posts never drift from the resume. Subjects rotate weekly; team projects are never featured as solo work.
* **Programmatic Diagram Graphic** — Uses Pillow to dynamically analyze post context and render a custom, high-engagement technical diagram (flowchart, comparison grid, or systems architecture map) complete with your branding and credentials.
* **Jinja2 + HTMX Local Dashboard** — A premium glassmorphism command center for local review, manual draft edits, real-time visual graphic previews, and direct publishing.
* **Compliance & Humanizer** — Removes filler phrases and in-body links, corrects tenure claims, and blocks any draft with a link, a self-reference to automation, credential or scraping language, or text over LinkedIn's limit.

---

## 🛠️ Architecture & Tech Stack

```mermaid
graph TD
    A[RSS News Sources] --> B[CurioSync Engine]
    B --> D[Deduplication & Credibility Filter]
    D --> E[Gemini API Fallback Chain]
    E --> F[AI Narrative Synthesis]
    F --> G[Pillow Diagram Rendering Engine]
    G --> K[Owner approval in GitHub]
    K --> H[LinkedIn API Publishing]
    
    subgraph Cloud Automation
        I[GitHub Actions Cron] -->|Sees environment secrets| B
    end
    
    subgraph Local Control
        J[Jinja2 + HTMX Web UI] -->|Direct Manual Edits| G
    end
```

| Component | Technology |
|---|---|
| **Language & Framework** | Python 3.11+, FastAPI |
| **Frontend Integration** | Jinja2 Templates, HTMX, Vanilla CSS (Glassmorphism) |
| **Database** | SQLite (async via aiosqlite), SQLAlchemy 2.0 ORM |
| **Asset Engine** | Pillow (PIL) for diagram/infographic generation |
| **Security & OAuth** | Cryptography (Fernet symmetric encryption), LinkedIn OAuth 2.0 |
| **Quality Verification** | pytest, pytest-asyncio (102 tests) |

---

## 📦 Setup & Installation

### 1. Local Development Setup
Clone the repository and install the dependencies inside a Python virtual environment:
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your actual credentials:
```bash
copy .env.example .env
```
Generate your Fernet encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Start the Web App
Run the local FastAPI server using Uvicorn:
```bash
uvicorn app.main:app --reload
```
Open **[http://localhost:8000](http://localhost:8000)** to connect your LinkedIn profile, fetch today's headlines, customize your posts, and see your graphic previews in real time.

---

## ☁️ Setting Up GitHub Actions (Free Cloud Execution)

You do not need to host a database or keep your personal computer turned on. Run the publisher daily on GitHub's free runners:

1. **Get Credentials from Local Dashboard:** 
   Start your local server, authenticate with LinkedIn, expand the **🚀 Deploy to GitHub Actions (Free)** accordion, and copy:
   * `LINKEDIN_SUB_URN`
   * `LINKEDIN_ACCESS_TOKEN`
2. **Add Repository Secrets to GitHub:**
   In your repository page, navigate to **Settings > Secrets and variables > Actions** and add these secrets:
   * `LINKEDIN_SUB_URN` (Pasted Sub URN)
   * `LINKEDIN_ACCESS_TOKEN` (Pasted token)
   * `GEMINI_API_KEY` (Your Google AI Studio API Key)
3. **Trigger workflow:**
   The action is configured in `.github/workflows/daily_post.yml` to run daily at **13:00 UTC (6:00 AM MST / America/Phoenix timezone)**. You can also manually trigger it by clicking **Run workflow** under the repository's **Actions** tab.
4. **Create the approval environment:**
   Under **Settings > Environments**, create `linkedin-publish` and add yourself as a required reviewer. Create it before the first run: a job that names a missing environment creates it without protection. On post days GitHub emails a review request; the draft text is on the run's summary page. Approve to post it unchanged, or reject to skip. Drafts older than 36 hours are not posted.

> [!IMPORTANT]
> **Token Expiry Notice:**
> LinkedIn access tokens expire every 60 days. Once every 2 months, run the local app, log in to refresh, copy the new token from the dashboard, and update `LINKEDIN_ACCESS_TOKEN` on your GitHub repository secrets.

---

## 🧪 Running the Test Suite
Ensure all services, API routers, model chains, and rendering pipelines are functioning correctly:
```powershell
$env:PYTHONPATH="."
.\venv\Scripts\pytest tests/ -v
```

---

## 📄 License
This project is licensed under the MIT License.
