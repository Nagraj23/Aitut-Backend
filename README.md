# 🚀 Ai-Tut Backend Ecosystem

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" />
  <img src="https://img.shields.io/badge/Spring_Boot-6DB33F?style=for-the-badge&logo=springboot&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/ChromaDB-7B61FF?style=for-the-badge" />
</p>

<p align="center">
  <b>AI-Powered Personalized Learning Platform</b>
</p>

---

## 🎯 Overview

Ai-Tut is a microservice-based backend powering an intelligent tutoring ecosystem featuring:

📚 AI Teacher with Retrieval-Augmented Generation (RAG)

🧪 Adaptive Assessments & Skill Evaluation

🗺️ Personalized Learning Roadmaps

🔔 Real-Time Study Reminders

🔐 JWT Authentication & Social Login

🎙️ Text-to-Speech Learning Sessions

⚡ Server-Sent Events (SSE) Streaming

---

## 🏗️ System Architecture

```text
                    ┌─────────────────┐
                    │  Mobile / Web   │
                    │     Client      │
                    └────────┬────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │ 🔐 Spring Boot Auth    │
                │ JWT + Redis + Google   │
                └────────┬───────────────┘
                         │
     ┌───────────────────┼───────────────────┐
     ▼                   ▼                   ▼

┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ 🧑‍🏫 TEACH   │   │ 🧠 Assessment│   │ ⏰ Reminder │
│ FastAPI RAG │   │ Django DRF  │   │ FastAPI SSE │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       ▼                 ▼                 ▼

 ┌──────────┐      ┌──────────┐     ┌──────────┐
 │ ChromaDB │      │ Postgres │     │  Redis   │
 │ Vectors  │      │ Learning │     │ Pub/Sub  │
 └──────────┘      └──────────┘     └──────────┘
```

---

# 🧩 Microservices

## 🧑‍🏫 TEACH — AI Teacher Service

### ✨ Features

* 📄 PDF Upload & Processing
* 🧩 Intelligent Chunking
* 🔍 Semantic Search
* 🧠 Groq LLM Integration
* 💬 Streaming AI Responses
* 🎙️ Edge-TTS Audio Generation
* 📝 Session History Tracking
* 📚 Subject-Based Knowledge Bases

### 🛠️ Tech Stack

| Component | Technology |
| --------- | ---------- |
| API       | FastAPI    |
| Vector DB | ChromaDB   |
| LLM       | Groq       |
| TTS       | Edge-TTS   |
| Database  | PostgreSQL |
| Streaming | SSE        |

---

## 🧠 Assessment Service

### ✨ Features

* 🧪 Dynamic Assessment Generation
* 📊 Performance Evaluation
* 🎯 Skill Gap Analysis
* 🗺️ AI Roadmap Creation
* 📈 Learning Progress Tracking
* 🧱 Knowledge Graph Storage

### 🛠️ Tech Stack

| Component | Technology |
| --------- | ---------- |
| Framework | Django     |
| API       | DRF        |
| AI        | Groq       |
| Database  | PostgreSQL |

---

## ⏰ Reminder Service

### ✨ Features

* 🔔 Real-Time Notifications
* 📅 Alarm Scheduling
* 📡 Redis PubSub
* 🌊 SSE Event Streaming
* 🎯 Study Session Reminders

---

## 🔐 Authentication Service

### ✨ Features

* 🔑 JWT Authentication
* 👤 Google OAuth Login
* 🗃️ Redis Session Management
* 🛡️ Token Verification
* ⚡ Secure Cross-Service Authentication

---

# 🗄️ Data Layer

| Storage       | Purpose                |
| ------------- | ---------------------- |
| 🐘 PostgreSQL | Persistent Data        |
| 🧱 ChromaDB   | Embeddings & Retrieval |
| 🗣️ Redis     | Real-Time Events       |
| 📂 PDF Files  | Learning Material      |

---

# 🌟 Core Capabilities

### 📚 AI Learning

* RAG-based tutoring
* Context-aware answers
* Textbook grounding

### 🎙️ Interactive Sessions

* Live response streaming
* Voice generation
* Session recap generation

### 🧠 Personalized Learning

* Adaptive assessments
* SWOT analysis
* AI-generated roadmaps

### ⏰ Productivity

* Smart reminders
* Real-time notifications
* Study schedule tracking

---

# 🚀 Future Enhancements

* 🎥 Video Lesson Generation
* 🤖 Multi-Agent Tutoring
* 📊 Analytics Dashboard
* 🏆 Gamification System
* 📱 Mobile Push Notifications
* 🌍 Multi-Language Support

---

# 📌 Project Status

🟢 Active Development

✅ AI Teacher Complete

✅ Assessment Engine Complete

✅ Reminder Service Complete

✅ Authentication Complete

🚀 Production Deployment In Progress

---

<p align="center">
Built with ❤️ for Personalized AI Education
</p>
