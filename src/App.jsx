import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, Database, ShieldAlert, Settings, 
  Search, FileText, X, ArrowUpRight, CheckCircle2, 
  AlertTriangle, Filter, UploadCloud, Loader2, FileSearch, Cpu, Terminal
} from 'lucide-react';
import NetworkGraph3D from './NetworkGraph3D';

// Моковые данные для таблицы (RAG)
const mockResults = [
  { id: 'R001', config: 'C01', dataset: 'HotpotQA', metric: 'NDCG@10', value: '0.85', origin: 'primary', status: 'valid', issue: null, source: { page: 7, text: 'Our system achieves an NDCG@10 of 0.85, outperforming the baseline by 12%.' } },
  { id: 'R002', config: 'C01', dataset: 'Natural Questions', metric: 'Recall@5', value: '0.92', origin: 'primary', status: 'valid', issue: null, source: { page: 8, text: 'The recall at 5 documents reached 0.92 for the GraphRAG setup.' } },
  { id: 'R003', config: 'C02', dataset: 'TriviaQA', metric: 'F1-Score', value: '1.15', origin: 'cited', status: 'critical', issue: 'metric_scale', source: { page: 9, text: 'We observe an F1-score of 1.15 on the test split.' } },
  { id: 'R004', config: 'C03', dataset: 'SQuAD', metric: 'EM', value: '0.76', origin: 'primary', status: 'valid', issue: null, source: { page: 12, text: 'Exact Match (EM) reaches 0.76 on the SQuAD dataset.' } },
  { id: 'R005', config: 'C02', dataset: 'TriviaQA', metric: 'Latency', value: '230', origin: 'primary', status: 'warning', issue: 'direction', source: { page: 10, text: 'Average latency is 230 ms per query.' } },
];

