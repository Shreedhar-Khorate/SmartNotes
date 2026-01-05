# 🧠 SmartNotes



> **Your Intelligent Academic Assistant.**  
> Summarize notes, generate quizzes, and master complex topics with the power of AI.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gemini AI](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

---

## 📖 Overview

**SmartNotes** is a modern, AI-powered web application designed to revolutionize how students and professionals interact with their study materials. By leveraging **Google's Gemini AI**, SmartNotes transforms lengthy documents into concise summaries, generates interactive quizzes to test your knowledge, and provides an intelligent chatbot for real-time academic assistance.

Whether you're drowning in research papers or need a quick revision tool, SmartNotes is your personal study companion.

## ✨ Key Features

### 📝 AI-Powered Summarization

- **Instant Summaries**: Upload PDF, DOCX, or TXT files and get comprehensive summaries in seconds.
- **Smart Extraction**: Automatically filters out headers, footers, and irrelevant metadata.
- **Statistics**: View original vs. summary word counts and see exactly how much time you've saved.

### 🧠 Intelligent Quiz Generation

- **Auto-Generated Quizzes**: Create 5-question multiple-choice quizzes directly from your uploaded content.
- **Context-Aware**: Questions are tailored to the specific topics covered in your notes.
- **Instant Feedback**: Get immediate explanations for correct and incorrect answers.

### 💬 Smart Chat Assistant

- **Contextual Help**: Ask questions about your notes or any academic topic.
- **Study-Oriented**: The AI is tuned to provide clear, educational explanations.
- **History Aware**: Remembers the context of your conversation for a natural flow.

### 📊 Analytics Dashboard

- **Progress Tracking**: Monitor your study habits with visual statistics.
- **History**: Access all your past summaries and quizzes in one place.
- **Time Saved**: See the tangible impact of AI on your productivity.

---



## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **AI Engine**: Google Gemini Pro (Generative AI)
- **Frontend**: HTML5, CSS3 (Glassmorphism UI), JavaScript
- **File Processing**: PyPDF2, python-docx
- **Styling**: Custom CSS with responsive design

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- A Google Cloud Project with **Gemini API** access

### Installation

1.  **Clone the repository**

    ```bash
    git clone https://github.com/yourusername/smartnotes.git
    cd smartnotes
    ```

2.  **Create a virtual environment**

    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**

    ```bash
    pip install flask python-dotenv google-generativeai PyPDF2
    ```

4.  **Configure Environment Variables**
    Create a `.env` file in the root directory:

    ```env
    GEMINI_API_KEY=your_gemini_api_key_here
    SECRET_KEY=your_secret_key_here
    ```

5.  **Run the Application**

    ```bash
    python app.py
    ```

6.  **Access the App**
    Open your browser and navigate to `http://127.0.0.1:5000`

---

## 📂 Project Structure

```
SmartNotes/
├── app.py                 # Main Flask application
├── .env                   # Environment variables (not committed)
├── .gitignore             # Git ignore rules
├── static/
│   ├── css/
│   │   └── ml.css         # Main stylesheet
│   └── js/
│       └── script.js      # Frontend logic
├── templates/             # HTML Templates
│   ├── base.html          # Base layout
│   ├── index.html         # Landing page
│   ├── dashboard.html     # User dashboard
│   ├── summarizer.html    # Summarization tool
│   ├── quiz.html          # Quiz interface
│   └── chatbot.html       # AI Chat interface
├── uploads/               # Temporary storage for uploads
└── summaries/             # JSON storage for saved summaries
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the project
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <p>Made with ❤️ by Shreedhar Khorate</p>
</div>
