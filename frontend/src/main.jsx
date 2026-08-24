import React, {useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Provider, useDispatch, useSelector} from 'react-redux'
import {analyze, clearHistory, loadHistory, store} from './store'
import './styles.css'

const money = n => n == null ? '—' : Number(n).toLocaleString('zh-TW',{maximumFractionDigits:2})
const percent = n => n == null ? '—' : `${(Number(n)*100).toFixed(2)}%`
const Metric = ({label,value}) => <div className="metric"><span>{label}</span><strong>{value}</strong></div>

const toNumber = value => value == null || value === '' ? null : Number(value)

function calculateWarrantValues(stockPrice, strikePrice, exerciseRatio, marketPrice) {
  const values = [stockPrice, strikePrice, exerciseRatio, marketPrice].map(toNumber)
  if (values.some(value => value == null || !Number.isFinite(value) || value < 0)) return null

  const [stock, strike, ratio, market] = values
  const intrinsicValue = Math.max(stock - strike, 0) * ratio
  const timeValue = market - intrinsicValue
  return { intrinsicValue, timeValue, warrantPrice: intrinsicValue + timeValue }
}

function SiteNav({page, onNavigate}) {
  return <nav className="site-nav" aria-label="主要導覽">
    <a className="brand" href="#dashboard" onClick={event=>onNavigate(event,'dashboard')}>
      <span className="brand-mark">W</span><span>權證實驗室</span>
    </a>
    <div className="nav-links">
      <a className={page==='dashboard'?'active':''} href="#dashboard" onClick={event=>onNavigate(event,'dashboard')}>權證評分</a>
      <a className={page==='calculator'?'active':''} href="#calculator" onClick={event=>onNavigate(event,'calculator')}>價格試算</a>
    </div>
  </nav>
}