export default function RAGDashboard() {
  const [activeTab, setActiveTab] = useState('overview'); 
  const [selectedResult, setSelectedResult] = useState(null);
  
  // Состояния для конвейера загрузки
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, processing, extracting, validating, done
  const [logs, setLogs] = useState([]);

  // Имитация работы конвейера ИИ
  useEffect(() => {
    if (uploadStatus === 'processing') {
      const addLog = (text) => setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${text}`]);
      
      addLog("Старт обработки PDF: article_test_45.pdf");
      addLog("Проверка SHA-256 и структуры файла... OK");
      
      const timer1 = setTimeout(() => {
        addLog("Текстовый слой не найден на стр. 3. Запуск OCR (Tesseract)...");
        setUploadStatus('extracting');
      }, 1500);
      
      const timer2 = setTimeout(() => {
        addLog("Отправка текста в LLM (модель: GigaChat)...");
        addLog("Извлечено: 1 конфигурация, 3 метрики, 2 цитаты.");
      }, 3000);

      const timer3 = setTimeout(() => {
        addLog("Проверка метрик: F1-score > 1.0 (Ошибка metric_scale).");
        addLog("Проверка цитат: все фрагменты найдены на указанных страницах.");
        setUploadStatus('validating');
      }, 4500);

      const timer4 = setTimeout(() => {
        addLog("Валидация завершена. Запись данных в DuckDB/CSV.");
        setUploadStatus('done');
      }, 6000);

      return () => { clearTimeout(timer1); clearTimeout(timer2); clearTimeout(timer3); clearTimeout(timer4); };
    }
  }, [uploadStatus]);

  const startUpload = () => {
    setLogs([]);
    setUploadStatus('processing');
  };

  return (
    <div className="flex h-screen bg-[#0B0E14] text-[#E2E8F0] font-sans overflow-hidden selection:bg-[#00D2FF] selection:text-black">
      
      {/* 1. ЛЕВЫЙ САЙДБАР (Навигация) */}
      <aside className="w-20 flex flex-col items-center py-6 border-r border-white/5 bg-[#0B0E14] z-30 shrink-0">
        <div className="w-10 h-10 bg-[#00D2FF] rounded-xl flex items-center justify-center font-bold text-black text-xl mb-10 shadow-[0_0_20px_rgba(0,210,255,0.4)]">
          R
        </div>
        
        <nav className="flex flex-col gap-6 flex-1 w-full">
          <button onClick={() => setActiveTab('overview')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'overview' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'overview' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}
            <LayoutDashboard className="w-6 h-6" />
          </button>
          
          <button onClick={() => setActiveTab('upload')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'upload' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'upload' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}
            <UploadCloud className="w-6 h-6" />
          </button>

          <button onClick={() => setActiveTab('data')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'data' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'data' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}
            <Database className="w-6 h-6" />
          </button>
          
          <button onClick={() => setActiveTab('validation')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'validation' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'validation' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}
            <ShieldAlert className="w-6 h-6" />
          </button>
        </nav>

        <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white mt-auto"><Settings className="w-6 h-6" /></button>
      </aside>

      {/* ОСНОВНАЯ ОБЛАСТЬ */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        
        {/* ВЕРХНЯЯ ПАНЕЛЬ (Хедер) */}
        <header className="h-20 flex items-center justify-between px-8 border-b border-white/5 shrink-0 z-20 bg-[#0B0E14]/80 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-medium text-white">
              {activeTab === 'overview' && 'Системный обзор'}
              {activeTab === 'upload' && 'Конвейер обработки PDF'}
              {activeTab === 'data' && 'Извлеченные данные'}
              {activeTab === 'validation' && 'Валидация и ошибки'}
            </h1>
            <span className="text-[10px] tracking-widest uppercase text-gray-500 border border-white/10 px-2 py-1 rounded">VINITI RAG EXPLORER</span>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input type="text" placeholder="Search..." className="bg-[#151A24] border border-white/10 text-xs text-white rounded-full py-2 pl-9 pr-4 w-64 focus:outline-none focus:border-[#00D2FF]/50" />
            </div>
          </div>
        </header>

        {/* КОНТЕНТ (Переключение экранов) */}
        <div className="flex-1 relative overflow-hidden">
          
          {/* ЭКРАН 1: ОБЗОР (С 3D-шаром) */}
          {activeTab === 'overview' && (
            <div className="absolute inset-0 flex">
              <NetworkGraph3D status="normal" />
              <div className="absolute top-12 left-12 z-10 max-w-sm pointer-events-none">
                <div className="text-[#00D2FF] text-xs font-mono tracking-widest mb-2">SYSTEM OVERVIEW</div>
                <h2 className="text-4xl font-light text-white leading-tight mb-4">EXTRACTED<br /><span className="font-bold">KNOWLEDGE.</span></h2>
                <p className="text-sm text-gray-400 leading-relaxed mb-8 pointer-events-auto">Автоматическое извлечение конфигураций RAG, наборов данных и метрик из 90 научных публикаций. Проверка валидности цитат.</p>
                <div className="flex gap-8 border-t border-white/10 pt-6 pointer-events-auto">
                  <div><div className="text-3xl font-mono text-white">90</div><div className="text-[10px] text-gray-500 uppercase mt-1">PDF Docs</div></div>
                  <div><div className="text-3xl font-mono text-[#00D2FF]">2.4K</div><div className="text-[10px] text-gray-500 uppercase mt-1">Metrics</div></div>
                  <div><div className="text-3xl font-mono text-[#FF0032]">12</div><div className="text-[10px] text-gray-500 uppercase mt-1">Issues</div></div>
                </div>
              </div>
            </div>
          )}

          {/* ЭКРАН 2: ЗАГРУЗКА И ОБРАБОТКА (Upload) */}
          {activeTab === 'upload' && (
            <div className="absolute inset-0 p-8 flex gap-8 bg-[#0B0E14]">
              {/* Левая часть: Drag & Drop */}
              <div className="w-1/3 flex flex-col gap-6">
                <div className="bg-[#151A24] border border-white/10 rounded-2xl p-8 flex flex-col items-center justify-center text-center h-64 border-dashed hover:border-[#00D2FF]/50 transition-colors cursor-pointer" onClick={startUpload}>
                  <div className="w-16 h-16 bg-[#00D2FF]/10 rounded-full flex items-center justify-center mb-4">
                    <UploadCloud className="w-8 h-8 text-[#00D2FF]" />
                  </div>
                  <h3 className="text-white font-medium mb-2">Загрузить статью</h3>
                  <p className="text-xs text-gray-500 mb-4">Перетащите PDF сюда или нажмите для выбора</p>
                  <button className="px-6 py-2 bg-[#00D2FF] text-black font-bold text-xs uppercase rounded-lg">Выбрать файл</button>
                </div>
                
                <div className="bg-[#151A24] border border-white/10 rounded-2xl p-6">
                  <h4 className="text-xs text-gray-400 uppercase tracking-wider mb-4">Требования к файлу</h4>
                  <ul className="text-xs text-gray-500 space-y-2">
                    <li className="flex items-center gap-2"><CheckCircle2 className="w-3 h-3 text-green-500"/> Формат: PDF</li>
                    <li className="flex items-center gap-2"><CheckCircle2 className="w-3 h-3 text-green-500"/> Размер: до 50 МБ</li>
                    <li className="flex items-center gap-2"><CheckCircle2 className="w-3 h-3 text-green-500"/> Наличие текстового слоя или OCR</li>
                  </ul>
                </div>
              </div>

              {/* Правая часть: Лог ИИ и статус */}
              <div className="flex-1 bg-[#050505] border border-white/10 rounded-2xl flex flex-col overflow-hidden relative">
                <div className="h-12 border-b border-white/10 flex items-center px-4 gap-2 bg-[#151A24]">
                  <Terminal className="w-4 h-4 text-gray-500" />
                  <span className="text-xs font-mono text-gray-400">AI Pipeline Log</span>
                  {uploadStatus !== 'idle' && uploadStatus !== 'done' && (
                    <span className="ml-auto flex items-center gap-2 text-xs text-[#00D2FF]"><Loader2 className="w-3 h-3 animate-spin"/> Processing...</span>
                  )}
                  {uploadStatus === 'done' && (
                    <span className="ml-auto flex items-center gap-2 text-xs text-green-500"><CheckCircle2 className="w-3 h-3"/> Completed</span>
                  )}
                </div>

                <div className="flex-1 p-6 font-mono text-sm overflow-y-auto space-y-2">
                  {logs.length === 0 && <span className="text-gray-600 italic">Ожидание загрузки файла...</span>}
                  {logs.map((log, i) => (
                    <div key={i} className="text-gray-300">
                      <span className="text-gray-500 mr-2">{'>'}</span> {log}
                    </div>
                  ))}
                  {uploadStatus === 'done' && (
                    <div className="mt-4 pt-4 border-t border-white/10">
                      <button onClick={() => setActiveTab('data')} className="px-4 py-2 bg-[#00D2FF] text-black text-xs font-bold rounded hover:bg-white transition-colors">
                        Перейти к извлеченным данным &rarr;
                      </button>
                    </div>
                  )}
                </div>

                {/* Прогресс бар снизу */}
                {uploadStatus !== 'idle' && (
                  <div className="h-1 w-full bg-gray-800">
                    <div 
                      className="h-full bg-[#00D2FF] transition-all duration-1000 ease-out"
                      style={{ width: uploadStatus === 'processing' ? '25%' : uploadStatus === 'extracting' ? '50%' : uploadStatus === 'validating' ? '75%' : '100%' }}
                    ></div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ЭКРАН 3: ДАННЫЕ (Таблица) */}
          {activeTab === 'data' && (
            <div className="absolute inset-0 p-8 flex flex-col overflow-hidden bg-[#0B0E14]">
              <div className="flex items-center gap-4 mb-6 shrink-0">
                <button className="flex items-center gap-2 text-xs text-white bg-white/5 border border-white/10 px-3 py-2 rounded-lg hover:bg-white/10"><Filter className="w-3 h-3" /> Фильтры</button>
                <select className="bg-[#151A24] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none"><option>Все конфигурации</option></select>
                <select className="bg-[#151A24] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none"><option>Все метрики</option></select>
                <div className="flex-1"></div>
                <span className="text-xs text-gray-500">Найдено записей: 1245</span>
              </div>

              <div className="flex-1 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-[#151A24] sticky top-0 border-b border-white/10 z-10">
                    <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                      <th className="p-4 font-normal">ID</th>
                      <th className="p-4 font-normal">Конфигурация</th>
                      <th className="p-4 font-normal">Датасет</th>
                      <th className="p-4 font-normal">Метрика</th>
                      <th className="p-4 font-normal">Значение</th>
                      <th className="p-4 font-normal">Источник</th>
                      <th className="p-4 font-normal">Статус</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {mockResults.map((row) => (
                      <tr key={row.id} onClick={() => setSelectedResult(row)} className="border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors group">
                        <td className="p-4 font-mono text-gray-400">{row.id}</td>
                        <td className="p-4 text-white">{row.config}</td>
                        <td className="p-4 text-gray-300">{row.dataset}</td>
                        <td className="p-4 text-gray-300 font-mono">{row.metric}</td>
                        <td className="p-4 font-mono text-white">{row.value}</td>
                        <td className="p-4 text-[#00D2FF] text-xs flex items-center gap-1">Page {row.source.page} <ArrowUpRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" /></td>
                        <td className="p-4">
                          {row.status === 'valid' && <span className="text-green-400 bg-green-400/10 px-2 py-1 rounded text-xs">Valid</span>}
                          {row.status === 'critical' && <span className="text-[#FF0032] bg-[#FF0032]/10 px-2 py-1 rounded text-xs">Error</span>}
                          {row.status === 'warning' && <span className="text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded text-xs">Warning</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ЭКРАН 4: ВАЛИДАЦИЯ (Замечания) */}
          {activeTab === 'validation' && (
            <div className="absolute inset-0 p-8 overflow-y-auto bg-[#0B0E14]">
              <h2 className="text-xl text-white mb-6">Найденные нарушения (Issues.csv)</h2>
              <div className="space-y-4">
                <div className="bg-[#FF0032]/5 border border-[#FF0032]/20 p-5 rounded-xl">
                  <div className="flex items-center gap-3 mb-2"><AlertTriangle className="w-5 h-5 text-[#FF0032]" /><h3 className="text-white font-medium">metric_scale: Значение вне допустимой шкалы</h3></div>
                  <p className="text-sm text-gray-400 mb-2">Запись R003: F1-Score = 1.15 (допустимо от 0 до 1.0).</p>
                  <button className="text-xs text-[#00D2FF] hover:underline" onClick={() => { setSelectedResult(mockResults[2]); setActiveTab('data'); }}>Посмотреть запись →</button>
                </div>
                <div className="bg-yellow-400/5 border border-yellow-400/20 p-5 rounded-xl">
                  <div className="flex items-center gap-3 mb-2"><ShieldAlert className="w-5 h-5 text-yellow-400" /><h3 className="text-white font-medium">direction: Не указано направление улучшения</h3></div>
                  <p className="text-sm text-gray-400 mb-2">Запись R005: Latency = 230. Для метрики latency должно быть lower_is_better.</p>
                  <button className="text-xs text-[#00D2FF] hover:underline" onClick={() => { setSelectedResult(mockResults[4]); setActiveTab('data'); }}>Посмотреть запись →</button>
                </div>
              </div>
            </div>
          )}

        </div>
      </main>

      {/* ВЫЕЗЖАЮЩАЯ ПАНЕЛЬ ДЕТАЛЕЙ (Drawer) */}
      <div className={`fixed inset-y-0 right-0 w-[450px] bg-[#0A0A0A] border-l border-white/10 z-40 shadow-2xl flex flex-col transition-transform duration-300 ease-in-out ${selectedResult ? 'translate-x-0' : 'translate-x-full'}`}>
        {selectedResult && (
          <>
            <div className="p-6 border-b border-white/10 flex justify-between items-start bg-[#151A24]">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs font-mono text-gray-400 bg-white/5 px-2 py-1 rounded">{selectedResult.id}</span>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded ${selectedResult.status === 'critical' ? 'text-[#FF0032] bg-[#FF0032]/10' : selectedResult.status === 'warning' ? 'text-yellow-400 bg-yellow-400/10' : 'text-green-400 bg-green-400/10'}`}>{selectedResult.status}</span>
                </div>
                <h2 className="text-lg font-bold text-white">{selectedResult.metric}</h2>
                <p className="text-sm text-gray-400 mt-1">Значение: <span className="text-white font-mono">{selectedResult.value}</span></p>
              </div>
              <button onClick={() => setSelectedResult(null)} className="p-2 hover:bg-white/10 rounded-full text-gray-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
              <div>
                <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-3">Метаданные</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div><span className="text-gray-500 block text-xs">Конфигурация</span> <span className="text-white">{selectedResult.config}</span></div>
                </div>
              </div>

              <div>
                <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-2"><FileText className="w-3 h-3" /> Цитата (source_fragment)</h4>
                <div className="bg-[#151A24] border-l-2 border-[#00D2FF] p-4 rounded-r-lg">
                  <p className="text-sm text-gray-300 font-mono italic leading-relaxed">"{selectedResult.source.text}"</p>
                  <p className="text-xs text-gray-500 mt-3 border-t border-white/5 pt-2">Страница PDF: {selectedResult.source.page}</p>
                </div>
              </div>

              {selectedResult.issue && (
                <div>
                  <h4 className="text-[10px] uppercase tracking-widest text-[#FF0032] mb-2 flex items-center gap-2"><AlertTriangle className="w-3 h-3" /> Замечание валидатора</h4>
                  <div className="bg-[#FF0032]/5 border border-[#FF0032]/20 p-4 rounded-lg">
                    <p className="text-sm text-gray-300">Нарушено правило: <strong>{selectedResult.issue}</strong>. Данные требуют ручной проверки.</p>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

    </div>
  );
}