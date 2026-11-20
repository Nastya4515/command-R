import React, { useState, useEffect, useMemo } from 'react';
import { 
  LayoutDashboard, Database, ShieldAlert, Settings, 
  Search, FileText, X, ArrowUpRight, CheckCircle2, 
  AlertTriangle, Filter, UploadCloud, Loader2, Terminal,
  Download, ExternalLink, ArrowDownWideNarrow, ArrowUpNarrowWide
} from 'lucide-react';
import NetworkGraph3D from './NetworkGraph3D';

const mockResults = [
  { id: 'R001', config: 'C01', dataset: 'HotpotQA', metric: 'NDCG@10', value: '0.85', numValue: 0.85, origin: 'primary', status: 'valid', issue: null, source: { page: 7, text: 'Our system achieves an NDCG@10 of 0.85, outperforming the baseline by 12%.' } },
  { id: 'R002', config: 'C01', dataset: 'Natural Questions', metric: 'Recall@5', value: '0.92', numValue: 0.92, origin: 'primary', status: 'valid', issue: null, source: { page: 8, text: 'The recall at 5 documents reached 0.92 for the GraphRAG setup.' } },
  { id: 'R003', config: 'C02', dataset: 'TriviaQA', metric: 'F1-Score', value: '1.15', numValue: 1.15, origin: 'cited', status: 'critical', issue: 'metric_scale', source: { page: 9, text: 'We observe an F1-score of 1.15 on the test split.' } },
  { id: 'R004', config: 'C03', dataset: 'SQuAD', metric: 'EM', value: '0.76', numValue: 0.76, origin: 'primary', status: 'valid', issue: null, source: { page: 12, text: 'Exact Match (EM) reaches 0.76 on the SQuAD dataset.' } },
  { id: 'R005', config: 'C02', dataset: 'TriviaQA', metric: 'Latency', value: '230', numValue: 230, origin: 'primary', status: 'warning', issue: 'direction', source: { page: 10, text: 'Average latency is 230 ms per query.' } },
];

