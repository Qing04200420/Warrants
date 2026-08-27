import { configureStore, createAsyncThunk, createSlice } from '@reduxjs/toolkit'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const apiUrl = path => `${API_BASE_URL}${path}`

const json = async (response) => {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `API 請求失敗 (${response.status})`)
  }
  return response.status === 204 ? null : response.json()
}
export const analyze = createAsyncThunk('warrant/analyze', async code => json(await fetch(apiUrl('/api/warrants/analyze'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})})))
export const estimate = createAsyncThunk('warrant/estimate', async payload => json(await fetch(apiUrl('/api/warrants/estimate'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})))
export const scoreStock = createAsyncThunk('stock/score', async payload => json(await fetch(apiUrl('/api/stocks/score'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})))
export const recommendWarrants = createAsyncThunk('warrant/recommend', async payload => json(await fetch(apiUrl('/api/warrants/recommend'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})))
export const loadHistory = createAsyncThunk('warrant/history', async () => json(await fetch(apiUrl('/api/history?limit=30'))))
export const clearHistory = createAsyncThunk('warrant/clear', async () => json(await fetch(apiUrl('/api/history'),{method:'DELETE'})))
const slice = createSlice({name:'warrant',initialState:{current:null,history:[],historyStatus:'idle',status:'idle',error:null,estimate:null,estimateStatus:'idle',estimateError:null,stockScore:null,stockScoreStatus:'idle',stockScoreError:null,warrantRecommendations:null,recommendationStatus:'idle',recommendationError:null},reducers:{},extraReducers:b=>b
  .addCase(analyze.pending,s=>{s.status='loading';s.error=null})
  .addCase(analyze.fulfilled,(s,a)=>{s.status='done';s.current=a.payload;s.history=[a.payload,...s.history.filter(x=>x.id!==a.payload.id)]})
  .addCase(analyze.rejected,(s,a)=>{s.status='error';s.error=a.error.message})
  .addCase(loadHistory.pending,s=>{s.historyStatus='loading'})
  .addCase(loadHistory.fulfilled,(s,a)=>{s.historyStatus='done';s.history=a.payload})
  .addCase(loadHistory.rejected,s=>{s.historyStatus='error'})
  .addCase(clearHistory.fulfilled,s=>{s.history=[]})
  .addCase(estimate.pending,s=>{s.estimateStatus='loading';s.estimateError=null})
  .addCase(estimate.fulfilled,(s,a)=>{s.estimateStatus='done';s.estimate=a.payload})
  .addCase(estimate.rejected,(s,a)=>{s.estimateStatus='error';s.estimateError=a.error.message})
  .addCase(scoreStock.pending,s=>{s.stockScoreStatus='loading';s.stockScoreError=null;s.warrantRecommendations=null;s.recommendationStatus='idle';s.recommendationError=null})
  .addCase(scoreStock.fulfilled,(s,a)=>{s.stockScoreStatus='done';s.stockScore=a.payload})
  .addCase(scoreStock.rejected,(s,a)=>{s.stockScoreStatus='error';s.stockScoreError=a.error.message})
  .addCase(recommendWarrants.pending,s=>{s.recommendationStatus='loading';s.recommendationError=null})
  .addCase(recommendWarrants.fulfilled,(s,a)=>{s.recommendationStatus='done';s.warrantRecommendations=a.payload})
  .addCase(recommendWarrants.rejected,(s,a)=>{s.recommendationStatus='error';s.recommendationError=a.error.message})})
export const store = configureStore({reducer:{warrant:slice.reducer}})

