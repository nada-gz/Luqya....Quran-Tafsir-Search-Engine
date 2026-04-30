---
title: Luqya Backend
emoji: 🕌
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
# لُـقـيَـا | Luqya Quran Search Engine

> **Live Demo:** [https://luqyaforquran.vercel.app](https://luqyaforquran.vercel.app)

<br/>

> **API Status:** [Running on Hugging Face Spaces](https://huggingface.co/spaces/nadagz/luqya)

**Luqya** is a high-performance Quranic search platform designed for precision and scholarly depth. It leverages advanced linguistic processing and a multi-layered data architecture to deliver instant results across authentic Quranic texts and classical interpretations.

---

## ⚡ The Three Search Pillars

| Mode | Purpose | Technical Logic |
| :--- | :--- | :--- |
| **Ayah Search** | Direct Quranic lookup | Specialized **SQLite FTS5** word-boundary matching. |
| **Tafsir Search** | Interpretative research | Substring matching across **4 major scholarly volumes**. |
| **Semantic Search** | Thematic exploration | Root-driven results powered by a custom **Enrichment Map**. |

---

## 📚 Academic Foundations (Data Sources)

This project integrates authenticated datasets to ensure the highest scholarly accuracy:

### 📖 Quranic Text & Interpretations
- **Uthmani Script**: Authentic calligraphic text via the **Tanzil Project** and **KFGQPC**.
- **The Four Tafsirs**:
  1. **Tafsir al-Muyassar**: Clear, modern interpretation (King Fahd Complex).
  2. **Tafsir as-Sa'di**: *Taysir al-Karim al-Rahman*.
  3. **Tafsir Ibn Kathir**: *Tafsir al-Qur'an al-Azim*.
  4. **Tafsir at-Tabari**: *Jami' al-Bayan* (The foundational classical reference).

### 🔬 Linguistic & Thematic Data
- **Morphology**: Integrated linguistic roots and lemmas from the **Quranic Arabic Corpus** (University of Leeds).
- **Taxonomy**: Custom **Enrichment Mapping** linking roots to dominant thematic topics and related concepts.

---

## 💎 Engineering Excellence

### ⚙️ Backend Strategy
- **FastAPI Core**: Engineered for sub-millisecond API response times.
- **FTS5 Optimization**: Custom SQL indexing that eliminates the need for external search engines while maintaining elite performance.
- **Arabic Normalization**: A custom-built pipeline that handles orthography exceptions and diacritic stripping for accurate searching.

### 🎨 Frontend & UI
- **Adaptive Branding**: Native **Light and Dark mode** support with high-contrast scholarly typography.
- **Mobile Perfection**: Sophisticated CSS shaping to ensure complex Quranic ligatures render perfectly on small screens.

### 🔄 DevOps & Automation
- **CI/CD Pipeline**: Automated **GitHub Actions** that mirror Git LFS database assets directly to Hugging Face Spaces.
- **Dockerized Architecture**: Ensuring a consistent environment from local development to production.

---

## 🛠️ Local Setup

```bash
# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
```