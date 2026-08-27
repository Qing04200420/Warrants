import React from 'react'

export const money = value => value == null ? '—' : Number(value).toLocaleString('zh-TW',{maximumFractionDigits:2})
export const percent = value => value == null ? '—' : `${(Number(value)*100).toFixed(2)}%`
export const sanitizeWarrantCode = value => String(value).replace(/\D/g,'').slice(0,6)
export const Metric = ({label,value}) => <div className="metric"><span>{label}</span><strong>{value}</strong></div>

export function LoadingSkeleton({label='資料載入中',compact=false}){
  return <section className={`loading-skeleton${compact?' compact':''}`} role="status" aria-label={label}>
    <span className="sr-only">{label}</span>
    <div className="skeleton-hero"><div><i className="skeleton-line short"/><i className="skeleton-line title"/><i className="skeleton-line medium"/></div><i className="skeleton-score"/></div>
    <div className="skeleton-grid">{[0,1,2,3].map(item=><div className="skeleton-card" key={item}><i className="skeleton-line medium"/><i className="skeleton-line"/><i className="skeleton-line"/><i className="skeleton-line short"/></div>)}</div>
  </section>
}
