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
export const loadHistory = createAsyncThunk('warrant/history', async () => json(await fetch(apiUrl('/api/history?limit=30'))))
export const clearHistory = createAsyncThunk('warrant/clear', async () => json(await fetch(apiUrl('/api/history'),{method:'DELETE'})))
const slice = createSlice({name:'warrant',initialState:{current:null,history:[],status:'idle',error:null},reducers:{},extraReducers:b=>b
  .addCase(analyze.pending,s=>{s.status='loading';s.error=null})
  .addCase(analyze.fulfilled,(s,a)=>{s.status='done';s.current=a.payload;s.history=[a.payload,...s.history.filter(x=>x.id!==a.payload.id)]})
  .addCase(analyze.rejected,(s,a)=>{s.status='error';s.error=a.error.message})
  .addCase(loadHistory.fulfilled,(s,a)=>{s.history=a.payload})
  .addCase(clearHistory.fulfilled,s=>{s.history=[]})})
export const store = configureStore({reducer:{warrant:slice.reducer}})

