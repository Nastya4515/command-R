import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  LayoutDashboard, Database, Settings, 
  Search, FileText, X, CheckCircle2, 
  AlertTriangle, Filter, UploadCloud, Loader2, Terminal,
  Download, ExternalLink, ArrowUpDown, ChevronLeft, ChevronRight,
  Sun, Network, Image as ImageIcon, SearchX
} from 'lucide-react';
import NetworkGraph3D from './NetworkGraph3D';

// Расширили данные для демонстрации пагинации
const allMockResults = [
  { id: 'R001', domain: 'RAG', config: 'C01', dataset: 'HotpotQA', metric: 'NDCG@10', value: '0.85', numValue: 0.85, origin: 'primary', status: 'valid', issue: null, source: { type: 'text', page: 7, text: 'Our system achieves an NDCG@10 of 0.85, outperforming the baseline by 12%.' } },
  { id: 'R002', domain: 'RAG', config: 'C02', dataset: 'TriviaQA', metric: 'F1-Score', value: '1.15', numValue: 1.15, origin: 'cited', status: 'critical', issue: 'metric_scale', source: { type: 'text', page: 9, text: 'We observe an F1-score of 1.15 on the test split.' } },
  { id: 'R003', domain: 'RAG', config: 'C03', dataset: 'Natural Questions', metric: 'EM', value: '0.76', numValue: 0.76, origin: 'primary', status: 'valid', issue: null, source: { type: 'text', page: 12, text: 'Exact Match (EM) reaches 0.76 on the NQ dataset.' } },
  { id: 'R004', domain: 'RAG', config: 'C01', dataset: 'SQuAD', metric: 'Latency', value: '230', numValue: 230, origin: 'primary', status: 'warning', issue: 'direction', source: { type: 'text', page: 10, text: 'Average latency is 230 ms per query.' } },
  { id: 'R005', domain: 'RAG', config: 'C04', dataset: 'HotpotQA', metric: 'Recall@5', value: '0.92', numValue: 0.92, origin: 'primary', status: 'valid', issue: null, source: { type: 'text', page: 8, text: 'The recall at 5 documents reached 0.92.' } },
  { id: 'S001', domain: 'Solar', config: 'Perovskite-A', dataset: 'FAPbI3', metric: 'PCE', value: '22.5%', numValue: 22.5, origin: 'primary', status: 'valid', issue: null, source: { type: 'text', page: 4, text: 'The champion device achieved a power conversion efficiency of 22.5%.' } },
  { id: 'S002', domain: 'Solar', config: 'CIGS-B', dataset: 'CIGS', metric: 'Voc', value: '0.68 V', numValue: 0.68, origin: 'primary', status: 'warning', issue: 'missing_source', source: { type: 'image', page: 6, figure: 'Figure 3', text: 'Значение Voc (0.68 V) извлечено с графика вольт-амперной характеристики (Рис. 3) с помощью Vision-модели.' } },
  { id: 'S003', domain: 'Solar', config: 'CdTe-C', dataset: 'CdTe', metric: 'PCE', value: '18.2%', numValue: 18.2, origin: 'primary', status: 'valid', issue: null, source: { type: 'text', page: 8, text: 'We report a PCE of 18.2% for the CdTe solar cell.' } },
  { id: 'S004', domain: 'Solar', config: 'Perovskite-B', dataset: 'MAPbI3', metric: 'Jsc', value: '24.1 mA/cm2', numValue: 24.1, origin: 'primary', status: 'valid', issue: null, source: { type: 'text', page: 5, text: 'The short-circuit current density (Jsc) was measured at 24.1 mA/cm2.' } },
  { id: 'S005', domain: 'Solar', config: 'CIGS-A', dataset: 'CIGS', metric: 'FF', value: '78.5%', numValue: 78.5, origin: 'cited', status: 'valid', issue: null, source: { type: 'text', page: 11, text: 'Fill factor (FF) reached 78.5% for the best performing cell.' } },
];

