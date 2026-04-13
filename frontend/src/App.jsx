import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Moon, Sun, Sparkles, Book, Library, BookOpen } from 'lucide-react';
import './index.css';

// ResultCard sub-component with interactive toggles
const ResultCard = ({ hit, mode }) => {
  const [activeTafsir, setActiveTafsir] = useState(null);

  const tafsirData = [
    { id: 'simple_moyassar', name: 'الميسر' },
    { id: 'simple_saadi', name: 'السعدي' },
    { id: 'advanced_katheer', name: 'ابن كثير' },
    { id: 'advanced_tabari', name: 'الطبري' }
  ];

  const translateExplanation = (exp) => {
    if (!exp) return "مطابقة";
    if (exp === "keyword found directly in the Ayah text") return "تم العثور في نص الآية";
    // Backend now provides "وجد في تفسير السعدي" etc. directly
    if (exp && exp.startsWith("Categorized under Linguistic Root:")) {
      return `مربوط بالجذر: ${exp.split(':').pop().trim()}`;
    }
    return exp || "مطابقة";
  };

  return (
    <div className="result-card">
      <div className="badge">
        <Sparkles size={14} />
        <span>{translateExplanation(hit.explanation)}</span>
      </div>
      
      <div className="ayah-header">
        <div className="ayah-reference">{/سور/i.test(hit.surah_name.replace(/[\u064B-\u065F]/g, '')) ? hit.surah_name : `سورة ${hit.surah_name}`} ({hit.surah_number}:{hit.ayah_number})</div>
      </div>
      
      <div className="ayah-text arabic-text" dir="rtl">
        {hit.text_uthmani}
        <span className="ayah-number-circle">{hit.ayah_number}</span>
      </div>

      <div className="tafsir-toggles">
        {tafsirData.map(t => (
          <button 
            key={t.id}
            className={`tafsir-btn ${activeTafsir === t.id ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              setActiveTafsir(activeTafsir === t.id ? null : t.id);
            }}
          >
            {t.name}
          </button>
        ))}
      </div>
      
      {activeTafsir && hit[`tafsir_${activeTafsir}`] && (
        <div className="tafsir-container">
          <div className="tafsir-title" dir="rtl">تفسير {tafsirData.find(t => t.id === activeTafsir).name}</div>
          <div className="tafsir-text arabic-text">
            {hit[`tafsir_${activeTafsir}`].split('.').filter(p => p.trim()).map((para, idx) => (
              <p key={idx} style={{ marginBottom: '1rem' }}>{para.trim()}.</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

function App() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('ayah_only');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  const toggleTheme = (e) => {
    e.preventDefault();
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  // Automatically trigger search when mode changes (Recovery bug fixed: added error check)
  useEffect(() => {
    if (query.trim() && (results || error)) {
      handleSearch();
    }
  }, [mode]);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    
    // We keep results visible while loading new ones to avoid flickering,
    // but update when fresh data arrives.

    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/search`, {
        params: { q: query, mode }
      });

      if (response.data.error) {
        setError(response.data.message);
        setResults(null);
      } else {
        setResults(response.data);
      }
    } catch (err) {
      setError("فشل الاتصال بمحرك البحث. تأكد من تشغيل الخادم.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="brand-title">
          <BookOpen className="text-accent" size={32} />
          <span>QuranLens</span>
        </div>
        <button onClick={toggleTheme} className="theme-toggle" title="تبديل المظهر">
          {theme === 'light' ? <Moon size={22} /> : <Sun size={22} />}
        </button>
      </header>

      <section className="search-module">
        <form onSubmit={handleSearch} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div className="search-input-wrapper">
            <Search className="search-icon" size={24} />
            <input
              type="text"
              dir="auto"
              className="search-input"
              placeholder="ابحث عن آية، أو كلمة، أو معنى ..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          
          <div className="mode-selector">
            {/* LTR order in DOM: Semantic (Leftmost), Tafsir (Mid), Ayah (Rightmost) */}
            <button 
              type="button" 
              className={`mode-btn ${mode === 'semantic_root' ? 'active' : ''}`}
              onClick={() => setMode('semantic_root')}
            >
              <Sparkles size={18} />
              <span>البحث بالمعاني والمقاصد</span>
            </button>
            <button 
              type="button" 
              className={`mode-btn ${mode === 'tafsir_only' ? 'active' : ''}`}
              onClick={() => setMode('tafsir_only')}
            >
              <Library size={18} />
              <span>ابحث في كتب التفسير</span>
            </button>
            <button 
              type="button" 
              className={`mode-btn ${mode === 'ayah_only' ? 'active' : ''}`}
              onClick={() => setMode('ayah_only')}
            >
              <Book size={18} />
              <span>ابحث في آيات القرآن</span>
            </button>
          </div>
        </form>
      </section>

      {loading && (
        <div className="loading-state">
          <div className="loading-spinner"><Search size={40} /></div>
          <p dir="rtl">جاري البحث في آيات الله...</p>
        </div>
      )}

      {error && (
        <div className="error-state">
          <p>{error}</p>
        </div>
      )}

      {results && !loading && (
        <section className="results-area">
          <div className="results-info" dir="rtl">
            تم العثور على {results.count} نتيجة
            {results.semantic_root_used && (
              <span> • مربوط بالجذر: <strong className="arabic-text" style={{ fontSize: '1.4rem', color: 'var(--accent-gold)' }}>{results.semantic_root_used}</strong></span>
            )}
          </div>
          
          <div className="results-list">
            {results.results.map((hit) => (
              <ResultCard key={hit.id} hit={hit} mode={mode} />
            ))}
          </div>
        </section>
      )}
      
      {!results && !loading && !error && (
        <div className="empty-state">
          <BookOpen size={64} style={{ opacity: 0.1, margin: '0 auto 1.5rem' }} />
          <p className="arabic-text" style={{ fontSize: '1.5rem' }}>أَفَلَا يَتَدَبَّرُونَ الْقُرْآنَ أَمْ عَلَىٰ قُلُوبٍ أَقْفَالُهَا</p>
          <p style={{ fontSize: '1rem', marginTop: '0.75rem', opacity: 0.6 }}>"Then do they not reflect upon the Qur'an, or are there locks upon [their] hearts?" (47:24)</p>
        </div>
      )}
    </div>
  );
}

export default App;