function Dashboard(){
  const dispatch=useDispatch(), {current,history,status,error}=useSelector(s=>s.warrant)
  const [code,setCode]=useState('067185')
  useEffect(()=>{dispatch(loadHistory())},[dispatch])
  const submit=e=>{e.preventDefault(); if(/^\d{6}$/.test(code)) dispatch(analyze(code))}
  return <>
    <header><div><p className="eyebrow">TAIWAN WARRANT LAB</p><h1>權證評分儀表板</h1><p>把複雜的風險參數，整理成一眼能比較的分數。</p></div><div className="market-dot">● 台股資料</div></header>
    <form className="score-form" onSubmit={submit}><label htmlFor="code">輸入六碼權證代號</label><div className="search"><input id="code" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} inputMode="numeric" placeholder="例如 067185"/><button disabled={status==='loading'||code.length!==6}>{status==='loading'?'分析中…':'開始評分'}</button></div>{error&&<p className="error">{error}</p>}</form>
    {current ? <>
      <section className="hero-card"><div><p className="eyebrow">{current.warrant_code}</p><h2>{current.warrant_name}</h2><p>對應標的　{current.stock.code} {current.stock.name}</p></div><div className="score"><span>綜合分數</span><strong>{current.score}</strong><em>{current.rating}</em></div></section>
      {current.warning&&<p className="warning">{current.warning}</p>}
      <section className="grid"><article><h3>標的行情</h3><div className="metrics"><Metric label="股價" value={money(current.stock.price)}/><Metric label="開盤" value={money(current.stock.open)}/><Metric label="最高" value={money(current.stock.high)}/><Metric label="最低" value={money(current.stock.low)}/><Metric label="交易量" value={money(current.stock.volume)}/><Metric label="來源" value={current.stock.source}/></div></article>
      <article><h3>權證參數</h3><div className="metrics"><Metric label="距到期日" value={`${current.metrics.days_to_expiry} 天`}/><Metric label="目前履約價" value={money(current.metrics.strike_price)}/><Metric label="權證價格" value={money(current.metrics.warrant_price)}/><Metric label="執行比例" value={current.metrics.exercise_ratio}/><Metric label="Delta" value={current.metrics.delta}/><Metric label="Theta" value={current.metrics.theta}/><Metric label="價內外" value={`${current.metrics.moneyness_percent}% ${current.metrics.moneyness_label}`}/><Metric label="有效槓桿" value={`${current.metrics.effective_leverage} 倍`}/></div></article>
      <article><h3>TWSE 盤後造市資料</h3><div className="metrics"><Metric label="委買隱含波動率" value={percent(current.metrics.implied_vol)}/><Metric label={current.metrics.iv_std_source==='twse_14d_max_change_proxy'?'14 日 IV 最大變動（暫代）':'14 日 IV 標準差'} value={percent(current.metrics.iv_std)}/><Metric label="買賣價差比" value={percent(current.metrics.bid_ask_spread)}/><Metric label="委託買量" value={money(current.metrics.bid_volume)}/><Metric label="委託賣量" value={money(current.metrics.ask_volume)}/><Metric label="資料日期" value={current.metrics.market_data_date||'—'}/><Metric label="來源" value={current.metrics.market_data_source||'—'}/></div></article></section>
      <section className="breakdown"><h3>評分拆解</h3>{current.score_items.map(x=><div className="bar-row" key={x.key}><div><b>{x.label}</b><small>{x.note}</small></div><div className="bar"><i style={{width:`${x.score/x.max_score*100}%`}}/></div><strong>{x.score}/{x.max_score}</strong></div>)}</section>
    </>:<section className="empty"><span>⌁</span><h2>從一檔權證開始</h2><p>系統會保留每次評分，方便觀察條件隨時間變化。</p></section>}
    <section className="history"><div className="section-title"><h3>歷史紀錄</h3>{history.length>0&&<button className="ghost" onClick={()=>dispatch(clearHistory())}>清除</button>}</div>{history.length===0?<p className="muted">尚無紀錄</p>:<div className="table-wrap"><table><thead><tr><th>時間</th><th>權證</th><th>標的</th><th>價格</th><th>分數</th></tr></thead><tbody>{history.map(x=><tr key={x.id} onClick={()=>{setCode(x.warrant_code);dispatch(analyze(x.warrant_code))}}><td>{new Date(x.analyzed_at).toLocaleString('zh-TW')}</td><td>{x.warrant_code} {x.warrant_name}</td><td>{x.stock.code} {x.stock.name}</td><td>{money(x.metrics.warrant_price)}</td><td><b>{x.score}</b> {x.rating}</td></tr>)}</tbody></table></div>}</section>
  </>
}

const fieldInfo = [
  {key:'stockPrice', label:'標的股價', unit:'元', step:'0.01'},
  {key:'strikePrice', label:'履約價', unit:'元', step:'0.01'},
  {key:'exerciseRatio', label:'行使比例', unit:'倍', step:'0.01'},
  {key:'marketPrice', label:'權證市價', unit:'元', step:'0.01'},
]

