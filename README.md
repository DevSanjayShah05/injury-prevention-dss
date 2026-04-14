# 🧠 Injury Prevention Decision Support System (DSS)

An AI-powered full-stack application that assesses injury risk and provides personalized training recommendations using rule-based analytics and locally hosted Large Language Models (LLMs).

---

## 📌 Project Overview

The Injury Prevention DSS is designed to help individuals make safer training decisions by analyzing workout intensity, recovery, and pain indicators.

The system combines:
- 📊 Explainable risk scoring (0–100)
- 🤖 AI-generated coaching using local LLM (Ollama)
- 📈 Interactive analytics dashboard
- 🔐 Secure authentication with user-specific data

Unlike traditional fitness tools, this system emphasizes **interpretability, privacy, and data-driven decision-making**.

---

## 🚀 Key Features

### 🔹 Injury Risk Assessment
- Computes a risk score (0–100)
- Categorizes:
  - Low Risk
  - Moderate Risk
  - High Risk
- Identifies top contributing factors

---

### 🔹 AI Coaching (Ollama Integration)
- Generates:
  - Risk explanation
  - Key contributing factors
  - 7-day structured training plan
  - Recovery & safety tips
- Uses **local LLaMA 3.1 model via Ollama**
- Includes fallback logic for reliability

---

### 🔹 Analytics Dashboard
- Total assessments
- Average risk score
- Risk distribution (Low / Moderate / High)
- 30-day trend analysis
- Top contributing factors
- Pain location insights
- AI usage tracking (Ollama vs fallback)

---

### 🔹 Authentication System
- User Registration & Login
- JWT-based authentication
- Password hashing using `pbkdf2_sha256`
- Each user accesses only their own data

---

## 🏗️ Tech Stack

### Frontend
- React.js (Vite)
- Tailwind CSS

### Backend
- FastAPI (Python)
- SQLite database

### AI Layer
- Ollama (Local LLM)
- Model: `llama3.1:8b`

### Authentication
- JWT Tokens
- Passlib (PBKDF2 hashing)

---

## ⚙️ System Architecture

1. User submits training inputs  
2. Backend calculates injury risk score  
3. AI model generates coaching recommendations  
4. Data stored in SQLite database  
5. Dashboard aggregates and visualizes insights  

---

## 📂 Project Structure
injury-prevention-dss/
│
├── backend/
│   ├── main.py
│   ├── database.db
│   └── …
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── …
│   └── package.json
│
└── README.md

---

## ▶️ How to Run the Project

### 1️⃣ Clone the repository
```bash
git clone https://github.com/DevSanjayShah05/injury-prevention-dss.git
cd injury-prevention-dss

2️⃣ Backend Setup
cd backend
python3 -m venv .venv
source .venv/bin/activate

pip install fastapi uvicorn passlib python-jose email-validator requests

uvicorn main:app --reload
Backend runs at:
http://127.0.0.1:8000

Swagger Docs:
http://127.0.0.1:8000/docs

3️⃣ Frontend Setup
cd frontend
npm install
npm run dev

Frontend runs at:
http://localhost:5173

4️⃣ Run AI (Ollama)
Make sure Ollama is installed and running:
ollama run llama3.1

🔐 Authentication Flow
	1.	User registers account
	2.	Logs in to receive JWT token
	3.	Token used for API requests
	4.	Each user sees only their own data

⸻

📊 API Endpoints

Authentication
	•	POST /auth/register
	•	POST /auth/login
	•	GET /auth/me

Core
	•	POST /assess
	•	POST /ai/coach

Dashboard
	•	/dashboard/summary
	•	/dashboard/risk_distribution
	•	/dashboard/recent
	•	/dashboard/ai_usage
	•	/dashboard/risk_trend
	•	/dashboard/top_factors
	•	/dashboard/avg_breakdown

⸻
⚠️ Challenges & Solutions
Challenge 									Solution
AI response inconsistency           Structured prompt engineering
External API dependency.            Switched to Ollama (local inference)
Password hashing issues             Used PBKDF2 instead of bcrypt
Data aggregation complexity         Optimized backend queries
Frontend styling issues             Migrated to Tailwind CSS

🔮 Future Enhancements
	•	Wearable device integration (heart rate, steps)
	•	Machine learning-based predictive models
	•	Personalized recommendation engine
	•	Cloud deployment (AWS/GCP)
	•	Mobile application

⸻

🎓 Academic Context

Developed as part of the MS Information Systems Termination Project
Binghamton University

⸻

👨‍💻 Author

Dev Sanjay Shah
MS Information Systems
Binghamton University

📄 License

For academic and research purposes only.

---

# ✅ What makes this strong
This README now clearly shows:
- Full-stack skills ✅
- AI integration ✅
- Authentication system ✅
- Analytics dashboard ✅
- Real-world problem solving ✅

👉 This is **resume + GitHub portfolio level**

---

# 🚀 Next (optional but powerful)

If you want your project to look **next-level professional**, I can help you add:
- 📸 Screenshots section (very important)
- 🎥 Demo GIF
- 🌐 Deploy (Render / Vercel)

Just say **“add screenshots section”** 👍