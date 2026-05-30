import { create } from 'zustand';
import type { Position, Trade, Alert, PortfolioValue } from '../types';
import { portfolioApi } from '../services/api';

interface PortfolioStore {
  positions: Position[];
  trades: Trade[];
  alerts: Alert[];
  value: PortfolioValue | null;
  loading: boolean;
  error: string | null;
  fetchAll: () => Promise<void>;
  fetchValue: () => Promise<void>;
  fetchTrades: () => Promise<void>;
  fetchAlerts: () => Promise<void>;
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  positions: [],
  trades: [],
  alerts: [],
  value: null,
  loading: false,
  error: null,

  fetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const [positions, value, trades, alerts] = await Promise.all([
        portfolioApi.getPositions(),
        portfolioApi.getValue(),
        portfolioApi.getTrades(),
        portfolioApi.getAlerts(),
      ]);
      set({ positions, value, trades, alerts, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },
  fetchValue: async () => {
    try {
      const value = await portfolioApi.getValue();
      set({ value });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
  fetchTrades: async () => {
    try {
      const trades = await portfolioApi.getTrades();
      set({ trades });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
  fetchAlerts: async () => {
    try {
      const alerts = await portfolioApi.getAlerts();
      set({ alerts });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
}));