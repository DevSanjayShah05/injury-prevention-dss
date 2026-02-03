# Injury Prevention Decision Support System

This project is an Exercise & Injury Prevention Decision Support System (DSS) designed to estimate training-related injury risk and provide actionable recommendations.

## Tech Stack
- Backend: Python, FastAPI
- Frontend: React (Vite)
- API Communication: REST
- Database (planned): SQLite

## Features
- Injury risk scoring (Low / Moderate / High)
- Explainable risk factors
- Personalized training and recovery recommendations
- Web-based interface for user interaction

## Project Structure



# Injury Prevention DSS

Exercise & Injury Prevention Decision Support System built with FastAPI (backend) and React (frontend).

## Run locally
### Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic
uvicorn main:app --reload --port 8000

### Frontend
cd frontend
npm create vite@latest . -- --template react
npm install
npm run dev