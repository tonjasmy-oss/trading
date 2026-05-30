import { create } from 'zustand';
import type { PriceData, SystemStatus, SanshengStatus } from '../types';
import { marketApi, systemApi } from '../services/api';

interface MarketStore {
  prices: PriceData[];
  loading: boolean;
  error: string | null;
  fetchPrices: () => Promise<void>;
}

export const useMarketStore = create<MarketStore>((set) => ({
  prices: [],
  loading: false,
  error: null,
  fetchPrices: async () => {
    set({ loading: true });
    try {
      const prices = await marketApi.getPrices();
      set({ prices, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },
}));

interface SystemStore {
  status: SystemStatus | null;
  sansheng: SanshengStatus | null;
  loading: boolean;
  error: string | null;
  fetchStatus: () => Promise<void>;
  fetchSansheng: () => Promise<void>;
}

export const useSystemStore = create<SystemStore>((set) => ({
  status: null,
  sansheng: null,
  loading: false,
  error: null,
  fetchStatus: async () => {
    try {
      const status = await systemApi.getStatus();
      set({ status });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
  fetchSansheng: async () => {
    try {
      const sansheng = await systemApi.getSanshengStatus();
      set({ sansheng });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
}));