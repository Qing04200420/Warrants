import React, {useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Provider, useDispatch, useSelector} from 'react-redux'
import {analyze, clearHistory, estimate as estimateWarrant, loadHistory, scoreStock, store} from './store'
import './styles.css'

const money = n => n == null ? '—' : Number(n).toLocaleString('zh-TW',{maximumFractionDigits:2})
const percent = n => n == null ? '—' : `${(Number(n)*100).toFixed(2)}%`
const Metric = ({label,value}) => <div className="metric"><span>{label}</span><strong>{value}</strong></div>

const toNumber = value => value == null || value === '' ? null : Number(value)

const MODEL_ASSUMPTIONS = { volatility:0.3, riskFreeRate:0.015, daysPerYear:365, callPut:'C' }

function normalCdf(value) {
  const sign = value < 0 ? -1 : 1
  const x = Math.abs(value) / Math.sqrt(2)
  const t = 1 / (1 + 0.3275911 * x)
  const erf = 1 - (((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-x*x)
  return 0.5 * (1 + sign * erf)
}

function calculateBlackScholesWarrant(stockPrice, strikePrice, exerciseRatio, daysToExpiry, assumptions=MODEL_ASSUMPTIONS) {
  const values = [stockPrice, strikePrice, exerciseRatio, daysToExpiry].map(toNumber)
  if (values.some(value => value == null || !Number.isFinite(value) || value < 0)) return null

  const [stock, strike, ratio, days] = values
  const callPut = assumptions.callPut === 'P' ? 'P' : 'C'
  const intrinsicValue = Math.max(callPut === 'C' ? stock-strike : strike-stock, 0) * ratio
  if (days === 0 || stock === 0 || strike === 0 || ratio === 0) {
    const warrantPrice = strike === 0 && callPut === 'C' ? stock * ratio : intrinsicValue
    return { intrinsicValue, timeValue:Math.max(warrantPrice-intrinsicValue,0), warrantPrice, d1:null, d2:null }
  }

  const {volatility, riskFreeRate, daysPerYear} = assumptions
  if(![volatility,riskFreeRate,daysPerYear].every(Number.isFinite)||volatility<0||daysPerYear<=0) return null
  const timeInYears = days / daysPerYear
  const timeVolatility = volatility * Math.sqrt(timeInYears)
  const d1 = (Math.log(stock/strike) + (riskFreeRate + volatility**2/2)*timeInYears) / timeVolatility
  const d2 = d1 - timeVolatility
  const optionValue = callPut === 'C'
    ? stock*normalCdf(d1) - strike*Math.exp(-riskFreeRate*timeInYears)*normalCdf(d2)
    : strike*Math.exp(-riskFreeRate*timeInYears)*normalCdf(-d2) - stock*normalCdf(-d1)
  const warrantPrice = Math.max(optionValue*ratio,intrinsicValue)
  return { intrinsicValue, timeValue:Math.max(warrantPrice-intrinsicValue,0), warrantPrice, d1, d2 }
}

function SiteNav({page, onNavigate}) {
  return <nav className="site-nav" aria-label="主要導覽">
    <a className="brand" href="#dashboard" onClick={event=>onNavigate(event,'dashboard')}>
      <span className="brand-mark">W</span><span>投資評分工具</span>
    </a>
    <div className="nav-links">
      <a className={page==='stock-score'?'active':''} href="#stock-score" onClick={event=>onNavigate(event,'stock-score')}>標的評分</a>
      <a className={page==='dashboard'?'active':''} href="#dashboard" onClick={event=>onNavigate(event,'dashboard')}>權證評分</a>
      <a className={page==='calculator'?'active':''} href="#calculator" onClick={event=>onNavigate(event,'calculator')}>價格試算</a>
    </div>
  </nav>
}

function Dashboard(){
  const dispatch=useDispatch(), {current,history,status,error}=useSelector(s=>s.warrant)
  const [code,setCode]=useState('067185')
  useEffect(()=>{dispatch(loadHistory())},[dispatch])
  const submit=e=>{e.preventDefault(); if(/^[0-9A-Z]{6}$/.test(code)) dispatch(analyze(code))}
  return <>
    <header><div><p className="eyebrow">TAIWAN WARRANT LAB</p><h1>權證評分儀表板</h1><p>把複雜的風險參數，整理成一眼能比較的分數。</p></div><div className="market-dot">● 台股資料</div></header>
    <form className="score-form" onSubmit={submit}><label htmlFor="code">輸入六碼權證代號</label><div className="search"><input id="code" value={code} onChange={e=>setCode(e.target.value.toUpperCase().replace(/[^0-9A-Z]/g,'').slice(0,6))} autoCapitalize="characters" placeholder="例如 067185 或 03002T"/><button disabled={status==='loading'||code.length!==6}>{status==='loading'?'分析中…':'開始評分'}</button></div>{error&&<p className="error">{error}</p>}</form>
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

const scoreGroups=['大盤環境','日線趨勢','週線趨勢','價格結構','量價關係','動能指標','風險報酬']

function StockScorePage(){
  const dispatch=useDispatch()
  const {stockScore,stockScoreStatus,stockScoreError}=useSelector(state=>state.warrant)
  const [form,setForm]=useState({code:'2330',entry_price:'',stop_loss_price:'',target_price:''})
  const update=(key,value)=>setForm(current=>({...current,[key]:value}))
  const numbers=[form.entry_price,form.stop_loss_price,form.target_price].map(toNumber)
  const planValid=numbers.every(value=>value!=null&&Number.isFinite(value)&&value>0)&&numbers[1]<numbers[0]&&numbers[0]<numbers[2]
  const codeValid=/^[0-9A-Z]{4,6}$/.test(form.code)
  const loading=stockScoreStatus==='loading'
  const result=stockScore?.code===form.code?stockScore:null
  const submit=event=>{
    event.preventDefault()
    if(codeValid&&planValid) dispatch(scoreStock({...form,entry_price:numbers[0],stop_loss_price:numbers[1],target_price:numbers[2]}))
  }
  const n=value=>value==null?'—':Number(value).toLocaleString('zh-TW',{maximumFractionDigits:2})
  const condition=value=><span className={`condition ${value?'pass':'fail'}`}>{value?'成立':'未成立'}</span>

  return <div className="stock-score-page">
    <header className="stock-score-header"><div><p className="eyebrow">UNDERLYING TREND SCORE</p><h1>股票標的評分</h1><p>先判斷大盤，再核對日線、週線、價格結構、量價與動能，最後把交易計畫的風險報酬納入同一個 100 分量表。</p></div><div className="formula-chip"><span>評分目的</span><strong>找出較適合偏多／認購權證策略的標的</strong></div></header>

    <form className="stock-plan-form" onSubmit={submit}>
      <div className="plan-heading"><div><span className="step-number">01</span><div><p>股票與交易計畫</p><small>停損價 &lt; 進場價 &lt; 目標價</small></div></div><button disabled={!codeValid||!planValid||loading}>{loading?'分析歷史行情中…':'開始評分'}</button></div>
      <div className="stock-input-grid">
        <label className="number-field" htmlFor="stock-code"><span>股票代號</span><div><input id="stock-code" value={form.code} onChange={event=>update('code',event.target.value.toUpperCase().replace(/[^0-9A-Z]/g,'').slice(0,6))} autoCapitalize="characters" placeholder="例如 2330"/></div></label>
        <label className="number-field" htmlFor="entry-price"><span>進場價</span><div><input id="entry-price" type="number" min="0" step="0.01" value={form.entry_price} onChange={event=>update('entry_price',event.target.value)} placeholder="例如 1200"/><em>元</em></div></label>
        <label className="number-field" htmlFor="stop-price"><span>停損價</span><div><input id="stop-price" type="number" min="0" step="0.01" value={form.stop_loss_price} onChange={event=>update('stop_loss_price',event.target.value)} placeholder="例如 1150"/><em>元</em></div></label>
        <label className="number-field" htmlFor="target-price"><span>目標價</span><div><input id="target-price" type="number" min="0" step="0.01" value={form.target_price} onChange={event=>update('target_price',event.target.value)} placeholder="例如 1300"/><em>元</em></div></label>
      </div>
      {!planValid&&numbers.some(value=>value!=null)&&<p className="plan-error">請確認三個價格皆大於 0，且符合「停損價 &lt; 進場價 &lt; 目標價」。</p>}
      {stockScoreError&&<p className="error">{stockScoreError}</p>}
    </form>

    {result?<>
      <section className="stock-score-hero"><div><p className="eyebrow">{result.code}・資料日 {result.as_of}</p><h2>{result.name}</h2><p>{result.summary}</p><small>收盤 {n(result.close)} 元・{result.source}</small></div><div className="score"><span>標的分數</span><strong>{result.score}</strong><em>{result.rating}</em></div></section>
      {result.warning&&<p className="warning">{result.warning}</p>}

      <section className="stock-overview-grid">
        <article><div className="stock-card-title"><h3>大盤環境</h3>{condition(result.market.above_ma20&&result.market.above_ma60)}</div><div className="metrics"><Metric label="加權指數" value={n(result.market.index_close)}/><Metric label="指數 MA20" value={n(result.market.ma20)}/><Metric label="指數 MA60" value={n(result.market.ma60)}/><Metric label="站上雙均線" value={result.market.above_ma20&&result.market.above_ma60?'是':'否'}/></div></article>
        <article><div className="stock-card-title"><h3>日線排列</h3>{condition(result.daily.ideal_order)}</div><div className="metrics"><Metric label="收盤" value={n(result.daily.close)}/><Metric label="MA5" value={n(result.daily.ma5)}/><Metric label="MA20" value={n(result.daily.ma20)}/><Metric label="MA60" value={n(result.daily.ma60)}/></div></article>
        <article><div className="stock-card-title"><h3>週線同步</h3>{condition(result.weekly.bullish)}</div><div className="metrics"><Metric label="週收盤" value={n(result.weekly.close)}/><Metric label="週 MA5" value={n(result.weekly.ma5)}/><Metric label="週 MA13" value={n(result.weekly.ma13)}/><Metric label="週線偏多" value={result.weekly.bullish?'是':'否'}/></div></article>
        <article><div className="stock-card-title"><h3>價格結構</h3>{condition(result.price_structure.higher_high&&result.price_structure.higher_low)}</div><div className="metrics"><Metric label="前高 → 新高" value={`${n(result.price_structure.prior_high)} → ${n(result.price_structure.latest_high)}`}/><Metric label="前低 → 新低" value={`${n(result.price_structure.prior_low)} → ${n(result.price_structure.latest_low)}`}/><Metric label="高點墊高" value={result.price_structure.higher_high?'是':'否'}/><Metric label="低點墊高" value={result.price_structure.higher_low?'是':'否'}/></div></article>
        <article><div className="stock-card-title"><h3>量價關係</h3><span className="condition neutral">量比 {n(result.volume.ratio)}</span></div><div className="metrics"><Metric label="判讀" value={result.volume.assessment}/><Metric label="當日量" value={n(result.volume.current)}/><Metric label="20 日均量" value={n(result.volume.average20)}/><Metric label="漲／跌日均量" value={`${n(result.volume.up_day_average)} / ${n(result.volume.down_day_average)}`}/></div></article>
        <article><div className="stock-card-title"><h3>動能指標</h3><span className="condition neutral">RSI {n(result.momentum.rsi14)}</span></div><div className="metrics"><Metric label="RSI(14)" value={n(result.momentum.rsi14)}/><Metric label="MACD / Signal" value={`${n(result.momentum.macd)} / ${n(result.momentum.macd_signal)}`}/><Metric label="MACD 柱" value={n(result.momentum.macd_histogram)}/><Metric label="K / D" value={`${n(result.momentum.k)} / ${n(result.momentum.d)}`}/></div></article>
      </section>

      <section className="risk-reward-card"><div><p className="eyebrow">TRADE PLAN</p><h3>風險報酬比</h3></div><div className="risk-equation"><div><span>進場</span><strong>{n(result.risk_reward.entry)}</strong></div><div><span>停損</span><strong>{n(result.risk_reward.stop_loss)}</strong></div><div><span>目標</span><strong>{n(result.risk_reward.target)}</strong></div><div className="ratio"><span>報酬 ÷ 風險</span><strong>{n(result.risk_reward.ratio)} : 1</strong></div></div></section>

      <section className="stock-breakdown"><div className="section-title"><div><p className="eyebrow">SCORE BREAKDOWN</p><h2>評分明細</h2></div><p>每一分都可回溯到實際條件</p></div><div className="score-group-grid">{scoreGroups.map(group=>{
        const rows=result.items.filter(item=>item.group===group)
        const earned=rows.reduce((sum,item)=>sum+item.score,0), maximum=rows.reduce((sum,item)=>sum+item.max_score,0)
        return <article className="score-group" key={group}><div className="score-group-title"><h3>{group}</h3><strong>{n(earned)} / {n(maximum)}</strong></div>{rows.map(item=><div className="score-check" key={item.key}><span className={item.passed?'pass':'fail'}>{item.passed?'✓':'–'}</span><div><b>{item.label}</b><small>{item.note}</small></div><strong>{n(item.score)}</strong></div>)}</article>
      })}</div></section>
    </>:<section className="empty stock-empty"><span>⌁</span><h2>先建立交易計畫</h2><p>輸入股票代號、進場價、停損價與目標價後，系統會載入至少 80 個交易日進行評分。</p></section>}
  </div>
}

function businessDaysBetween(startValue,endValue,holidays=[]){
  if(!startValue||!endValue) return 0
  const start=new Date(`${startValue}T00:00:00`), end=new Date(`${endValue}T00:00:00`)
  if(!Number.isFinite(start.getTime())||start>=end) return 0
  const closed=new Set(holidays)
  let count=0
  for(const cursor=new Date(start.getTime()+86400000);cursor<=end;cursor.setDate(cursor.getDate()+1)){
    const iso=`${cursor.getFullYear()}-${String(cursor.getMonth()+1).padStart(2,'0')}-${String(cursor.getDate()).padStart(2,'0')}`
    if(cursor.getDay()!==0&&cursor.getDay()!==6&&!closed.has(iso)) count+=1
  }
  return count
}

function CalculatorPage(){
  const dispatch=useDispatch()
  const {estimate:marketData,estimateStatus,estimateError}=useSelector(state=>state.warrant)
  const [code,setCode]=useState('067185')
  const [inputs,setInputs]=useState({stockPrice:'',volatility:'',valuationDate:'',riskFreeRate:'1.5'})
  const validCode=/^[0-9A-Z]{6}$/.test(code)

  const load=()=>{if(validCode) dispatch(estimateWarrant({code}))}
  useEffect(()=>{
    if(!validCode) return undefined
    const timer=setTimeout(()=>dispatch(estimateWarrant({code})),450)
    return ()=>clearTimeout(timer)
  },[code,dispatch,validCode])
  useEffect(()=>{
    if(!marketData||marketData.contract.code!==code) return
    setInputs({
      stockPrice:String(marketData.stock.price??''),
      volatility:String(Number(marketData.implied_vol*100).toFixed(2)),
      valuationDate:marketData.valuation_date,
      riskFreeRate:String(Number(marketData.risk_free_rate*100).toFixed(2)),
    })
  },[marketData,code])

  const contract=marketData?.contract.code===code?marketData.contract:null
  const tradingDays=contract?businessDaysBetween(inputs.valuationDate,contract.last_trading_date,marketData.market_holidays||[]):0
  const result=contract?calculateBlackScholesWarrant(
    inputs.stockPrice,
    contract.strike_price,
    contract.exercise_ratio,
    tradingDays,
    {volatility:Number(inputs.volatility)/100,riskFreeRate:Number(inputs.riskFreeRate)/100,daysPerYear:252,callPut:contract.call_put},
  ):null
  const update=(key,value)=>setInputs(current=>({...current,[key]:value}))
  const display=value=>value==null?'—':Number(value).toLocaleString('zh-TW',{minimumFractionDigits:2,maximumFractionDigits:4})
  const loading=estimateStatus==='loading'

  return <div className="calculator-page">
    <header className="calculator-header">
      <div><p className="eyebrow">WARRANT PRICE ESTIMATOR</p><h1>權證價格預估</h1><p>輸入權證代號後，自動取得最新條款、標的行情與委買隱含波動率，再以 Black–Scholes 模型計算每單位權證價值。</p></div>
      <div className="formula-chip"><span>市場資料狀態</span><strong>{contract?`${contract.terms_source}・資料日 ${contract.terms_date}`:'輸入代號後自動載入'}</strong></div>
    </header>

    <form className="warrant-lookup" onSubmit={event=>{event.preventDefault();load()}}>
      <label htmlFor="calculator-code">權證代號</label>
      <div className="search"><input id="calculator-code" value={code} onChange={event=>setCode(event.target.value.toUpperCase().replace(/[^0-9A-Z]/g,'').slice(0,6))} autoCapitalize="characters" placeholder="例如 067185 或 03002T"/><button disabled={!validCode||loading}>{loading?'載入行情中…':'查詢並試算'}</button></div>
      {estimateError&&<p className="error">{estimateError}</p>}
    </form>

    {contract&&<section className="contract-card">
      <div className="contract-title"><div><span className={`type-pill ${contract.call_put==='P'?'put':''}`}>{contract.type_label}</span><div><p>{contract.code}</p><h2>{contract.name}</h2></div></div><p>標的 <strong>{contract.underlying_code} {contract.underlying_name}</strong></p></div>
      <div className="contract-metrics"><Metric label="最新履約價" value={`${display(contract.strike_price)} 元`}/><Metric label="最新行使比例" value={contract.exercise_ratio}/><Metric label="最後交易日" value={contract.last_trading_date}/><Metric label="到期日" value={contract.expiry_date}/><Metric label="權證市價" value={`${display(marketData.warrant_quote.price)} 元`}/><Metric label="行情來源" value={marketData.stock.source}/></div>
      {marketData.warning&&<p className="warning inline-warning">{marketData.warning}</p>}
    </section>}

    <section className="calculator-layout">
      <form className="calculator-form" onSubmit={event=>event.preventDefault()}>
        <div className="card-heading"><div><span className="step-number">01</span><div><p>試算情境</p><small>{contract?'資料已帶入，可自行調整':'請先輸入權證代號'}</small></div></div></div>
        <div className="input-grid">
          <label className="number-field" htmlFor="stockPrice"><span>標的股價</span><div><input id="stockPrice" type="number" min="0" step="0.01" disabled={!contract} value={inputs.stockPrice} onChange={event=>update('stockPrice',event.target.value)}/><em>元</em></div></label>
          <label className="number-field" htmlFor="volatility"><span>買價隱含波動率</span><div><input id="volatility" type="number" min="0.01" step="0.01" disabled={!contract} value={inputs.volatility} onChange={event=>update('volatility',event.target.value)}/><em>%</em></div></label>
          <label className="number-field" htmlFor="valuationDate"><span>評價日</span><div><input id="valuationDate" type="date" disabled={!contract} max={contract?.last_trading_date} value={inputs.valuationDate} onChange={event=>update('valuationDate',event.target.value)}/></div></label>
          <label className="number-field" htmlFor="riskFreeRate"><span>無風險利率</span><div><input id="riskFreeRate" type="number" step="0.01" disabled={!contract} value={inputs.riskFreeRate} onChange={event=>update('riskFreeRate',event.target.value)}/><em>%</em></div></label>
        </div>
        <p className="form-note"><span>i</span> 波動率預設採 TWSE 委買隱波；剩餘期間依交易日計算，一年採 252 個交易日。{marketData?.volatility_source&&` 目前波動率來源：${marketData.volatility_source}`}</p>
      </form>

      <section className="result-card" aria-live="polite">
        <div className="card-heading"><div><span className="step-number light">02</span><div><p>試算結果</p><small>{contract?`${contract.type_label}權證・剩餘 ${tradingDays} 個交易日`:'等待權證資料'}</small></div></div></div>
        {result ? <>
          <div className="price-result"><span>Black–Scholes 理論價格</span><strong><small>NT$</small>{display(result.warrantPrice)}</strong><p>每單位權證預估價格</p></div>
          <div className="value-equation">
            <div><span>內含價值</span><strong>{display(result.intrinsicValue)}</strong></div><b>＋</b>
            <div><span>時間價值</span><strong>{display(result.timeValue)}</strong></div><b>＝</b>
            <div><span>理論價格</span><strong>{display(result.warrantPrice)}</strong></div>
          </div>
          <div className="model-assumptions"><span>σ {inputs.volatility}%</span><span>r {inputs.riskFreeRate}%</span><span>{tradingDays} 交易日</span></div>
          {marketData?.warrant_quote.price!=null&&<p className="market-comparison">目前權證市價 {display(marketData.warrant_quote.price)} 元・理論價差 {display(result.warrantPrice-marketData.warrant_quote.price)} 元</p>}
        </>:<div className="invalid-result"><strong>{loading?'正在取得真實行情':'等待完整資料'}</strong><p>輸入六碼權證代號後，系統會自動帶入條款並計算。</p></div>}
      </section>
    </section>

    <section className="pricing-note"><h3>估價口徑</h3><p>履約價與行使比例採最新官方條款，避免除權息、減資或分割後仍用舊資料。結果是模型理論值，不等同造市商實際委買／委賣價；流動性、股利與市場供需仍會造成價差。</p></section>
  </div>
}

function App(){
  const getPage=()=>window.location.hash==='#calculator'?'calculator':window.location.hash==='#stock-score'?'stock-score':'dashboard'
  const [page,setPage]=useState(getPage)
  useEffect(()=>{
    const syncPage=()=>setPage(getPage())
    window.addEventListener('hashchange',syncPage)
    return ()=>window.removeEventListener('hashchange',syncPage)
  },[])
  const navigate=(event,nextPage)=>{event.preventDefault();window.location.hash=nextPage;setPage(nextPage)}
  return <main>
    <SiteNav page={page} onNavigate={navigate}/>
    {page==='calculator'?<CalculatorPage/>:page==='stock-score'?<StockScorePage/>:<Dashboard/>}
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

export { money, Metric, MODEL_ASSUMPTIONS, businessDaysBetween, calculateBlackScholesWarrant, StockScorePage, CalculatorPage, App }

