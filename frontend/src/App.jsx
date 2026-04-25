import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Moon, Sun, Sparkles, Book, Library, BookOpen } from 'lucide-react';
import './index.css';

// Integrated Logo Component: Search icon inside the letter 'ق'
const SearchInLogo = ({ color = "var(--accent-gold)" }) => (
  <div className="brand-logo-container">
    <span className="brand-name">لُـقـيَـا</span>
    <div className="qaf-search-lens">
      <svg width="24" height="24" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="45" cy="45" r="35" stroke={color} strokeWidth="8" />
        <path d="M70 70L85 85" stroke={color} strokeWidth="10" strokeLinecap="round" />
      </svg>
    </div>
  </div>
);

const ResultCard = ({ hit, mode }) => {
  const [activeTafsir, setActiveTafsir] = useState(null);

  if (!hit || !hit.surah_name) return null;

  const tafsirData = [
    { id: 'simple_moyassar', name: 'الميسر' },
    { id: 'simple_saadi', name: 'السعدي' },
    { id: 'advanced_katheer', name: 'ابن كثير' },
    { id: 'advanced_tabari', name: 'الطبري' }
  ];

  const translateExplanation = (exp) => {
    if (!exp) return "مطابقة";
    if (exp === "keyword found directly in the Ayah text") return "تم العثور في نص الآية";
    if (exp && exp.includes("Thematic Match:")) {
      return exp.replace("Thematic Match:", "موضوع: ");
    }
    if (exp && exp.includes("Linguistic Root:")) {
      return exp.replace("Linguistic Root:", "جذر لغوي: ");
    }
    return exp || "مطابقة";
  };

  const safeSurahName = hit.surah_name || "سورة";
  const normalizedSurahName = safeSurahName.replace(/[\u064B-\u065F]/g, '');

  return (
    <div className="result-card">
      <div className="badge-container">
        {(hit.explanation || "مطابقة").split(' | ').map((exp, idx) => (
          <div key={idx} className={`badge ${exp.includes('Thematic') ? 'thematic-badge' : ''}`}>
            <Sparkles size={14} />
            <span>{translateExplanation(exp)}</span>
          </div>
        ))}
      </div>
      
      <div className="ayah-header">
        <div className="ayah-reference">
          {/سور/i.test(normalizedSurahName) ? safeSurahName : `سورة ${safeSurahName}`} ({hit.surah_number}:{hit.ayah_number})
        </div>
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
      const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
      const response = await axios.get(`${API_BASE}/api/search`, {
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
        <button onClick={toggleTheme} className="theme-toggle" title="تبديل المظهر">
          {theme === 'light' ? <Moon size={22} /> : <Sun size={22} />}
        </button>
        <div className="brand-title">
          <SearchInLogo />
        </div>
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
            {/* New order: Ayah (Top/First), Tafsir (Middle), Semantic (Bottom/Last) */}
            <button 
              type="button" 
              className={`mode-btn ${mode === 'ayah_only' ? 'active' : ''}`}
              onClick={() => setMode('ayah_only')}
            >
              <Book size={18} />
              <span>ابحث في آيات القرآن</span>
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
              className={`mode-btn ${mode === 'semantic_root' ? 'active' : ''}`}
              onClick={() => setMode('semantic_root')}
            >
              <Sparkles size={18} />
              <span>البحث بالمعاني والمقاصد</span>
            </button>
          </div>
        </form>
      </section>

      {loading && (
        <div className="loading-state">
          <div className="loading-spinner"><Search size={40} /></div>
          <p dir="rtl">جاري البحث في آيات الله عبر لُقْيَا...</p>
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
          
          {results.related_themes && results.related_themes.length > 0 && (
            <div className="related-themes-section" style={{ marginTop: '3rem', borderTop: '2px dashed var(--border)', paddingTop: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', marginBottom: '1.5rem', gap: '0.75rem' }}>
                <h2 className="arabic-text" dir="rtl" style={{ fontSize: '1.8rem', color: 'var(--text)', margin: 0 }}>مواضيع متعلقة</h2>
                <BookOpen size={24} style={{ color: 'var(--accent-gold)' }} />
              </div>
              
              <div className="related-themes-list" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                {results.related_themes.map((themeGroup, idx) => (
                  <div key={idx} className="theme-group" style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: '16px', border: '1px solid var(--border)' }}>
                    <h3 className="arabic-text" dir="rtl" style={{ fontSize: '1.4rem', color: 'var(--accent-gold)', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Library size={18} />
                      {themeGroup.theme_name}
                    </h3>
                    <div className="theme-ayah-list" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {themeGroup.ayahs.map(hit => (
                        <div key={hit.id} className="theme-ayah-card" style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '12px' }}>
                          <p className="arabic-text" dir="rtl" style={{ fontSize: '1.2rem', lineHeight: '2', margin: 0 }}>
                            {hit.text_uthmani} <span className="ayah-number-circle" style={{ fontSize: '0.8rem', transform: 'scale(0.8)' }}>{hit.ayah_number}</span>
                          </p>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.5rem', textAlign: 'right' }}>
                            {hit.surah_name.includes('سورة') ? hit.surah_name : `سورة ${hit.surah_name}`} ({hit.surah_number}:{hit.ayah_number})
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
      
      {!results && !loading && !error && (
        <div className="empty-state">
          <div style={{ opacity: 0.1, margin: '0 auto 2.5rem', display: 'flex', justifyContent: 'center', transform: 'scale(2.5)' }}>
            <SearchInLogo />
          </div>
          <p className="arabic-text" style={{ fontSize: '1.5rem' }}>أَفَلَا يَتَدَبَّرُونَ الْقُرْآنَ أَمْ عَلَىٰ قُلُوبٍ أَقْفَالُهَا</p>
          <p style={{ fontSize: '1rem', marginTop: '0.75rem', opacity: 0.6 }}>"Then do they not reflect upon the Qur'an, or are there locks upon [their] hearts?" (47:24)</p>
        </div>
      )}
    </div>
  );
}

export default App;
