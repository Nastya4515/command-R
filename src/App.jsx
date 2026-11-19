import React from 'react';
import logo from './assets/logo.png'; 
import { 
  LayoutDashboard, AlertTriangle, Users, Settings, 
  Search, Bot, Clock, ShieldAlert, ArrowRight 
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
    status: 'В работе'
  },
  {
    id: 'INC-1043',
    title: 'Деградация БД (Кластер 2)',
    severity: 'warning',
    timeLeft: '45:10',
    progress: 40,
    team: 'DBA Team',
    status: 'Ожидает'
  },
  {
    id: 'INC-1044',
    title: 'Высокий Ping до CDN',
    severity: 'warning',
    timeLeft: '1:12:00',
    progress: 20,
    team: 'Network',
    status: 'Назначен'
  }
];

export default function IncidentDashboard() {
  return (
    // Основной фон (Deep Space)
    <div className="flex h-screen bg-[#0B0E14] text-gray-200 font-sans overflow-hidden selection:bg-[#E30611] selection:text-white">
      
      {/* 1. ЛЕВЫЙ САЙДБАР (Минималистичный, только иконки) */}
      <aside className="w-20 flex flex-col items-center py-6 border-r border-white/5 bg-[#0B0E14]/50 backdrop-blur-md z-20">
                {/* Логотип */}
        <div className="w-12 h-12 mb-10 flex items-center justify-center cursor-pointer transition-transform hover:scale-105">
          <img 
            src={logo} 
            alt="Logo" 
            className="w-full h-full object-contain drop-shadow-[0_0_15px_rgba(227,6,17,0.5)]" 
          />
        </div>
        
        <nav className="flex flex-col gap-6 flex-1 w-full">
          {/* Активная вкладка */}
          <button className="w-full flex justify-center py-3 relative group">
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#E30611] rounded-r-md"></div>
            <LayoutDashboard className="w-6 h-6 text-[#E30611]" />
          </button>
          <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white transition-colors group">
            <AlertTriangle className="w-6 h-6" />
          </button>
          <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white transition-colors group">
            <Users className="w-6 h-6" />
          </button>
        </nav>

        <button className="w-full flex justify-center py-3 text-gray-500 hover:text-white transition-colors mt-auto">
          <Settings className="w-6 h-6" />
        </button>
      </aside>

      {/* ОСНОВНАЯ ОБЛАСТЬ */}
      <main className="flex-1 flex flex-col p-6 overflow-hidden relative">
        
        {/* 2. ВЕРХНЯЯ ПАНЕЛЬ */}
        <header className="flex items-center justify-between mb-6 z-10">
          <div>
            <h1 className="text-2xl font-semibold text-white">Центр управления инцидентами</h1>
            <p className="text-sm text-gray-400 mt-1">Смена: Ночная • Координатор: Алексей</p>
          </div>
          
          {/* ИИ Поиск */}
          <div className="flex items-center gap-4">
            <div className="relative group">
              <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-[#00D2FF] transition-colors" />
              <input 
                type="text" 
                placeholder="Спросить ИИ или найти инцидент (Cmd+K)" 
                className="bg-[#151A24] border border-white/10 text-sm text-white rounded-full py-2 pl-10 pr-4 w-80 focus:outline-none focus:border-[#00D2FF]/50 focus:ring-1 focus:ring-[#00D2FF]/50 transition-all placeholder-gray-500"
              />
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#E30611] to-orange-500 flex items-center justify-center border-2 border-[#151A24] cursor-pointer">
              <span className="text-white font-bold text-sm">АС</span>
            </div>
          </div>
        </header>

        {/* 3. BENTO GRID (Центральное пространство) */}
        <div className="grid grid-cols-12 gap-6 flex-1 overflow-hidden">
          
          {/* ЛЕВАЯ И ЦЕНТРАЛЬНАЯ КОЛОНКИ (3D + ИИ) */}
          <div className="col-span-8 flex flex-col gap-6">
            
            {/* БЛОК ИИ-ПОМОЩНИКА (Сверху) */}
            <div className="bg-[#151A24]/80 backdrop-blur-xl border border-[#00D2FF]/20 rounded-2xl p-4 flex items-start gap-4 shadow-[0_0_30px_rgba(0,210,255,0.05)]">
              <div className="p-2 bg-[#00D2FF]/10 rounded-lg mt-1">
                <Bot className="w-6 h-6 text-[#00D2FF]" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-[#00D2FF]">ИИ Аналитика</span>
                  <span className="text-xs bg-[#00D2FF]/10 text-[#00D2FF] px-2 py-0.5 rounded-full">Live</span>
                </div>
                <p className="text-sm text-gray-300 leading-relaxed">
                  <strong>Внимание:</strong> Обнаружен каскадный риск. Сбой в API авторизации (INC-1042) может затронуть сервис оплаты через <span className="text-[#E30611] font-medium">15 минут</span>. Рекомендую эскалировать команде Backend.
                </p>
                <div className="flex gap-2 mt-3">
                  <button className="text-xs bg-[#E30611] hover:bg-red-700 text-white px-3 py-1.5 rounded-md transition-colors font-medium flex items-center gap-1">
                    Эскалировать <ArrowRight className="w-3 h-3" />
                  </button>
                  <button className="text-xs bg-white/5 hover:bg-white/10 text-gray-300 px-3 py-1.5 rounded-md transition-colors border border-white/10">
                    Игнорировать
                  </button>
                </div>
              </div>
            </div>

            {/* ЗАГЛУШКА ПОД 3D (WebGL) */}
            <div className="flex-1 bg-[#151A24]/50 border border-white/5 rounded-2xl relative overflow-hidden flex flex-col items-center justify-center group">
              {/* Декоративные элементы (сетка) */}
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:40px_40px]"></div>
              
              {/* Здесь будет ваш Canvas от React Three Fiber */}
              <div className="z-10 flex flex-col items-center text-center">
                <div className="w-32 h-32 rounded-full border border-[#E30611]/30 border-t-[#E30611] animate-spin mb-6 flex items-center justify-center">
                  <div className="w-24 h-24 rounded-full border border-gray-700/50 border-b-gray-400 animate-spin-reverse"></div>
                </div>
                <h3 className="text-lg font-medium text-gray-300 mb-2">3D Топология сети (WebGL)</h3>
                <p className="text-sm text-gray-500 max-w-xs">Здесь будет интерактивный граф микросервисов на Three.js.</p>
              </div>
            </div>

          </div>

          {/* ПРАВАЯ КОЛОНКА (Лента инцидентов) */}
          <div className="col-span-4 bg-[#151A24]/80 backdrop-blur-xl border border-white/5 rounded-2xl flex flex-col overflow-hidden">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h2 className="font-semibold text-white">Критические инциденты</h2>
              <span className="bg-[#E30611] text-white text-xs font-bold px-2 py-1 rounded-md">3</span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 custom-scrollbar">
              {mockIncidents.map((incident) => (
                <div 
                  key={incident.id} 
                  className={`p-4 rounded-xl border transition-all cursor-pointer hover:bg-white/5
                    ${incident.severity === 'critical' 
                      ? 'border-[#FF4D4D]/50 bg-[#FF4D4D]/5 shadow-[0_0_15px_rgba(255,77,77,0.1)]' 
                      : 'border-[#FFB000]/30 bg-[#FFB000]/5'
                    }
                  `}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs text-gray-400 font-mono">{incident.id}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${incident.severity === 'critical' ? 'text-[#FF4D4D] bg-[#FF4D4D]/10' : 'text-[#FFB000] bg-[#FFB000]/10'}`}>
                      {incident.status}
                    </span>
                  </div>
                  
                  <h3 className="text-sm font-semibold text-white mb-3">{incident.title}</h3>
                  
                  {/* Прогресс-бар SLA (Таймер) */}
                  <div className="mb-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-400 flex items-center gap-1"><Clock className="w-3 h-3"/> До эскалации</span>
                      <span className={`font-mono font-bold ${incident.severity === 'critical' ? 'text-[#FF4D4D]' : 'text-[#FFB000]'}`}>
                        {incident.timeLeft}
                      </span>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-1.5">
                      <div 
                        className={`h-1.5 rounded-full ${incident.severity === 'critical' ? 'bg-[#FF4D4D]' : 'bg-[#FFB000]'}`} 
                        style={{ width: `${incident.progress}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-gray-400 mt-4 pt-3 border-t border-white/5">
                    <span className="flex items-center gap-1"><ShieldAlert className="w-3.5 h-3.5"/> {incident.team}</span>
                    <span className="text-[#E30611] hover:underline cursor-pointer">Детали &rarr;</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}