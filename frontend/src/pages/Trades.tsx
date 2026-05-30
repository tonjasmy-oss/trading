import { useEffect } from 'react';
import { usePortfolioStore } from '../stores/portfolioStore';

export default function Trades() {
  const { trades, fetchTrades } = usePortfolioStore();

  useEffect(() => {
    fetchTrades();
    const iv = setInterval(fetchTrades, 30000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="p-6 space-y-5">
      <h2 className="text-xl font-bold text-white">交易记录</h2>
      {trades?.length ? (
        <div className="bg-[#1a1a2e] rounded-lg border border-[#2d2d44] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2d2d44] text-gray-500 text-left">
                <th className="px-4 py-3">时间</th>
                <th className="px-4 py-3">品种</th>
                <th className="px-4 py-3">市场</th>
                <th className="px-4 py-3">方向</th>
                <th className="px-4 py-3 text-right">数量</th>
                <th className="px-4 py-3 text-right">价格</th>
                <th className="px-4 py-3 text-right">总额</th>
              </tr>
            </thead>
            <tbody>
              {trades.map(t => (
                <tr key={t.id} className="border-b border-[#2d2d44]/50 hover:bg-[#252540]">
                  <td className="px-4 py-3 text-gray-400">
                    {new Date(t.traded_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="px-4 py-3 font-bold text-white">{t.symbol}</td>
                  <td className="px-4 py-3 text-gray-400">{t.market}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${t.trade_type === 'BUY' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                      {t.trade_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300">{t.quantity.toFixed(6)}</td>
                  <td className="px-4 py-3 text-right text-gray-300">¥{t.price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-white">¥{t.total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-16 text-gray-600">暂无交易记录</div>
      )}
    </div>
  );
}