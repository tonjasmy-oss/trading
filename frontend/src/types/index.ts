export interface Position {
  id: number;
  symbol: string;
  market: string;
  quantity: number;
  avg_price: number;
  created_at: string;
  updated_at: string;
}

export interface Trade {
  id: number;
  symbol: string;
  market: string;
  trade_type: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  total: number;
  traded_at: string;
}

export interface Alert {
  id: number;
  symbol: string;
  market: string;
  alert_type: string;
  price: number;
  threshold: number;
  message: string;
  created_at: string;
}

export interface PortfolioValue {
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions: PositionDetail[];
}

export interface PositionDetail extends Position {
  current_price: number;
  cost: number;
  value: number;
  pnl: number;
  pnl_pct: number;
}

export interface SystemStatus {
  monitor: { status: string; message: string };
  uptime: number;
  start_time: string;
}

export interface SanshengStatus {
  live_trading: boolean;
  exchange: string;
  testnet: boolean;
  menxia_available: boolean;
  shangshu_available: boolean;
  menxia: MenxiaStatus;
}

export interface MenxiaStatus {
  level: string;
  daily_loss_pct: number;
  exposure_pct: number;
  open_positions: number;
  daily_trades: number;
  can_open: boolean;
}

export interface PriceData {
  symbol: string;
  market: string;
  name: string;
  price: number;
  prev_close: number;
  change: number;
  change_pct: number;
  high_24h: number;
  low_24h: number;
}

export interface OHLCV {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v?: number;
}

export interface ChartData {
  ohlcv: OHLCV[];
  equity_curve: { t: number; v: number }[];
  buy_markers: { t: number; v: number }[];
  sell_markers: { t: number; v: number }[];
  indicators: Record<string, { t: number; v: number }[]>;
  strategy: string;
}