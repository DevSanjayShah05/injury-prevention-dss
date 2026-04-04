🧠 Injury Prevention Decision Support System (DSS)

An AI-assisted web application that helps athletes and fitness enthusiasts assess injury risk, understand contributing factors, and receive actionable training recommendations.

⸻

📌 Overview

This project is a full-stack Decision Support System (DSS) that combines rule-based risk scoring with AI-generated coaching insights.

Users input training, recovery, and pain-related data, and the system:
	•	Calculates an injury risk score
	•	Identifies key contributing factors
	•	Provides structured recommendations
	•	Generates a personalized 7-day coaching plan using AI
	•	Tracks historical data and visualizes trends via a dashboard

⸻

🎯 Problem Statement

Injury risk in training is often overlooked due to:
	•	Lack of structured tracking
	•	Poor understanding of training load vs recovery
	•	No real-time feedback system

This system aims to provide:

Data-driven, explainable, and actionable injury risk insights

⸻

💡 Key Features

🔹 Risk Assessment Engine
	•	Rule-based scoring system (0–100)
	•	Categorizes risk into:
	•	Low
	•	Moderate
	•	High
	•	Provides:
	•	Score breakdown
	•	Top contributing factors
	•	Recommendations

⸻

🤖 AI Coaching (Ollama - Local LLM)
	•	Uses Ollama (llama3.1 model) for local AI inference
	•	Generates structured output:
	•	Risk summary
	•	Top drivers
	•	7-day training adjustment plan
	•	Red flags
	•	Includes fallback logic if AI fails

⸻

📊 Dashboard Analytics
	•	Total assessments
	•	Average risk score
	•	Risk distribution
	•	Top pain locations
	•	AI usage tracking (Ollama vs fallback)
	•	Risk trend over time
	•	Top contributing factors
	•	Average score breakdown

⸻

💾 Data Persistence
	•	SQLite database
	•	Stores:
	•	User inputs
	•	Risk scores
	•	AI outputs
	•	Timestamps

⸻
🏗️ System Architecture
Frontend (React + Tailwind)
        ↓
FastAPI Backend (Python)
        ↓
Decision Support Logic (Rule-based)
        ↓
AI Layer (Ollama - LLM)
        ↓
SQLite Database

⸻
🛠️ Tech Stack

Frontend
	•	React (Vite)
	•	Tailwind CSS

Backend
	•	FastAPI
	•	Python

AI
	•	Ollama (Local LLM)
	•	Model: llama3.1

Database
	•	SQLite

Tools
	•	Git & GitHub
	•	VS Code
	•	Postman / cURL

⸻

⚙️ How to Run Locally

1. Clone the repository
git clone https://github.com/DevSanjayShah05/injury-prevention-dss.git
cd injury-prevention-dss

⸻

2. Start Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

⸻

3. Start Frontend
cd frontend
npm install
npm run dev

⸻
4. Run Ollama (AI)

Install Ollama: https://ollama.com

Then run:
ollama pull llama3.1
ollama run llama3.1

🧪 API Endpoints

Core
	•	POST /assess → Calculate risk
	•	POST /ai/coach → Generate AI coaching plan

Dashboard
	•	/dashboard/summary
	•	/dashboard/risk_distribution
	•	/dashboard/ai_usage
	•	/dashboard/risk_trend
	•	/dashboard/top_factors
	•	/dashboard/avg_breakdown

⸻

📸 Screenshots

(Add screenshots here for better presentation)

⸻

⚠️ Challenges Faced
	•	Integrating local AI (Ollama) with structured outputs
	•	Designing explainable scoring logic
	•	Handling fallback when AI fails
	•	Building a responsive and clean UI with Tailwind
	•	Designing meaningful dashboard analytics

⸻

🔮 Future Improvements
	•	User authentication & profiles
	•	Personalized long-term tracking
	•	ML-based predictive modeling
	•	Mobile responsiveness improvements
	•	Deployment (Vercel + Render)
	•	Exportable reports (PDF)

⸻

🧾 Conclusion

This project demonstrates how AI + rule-based systems can be combined to build a practical, real-world decision support system.

It bridges the gap between:
	•	Data → Insights → Action

⸻

👨‍💻 Author

Dev Sanjay Shah
MS Information Systems, Binghamton University
🔗 GitHub: https://github.com/DevSanjayShah05
🔗 LinkedIn: https://www.linkedin.com/in/dev-s-shah/