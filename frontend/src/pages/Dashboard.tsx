import { useEffect, useState } from 'react';
import { usePortfolioStore } from '../stores/portfolioStore';
import { useSystemStore } from '../stores/marketStore';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function Dashboard() {
  const { value, positions, alerts, fetchAll } = usePortfolioStore();
  const { status, sansheng, fetchStatus, fetchSansheng } = useSystemStore();
  const [uptime, setUptime] = useState('');

  useEffect(() => {
    fetchAll();
    fetchStatus();
    fetchSansheng();
    const interval = setInterval(() => {
      fetchAll();
      fetchStatus();
      fetchSansheng();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (status?.uptime) {
      const s = Math.floor((Date.now() / 1000 - status.uptime));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      setUptime(`${h}h ${m}m`);
    }
  }, [status]);

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Dashboard</h2>
          <p className="text-sm text-gray-500">系统总览 · 实时监控</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
            status?.monitor?.status === 'running'
              ? 'bg-green-900 text-green-400'
              : 'bg-gray-800 text-gray-400'
          }`}>
            监控 {status?.monitor?.status === 'running' ? '运行中' : '已停止'}
          </span>
          {uptime && <span className="text-xs text-gray-500">运行时长 {uptime}</span>}
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="持仓市值"
          value={`¥${value?.total_value?.toFixed(2) ?? '—'}`}
          sub={value?.total_pnl_pct != null ? `${value.total_pnl >= 0 ? '+' : ''}${value.total_pnl_pct.toFixed(2)}%` : ''}
          color={value?.total_pnl_pct && value.total_pnl_pct >= 0 ? 'green' : 'red'}
        />
        <StatCard
          label="持仓盈亏"
          value={`${value?.total_pnl != null && value.total_pnl >= 0 ? '+' : ''}¥${value?.total_pnl?.toFixed(2) ?? '—'}`}
          sub={`成本 ¥${value?.total_cost?.toFixed(2) ?? '—'}`}
          color={value?.total_pnl != null && value.total_pnl >= 0 ? 'green' : 'red'}
        />
        <StatCard
          label="持仓数量"
          value={String(positions?.length ?? '—')}
          sub={`${value?.positions?.length ?? 0} 个品种`}
          color="cyan"
        />
        <StatCard
          label="风险等级"
          value={sansheng?.menxia?.level?.toUpperCase() ?? '—'}
          sub={sansheng?.menxia?.can_open ? '允许开仓' : '禁止开仓'}
          color={sansheng?.menxia?.can_open ? 'green' : 'red'}
        />
      </div>

      {/* 三省六部状态 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <h3 className="text-sm font-medium text-gray-400 mb-3">门下省 · 风控状态</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">风险等级</span>
              <span className={sansheng?.menxia?.level === 'NORMAL' ? 'text-green-400' : 'text-yellow-400'}>
                {sansheng?.menxia?.level ?? '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">当日亏损</span>
              <span className={ (sansheng?.menxia?.daily_loss_pct ?? 0) > 3 ? 'text-red-400' : 'text-gray-300'}>
                {sansheng?.menxia?.daily_loss_pct?.toFixed(2) ?? '0'}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">暴露度</span>
              <span>{sansheng?.menxia?.exposure_pct?.toFixed(1) ?? '0'}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">开仓次数</span>
              <span>{sansheng?.menxia?.daily_trades ?? 0}/10</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">开仓权限</span>
              <span className={sansheng?.menxia?.can_open ? 'text-green-400' : 'text-red-400'}>
                {sansheng?.menxia?.can_open ? '✅ 允许' : '❌ 禁止'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <h3 className="text-sm font-medium text-gray-400 mb-3">尚书省 · 实盘状态</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">实盘交易</span>
              <span className={sansheng?.live_trading ? 'text-green-400' : 'text-gray-400'}>
                {sansheng?.live_trading ? '✅ 已开启' : '❌ 已关闭'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">交易所</span>
              <span>{sansheng?.exchange ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">测试网络</span>
              <span>{sansheng?.testnet ? '✅ 是' : '❌ 否'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">中书省</span>
              <span className={sansheng?.shangshu_available ? 'text-green-400' : 'text-gray-500'}>
                {sansheng?.shangshu_available ? '✅ 就绪' : '❌ 未就绪'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <h3 className="text-sm font-medium text-gray-400 mb-3">最近告警</h3>
          {alerts?.length ? (
            <div className="space-y-2">
              {alerts.slice(0, 4).map(a => (
                <div key={a.id} className="flex justify-between items-center text-xs">
                  <span className="text-gray-400">{a.symbol}</span>
                  <span className="text-red-400">{a.alert_type}</span>
                  <span className="text-gray-500">{new Date(a.created_at).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600">暂无告警</p>
          )}
        </div>
      </div>

      {/* 持仓概览 + 权益曲线 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <h3 className="text-sm font-medium text-gray-400 mb-3">持仓概览</h3>
          {positions?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-[#2d2d44]">
                    <th className="text-left py-1.5">品种</th>
                    <th className="text-right py-1.5">数量</th>
                    <th className="text-right py-1.5">均价</th>
                    <th className="text-right py-1.5">市值</th>
                    <th className="text-right py-1.5">盈亏%</th>
                  </tr>
                </thead>
                <tbody>
                  {value?.positions?.map(p => (
                    <tr key={p.symbol + p.market} className="border-b border-[#2d2d44]/50">
                      <td className="py-1.5 font-medium">{p.symbol}</td>
                      <td className="text-right text-gray-400">{p.quantity.toFixed(4)}</td>
                      <td className="text-right text-gray-400">¥{p.avg_price.toFixed(2)}</td>
                      <td className="text-right">¥{p.value.toFixed(2)}</td>
                      <td className={`text-right font-medium ${p.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {p.pnl_pct >= 0 ? '+' : ''}{p.pnl_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-gray-600 py-6 text-center">暂无持仓</p>
          )}
        </div>

        <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
          <h3 className="text-sm font-medium text-gray-400 mb-3">权益曲线（模拟）</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={(value?.positions ?? []).map(() => ({ v: value?.total_value ?? 0 }))}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00bcd4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00bcd4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="index" hide />
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#252540', border: '1px solid #2d2d44', borderRadius: 6 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Area type="monotone" dataKey="v" stroke="#00bcd4" fill="url(#equityGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub: string; color: 'green' | 'red' | 'cyan' | 'yellow' | 'gray' }) {
  const colorMap = {
    green: 'text-green-400',
    red: 'text-red-400',
    cyan: 'text-cyan-400',
    yellow: 'text-yellow-400',
    gray: 'text-gray-300',
  };
  return (
    <div className="bg-[#1a1a2e] rounded-lg p-4 border border-[#2d2d44]">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-bold ${colorMap[color]}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}