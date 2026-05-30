import { useEffect } from 'react';
import { usePortfolioStore } from '../stores/portfolioStore';

export default function Alerts() {
  const { alerts, fetchAlerts } = usePortfolioStore();

  useEffect(() => {
    fetchAlerts();
    const iv = setInterval(fetchAlerts, 30000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="p-6 space-y-5">
      <h2 className="text-xl font-bold text-white">告警记录</h2>
      {alerts?.length ? (
        <div className="space-y-2">
          {alerts.map(a => (
            <div key={a.id} className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44] flex items-center gap-4">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg
                ${a.alert_type.includes('止损') || a.alert_type.includes('波动') ? 'bg-red-900/30' : 'bg-yellow-900/30'}`}>
                ⚠️
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-white">{a.symbol}</span>
                  <span className="text-red-400 text-sm">{a.alert_type}</span>
                  <span className="text-gray-500 text-xs">
                    {new Date(a.created_at).toLocaleString('zh-CN')}
                  </span>
                </div>
                <p className="text-sm text-gray-400 mt-0.5">{a.message || `${a.alert_type} · 价格 ¥${a.price}`}</p>
              </div>
              <div className="text-right text-sm">
                <p className="text-white font-medium">¥{a.price}</p>
                <p className="text-gray-500 text-xs">阈值 {a.threshold}%</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-16 text-gray-600">暂无告警记录</div>
      )}
    </div>
  );
}