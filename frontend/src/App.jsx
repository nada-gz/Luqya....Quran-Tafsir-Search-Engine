import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Moon, Sun, Sparkles, BookOpen } from 'lucide-react';
import './index.css';

function App() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('ayah_only');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Theme state
  const [theme, setTheme] = useState('light');

  // Load theme on startup
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/search`, {
        params: { q: query, mode }
      });

      if (response.data.error) {
        setError(response.data.message);
      } else {
        setResults(response.data);
      }
    } catch (err) {
      setError("Failed to connect to the search engine. Ensure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="brand-title">
          <BookOpen className="text-accent" size={28} />
          <span>QuranLens</span>
        </div>
        <button onClick={toggleTheme} className="theme-toggle" aria-label="تبديل المظهر">
          {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
        </button>
      </header>

      {/* Search Module */}
      <section className="search-module">
        <form onSubmit={handleSearch}>
          <div className="search-input-wrapper">
            <Search className="search-icon" size={22} />
            <input
              type="text"
              className="search-input arabic-text"
              placeholder="ابحث في القرآن أو التفسير..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          
          <div className="mode-selector">
            <button 
              type="button" 
              className={`mode-btn ${mode === 'ayah_only' ? 'active' : ''}`}
              onClick={() => setMode('ayah_only')}
            >
              ابحث في آيات القرآن
            </button>
            <button 
              type="button" 
              className={`mode-btn ${mode === 'tafsir_only' ? 'active' : ''}`}
              onClick={() => setMode('tafsir_only')}
            >
              ابحث في كتب التفسير
            </button>
            <button 
              type="button" 
              className={`mode-btn ${mode === 'semantic_root' ? 'active' : ''}`}
              onClick={() => setMode('semantic_root')}
            >
              <Sparkles size={14} style={{ display: 'inline', marginLeft: '4px', verticalAlign: 'text-bottom' }} />
              البحث بالمعاني والمقاصد
            </button>
          </div>
        </form>
      </section>

      {/* State Handlers */}
      {loading && (
        <div className="loading-state">
          <div className="loading-spinner"><Search size={32} /></div>
          <p>جاري البحث في آيات الله وتفاسيرها...</p>
        </div>
      )}

      {error && (
        <div className="error-state">
          <p>{error}</p>
        </div>
      )}

      {/* Results */}
      {results && !loading && (
        <section className="results-area">
          <div className="results-info" dir="rtl">
            تم العثور على {results.estimatedTotalHits} نتيجة في {results.processingTimeMs} ملي ثانية
            {results.semantic_root_used && (
              <span> • تم الربط بجذر: <strong className="arabic-text" style={{ fontSize: '1.2rem' }}>{results.semantic_root_used}</strong></span>
            )}
          </div>
          
          <div className="results-list">
            {results.results.map((hit) => (
              <div key={hit.id} className="result-card">
                <div className="badge">
                  <Sparkles size={12} /> {hit.explanation === "keyword found directly in the Ayah text" ? "تم العثور على الكلمة في نص الآية" : 
                                          hit.explanation.startsWith("Categorized under Linguistic Root:") ? `مصنف تحت الجذر اللغوي: ${hit.semantic_root_used || results.semantic_root_used}` : 
                                          hit.explanation}
                </div>
                
                <div className="ayah-header">
                  <span className="ayah-reference">سورة {hit.surah_name} ({hit.surah_number}:{hit.ayah_number})</span>
                </div>
                
                <div className="ayah-text arabic-text">
                  {hit.text_uthmani}
                </div>
                
                {(mode === 'tafsir_only' || hit.tafsir_simple_saadi) && (
                  <div className="tafsir-container">
                    <div className="tafsir-title">تفسير السعدي</div>
                    <div className="tafsir-text arabic-text">
                      {hit.tafsir_simple_saadi}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
      
      {!results && !loading && !error && (
        <div className="empty-state">
          <BookOpen size={48} style={{ opacity: 0.1, margin: '0 auto 1rem' }} />
          <p className="arabic-text">أَفَلَا يَتَدَبَّرُونَ الْقُرْآنَ أَمْ عَلَىٰ قُلُوبٍ أَقْفَالُهَا</p>
          <p style={{ fontSize: '0.85rem', marginTop: '0.5rem', opacity: 0.7 }}>"Then do they not reflect upon the Qur'an, or are there locks upon [their] hearts?" (47:24)</p>
        </div>
      )}
    </div>
  );
}

export default App;
