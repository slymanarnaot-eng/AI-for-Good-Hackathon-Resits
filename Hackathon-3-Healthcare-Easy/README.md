# 🏥 Healthcare Easy

## Understand healthcare information in your own language

Healthcare Easy is an AI-powered healthcare information explainer.

It helps people understand a healthcare message they received from a doctor,
hospital, or healthcare service.

The user can provide a healthcare message in one language and choose another
language in which they want the information explained.

The goal is not only translation. Healthcare Easy explains and simplifies the
message while keeping important medical information such as medicines,
dosages, dates, times, warnings, and instructions unchanged.

---

## 🎯 Problem

Some people in the Netherlands have difficulty understanding healthcare
information because of language barriers or complex medical terminology.

A Nivel study of 11,441 people found that 52.8% experienced difficulty with
at least one aspect of finding, understanding, evaluating, and/or using health
information.

The problem is not only translation. A person may understand the words but
still have difficulty understanding medical terminology, instructions, what
the message means, or what they are expected to do.

Healthcare Easy focuses on:

**Unequal access to understandable healthcare information.**

---

## 🌍 SDG 10 — Reduced Inequalities

Healthcare Easy connects to **UN Sustainable Development Goal 10:
Reduced Inequalities**.

The project focuses on making healthcare information easier to understand
for people who may experience language or health-literacy barriers.

Our primary user group is:

- Patients in the Netherlands with limited Dutch proficiency
- People who struggle with complex medical terminology

The project is not intended to replace healthcare professionals,
interpreters, or emergency medical services.

---

## 💡 Solution

Healthcare Easy uses AI to explain a specific healthcare message.

The user:

1. Selects the language of the original message.
2. Selects the language they want to understand it in.
3. Pastes the healthcare message or report.
4. Healthcare Easy sends the information to Gemini.
5. The AI explains the complete message in the selected language.

For example:

**Dutch medical report → Arabic explanation**

or:

**Arabic medical message → English explanation**

The system can work in both directions.

---

## 🌐 Supported Languages

- 🇳🇱 Dutch
- 🇬🇧 English
- 🇸🇦 Arabic
- 🇷🇴 Romanian
- 🇱🇹 Lithuanian

The source language and explanation language can be different.

---

## 🧠 What the AI Provides

The result is divided into several sections:

### Simple Explanation

A clear explanation of the healthcare message.

### What does the message say I should do?

Lists the actions explicitly stated in the original message.

### Important Information

Highlights important facts such as:

- Medicine names
- Dosages
- Dates
- Times
- Appointments
- Warnings
- Important instructions

### Missing or Unclear Information

Identifies information that is missing, vague, or unclear instead of
inventing an answer.

### Full Explanation

Explains the complete original message in the user's selected language.

### Safety Note

Explains the limitations of the tool.

---

## 🔐 Safety & Privacy

Healthcare Easy is an information explainer, not a medical advice tool.

It does not:

- Diagnose diseases or medical conditions
- Prescribe medication
- Recommend treatment
- Replace doctors, nurses, pharmacists, or professional interpreters
- Invent missing medical information

The system is designed not to change important information such as:

- Dosages
- Dates
- Times
- Numbers
- Medicine names
- Warnings
- Instructions

Users should avoid entering unnecessary personal or sensitive information.

If important information is unclear, users should contact a healthcare
professional.

---

## 🔎 Research

Our desk research identified several existing approaches to healthcare
communication barriers, including professional interpreters, translated
healthcare information, easy-language information, cultural mediation, and
support from healthcare professionals.

The research also identified an opportunity to explore AI for explaining a
specific healthcare message that a patient has already received.

The key distinction is:

**Translation is not always the same as understanding.**

Healthcare Easy explores whether an AI system can explain a specific healthcare
message in simpler language and, when needed, in the user's preferred
language without changing its important meaning.

---

## 🛠️ Technology

- Python
- Google Gemini API
- Google GenAI SDK
- Pydantic
- Rich
- `arabic-reshaper`
- `python-bidi`

The application currently runs as a terminal-based Python application.

---

## 🚀 How to Run

### 1. Install the requirements

Open your terminal in the project folder and run:

```bash
pip install -r requirements.txt
```

### 2. Set your Gemini API key

Set your Gemini API key as the environment variable:

```text
GEMINI_API_KEY
```

The API key should **not** be written directly inside the Python code or
committed to the project.

The application uses the environment variable automatically.

### 3. Run the application

```bash
python terminal_app.py
```

### 4. Use Healthcare Easy

Follow the instructions in the terminal:

1. Choose the source language.
2. Choose the language you want the explanation in.
3. Paste the healthcare message or report. You can use multiple lines.
4. Press Enter on an empty line when you finish.
5. Review the request and confirm it.
6. The AI generates the explanation.

---

## 🧪 Example

### Input

**Source language:** Dutch  
**Explanation language:** Arabic

A user can paste a Dutch healthcare message or medical report.

### Output

Healthcare Easy provides:

- A simple explanation
- Explicit actions from the message
- Important information
- Missing or unclear information
- A full explanation in Arabic
- A safety note

The same process can also be used in the other supported language
directions.

---

## ⚠️ Limitations

Healthcare Easy is an exploratory AI prototype.

AI-generated explanations can contain errors. The system therefore should
not be used as a replacement for professional medical advice.

The project focuses on explaining information that the user already received.
It does not independently verify a diagnosis, prescribe treatment, or decide
what medical action a patient should take.

When information is missing or unclear, the system should identify this
instead of creating an answer.

For important medical decisions, users should contact an appropriate
healthcare professional.

---

## 📁 Project Files

The main project files are:

```text
healthcare-easy/
├── terminal_app.py
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 🎯 Project Goal

Healthcare Easy explores how AI can help reduce barriers to understanding
healthcare information.

The goal is simple:

**Translate + Explain + Simplify**

while keeping important information from the original healthcare message
unchanged.
