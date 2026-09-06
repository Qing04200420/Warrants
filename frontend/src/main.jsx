import React, {lazy, Suspense, useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Provider, useDispatch, useSelector} from 'react-redux'
import {analyze, clearHistory, loadHistory, recommendWarrants, scoreStock, store} from './store'
import {LoadingSkeleton, Metric, money, percent, sanitizeWarrantCode} from './ui'
import './styles.css'
import './not-found.css'
import './trading-theme.css'

const toNumber = value => value == null || value === '' ? null : Number(value)
const CalculatorPage=lazy(()=>import('./calculator'))

function SiteNav({page, onNavigate}) {
  return <nav className="site-nav" aria-label="主要導覽">
    <a className="brand" href="#stock-score" onClick={event=>onNavigate(event,'stock-score')}>
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
  const dispatch=useDispatch(), {current,history,historyStatus,status,error}=useSelector(s=>s.warrant)
  const [code,setCode]=useState('067185')
  const numericHistory=history.filter(item=>/^\d{6}$/.test(item.warrant_code))
  useEffect(()=>{dispatch(loadHistory())},[dispatch])
  useEffect(()=>{if(/^\d{6}$/.test(current?.warrant_code||''))setCode(current.warrant_code)},[current?.warrant_code])
  const submit=e=>{e.preventDefault();if(/^\d{6}$/.test(code))dispatch(analyze(code))}
  return <>
    <header><div><p className="eyebrow">TAIWAN WARRANT LAB</p><h1>權證評分儀表板</h1><p>把複雜的風險參數，整理成一眼能比較的分數。</p></div><div className="market-dot">● 台股資料</div></header>
    <form className="score-form" onSubmit={submit}><label htmlFor="code">輸入六碼數字權證代號</label><div className="search"><input id="code" value={code} onChange={e=>setCode(sanitizeWarrantCode(e.target.value))} inputMode="numeric" pattern="[0-9]{6}" maxLength="6" placeholder="例如 067185"/><button disabled={status==='loading'||code.length!==6}>{status==='loading'?'分析中…':'開始評分'}</button></div>{error&&<p className="error">{error}</p>}</form>
    {status==='loading'?<LoadingSkeleton label="正在載入權證評分"/>:current ? <>
      <section className="hero-card"><div><p className="eyebrow">{current.warrant_code}</p><h2>{current.warrant_name}</h2><p>對應標的　{current.stock.code} {current.stock.name}</p></div><div className="score"><span>綜合分數</span><strong>{current.score}</strong><em>{current.rating}</em></div></section>
      {current.warning&&<p className="warning">{current.warning}</p>}
      <section className="grid"><article><h3>標的行情</h3><div className="metrics"><Metric label="股價" value={money(current.stock.price)}/><Metric label="開盤" value={money(current.stock.open)}/><Metric label="最高" value={money(current.stock.high)}/><Metric label="最低" value={money(current.stock.low)}/><Metric label="交易量" value={money(current.stock.volume)}/><Metric label="來源" value={current.stock.source}/></div></article>
      <article><h3>權證參數</h3><div className="metrics"><Metric label="距到期日" value={`${current.metrics.days_to_expiry} 天`}/><Metric label="目前履約價" value={money(current.metrics.strike_price)}/><Metric label="權證價格" value={money(current.metrics.warrant_price)}/><Metric label="執行比例" value={current.metrics.exercise_ratio}/><Metric label="Delta" value={current.metrics.delta}/><Metric label="Theta" value={current.metrics.theta}/><Metric label="價內外" value={`${current.metrics.moneyness_percent}% ${current.metrics.moneyness_label}`}/><Metric label="有效槓桿" value={`${current.metrics.effective_leverage} 倍`}/></div></article>
      <article><h3>TWSE 盤後造市資料</h3><div className="metrics"><Metric label="委買隱含波動率" value={percent(current.metrics.implied_vol)}/><Metric label={current.metrics.iv_std_source==='twse_14d_max_change_proxy'?'14 日 IV 最大變動（暫代）':'14 日 IV 標準差'} value={percent(current.metrics.iv_std)}/><Metric label="買賣價差比" value={percent(current.metrics.bid_ask_spread)}/><Metric label="委託買量" value={money(current.metrics.bid_volume)}/><Metric label="委託賣量" value={money(current.metrics.ask_volume)}/><Metric label="資料日期" value={current.metrics.market_data_date||'—'}/><Metric label="來源" value={current.metrics.market_data_source||'—'}/></div></article></section>
      <section className="breakdown"><h3>評分拆解</h3>{current.score_items.map(x=><div className="bar-row" key={x.key}><div><b>{x.label}</b><small>{x.note}</small></div><div className="bar"><i style={{width:`${x.score/x.max_score*100}%`}}/></div><strong>{x.score}/{x.max_score}</strong></div>)}</section>
    </>:<section className="empty"><span>⌁</span><h2>從一檔權證開始</h2><p>系統會保留每次評分，方便觀察條件隨時間變化。</p></section>}
    <section className="history"><div className="section-title"><h3>歷史紀錄</h3>{numericHistory.length>0&&<button className="ghost" onClick={()=>dispatch(clearHistory())}>清除</button>}</div>{historyStatus==='loading'?<div className="history-skeleton" role="status" aria-label="正在載入歷史紀錄"><i className="skeleton-line"/><i className="skeleton-line medium"/><i className="skeleton-line"/></div>:numericHistory.length===0?<p className="muted">尚無紀錄</p>:<div className="table-wrap"><table><thead><tr><th>時間</th><th>權證</th><th>標的</th><th>價格</th><th>分數</th></tr></thead><tbody>{numericHistory.map(x=><tr key={x.id} onClick={()=>{setCode(x.warrant_code);dispatch(analyze(x.warrant_code))}}><td>{new Date(x.analyzed_at).toLocaleString('zh-TW')}</td><td>{x.warrant_code} {x.warrant_name}</td><td>{x.stock.code} {x.stock.name}</td><td>{money(x.metrics.warrant_price)}</td><td><b>{x.score}</b> {x.rating}</td></tr>)}</tbody></table></div>}</section>
  </>
}

