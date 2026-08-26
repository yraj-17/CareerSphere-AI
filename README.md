# 🚀 CareerSphere AI

> **Next-Generation AI Career Intelligence & Professional Guidance Platform**

CareerSphere AI is an end-to-end, AI-powered career growth platform designed to empower professionals, job seekers, and students. By leveraging intelligent skill diagnostics, real-time interactive interview simulation, predictive career path analytics, and targeted professional networking, CareerSphere AI transforms career development into a data-driven, actionable journey.

---

## 🌟 Key Features

### 🧠 AI-Powered Career Engine
* **Skill Gap Diagnostics**: Analyzes your current skills against live market demand to identify missing competencies.
* **Interactive Career Mapping**: Offers tailored career pathways and step-by-step upskilling roadmaps.
* **Smart Career Recommendations**: Personalizes learning modules and job target strategies.

### 🎙️ AI Mock Interview Simulator
* **Real-Time Interactive Practice**: Simulate real-life technical, behavioral, and role-specific interview scenarios.
* **Actionable Instant Feedback**: Provides detailed scoring on response clarity, technical depth, and confidence metrics.

### 📊 Analytics & Insights Dashboard
* **Visual Skill Matrix**: Dynamic charts and progress trackers for visualizing your professional growth.
* **Market Demand Tracking**: Real-time salary insights and industry trends.
* **Match Score Engine**: Instant alignment ratings between your profile and target job descriptions.

### 🔒 Enterprise Auth & Security
* **Robust Authentication**: Powered by FastAPI, JWT tokens, and Bcrypt password hashing.
* **Live Username Validation**: Real-time check-username endpoint with pattern and availability feedback.
* **Dual-Identifier Login**: Seamless access via either username or registered email address.

### 🎨 Modern & Responsive Design
* **Glassmorphism & Dark Aesthetics**: UI crafted with Next.js 14, Tailwind CSS, and Framer Motion micro-animations.
* **Fully Responsive**: Optimized for desktop, tablet, and mobile viewing experiences.

---

## 🛠️ Technology Stack

### **Frontend**
* **Framework**: [Next.js 14](https://nextjs.org/) (App Router)
* **Library**: [React 18](https://react.dev/)
* **Styling**: [Tailwind CSS 3](https://tailwindcss.com/) & [PostCSS](https://postcss.org/)
* **Animations**: [Framer Motion](https://www.framer.com/motion/)
* **Icons**: [Lucide React](https://lucide.dev/)
* **HTTP Client**: [Axios](https://axios-http.com/)

### **Backend**
* **Framework**: [FastAPI 0.115+](https://fastapi.tiangolo.com/)
* **ASGI Server**: [Uvicorn](https://www.uvicorn.org/)
* **ORM & Database**: [SQLAlchemy 2.0+](https://www.sqlalchemy.org/) with PostgreSQL / SQLite
* **Validation & Settings**: [Pydantic v2](https://docs.pydantic.dev/) & `pydantic-settings`
* **Security & Auth**: [PyJWT](https://pyjwt.readthedocs.io/) & [Bcrypt](https://pypi.org/project/bcrypt/)
* **Testing**: [Pytest](https://docs.pytest.org/) & [HTTPX](https://www.python-httpx.org/)

---

## 📁 Repository Structure

```
CareerSphere AI/
├── backend/                  # FastAPI Python Backend
│   ├── app/                  # Core application package
│   │   ├── api/              # API endpoints (Auth, Users, Health)
│   │   ├── core/             # Application config & security logic
│   │   ├── db/               # SQLAlchemy models & database session setup
│   │   ├── schemas/          # Pydantic data schemas & response models
│   │   └── main.py           # FastAPI entrypoint & middleware setup
│   ├── tests/                # Automated pytest suite
│   ├── init_db.py            # Database initialization utility
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Backend environment variables template
│   └── careersphere.db       # SQLite local database instance
│
├── frontend/                 # Next.js React Frontend
│   ├── app/                  # Next.js App Router pages (Login, Signup, Dashboard)
│   ├── components/           # UI Components
│   │   ├── auth/             # Authentication forms & validation indicators
│   │   ├── common/           # Shared UI elements
│   │   └── landing/          # Interactive landing page sections
│   ├── context/              # React Auth Context & Global State
│   ├── hooks/                # Custom React Hooks
│   ├── services/             # API service layers
│   ├── public/               # Static assets & graphics
│   ├── package.json          # Node.js dependencies & scripts
│   ├── tailwind.config.js    # Tailwind CSS configuration
│   └── .env.example          # Frontend environment variables template
│
└── README.md                 # Project Documentation
```

---

## 🚀 Getting Started

Follow these steps to set up CareerSphere AI locally on your computer.

### 📋 Prerequisites
* **Node.js**: v18.0.0 or higher
* **npm**: v9.0.0 or higher
* **Python**: v3.10 or higher
* **Git**: Installed on your system

---

### 1️⃣ Setting Up the Backend

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create a virtual environment**:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install backend dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to create `.env`:
   ```bash
   cp .env.example .env
   ```
   *Modify `.env` if you want to connect to a local PostgreSQL instance or change the JWT secret key.*

5. **Initialize Database Tables**:
   ```bash
   python init_db.py
   ```

6. **Start the FastAPI Development Server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   *The API backend will be available at `http://localhost:8000`.*

---

### 2️⃣ Setting Up the Frontend

1. **Open a new terminal tab and navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install Node dependencies**:
   ```bash
   npm install
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to create `.env.local`:
   ```bash
   cp .env.example .env.local
   ```
   *Ensure `NEXT_PUBLIC_API_URL` points to `http://localhost:8000`.*

4. **Start the Next.js Development Server**:
   ```bash
   npm run dev
   ```
   *The frontend client will be available at `http://localhost:3000`.*

---

## 🔑 Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `CareerSphere AI` | Title of the application |
| `DATABASE_URL` | `postgresql+psycopg://...` / `sqlite:///...` | Connection string for database |
| `SECRET_KEY` | `careersphere_super_secret...` | Key used for signing JWT tokens |
| `ALGORITHM` | `HS256` | JWT signature algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiration time in minutes (24h) |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins for frontend requests |

### Frontend (`frontend/.env.local`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

---

## 📡 API Documentation & Endpoints

FastAPI automatically generates interactive documentation for all endpoints:
* 📖 **Swagger UI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* 📑 **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Core Auth Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check & DB connection verification |
| `GET` | `/api/auth/check-username` | Real-time username availability & format check |
| `POST` | `/api/auth/register` | Register a new user account |
| `POST` | `/api/auth/login` | Authenticate user (Username/Email) & get JWT token |
| `GET` | `/api/auth/me` | Fetch authenticated user profile (Requires Bearer token) |
| `POST` | `/api/auth/logout` | Client-side session log out |

---

## 🧪 Testing

### Backend Unit & Integration Tests
Run pytest from the `backend` directory:
```bash
cd backend
pytest
```

### Frontend Code Quality & Linting
Run Next.js linter from the `frontend` directory:
```bash
cd frontend
npm run lint
```

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for details.

---

## 🤝 Contributing

Contributions are welcome! If you'd like to improve CareerSphere AI:
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

<p align="center">
  Made with ❤️ by the <b>CareerSphere AI</b> Team
</p>