function CalculatorPage(){
  const [inputs,setInputs]=useState({stockPrice:'130',strikePrice:'120',exerciseRatio:'0.1',marketPrice:'1.5'})
  const result=calculateWarrantValues(inputs.stockPrice,inputs.strikePrice,inputs.exerciseRatio,inputs.marketPrice)
  const update=(key,value)=>setInputs(current=>({...current,[key]:value}))
  const display=value=>Number(value).toLocaleString('zh-TW',{minimumFractionDigits:2,maximumFractionDigits:4})

  return <div className="calculator-page">
    <header className="calculator-header">
      <div><p className="eyebrow">WARRANT PRICE ESTIMATOR</p><h1>預估權證價格</h1><p>輸入市場條件，快速看懂權證價格中有多少是現在的價值、多少是未來的可能。</p></div>
      <div className="formula-chip"><span>核心公式</span><strong>權證價格 = 內含價值 + 時間價值</strong></div>
    </header>

    <section className="calculator-layout">
      <form className="calculator-form" onSubmit={event=>event.preventDefault()}>
        <div className="card-heading"><div><span className="step-number">01</span><div><p>輸入條件</p><small>數值變動時將自動更新結果</small></div></div><button type="button" className="reset-button" onClick={()=>setInputs({stockPrice:'130',strikePrice:'120',exerciseRatio:'0.1',marketPrice:'1.5'})}>重設範例</button></div>
        <div className="input-grid">
          {fieldInfo.map(field=><label className="number-field" key={field.key} htmlFor={field.key}>
            <span>{field.label}</span>
            <div><input id={field.key} type="number" min="0" step={field.step} value={inputs[field.key]} onChange={event=>update(field.key,event.target.value)}/><em>{field.unit}</em></div>
          </label>)}
        </div>
        <p className="form-note"><span>i</span> 權證市價用來推算目前市場給予的時間價值。</p>
      </form>

      <section className="result-card" aria-live="polite">
        <div className="card-heading"><div><span className="step-number light">02</span><div><p>試算結果</p><small>認購權證價格拆解</small></div></div></div>
        {result ? <>
          <div className="price-result"><span>權證價格</span><strong><small>NT$</small>{display(result.warrantPrice)}</strong><p>每單位權證預估價格</p></div>
          <div className="value-equation">
            <div><span>內含價值</span><strong>{display(result.intrinsicValue)}</strong></div>
            <b>＋</b>
            <div><span>時間價值</span><strong className={result.timeValue<0?'negative':''}>{display(result.timeValue)}</strong></div>
            <b>＝</b>
            <div><span>權證價格</span><strong>{display(result.warrantPrice)}</strong></div>
          </div>
          {result.timeValue<0&&<p className="result-warning">目前市價低於計算出的內含價值，請確認輸入資料或市場報價。</p>}
        </>:<div className="invalid-result"><strong>等待完整資料</strong><p>請輸入大於或等於 0 的有效數字。</p></div>}
      </section>
    </section>

    <section className="explanation-section">
      <div className="section-intro"><p className="eyebrow">HOW IT WORKS</p><h2>價格從哪裡來？</h2><p>權證價格可以拆成兩部分。內含價值反映現在立刻履約的價值；時間價值則反映到期前，標的仍可能朝有利方向移動的可能性。</p></div>
      <div className="explain-cards">
        <article className="explain-card"><span className="explain-icon">01</span><h3>內含價值</h3><p>現在立刻履約可以取得的價值。認購權證只有在標的價格高於履約價時，才具有內含價值。</p><code>max(標的價格 − 履約價, 0) × 行使比例</code></article>
        <article className="explain-card"><span className="explain-icon amber">02</span><h3>時間價值</h3><p>距離到期日前，標的仍可能朝有利方向變動的價值，會隨時間與市場預期而改變。</p><code>權證市價 − 內含價值</code></article>
      </div>
    </section>

    <section className="example-card">
      <div><p className="eyebrow">EXAMPLE</p><h2>用一個例子快速理解</h2><p>標的股價 130 元、履約價 120 元、行使比例 0.1、權證市價 1.5 元。</p></div>
      <div className="example-steps"><p><span>1</span>內含價值：max(130 − 120, 0) × 0.1 = <strong>1 元</strong></p><p><span>2</span>時間價值：1.5 − 1 = <strong>0.5 元</strong></p><p className="example-total"><span>3</span>權證價格：1 + 0.5 = <strong>1.5 元</strong></p></div>
    </section>
  </div>
}

function App(){
  const getPage=()=>window.location.hash==='#calculator'?'calculator':'dashboard'
  const [page,setPage]=useState(getPage)
  useEffect(()=>{
    const syncPage=()=>setPage(getPage())
    window.addEventListener('hashchange',syncPage)
    return ()=>window.removeEventListener('hashchange',syncPage)
  },[])
  const navigate=(event,nextPage)=>{event.preventDefault();window.location.hash=nextPage;setPage(nextPage)}
  return <main>
    <SiteNav page={page} onNavigate={navigate}/>
    {page==='calculator'?<CalculatorPage/>:<Dashboard/>}
    <footer>內容僅供研究與試算，不構成投資建議。</footer>
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

export { money, Metric, calculateWarrantValues, CalculatorPage, App }

