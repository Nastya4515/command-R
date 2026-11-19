import logo from './assets/logo.png'; 
import NetworkGraph3D from './NetworkGraph3D';
import React, { useState } from 'react';
import { 
  LayoutDashboard, AlertTriangle, Users, Settings, 
  Search, Bot, Clock, ShieldAlert, ArrowRight, X, Send
} from 'lucide-react';

// Моковые данные для карточек инцидентов
const mockIncidents = [
  {
    id: 'INC-1042',
    title: 'Отказ API авторизации',
    severity: 'critical',
    timeLeft: '14:32',
    progress: 75,
    team: 'Backend Team',
    status: 'В работе',
    // НОВОЕ: Моковые сообщения для чата
    messages: [
      { sender: 'Система', text: 'Инцидент создан автоматически.', time: '10:00', isMe: false },
      { sender: 'Иван (Backend)', text: 'Принял в работу, смотрю логи.', time: '10:02', isMe: false },
      { sender: 'Вы', text: 'Срочно нужно решение, падает прод.', time: '10:05', isMe: true },
    ]
  },
  {
    id: 'INC-1043',
    title: 'Деградация БД (Кластер 2)',
    severity: 'warning',
    timeLeft: '45:10',
    progress: 40,
    team: 'DBA Team',
    status: 'Ожидает',
    messages: [{ sender: 'Система', text: 'Ожидает назначения.', time: '09:45', isMe: false }]
  },
  {
    id: 'INC-1044',
    title: 'Высокий Ping до CDN',
    severity: 'warning',
    timeLeft: '1:12:00',
    progress: 20,
    team: 'Network',
    status: 'Назначен',
    messages: [{ sender: 'Сеть', text: 'Проверяем маршрутизацию.', time: '09:15', isMe: false }]
  }
];

