import axios from 'axios';
import type {
  Position,
  Trade,
  Alert,
  PortfolioValue,
  SystemStatus,
  SanshengStatus,
  PriceData,
  ChartData,
} from '../types';

const api = axios.create({ baseURL: '/api' });

export const systemApi = {
  getStatus: () => api.get<SystemStatus>('/system/status').then(r => r.data),
  getSanshengStatus: () => api.get<SanshengStatus>('/sansheng/status').then(r => r.data),
  getHealth: () => api.get('/health').then(r => r.data),
};

export const portfolioApi = {
  getPositions: () => api.get<Position[]>('/positions').then(r => r.data),
  getValue: () => api.get<PortfolioValue>('/portfolio/value').then(r => r.data),
  getTrades: (limit = 50) => api.get<Trade[]>(`/trades?limit=${limit}`).then(r => r.data),
  getAlerts: (limit = 20) => api.get<Alert[]>(`/alerts?limit=${limit}`).then(r => r.data),
};

export const marketApi = {
  getPrices: () => api.get<PriceData[]>('/market/prices').then(r => r.data),
  getPrice: (market: string, symbol: string) =>
    api.get<PriceData>(`/price/${market}/${symbol}`).then(r => r.data),
};

export const monitorApi = {
  start: () => api.post('/monitor', { action: 'start' }).then(r => r.data),
  stop: () => api.post('/monitor', { action: 'stop' }).then(r => r.data),
};

export const stockChartApi = {
  getChart: (params: {
    codes: string;
    start_date: string;
    end_date: string;
    strategy?: string;
    fast?: number;
    slow?: number;
  }) => api.get<ChartData>('/stock/chart', { params }).then(r => r.data),
};

export const backtestChartApi = {
  getChart: (strategy: string) =>
    api.get<ChartData>(`/backtest/chart/${strategy}`).then(r => r.data),
};

export const tradingModeApi = {
  setMode: (mode: 'live' | 'sim', token: string) =>
    api.post('/trading/mode', { mode, token }).then(r => r.data),
};

export default api;