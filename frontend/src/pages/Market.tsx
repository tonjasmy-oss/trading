import { useEffect } from 'react';
import { useMarketStore } from '../stores/marketStore';

export default function Market() {
  const { prices, fetchPrices } = useMarketStore();

  useEffect(() => {
    fetchPrices();
    const iv = setInterval(fetchPrices, 15000);
    return () => clearInterval(iv);
  }, []);

  const crypto = prices.filter(p => p.market === 'CRYPTO');
  const us = prices.filter(p => p.market === 'US');
  const hk = prices.filter(p => p.market === 'HK');
  const cn = prices.filter(p => p.market === 'CN');

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">行情监控</h2>
        <span className="text-xs text-gray-500">每15秒自动刷新</span>
      </div>

      {[
        { label: '🪙 加密货币', data: crypto },
        { label: '🇺🇸 美股', data: us },
        { label: '🇭🇰 港股', data: hk },
        { label: '🇨🇳 A股', data: cn },
      ].map(({ label, data }) => (
        <div key={label}>
          <h3 className="text-sm font-medium text-gray-400 mb-2">{label}</h3>
          {data.length ? (
            <div className="grid grid-cols-4 gap-3">
              {data.map(p => (
                <div key={p.symbol} className="bg-[#1a1a2e] rounded-lg p-3 border border-[#2d2d44]">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-bold text-white">{p.symbol}</span>
                    <span className={`text-sm font-medium ${p.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {p.change_pct >= 0 ? '+' : ''}{p.change_pct?.toFixed(2) ?? 0}%
                    </span>
                  </div>
                  <p className="text-lg font-bold text-white">
                    {p.market === 'CRYPTO' ? '$' : '¥'}{p.price?.toFixed(p.market === 'CRYPTO' ? 2 : 2)}
                  </p>
                  <div className="flex justify-between mt-1 text-xs text-gray-500">
                    <span>高 {p.high_24h?.toFixed(2) ?? '—'}</span>
                    <span>低 {p.low_24h?.toFixed(2) ?? '—'}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600">暂无数据</p>
          )}
        </div>
      ))}
    </div>
  );
}