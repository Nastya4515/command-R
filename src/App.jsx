import { useState, useEffect, useRef } from 'react';
import { 
  LayoutDashboard, Database, Settings, 
  Search, FileText, X, CheckCircle2, 
  AlertTriangle, Filter, UploadCloud, Loader2, Terminal,
  Download, ArrowUpDown, ChevronLeft, ChevronRight,
  Network, SearchX, Table2
} from 'lucide-react';
import NetworkGraph3D from './NetworkGraph3D';

const API = '/api';
const PER_PAGE = 10;
const AREA_LABELS = { rag: 'RAG', solar: 'Solar' };

export default function RAGDashboard() {
  const [activeTab, setActiveTab] = useState('overview'); 
  const [selectedResult, setSelectedResult] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [isPdfOpen, setIsPdfOpen] = useState(false);

  // Области и наборы (мультиобластной режим v2)
  const [areasInfo, setAreasInfo] = useState(null);
  const [currentArea, setCurrentArea] = useState('rag');
  const [currentSet, setCurrentSet] = useState('test');
  const [activeTable, setActiveTable] = useState('results');
  const [tableData, setTableData] = useState({ columns: [], items: [], total: 0 });
  const [tablePage, setTablePage] = useState(1);
  const [uploadArea, setUploadArea] = useState('rag');

  // Фильтры и поиск (серверные)
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [filterMetric, setFilterMetric] = useState('all'); 
  const [filterOrigin, setFilterOrigin] = useState('all');
  const [withIssues, setWithIssues] = useState(false);

  // Данные с бекенда
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [stats, setStats] = useState(null);
  const [facets, setFacets] = useState({ metrics: [], check_names: [], publications: [] });

  // Сортировка (серверная)
  const [sortConfig, setSortConfig] = useState({ key: 'result_id', direction: 'asc' });

  // Пагинация (серверная)
  const [currentPage, setCurrentPage] = useState(1);

  // Замечания и публикации
  const [issuesData, setIssuesData] = useState({ total: 0, items: [] });
  const [issueCheck, setIssueCheck] = useState('all');
  const [issuePid, setIssuePid] = useState('all');
  const [issuePage, setIssuePage] = useState(1);
  const [pubs, setPubs] = useState([]);
  const [selectedPub, setSelectedPub] = useState(null);

  const [uploadStatus, setUploadStatus] = useState('idle'); 
  const [logs, setLogs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [jobPid, setJobPid] = useState(null);
  const [jobResults, setJobResults] = useState(0);
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);

  // Запрет браузеру открывать PDF при дропе мимо зоны загрузки
  useEffect(() => {
    const block = (e) => e.preventDefault();
    window.addEventListener('dragover', block);
    window.addEventListener('drop', block);
    return () => { window.removeEventListener('dragover', block); window.removeEventListener('drop', block); };
  }, []);

  // Дебаунс поиска
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(searchQuery), 350);
    return () => clearTimeout(t);
  }, [searchQuery]);

  // Сброс страницы при смене фильтров
  const updateFilter = (setter) => (value) => { setter(value); setCurrentPage(1); };

  // Сводка и фасеты — один раз
  const refreshData = () => {
    fetch(`${API}/stats`).then(r => r.json()).then(setStats).catch(() => setApiError('Бекенд недоступен (uvicorn запущен?)'));
    fetch(`${API}/facets`).then(r => r.json()).then(setFacets).catch(() => {});
  };
  useEffect(() => {
    fetch(`${API}/areas`).then(r => r.json()).then(d => {
      setAreasInfo(d);
      setCurrentArea(d.current.area);
      setCurrentSet(d.current.set);
    }).catch(() => {});
    refreshData();
  }, []);

  // Переключение области/набора на сервере
  const switchSelection = (area, setName) => {
    fetch(`${API}/select?area=${area}&set_name=${setName}`, { method: 'POST' })
      .then(r => r.json())
      .then(() => {
        setCurrentArea(area);
        setCurrentSet(setName);
        setCurrentPage(1);
        setTablePage(1);
        setActiveTable('results');
        refreshData();
      })
      .catch(() => {});
  };

  // Универсальный просмотр любой из 7 таблиц области
  useEffect(() => {
    if (activeTab !== 'tables') return;
    const params = new URLSearchParams({ page: String(tablePage), per_page: '20' });
    fetch(`${API}/tables/${activeTable}?${params}`)
      .then(r => r.json())
      .then(setTableData)
      .catch(() => setTableData({ columns: [], items: [], total: 0 }));
  }, [activeTab, activeTable, tablePage, currentArea, currentSet]);

  // Загрузка результатов при изменении фильтров/сортировки/страницы
  useEffect(() => {
    if (activeTab !== 'data') return;
    queueMicrotask(() => { setLoading(true); setApiError(null); });
    const params = new URLSearchParams({
      q: debouncedQuery,
      sort: sortConfig.key,
      direction: sortConfig.direction,
      page: String(currentPage),
      per_page: String(PER_PAGE),
    });
    if (filterMetric !== 'all') params.set('metric', filterMetric);
    if (filterOrigin !== 'all') params.set('origin', filterOrigin);
    if (withIssues) params.set('with_issues', 'true');
    fetch(`${API}/results?${params}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => { setItems(data.items); setTotal(data.total); setLoading(false); })
      .catch(e => { setApiError(`Ошибка API: ${e.message}`); setLoading(false); });
  }, [activeTab, debouncedQuery, filterMetric, filterOrigin, withIssues, sortConfig, currentPage]);

  // Замечания
  useEffect(() => {
    if (activeTab !== 'issues') return;
    const params = new URLSearchParams({ page: String(issuePage), per_page: '20' });
    if (issueCheck !== 'all') params.set('check_name', issueCheck);
    if (issuePid !== 'all') params.set('pid', issuePid);
    fetch(`${API}/issues?${params}`).then(r => r.json()).then(setIssuesData).catch(() => {});
  }, [activeTab, issueCheck, issuePid, issuePage]);

  // Публикации
  useEffect(() => {
    if (activeTab !== 'pubs') return;
    fetch(`${API}/publications`).then(r => r.json()).then(setPubs).catch(() => {});
  }, [activeTab]);

  useEffect(() => {
    if (!selectedPub) return;
    fetch(`${API}/publications/${selectedPub.publication_id}`).then(r => r.json()).then(setSelectedPub).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPub?.publication_id]);

  // Карточка записи со связями
  useEffect(() => {
    if (!selectedResult) return;
    fetch(`${API}/results/${selectedResult.publication_id}/${selectedResult.result_id}`)
      .then(r => r.json())
      .then(setSelectedDetail)
      .catch(() => setSelectedDetail(null));
  }, [selectedResult]);

  // Опрос фоновой задачи конвейера на бэкенде
  useEffect(() => {
    if (uploadStatus !== 'processing' || !jobId) return;
    const timer = setInterval(async () => {
      try {
        const r = await fetch(`${API}/jobs/${jobId}`);
        if (!r.ok) return;
        const job = await r.json();
        const stamp = new Date().toLocaleTimeString();
        setLogs([
          `[${stamp}] Статья: ${job.pid} · шаг: ${job.step || 'запуск'}`,
          ...job.log.map(l => `[конвейер] ${l}`),
        ]);
        if (job.status === 'done') {
          setJobResults(job.results_count);
          setUploadStatus('done');
          fetch(`${API}/stats`).then(res => res.json()).then(setStats).catch(() => {});
          fetch(`${API}/facets`).then(res => res.json()).then(setFacets).catch(() => {});
        } else if (job.status === 'error') {
          setLogs(prev => [...prev, `[${stamp}] Ошибка: ${job.error}`]);
          setUploadStatus('error');
        }
      } catch { /* разовый сбой опроса — повторим */ }
    }, 1500);
    return () => clearInterval(timer);
  }, [uploadStatus, jobId]);

  const totalPages = Math.ceil(total / PER_PAGE);
  const indexOfFirstItem = (currentPage - 1) * PER_PAGE;

  const handleSort = (key) => {
    setSortConfig(prev => ({ key, direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc' }));
  };

  const handleExportCSV = () => {
    const params = new URLSearchParams({ q: debouncedQuery });
    if (filterMetric !== 'all') params.set('metric', filterMetric);
    if (filterOrigin !== 'all') params.set('origin', filterOrigin);
    window.location.href = `${API}/export?${params}`;
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
    xhr.open('POST', `${API}/upload?area=${uploadArea}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const resp = JSON.parse(xhr.responseText);
        setJobId(resp.job_id);
        setJobPid(resp.pid);
        setLogs(prev => [...prev,
          `[${new Date().toLocaleTimeString()}] Файл загружен на сервер: ${resp.originalName} (${(resp.size / 1024).toFixed(1)} КБ)`,
          `[${new Date().toLocaleTimeString()}] Запущен конвейер извлечения (задача ${resp.job_id})...`]);
        setUploadStatus('processing');
      } else {
        let msg = 'Ошибка сервера';
        try { msg = JSON.parse(xhr.responseText).error || JSON.parse(xhr.responseText).detail || msg; } catch { /* не JSON */ }
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Ошибка загрузки: ${msg}`]);
        setUploadStatus('error');
      }
    };
    xhr.onerror = () => {
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Ошибка: сервер недоступен (запущен ли uvicorn?)`]);
      setUploadStatus('error');
    };
    xhr.send(formData);
  };

  const isUploadBusy = ['uploading', 'processing', 'extracting'].includes(uploadStatus);

  const columns = [
    { label: 'ID', key: 'result_id' },
    { label: 'Статья', key: 'publication_id' },
    { label: 'Конфиг', key: 'config_id' },
    { label: 'Метрика', key: 'metric_name' },
    { label: 'Значение', key: 'metric_value' },
    { label: 'Страница', key: 'source_page' },
    { label: 'Происхождение', key: 'result_origin' },
  ];

  return (
    <div className="flex h-screen bg-[#0B0E14] text-[#E2E8F0] font-sans overflow-hidden selection:bg-[#00D2FF] selection:text-black">
      
      {/* САЙДБАР */}
      <aside className="w-20 flex flex-col items-center py-6 border-r border-white/5 bg-[#0B0E14] z-30 shrink-0">
        <div className="w-10 h-10 bg-[#00D2FF] rounded-xl flex items-center justify-center font-bold text-black text-xl mb-10 shadow-[0_0_20px_rgba(0,210,255,0.4)]">R</div>
        <nav className="flex flex-col gap-6 flex-1 w-full">
          <button onClick={() => setActiveTab('overview')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'overview' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><LayoutDashboard className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('upload')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'upload' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><UploadCloud className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('data')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'data' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><Database className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('tables')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'tables' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><Table2 className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('issues')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'issues' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><AlertTriangle className="w-6 h-6" /></button>
          <button onClick={() => setActiveTab('pubs')} className={`w-full flex justify-center py-3 relative transition-colors ${activeTab === 'pubs' ? 'text-[#00D2FF]' : 'text-gray-500 hover:text-white'}`}><FileText className="w-6 h-6" /></button>
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
              {activeTab === 'tables' && 'Таблицы набора'}
              {activeTab === 'issues' && 'Замечания проверки'}
              {activeTab === 'pubs' && 'Публикации'}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {areasInfo && (
              <>
                <select
                  value={currentArea}
                  onChange={(e) => {
                    const area = e.target.value;
                    const info = areasInfo.areas.find(a => a.id === area);
                    const setName = info?.sets?.includes(currentSet) ? currentSet : (info?.sets?.[0] || 'test');
                    switchSelection(area, setName);
                  }}
                  className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none"
                >
                  {areasInfo.areas.map(a => (
                    <option key={a.id} value={a.id}>{AREA_LABELS[a.id] || a.id}</option>
                  ))}
                </select>
                <select
                  value={currentSet}
                  onChange={(e) => switchSelection(currentArea, e.target.value)}
                  className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none"
                >
                  {(areasInfo.areas.find(a => a.id === currentArea)?.sets || []).map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </>
            )}
            {stats && <span className="text-xs text-gray-500 font-mono">{stats.area}/{stats.dataset}</span>}
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
                <p className="text-base text-gray-400 leading-relaxed mb-8">Единая база данных результатов RAG-экспериментов, извлечённых из научных статей.</p>
                <div className="flex gap-10 border-t border-white/10 pt-8 mt-8">
                  <div><div className="text-3xl font-mono text-white mb-1">{stats ? stats.publications : '—'}</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Статей</div></div>
                  <div><div className="text-3xl font-mono text-[#00D2FF] mb-1">{stats ? stats.results : '—'}</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Результатов</div></div>
                  <div><div className="text-3xl font-mono text-[#FF0032] mb-1">{stats ? stats.issues : '—'}</div><div className="text-[10px] text-gray-500 uppercase tracking-widest">Замечаний</div></div>
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
                  className={`bg-[#151A24] border rounded-2xl p-8 flex flex-col items-center justify-center text-center h-64 border-dashed transition-colors ${isUploadBusy ? 'opacity-60 cursor-wait border-white/10' : dragOver ? 'border-[#00D2FF] bg-[#00D2FF]/5 cursor-copy' : 'border-white/10 hover:border-[#00D2FF]/50 cursor-pointer'}`}
                  onClick={() => { if (!isUploadBusy) fileInputRef.current?.click(); }}
                  onDragOver={(e) => { e.preventDefault(); if (!isUploadBusy) setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    if (!isUploadBusy) handleFileSelected(e.dataTransfer.files?.[0]);
                  }}
                >
                  <UploadCloud className="w-8 h-8 text-[#00D2FF] mb-4" />
                  <h3 className="text-white font-medium mb-2">Загрузить PDF</h3>
                  <p className="text-xs text-gray-500 mb-4">Файл отправится на сервер и пройдёт конвейер извлечения</p>
                  <select
                    value={uploadArea}
                    onChange={(e) => setUploadArea(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    className="mb-4 bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none"
                  >
                    <option value="rag">Область: RAG</option>
                    <option value="solar">Область: Solar</option>
                  </select>
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
                  {uploadStatus === 'done' && (
                    <span className="ml-auto flex items-center gap-3 text-xs text-green-500">
                      <CheckCircle2 className="w-3 h-3"/> Готово: {jobResults} результатов
                      {jobPid && (
                        <button
                          onClick={() => { setSearchQuery(jobPid); setActiveTab('data'); }}
                          className="px-2 py-1 rounded bg-[#00D2FF]/10 text-[#00D2FF] hover:bg-[#00D2FF]/20 transition-colors"
                        >
                          Открыть результаты {jobPid}
                        </button>
                      )}
                    </span>
                  )}
                  {uploadStatus === 'error' && <span className="ml-auto flex items-center gap-2 text-xs text-[#FF0032]"><AlertTriangle className="w-3 h-3"/> Error</span>}
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
                    <input type="text" placeholder="Поиск по метрике, цитате, ID..." value={searchQuery} onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }} className="w-full bg-[#0B0E14] border border-white/10 text-sm text-white rounded-lg py-2.5 pl-12 pr-10 focus:outline-none" />
                  </div>
                  <button onClick={handleExportCSV} className="flex items-center gap-2 px-4 py-2.5 bg-white/5 border border-white/10 text-white text-xs font-bold uppercase rounded-lg hover:bg-white/10 transition-colors shrink-0">
                    <Download className="w-4 h-4" /> Экспорт CSV
                  </button>
                </div>
                
                <div className="flex items-center gap-4 flex-wrap">
                   <div className="flex items-center gap-2 text-xs text-gray-400"><Filter className="w-3 h-3" /> Фильтры:</div>
                   <select value={filterMetric} onChange={(e) => updateFilter(setFilterMetric)(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none max-w-[240px]">
                    <option value="all">Все метрики</option>
                    {facets.metrics.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                   <select value={filterOrigin} onChange={(e) => updateFilter(setFilterOrigin)(e.target.value)} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none">
                    <option value="all">Любое происхождение</option>
                    <option value="primary">Primary</option>
                    <option value="cited">Cited</option>
                  </select>
                  <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                    <input type="checkbox" checked={withIssues} onChange={(e) => updateFilter(setWithIssues)(e.target.checked)} className="accent-[#00D2FF]" />
                    Есть замечания
                  </label>
                  {apiError && <span className="text-xs text-[#FF0032] ml-auto">{apiError}</span>}
                </div>
              </div>

              {/* ТАБЛИЦА */}
              <div className="flex-1 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50 flex flex-col relative">
                {loading && <div className="absolute inset-0 bg-[#0B0E14]/50 z-20 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-[#00D2FF]" /></div>}
                <table className="w-full text-left border-collapse">
                  <thead className="bg-[#151A24] sticky top-0 border-b border-white/10 z-10">
                    <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                      {columns.map((col) => (
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
                    {!loading && items.length === 0 ? (
                      <tr>
                        <td colSpan={columns.length} className="p-12 text-center">
                          <div className="flex flex-col items-center justify-center text-gray-500">
                            <SearchX className="w-12 h-12 mb-4 text-gray-600" />
                            <h3 className="text-lg font-medium text-white mb-1">Ничего не найдено</h3>
                            <p className="text-sm">Попробуйте изменить поисковый запрос или сбросить фильтры.</p>
                            <button 
                              onClick={() => { setSearchQuery(''); setFilterMetric('all'); setFilterOrigin('all'); setWithIssues(false); setCurrentPage(1); }}
                              className="mt-4 px-4 py-2 bg-[#00D2FF]/10 text-[#00D2FF] text-xs font-medium rounded hover:bg-[#00D2FF]/20 transition-colors"
                            >
                              Сбросить всё
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      items.map((row) => (
                        <tr key={`${row.publication_id}-${row.result_id}`} onClick={() => { setSelectedResult(row); setSelectedDetail(null); }} className="border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors group">
                          <td className="p-4 font-mono text-gray-400">{row.result_id}</td>
                          <td className="p-4">
                            <span className="flex items-center gap-1 text-xs text-[#00D2FF]"><Network className="w-3 h-3"/> {row.publication_id}</span>
                          </td>
                          <td className="p-4 text-white font-mono">{row.config_id || '—'}</td>
                          <td className="p-4 text-gray-300 font-mono">{row.metric_name}{row.metric_k ? `@${row.metric_k}` : ''}</td>
                          <td className="p-4 font-mono text-white">{row.raw_value}</td>
                          <td className="p-4 text-xs text-[#00D2FF]">
                            {row.source_table ? `${row.source_table}, ` : ''}стр. {row.source_page}
                          </td>
                          <td className="p-4">
                            {row.result_origin === 'primary' && <span className="text-green-400 bg-green-400/10 px-2 py-1 rounded text-xs">primary</span>}
                            {row.result_origin === 'cited' && <span className="text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded text-xs">cited</span>}
                            {!row.result_origin && <span className="text-gray-500 text-xs">—</span>}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>

                {/* ПАГИНАЦИЯ (Footer таблицы) */}
                <div className="mt-auto p-4 border-t border-white/10 bg-[#151A24] flex items-center justify-between shrink-0 rounded-b-xl">
                  <span className="text-xs text-gray-500">
                    Показано <span className="text-white">{total > 0 ? indexOfFirstItem + 1 : 0}</span> - <span className="text-white">{Math.min(indexOfFirstItem + PER_PAGE, total)}</span> из <span className="text-white">{total}</span> записей
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

          {/* ТАБЛИЦЫ НАБОРА (все 7 по схеме области) */}
          {activeTab === 'tables' && areasInfo && (
            <div className="absolute inset-0 p-8 flex flex-col overflow-hidden bg-[#0B0E14]">
              <div className="flex items-center gap-2 mb-6 shrink-0 bg-[#151A24] p-4 rounded-xl border border-white/10 flex-wrap">
                {(areasInfo.areas.find(a => a.id === currentArea)?.tables || []).map(t => (
                  <button
                    key={t}
                    onClick={() => { setActiveTable(t); setTablePage(1); }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-colors ${activeTable === t ? 'bg-[#00D2FF] text-black font-bold' : 'bg-white/5 text-gray-400 hover:text-white'}`}
                  >
                    {t}
                  </button>
                ))}
                <span className="text-xs text-gray-500 ml-auto">Всего: <span className="text-white">{tableData.total}</span></span>
              </div>
              <div className="flex-1 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50 flex flex-col">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-[#151A24] sticky top-0 border-b border-white/10 z-10">
                    <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                      {tableData.columns.map(c => <th key={c} className="p-3 font-normal whitespace-nowrap">{c}</th>)}
                    </tr>
                  </thead>
                  <tbody className="text-xs font-mono">
                    {tableData.items.map((row, i) => (
                      <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        {tableData.columns.map(c => (
                          <td key={c} className="p-3 text-gray-300 max-w-[280px] truncate" title={row[c]}>{row[c] || '—'}</td>
                        ))}
                      </tr>
                    ))}
                    {tableData.items.length === 0 && (
                      <tr><td colSpan={tableData.columns.length || 1} className="p-12 text-center text-gray-500 italic">Таблица пуста</td></tr>
                    )}
                  </tbody>
                </table>
                <div className="mt-auto p-4 border-t border-white/10 bg-[#151A24] flex items-center justify-end gap-2 shrink-0 rounded-b-xl">
                  <button onClick={() => setTablePage(p => Math.max(p - 1, 1))} disabled={tablePage === 1} className="p-1.5 rounded bg-[#0B0E14] border border-white/10 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"><ChevronLeft className="w-4 h-4" /></button>
                  <span className="text-xs font-mono text-gray-300 px-2">Стр. {tablePage} из {Math.ceil(tableData.total / 20) || 1}</span>
                  <button onClick={() => setTablePage(p => Math.min(p + 1, Math.ceil(tableData.total / 20)))} disabled={tablePage >= Math.ceil(tableData.total / 20)} className="p-1.5 rounded bg-[#0B0E14] border border-white/10 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"><ChevronRight className="w-4 h-4" /></button>
                </div>
              </div>
            </div>
          )}

          {/* ЗАМЕЧАНИЯ */}
          {activeTab === 'issues' && (
            <div className="absolute inset-0 p-8 flex flex-col overflow-hidden bg-[#0B0E14]">
              <div className="flex items-center gap-4 mb-6 shrink-0 bg-[#151A24] p-5 rounded-xl border border-white/10">
                <div className="flex items-center gap-2 text-xs text-gray-400"><Filter className="w-3 h-3" /> Фильтры:</div>
                <select value={issueCheck} onChange={(e) => { setIssueCheck(e.target.value); setIssuePage(1); }} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none">
                  <option value="all">Все правила</option>
                  {facets.check_names.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <select value={issuePid} onChange={(e) => { setIssuePid(e.target.value); setIssuePage(1); }} className="bg-[#0B0E14] border border-white/10 text-xs text-gray-300 rounded-lg px-3 py-2 outline-none">
                  <option value="all">Все статьи</option>
                  {facets.publications.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <span className="text-xs text-gray-500 ml-auto">Всего: <span className="text-white">{issuesData.total}</span></span>
              </div>

              <div className="flex-1 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50 flex flex-col">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-[#151A24] sticky top-0 border-b border-white/10 z-10">
                    <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                      <th className="p-4 font-normal">Статья</th>
                      <th className="p-4 font-normal">ID</th>
                      <th className="p-4 font-normal">Правило</th>
                      <th className="p-4 font-normal">Описание</th>
                      <th className="p-4 font-normal">Стр.</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {issuesData.items.map((issue) => (
                      <tr key={`${issue.publication_id}-${issue.issue_id}`} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="p-4 font-mono text-[#00D2FF] text-xs">{issue.publication_id}</td>
                        <td className="p-4 font-mono text-gray-400">{issue.issue_id}</td>
                        <td className="p-4"><span className="text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded text-xs font-mono">{issue.check_name}</span></td>
                        <td className="p-4 text-gray-300 text-xs max-w-xl">{issue.description}</td>
                        <td className="p-4 text-gray-400 text-xs">{issue.source_page || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-auto p-4 border-t border-white/10 bg-[#151A24] flex items-center justify-end gap-2 shrink-0 rounded-b-xl">
                  <button onClick={() => setIssuePage(p => Math.max(p - 1, 1))} disabled={issuePage === 1} className="p-1.5 rounded bg-[#0B0E14] border border-white/10 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"><ChevronLeft className="w-4 h-4" /></button>
                  <span className="text-xs font-mono text-gray-300 px-2">Стр. {issuePage} из {Math.ceil(issuesData.total / 20) || 1}</span>
                  <button onClick={() => setIssuePage(p => Math.min(p + 1, Math.ceil(issuesData.total / 20)))} disabled={issuePage >= Math.ceil(issuesData.total / 20)} className="p-1.5 rounded bg-[#0B0E14] border border-white/10 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"><ChevronRight className="w-4 h-4" /></button>
                </div>
              </div>
            </div>
          )}

          {/* ПУБЛИКАЦИИ */}
          {activeTab === 'pubs' && (
            <div className="absolute inset-0 p-8 flex gap-6 overflow-hidden bg-[#0B0E14]">
              <div className="w-2/5 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50">
                {pubs.map((pub) => (
                  <div key={pub.publication_id} onClick={() => setSelectedPub(pub)} className={`p-4 border-b border-white/5 cursor-pointer transition-colors ${selectedPub?.publication_id === pub.publication_id ? 'bg-[#00D2FF]/10 border-l-2 border-l-[#00D2FF]' : 'hover:bg-white/5'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-[#00D2FF]">{pub.publication_id}</span>
                      <span className="text-xs text-gray-500">{pub.year}</span>
                      {pub.in_scope === 'false' && <span className="text-[10px] text-[#FF0032] bg-[#FF0032]/10 px-1.5 py-0.5 rounded">out of scope</span>}
                    </div>
                    <div className="text-sm text-gray-300 leading-snug">{pub.title || '(название не извлечено)'}</div>
                  </div>
                ))}
              </div>

              <div className="flex-1 overflow-auto border border-white/10 rounded-xl bg-[#151A24]/50 p-6">
                {!selectedPub ? (
                  <div className="h-full flex items-center justify-center text-gray-600 italic text-sm">Выберите статью слева</div>
                ) : (
                  <>
                    <h2 className="text-lg font-bold text-white mb-1">{selectedPub.publication?.title || selectedPub.publication_id}</h2>
                    <div className="text-xs text-gray-500 mb-6 font-mono">
                      {selectedPub.publication?.year} {selectedPub.publication?.DOI && `· DOI: ${selectedPub.publication.DOI}`} · результатов: {selectedPub.results_count}
                    </div>
                    <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Конфигурации ({selectedPub.configurations?.length ?? 0})</h4>
                    <div className="space-y-1 mb-6">
                      {(selectedPub.configurations || []).slice(0, 30).map(c => (
                        <div key={c.config_id} className="text-xs font-mono text-gray-300 py-1 border-b border-white/5"><span className="text-[#00D2FF]">{c.config_id}</span> — {c.rag_variant}</div>
                      ))}
                      {(selectedPub.configurations?.length ?? 0) > 30 && <div className="text-xs text-gray-600 italic">…ещё {selectedPub.configurations.length - 30}</div>}
                    </div>
                    <button onClick={() => { setFilterOrigin('all'); setFilterMetric('all'); setSearchQuery(''); setActiveTab('data'); }} className="px-4 py-2 bg-[#00D2FF]/10 text-[#00D2FF] text-xs font-medium rounded hover:bg-[#00D2FF]/20 transition-colors">
                      Показать результаты в таблице
                    </button>
                  </>
                )}
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
                  <span className="text-xs font-mono text-gray-400 bg-white/5 px-2 py-1 rounded">{selectedResult.result_id}</span>
                  <span className="text-xs font-mono text-gray-400 bg-white/5 px-2 py-1 rounded">{selectedResult.publication_id}</span>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded ${selectedResult.result_origin === 'cited' ? 'text-yellow-400 bg-yellow-400/10' : 'text-green-400 bg-green-400/10'}`}>{selectedResult.result_origin || '—'}</span>
                </div>
                <h2 className="text-lg font-bold text-white">{selectedResult.metric_name}{selectedResult.metric_k ? `@${selectedResult.metric_k}` : ''}</h2>
                <p className="text-sm text-gray-400 mt-1">Значение: <span className="text-white font-mono">{selectedResult.raw_value}</span>
                  {selectedResult.metric_value !== selectedResult.raw_value && <span className="text-gray-500"> → {selectedResult.metric_value}</span>}
                </p>
              </div>
              <button onClick={() => { setSelectedResult(null); setSelectedDetail(null); }} className="p-2 hover:bg-white/10 rounded-full text-gray-400"><X className="w-5 h-5" /></button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
              <div>
                <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-2">
                  <FileText className="w-3 h-3" /> Цитата (стр. {selectedResult.source_page}{selectedResult.source_table ? `, ${selectedResult.source_table}` : ''})
                </h4>
                <div className="bg-[#151A24] border-l-2 border-[#00D2FF] p-4 rounded-r-lg relative group">
                  <p className="text-sm text-gray-300 font-mono italic leading-relaxed">"{selectedResult.source_fragment}"</p>
                  {selectedResult.source_section && <p className="text-xs text-gray-500 mt-3 border-t border-white/5 pt-2">Раздел: {selectedResult.source_section}</p>}
                </div>
                <button onClick={() => setIsPdfOpen(true)} className="mt-3 w-full py-2 border border-white/20 text-gray-300 text-xs font-medium rounded hover:bg-white/10 transition-colors flex items-center justify-center gap-2">
                  <FileText className="w-4 h-4" /> Открыть источник (стр. {selectedResult.source_page})
                </button>
              </div>

              {selectedDetail?.issues?.length > 0 && (
                <div>
                  <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2 flex items-center gap-2"><AlertTriangle className="w-3 h-3 text-yellow-400" /> Замечания проверки</h4>
                  {selectedDetail.issues.map(issue => (
                    <div key={issue.issue_id} className="bg-yellow-400/5 border-l-2 border-yellow-400 p-3 rounded-r-lg mb-2">
                      <div className="text-xs font-mono text-yellow-400 mb-1">{issue.check_name}</div>
                      <p className="text-xs text-gray-300">{issue.description}</p>
                    </div>
                  ))}
                </div>
              )}

              {selectedDetail?.duplicates?.length > 0 && (
                <div>
                  <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Повторные упоминания</h4>
                  {selectedDetail.duplicates.map(d => (
                    <div key={d.result_id} className="text-xs text-gray-400 font-mono py-1">{d.result_id}: {d.metric_name} = {d.raw_value}</div>
                  ))}
                </div>
              )}

              {selectedResult.note && (
                <div>
                  <h4 className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Заметка</h4>
                  <p className="text-xs text-gray-400">{selectedResult.note}</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* МОДАЛКА ИСТОЧНИКА — настоящий PDF на нужной странице */}
      {isPdfOpen && selectedResult && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-8">
          <div className="w-full max-w-4xl h-full max-h-[90vh] bg-[#1A1A1A] rounded-xl flex flex-col overflow-hidden border border-white/10 shadow-2xl">
            <div className="h-12 bg-[#252525] flex items-center justify-between px-4 border-b border-white/10 shrink-0">
              <div className="flex items-center gap-3 text-gray-300 text-sm">
                <FileText className="w-4 h-4 text-[#FF0032]" />
                <span className="font-medium">{selectedResult.publication_id}.pdf</span>
                <span className="text-gray-500 text-xs px-2 bg-white/5 rounded">Страница {selectedResult.source_page}</span>
              </div>
              <button onClick={() => setIsPdfOpen(false)} className="p-1.5 hover:bg-white/10 rounded text-gray-400"><X className="w-4 h-4" /></button>
            </div>
            <iframe
              src={`${API}/pdf/${selectedResult.publication_id}#page=${selectedResult.source_page}`}
              className="flex-1 w-full bg-[#2A2A2A]"
              title="PDF источника"
            />
          </div>
        </div>
      )}
    </div>
  );
}