const scoreGroups=['大盤環境','日線趨勢','週線趨勢','價格結構','量價關係','動能指標','風險報酬']

function StockScorePage(){
  const dispatch=useDispatch()
  const {stockScore,stockScoreStatus,stockScoreError,warrantRecommendations,recommendationStatus,recommendationError}=useSelector(state=>state.warrant)
  const [form,setForm]=useState({code:'2330',entry_price:'',stop_loss_price:'',target_price:''})
  const update=(key,value)=>setForm(current=>({...current,[key]:value}))
  const numbers=[form.entry_price,form.stop_loss_price,form.target_price].map(toNumber)
  const planValid=numbers.every(value=>value!=null&&Number.isFinite(value)&&value>0)&&numbers[1]<numbers[0]&&numbers[0]<numbers[2]
  const codeValid=/^[0-9A-Z]{4,6}$/.test(form.code)
  const loading=stockScoreStatus==='loading'
  const result=stockScore?.code===form.code?stockScore:null
  const recommendationResult=warrantRecommendations?.underlying_code===result?.code?warrantRecommendations:null
  const submit=event=>{
    event.preventDefault()
    if(codeValid&&planValid) dispatch(scoreStock({...form,entry_price:numbers[0],stop_loss_price:numbers[1],target_price:numbers[2]}))
  }
  const n=value=>value==null?'—':Number(value).toLocaleString('zh-TW',{maximumFractionDigits:2})
  const condition=value=><span className={`condition ${value?'pass':'fail'}`}>{value?'成立':'未成立'}</span>
  const requestRecommendations=()=>{
    if(!result) return
    dispatch(recommendWarrants({underlying_code:result.code,underlying_name:result.name,stock_price:result.close,limit:5}))
  }
  const openWarrantScore=code=>{
    dispatch(analyze(code))
    window.location.hash='#dashboard'
  }

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

    {loading?<LoadingSkeleton label="正在分析股票歷史行情"/>:result?<>
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

      <section className="warrant-recommendation" aria-live="polite">
        <div className="recommendation-heading"><div><p className="eyebrow">WARRANT MATCH</p><h2>此標的的認購權證候選</h2><p>以收盤價 {n(result.close)} 元比對履約價與剩餘期間，先做基本條款初選。</p></div><button type="button" onClick={requestRecommendations} disabled={recommendationStatus==='loading'}>{recommendationStatus==='loading'?'篩選權證中…':'推薦此標的權證'}</button></div>
        {recommendationError&&<p className="recommendation-error">{recommendationError}</p>}
        {recommendationStatus==='loading'?<div className="recommendation-grid skeleton-recommendations">{[0,1].map(item=><div className="skeleton-card" key={item}><i className="skeleton-line short"/><i className="skeleton-line title"/><i className="skeleton-line"/><i className="skeleton-line medium"/></div>)}</div>:recommendationResult&&(recommendationResult.recommendations.length>0?<>
          <div className="recommendation-grid">{recommendationResult.recommendations.map(item=><article className="recommendation-card" key={item.code}>
            <div className="recommendation-card-title"><div><span>{item.code}</span><h3>{item.name}</h3></div><strong aria-label={`條款符合度 ${n(item.match_score)} 分`} title="條款符合度">{n(item.match_score)}</strong></div>
            <p>{item.reason}</p>
            <dl><div><dt>履約價</dt><dd>{n(item.strike_price)} 元</dd></div><div><dt>行使比例</dt><dd>{n(item.exercise_ratio)}</dd></div><div><dt>最後交易日</dt><dd>{item.last_trading_date}</dd></div></dl>
            <button type="button" onClick={()=>openWarrantScore(item.code)}>查看權證評分</button>
          </article>)}</div>
          <p className="recommendation-notice">{recommendationResult.notice}</p>
        </>:<p className="recommendation-empty">目前找不到剩餘至少 30 天、且履約價在現價 ±20% 內的上市認購權證。</p>)}
      </section>

      <section className="stock-breakdown"><div className="section-title"><div><p className="eyebrow">SCORE BREAKDOWN</p><h2>評分明細</h2></div><p>每一分都可回溯到實際條件</p></div><div className="score-group-grid">{scoreGroups.map(group=>{
        const rows=result.items.filter(item=>item.group===group)
        const earned=rows.reduce((sum,item)=>sum+item.score,0), maximum=rows.reduce((sum,item)=>sum+item.max_score,0)
        return <article className="score-group" key={group}><div className="score-group-title"><h3>{group}</h3><strong>{n(earned)} / {n(maximum)}</strong></div>{rows.map(item=><div className="score-check" key={item.key}><span className={item.passed?'pass':'fail'}>{item.passed?'✓':'–'}</span><div><b>{item.label}</b><small>{item.note}</small></div><strong>{n(item.score)}</strong></div>)}</article>
      })}</div></section>
    </>:<section className="empty stock-empty"><span>⌁</span><h2>先建立交易計畫</h2><p>輸入股票代號、進場價、停損價與目標價後，系統會載入至少 80 個交易日進行評分。</p></section>}
  </div>
}