export default function RAGDashboard() {
  const [activeTab, setActiveTab] = useState('overview'); 
  const [selectedResult, setSelectedResult] = useState(null);
  const [isPdfOpen, setIsPdfOpen] = useState(false);

  // Фильтры и поиск
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDomain, setFilterDomain] = useState('all'); 
  const [filterStatus, setFilterStatus] = useState('all');

  // Сортировка
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

  // Пагинация
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5; // По 5 строк на страницу

  const [uploadStatus, setUploadStatus] = useState('idle'); 
  const [logs, setLogs] = useState([]);
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Сброс страницы при изменении фильтров
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, filterDomain, filterStatus]);

  useEffect(() => {
    if (uploadStatus === 'processing') {
      const addLog = (text) => setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${text}`]);
      addLog("Старт Multimodal AI Pipeline...");
      const timer1 = setTimeout(() => { addLog("Анализ текста (OCR + NLP)..."); addLog("Анализ графиков (Vision Model)..."); setUploadStatus('extracting'); }, 1500);
      const timer2 = setTimeout(() => { addLog("Извлечение метрик и проверка правил..."); }, 3000);
      const timer3 = setTimeout(() => { addLog("Готово."); setUploadStatus('done'); }, 4500);
      return () => { clearTimeout(timer1); clearTimeout(timer2); clearTimeout(timer3); };
    }
  }, [uploadStatus]);

  // --- ЛОГИКА ФИЛЬТРАЦИИ И СОРТИРОВКИ ---
  const filteredResults = useMemo(() => {
    let result = [...allMockResults];
    
    if (searchQuery.trim() !== '') {
      const lowerQ = searchQuery.toLowerCase();
      result = result.filter(r => 
        r.id.toLowerCase().includes(lowerQ) || r.config.toLowerCase().includes(lowerQ) ||
        r.dataset.toLowerCase().includes(lowerQ) || r.metric.toLowerCase().includes(lowerQ)
      );
    }
    if (filterDomain !== 'all') result = result.filter(r => r.domain === filterDomain);
    if (filterStatus !== 'all') result = result.filter(r => r.status === filterStatus);
    
    return result;
  }, [searchQuery, filterDomain, filterStatus]);

  const sortedResults = useMemo(() => {
    let sortableItems = [...filteredResults];
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let aValue = a[sortConfig.key];
        let bValue = b[sortConfig.key];

        // Для колонки Value используем числовое значение
        if (sortConfig.key === 'value') {
          aValue = a.numValue;
          bValue = b.numValue;
        }

        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }
    return sortableItems;
  }, [filteredResults, sortConfig]);

  // --- ЛОГИКА ПАГИНАЦИИ ---
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentItems = sortedResults.slice(indexOfFirstItem, indexOfLastItem);
  const totalPages = Math.ceil(sortedResults.length / itemsPerPage);

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    } else if (sortConfig.key === key && sortConfig.direction === 'desc') {
      direction = 'asc'; // Сброс или продолжение цикла
    }
    setSortConfig({ key, direction });
  };

  const handleExportCSV = () => {
    const headers = ['ID', 'Domain', 'Configuration', 'Dataset', 'Metric', 'Value', 'Status', 'Source_Page'];
    const csvRows = [headers.join(','), ...sortedResults.map(r => [r.id, r.domain, r.config, r.dataset, r.metric, r.value, r.status, r.source.page].join(','))];
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `all_results_export.csv`;
    link.click();
  };

  // Реальная загрузка PDF на бекенд (POST /api/upload)
  const handleFileSelected = (file) => {
    if (!file) return;
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    setLogs([]);
    setSelectedFile(null);
    if (!isPdf) {
      setUploadStatus('error');
      setLogs([`[${new Date().toLocaleTimeString()}] Ошибка: можно загружать только PDF-файлы`]);
      return;
    }

    setSelectedFile(file);
    setUploadStatus('uploading');
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const resp = JSON.parse(xhr.responseText);
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Файл загружен на сервер: ${resp.originalName} (${(resp.size / 1024).toFixed(1)} КБ)`]);
        setUploadStatus('processing'); // дальше подхватывает эффект пайплайна
      } else {
        let msg = 'Ошибка сервера';
        try { msg = JSON.parse(xhr.responseText).error || msg; } catch { /* не JSON */ }
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Ошибка загрузки: ${msg}`]);
        setUploadStatus('error');
      }
    };
    xhr.onerror = () => {
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Ошибка: сервер недоступен (запущен ли "npm run server"?)`]);
      setUploadStatus('error');
    };
    xhr.send(formData);
  };

  const isUploadBusy = ['uploading', 'processing', 'extracting'].includes(uploadStatus);

  return (
    <div className="flex h-screen bg-[#0B0E14] text-[#E2E8F0] font-sans overflow-hidden selection:bg-[#00D2FF] selection:text-black">
      
      {/* САЙДБАР */}
      <aside className="w-20 flex flex-col items-center py-6 border-r border-white/5 bg-[#0B0E14] z-30 shrink-0">
        <div className="w-10 h-10 bg-[#00D2FF] rounded-xl flex items-center justify-center font-bold text-black text-xl mb-10 shadow-[0_0_20px_rgba(0,210,255,0.4)]">R</div>
        <nav className="flex flex-col gap-6 flex-1 w-full">
          <button onClick={() => setActiveTab('overview')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'overview' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><LayoutDashboard className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('upload')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'upload' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><UploadCloud className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('data')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'data' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><Database className="w-6 h-6" /></button>
        </nav>
        <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white mt-auto"><Settings className="w-6 h-6" /></button>
      </aside>

      {/* ОСНОВНАЯ ОБЛАСТЬ */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        <header className="h-20 flex items-center justify-between px-8 border-b border-white/5 shrink-0 z-20 bg-[#0B0E14]/80 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-medium text-white">
              {activeTab === 'overview' && 'Системный обзор'}
              {activeTab === 'upload' && 'Обработка PDF (Multimodal AI)'}
              {activeTab === 'data' && 'Единая база знаний'}
            </h1>
          </div>
        </header>

        <div className="flex-1 relative overflow-hidden">
          
          {/* ОБЗОР */}
          {activeTab === 'overview' && (
            <div className="absolute inset-0 flex">
              <NetworkGraph3D status="normal" onClick={() => setActiveTab('data')} />
              <div className="absolute inset-0 bg-gradient-to-r from-[#05080F] via-[#05080F]/70 to-transparent w-[60%] pointer-events-none z-10"></div>
              <div className="absolute top-16 left-16 z-20 max-w-md pointer-events-auto">
                <div className="flex items-center gap-4 mb-4"><div className="h-[2px] w-12 bg-[#00D2FF]"></div><div className="text-[#00D2FF] text-xs font-mono tracking-[0.2em]">MULTIMODAL SYSTEM</div></div>
                <h2 className="text-5xl font-light text-white leading-tight mb-6">EXTRACTED<br /><span className="font-bold">KNOWLEDGE.</span></h2>
                <p className="text-base text-gray-400 leading-relaxed mb-8">Единая база данных для двух предметных областей. Извлечение текста и графиков.</p>
                <div className="flex gap-10 border-t border-white/10 pt-8 mt-8">
                  <div><div className="text-3xl font-mono text-white mb-1">135</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">PDF Docs</div></div>
                  <div><div className="text-3xl font-mono text-[#00D2FF] mb-1">3.6K</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Metrics</div></div>
                  <div><div className="text-3xl font-mono text-[#FF0032] mb-1">19</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Issues</div></div>
                </div>
              </div>
            </div>
          )}

          {/* ЗАГРУЗКА */}
          {activeTab === 'upload' && (
            <div className="absolute inset-0 p-8 flex gap-8 bg-[#0B0E14]">
              <div className="w-1/3 flex flex-col gap-6">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(e) => { handleFileSelected(e.target.files?.[0]); e.target.value = ''; }}
                />
                <div
                  className={`bg-[#151A24] border border-white/10 rounded-2xl p-8 flex flex-col items-center justify-center text-center h-64 border-dashed transition-colors ${isUploadBusy ? 'opacity-60 cursor-wait' : 'hover:border-[#00D2FF]/50 cursor-pointer'}`}
                  onClick={() => { if (!isUploadBusy) fileInputRef.current?.click(); }}
                >
                  <UploadCloud className="w-8 h-8 text-[#00D2FF] mb-4" />
                  <h3 className="text-white font-medium mb-2">Загрузить PDF</h3>
                  <p className="text-xs text-gray-500 mb-4">Файл отправится на сервер, затем ИИ определит область</p>
                  <button className="px-6 py-2 bg-[#00D2FF] text-black font-bold text-xs uppercase rounded-lg">Выбрать файл</button>
                </div>

                {selectedFile && (
                  <div className="bg-[#151A24] border border-white/10 rounded-xl p-4">
                    <div className="flex items-center gap-2 text-sm text-white mb-2">
                      <FileText className="w-4 h-4 text-[#00D2FF] shrink-0" />
                      <span className="truncate">{selectedFile.name}</span>
                      <span className="text-xs text-gray-500 shrink-0 ml-auto">{(selectedFile.size / 1024).toFixed(1)} КБ</span>
                    </div>
                    {uploadStatus === 'uploading' && (
                      <div className="h-1.5 bg-white/10 rounded overflow-hidden">
                        <div className="h-full bg-[#00D2FF] transition-all" style={{ width: `${uploadProgress}%` }}></div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="flex-1 bg-[#050505] border border-white/10 rounded-2xl flex flex-col overflow-hidden relative">
                <div className="h-12 border-b border-white/10 flex items-center px-4 gap-2 bg-[#151A24]">
                  <Terminal className="w-4 h-4 text-gray-500" /><span className="text-xs font-mono text-gray-400">Multimodal AI Pipeline Log</span>
                  {isUploadBusy && <span className="ml-auto flex items-center gap-2 text-xs text-[#00D2FF]"><Loader2 className="w-3 h-3 animate-spin"/> {uploadStatus === 'uploading' ? `Uploading... ${uploadProgress}%` : 'Processing...'}</span>}
                  {uploadStatus === 'error' && <span className="ml-auto flex items-center gap-2 text-xs text-[#FF0032]"><AlertTriangle className="w-3 h-3"/> Error</span>}
                  {uploadStatus === 'done' && <span className="ml-auto flex items-center gap-2 text-xs text-green-500"><CheckCircle2 className="w-3 h-3"/> Completed</span>}
                </div>
                <div className="flex-1 p-6 font-mono text-sm overflow-y-auto space-y-2">
                  {logs.length === 0 && <span className="text-gray-600 italic">Ожидание файла...</span>}
                  {logs.map((log, i) => <div key={i} className="text-gray-300"><span className="text-gray-500 mr-2">{'>'}</span> {log}</div>)}
                </div>
              </div>
            </div>
          )}

          {/* ДАННЫЕ (Таблица) */}
          {activeTab === 'data' && (
            <div className="absolute inset-0 p-8 flex flex-col overflow-hidden bg-[#0B0E14]">
              
              <div className="flex flex-col gap-4 mb-6 shrink-0 bg-[#151A24] p-5 rounded-xl border border-white/10">
                <div className="flex gap-4 items-center">
                  <div className="relative flex-1">
                    <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input type="text" placeholder="Поиск по всем областям..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full bg-[#0B0E14] border border-white/10 text-sm text-white rounded-lg py-2.5 pl-12 pr-10 focus:outline-none" />
                  </div>
                  <button onClick={handleExportCSV} className="flex items-center gap-2 px-4 py-2.5 bg-white/5 border border-white/10 text-white text-xs font-bold uppercase rounded-lg hover:bg-white/10 transition-colors shrink-0">
                    <Download className="w-4 h-4" /> Экспорт CSV
                  </button>
                </div>
                
                <div className="flex items-center gap-4">
                   <div className="flex items-center gap-2 text-xs text-gray-400"><Filter className="w-3 h-3" /> Фильтры:</div>
                   <select value={filterDomain} onChange={(e) => setFilterDomain(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none">
                    <option value="all">Все области</option>
                    <option value="Solar">Только Solar Cells</option>
                    <option value="RAG">Только RAG Systems</option>
                  </select>
                   <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none">
                    <option value="all">Все статусы</option>
                    <option value="valid">Valid</option>
                    <option value="critical">Error</option>
                    <option value="warning">Warning</option>
                  </select>
                </div>
              </div>

              {/* ТАБЛИЦА */}
              <div className="flex-1 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50 flex flex-col">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-[#151A24] sticky top-0 border-b border-white/10 z-10">
                    <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                      {[
                        { label: 'ID', key: 'id' },
                        { label: 'Область', key: 'domain' },
                        { label: 'Объект / Конфиг', key: 'config' },
                        { label: 'Материал / Датасет', key: 'dataset' },
                        { label: 'Метрика', key: 'metric' },
                        { label: 'Значение', key: 'value' },
                        { label: 'Источник', key: 'source_page' },
                        { label: 'Статус', key: 'status' }
                      ].map((col) => (
                        <th 
                          key={col.key} 
                          onClick={() => handleSort(col.key)}
                          className="p-4 font-normal cursor-pointer hover:bg-white/5 hover:text-white transition-colors group"
                        >
                          <div className="flex items-center gap-2">
                            {col.label}
                            <ArrowUpDown className={`w-3 h-3 ${sortConfig.key === col.key ? 'text-[#00D2FF]' : 'text-gray-600 opacity-0 group-hover:opacity-100'}`} />
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {currentItems.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="p-12 text-center">
                          {/* КРАСИВЫЙ ПУСТОЙ ЭКРАН */}
                          <div className="flex flex-col items-center justify-center text-gray-500">
                            <SearchX className="w-12 h-12 mb-4 text-gray-600" />
                            <h3 className="text-lg font-medium text-white mb-1">Ничего не найдено</h3>
                            <p className="text-sm">Попробуйте изменить поисковый запрос или сбросить фильтры.</p>
                            <button 
                              onClick={() => { setSearchQuery(''); setFilterDomain('all'); setFilterStatus('all'); }}
                              className="mt-4 px-4 py-2 bg-[#00D2FF]/10 text-[#00D2FF] text-xs font-medium rounded hover:bg-[#00D2FF]/20 transition-colors"
                            >
                              Сбросить всё
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      currentItems.map((row) => (
                        <tr key={row.id} onClick={() => setSelectedResult(row)} className="border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors group">
                          <td className="p-4 font-mono text-gray-400">{row.id}</td>
                          <td className="p-4">
                            {row.domain === 'Solar' 
                              ? <span className="flex items-center gap-1 text-xs text-yellow-400"><Sun className="w-3 h-3"/> Solar</span>
                              : <span className="flex items-center gap-1 text-xs text-[#00D2FF]"><Network className="w-3 h-3"/> RAG</span>
                            }
                          </td>
                          <td className="p-4 text-white">{row.config}</td>
                          <td className="p-4 text-gray-300">{row.dataset}</td>
                          <td className="p-4 text-gray-300 font-mono">{row.metric}</td>
                          <td className="p-4 font-mono text-white">{row.value}</td>
                          <td className={`p-4 text-xs flex items-center gap-1 ${row.domain === 'Solar' ? 'text-yellow-400' : 'text-[#00D2FF]'}`}>
                            {row.source.type === 'image' ? <><ImageIcon className="w-3 h-3"/> Рис. {row.source.figure}</> : `Page ${row.source.page}`}
                          </td>
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

                {/* ПАГИНАЦИЯ (Footer таблицы) */}
                <div className="mt-auto p-4 border-t border-white/10 bg-[#151A24] flex items-center justify-between shrink-0 rounded-b-xl">
                  <span className="text-xs text-gray-500">
                    Показано <span className="text-white">{filteredResults.length > 0 ? indexOfFirstItem + 1 : 0}</span> - <span className="text-white">{Math.min(indexOfLastItem, filteredResults.length)}</span> из <span className="text-white">{filteredResults.length}</span> записей
                  </span>
                  
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))} 
                      disabled={currentPage === 1}
                      className="p-1.5 rounded bg-[#0B0E14] border border-white/10 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-xs font-mono text-gray-300 px-2">Стр. {currentPage} из {totalPages || 1}</span>
                    <button 
                      onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))} 
                      disabled={currentPage === totalPages || totalPages === 0}
                      className="p-1.5 rounded bg-[#0B0E14] border border-white/10 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>

              </div>
            </div>
          )}

        </div>
      </main>

      {/* DRAWER */}
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
              <button onClick={() => setSelectedResult(null)} className="p-2 hover:bg-white/10 rounded-full text-gray-400"><X className="w-5 h-5" /></button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
              <div>
                <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-2">
                  {selectedResult.source.type === 'image' ? <><ImageIcon className="w-3 h-3" /> Данные из изображения</> : <><FileText className="w-3 h-3" /> Цитата (текст)</>}
                </h4>
                <div className={`bg-[#151A24] border-l-2 p-4 rounded-r-lg relative group ${selectedResult.source.type === 'image' ? 'border-yellow-400' : 'border-[#00D2FF]'}`}>
                  <p className="text-sm text-gray-300 font-mono italic leading-relaxed">"{selectedResult.source.text}"</p>
                  <p className="text-xs text-gray-500 mt-3 border-t border-white/5 pt-2">
                    {selectedResult.source.type === 'image' ? `Источник: ${selectedResult.source.figure}, Стр. ${selectedResult.source.page}` : `Страница PDF: ${selectedResult.source.page}`}
                  </p>
                </div>
                <button onClick={() => setIsPdfOpen(true)} className="mt-3 w-full py-2 border border-white/20 text-gray-300 text-xs font-medium rounded hover:bg-white/10 transition-colors flex items-center justify-center gap-2">
                  <FileText className="w-4 h-4" /> Открыть источник
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* МОДАЛКА ИСТОЧНИКА */}
      {isPdfOpen && selectedResult && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-8">
          <div className="w-full max-w-4xl h-full max-h-[90vh] bg-[#1A1A1A] rounded-xl flex flex-col overflow-hidden border border-white/10 shadow-2xl">
            <div className="h-12 bg-[#252525] flex items-center justify-between px-4 border-b border-white/10">
              <div className="flex items-center gap-3 text-gray-300 text-sm">
                {selectedResult.source.type === 'image' ? <ImageIcon className="w-4 h-4 text-yellow-400" /> : <FileText className="w-4 h-4 text-[#FF0032]" />}
                <span className="font-medium">article_test_45.pdf</span>
                <span className="text-gray-500 text-xs px-2 bg-white/5 rounded">Страница {selectedResult.source.page}</span>
              </div>
              <button onClick={() => setIsPdfOpen(false)} className="p-1.5 hover:bg-white/10 rounded text-gray-400"><X className="w-4 h-4" /></button>
            </div>
            
            <div className="flex-1 overflow-y-auto bg-[#2A2A2A] p-8 flex justify-center">
              <div className="w-[800px] bg-white min-h-full shadow-2xl p-12 text-black font-serif">
                <h1 className="text-2xl font-bold mb-6 text-center">Scientific Publication Extract</h1>
                
                {selectedResult.source.type === 'image' ? (
                   <div className="mt-8 border-2 border-dashed border-gray-400 bg-gray-100 rounded-lg p-8 flex flex-col items-center justify-center text-center relative">
                      <ImageIcon className="w-20 h-20 text-gray-400 mb-4" />
                      <h3 className="text-xl font-bold mb-2">{selectedResult.source.figure}: Graph</h3>
                      <div className="bg-yellow-200 p-2 border border-yellow-400 font-mono text-sm shadow-sm">Extracted: {selectedResult.metric} = {selectedResult.value}</div>
                   </div>
                ) : (
                  <p className="text-base leading-relaxed mb-6 text-justify text-gray-800">
                    <mark className="bg-yellow-300 px-1 rounded-sm text-black font-medium">{selectedResult.source.text}</mark>
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}