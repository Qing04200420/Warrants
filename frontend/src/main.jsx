import React, {useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Provider, useDispatch, useSelector} from 'react-redux'
import {analyze, clearHistory, loadHistory, store} from './store'
import './styles.css'

const money = n => n == null ? '—' : Number(n).toLocaleString('zh-TW',{maximumFractionDigits:2})
const percent = n => n == null ? '—' : `${(Number(n)*100).toFixed(2)}%`
const Metric = ({label,value}) => <div className="metric"><span>{label}</span><strong>{value}</strong></div>

function App(){
  const dispatch=useDispatch(), {current,history,status,error}=useSelector(s=>s.warrant)
  const [code,setCode]=useState('067185')
  useEffect(()=>{dispatch(loadHistory())},[dispatch])
  const submit=e=>{e.preventDefault(); if(/^\d{6}$/.test(code)) dispatch(analyze(code))}
  return <main>
    <header><div><p className="eyebrow">TAIWAN WARRANT LAB</p><h1>權證評分儀表板</h1><p>把複雜的風險參數，整理成一眼能比較的分數。</p></div><div className="market-dot">● 台股資料</div></header>
    <form onSubmit={submit}><label htmlFor="code">輸入六碼權證代號</label><div className="search"><input id="code" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} inputMode="numeric" placeholder="例如 067185"/><button disabled={status==='loading'||code.length!==6}>{status==='loading'?'分析中…':'開始評分'}</button></div>{error&&<p className="error">{error}</p>}</form>
    {current ? <>
      <section className="hero-card"><div><p className="eyebrow">{current.warrant_code}</p><h2>{current.warrant_name}</h2><p>對應標的　{current.stock.code} {current.stock.name}</p></div><div className="score"><span>綜合分數</span><strong>{current.score}</strong><em>{current.rating}</em></div></section>
      {current.warning&&<p className="warning">{current.warning}</p>}
      <section className="grid"><article><h3>標的行情</h3><div className="metrics"><Metric label="股價" value={money(current.stock.price)}/><Metric label="開盤" value={money(current.stock.open)}/><Metric label="最高" value={money(current.stock.high)}/><Metric label="最低" value={money(current.stock.low)}/><Metric label="交易量" value={money(current.stock.volume)}/><Metric label="來源" value={current.stock.source}/></div></article>
      <article><h3>權證參數</h3><div className="metrics"><Metric label="距到期日" value={`${current.metrics.days_to_expiry} 天`}/><Metric label="目前履約價" value={money(current.metrics.strike_price)}/><Metric label="權證價格" value={money(current.metrics.warrant_price)}/><Metric label="執行比例" value={current.metrics.exercise_ratio}/><Metric label="Delta" value={current.metrics.delta}/><Metric label="Theta" value={current.metrics.theta}/><Metric label="價內外" value={`${current.metrics.moneyness_percent}% ${current.metrics.moneyness_label}`}/><Metric label="有效槓桿" value={`${current.metrics.effective_leverage} 倍`}/></div></article>
      <article><h3>TWSE 盤後造市資料</h3><div className="metrics"><Metric label="委買隱含波動率" value={percent(current.metrics.implied_vol)}/><Metric label={current.metrics.iv_std_source==='twse_14d_max_change_proxy'?'14 日 IV 最大變動（暫代）':'14 日 IV 標準差'} value={percent(current.metrics.iv_std)}/><Metric label="買賣價差比" value={percent(current.metrics.bid_ask_spread)}/><Metric label="委託買量" value={money(current.metrics.bid_volume)}/><Metric label="委託賣量" value={money(current.metrics.ask_volume)}/><Metric label="資料日期" value={current.metrics.market_data_date||'—'}/><Metric label="來源" value={current.metrics.market_data_source||'—'}/></div></article></section>
      <section className="breakdown"><h3>評分拆解</h3>{current.score_items.map(x=><div className="bar-row" key={x.key}><div><b>{x.label}</b><small>{x.note}</small></div><div className="bar"><i style={{width:`${x.score/x.max_score*100}%`}}/></div><strong>{x.score}/{x.max_score}</strong></div>)}</section>
    </>:<section className="empty"><span>⌁</span><h2>從一檔權證開始</h2><p>系統會保留每次評分，方便觀察條件隨時間變化。</p></section>}
    <section className="history"><div className="section-title"><h3>歷史紀錄</h3>{history.length>0&&<button className="ghost" onClick={()=>dispatch(clearHistory())}>清除</button>}</div>{history.length===0?<p className="muted">尚無紀錄</p>:<div className="table-wrap"><table><thead><tr><th>時間</th><th>權證</th><th>標的</th><th>價格</th><th>分數</th></tr></thead><tbody>{history.map(x=><tr key={x.id} onClick={()=>{setCode(x.warrant_code);dispatch(analyze(x.warrant_code))}}><td>{new Date(x.analyzed_at).toLocaleString('zh-TW')}</td><td>{x.warrant_code} {x.warrant_name}</td><td>{x.stock.code} {x.stock.name}</td><td>{money(x.metrics.warrant_price)}</td><td><b>{x.score}</b> {x.rating}</td></tr>)}</tbody></table></div>}</section>
    <footer>評分僅供研究與比較，不構成投資建議。</footer>
  </main>
}

const rootElement =
  typeof document !== 'undefined'
    ? document.getElementById('root')
    : null

if (rootElement) {
  createRoot(rootElement).render(
    <Provider store={store}>
      <App />
    </Provider>
  )
}

export { money, Metric, App }