function NotFoundPage({onNavigate}) {
  return <section className="not-found-page">
    <p className="eyebrow">PAGE NOT FOUND</p>
    <strong>404</strong>
    <h1>找不到此頁面</h1>
    <p>您輸入的網址不存在，或頁面已經移動。</p>
    <a href="#stock-score" onClick={event=>onNavigate(event,'stock-score')}>返回標的評分</a>
  </section>
}

function getPageFromHash(hash) {
  if (!hash || hash==='#' || hash==='#stock-score') return 'stock-score'
  if (hash==='#dashboard') return 'dashboard'
  if (hash==='#calculator') return 'calculator'
  return 'not-found'
}

function App(){
  const getPage=()=>getPageFromHash(window.location.hash)
  const [page,setPage]=useState(getPage)
  useEffect(()=>{
    const syncPage=()=>setPage(getPage())
    window.addEventListener('hashchange',syncPage)
    return ()=>window.removeEventListener('hashchange',syncPage)
  },[])
  const navigate=(event,nextPage)=>{event.preventDefault();window.location.hash=nextPage;setPage(nextPage)}
  return <main>
    <SiteNav page={page} onNavigate={navigate}/>
    {page==='calculator'
      ? <Suspense fallback={<LoadingSkeleton label="正在載入價格試算頁"/>}><CalculatorPage/></Suspense>
      : page==='stock-score'
        ? <StockScorePage/>
        : page==='dashboard'
          ? <Dashboard/>
          : <NotFoundPage onNavigate={navigate}/>
    }
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

export {money,Metric,Dashboard,StockScorePage,CalculatorPage,NotFoundPage,getPageFromHash,App}