export default function IncidentDashboard() {
  // НОВОЕ: Состояние для выбранного инцидента (если null - панель закрыта)
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [chatInput, setChatInput] = useState('');

  return (
    <div className="flex h-screen bg-[#0B0E14] text-gray-200 font-sans overflow-hidden selection:bg-[#E30611] selection:text-white relative">
      
      {/* 1. ЛЕВЫЙ САЙДБАР */}
      <aside className="w-20 flex flex-col items-center py-6 border-r border-white/5 bg-[#0B0E14]/50 backdrop-blur-md z-20">
                <div className="w-12 h-12 mb-10 flex items-center justify-center cursor-pointer transition-transform hover:scale-105">
          <img 
            src={logo} 
            alt="Logo" 
            className="w-full h-full object-contain drop-shadow-[0_0_15px_rgba(227,6,17,0.5)]" 
          />
        </div>
        <nav className="flex flex-col gap-6 flex-1 w-full">
          <button className="w-full flex justify-center py-3 relative group">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#E30611] rounded-r-md"></div>
            <LayoutDashboard className="w-6 h-6 text-[#E30611]" />
          </button>
          <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white transition-colors group"><AlertTriangle className="w-6 h-6" /></button>
          <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white transition-colors group"><Users className="w-6 h-6" /></button>
        </nav>
        <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white transition-colors mt-auto"><Settings className="w-6 h-6" /></button>
      </aside>

      {/* ОСНОВНАЯ ОБЛАСТЬ */}
      <main className="flex-1 flex flex-col p-6 overflow-hidden relative">
        
        {/* ВЕРХНЯЯ ПАНЕЛЬ */}
        <header className="flex items-center justify-between mb-6 z-10">
          <div>
            <h1 className="text-2xl font-semibold text-white">Центр управления инцидентами</h1>
            <p className="text-sm text-gray-400 mt-1">Смена: Ночная • Координатор: Алексей</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="relative group">
              <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-[#00D2FF] transition-colors" />
              <input type="text" placeholder="Спросить ИИ (Cmd+K)" className="bg-[#151A24] border border-white/10 text-sm text-white rounded-full py-2 pl-10 pr-4 w-80 focus:outline-none focus:border-[#00D2FF]/50 focus:ring-1 focus:ring-[#00D2FF]/50 transition-all placeholder-gray-500" />
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#E30611] to-orange-500 flex items-center justify-center border-2 border-[#151A24] cursor-pointer">
              <span className="text-white font-bold text-sm">АС</span>
            </div>
          </div>
        </header>

        {/* BENTO GRID */}
        <div className="grid grid-cols-12 gap-6 flex-1 overflow-hidden">
          
          <div className="col-span-8 flex flex-col gap-6">
            {/* ИИ БЛОК */}
            <div className="bg-[#151A24]/80 backdrop-blur-xl border border-[#00D2FF]/20 rounded-2xl p-4 flex items-start gap-4 shadow-[0_0_30px_rgba(0,210,255,0.05)]">
              <div className="p-2 bg-[#00D2FF]/10 rounded-lg mt-1"><Bot className="w-6 h-6 text-[#00D2FF]" /></div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-[#00D2FF]">ИИ Аналитика</span>
                  <span className="text-xs bg-[#00D2FF]/10 text-[#00D2FF] px-2 py-0.5 rounded-full">Live</span>
                </div>
                <p className="text-sm text-gray-300 leading-relaxed">
                  <strong>Внимание:</strong> Обнаружен каскадный риск. Сбой в API авторизации (INC-1042) может затронуть сервис оплаты через <span className="text-[#E30611] font-medium">15 минут</span>.
                </p>
                <div className="flex gap-2 mt-3">
                  <button className="text-xs bg-[#E30611] hover:bg-red-700 text-white px-3 py-1.5 rounded-md transition-colors font-medium flex items-center gap-1">Эскалировать <ArrowRight className="w-3 h-3" /></button>
                </div>
              </div>
            </div>

            {/* ЗАГЛУШКА 3D */}
                        {/* 3D СЦЕНА */}
            <div className="flex-1 bg-[#151A24]/50 border border-white/5 rounded-2xl relative overflow-hidden">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:40px_40px]"></div>
              
              {/* Наш 3D компонент */}
              <NetworkGraph3D />
              
              {/* Плашка поверх 3D */}
              <div className="absolute top-4 left-4 z-10 bg-[#0B0E14]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10">
                <span className="text-xs text-gray-300 font-medium flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[#00D2FF] animate-pulse"></div>
                  Live Топология
                </span>
              </div>
            </div>
          </div>

          {/* ПРАВАЯ КОЛОНКА (С КЛИКОМ) */}
          <div className="col-span-4 bg-[#151A24]/80 backdrop-blur-xl border border-white/5 rounded-2xl flex flex-col overflow-hidden">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h2 className="font-semibold text-white">Инциденты</h2>
              <span className="bg-[#E30611] text-white text-xs font-bold px-2 py-1 rounded-md">3</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
              {mockIncidents.map((incident) => (
                <div 
                  key={incident.id} 
                  // НОВОЕ: Добавили onClick
                  onClick={() => setSelectedIncident(incident)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer hover:bg-white/5 hover:scale-[1.02]
                    ${incident.severity === 'critical' ? 'border-[#FF4D4D]/50 bg-[#FF4D4D]/5 shadow-[0_0_15px_rgba(255,77,77,0.1)]' : 'border-[#FFB000]/30 bg-[#FFB000]/5'}
                  `}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs text-gray-400 font-mono">{incident.id}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${incident.severity === 'critical' ? 'text-[#FF4D4D] bg-[#FF4D4D]/10' : 'text-[#FFB000] bg-[#FFB000]/10'}`}>{incident.status}</span>
                  </div>
                  <h3 className="text-sm font-semibold text-white mb-3">{incident.title}</h3>
                  <div className="mb-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-400 flex items-center gap-1"><Clock className="w-3 h-3"/> До эскалации</span>
                      <span className={`font-mono font-bold ${incident.severity === 'critical' ? 'text-[#FF4D4D]' : 'text-[#FFB000]'}`}>{incident.timeLeft}</span>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-1.5">
                      <div className={`h-1.5 rounded-full ${incident.severity === 'critical' ? 'bg-[#FF4D4D]' : 'bg-[#FFB000]'}`} style={{ width: `${incident.progress}%` }}></div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-400 mt-4 pt-3 border-t border-white/5">
                    <span className="flex items-center gap-1"><ShieldAlert className="w-3.5 h-3.5"/> {incident.team}</span>
                    <span className="text-[#E30611] font-medium">Открыть &rarr;</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      {/* ========================================================= */}
      {/* НОВОЕ: ВЫЕЗЖАЮЩАЯ ПАНЕЛЬ (DRAWER) И ЗАТЕМНЕНИЕ          */}
      {/* ========================================================= */}
      
      {/* Затемнение фона (клик закрывает панель) */}
      <div 
        className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity duration-300 ${selectedIncident ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setSelectedIncident(null)}
      ></div>

      {/* Сама панель */}
      <div 
        className={`fixed inset-y-0 right-0 w-[450px] bg-[#151A24] border-l border-white/10 z-50 shadow-2xl flex flex-col transition-transform duration-300 ease-in-out ${selectedIncident ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {selectedIncident && (
          <>
            {/* Шапка панели */}
            <div className="p-6 border-b border-white/10 flex justify-between items-start bg-[#0B0E14]/50">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs font-mono text-gray-400 bg-white/5 px-2 py-1 rounded">{selectedIncident.id}</span>
                  <span className="text-xs font-semibold text-[#FF4D4D] bg-[#FF4D4D]/10 px-2 py-1 rounded">{selectedIncident.severity.toUpperCase()}</span>
                </div>
                <h2 className="text-xl font-bold text-white">{selectedIncident.title}</h2>
                <p className="text-sm text-gray-400 mt-1">Ответственная команда: <span className="text-white">{selectedIncident.team}</span></p>
              </div>
              <button 
                onClick={() => setSelectedIncident(null)}
                className="p-2 hover:bg-white/10 rounded-full transition-colors text-gray-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Чат */}
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 bg-[#0B0E14]/30">
              {selectedIncident.messages.map((msg, index) => (
                <div key={index} className={`flex flex-col ${msg.isMe ? 'items-end' : 'items-start'}`}>
                  <span className="text-xs text-gray-500 mb-1">{msg.sender} • {msg.time}</span>
                  <div className={`px-4 py-2 rounded-2xl max-w-[85%] text-sm ${msg.isMe ? 'bg-[#E30611] text-white rounded-tr-sm' : 'bg-[#151A24] border border-white/10 text-gray-200 rounded-tl-sm'}`}>
                    {msg.text}
                  </div>
                </div>
              ))}
            </div>

            {/* Поле ввода */}
            <div className="p-4 border-t border-white/10 bg-[#151A24]">
              <div className="relative flex items-center">
                <input 
                  type="text" 
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Написать команде..." 
                  className="w-full bg-[#0B0E14] border border-white/10 text-sm text-white rounded-full py-3 pl-4 pr-12 focus:outline-none focus:border-[#E30611]/50"
                />
                <button className="absolute right-2 p-2 bg-[#E30611] hover:bg-red-700 text-white rounded-full transition-colors">
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

    </div>
  );
}