export default function RAGDashboard() {
  const [activeTab, setActiveTab] = useState('overview'); 
  const [selectedResult, setSelectedResult] = useState(null);
  const [isPdfOpen, setIsPdfOpen] = useState(false);

  // Состояния для фильтров, поиска и сортировки
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDataset, setFilterDataset] = useState('all');
  const [filterMetric, setFilterMetric] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortOrder, setSortOrder] = useState('none');

  const [uploadStatus, setUploadStatus] = useState('idle'); 
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    if (uploadStatus === 'processing') {
      const addLog = (text) => setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${text}`]);
      addLog("Старт обработки PDF: article_test_45.pdf");
      const timer1 = setTimeout(() => { addLog("Запуск OCR..."); setUploadStatus('extracting'); }, 1500);
      const timer2 = setTimeout(() => { addLog("Отправка в LLM..."); }, 3000);
      const timer3 = setTimeout(() => { addLog("Валидация..."); setUploadStatus('validating'); }, 4500);
      const timer4 = setTimeout(() => { addLog("Готово."); setUploadStatus('done'); }, 6000);
      return () => { clearTimeout(timer1); clearTimeout(timer2); clearTimeout(timer3); clearTimeout(timer4); };
    }
  }, [uploadStatus]);

  // Логика фильтрации, поиска и сортировки
  const processedResults = useMemo(() => {
    let result = [...mockResults];

    // 1. Текстовый поиск
    if (searchQuery.trim() !== '') {
      const lowerQ = searchQuery.toLowerCase();
      result = result.filter(r => 
        r.id.toLowerCase().includes(lowerQ) ||
        r.config.toLowerCase().includes(lowerQ) ||
        r.dataset.toLowerCase().includes(lowerQ) ||
        r.metric.toLowerCase().includes(lowerQ) ||
        r.value.toLowerCase().includes(lowerQ)
      );
    }

    // 2. Фильтры (выпадающие списки)
    if (filterDataset !== 'all') result = result.filter(r => r.dataset === filterDataset);
    if (filterMetric !== 'all') result = result.filter(r => r.metric === filterMetric);
    if (filterStatus !== 'all') result = result.filter(r => r.status === filterStatus);

    // 3. Сортировка
    if (sortOrder === 'asc') result.sort((a, b) => a.numValue - b.numValue);
    if (sortOrder === 'desc') result.sort((a, b) => b.numValue - a.numValue);

    return result;
  }, [searchQuery, filterDataset, filterMetric, filterStatus, sortOrder]);

  return (
    <div className="flex h-screen bg-[#0B0E14] text-[#E2E8F0] font-sans overflow-hidden selection:bg-[#00D2FF] selection:text-black">
      
      {/* САЙДБАР */}
      <aside className="w-20 flex flex-col items-center py-6 border-r border-white/5 bg-[#0B0E14] z-30 shrink-0">
        <div className="w-10 h-10 bg-[#00D2FF] rounded-xl flex items-center justify-center font-bold text-black text-xl mb-10 shadow-[0_0_20px_rgba(0,210,255,0.4)]">R</div>
        <nav className="flex flex-col gap-6 flex-1 w-full">
          <button onClick={() => setActiveTab('overview')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'overview' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'overview' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}<LayoutDashboard className="w-6 h-6" />
          </button>
          <button onClick={() => setActiveTab('upload')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'upload' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'upload' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}<UploadCloud className="w-6 h-6" />
          </button>
          <button onClick={() => setActiveTab('data')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'data' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'data' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}<Database className="w-6 h-6" />
          </button>
          <button onClick={() => setActiveTab('validation')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'validation' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}>
            {activeTab === 'validation' && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00D2FF] rounded-r-md"></div>}<ShieldAlert className="w-6 h-6" />
          </button>
        </nav>
        <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white mt-auto"><Settings className="w-6 h-6" /></button>
      </aside>

      {/* ОСНОВНАЯ ОБЛАСТЬ */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        
        {/* ХЕДЕР (Поиск убран отсюда) */}
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
        </header>

        <div className="flex-1 relative overflow-hidden">
          
          {/* ОБЗОР */}
          {activeTab === 'overview' && (
            <div className="absolute inset-0 flex">
              <NetworkGraph3D status="normal" onClick={() => setActiveTab('data')} />
              <div className="absolute inset-0 bg-gradient-to-r from-[#05080F] via-[#05080F]/70 to-transparent w-[60%] pointer-events-none z-10"></div>
              <div className="absolute top-16 left-16 z-20 max-w-md pointer-events-auto">
                <div className="flex items-center gap-4 mb-4"><div className="h-[2px] w-12 bg-[#00D2FF]"></div><div className="text-[#00D2FF] text-xs font-mono tracking-[0.2em]">SYSTEM OVERVIEW</div></div>
                <h2 className="text-5xl font-light text-white leading-tight mb-6">EXTRACTED<br /><span className="font-bold">KNOWLEDGE.</span></h2>
                <p className="text-base text-gray-400 leading-relaxed mb-8">Автоматическое извлечение конфигураций RAG, наборов данных и метрик из 90 научных публикаций. Проверка валидности цитат.</p>
                <div className="flex items-center gap-3 bg-white/5 border border-white/10 p-3 rounded-lg w-fit cursor-pointer hover:bg-white/10 hover:border-[#00D2FF]/50 transition-all group" onClick={() => setActiveTab('data')}>
                   <div className="w-2 h-2 bg-[#00D2FF] rounded-full animate-pulse"></div>
                   <span className="text-xs text-gray-300 font-medium group-hover:text-white transition-colors">Кликните на ядро, чтобы открыть данные</span>
                   <ArrowUpRight className="w-3 h-3 text-gray-500 group-hover:text-[#00D2FF] transition-colors" />
                </div>
                <div className="flex gap-10 border-t border-white/10 pt-8 mt-8">
                  <div><div className="text-3xl font-mono text-white mb-1">90</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">PDF Docs</div></div>
                  <div><div className="text-3xl font-mono text-[#00D2FF] mb-1">2.4K</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Metrics</div></div>
                  <div><div className="text-3xl font-mono text-[#FF0032] mb-1">12</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Issues</div></div>
                </div>
              </div>
            </div>
          )}

          {/* ЗАГРУЗКА */}
          {activeTab === 'upload' && (
            <div className="absolute inset-0 p-8 flex gap-8 bg-[#0B0E14]">
              <div className="w-1/3 flex flex-col gap-6">
                <div className="bg-[#151A24] border border-white/10 rounded-2xl p-8 flex flex-col items-center justify-center text-center h-64 border-dashed hover:border-[#00D2FF]/50 transition-colors cursor-pointer" onClick={() => { setLogs([]); setUploadStatus('processing'); }}>
                  <UploadCloud className="w-8 h-8 text-[#00D2FF] mb-4" />
                  <h3 className="text-white font-medium mb-2">Загрузить статью</h3>
                  <p className="text-xs text-gray-500 mb-4">Перетащите PDF сюда</p>
                  <button className="px-6 py-2 bg-[#00D2FF] text-black font-bold text-xs uppercase rounded-lg">Выбрать файл</button>
                </div>
              </div>
              <div className="flex-1 bg-[#050505] border border-white/10 rounded-2xl flex flex-col overflow-hidden relative">
                <div className="h-12 border-b border-white/10 flex items-center px-4 gap-2 bg-[#151A24]">
                  <Terminal className="w-4 h-4 text-gray-500" /><span className="text-xs font-mono text-gray-400">AI Pipeline Log</span>
                  {uploadStatus !== 'idle' && uploadStatus !== 'done' && <span className="ml-auto flex items-center gap-2 text-xs text-[#00D2FF]"><Loader2 className="w-3 h-3 animate-spin"/> Processing...</span>}
                  {uploadStatus === 'done' && <span className="ml-auto flex items-center gap-2 text-xs text-green-500"><CheckCircle2 className="w-3 h-3"/> Completed</span>}
                </div>
                <div className="flex-1 p-6 font-mono text-sm overflow-y-auto space-y-2">
                  {logs.length === 0 && <span className="text-gray-600 italic">Ожидание загрузки файла...</span>}
                  {logs.map((log, i) => <div key={i} className="text-gray-300"><span className="text-gray-500 mr-2">{'>'}</span> {log}</div>)}
                  {uploadStatus === 'done' && <div className="mt-4 pt-4 border-t border-white/10"><button onClick={() => setActiveTab('data')} className="px-4 py-2 bg-[#00D2FF] text-black text-xs font-bold rounded hover:bg-white transition-colors">Перейти к данным &rarr;</button></div>}
                </div>
                {uploadStatus !== 'idle' && <div className="h-1 w-full bg-gray-800"><div className="h-full bg-[#00D2FF] transition-all duration-1000 ease-out" style={{ width: uploadStatus === 'processing' ? '25%' : uploadStatus === 'extracting' ? '50%' : uploadStatus === 'validating' ? '75%' : '100%' }}></div></div>}
              </div>
            </div>
          )}

          {/* ДАННЫЕ (Таблица с поиском и фильтрами) */}
          {activeTab === 'data' && (
            <div className="absolute inset-0 p-8 flex flex-col overflow-hidden bg-[#0B0E14]">
              
              {/* ПАНЕЛЬ ПОИСКА И ФИЛЬТРОВ */}
              <div className="flex flex-col gap-4 mb-6 shrink-0 bg-[#151A24] p-5 rounded-xl border border-white/10">
                
                {/* Строка поиска */}
                <div className="relative w-full">
                  <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input 
                    type="text" 
                    placeholder="Поиск по ID, метрике, датасету или значению..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-[#0B0E14] border border-white/10 text-sm text-white rounded-lg py-3 pl-12 pr-10 focus:outline-none focus:border-[#00D2FF]/50 transition-colors"
                  />
                  {searchQuery && (
                    <button onClick={() => setSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Фильтры и сортировка */}
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2 text-xs text-gray-400"><Filter className="w-3 h-3" /> Фильтры:</div>
                  
                  <select value={filterDataset} onChange={(e) => setFilterDataset(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none focus:border-[#00D2FF]/50">
                    <option value="all">Все датасеты</option>
                    <option value="HotpotQA">HotpotQA</option>
                    <option value="Natural Questions">Natural Questions</option>
                    <option value="TriviaQA">TriviaQA</option>
                    <option value="SQuAD">SQuAD</option>
                  </select>

                  <select value={filterMetric} onChange={(e) => setFilterMetric(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none focus:border-[#00D2FF]/50">
                    <option value="all">Все метрики</option>
                    <option value="NDCG@10">NDCG@10</option>
                    <option value="Recall@5">Recall@5</option>
                    <option value="F1-Score">F1-Score</option>
                    <option value="EM">EM</option>
                    <option value="Latency">Latency</option>
                  </select>

                  <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none focus:border-[#00D2FF]/50">
                    <option value="all">Все статусы</option>
                    <option value="valid">Valid</option>
                    <option value="critical">Error</option>
                    <option value="warning">Warning</option>
                  </select>

                  <div className="flex-1"></div>
                  
                  {/* Сортировка */}
                  <div className="flex items-center gap-2 border border-white/10 rounded-lg p-1 bg-[#0B0E14]">
                    <span className="text-[10px] text-gray-500 px-2 uppercase tracking-wider">Сортировка</span>
                    <button onClick={() => setSortOrder(sortOrder === 'desc' ? 'none' : 'desc')} className={`p-1.5 rounded ${sortOrder === 'desc' ? 'bg-[#00D2FF] text-black' : 'text-gray-400 hover:text-white'}`} title="По убыванию"><ArrowDownWideNarrow className="w-4 h-4" /></button>
                    <button onClick={() => setSortOrder(sortOrder === 'asc' ? 'none' : 'asc')} className={`p-1.5 rounded ${sortOrder === 'asc' ? 'bg-[#00D2FF] text-black' : 'text-gray-400 hover:text-white'}`} title="По возрастанию"><ArrowUpNarrowWide className="w-4 h-4" /></button>
                  </div>
                </div>
              </div>

              {/* ТАБЛИЦА */}
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
                    {processedResults.length === 0 ? (
                      <tr><td colSpan="7" className="p-8 text-center text-gray-500">По вашему запросу ничего не найдено. Попробуйте изменить фильтры или запрос.</td></tr>
                    ) : (
                      processedResults.map((row) => (
                        <tr key={row.id} onClick={() => setSelectedResult(row)} className="border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors group">
                          <td className="p-4 font-mono text-gray-400">{row.id}</td>
                          <td className="p-4 text-white">{row.config}</td>
                          <td className="p-4 text-gray-300">{row.dataset}</td>
                          <td className="p-4 text-gray-300 font-mono">{row.metric}</td>
                          <td className="p-4 font-mono text-white">{row.value}</td>
                          <td className="p-4 text-[#00D2FF] text-xs flex items-center gap-1">Page {row.source.page} <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" /></td>
                          <td className="p-4">
                            {row.status === 'valid' && <span className="text-green-400 bg-green-400/10 px-2 py-1 rounded text-xs">Valid</span>}
                            {row.status === 'critical' && <span className="text-[#FF0032] bg-[#FF0032]/10 px-2 py-1 rounded text-xs">Error</span>}
                            {row.status === 'warning' && <span className="text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded text-xs">Warning</span>}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ВАЛИДАЦИЯ */}
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
                <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-2"><FileText className="w-3 h-3" /> Цитата (source_fragment)</h4>
                <div className="bg-[#151A24] border-l-2 border-[#00D2FF] p-4 rounded-r-lg relative group">
                  <p className="text-sm text-gray-300 font-mono italic leading-relaxed">"{selectedResult.source.text}"</p>
                  <p className="text-xs text-gray-500 mt-3 border-t border-white/5 pt-2">Страница PDF: {selectedResult.source.page}</p>
                  <button onClick={() => setIsPdfOpen(true)} className="absolute top-2 right-2 p-2 bg-[#00D2FF]/10 text-[#00D2FF] rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[#00D2FF]/20" title="Открыть в PDF"><ExternalLink className="w-4 h-4" /></button>
                </div>
                <button onClick={() => setIsPdfOpen(true)} className="mt-3 w-full py-2 border border-[#00D2FF]/30 text-[#00D2FF] text-xs font-medium rounded hover:bg-[#00D2FF]/10 transition-colors flex items-center justify-center gap-2">
                  <FileText className="w-4 h-4" /> Открыть PDF на стр. {selectedResult.source.page}
                </button>
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

      {/* МОДАЛЬНОЕ ОКНО PDF */}
      {isPdfOpen && selectedResult && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-8">
          <div className="w-full max-w-4xl h-full max-h-[90vh] bg-[#1A1A1A] rounded-xl flex flex-col overflow-hidden border border-white/10 shadow-2xl">
            <div className="h-12 bg-[#252525] flex items-center justify-between px-4 border-b border-white/10">
              <div className="flex items-center gap-3 text-gray-300 text-sm"><FileText className="w-4 h-4 text-[#FF0032]" /><span className="font-medium">article_test_45.pdf</span><span className="text-gray-500 text-xs px-2 bg-white/5 rounded">Страница {selectedResult.source.page}</span></div>
              <div className="flex items-center gap-2">
                <button className="p-1.5 hover:bg-white/10 rounded text-gray-400"><Download className="w-4 h-4" /></button>
                <button onClick={() => setIsPdfOpen(false)} className="p-1.5 hover:bg-white/10 rounded text-gray-400"><X className="w-4 h-4" /></button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto bg-[#2A2A2A] p-8 flex justify-center">
              <div className="w-[800px] bg-white min-h-full shadow-2xl p-12 text-black font-serif">
                <h1 className="text-2xl font-bold mb-6 text-center">Evaluating Retrieval-Augmented Generation Systems on Scientific Corpora</h1>
                <p className="text-sm text-center text-gray-600 mb-8">John Doe, Jane Smith — VINITI RAS</p>
                <h2 className="text-lg font-bold mb-4">4. Results</h2>
                <p className="text-base leading-relaxed mb-6 text-justify text-gray-800">
                  Table 3 presents the main results of our experiments. As can be seen, the proposed configuration demonstrates strong performance across various metrics. 
                  <mark className="bg-yellow-300 px-1 rounded-sm text-black font-medium shadow-sm transition-colors duration-500">{selectedResult.source.text}</mark>
                  This indicates that the system is capable of effectively retrieving and utilizing relevant information.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}