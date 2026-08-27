import React, {useEffect, useState} from 'react'
import {useDispatch, useSelector} from 'react-redux'
import {estimate as estimateWarrant} from './store'
import {LoadingSkeleton, Metric, sanitizeWarrantCode} from './ui'

const toNumber = value => value == null || value === '' ? null : Number(value)

export const MODEL_ASSUMPTIONS = {volatility:0.3,riskFreeRate:0.015,daysPerYear:365,callPut:'C'}

function normalCdf(value){
  const sign=value<0?-1:1
  const x=Math.abs(value)/Math.sqrt(2)
  const t=1/(1+0.3275911*x)
  const erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-x*x)
  return 0.5*(1+sign*erf)
}

export function calculateBlackScholesWarrant(stockPrice,strikePrice,exerciseRatio,daysToExpiry,assumptions=MODEL_ASSUMPTIONS){
  const values=[stockPrice,strikePrice,exerciseRatio,daysToExpiry].map(toNumber)
  if(values.some(value=>value==null||!Number.isFinite(value)||value<0)) return null

  const [stock,strike,ratio,days]=values
  const callPut=assumptions.callPut==='P'?'P':'C'
  const intrinsicValue=Math.max(callPut==='C'?stock-strike:strike-stock,0)*ratio
  if(days===0||stock===0||strike===0||ratio===0){
    const warrantPrice=strike===0&&callPut==='C'?stock*ratio:intrinsicValue
    return {intrinsicValue,timeValue:Math.max(warrantPrice-intrinsicValue,0),warrantPrice,d1:null,d2:null}
  }

  const {volatility,riskFreeRate,daysPerYear}=assumptions
  if(![volatility,riskFreeRate,daysPerYear].every(Number.isFinite)||volatility<0||daysPerYear<=0) return null
  const timeInYears=days/daysPerYear
  const timeVolatility=volatility*Math.sqrt(timeInYears)
  const d1=(Math.log(stock/strike)+(riskFreeRate+volatility**2/2)*timeInYears)/timeVolatility
  const d2=d1-timeVolatility
  const optionValue=callPut==='C'
    ? stock*normalCdf(d1)-strike*Math.exp(-riskFreeRate*timeInYears)*normalCdf(d2)
    : strike*Math.exp(-riskFreeRate*timeInYears)*normalCdf(-d2)-stock*normalCdf(-d1)
  const warrantPrice=Math.max(optionValue*ratio,intrinsicValue)
  return {intrinsicValue,timeValue:Math.max(warrantPrice-intrinsicValue,0),warrantPrice,d1,d2}
}

export function businessDaysBetween(startValue,endValue,holidays=[]){
  if(!startValue||!endValue) return 0
  const start=new Date(`${startValue}T00:00:00`),end=new Date(`${endValue}T00:00:00`)
  if(!Number.isFinite(start.getTime())||start>=end) return 0
  const closed=new Set(holidays)
  let count=0
  for(const cursor=new Date(start.getTime()+86400000);cursor<=end;cursor.setDate(cursor.getDate()+1)){
    const iso=`${cursor.getFullYear()}-${String(cursor.getMonth()+1).padStart(2,'0')}-${String(cursor.getDate()).padStart(2,'0')}`
    if(cursor.getDay()!==0&&cursor.getDay()!==6&&!closed.has(iso)) count+=1
  }
  return count
}

export function CalculatorPage(){
  const dispatch=useDispatch()
  const {estimate:marketData,estimateStatus,estimateError}=useSelector(state=>state.warrant)
  const [code,setCode]=useState('067185')
  const [inputs,setInputs]=useState({stockPrice:'',volatility:'',valuationDate:'',riskFreeRate:'1.5'})
  const validCode=/^\d{6}$/.test(code)

  const load=()=>{if(validCode)dispatch(estimateWarrant({code}))}
  useEffect(()=>{
    if(!validCode)return undefined
    const timer=setTimeout(()=>dispatch(estimateWarrant({code})),450)
    return ()=>clearTimeout(timer)
  },[code,dispatch,validCode])
  useEffect(()=>{
    if(!marketData||marketData.contract.code!==code)return
    setInputs({
      stockPrice:String(marketData.stock.price??''),
      volatility:String(Number(marketData.implied_vol*100).toFixed(2)),
      valuationDate:marketData.valuation_date,
      riskFreeRate:String(Number(marketData.risk_free_rate*100).toFixed(2)),
    })
  },[marketData,code])

  const contract=marketData?.contract.code===code?marketData.contract:null
  const tradingDays=contract?businessDaysBetween(inputs.valuationDate,contract.last_trading_date,marketData.market_holidays||[]):0
  const result=contract?calculateBlackScholesWarrant(inputs.stockPrice,contract.strike_price,contract.exercise_ratio,tradingDays,{volatility:Number(inputs.volatility)/100,riskFreeRate:Number(inputs.riskFreeRate)/100,daysPerYear:252,callPut:contract.call_put}):null
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
      <div className="search"><input id="calculator-code" value={code} onChange={event=>setCode(sanitizeWarrantCode(event.target.value))} inputMode="numeric" pattern="[0-9]{6}" maxLength="6" placeholder="例如 067185"/><button disabled={!validCode||loading}>{loading?'載入行情中…':'查詢並試算'}</button></div>
      {estimateError&&<p className="error">{estimateError}</p>}
    </form>

    {loading?<LoadingSkeleton label="正在載入權證條款與行情"/>:<>
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
          {result?<>
            <div className="price-result"><span>Black–Scholes 理論價格</span><strong><small>NT$</small>{display(result.warrantPrice)}</strong><p>每單位權證預估價格</p></div>
            <div className="value-equation"><div><span>內含價值</span><strong>{display(result.intrinsicValue)}</strong></div><b>＋</b><div><span>時間價值</span><strong>{display(result.timeValue)}</strong></div><b>＝</b><div><span>理論價格</span><strong>{display(result.warrantPrice)}</strong></div></div>
            <div className="model-assumptions"><span>σ {inputs.volatility}%</span><span>r {inputs.riskFreeRate}%</span><span>{tradingDays} 交易日</span></div>
            {marketData?.warrant_quote.price!=null&&<p className="market-comparison">目前權證市價 {display(marketData.warrant_quote.price)} 元・理論價差 {display(result.warrantPrice-marketData.warrant_quote.price)} 元</p>}
          </>:<div className="invalid-result"><strong>等待完整資料</strong><p>輸入六碼數字權證代號後，系統會自動帶入條款並計算。</p></div>}
        </section>
      </section>

      <section className="pricing-note"><h3>估價口徑</h3><p>履約價與行使比例採最新官方條款，避免除權息、減資或分割後仍用舊資料。結果是模型理論值，不等同造市商實際委買／委賣價；流動性、股利與市場供需仍會造成價差。</p></section>
    </>}
  </div>
}

export default CalculatorPage
