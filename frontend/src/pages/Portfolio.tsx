import { useEffect } from 'react';
import { usePortfolioStore } from '../stores/portfolioStore';

export default function Portfolio() {
  const { positions, value, fetchAll } = usePortfolioStore();

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 30000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">持仓管理</h2>
        <div className="flex gap-3">
          <span className="text-sm text-gray-500">
            总市值 <span className="text-cyan-400 font-bold">¥{value?.total_value?.toFixed(2) ?? '—'}</span>
          </span>
          <span className={`text-sm font-medium ${(value?.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {value?.total_pnl != null && value.total_pnl >= 0 ? '+' : ''}¥{value?.total_pnl?.toFixed(2) ?? '—'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <p className="text-xs text-gray-500 mb-1">总成本</p>
          <p className="text-lg font-bold text-white">¥{value?.total_cost?.toFixed(2) ?? '—'}</p>
        </div>
        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <p className="text-xs text-gray-500 mb-1">当前市值</p>
          <p className="text-lg font-bold text-cyan-400">¥{value?.total_value?.toFixed(2) ?? '—'}</p>
        </div>
        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <p className="text-xs text-gray-500 mb-1">持仓盈亏</p>
          <p className={`text-lg font-bold ${(value?.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {value?.total_pnl != null && value.total_pnl >= 0 ? '+' : ''}¥{value?.total_pnl?.toFixed(2) ?? '—'}
          </p>
        </div>
      </div>

      {positions?.length ? (
        <div className="bg-[#1a1a2e] rounded-lg border border-[#2d2d44] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2d2d44] text-gray-500 text-left">
                <th className="px-4 py-3">品种</th>
                <th className="px-4 py-3">市场</th>
                <th className="px-4 py-3 text-right">数量</th>
                <th className="px-4 py-3 text-right">均价</th>
                <th className="px-4 py-3 text-right">现价</th>
                <th className="px-4 py-3 text-right">市值</th>
                <th className="px-4 py-3 text-right">盈亏</th>
                <th className="px-4 py-3 text-right">收益率</th>
              </tr>
            </thead>
            <tbody>
              {value?.positions?.map(p => (
                <tr key={p.symbol + p.market} className="border-b border-[#2d2d44]/50 hover:bg-[#252540]">
                  <td className="px-4 py-3 font-bold text-white">{p.symbol}</td>
                  <td className="px-4 py-3 text-gray-400">{p.market}</td>
                  <td className="px-4 py-3 text-right text-gray-300">{p.quantity.toFixed(6)}</td>
                  <td className="px-4 py-3 text-right text-gray-300">¥{p.avg_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-white">¥{p.current_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-white">¥{p.value.toFixed(2)}</td>
                  <td className={`px-4 py-3 text-right font-medium ${p.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {p.pnl >= 0 ? '+' : ''}¥{p.pnl.toFixed(2)}
                  </td>
                  <td className={`px-4 py-3 text-right font-medium ${p.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {p.pnl_pct >= 0 ? '+' : ''}{p.pnl_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-16 text-gray-600">暂无持仓</div>
      )}
    </div>
  );
}